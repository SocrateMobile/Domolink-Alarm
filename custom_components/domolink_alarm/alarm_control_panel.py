"""Interfaces with Domolink Alarm."""
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
    CONF_NIGHT_SENSORS,
    CONF_PERSONS,
    CONF_MOTION_SENSORS,
    CONF_CAMERAS,
    CONF_TAMPER_SENSORS,
    CONF_SIRENS,
    CONF_LIGHTS,
    CONF_MEDIA_PLAYERS,
    CONF_NOTIFY_SERVICES,
    CONF_USERS_CODES,
    CONF_DURESS_CODE,
    CONF_RFID_TAGS,
    CONF_BYPASS_ALLOWED,
    CONF_HEALTH_CHECK,
    CONF_GEOFENCE_AUTO_ARM,
    CONF_EXIT_DELAY,
    CONF_ENTRY_DELAY,
    CONF_SIREN_DURATION,
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
            sw_version="0.6.14-beta",
        )

        self._siren_task = None
        self._arming_task = None
        self._pending_task = None
        self._faults = []
        self._triggered_by = None
        self._event_sensor = None

        self._failed_attempts = 0
        self._blocked_until = 0.0

        self._last_triggered_by = None
        self._last_user = None

        self._users = {}
        self._duress_code = ""

        self._load_config()

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

        self._opening_sensors = options.get(CONF_OPENING_SENSORS, data.get(CONF_OPENING_SENSORS)) or []
        self._night_sensors = options.get(CONF_NIGHT_SENSORS, data.get(CONF_NIGHT_SENSORS)) or []
        self._persons = options.get(CONF_PERSONS, data.get(CONF_PERSONS)) or []
        self._motion_sensors = options.get(CONF_MOTION_SENSORS, data.get(CONF_MOTION_SENSORS)) or []
        self._cameras = options.get(CONF_CAMERAS, data.get(CONF_CAMERAS)) or []
        self._tamper_sensors = options.get(CONF_TAMPER_SENSORS, data.get(CONF_TAMPER_SENSORS)) or []

        self._sirens = options.get(CONF_SIRENS, data.get(CONF_SIRENS)) or []
        self._lights = options.get(CONF_LIGHTS, data.get(CONF_LIGHTS)) or []
        self._media_players = options.get(CONF_MEDIA_PLAYERS, data.get(CONF_MEDIA_PLAYERS)) or []
        self._notify_services = options.get(CONF_NOTIFY_SERVICES, data.get(CONF_NOTIFY_SERVICES)) or []

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
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {
            "faults": self._faults,
            "triggered_by": self._triggered_by,
        }

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
            "last_triggered_by": self._last_triggered_by,
            "last_user": self._last_user,
            "failed_attempts": self._failed_attempts,
            "geofence_active": self._geofence_auto_arm,
            "health_check_active": self._health_check,
        }

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

        # Track sensor changes
        all_sensors = list(set(self._opening_sensors + self._motion_sensors + self._tamper_sensors + self._night_sensors + self._persons))
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

        # Geofencing
        if self._geofence_auto_arm:
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

    # ─── Geofencing ───────────────────────────────────────────────

    async def _async_zone_changed(self, event):
        """Handle zone.home state changes for auto arm/disarm."""
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
            # Everyone left → Auto Arm
            if self._state == AlarmControlPanelState.DISARMED:
                _LOGGER.info("Geofencing: No one at home, auto arming away")
                await self._async_send_notification(
                    "🏠 Domolink: Plus personne à la maison, armement automatique activé."
                )
                await self.async_alarm_arm_away()

        elif old_count == 0 and new_count > 0:
            # Someone arrived → Auto Disarm
            if self._state in (
                AlarmControlPanelState.ARMED_AWAY,
                AlarmControlPanelState.ARMED_NIGHT,
                AlarmControlPanelState.ARMING,
            ):
                _LOGGER.info("Geofencing: Someone arrived, auto disarming")
                self._cancel_all_tasks()
                self._state = AlarmControlPanelState.DISARMED
                self._last_user = "Géolocalisation"
                self.async_write_ha_state()
                await self._async_turn_off_siren()
                await self._async_send_notification(
                    "🏠 Domolink: Retour détecté, désarmement automatique."
                )

    # ─── Mobile Actionable Notifications ──────────────────────────

    async def _async_handle_mobile_action(self, event):
        """Handle actionable notification button clicks."""
        action = event.data.get("action")
        reply_text = event.data.get("reply_text")

        if action == "DOMOLINK_DISARM":
            _LOGGER.info("Disarm triggered via mobile actionable notification")
            self._cancel_all_tasks()
            self._state = AlarmControlPanelState.DISARMED
            self._last_user = "Mobile App"
            self._faults.clear()
            self._triggered_by = None
            self.async_write_ha_state()
            await self._async_turn_off_siren()
            self._log_event("Alarme Désarmée (Mobile App)")
            await self._async_send_notification(
                "✅ Alarme désarmée via Apple Watch / Mobile."
            )

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

    # ─── Health Check ─────────────────────────────────────────────

    async def _async_perform_health_check(self, now=None):
        """Check battery and availability of all linked devices (Fix #13)."""
        all_devices = (
            self._opening_sensors
            + self._motion_sensors
            + self._tamper_sensors
            + self._sirens
            + self._cameras
            + self._lights
        )
        if not all_devices:
            return

        warnings = []
        for device_id in all_devices:
            state = self.hass.states.get(device_id)
            if not state or state.state in ("unavailable", "unknown"):
                friendly = state.name if state else device_id
                warnings.append(f"⚠️ {friendly} est indisponible.")
                continue
            # Check battery (try both common attribute names)
            battery = state.attributes.get("battery_level") or state.attributes.get("battery")
            if battery is not None:
                try:
                    if float(battery) < 10:
                        warnings.append(f"🪫 {state.name} batterie faible ({battery}%).")
                except (ValueError, TypeError):
                    pass

        if warnings:
            notify_msg = "🔋 Health Check Domolink:\n" + "\n".join(warnings)
            await self._async_send_notification(notify_msg)

    # ─── Notifications ────────────────────────────────────────────

    async def _async_send_notification(self, message, is_alert=False, custom_data=None):
        """Send notifications to configured services/entities with universal compatibility."""
        if not self._notify_services:
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
            data.update(alert_data)

        if custom_data:
            data.update(custom_data)

        for target in self._notify_services:
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

        _LOGGER.info(
            "Domolink Alarm: Détection sur %s (état: %s, état alarme: %s)",
            entity_id,
            state_val,
            self._state,
        )

        # Tamper triggers immediately regardless of state (24/7)
        if entity_id in self._tamper_sensors:
            _LOGGER.warning("Tamper / Sabotage détecté sur %s !", entity_id)
            await self._async_trigger_alarm(entity_id)
            return

        # Ignore sensors when disarmed or during exit delay
        if self._state in (
            AlarmControlPanelState.DISARMED,
            AlarmControlPanelState.ARMING,
        ):
            _LOGGER.debug(
                "Capteur ignoré car l'alarme est en état %s (délai de sortie ou désarmée)",
                self._state,
            )
            return

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

        # 1. Critical notification with disarm button
        await self._async_send_notification(
            f"🚨 INTRUSION DÉTECTÉE 🚨\nCapteur : {name}",
            is_alert=True,
        )

        # 2. Camera Recording
        if self._cameras:
            self._log_event(f"Lancement de l'enregistrement sur {len(self._cameras)} caméra(s)")
        for camera in self._cameras:
            try:
                await self.hass.services.async_call(
                    "camera", "record",
                    {"entity_id": camera, "duration": 30},
                )
            except Exception as e:
                _LOGGER.error("Failed to record camera %s: %s", camera, e)

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

    # ─── Code Validation ──────────────────────────────────────────

    def _validate_code(self, code):
        """Validate given code and return user name if valid."""
        if not code:
            return None

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

    # ─── Arm / Disarm Commands ────────────────────────────────────

    async def async_alarm_disarm(self, code=None):
        """Send disarm command."""
        user = self._validate_code(code)
        if not user:
            _LOGGER.warning("Invalid code provided for disarm")
            return

        if user == "DURESS":
            await self._async_send_notification(
                "🆘 ALERTE SOS SILENCIEUSE (Code de détresse utilisé) 🆘"
            )
            # Continue to disarm silently so intruder doesn't know

        self._cancel_all_tasks()
        self._state = AlarmControlPanelState.DISARMED
        self._last_user = user
        self._faults.clear()
        self._triggered_by = None
        self._log_event(f"Alarme Désarmée (Utilisateur: {user})")
        self.async_write_ha_state()

        await self._async_turn_off_siren()

        if user != "DURESS":
            # Personalized TTS greeting
            self.hass.async_create_task(
                self._async_play_tts(f"Alarme désarmée. Bienvenue {user}.")
            )

    async def _check_bypass(self, target_mode="AWAY", force=False):
        """Check if sensors are open before arming."""
        open_sensors = []
        # Check opening sensors
        for sensor in self._opening_sensors:
            state = self.hass.states.get(sensor)
            if state and str(state.state).lower() in ("on", "open", "true", "detected", "unlocked", "1"):
                open_sensors.append(state.name or sensor)

        # Also for NIGHT mode, check night sensors
        if target_mode == "NIGHT":
            for sensor in self._night_sensors:
                state = self.hass.states.get(sensor)
                if state and str(state.state).lower() in ("on", "open", "true", "detected", "unlocked", "1"):
                    if (state.name or sensor) not in open_sensors:
                        open_sensors.append(state.name or sensor)

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
        self._log_event(f"Alarme Armée (Mode: Nuit) par {self._last_user}")
        self.async_write_ha_state()
