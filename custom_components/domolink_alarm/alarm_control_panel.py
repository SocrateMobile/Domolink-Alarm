"""Interfaces with Domolink Alarm."""
import os
import logging
from datetime import timedelta

import asyncio
from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
    CodeFormat,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_call_later,
    async_track_time_interval,
)
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util.dt import utcnow

from .const import (
    DOMAIN,
    CONF_NAME,
    DEFAULT_NAME,
    CONF_OPENING_SENSORS,
    CONF_OPENING_SENSORS_LABELS,
    CONF_NIGHT_SENSORS,
    CONF_NIGHT_SENSORS_LABELS,
    CONF_PERSONS,
    CONF_PERSONS_LABELS,
    CONF_MOTION_SENSORS,
    CONF_MOTION_SENSORS_LABELS,
    CONF_CAMERAS,
    CONF_CAMERAS_LABELS,
    CONF_TAMPER_SENSORS,
    CONF_TAMPER_SENSORS_LABELS,
    CONF_SIRENS,
    CONF_SIRENS_LABELS,
    CONF_LIGHTS,
    CONF_LIGHTS_LABELS,
    CONF_MEDIA_PLAYERS,
    CONF_MEDIA_PLAYERS_LABELS,
    CONF_NOTIFY_SERVICES,
    CONF_NOTIFY_SERVICES_LABELS,
    CONF_USERS_CODES,
    CONF_DURESS_CODE,
    CONF_RFID_TAGS,
    CONF_BYPASS_ALLOWED,
    CONF_HEALTH_CHECK,
    CONF_GEOFENCE_AUTO_ARM,
    CONF_EXIT_DELAY,
    CONF_ENTRY_DELAY,
    CONF_SIREN_DURATION,
    CONF_CHIME_MODE,
    CONF_SAFETY_SENSORS,
    CONF_SAFETY_SENSORS_LABELS,
    CONF_PRESENCE_SIMULATION_ENTITIES,
    CONF_PRESENCE_SIMULATION_LABELS,
    CONF_PRESENCE_SIMULATION_HISTORY_DAYS,
    CONF_CROSS_ZONING,
    CONF_CROSS_ZONING_WINDOW,
    CONF_GEOFENCE_REMINDER,
    CONF_GEOFENCE_REMINDER_DELAY,
    DEFAULT_CHIME_MODE,
    DEFAULT_CROSS_ZONING,
    DEFAULT_CROSS_ZONING_WINDOW,
    DEFAULT_GEOFENCE_REMINDER,
    DEFAULT_GEOFENCE_REMINDER_DELAY,
    DEFAULT_PRESENCE_SIMULATION_HISTORY_DAYS,
)

_LOGGER = logging.getLogger(__name__)

# Map string states back to AlarmControlPanelState enum for state restoration
_STATE_MAP = {
    "disarmed": AlarmControlPanelState.DISARMED,
    "armed_home": AlarmControlPanelState.ARMED_HOME,
    "armed_away": AlarmControlPanelState.ARMED_AWAY,
    "armed_night": AlarmControlPanelState.ARMED_NIGHT,
    "pending": AlarmControlPanelState.PENDING,
    "arming": AlarmControlPanelState.ARMING,
    "triggered": AlarmControlPanelState.TRIGGERED,
}


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities):
    """Set up the alarm control panel from a config entry."""
    entity = DomolinkAlarm(hass, entry)
    async_add_entities([entity], True)
    # Store entity reference so __init__.py can forward options updates
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {"entity": entity}

    async def async_handle_bypass_sensor(call):
        """Handle bypass sensor service call."""
        sensor_id = call.data.get("entity_id")
        if sensor_id:
            await entity.async_bypass_sensor(sensor_id)

    async def async_handle_unbypass_sensor(call):
        """Handle unbypass sensor service call."""
        sensor_id = call.data.get("entity_id")
        if sensor_id:
            await entity.async_unbypass_sensor(sensor_id)

    async def async_handle_panic(call):
        """Handle panic button service call."""
        activate_sirens = call.data.get("activate_sirens", False)
        await entity.async_panic(activate_sirens)

    async def async_handle_start_sim(call):
        """Handle start presence simulation service call."""
        await entity.async_start_presence_simulation()

    async def async_handle_stop_sim(call):
        """Handle stop presence simulation service call."""
        await entity.async_stop_presence_simulation()

    async def async_handle_toggle_sim(call):
        """Handle toggle presence simulation service call."""
        await entity.async_toggle_presence_simulation()

    hass.services.async_register(
        DOMAIN, "bypass_sensor", async_handle_bypass_sensor
    )
    hass.services.async_register(
        DOMAIN, "unbypass_sensor", async_handle_unbypass_sensor
    )
    hass.services.async_register(
        DOMAIN, "panic", async_handle_panic
    )
    hass.services.async_register(
        DOMAIN, "start_presence_simulation", async_handle_start_sim
    )
    hass.services.async_register(
        DOMAIN, "stop_presence_simulation", async_handle_stop_sim
    )
    hass.services.async_register(
        DOMAIN, "toggle_presence_simulation", async_handle_toggle_sim
    )


