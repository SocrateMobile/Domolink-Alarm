"""Interfaces with Domolink Alarm."""
import asyncio
import logging
from datetime import timedelta

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
    CodeFormat,
)
from homeassistant.const import EVENT_STATE_CHANGED
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event, async_call_later
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    DOMAIN,
    CONF_OPENING_SENSORS,
    CONF_MOTION_SENSORS,
    CONF_CAMERAS,
    CONF_TAMPER_SENSORS,
    CONF_SIRENS,
    CONF_MEDIA_PLAYERS,
    CONF_NOTIFY_SERVICES,
    CONF_MAIN_CODE,
    CONF_SECONDARY_CODES,
    CONF_BYPASS_ALLOWED,
    CONF_EXIT_DELAY,
    CONF_ENTRY_DELAY,
    CONF_SIREN_DURATION,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities):
    """Set up the alarm control panel from a config entry."""
    async_add_entities([DomolinkAlarm(hass, entry)], True)


class DomolinkAlarm(AlarmControlPanelEntity, RestoreEntity):
    """Representation of a Domolink Alarm."""

    _attr_name = "Domolink Alarm"
    _attr_has_entity_name = True
    _attr_code_format = CodeFormat.NUMBER
    _attr_supported_features = (
        AlarmControlPanelEntityFeature.ARM_HOME
        | AlarmControlPanelEntityFeature.ARM_AWAY
        | AlarmControlPanelEntityFeature.ARM_NIGHT
        | AlarmControlPanelEntityFeature.TRIGGER
    )

    def __init__(self, hass: HomeAssistant, entry):
        """Initialize the alarm."""
        self.hass = hass
        self._entry = entry
        self._state = AlarmControlPanelState.DISARMED
        self._pre_trigger_state = AlarmControlPanelState.DISARMED
        self._unique_id = f"domolink_alarm_{entry.entry_id}"

        self._siren_task = None
        self._arming_task = None
        self._pending_task = None

        self._load_config()

    def _load_config(self):
        data = self._entry.data
        options = self._entry.options

        # Options override data
        self._main_code = options.get(CONF_MAIN_CODE, data.get(CONF_MAIN_CODE))
        secondary = options.get(CONF_SECONDARY_CODES, data.get(CONF_SECONDARY_CODES, ""))
        self._secondary_codes = [c.strip() for c in secondary.split(",") if c.strip()]
        
        self._exit_delay = options.get(CONF_EXIT_DELAY, data.get(CONF_EXIT_DELAY, 30))
        self._entry_delay = options.get(CONF_ENTRY_DELAY, data.get(CONF_ENTRY_DELAY, 30))
        self._siren_duration = options.get(CONF_SIREN_DURATION, data.get(CONF_SIREN_DURATION, 180))
        self._bypass_allowed = options.get(CONF_BYPASS_ALLOWED, data.get(CONF_BYPASS_ALLOWED, False))

        self._opening_sensors = data.get(CONF_OPENING_SENSORS, [])
        self._motion_sensors = data.get(CONF_MOTION_SENSORS, [])
        self._cameras = data.get(CONF_CAMERAS, [])
        self._tamper_sensors = data.get(CONF_TAMPER_SENSORS, [])

        self._sirens = data.get(CONF_SIRENS, [])
        self._media_players = data.get(CONF_MEDIA_PLAYERS, [])
        self._notify_services = data.get(CONF_NOTIFY_SERVICES, [])

    @property
    def unique_id(self):
        """Return a unique ID to use for this entity."""
        return self._unique_id

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def code_arm_required(self):
        """Whether the code is required for arm actions."""
        return False

    async def async_added_to_hass(self):
        """Run when entity about to be added."""
        await super().async_added_to_hass()
        state = await self.async_get_last_state()
        if state:
            self._state = state.state

        # Track sensor changes
        all_sensors = self._opening_sensors + self._motion_sensors + self._tamper_sensors
        if all_sensors:
            self.async_on_remove(
                async_track_state_change_event(
                    self.hass, all_sensors, self._async_sensor_changed
                )
            )

    async def _async_sensor_changed(self, event):
        """Handle sensor state changes."""
        entity_id = event.data.get("entity_id")
        new_state = event.data.get("new_state")

        if not new_state or new_state.state not in ("on", "open", "true"):
            return

        _LOGGER.debug(f"Sensor {entity_id} triggered")

        # Tamper triggers immediately regardless of state
        if entity_id in self._tamper_sensors:
            _LOGGER.warning(f"Tamper detected on {entity_id}")
            await self._async_trigger_alarm(entity_id)
            return

        if self._state == AlarmControlPanelState.DISARMED:
            return

        # Handle different modes
        if self._state == AlarmControlPanelState.ARMED_HOME:
            if entity_id in self._opening_sensors:
                await self._async_trigger_alarm(entity_id)
        elif self._state in (AlarmControlPanelState.ARMED_AWAY, AlarmControlPanelState.ARMED_NIGHT):
            if entity_id in self._opening_sensors or entity_id in self._motion_sensors:
                # If away, we have entry delay
                if self._state == AlarmControlPanelState.ARMED_AWAY and self._entry_delay > 0:
                    if self._pending_task is None:
                        _LOGGER.info("Starting entry delay")
                        self._pre_trigger_state = self._state
                        self._state = AlarmControlPanelState.PENDING
                        self.async_write_ha_state()
                        self._pending_task = async_call_later(
                            self.hass, self._entry_delay, lambda now: self.hass.async_create_task(self._async_trigger_alarm(entity_id))
                        )
                else:
                    await self._async_trigger_alarm(entity_id)

    async def _async_trigger_alarm(self, triggering_entity):
        """Trigger the alarm."""
        if self._state == AlarmControlPanelState.TRIGGERED:
            return

        self._state = AlarmControlPanelState.TRIGGERED
        self.async_write_ha_state()

        if self._pending_task:
            self._pending_task()
            self._pending_task = None

        triggered_sensors = [triggering_entity] # In a real scenario, we might collect multiple
        sensor_names = []
        for entity_id in triggered_sensors:
            state = self.hass.states.get(entity_id)
            name = state.name if state else entity_id
            sensor_names.append(name)

        if len(sensor_names) == 1:
            notify_msg = f"Intrusion détectée : {sensor_names[0]}"
        else:
            notify_msg = f"Détection multiple : {', '.join(sensor_names)}"

        # 1. Notifications
        for notify_service in self._notify_services:
            domain, service = notify_service.split(".", 1) if "." in notify_service else ("notify", notify_service)
            try:
                await self.hass.services.async_call(domain, service, {"message": notify_msg})
            except Exception as e:
                _LOGGER.error(f"Failed to call notify service {notify_service}: {e}")

        # 2. Camera Recording
        for camera in self._cameras:
            try:
                await self.hass.services.async_call("camera", "record", {"entity_id": camera, "duration": 30})
            except Exception as e:
                _LOGGER.error(f"Failed to record camera {camera}: {e}")

        # 3. TTS (Only Away or Night modes for TTS in requirements)
        if self._pre_trigger_state in (AlarmControlPanelState.ARMED_AWAY, AlarmControlPanelState.ARMED_NIGHT, AlarmControlPanelState.DISARMED) or triggering_entity in self._tamper_sensors:
            tts_message = "Alerte intrusion détectée, le propriétaire et la police ont été prévenus. Les enregistrements photos et vidéo ont été réalisés à l'intérieur mais aussi à l'extérieur dès que vous avez pénétré dans la propriété. Tout est d'ores et déjà sauvegardé en ligne, sur des serveurs sécurisés."
            for player in self._media_players:
                try:
                    await self.hass.services.async_call("tts", "google_translate_say", {"entity_id": player, "message": tts_message})
                except Exception as e:
                    _LOGGER.error(f"Failed to play TTS on {player}: {e}")

        # 4. Siren (Only Away mode or Tamper)
        if self._pre_trigger_state == AlarmControlPanelState.ARMED_AWAY or triggering_entity in self._tamper_sensors:
            if self._sirens:
                try:
                    await self.hass.services.async_call("homeassistant", "turn_on", {"entity_id": self._sirens})
                    self._siren_task = async_call_later(
                        self.hass, self._siren_duration, self._async_turn_off_siren
                    )
                except Exception as e:
                    _LOGGER.error(f"Failed to turn on sirens: {e}")

    @callback
    async def _async_turn_off_siren(self, now=None):
        if self._sirens:
            await self.hass.services.async_call("homeassistant", "turn_off", {"entity_id": self._sirens})
        self._siren_task = None

    def _validate_code(self, code, state):
        """Validate given code."""
        if not code:
            return False
        return code == str(self._main_code) or code in self._secondary_codes

    async def async_alarm_disarm(self, code=None):
        """Send disarm command."""
        if not self._validate_code(code, AlarmControlPanelState.DISARMED):
            _LOGGER.warning("Invalid code provided for disarm")
            return

        self._state = AlarmControlPanelState.DISARMED
        self.async_write_ha_state()

        if self._arming_task:
            self._arming_task()
            self._arming_task = None
        if self._pending_task:
            self._pending_task()
            self._pending_task = None
        
        await self._async_turn_off_siren()

    async def _check_bypass(self):
        """Check if sensors are open before arming."""
        open_sensors = []
        for sensor in self._opening_sensors:
            state = self.hass.states.get(sensor)
            if state and state.state in ("on", "open", "true"):
                open_sensors.append(sensor)
        
        if open_sensors and not self._bypass_allowed:
            _LOGGER.warning(f"Cannot arm, sensors open: {open_sensors}")
            return False
        return True

    async def async_alarm_arm_home(self, code=None):
        """Send arm home command."""
        if not await self._check_bypass():
            return
        self._state = AlarmControlPanelState.ARMED_HOME
        self.async_write_ha_state()

    async def async_alarm_arm_away(self, code=None):
        """Send arm away command."""
        if not await self._check_bypass():
            return
        
        if self._exit_delay > 0:
            self._state = AlarmControlPanelState.ARMING
            self.async_write_ha_state()
            self._arming_task = async_call_later(
                self.hass, self._exit_delay, self._async_arm_away_complete
            )
        else:
            await self._async_arm_away_complete()

    @callback
    async def _async_arm_away_complete(self, now=None):
        self._state = AlarmControlPanelState.ARMED_AWAY
        self._pre_trigger_state = AlarmControlPanelState.ARMED_AWAY
        self.async_write_ha_state()
        self._arming_task = None

    async def async_alarm_arm_night(self, code=None):
        """Send arm night command."""
        if not await self._check_bypass():
            return
        self._state = AlarmControlPanelState.ARMED_NIGHT
        self.async_write_ha_state()
