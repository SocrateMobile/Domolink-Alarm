"""Interfaces with Domolink Alarm."""
import asyncio
import logging
from datetime import timedelta
import time

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
    CodeFormat,
)
from homeassistant.const import EVENT_STATE_CHANGED
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event, async_call_later, async_track_time_interval
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    DOMAIN,
    CONF_OPENING_SENSORS,
    CONF_MOTION_SENSORS,
    CONF_CAMERAS,
    CONF_TAMPER_SENSORS,
    CONF_SIRENS,
    CONF_LIGHTS,
    CONF_MEDIA_PLAYERS,
    CONF_NOTIFY_SERVICES,
    CONF_USERS_CODES,
    CONF_DURESS_CODE,
    CONF_BYPASS_ALLOWED,
    CONF_HEALTH_CHECK,
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
        self._health_check_remove = None

        self._failed_attempts = 0
        self._blocked_until = 0

        self._users = {}  # dict of code: name
        self._duress_code = ""

        self._load_config()

    def _load_config(self):
        data = self._entry.data
        options = self._entry.options

        # Users and Codes parsing
        users_str = options.get(CONF_USERS_CODES, data.get(CONF_USERS_CODES, ""))
        self._users = {}
        for pair in users_str.split(","):
            if ":" in pair:
                name, code = pair.split(":", 1)
                self._users[code.strip()] = name.strip()
                
        self._duress_code = str(options.get(CONF_DURESS_CODE, data.get(CONF_DURESS_CODE, ""))).strip()
        
        self._exit_delay = options.get(CONF_EXIT_DELAY, data.get(CONF_EXIT_DELAY, 30))
        self._entry_delay = options.get(CONF_ENTRY_DELAY, data.get(CONF_ENTRY_DELAY, 30))
        self._siren_duration = options.get(CONF_SIREN_DURATION, data.get(CONF_SIREN_DURATION, 180))
        self._bypass_allowed = options.get(CONF_BYPASS_ALLOWED, data.get(CONF_BYPASS_ALLOWED, False))
        self._health_check = options.get(CONF_HEALTH_CHECK, data.get(CONF_HEALTH_CHECK, True))

        self._opening_sensors = data.get(CONF_OPENING_SENSORS) or []
        self._motion_sensors = data.get(CONF_MOTION_SENSORS) or []
        self._cameras = data.get(CONF_CAMERAS) or []
        self._tamper_sensors = data.get(CONF_TAMPER_SENSORS) or []

        self._sirens = data.get(CONF_SIRENS) or []
        self._lights = data.get(CONF_LIGHTS) or []
        self._media_players = data.get(CONF_MEDIA_PLAYERS) or []
        self._notify_services = data.get(CONF_NOTIFY_SERVICES) or []

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

        # Start health check if enabled
        if self._health_check:
            self._health_check_remove = async_track_time_interval(
                self.hass, self._async_perform_health_check, timedelta(hours=4)
            )
            self.async_on_remove(self._health_check_remove)

    async def _async_perform_health_check(self, now=None):
        """Check battery and availability of sensors."""
        all_sensors = self._opening_sensors + self._motion_sensors + self._tamper_sensors
        warnings = []
        for sensor_id in all_sensors:
            state = self.hass.states.get(sensor_id)
            if not state or state.state in ("unavailable", "unknown"):
                warnings.append(f"{sensor_id} est indisponible.")
                continue
            battery = state.attributes.get("battery")
            if battery is not None:
                try:
                    if int(battery) < 10:
                        warnings.append(f"{sensor_id} batterie faible ({battery}%).")
                except ValueError:
                    pass

        if warnings:
            notify_msg = "Health Check Alarme: \n" + "\n".join(warnings)
            await self._async_send_notification(notify_msg)

    async def _async_send_notification(self, message):
        """Helper to send notifications."""
        for notify_service in self._notify_services:
            domain, service = notify_service.split(".", 1) if "." in notify_service else ("notify", notify_service)
            try:
                await self.hass.services.async_call(domain, service, {"message": message})
            except Exception as e:
                _LOGGER.error(f"Failed to call notify service {notify_service}: {e}")

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
                        
                        # Pre-alarm feedback (Lights + TTS)
                        await self._async_pre_alarm_feedback()
                        
                        self._pending_task = async_call_later(
                            self.hass, self._entry_delay, lambda now: self.hass.async_create_task(self._async_trigger_alarm(entity_id))
                        )
                else:
                    await self._async_trigger_alarm(entity_id)

    async def _async_pre_alarm_feedback(self):
        """Flash lights and warn during pending state."""
        if self._lights:
            try:
                await self.hass.services.async_call("light", "turn_on", {"entity_id": self._lights, "flash": "short"})
            except:
                await self.hass.services.async_call("homeassistant", "turn_on", {"entity_id": self._lights})

        for player in self._media_players:
            try:
                await self.hass.services.async_call("tts", "google_translate_say", {"entity_id": player, "message": "Veuillez désarmer l'alarme immédiatement."})
            except:
                pass

    async def _async_trigger_alarm(self, triggering_entity):
        """Trigger the alarm."""
        if self._state == AlarmControlPanelState.TRIGGERED:
            return

        self._state = AlarmControlPanelState.TRIGGERED
        self.async_write_ha_state()

        if self._pending_task:
            self._pending_task()
            self._pending_task = None

        state = self.hass.states.get(triggering_entity)
        name = state.name if state else triggering_entity
        
        notify_msg = f"🚨 INTRUSION DÉTECTÉE 🚨\nCapteur : {name}"
        await self._async_send_notification(notify_msg)

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
                    pass

        # 4. Siren & Panic Lights
        if self._pre_trigger_state == AlarmControlPanelState.ARMED_AWAY or triggering_entity in self._tamper_sensors:
            if self._sirens:
                try:
                    await self.hass.services.async_call("homeassistant", "turn_on", {"entity_id": self._sirens})
                    self._siren_task = async_call_later(
                        self.hass, self._siren_duration, self._async_turn_off_siren
                    )
                except Exception as e:
                    _LOGGER.error(f"Failed to turn on sirens: {e}")
            if self._lights:
                try:
                    # Rouge si supporté, sinon allumage
                    await self.hass.services.async_call("light", "turn_on", {"entity_id": self._lights, "color_name": "red", "brightness": 255})
                except:
                    await self.hass.services.async_call("homeassistant", "turn_on", {"entity_id": self._lights})

    @callback
    async def _async_turn_off_siren(self, now=None):
        if self._sirens:
            await self.hass.services.async_call("homeassistant", "turn_off", {"entity_id": self._sirens})
        if self._lights:
            await self.hass.services.async_call("homeassistant", "turn_off", {"entity_id": self._lights})
        self._siren_task = None

    def _validate_code(self, code):
        """Validate given code and return user name if valid."""
        if not code:
            return None
            
        current_time = time.time()
        if self._blocked_until > current_time:
            return None

        # Check Duress
        if self._duress_code and code == self._duress_code:
            return "DURESS"

        user_name = self._users.get(code)
        if user_name:
            self._failed_attempts = 0
            return user_name
        else:
            self._failed_attempts += 1
            if self._failed_attempts >= 3:
                self._blocked_until = current_time + 300 # Block for 5 minutes
                self.hass.async_create_task(self._async_send_notification("⚠️ Tentatives de désarmement bloquées (Brute-force). Pavé numérique verrouillé 5 minutes."))
            return None

    async def async_alarm_disarm(self, code=None):
        """Send disarm command."""
        user = self._validate_code(code)
        if not user:
            _LOGGER.warning("Invalid code provided for disarm")
            return

        if user == "DURESS":
            # Silent SOS
            await self._async_send_notification("🆘 ALERTE SOS SILENCIEUSE (Code de détresse utilisé) 🆘")
            # We continue to disarm silently so the intruder doesn't know

        self._state = AlarmControlPanelState.DISARMED
        self.async_write_ha_state()

        if self._arming_task:
            self._arming_task()
            self._arming_task = None
        if self._pending_task:
            self._pending_task()
            self._pending_task = None
        
        await self._async_turn_off_siren()

        if user != "DURESS":
            # Personalized TTS greeting
            for player in self._media_players:
                try:
                    await self.hass.services.async_call("tts", "google_translate_say", {"entity_id": player, "message": f"Alarme désarmée. Bienvenue {user}."})
                except:
                    pass

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