class DomolinkAlarm(AlarmControlPanelEntity, RestoreEntity):
    """Representation of a Domolink Alarm."""

    _attr_has_entity_name = True
    _attr_name = None
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
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._unique_id)},
            name=self._attr_name,
            manufacturer="Domolink",
            model="Domolink Smart Alarm",
            sw_version="0.9.5",
        )

        self._siren_task = None
        self._arming_task = None
        self._pending_task = None
        self._geofence_reminder_task = None
        self._presence_simulation_task = None
        self._faults = []
        self._bypassed_sensors = set()
        self._triggered_by = None
        self._event_sensor = None
        self._last_motion_detection = {}

        self._failed_attempts = 0
        self._blocked_until = 0.0

        self._last_triggered_by = None
        self._last_user = None

        self._users = {}
        self._duress_code = ""
        
        self._arm_history = []
        self._sensor_health = {}
        self._presence_simulation_events = []
        self._presence_simulation_forced = False

        self._load_config()

    def _resolve_labels(self, label_ids: list, allowed_domains: list = None) -> list:
        """Find all entities matching the given labels and domains."""
        if not label_ids:
            return []
            
        entity_reg = er.async_get(self.hass)
        device_reg = dr.async_get(self.hass)
        
        matched_entities = set()
        
        # 1. Find entities directly having the labels
        for entity in entity_reg.entities.values():
            if entity.labels and any(label in entity.labels for label in label_ids):
                if not allowed_domains or entity.domain in allowed_domains:
                    matched_entities.add(entity.entity_id)
                    
        # 2. Find devices having the labels, and add their entities
        for device in device_reg.devices.values():
            if device.labels and any(label in device.labels for label in label_ids):
                # Find all entities for this device
                for entity in er.async_entries_for_device(entity_reg, device.id):
                    if not allowed_domains or entity.domain in allowed_domains:
                        matched_entities.add(entity.entity_id)
                        
        return list(matched_entities)

    def _load_config(self):
        """Load configuration from entry data and options."""
        data = self._entry.data
        options = self._entry.options

        # Users and Codes parsing — format: "Jean:1234, Marie:5678"
        users_str = options.get(CONF_USERS_CODES, data.get(CONF_USERS_CODES, ""))
        self._users = {}
        if users_str:
            for pair in users_str.split(","):
                pair = pair.strip()
                if ":" in pair:
                    name, code = pair.split(":", 1)
                    name, code = name.strip(), code.strip()
                    if name and code:
                        self._users[code] = name

        self._duress_code = str(
            options.get(CONF_DURESS_CODE, data.get(CONF_DURESS_CODE, ""))
        ).strip()

        # RFID Tags parsing — format: "04-7A-5B:Jean, 8F-B2:Marie"
        rfid_str = options.get(CONF_RFID_TAGS, data.get(CONF_RFID_TAGS, ""))
        self._rfid_tags = {}
        if rfid_str:
            for pair in rfid_str.split(","):
                pair = pair.strip()
                if ":" in pair:
                    tag_id, name = pair.split(":", 1)
                    tag_id, name = tag_id.strip(), name.strip()
                    if tag_id and name:
                        self._rfid_tags[tag_id] = name

        self._exit_delay = int(options.get(CONF_EXIT_DELAY, data.get(CONF_EXIT_DELAY, 30)))
        self._entry_delay = int(options.get(CONF_ENTRY_DELAY, data.get(CONF_ENTRY_DELAY, 30)))
        self._siren_duration = int(options.get(CONF_SIREN_DURATION, data.get(CONF_SIREN_DURATION, 180)))
        self._bypass_allowed = bool(options.get(CONF_BYPASS_ALLOWED, data.get(CONF_BYPASS_ALLOWED, False)))
        self._health_check = bool(options.get(CONF_HEALTH_CHECK, data.get(CONF_HEALTH_CHECK, True)))
        self._geofence_auto_arm = bool(options.get(CONF_GEOFENCE_AUTO_ARM, data.get(CONF_GEOFENCE_AUTO_ARM, False)))
        self._geofence_reminder = bool(options.get(CONF_GEOFENCE_REMINDER, data.get(CONF_GEOFENCE_REMINDER, DEFAULT_GEOFENCE_REMINDER)))
        self._geofence_reminder_delay = int(options.get(CONF_GEOFENCE_REMINDER_DELAY, data.get(CONF_GEOFENCE_REMINDER_DELAY, DEFAULT_GEOFENCE_REMINDER_DELAY)))
        self._chime_mode = bool(options.get(CONF_CHIME_MODE, data.get(CONF_CHIME_MODE, DEFAULT_CHIME_MODE)))
        self._cross_zoning = bool(options.get(CONF_CROSS_ZONING, data.get(CONF_CROSS_ZONING, DEFAULT_CROSS_ZONING)))
        self._cross_zoning_window = int(options.get(CONF_CROSS_ZONING_WINDOW, data.get(CONF_CROSS_ZONING_WINDOW, DEFAULT_CROSS_ZONING_WINDOW)))
        self._presence_simulation_history_days = int(options.get(CONF_PRESENCE_SIMULATION_HISTORY_DAYS, data.get(CONF_PRESENCE_SIMULATION_HISTORY_DAYS, DEFAULT_PRESENCE_SIMULATION_HISTORY_DAYS)))

        # Siren Test
        self._siren_test = bool(options.get("siren_test", data.get("siren_test", False)))
        self._siren_test_day = int(options.get("siren_test_day", data.get("siren_test_day", 5)))
        self._siren_test_hour = int(options.get("siren_test_hour", data.get("siren_test_hour", 12)))

        # Scheduling
        self._schedule_enabled = bool(options.get("schedule_enabled", data.get("schedule_enabled", False)))
        self._schedule_arm_time = options.get("schedule_arm_time", data.get("schedule_arm_time", "23:00"))
        self._schedule_disarm_time = options.get("schedule_disarm_time", data.get("schedule_disarm_time", "06:00"))
        self._schedule_mode = options.get("schedule_mode", data.get("schedule_mode", "night"))

        def get_merged(key, labels_key, allowed_domains=None):
            entities = set(options.get(key, data.get(key)) or [])
            labels = options.get(labels_key, data.get(labels_key)) or []
            if labels:
                entities.update(self._resolve_labels(labels, allowed_domains))
            return list(entities)

        self._opening_sensors = get_merged(CONF_OPENING_SENSORS, CONF_OPENING_SENSORS_LABELS, ["binary_sensor", "sensor"])
        self._night_sensors = get_merged(CONF_NIGHT_SENSORS, CONF_NIGHT_SENSORS_LABELS, ["binary_sensor", "sensor"])
        self._motion_sensors = get_merged(CONF_MOTION_SENSORS, CONF_MOTION_SENSORS_LABELS, ["binary_sensor", "sensor"])
        self._tamper_sensors = get_merged(CONF_TAMPER_SENSORS, CONF_TAMPER_SENSORS_LABELS, ["binary_sensor", "sensor"])
        self._safety_sensors = get_merged(CONF_SAFETY_SENSORS, CONF_SAFETY_SENSORS_LABELS, ["binary_sensor", "sensor"])
        self._cameras = get_merged(CONF_CAMERAS, CONF_CAMERAS_LABELS, ["camera"])
        self._sirens = get_merged(CONF_SIRENS, CONF_SIRENS_LABELS, ["switch", "siren"])
        self._lights = get_merged(CONF_LIGHTS, CONF_LIGHTS_LABELS, ["light"])
        self._media_players = get_merged(CONF_MEDIA_PLAYERS, CONF_MEDIA_PLAYERS_LABELS, ["media_player"])
        self._persons = get_merged(CONF_PERSONS, CONF_PERSONS_LABELS, ["person"])
        self._notify_services = get_merged(CONF_NOTIFY_SERVICES, CONF_NOTIFY_SERVICES_LABELS, ["notify"])
        self._emergency_contact = get_merged("emergency_contact", "emergency_contact_labels", ["notify"])
        self._presence_simulation_entities = get_merged(CONF_PRESENCE_SIMULATION_ENTITIES, CONF_PRESENCE_SIMULATION_LABELS, ["light", "switch", "cover"])

    @callback
    def async_update_options(self):
        """Reload config when options change (called from __init__.py listener)."""
        self._load_config()
        self.async_write_ha_state()

    # ─── Properties ───────────────────────────────────────────────

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._unique_id

    @property
    def alarm_state(self):
        """Return the state of the device (modern HA property)."""
        return self._state

    @property
    def code_arm_required(self):
        """Whether the code is required for arm actions."""
        return False

    @property
    def extra_state_attributes(self):
        """Expose extra attributes for Lovelace and automations."""
        return {
            "faults": self._faults,
            "triggered_by": self._triggered_by,
            "last_triggered_by": self._last_triggered_by,
            "last_user": self._last_user,
            "failed_attempts": self._failed_attempts,
            "geofence_active": self._geofence_auto_arm,
            "health_check_active": self._health_check,
            "opening_sensors": self._opening_sensors,
            "motion_sensors": self._motion_sensors,
            "tamper_sensors": self._tamper_sensors,
            "night_sensors": self._night_sensors,
            "sirens": self._sirens,
            "lights": self._lights,
            "cameras": self._cameras,
            "media_players": self._media_players,
            "persons": self._persons,
            "bypassed_sensors": list(self._bypassed_sensors),
            "chime_active": self._chime_mode,
            "safety_sensors": self._safety_sensors,
            "presence_simulation_entities": self._presence_simulation_entities,
            "presence_simulation_active": self._presence_simulation_task is not None,
            "presence_simulation_history_days": self._presence_simulation_history_days,
            "presence_simulation_forced": self._presence_simulation_forced,
            "presence_simulation_events": self._presence_simulation_events,
            "cross_zoning_active": self._cross_zoning,
            "geofence_reminder_active": self._geofence_reminder,
            "arm_history": self._arm_history,
            "sensor_health": self._sensor_health,
        }

    async def async_bypass_sensor(self, entity_id: str):
        """Bypass / ignore a sensor temporarily."""
        self._bypassed_sensors.add(entity_id)
        # Also remove from current faults if present
        if entity_id in self._faults:
            self._faults.remove(entity_id)
        self._log_event(f"Capteur ignoré (Bypass): {entity_id}")
        self.async_write_ha_state()

    async def async_unbypass_sensor(self, entity_id: str):
        """Unbypass / restore a sensor to active monitoring."""
        self._bypassed_sensors.discard(entity_id)
        self._log_event(f"Capteur rétabli: {entity_id}")
        self.async_write_ha_state()

    def set_log_sensor(self, sensor):
        """Register the event log sensor."""
        self._event_sensor = sensor

    def _log_event(self, message):
        """Log an event and notify sensor."""
        if self._event_sensor:
            self._event_sensor.async_add_event(utcnow().isoformat(), message)

    # ─── Lifecycle ────────────────────────────────────────────────

    async def async_added_to_hass(self):
        """Run when entity about to be added."""
        await super().async_added_to_hass()

        # Restore state — map string back to Enum (Fix #3)
        last_state = await self.async_get_last_state()
        if last_state and last_state.state in _STATE_MAP:
            self._state = _STATE_MAP[last_state.state]
            if last_state.attributes:
                self._last_triggered_by = last_state.attributes.get("last_triggered_by")
                self._last_user = last_state.attributes.get("last_user")
                self._arm_history = last_state.attributes.get("arm_history", [])

        # Track sensor changes
        all_sensors = list(set(
            self._opening_sensors
            + self._motion_sensors
            + self._tamper_sensors
            + self._night_sensors
            + self._safety_sensors
            + self._persons
        ))
        if all_sensors:
            self.async_on_remove(
                async_track_state_change_event(
                    self.hass, all_sensors, self._async_sensor_changed
                )
            )

        # Health check periodic task
        if self._health_check:
            self.async_on_remove(
                async_track_time_interval(
                    self.hass, self._async_perform_health_check, timedelta(hours=4)
                )
            )

        # Geofencing (Auto-Arm or Reminder)
        if self._geofence_auto_arm or self._geofence_reminder:
            self.async_on_remove(
                async_track_state_change_event(
                    self.hass, ["zone.home"], self._async_zone_changed
                )
            )

        # Actionable notifications listener — register cleanup (Fix #4)
        self.async_on_remove(
            self.hass.bus.async_listen(
                "mobile_app_notification_action", self._async_handle_mobile_action
            )
        )

        # RFID Tags listener
        if self._rfid_tags:
            self.async_on_remove(
                self.hass.bus.async_listen(
                    "tag_scanned", self._async_handle_tag_scanned
                )
            )

        # Siren Test Schedule
        if getattr(self, "_siren_test", False):
            from homeassistant.helpers.event import async_track_time_change
            self.async_on_remove(
                async_track_time_change(
                    self.hass,
                    self._cb_siren_test,
                    hour=self._siren_test_hour,
                    minute=0,
                    second=0
                )
            )

        # Time-based Auto-Arming
        if getattr(self, "_schedule_enabled", False):
            from homeassistant.helpers.event import async_track_time_change
            arm_time = self._schedule_arm_time.split(":")
            disarm_time = self._schedule_disarm_time.split(":")
            if len(arm_time) == 2 and len(disarm_time) == 2:
                self.async_on_remove(
                    async_track_time_change(
                        self.hass,
                        self._cb_schedule_arm,
                        hour=int(arm_time[0]),
                        minute=int(arm_time[1]),
                        second=0
                    )
                )
                self.async_on_remove(
                    async_track_time_change(
                        self.hass,
                        self._cb_schedule_disarm,
                        hour=int(disarm_time[0]),
                        minute=int(disarm_time[1]),
                        second=0
                    )
                )

    # ─── Geofencing ───────────────────────────────────────────────

    async def _async_zone_changed(self, event):
        """Handle zone.home state changes for auto arm/disarm and reminders."""
        new_state = event.data.get("new_state")
        old_state = event.data.get("old_state")

        if not new_state or not old_state:
            return

        try:
            old_count = int(old_state.state)
            new_count = int(new_state.state)
        except (ValueError, TypeError):
            return

        if old_count > 0 and new_count == 0:
            # Everyone left
            if self._state == AlarmControlPanelState.DISARMED:
                if self._geofence_auto_arm:
                    _LOGGER.info("Geofencing: Plus personne à la maison, auto armement en Absence")
                    await self._async_send_notification(
                        "🏠 Domolink: Plus personne à la maison, armement automatique activé."
                    )
                    await self.async_alarm_arm_away()
                elif self._geofence_reminder:
                    if not self._geofence_reminder_task:
                        _LOGGER.info(
                            "Geofencing: Plus personne à la maison, planification rappel dans %d min",
                            self._geofence_reminder_delay,
                        )
                        self._geofence_reminder_task = async_call_later(
                            self.hass,
                            self._geofence_reminder_delay * 60,
                            self._cb_geofence_reminder,
                        )

        elif old_count == 0 and new_count > 0:
            # Someone arrived
            if self._geofence_reminder_task:
                self._geofence_reminder_task()
                self._geofence_reminder_task = None

            if self._geofence_auto_arm and self._state in (
                AlarmControlPanelState.ARMED_AWAY,
                AlarmControlPanelState.ARMED_NIGHT,
                AlarmControlPanelState.ARMING,
            ):
                _LOGGER.info("Geofencing: Quelqu'un est arrivé, auto désarmement")
                self._cancel_all_tasks()
                self._state = AlarmControlPanelState.DISARMED
                self._last_user = "Géolocalisation"
                self.async_write_ha_state()
                await self._async_turn_off_siren()
                await self._async_send_notification(
                    "🏠 Domolink: Retour détecté, désarmement automatique."
                )

    @callback
    def _cb_geofence_reminder(self, _now):
        """Send actionable reminder notification to arm the alarm."""
        self._geofence_reminder_task = None
        if self._state != AlarmControlPanelState.DISARMED:
            return

        states = [self.hass.states.get(p) for p in self._persons]
        states = [s.state for s in states if s is not None]
        if all(s != "home" for s in states):
            _LOGGER.info("Geofencing: Envoi notification rappel d'oubli d'armement")
            self._log_event("Rappel d'armement envoyé (Absence prolongée)")
            action_data = {
                "actions": [
                    {
                        "action": "DOMOLINK_REMINDER_ARM_AWAY",
                        "title": "⚡ Armer en Absence",
                    },
                    {
                        "action": "DOMOLINK_CANCEL_ARM",
                        "title": "❌ Ignorer",
                        "destructive": True,
                    },
                ]
            }
            self.hass.async_create_task(
                self._async_send_notification(
                    "📍 Vous semblez avoir quitté la maison sans activer l'alarme.\n\nVoulez-vous l'armer maintenant ?",
                    custom_data=action_data,
                )
            )

    # ─── Mobile Actionable Notifications ──────────────────────────

    async def _async_handle_mobile_action(self, event):
        """Handle actionable notification button clicks."""
        action = event.data.get("action")
        reply_text = event.data.get("reply_text")

        if action == "DOMOLINK_DISARM":
            _LOGGER.info("Disarm triggered via mobile actionable notification")
            self._cancel_all_tasks()
            user_name = "App Mobile"
            if event.context and event.context.user_id:
                user_obj = await self.hass.auth.async_get_user(event.context.user_id)
                if user_obj and user_obj.name:
                    user_name = f"{user_obj.name} (Mobile)"
            self._log_event(f"Alarme Désarmée par {user_name}")
            self._record_arm_event("disarm", user_name)
            await self.async_alarm_disarm("MOBILE_APP")
            await self._async_send_notification(
                "✅ Alarme désarmée via Apple Watch / Mobile."
            )

        elif action == "DOMOLINK_REMINDER_ARM_AWAY":
            _LOGGER.info("Arming Away via geofencing reminder notification")
            self._log_event("Armement suite au rappel de géolocalisation")
            await self.async_alarm_arm_away()

        elif action in ("DOMOLINK_FORCE_ARM_AWAY", "DOMOLINK_FORCE_ARM_HOME", "DOMOLINK_FORCE_ARM_NIGHT"):
            # Check user PIN code if provided
            user = "Mobile App"
            if reply_text:
                user = self._validate_code(str(reply_text).strip())
                if not user:
                    _LOGGER.warning("Invalid code for forced arming from mobile app")
                    await self._async_send_notification("⛔ Code erroné. Armement forcé refusé.")
                    return

            mode_map = {
                "DOMOLINK_FORCE_ARM_AWAY": (AlarmControlPanelState.ARMED_AWAY, "Absent"),
                "DOMOLINK_FORCE_ARM_HOME": (AlarmControlPanelState.ARMED_HOME, "Présent"),
                "DOMOLINK_FORCE_ARM_NIGHT": (AlarmControlPanelState.ARMED_NIGHT, "Nuit"),
            }
            target_state, mode_name = mode_map[action]
            self._cancel_all_tasks()
            self._state = target_state
            self._pre_trigger_state = target_state
            self._last_user = user
            self.async_write_ha_state()
            self._log_event(f"Alarme Armée avec Bypass forcé ({mode_name}) par {user}")
            await self._async_send_notification(
                f"⚠️ Alarme armée avec mise en marche forcée (Mode: {mode_name})."
            )

        elif action == "DOMOLINK_CANCEL_ARM":
            self._log_event("Armement annulé par l'utilisateur")
            await self._async_send_notification("❌ Armement annulé.")

    # ─── RFID Tag Handling ────────────────────────────────────────

    async def _async_handle_tag_scanned(self, event):
        """Handle RFID/NFC tag scans to toggle alarm state."""
        tag_id = event.data.get("tag_id")
        if not tag_id or tag_id not in self._rfid_tags:
            return

        user_name = self._rfid_tags[tag_id]
        _LOGGER.info("RFID Tag scanned by %s", user_name)

        if self._state == AlarmControlPanelState.DISARMED:
            # Arm the alarm (Away mode by default)
            _LOGGER.info("Arming via RFID (User: %s)", user_name)
            if not await self._check_bypass(target_mode="AWAY", force=True):
                # Should not happen since force=True
                pass
            
            self._last_user = f"{user_name} (RFID)"
            if self._exit_delay > 0:
                self._state = AlarmControlPanelState.ARMING
                self.async_write_ha_state()
                self._arming_task = async_call_later(
                    self.hass,
                    self._exit_delay,
                    self._cb_arm_away_complete,
                )
            else:
                self._cb_arm_away_complete()
                
            await self._async_send_notification(
                f"🔒 Alarme activée par {user_name} (Badge)."
            )
        else:
            # Disarm the alarm
            _LOGGER.info("Disarming via RFID (User: %s)", user_name)
            self._cancel_all_tasks()
            self._state = AlarmControlPanelState.DISARMED
            self._last_user = f"{user_name} (RFID)"
            self._faults.clear()
            self._triggered_by = None
            self.async_write_ha_state()
            await self._async_turn_off_siren()
            self._log_event(f"Alarme Désarmée ({user_name} - Badge)")
            await self._async_send_notification(
                f"✅ Alarme désarmée par {user_name} (Badge)."
            )
            self.hass.async_create_task(
                self._async_play_tts(f"Alarme désarmée. Bienvenue {user_name}.")
            )

    # ─── Health Check & Battery Diagnostics ───────────────────────

    def _get_device_battery_level(self, entity_id: str) -> float | None:
        """Find battery level from entity attributes or associated device entities."""
        state = self.hass.states.get(entity_id)
        if not state:
            return None

        # 1. Check direct entity attributes
        battery = state.attributes.get("battery_level") or state.attributes.get("battery")
        if battery is not None:
            try:
                return float(battery)
            except (ValueError, TypeError):
                pass

        # 2. Check device registry for associated battery sensor
        try:
            entity_reg = er.async_get(self.hass)
            entry = entity_reg.async_get(entity_id)
            if entry and entry.device_id:
                for e in er.async_entries_for_device(entity_reg, entry.device_id):
                    if e.domain == "sensor":
                        s_state = self.hass.states.get(e.entity_id)
                        if s_state and s_state.attributes.get("device_class") == "battery":
                            try:
                                return float(s_state.state)
                            except (ValueError, TypeError):
                                pass
        except Exception as e:
            _LOGGER.debug("Domolink: Erreur lecture batterie périphérique pour %s: %s", entity_id, e)

        return None

    async def _async_perform_health_check(self, now=None):
        """Check battery and availability of all linked devices."""
        all_devices = list(set(
            self._opening_sensors
            + self._motion_sensors
            + self._tamper_sensors
            + self._night_sensors
            + self._sirens
            + self._cameras
            + self._lights
        ))
        if not all_devices:
            return

        warnings = []
        health_data = {}
        for device_id in all_devices:
            if device_id in self._bypassed_sensors:
                continue
                
            state = self.hass.states.get(device_id)
            friendly = state.name if state and state.name else device_id
            
            is_offline = not state or state.state in ("unavailable", "unknown")
            last_changed = state.last_changed.isoformat() if state and state.last_changed else None
            battery = self._get_device_battery_level(device_id)
            
            health_data[device_id] = {
                "name": friendly,
                "offline": is_offline,
                "battery": battery,
                "last_changed": last_changed
            }
            
            if is_offline:
                warnings.append(f"⚠️ {friendly} est hors ligne / indisponible.")
            elif battery is not None and battery <= 15:
                warnings.append(f"🪫 {friendly} : pile faible ({int(battery)}%).")

        self._sensor_health = health_data
        self.async_write_ha_state()

        if warnings:
            self._log_event(f"Diagnostic : {len(warnings)} alerte(s) équipement(s)")
            notify_msg = "🔋 Diagnostic Domolink :\n" + "\n".join(warnings)
            await self._async_send_notification(notify_msg)

    # ─── Notifications ────────────────────────────────────────────

    async def _async_send_notification(self, message, is_alert=False, custom_data=None, is_emergency=False):
        """Send notifications to configured services/entities with universal compatibility."""
        targets = []
        if self._notify_services:
            targets.extend(self._notify_services)
        if is_emergency and self._emergency_contact:
            for ec in self._emergency_contact:
                if ec not in targets:
                    targets.append(ec)
                    
        if not targets:
            return

        # Action par défaut: ouvrir l'application sur le tableau de bord
        data = {
            "url": "/",
            "clickAction": "/"
        }
        
        if is_alert:
            alert_data = {
                "push": {
                    "category": "camera",
                    "sound": {
                        "name": "default",
                        "critical": 1,
                        "volume": 1.0,
                    }
                },
                "actions": [
                    {
                        "action": "DOMOLINK_DISARM",
                        "title": "🔓 Désarmer l'alarme",
                        "destructive": True,
                    }
                ],
            }
            if self._cameras:
                alert_data["entity_id"] = self._cameras[0]
                alert_data["image"] = "/local/domolink_alarm_alert.jpg"
                alert_data["attachment"] = {
                    "url": "/local/domolink_alarm_alert.jpg",
                    "content-type": "jpeg",
                    "hide-thumbnail": False,
                }
            data.update(alert_data)

        if custom_data:
            data.update(custom_data)
            
        if is_emergency:
            # Add GPS data if available (take first person location)
            for person_id in self._persons:
                state = self.hass.states.get(person_id)
                if state and state.attributes.get("latitude") and state.attributes.get("longitude"):
                    data["location"] = {
                        "latitude": state.attributes.get("latitude"),
                        "longitude": state.attributes.get("longitude")
                    }
                    break

        for target in targets:
            sent = False

            # Strategy 1: Modern HA Notify Entity (`notify.send_message` with entity_id)
            if self.hass.services.has_service("notify", "send_message"):
                try:
                    payload = {"entity_id": target, "message": message}
                    if data:
                        payload["data"] = data
                    await self.hass.services.async_call("notify", "send_message", payload)
                    sent = True
                    _LOGGER.debug("Domolink: Notification envoyée via notify.send_message à %s", target)
                except Exception as e:
                    _LOGGER.debug("Domolink: notify.send_message échoué pour %s: %s", target, e)

            # Strategy 2: Direct service call (e.g. notify.mobile_app_iphone, notify.telegram)
            if not sent:
                if "." in target:
                    domain, service = target.split(".", 1)
                else:
                    domain, service = "notify", target

                if self.hass.services.has_service(domain, service):
                    try:
                        payload = {"message": message}
                        if data:
                            payload["data"] = data
                        await self.hass.services.async_call(domain, service, payload)
                        sent = True
                        _LOGGER.debug("Domolink: Notification envoyée directement à %s.%s", domain, service)
                    except Exception as e:
                        _LOGGER.error("Domolink: Échec d'envoi vers %s.%s: %s", domain, service, e)

                # Strategy 3: Target is notify.iphone -> try notify.mobile_app_iphone
                elif domain == "notify" and self.hass.services.has_service("notify", f"mobile_app_{service}"):
                    try:
                        payload = {"message": message}
                        if data:
                            payload["data"] = data
                        await self.hass.services.async_call("notify", f"mobile_app_{service}", payload)
                        sent = True
                        _LOGGER.debug("Domolink: Notification envoyée à notify.mobile_app_%s", service)
                    except Exception as e:
                        _LOGGER.error("Domolink: Échec d'envoi vers notify.mobile_app_%s: %s", service, e)

            if not sent:
                _LOGGER.warning("Domolink: Impossible de trouver un service de notification valide pour %s", target)

    async def _async_handle_person_changed(self):
        """Handle geofencing auto-arm logic."""
        if not self._geofence_auto_arm or not self._persons:
            return
            
        states = [self.hass.states.get(p) for p in self._persons]
        states = [s.state for s in states if s is not None]
        
        if all(s != "home" for s in states) and self._state == AlarmControlPanelState.DISARMED:
            self._log_event("Auto-armement (Toutes les personnes sont absentes)")
            await self.async_alarm_arm_away()
        elif any(s == "home" for s in states) and self._state in (AlarmControlPanelState.ARMED_AWAY, AlarmControlPanelState.ARMING):
            self._log_event("Auto-désarmement (Une personne est arrivée)")
            await self.async_alarm_disarm(code=None)  # Auto disarm

    # ─── Sensor Monitoring ────────────────────────────────────────

    async def _async_sensor_changed(self, event):
        """Handle sensor state changes."""
        entity_id = event.data.get("entity_id")
        new_state = event.data.get("new_state")
        old_state = event.data.get("old_state")

        if not new_state:
            return

        # Geofencing
        if entity_id in self._persons:
            await self._async_handle_person_changed()
            return

        state_val = str(new_state.state).lower()
        if state_val not in ("on", "open", "true", "detected", "unlocked", "1"):
            return

        # Check if sensor is bypassed
        if entity_id in self._bypassed_sensors:
            _LOGGER.debug("Domolink: Capteur %s ignoré (bypassed)", entity_id)
            return

        _LOGGER.info(
            "Domolink Alarm: Détection sur %s (état: %s, état alarme: %s)",
            entity_id,
            state_val,
            self._state,
        )

        # Safety Sensors 24/7 (Smoke, Water, Gas, CO)
        if entity_id in self._safety_sensors:
            device_class = new_state.attributes.get("device_class", "")
            friendly = new_state.name or entity_id
            
            if device_class in ("smoke", "carbon_monoxide", "gas"):
                type_label = "Fumée / Gaz"
                tts_msg = f"Alerte d'urgence : détection de fumée ou de gaz sur {friendly} !"
            elif device_class in ("moisture", "water"):
                type_label = "Fuite d'eau"
                tts_msg = f"Alerte inondation : détection d'eau sur {friendly} !"
            else:
                type_label = "Technique 24/7"
                tts_msg = f"Alerte d'urgence technique sur {friendly} !"

            _LOGGER.warning("Domolink: Alerte Capteur Technique 24/7 (%s) sur %s", type_label, entity_id)
            self._log_event(f"ALERTE 24/7 ({type_label}): {friendly}")
            await self._async_send_notification(
                f"🚨 ALERTE D'URGENCE 24/7 🚨\nType : {type_label}\nCapteur : {friendly}",
                is_alert=True,
            )
            self.hass.async_create_task(self._async_play_tts(tts_msg))
            return

        # Tamper triggers immediately regardless of state (24/7)
        if entity_id in self._tamper_sensors:
            _LOGGER.warning("Tamper / Sabotage détecté sur %s !", entity_id)
            await self._async_trigger_alarm(entity_id)
            return

        # Chime Mode when disarmed
        if self._state == AlarmControlPanelState.DISARMED:
            if self._chime_mode and entity_id in self._opening_sensors:
                friendly = new_state.name or entity_id
                _LOGGER.info("Domolink Chime: %s ouverte", friendly)
                self._log_event(f"Carillon : {friendly} ouverte")
                self.hass.async_create_task(
                    self._async_play_tts(f"{friendly} ouverte.")
                )
            return

        # Ignore sensors during exit delay
        if self._state == AlarmControlPanelState.ARMING:
            _LOGGER.debug(
                "Capteur ignoré car l'alarme est en cours d'armement (délai de sortie)",
            )
            return

        # Cross-zoning check for motion sensors in Away / Night
        if self._cross_zoning and entity_id in self._motion_sensors and self._state in (AlarmControlPanelState.ARMED_AWAY, AlarmControlPanelState.ARMED_NIGHT):
            now_loop = self.hass.loop.time()
            confirmed = False
            for prev_id, prev_time in list(self._last_motion_detection.items()):
                diff = now_loop - prev_time
                if (diff <= self._cross_zoning_window) and (prev_id != entity_id or diff >= 2.0):
                    confirmed = True
                    break

            self._last_motion_detection[entity_id] = now_loop

            if not confirmed:
                _LOGGER.info(
                    "Domolink Cross-Zoning: 1ère détection sur %s, en attente de confirmation dans les %ds",
                    entity_id,
                    self._cross_zoning_window,
                )
                self._log_event(f"Pré-détection mouvement (Cross-Zoning): {new_state.name}")
                return
            else:
                _LOGGER.info("Domolink Cross-Zoning: Double détection confirmée sur %s !", entity_id)
                self._log_event(f"Double détection confirmée sur {new_state.name}")

        # Already triggered: if sirens stopped, re-trigger full sequence; otherwise notify additional detection
        if self._state == AlarmControlPanelState.TRIGGERED:
            if self._siren_task is None:
                _LOGGER.info("Domolink: Nouveau déclenchement après arrêt sirène sur %s", entity_id)
                await self._async_trigger_alarm(entity_id)
            else:
                if entity_id not in self._faults:
                    self._faults.append(entity_id)
                self.async_write_ha_state()
                self._log_event(f"Autre détection: {new_state.name}")
                await self._async_send_notification(f"🚨 Détection supplémentaire : {new_state.name}", is_alert=True)
            return

        # Handle different armed modes
        if self._state == AlarmControlPanelState.ARMED_HOME:
            if entity_id in self._opening_sensors:
                await self._async_trigger_alarm(entity_id)

        elif self._state in (
            AlarmControlPanelState.ARMED_AWAY,
            AlarmControlPanelState.ARMED_NIGHT,
        ):
            is_valid_sensor = False
            if self._state == AlarmControlPanelState.ARMED_NIGHT:
                is_valid_sensor = entity_id in self._night_sensors
            else:
                is_valid_sensor = (entity_id in self._opening_sensors) or (entity_id in self._motion_sensors)

            if is_valid_sensor:
                # Entry delay only for ARMED_AWAY
                if self._state == AlarmControlPanelState.ARMED_AWAY and self._entry_delay > 0:
                    if self._pending_task is None:
                        _LOGGER.info("Starting entry delay for %s", entity_id)
                        self._pre_trigger_state = self._state
                        self._state = AlarmControlPanelState.PENDING
                        if entity_id not in self._faults:
                            self._faults.append(entity_id)
                        self._triggered_by = new_state.name
                        self.async_write_ha_state()
                        await self._async_pre_alarm_feedback()
                        # Send alert notification with disarm button
                        await self._async_send_notification(
                            f"⏳ Délai d'entrée déclenché par {new_state.name}. Veuillez désarmer.",
                            is_alert=True,
                        )
                        self._pending_task = async_call_later(
                            self.hass,
                            self._entry_delay,
                            lambda now: self.hass.async_create_task(
                                self._async_trigger_alarm(entity_id)
                            ),
                        )
                else:
                    await self._async_trigger_alarm(entity_id)

        elif self._state == AlarmControlPanelState.PENDING:
            # Already in pending state, additional sensor confirms intrusion
            if entity_id not in self._faults:
                self._faults.append(entity_id)
            self.async_write_ha_state()

    # ─── TTS Helper ───────────────────────────────────────────────

    async def _async_play_tts(self, message):
        """Prepare media players and play TTS message in background."""
        if not self._media_players:
            return

        for player in self._media_players:
            try:
                # 1. Allumer l'ampli/player
                await self.hass.services.async_call(
                    "media_player", "turn_on",
                    {"entity_id": player},
                )
            except Exception as e:
                pass
                
            try:
                # 2. Régler le volume à 50%
                await self.hass.services.async_call(
                    "media_player", "volume_set",
                    {"entity_id": player, "volume_level": 0.5},
                )
            except Exception as e:
                pass

        # 3. Attendre 2.5s que l'ampli s'allume et se connecte (Onkyo etc.)
        await asyncio.sleep(2.5)

        for player in self._media_players:
            try:
                # 4. Envoyer le TTS
                await self.hass.services.async_call(
                    "tts", "google_translate_say",
                    {"entity_id": player, "message": message},
                )
            except Exception as e:
                _LOGGER.debug("Failed to play TTS on %s: %s", player, e)

    # ─── Pre-Alarm Feedback ───────────────────────────────────────

    async def _async_pre_alarm_feedback(self):
        """Flash lights and warn during pending state."""
        if self._lights:
            try:
                await self.hass.services.async_call(
                    "light", "turn_on",
                    {"entity_id": self._lights, "flash": "short"},
                )
            except Exception:
                try:
                    await self.hass.services.async_call(
                        "homeassistant", "turn_on",
                        {"entity_id": self._lights},
                    )
                except Exception as e:
                    _LOGGER.error("Failed to flash panic lights: %s", e)

        self.hass.async_create_task(
            self._async_play_tts("Veuillez désarmer l'alarme immédiatement.")
        )

    # ─── Alarm Triggering ─────────────────────────────────────────

    async def _async_trigger_alarm(self, triggering_entity):
        """Trigger the alarm — full alert sequence."""
        # Only ignore if already triggered AND siren is currently ringing
        if self._state == AlarmControlPanelState.TRIGGERED and self._siren_task is not None:
            return

        self._state = AlarmControlPanelState.TRIGGERED
        self._last_triggered_by = triggering_entity
        self.async_write_ha_state()

        # Cancel pending task if any
        if self._pending_task:
            self._pending_task()
            self._pending_task = None

        if triggering_entity not in self._faults:
            self._faults.append(triggering_entity)

        state = self.hass.states.get(triggering_entity)
        self._triggered_by = state.name if state else triggering_entity
        
        self._log_event(f"Alarme DÉCLENCHÉE par {self._triggered_by}")
        name = state.name if state else triggering_entity

        # 1. Camera Snapshot & Recording
        if self._cameras:
            try:
                www_dir = self.hass.config.path("www")
                if not os.path.exists(www_dir):
                    os.makedirs(www_dir, exist_ok=True)

                snapshot_path = self.hass.config.path("www/domolink_alarm_alert.jpg")
                first_cam = self._cameras[0]
                await self.hass.services.async_call(
                    "camera", "snapshot",
                    {"entity_id": first_cam, "filename": snapshot_path},
                    blocking=True,
                )
                self._log_event(f"Photo capturée ({first_cam})")
            except Exception as e:
                _LOGGER.debug("Domolink: Erreur capture photo caméra: %s", e)

            self._log_event(f"Lancement de l'enregistrement sur {len(self._cameras)} caméra(s)")
            for camera in self._cameras:
                try:
                    await self.hass.services.async_call(
                        "camera", "record",
                        {"entity_id": camera, "duration": 30},
                    )
                except Exception as e:
                    _LOGGER.error("Failed to record camera %s: %s", camera, e)

        # 2. Critical notification with disarm button and camera photo
        await self._async_send_notification(
            f"🚨 INTRUSION DÉTECTÉE 🚨\nCapteur : {name}",
            is_alert=True,
        )

        # 3. TTS dissuasion (Away, Night, or Tamper)
        should_tts = (
            self._pre_trigger_state in (
                AlarmControlPanelState.ARMED_AWAY,
                AlarmControlPanelState.ARMED_NIGHT,
                AlarmControlPanelState.DISARMED,
            )
            or triggering_entity in self._tamper_sensors
        )
        if should_tts:
            tts_message = (
                "Alerte intrusion détectée, le propriétaire et la police ont été prévenus. "
                "Les enregistrements photos et vidéo ont été réalisés à l'intérieur mais aussi "
                "à l'extérieur dès que vous avez pénétré dans la propriété. "
                "Tout est d'ores et déjà sauvegardé en ligne, sur des serveurs sécurisés."
            )
            self.hass.async_create_task(
                self._async_play_tts(tts_message)
            )

        # 4. Siren & Panic Lights (Away mode or Tamper)
        should_siren = (
            self._pre_trigger_state == AlarmControlPanelState.ARMED_AWAY
            or triggering_entity in self._tamper_sensors
        )
        if should_siren:
            self._log_event("Activation des sirènes et lumières d'urgence")
            if self._sirens:
                try:
                    await self.hass.services.async_call(
                        "homeassistant", "turn_on",
                        {"entity_id": self._sirens},
                    )
                    self._siren_task = async_call_later(
                        self.hass,
                        self._siren_duration,
                        self._cb_turn_off_siren,  # Fix #1: sync callback
                    )
                except Exception as e:
                    _LOGGER.error("Failed to turn on sirens: %s", e)

            if self._lights:
                try:
                    await self.hass.services.async_call(
                        "light", "turn_on",
                        {"entity_id": self._lights, "color_name": "red", "brightness": 255},
                    )
                except Exception:
                    try:
                        await self.hass.services.async_call(
                            "homeassistant", "turn_on",
                            {"entity_id": self._lights},
                        )
                    except Exception as e:
                        _LOGGER.error("Failed to turn on panic lights: %s", e)

    # ─── Siren / Lights Off ───────────────────────────────────────

    @callback
    def _cb_turn_off_siren(self, now=None):
        """Sync @callback for async_call_later — schedules async cleanup (Fix #1)."""
        self.hass.async_create_task(self._async_turn_off_siren())

    async def _async_turn_off_siren(self):
        """Turn off sirens and panic lights."""
        self._log_event("Arrêt des sirènes et des lumières")
        if self._sirens:
            try:
                await self.hass.services.async_call(
                    "homeassistant", "turn_off",
                    {"entity_id": self._sirens},
                )
            except Exception as e:
                _LOGGER.error("Failed to turn off sirens: %s", e)
        if self._lights:
            try:
                await self.hass.services.async_call(
                    "homeassistant", "turn_off",
                    {"entity_id": self._lights},
                )
            except Exception as e:
                _LOGGER.error("Failed to turn off lights: %s", e)
        self._siren_task = None

        # If sirens turned off after cycle and alarm was not disarmed, re-arm to pre-trigger state
        # so any subsequent detection triggers a full alarm cycle again
        if self._state == AlarmControlPanelState.TRIGGERED:
            target_state = (
                self._pre_trigger_state
                if self._pre_trigger_state != AlarmControlPanelState.DISARMED
                else AlarmControlPanelState.ARMED_AWAY
            )
            self._state = target_state
            self._faults.clear()
            self._log_event(f"Fin de cycle sirène — Système ré-armé ({target_state.value})")
            self.async_write_ha_state()

    # ─── Helper: Cancel All Tasks ─────────────────────────────────

    def _cancel_all_tasks(self):
        """Cancel any pending timers."""
        if self._arming_task:
            self._arming_task()
            self._arming_task = None
        if self._pending_task:
            self._pending_task()
            self._pending_task = None
        if self._siren_task:
            self._siren_task()
            self._siren_task = None
        if self._geofence_reminder_task:
            self._geofence_reminder_task()
            self._geofence_reminder_task = None
        if self._presence_simulation_task:
            self._presence_simulation_task()
            self._presence_simulation_task = None

    # ─── Presence Simulation Engine ───────────────────────────────

    async def async_start_presence_simulation(self):
        """Service handler to start presence simulation manually."""
        self._presence_simulation_forced = True
        self._start_presence_simulation()
        self.async_write_ha_state()

    async def async_stop_presence_simulation(self):
        """Service handler to stop presence simulation manually."""
        self._presence_simulation_forced = False
        self._stop_presence_simulation()
        self.async_write_ha_state()

    async def async_toggle_presence_simulation(self):
        """Service handler to toggle presence simulation."""
        if self._presence_simulation_task is not None:
            await self.async_stop_presence_simulation()
        else:
            await self.async_start_presence_simulation()

    def _start_presence_simulation(self):
        """Start presence simulation based on historic recorder data."""
        if not self._presence_simulation_entities:
            return
        if self._presence_simulation_task is None:
            _LOGGER.info(
                "Domolink: Démarrage de la simulation de présence (Replay J-%d sur %d appareils)",
                self._presence_simulation_history_days,
                len(self._presence_simulation_entities),
            )
            self._log_event(f"Démarrage Simulation Présence ({len(self._presence_simulation_entities)} appareils)")
            self._presence_simulation_task = async_track_time_interval(
                self.hass,
                self._async_presence_simulation_tick,
                timedelta(minutes=1),
            )
            # Run one tick immediately
            self.hass.async_create_task(self._async_presence_simulation_tick())

    def _stop_presence_simulation(self):
        """Stop running presence simulation."""
        if self._presence_simulation_task:
            self._presence_simulation_task()
            self._presence_simulation_task = None
            _LOGGER.info("Domolink: Arrêt de la simulation de présence")
            self._log_event("Arrêt Simulation Présence")

    async def _async_presence_simulation_tick(self, _now=None):
        """Replay historic states of presence simulation entities."""
        # Active if either forced manually OR alarm is armed away
        is_active = self._presence_simulation_forced or (self._state == AlarmControlPanelState.ARMED_AWAY)
        if not is_active or not self._presence_simulation_entities:
            return

        try:
            from homeassistant.components.recorder import get_instance, history

            now = utcnow()
            past_now = now - timedelta(days=self._presence_simulation_history_days)
            past_start = past_now - timedelta(minutes=2)

            instance = get_instance(self.hass)
            states = await instance.async_add_executor_job(
                history.get_significant_states,
                self.hass,
                past_start,
                past_now,
                self._presence_simulation_entities,
            )

            for entity_id, entity_states in (states or {}).items():
                if not entity_states:
                    continue
                target_state = entity_states[-1].state
                if target_state not in ("on", "off"):
                    continue

                current = self.hass.states.get(entity_id)
                if current and current.state != target_state:
                    domain = entity_id.split(".")[0]
                    if domain in ("light", "switch", "cover"):
                        if domain == "cover":
                            service = "open_cover" if target_state in ("open", "on") else "close_cover"
                        else:
                            service = "turn_on" if target_state == "on" else "turn_off"

                        _LOGGER.info(
                            "Domolink Simulation Présence: %s -> %s (rejoué depuis J-%d)",
                            entity_id,
                            target_state,
                            self._presence_simulation_history_days,
                        )
                        friendly_name = current.name or entity_id
                        self._log_event(f"Simulation Présence: {friendly_name} -> {target_state}")
                        
                        # Record in presence simulation event history
                        sim_event = {
                            "time": utcnow().isoformat(),
                            "entity_id": entity_id,
                            "name": friendly_name,
                            "state": target_state,
                            "domain": domain,
                            "history_days": self._presence_simulation_history_days
                        }
                        self._presence_simulation_events.insert(0, sim_event)
                        if len(self._presence_simulation_events) > 50:
                            self._presence_simulation_events = self._presence_simulation_events[:50]
                        self.async_write_ha_state()

                        await self.hass.services.async_call(
                            domain, service, {"entity_id": entity_id}
                        )
        except Exception as e:
            _LOGGER.debug("Domolink: Simulation Présence tick error: %s", e)

    # ─── Code Validation ──────────────────────────────────────────

    def _validate_code(self, code):
        """Validate given code and return user name if valid."""
        if not code:
            if not self._users:
                return "Dashboard"
            return None

        if code in ("MOBILE_APP", "AUTO_SCHEDULE", "GEOFENCE"):
            special_names = {
                "MOBILE_APP": "App Mobile",
                "AUTO_SCHEDULE": "Planification horaire",
                "GEOFENCE": "Géolocalisation"
            }
            return special_names.get(code, "Système")

        current_time = self.hass.loop.time()  # Fix #15: async-safe time

        if self._blocked_until > current_time:
            remaining = int(self._blocked_until - current_time)
            _LOGGER.warning("Keypad blocked for %d more seconds", remaining)
            return None

        # Check Duress code
        if self._duress_code and code == self._duress_code:
            return "DURESS"

        user_name = self._users.get(code)
        if user_name:
            self._failed_attempts = 0
            return user_name

        # Invalid code
        self._failed_attempts += 1
        _LOGGER.warning("Invalid code attempt %d/3", self._failed_attempts)

        if self._failed_attempts >= 3:
            self._blocked_until = current_time + 300  # 5 minutes
            # Fix #18: notification BEFORE resetting counter
            self.hass.async_create_task(
                self._async_send_notification(
                    f"⚠️ Clavier verrouillé 5 minutes après {self._failed_attempts} tentatives erronées."
                )
            )
            self._failed_attempts = 0

        return None

    def _record_arm_event(self, action, user, mode=None):
        """Record arm/disarm events into history."""
        event = {
            "time": utcnow().isoformat(),
            "action": action,
            "user": user or "Système",
        }
        if mode:
            event["mode"] = mode
            
        self._arm_history.insert(0, event)
        if len(self._arm_history) > 50:
            self._arm_history = self._arm_history[:50]

    async def async_alarm_disarm(self, code=None):
        """Send disarm command."""
        user = self._validate_code(code)
        if not user:
            _LOGGER.warning("Invalid code provided for disarm")
            raise HomeAssistantError("Code PIN invalide.")

        if user == "DURESS":
            await self._async_send_notification(
                "🆘 ALERTE SOS SILENCIEUSE (Code de détresse utilisé) 🆘",
                is_alert=True,
                is_emergency=True
            )
            # Continue to disarm silently so intruder doesn't know

        self._record_arm_event("disarm", user)

        self._cancel_all_tasks()
        self._state = AlarmControlPanelState.DISARMED
        self._last_user = user
        self._faults.clear()
        self._bypassed_sensors.clear()
        self._triggered_by = None
        self._log_event(f"Alarme Désarmée par {user}")
        self.async_write_ha_state()

        await self._async_turn_off_siren()

        if user != "DURESS":
            # Personalized TTS greeting
            self.hass.async_create_task(
                self._async_play_tts(f"Alarme désarmée. Bienvenue {user}.")
            )

    async def _check_bypass(self, target_mode="AWAY", force=False):
        """Check if sensors are open or unavailable before arming."""
        open_sensors = []
        # Check opening sensors
        for sensor in self._opening_sensors:
            if sensor in self._bypassed_sensors:
                continue
            state = self.hass.states.get(sensor)
            if not state or str(state.state).lower() in ("on", "open", "true", "detected", "unlocked", "1", "unavailable", "unknown"):
                name = state.name if state and state.name else sensor
                open_sensors.append(name)

        # Also for NIGHT mode, check night sensors
        if target_mode == "NIGHT":
            for sensor in self._night_sensors:
                if sensor in self._bypassed_sensors:
                    continue
                state = self.hass.states.get(sensor)
                if not state or str(state.state).lower() in ("on", "open", "true", "detected", "unlocked", "1", "unavailable", "unknown"):
                    name = state.name if state and state.name else sensor
                    if name not in open_sensors:
                        open_sensors.append(name)

        if open_sensors:
            if not self._bypass_allowed and not force:
                _LOGGER.warning("Cannot arm, sensors open: %s", open_sensors)
                sensor_list = "\n".join(f"• {s}" for s in open_sensors)
                message = (
                    f"⛔ Impossible d'armer l'alarme.\n\n"
                    f"Capteur(s) ouvert(s) :\n{sensor_list}\n\n"
                    f"Voulez-vous forcer la mise en marche (Bypass) ?"
                )
                self._log_event(f"Échec armement : {len(open_sensors)} capteur(s) ouvert(s)")
                
                # Send actionable notification to mobile app (Prompt for bypass & PIN)
                action_data = {
                    "actions": [
                        {
                            "action": f"DOMOLINK_FORCE_ARM_{target_mode}",
                            "title": "⚡ Forcer la mise en marche",
                            "behavior": "textInput",
                            "textInputButtonTitle": "Valider",
                            "textInputPlaceholder": "Code PIN (optionnel)",
                        },
                        {
                            "action": "DOMOLINK_CANCEL_ARM",
                            "title": "❌ Annuler",
                            "destructive": True,
                        },
                    ]
                }
                await self._async_send_notification(message, custom_data=action_data)
                raise HomeAssistantError(f"Échec armement : {len(open_sensors)} capteur(s) ouvert(s). Consultez vos notifications.")
            else:
                # Bypass is globally enabled in config
                sensor_list = "\n".join(f"• {s}" for s in open_sensors)
                await self._async_send_notification(
                    f"⚠️ Alarme armée avec bypass automatique.\nCapteurs ignorés :\n{sensor_list}"
                )

        # Proactive low battery check on armed sensors (Health Check Pro)
        battery_warnings = []
        for sensor in (self._opening_sensors + self._motion_sensors + self._night_sensors):
            if sensor in self._bypassed_sensors:
                continue
            batt = self._get_device_battery_level(sensor)
            if batt is not None and batt <= 15:
                s_state = self.hass.states.get(sensor)
                s_name = s_state.name if s_state and s_state.name else sensor
                battery_warnings.append(f"{s_name} ({int(batt)}%)")

        if battery_warnings:
            batt_str = ", ".join(battery_warnings)
            self._log_event(f"Pile(s) faible(s) détectée(s) : {batt_str}")
            self.hass.async_create_task(
                self._async_send_notification(f"🪫 Attention : Pile faible sur {batt_str}")
            )

        return True

    async def async_alarm_arm_home(self, code=None):
        """Send arm home command."""
        user = None
        if code:
            user = self._validate_code(code)
            if not user:
                raise HomeAssistantError("Code invalide.")

        if not await self._check_bypass(target_mode="HOME", force=(user is not None)):
            return
        self._pre_trigger_state = AlarmControlPanelState.ARMED_HOME  # Fix #11
        self._state = AlarmControlPanelState.ARMED_HOME
        self._last_user = user or "Dashboard"
        self._record_arm_event("arm", self._last_user, "HOME")
        self._log_event(f"Alarme Armée (Mode: Présent) par {self._last_user}")
        self.async_write_ha_state()

    async def async_alarm_arm_away(self, code=None):
        """Send arm away command."""
        user = None
        if code:
            user = self._validate_code(code)
            if not user:
                raise HomeAssistantError("Code invalide.")

        if not await self._check_bypass(target_mode="AWAY", force=(user is not None)):
            return

        self._last_user = user or "Dashboard"
        self._record_arm_event("arm", self._last_user, "AWAY")
        
        if self._exit_delay > 0:
            self._state = AlarmControlPanelState.ARMING
            self.async_write_ha_state()
            self._arming_task = async_call_later(
                self.hass,
                self._exit_delay,
                self._cb_arm_away_complete,  # Fix #2: sync callback
            )
        else:
            self._cb_arm_away_complete()

    @callback
    def _cb_arm_away_complete(self, now=None):
        """Sync @callback: finalize arm away (Fix #2)."""
        self._state = AlarmControlPanelState.ARMED_AWAY
        self._pre_trigger_state = AlarmControlPanelState.ARMED_AWAY
        self._log_event(f"Alarme Armée (Mode: Absent) par {self._last_user}")
        self._start_presence_simulation()
        self.async_write_ha_state()
        self._arming_task = None

    async def async_alarm_arm_night(self, code=None):
        """Send arm night command."""
        user = None
        if code:
            user = self._validate_code(code)
            if not user:
                raise HomeAssistantError("Code invalide.")

        if not await self._check_bypass(target_mode="NIGHT", force=(user is not None)):
            return
        self._pre_trigger_state = AlarmControlPanelState.ARMED_NIGHT  # Fix #11
        self._state = AlarmControlPanelState.ARMED_NIGHT
        self._last_user = user or "Dashboard"
        self._record_arm_event("arm", self._last_user, "NIGHT")
        self._log_event(f"Alarme Armée (Mode: Nuit) par {self._last_user}")
        self.async_write_ha_state()

    # ─── New Services & Scheduled Actions ─────────────────────────

    async def async_panic(self, activate_sirens=False):
        """Trigger panic mode."""
        self._log_event("🚨 BOUTON PANIQUE SOS ACTIVÉ")
        
        # Determine triggering user/location
        message = "🚨 ALERTE PANIQUE SOS DÉCLENCHÉE MANUELLEMENT 🚨"
        
        # 1. Notify everyone including emergency contact (is_emergency=True includes GPS)
        await self._async_send_notification(
            message,
            is_alert=True,
            is_emergency=True
        )
        
        # 2. Trigger Sirens if requested
        if activate_sirens and self._sirens:
            self._log_event("Activation manuelle des sirènes (Panique)")
            try:
                await self.hass.services.async_call(
                    "homeassistant", "turn_on",
                    {"entity_id": self._sirens},
                )
                self._siren_task = async_call_later(
                    self.hass,
                    self._siren_duration,
                    self._cb_turn_off_siren,
                )
            except Exception as e:
                _LOGGER.error("Failed to turn on sirens for panic: %s", e)
                
        # 3. Trigger Panic Lights
        if self._lights:
            try:
                await self.hass.services.async_call(
                    "light", "turn_on",
                    {"entity_id": self._lights, "color_name": "red", "brightness": 255},
                )
            except Exception:
                try:
                    await self.hass.services.async_call(
                        "homeassistant", "turn_on",
                        {"entity_id": self._lights},
                    )
                except Exception as e:
                    pass

    @callback
    def _cb_siren_test(self, now):
        """Run weekly siren test."""
        # Only run on the configured day
        if now.weekday() != self._siren_test_day:
            return
            
        self._log_event("Test automatique des sirènes en cours...")
        self.hass.async_create_task(self._async_run_siren_test())
        
    async def _async_run_siren_test(self):
        """Execute the siren test asynchronously."""
        if not self._sirens:
            return
            
        failed_sirens = []
        for siren in self._sirens:
            try:
                # Turn on
                await self.hass.services.async_call("homeassistant", "turn_on", {"entity_id": siren})
                await asyncio.sleep(1.0) # wait 1 second
                # Turn off
                await self.hass.services.async_call("homeassistant", "turn_off", {"entity_id": siren})
            except Exception as e:
                failed_sirens.append(siren)
                
        if failed_sirens:
            msg = f"⚠️ Le test automatique des sirènes a échoué sur : {', '.join(failed_sirens)}."
            self._log_event("Échec du test sirène")
            await self._async_send_notification(msg)
        else:
            self._log_event("Test sirène OK")
            await self._async_send_notification("✅ Test automatique hebdomadaire des sirènes réussi.")

    @callback
    def _cb_schedule_arm(self, now):
        """Arm alarm on schedule."""
        if self._state == AlarmControlPanelState.DISARMED:
            _LOGGER.info("Auto-armement horaire activé")
            self._log_event("Auto-armement horaire déclenché")
            
            if self._schedule_mode == "night":
                self.hass.async_create_task(self.async_alarm_arm_night("AUTO_SCHEDULE"))
            else:
                self.hass.async_create_task(self.async_alarm_arm_home("AUTO_SCHEDULE"))
                
            self.hass.async_create_task(
                self._async_send_notification(f"⏰ Armement automatique horaire activé (Mode {self._schedule_mode}).")
            )

    @callback
    def _cb_schedule_disarm(self, now):
        """Disarm alarm on schedule."""
        if self._state in (AlarmControlPanelState.ARMED_HOME, AlarmControlPanelState.ARMED_NIGHT):
            _LOGGER.info("Auto-désarmement horaire activé")
            self._log_event("Auto-désarmement horaire déclenché")
            
            self.hass.async_create_task(self.async_alarm_disarm("AUTO_SCHEDULE"))
            
            self.hass.async_create_task(
                self._async_send_notification("⏰ Désarmement automatique horaire effectué.")
            )
