"""Interfaces with Domolink Alarm."""
import asyncio
from datetime import timedelta
import hashlib
import json
import logging
import os
import secrets

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
    CodeFormat,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.event import (
    async_call_later,
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import dt as dt_util
from homeassistant.util.dt import now as dt_now, utcnow

from .cloud_uploader import (
    CloudUploader,
    ReusedSessionFTP_TLS,
    _ReusedSslSocket,
    _build_ftp_target_path,
    _create_ftp_client,
    _ftp_navigate_and_ensure_dirs,
    _sftp_navigate_and_ensure_dirs,
)
from .const import (
    VERSION,
    CONF_BYPASS_ALLOWED,
    CONF_CAMERAS,
    CONF_CAMERAS_ARM_ENTITIES,
    CONF_CAMERAS_ARM_ENTITIES_LABELS,
    CONF_CAMERAS_LABELS,
    CONF_CHIME_MODE,
    CONF_CROSS_ZONING,
    CONF_CROSS_ZONING_WINDOW,
    CONF_DETERRENCE_ENABLED,
    CONF_DETERRENCE_LEVEL,
    CONF_DURESS_CODE,
    CONF_EMERGENCY_CONTACT,
    CONF_EMERGENCY_CONTACT_LABELS,
    CONF_ENTRY_DELAY,
    CONF_EXIT_DELAY,
    CONF_FAILOVER_GSM_ENABLED,
    CONF_FAILOVER_GSM_SERVICE,
    CONF_FAILOVER_LOCAL_ALARM,
    CONF_FREE_MOBILE_PASS,
    CONF_FREE_MOBILE_USER,
    CONF_FTP_ALLOW_INSECURE_TLS,
    CONF_FTP_ENABLED,
    CONF_FTP_HOST,
    CONF_FTP_PASS,
    CONF_FTP_PATH,
    CONF_FTP_PORT,
    CONF_FTP_PROTOCOL,
    CONF_FTP_USER,
    CONF_GEOFENCE_APPROACH_DISTANCE,
    CONF_GEOFENCE_APPROACH_REMINDER,
    CONF_GEOFENCE_AUTO_ARM,
    CONF_GEOFENCE_REMINDER,
    CONF_GEOFENCE_REMINDER_DELAY,
    CONF_GLOBAL_CAMERAS,
    CONF_GLOBAL_CAMERAS_LABELS,
    CONF_GOOGLE_DRIVE_CLIENT_ID,
    CONF_GOOGLE_DRIVE_CLIENT_SECRET,
    CONF_GOOGLE_DRIVE_ENABLED,
    CONF_GOOGLE_DRIVE_FOLDER_ID,
    CONF_GOOGLE_DRIVE_METHOD,
    CONF_GOOGLE_DRIVE_REFRESH_TOKEN,
    CONF_GOOGLE_DRIVE_WEBHOOK_URL,
    CONF_HEALTH_CHECK,
    CONF_ICLOUD_ACCOUNT,
    CONF_ICLOUD_DEVICES,
    CONF_KEYPAD_BEEP_ENTRY,
    CONF_KEYPAD_BEEP_EXIT,
    CONF_KEYPAD_ENABLED,
    CONF_KEYPADS,
    CONF_KEYPADS_LABELS,
    CONF_LIGHTS,
    CONF_LIGHTS_LABELS,
    CONF_MEDIA_MAX_SIZE_MB,
    CONF_MEDIA_PATH,
    CONF_MEDIA_PLAYERS,
    CONF_MEDIA_PLAYERS_LABELS,
    CONF_MEDIA_RETENTION_DAYS,
    CONF_MOTION_SENSORS,
    CONF_MOTION_SENSORS_LABELS,
    CONF_MQTT_ENABLED,
    CONF_MQTT_REQUIRE_CODE,
    CONF_MQTT_TOPIC_BASE,
    CONF_NAME,
    CONF_NAS_CONFIGS,
    CONF_NAS_TYPE,
    CONF_NF_A2P_MODE,
    CONF_NF_A2P_PRE_ALERT_CHIME,
    CONF_NF_A2P_STRICT_DISTINCT,
    CONF_NF_A2P_WINDOW,
    CONF_NIGHT_SENSORS,
    CONF_NIGHT_SENSORS_LABELS,
    CONF_NOTIFY_SERVICES,
    CONF_NOTIFY_SERVICES_LABELS,
    CONF_OPENING_SENSORS,
    CONF_OPENING_SENSORS_LABELS,
    CONF_PERSONS,
    CONF_PERSONS_LABELS,
    CONF_PRESENCE_SIMULATION_ENTITIES,
    CONF_PRESENCE_SIMULATION_HISTORY_DAYS,
    CONF_PRESENCE_SIMULATION_LABELS,
    CONF_PROXIMITY_SENSOR,
    CONF_RFID_TAGS,
    CONF_SAFETY_SENSORS,
    CONF_SAFETY_SENSORS_LABELS,
    CONF_SCHEDULE_ARM_TIME,
    CONF_SCHEDULE_DISARM_TIME,
    CONF_SCHEDULE_ENABLED,
    CONF_SCHEDULE_MODE,
    CONF_SIREN_DURATION,
    CONF_SIREN_TEST,
    CONF_SIREN_TEST_DAY,
    CONF_SIREN_TEST_HOUR,
    CONF_SIRENS,
    CONF_SIRENS_LABELS,
    CONF_TAMPER_SENSORS,
    CONF_TAMPER_SENSORS_LABELS,
    CONF_TELEGRAM_CHAT_ID,
    CONF_TELEGRAM_ENABLED,
    CONF_TELEGRAM_TOKEN,
    CONF_TTS_ALARM_MSG,
    CONF_TTS_PRE_ALERT_MSG,
    CONF_TTS_VOLUME_ALERT,
    CONF_TTS_VOLUME_INFO,
    CONF_USERS_CODES,
    CONF_USERS_PROFILES,
    CONF_WEBDAV_ENABLED,
    CONF_WEBDAV_PASS,
    CONF_WEBDAV_PATH,
    CONF_WEBDAV_URL,
    CONF_WEBDAV_USER,
    CONF_ZONE_LABELS,
    DEFAULT_BYPASS_ALLOWED,
    DEFAULT_CHIME_MODE,
    DEFAULT_CROSS_ZONING,
    DEFAULT_CROSS_ZONING_WINDOW,
    DEFAULT_DETERRENCE_ENABLED,
    DEFAULT_DETERRENCE_LEVEL,
    DEFAULT_ENTRY_DELAY,
    DEFAULT_EXIT_DELAY,
    DEFAULT_FAILOVER_GSM_ENABLED,
    DEFAULT_FAILOVER_LOCAL_ALARM,
    DEFAULT_FTP_ALLOW_INSECURE_TLS,
    DEFAULT_FTP_ENABLED,
    DEFAULT_FTP_PATH,
    DEFAULT_FTP_PORT,
    DEFAULT_FTP_PROTOCOL,
    DEFAULT_GEOFENCE_APPROACH_DISTANCE,
    DEFAULT_GEOFENCE_APPROACH_REMINDER,
    DEFAULT_GEOFENCE_AUTO_ARM,
    DEFAULT_GEOFENCE_REMINDER,
    DEFAULT_GEOFENCE_REMINDER_DELAY,
    DEFAULT_GOOGLE_DRIVE_ENABLED,
    DEFAULT_GOOGLE_DRIVE_METHOD,
    DEFAULT_HEALTH_CHECK,
    DEFAULT_KEYPAD_BEEP_ENTRY,
    DEFAULT_KEYPAD_BEEP_EXIT,
    DEFAULT_KEYPAD_ENABLED,
    DEFAULT_MEDIA_MAX_SIZE_MB,
    DEFAULT_MEDIA_PATH,
    DEFAULT_MEDIA_RETENTION_DAYS,
    DEFAULT_MQTT_ENABLED,
    DEFAULT_MQTT_REQUIRE_CODE,
    DEFAULT_MQTT_TOPIC_BASE,
    DEFAULT_NAME,
    DEFAULT_NAS_CONFIGS,
    DEFAULT_NAS_TYPE,
    DEFAULT_NF_A2P_MODE,
    DEFAULT_NF_A2P_PRE_ALERT_CHIME,
    DEFAULT_NF_A2P_STRICT_DISTINCT,
    DEFAULT_NF_A2P_WINDOW,
    DEFAULT_PRESENCE_SIMULATION_HISTORY_DAYS,
    DEFAULT_SCHEDULE_ARM_TIME,
    DEFAULT_SCHEDULE_DISARM_TIME,
    DEFAULT_SCHEDULE_ENABLED,
    DEFAULT_SCHEDULE_MODE,
    DEFAULT_SIREN_DURATION,
    DEFAULT_SIREN_TEST,
    DEFAULT_SIREN_TEST_DAY,
    DEFAULT_SIREN_TEST_HOUR,
    DEFAULT_TELEGRAM_ENABLED,
    DEFAULT_TTS_ALARM_MSG,
    DEFAULT_TTS_PRE_ALERT_MSG,
    DEFAULT_TTS_VOLUME_ALERT,
    DEFAULT_TTS_VOLUME_INFO,
    DEFAULT_WEBDAV_ENABLED,
    DEFAULT_WEBDAV_PATH,
    DOMAIN,
    FTP_PROTOCOLS,
    SECRET_MASK,
)
from .geofencing import GeofenceManager
from .media_manager import MediaManager
from .notification_manager import NotificationManager
from .presence_simulation import PresenceSimulator
from .security_utils import (
    hash_pin,
    is_hashed,
    mask_secret,
    sanitize_log_payload,
    verify_pin,
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
    hass.data.setdefault(DOMAIN, {}).setdefault(entry.entry_id, {})["entity"] = entity
    async_add_entities([entity], True)

    async def async_handle_bypass_sensor(call):
        sensor_id = call.data.get("entity_id")
        if sensor_id:
            await entity.async_bypass_sensor(sensor_id)

    async def async_handle_unbypass_sensor(call):
        sensor_id = call.data.get("entity_id")
        if sensor_id:
            await entity.async_unbypass_sensor(sensor_id)

    async def async_handle_panic(call):
        activate_sirens = call.data.get("activate_sirens", False)
        await entity.async_panic(activate_sirens)

    async def async_handle_start_sim(call):
        await entity.async_start_presence_simulation()

    async def async_handle_stop_sim(call):
        await entity.async_stop_presence_simulation()

    async def async_handle_toggle_sim(call):
        await entity.async_toggle_presence_simulation()

    async def async_handle_update_settings(call):
        await entity.async_update_settings(call)

    async def async_handle_media_action(call):
        await entity.async_media_action(call)

    async def async_handle_test_cameras(call):
        await entity.async_test_cameras_recording(call)

    async def async_handle_test_ftp(call):
        return await entity.async_test_ftp(call)

    async def async_handle_test_webdav(call):
        return await entity.async_test_webdav(call)

    async def async_handle_test_google_drive(call):
        return await entity.async_test_google_drive(call)

    async def async_handle_clean_media(call):
        await entity.async_clean_media(call)

    async def async_handle_add_user_profile(call):
        data = dict(call.data)
        data.pop("entity_id", None)
        await entity.async_add_user_profile(**data)

    async def async_handle_delete_user_profile(call):
        name = call.data.get("name")
        pin = call.data.get("pin")
        profile_id = call.data.get("id") or call.data.get("profile_id")
        await entity.async_delete_user_profile(profile_id=profile_id, pin=pin, name=name)

    async def async_handle_snooze_reminder(call):
        minutes = call.data.get("minutes", 15)
        await entity.async_snooze_reminder(minutes)

    async def async_handle_sync_physical_keypad(call):
        await entity.async_sync_keypads()

    async def async_handle_generate_incident_report(call):
        return entity.get_incident_report_data()

    hass.services.async_register(DOMAIN, "update_settings", async_handle_update_settings)
    hass.services.async_register(DOMAIN, "media_action", async_handle_media_action)
    hass.services.async_register(DOMAIN, "test_cameras_recording", async_handle_test_cameras)

    try:
        from homeassistant.core import SupportsResponse

        supports_opt = SupportsResponse.OPTIONAL
    except Exception:
        supports_opt = None

    if supports_opt is not None:
        hass.services.async_register(
            DOMAIN, "test_ftp", async_handle_test_ftp, supports_response=supports_opt
        )
        hass.services.async_register(
            DOMAIN, "test_webdav", async_handle_test_webdav, supports_response=supports_opt
        )
        hass.services.async_register(
            DOMAIN, "test_google_drive", async_handle_test_google_drive, supports_response=supports_opt
        )
        hass.services.async_register(
            DOMAIN, "generate_incident_report", async_handle_generate_incident_report, supports_response=supports_opt
        )
    else:
        hass.services.async_register(DOMAIN, "test_ftp", async_handle_test_ftp)
        hass.services.async_register(DOMAIN, "test_webdav", async_handle_test_webdav)
        hass.services.async_register(DOMAIN, "test_google_drive", async_handle_test_google_drive)
        hass.services.async_register(DOMAIN, "generate_incident_report", async_handle_generate_incident_report)

    hass.services.async_register(DOMAIN, "clean_media", async_handle_clean_media)
    hass.services.async_register(DOMAIN, "bypass_sensor", async_handle_bypass_sensor)
    hass.services.async_register(DOMAIN, "unbypass_sensor", async_handle_unbypass_sensor)
    hass.services.async_register(DOMAIN, "panic", async_handle_panic)
    hass.services.async_register(DOMAIN, "start_presence_simulation", async_handle_start_sim)
    hass.services.async_register(DOMAIN, "stop_presence_simulation", async_handle_stop_sim)
    hass.services.async_register(DOMAIN, "toggle_presence_simulation", async_handle_toggle_sim)
    hass.services.async_register(DOMAIN, "add_user_profile", async_handle_add_user_profile)
    hass.services.async_register(DOMAIN, "delete_user_profile", async_handle_delete_user_profile)
    hass.services.async_register(DOMAIN, "snooze_reminder", async_handle_snooze_reminder)
    hass.services.async_register(DOMAIN, "sync_physical_keypad", async_handle_sync_physical_keypad)


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

        _sw_version = VERSION
        try:
            _manifest_path = os.path.join(os.path.dirname(__file__), "manifest.json")
            with open(_manifest_path, encoding="utf-8") as _mf:
                _sw_version = json.load(_mf).get("version", _sw_version)
        except Exception:
            pass

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._unique_id)},
            name=self._attr_name,
            manufacturer="Domolink",
            model="Domolink Smart Alarm",
            sw_version=_sw_version,
        )

        self._system_version = _sw_version
        self._update_available = False
        self._latest_version = _sw_version
        self._release_notes = ""
        self._release_url = ""

        self._siren_task = None
        self._arming_task = None
        self._pending_task = None
        self._post_trigger_active = False
        self._disarm_cooldown_task = None
        self._faults = []
        self._bypassed_sensors = set()
        self._triggered_by = None
        self._last_triggered_by = None
        self._last_user = None
        self._event_sensor = None
        self._watch_sensor = None
        self._last_motion_detection = {}

        self._failed_attempts = 0
        self._blocked_until = 0.0

        self._users = {}
        self._duress_code = ""
        self._users_profiles = []
        self._arm_history = []
        self._system_events = []
        self._sensor_health = {}
        self._last_incident_report = {}

        # NF A2P Double Detection
        self._nf_a2p_mode = DEFAULT_NF_A2P_MODE
        self._nf_a2p_window = DEFAULT_NF_A2P_WINDOW
        self._nf_a2p_strict_distinct = DEFAULT_NF_A2P_STRICT_DISTINCT
        self._nf_a2p_pre_alert_chime = DEFAULT_NF_A2P_PRE_ALERT_CHIME
        self._pre_alert_active = False
        self._pre_alert_sensor = None
        self._pre_alert_sensor_name = None
        self._pre_alert_task = None
        self._pre_alert_expires_at = 0.0

        # Sub-Managers Initialization
        self.cloud_uploader = CloudUploader(
            self.hass,
            self._get_config_value,
            self._log_event,
            self.async_write_ha_state,
        )
        self.notification_manager = NotificationManager(
            self.hass,
            self._get_config_value,
            self._log_event,
            self.async_write_ha_state,
            self._async_turn_on_siren,
        )
        self.media_manager = MediaManager(
            self.hass,
            self._get_config_value,
            self._log_event,
            self.async_write_ha_state,
            self.cloud_uploader,
            self.notification_manager.async_send_notification,
        )
        self.presence_simulator = PresenceSimulator(
            self.hass,
            self._get_config_value,
            self._log_event,
            self.async_write_ha_state,
            lambda: self._state,
        )
        self.geofence_manager = GeofenceManager(
            self.hass,
            self,
            self._get_config_value,
            self._log_event,
            self.async_write_ha_state,
        )

        self._load_config()

    def _get_config_value(self, key, default=None):
        """Helper to get merged option / data value."""
        if not self._entry:
            return default
        options = self._entry.options or {}
        data = self._entry.data or {}
        return options.get(key, data.get(key, default))

    def _get_entity_labels(self, entity_id: str) -> set[str]:
        """Get all labels attached to an entity or its parent device."""
        if not entity_id:
            return set()
        labels = set()
        try:
            entity_reg = er.async_get(self.hass)
            entry = entity_reg.async_get(entity_id)
            if entry:
                if entry.labels:
                    labels.update(entry.labels)
                if entry.device_id:
                    device_reg = dr.async_get(self.hass)
                    dev = device_reg.async_get(entry.device_id)
                    if dev and dev.labels:
                        labels.update(dev.labels)
        except Exception as e:
            _LOGGER.debug("Domolink: Erreur lecture labels pour %s: %s", entity_id, e)
        return labels

    def _get_cameras_for_sensor(self, sensor_entity_id: str = None) -> tuple[list[str], set[str]]:
        """Return cameras associated with the triggering sensor's zone, plus global cameras."""
        if not self._cameras:
            return ([], set())

        if not sensor_entity_id or not self._zone_labels:
            return (list(self._cameras), set())

        sensor_labels = self._get_entity_labels(sensor_entity_id)
        matching_zones = sensor_labels.intersection(self._zone_labels)

        if not matching_zones:
            return (list(self._cameras), set())

        zone_cameras = []
        for cam in self._cameras:
            cam_labels = self._get_entity_labels(cam)
            if cam_labels.intersection(matching_zones):
                zone_cameras.append(cam)

        combined = list(zone_cameras)
        for g_cam in self._global_cameras:
            if g_cam in self._cameras and g_cam not in combined:
                combined.append(g_cam)

        if not combined:
            return (list(self._cameras), matching_zones)

        return (combined, matching_zones)

    def _get_entity_zones_map(self) -> dict[str, list[str]]:
        """Return mapping of entity_id -> list of zone label IDs."""
        if not self._zone_labels:
            return {}
        all_monitored = set(
            self._opening_sensors
            + self._motion_sensors
            + self._night_sensors
            + self._cameras
            + self._safety_sensors
            + self._tamper_sensors
        )
        zones_map = {}
        for eid in all_monitored:
            labels = self._get_entity_labels(eid)
            matching = list(labels.intersection(self._zone_labels))
            if matching:
                zones_map[eid] = matching
        return zones_map

    def _resolve_labels(self, label_ids: list, allowed_domains: list = None) -> list:
        """Find all entities matching the given labels and domains."""
        if not label_ids:
            return []

        entity_reg = er.async_get(self.hass)
        device_reg = dr.async_get(self.hass)
        matched_entities = set()

        for entity in entity_reg.entities.values():
            if entity.labels and any(label in entity.labels for label in label_ids):
                if not allowed_domains or entity.domain in allowed_domains:
                    matched_entities.add(entity.entity_id)

        for device in device_reg.devices.values():
            if device.labels and any(label in device.labels for label in label_ids):
                for entity in er.async_entries_for_device(entity_reg, device.id):
                    if not allowed_domains or entity.domain in allowed_domains:
                        matched_entities.add(entity.entity_id)

        return list(matched_entities)

    def _load_config(self):
        """Load configuration from entry data and options."""
        data = self._entry.data or {}
        options = self._entry.options or {}

        # Users and Codes parsing
        users_raw = options.get(CONF_USERS_CODES, data.get(CONF_USERS_CODES, ""))
        self._users = {}
        if isinstance(users_raw, dict):
            self._users = {str(k).strip(): str(v).strip() for k, v in users_raw.items()}
        elif isinstance(users_raw, str) and users_raw:
            for pair in users_raw.split(","):
                pair = pair.strip()
                if ":" in pair:
                    name, code = pair.split(":", 1)
                    name, code = name.strip(), code.strip()
                    if name and code:
                        self._users[name] = code

        self._duress_code = str(
            options.get(CONF_DURESS_CODE, data.get(CONF_DURESS_CODE, ""))
        ).strip()

        # RFID Tags parsing
        rfid_raw = options.get(CONF_RFID_TAGS, data.get(CONF_RFID_TAGS, ""))
        self._rfid_tags = {}
        if isinstance(rfid_raw, dict):
            self._rfid_tags = {str(k).strip(): str(v).strip() for k, v in rfid_raw.items()}
        elif isinstance(rfid_raw, str) and rfid_raw:
            for pair in rfid_raw.split(","):
                pair = pair.strip()
                if ":" in pair:
                    tag_id, name = pair.split(":", 1)
                    tag_id, name = tag_id.strip(), name.strip()
                    if tag_id and name:
                        self._rfid_tags[tag_id] = name

        self._exit_delay = int(options.get(CONF_EXIT_DELAY, data.get(CONF_EXIT_DELAY, DEFAULT_EXIT_DELAY)))
        self._entry_delay = int(options.get(CONF_ENTRY_DELAY, data.get(CONF_ENTRY_DELAY, DEFAULT_ENTRY_DELAY)))
        self._siren_duration = int(options.get(CONF_SIREN_DURATION, data.get(CONF_SIREN_DURATION, DEFAULT_SIREN_DURATION)))
        self._bypass_allowed = bool(options.get(CONF_BYPASS_ALLOWED, data.get(CONF_BYPASS_ALLOWED, DEFAULT_BYPASS_ALLOWED)))
        self._health_check = bool(options.get(CONF_HEALTH_CHECK, data.get(CONF_HEALTH_CHECK, DEFAULT_HEALTH_CHECK)))
        self._chime_mode = bool(options.get(CONF_CHIME_MODE, data.get(CONF_CHIME_MODE, DEFAULT_CHIME_MODE)))
        self._cross_zoning = bool(options.get(CONF_CROSS_ZONING, data.get(CONF_CROSS_ZONING, DEFAULT_CROSS_ZONING)))
        self._cross_zoning_window = int(options.get(CONF_CROSS_ZONING_WINDOW, data.get(CONF_CROSS_ZONING_WINDOW, DEFAULT_CROSS_ZONING_WINDOW)))

        # Siren Test
        self._siren_test = bool(options.get(CONF_SIREN_TEST, data.get(CONF_SIREN_TEST, DEFAULT_SIREN_TEST)))
        self._siren_test_day = int(options.get(CONF_SIREN_TEST_DAY, data.get(CONF_SIREN_TEST_DAY, DEFAULT_SIREN_TEST_DAY)))
        self._siren_test_hour = int(options.get(CONF_SIREN_TEST_HOUR, data.get(CONF_SIREN_TEST_HOUR, DEFAULT_SIREN_TEST_HOUR)))

        # Scheduling
        self._schedule_enabled = bool(options.get(CONF_SCHEDULE_ENABLED, data.get(CONF_SCHEDULE_ENABLED, DEFAULT_SCHEDULE_ENABLED)))
        self._schedule_arm_time = options.get(CONF_SCHEDULE_ARM_TIME, data.get(CONF_SCHEDULE_ARM_TIME, DEFAULT_SCHEDULE_ARM_TIME))
        self._schedule_disarm_time = options.get(CONF_SCHEDULE_DISARM_TIME, data.get(CONF_SCHEDULE_DISARM_TIME, DEFAULT_SCHEDULE_DISARM_TIME))
        self._schedule_mode = options.get(CONF_SCHEDULE_MODE, data.get(CONF_SCHEDULE_MODE, DEFAULT_SCHEDULE_MODE))

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
        self._notify_services = get_merged(CONF_NOTIFY_SERVICES, CONF_NOTIFY_SERVICES_LABELS, ["notify", "script"])
        self._emergency_contact = get_merged(CONF_EMERGENCY_CONTACT, CONF_EMERGENCY_CONTACT_LABELS, ["notify", "script"])
        self._zone_labels = options.get(CONF_ZONE_LABELS, data.get(CONF_ZONE_LABELS, [])) or []
        self._global_cameras = get_merged(CONF_GLOBAL_CAMERAS, CONF_GLOBAL_CAMERAS_LABELS, ["camera"])
        self._cameras_arm_entities = get_merged(CONF_CAMERAS_ARM_ENTITIES, CONF_CAMERAS_ARM_ENTITIES_LABELS, ["switch", "alarm_control_panel", "camera"])
        self._keypads = get_merged(CONF_KEYPADS, CONF_KEYPADS_LABELS, ["switch", "binary_sensor"])

        self._mqtt_enabled = options.get(CONF_MQTT_ENABLED, data.get(CONF_MQTT_ENABLED, DEFAULT_MQTT_ENABLED))
        self._mqtt_topic_base = options.get(CONF_MQTT_TOPIC_BASE, data.get(CONF_MQTT_TOPIC_BASE, DEFAULT_MQTT_TOPIC_BASE))
        self._mqtt_require_code = options.get(CONF_MQTT_REQUIRE_CODE, data.get(CONF_MQTT_REQUIRE_CODE, DEFAULT_MQTT_REQUIRE_CODE))

        # NF A2P Double Detection
        self._nf_a2p_mode = bool(options.get(CONF_NF_A2P_MODE, data.get(CONF_NF_A2P_MODE, DEFAULT_NF_A2P_MODE)))
        self._nf_a2p_window = int(options.get(CONF_NF_A2P_WINDOW, data.get(CONF_NF_A2P_WINDOW, DEFAULT_NF_A2P_WINDOW)))
        self._nf_a2p_strict_distinct = bool(options.get(CONF_NF_A2P_STRICT_DISTINCT, data.get(CONF_NF_A2P_STRICT_DISTINCT, DEFAULT_NF_A2P_STRICT_DISTINCT)))
        self._nf_a2p_pre_alert_chime = bool(options.get(CONF_NF_A2P_PRE_ALERT_CHIME, data.get(CONF_NF_A2P_PRE_ALERT_CHIME, DEFAULT_NF_A2P_PRE_ALERT_CHIME)))

        # Extended User Profiles
        raw_profiles = options.get(CONF_USERS_PROFILES, data.get(CONF_USERS_PROFILES, []))
        if isinstance(raw_profiles, str):
            try:
                self._users_profiles = json.loads(raw_profiles) if raw_profiles.strip() else []
            except Exception:
                self._users_profiles = []
        elif isinstance(raw_profiles, list):
            self._users_profiles = list(raw_profiles)
        else:
            self._users_profiles = []

        # Audio Deterrence & Keypads
        self._keypad_enabled = bool(options.get(CONF_KEYPAD_ENABLED, data.get(CONF_KEYPAD_ENABLED, DEFAULT_KEYPAD_ENABLED)))
        self._keypad_beep_entry = bool(options.get(CONF_KEYPAD_BEEP_ENTRY, data.get(CONF_KEYPAD_BEEP_ENTRY, DEFAULT_KEYPAD_BEEP_ENTRY)))
        self._keypad_beep_exit = bool(options.get(CONF_KEYPAD_BEEP_EXIT, data.get(CONF_KEYPAD_BEEP_EXIT, DEFAULT_KEYPAD_BEEP_EXIT)))
        self._tts_pre_alert_msg = str(options.get(CONF_TTS_PRE_ALERT_MSG, data.get(CONF_TTS_PRE_ALERT_MSG, DEFAULT_TTS_PRE_ALERT_MSG)))
        self._tts_alarm_msg = str(options.get(CONF_TTS_ALARM_MSG, data.get(CONF_TTS_ALARM_MSG, DEFAULT_TTS_ALARM_MSG)))
        self._tts_volume_alert = float(options.get(CONF_TTS_VOLUME_ALERT, data.get(CONF_TTS_VOLUME_ALERT, DEFAULT_TTS_VOLUME_ALERT)))
        self._tts_volume_info = float(options.get(CONF_TTS_VOLUME_INFO, data.get(CONF_TTS_VOLUME_INFO, DEFAULT_TTS_VOLUME_INFO)))

        # Pre-compute entity zones map
        self._entity_zones_cache = self._get_entity_zones_map()

    @callback
    def async_update_options(self):
        """Reload config when options change (called from __init__.py listener)."""
        self._load_config()
        self.async_write_ha_state()

    @callback
    def async_write_ha_state(self):
        """Write state to HA and push to MQTT if enabled."""
        super().async_write_ha_state()
        if getattr(self, "_mqtt_enabled", False) and "mqtt" in self.hass.config.components:
            from homeassistant.components import mqtt

            state_str = self.state if hasattr(self, "state") and self.state else "unknown"
            self.hass.async_create_task(
                mqtt.async_publish(self.hass, f"{self._mqtt_topic_base}/state", state_str, retain=True)
            )
            if hasattr(self, "state_attributes") and self.state_attributes:
                self.hass.async_create_task(
                    mqtt.async_publish(
                        self.hass,
                        f"{self._mqtt_topic_base}/attributes",
                        json.dumps(self.state_attributes),
                        retain=True,
                    )
                )

    @property
    def unique_id(self):
        return self._unique_id

    @property
    def alarm_state(self):
        return self._state

    @property
    def code_arm_required(self):
        return False

    @property
    def extra_state_attributes(self):
        """Expose extra attributes for Lovelace and automations."""
        now_ts = self.hass.loop.time()
        media_files = self.media_manager.list_media_files()
        cur_nas = self._get_config_value(CONF_NAS_TYPE, DEFAULT_NAS_TYPE)

        return {
            "domolink_alarm": True,
            "ai_recent_events": [e["message"] for e in self._system_events[:5]],
            "faults": self._faults,
            "triggered_by": self._triggered_by,
            "last_triggered_by": self._last_triggered_by,
            "last_user": self._last_user,
            "failed_attempts": self._failed_attempts,
            "geofence_active": self.geofence_manager.auto_arm,
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
            "presence_simulation_entities": self.presence_simulator.entities,
            "presence_simulation_active": self.presence_simulator.is_running,
            "presence_simulation_history_days": self.presence_simulator.history_days,
            "presence_simulation_forced": self.presence_simulator.forced,
            "presence_simulation_events": self.presence_simulator.events,
            "cross_zoning_active": self._cross_zoning,
            "geofence_reminder_active": self.geofence_manager.reminder_enabled,
            "arm_history": self._arm_history,
            "system_events": list(self._system_events),
            "sensor_health": self._sensor_health,
            "telegram_status": self.cloud_uploader.telegram_status,
            "ftp_status": self.cloud_uploader.ftp_status,
            "cameras_armed": self.media_manager.cameras_armed,
            "cameras_arm_entities": self._cameras_arm_entities,
            "media_path": self.media_manager.media_path,
            "media_files": media_files,
            "zone_labels": self._zone_labels,
            "global_cameras": self._global_cameras,
            "entity_zones": self._entity_zones_cache,
            "disarm_cooldown": self._disarm_cooldown_task is not None,
            "camera_test_running": self.media_manager.is_testing_cameras,
            "camera_test_info": dict(self.media_manager.camera_test_info),
            "ftp_host": self._get_config_value(CONF_FTP_HOST, ""),
            "ftp_protocol": self._get_config_value(CONF_FTP_PROTOCOL, DEFAULT_FTP_PROTOCOL),
            "ftp_test_running": self.cloud_uploader.ftp_test_running,
            "ftp_test_logs": list(self.cloud_uploader.ftp_test_logs),
            "ftp_test_result": dict(self.cloud_uploader.ftp_test_result),
            "webdav_status": self.cloud_uploader.webdav_status,
            "webdav_url": self._get_config_value(CONF_WEBDAV_URL, ""),
            "webdav_path": self._get_config_value(CONF_WEBDAV_PATH, DEFAULT_WEBDAV_PATH),
            "webdav_test_running": self.cloud_uploader.webdav_test_running,
            "webdav_test_logs": list(self.cloud_uploader.webdav_test_logs),
            "webdav_test_result": dict(self.cloud_uploader.webdav_test_result),
            "nas_type": cur_nas,
            "nas_configs": self._get_safe_nas_configs(),
            "nas_test_results": dict(self.cloud_uploader.nas_test_results),
            "google_drive_status": self.cloud_uploader.google_drive_status,
            "google_drive_method": self._get_config_value(CONF_GOOGLE_DRIVE_METHOD, DEFAULT_GOOGLE_DRIVE_METHOD),
            "google_drive_test_running": self.cloud_uploader.google_drive_test_running,
            "google_drive_test_logs": list(self.cloud_uploader.google_drive_test_logs),
            "google_drive_test_result": dict(self.cloud_uploader.google_drive_test_result),
            "media_storage_bytes": self.media_manager.storage_stats.get("bytes", 0),
            "media_storage_mb": self.media_manager.storage_stats.get("mb", 0.0),
            "media_storage_max_mb": self.media_manager.max_size_mb,
            "media_storage_retention_days": self.media_manager.retention_days,
            "media_storage_count": self.media_manager.storage_stats.get("count", 0),
            "media_storage_percent": self.media_manager.storage_stats.get("percent", 0.0),
            # NF A2P Double Detection
            "nf_a2p_mode": self._nf_a2p_mode,
            "pre_alert": self._pre_alert_active,
            "pre_alert_sensor": self._pre_alert_sensor,
            "pre_alert_sensor_name": self._pre_alert_sensor_name,
            "pre_alert_remaining": max(0, int(self._pre_alert_expires_at - now_ts)) if self._pre_alert_active else 0,
            # Compact smartwatch state
            "compact_state": self._get_compact_state(),
            "compact_label": self._get_compact_label(),
            # Extended User Profiles
            "user_profiles": self._get_safe_user_profiles(),
            # Failover Alerting
            "network_failover_active": self.notification_manager.network_failover_active,
            # Certified Incident Data
            "last_incident_report": dict(self._last_incident_report),
            "installed_config": self._get_installed_config(),
            "system_version": self._system_version,
            "update_available": self._update_available,
            "latest_version": self._latest_version,
            "release_notes": self._release_notes,
            "release_url": self._release_url,
        }

    def _get_safe_user_profiles(self):
        """Return user profiles with PIN masked for frontend and WebSocket safety."""
        safe = []
        for p in getattr(self, "_users_profiles", []):
            cp = dict(p)
            cp["pin"] = "••••"
            if "id" not in cp:
                cp["id"] = cp.get("name", "profile")
            safe.append(cp)
        return safe

    def _get_masked_users_codes(self):
        """Return formatted users without exposed PIN hashes."""
        if not self._users:
            return ""
        return ", ".join(f"{name}:{SECRET_MASK}" for name in self._users.keys())

    def _get_safe_nas_configs(self):
        """Return NAS configs with all passwords masked."""
        safe_cfgs = {}
        raw_nas = self._get_config_value(CONF_NAS_CONFIGS, DEFAULT_NAS_CONFIGS) or {}
        for brand, cfg in raw_nas.items():
            if isinstance(cfg, dict):
                cp = dict(cfg)
                cp["ftp_pass"] = mask_secret(cp.get("ftp_pass"))
                cp["webdav_pass"] = mask_secret(cp.get("webdav_pass"))
                safe_cfgs[brand] = cp
            else:
                safe_cfgs[brand] = cfg
        return safe_cfgs

    def _async_persist_users_and_duress(self):
        """Save updated (hashed) users and duress code into config entry options."""
        if not self._entry:
            return
        new_options = dict(self._entry.options if self._entry.options else self._entry.data)
        users_str = ", ".join(f"{name}:{h}" for name, h in self._users.items())
        new_options[CONF_USERS_CODES] = users_str
        new_options[CONF_DURESS_CODE] = self._duress_code
        self.hass.config_entries.async_update_entry(self._entry, options=new_options)

    def _get_compact_state(self):
        """Return a compact emoji status for smartwatch complications and tiles."""
        if self._state == AlarmControlPanelState.DISARMED:
            return "🟢 Désarmée"
        elif self._state == AlarmControlPanelState.ARMED_AWAY:
            return "🔴 Armée (Absent)"
        elif self._state == AlarmControlPanelState.ARMED_NIGHT:
            return "🌙 Armée (Nuit)"
        elif self._state == AlarmControlPanelState.ARMED_HOME:
            return "🟠 Armée (Maison)"
        elif self._state == AlarmControlPanelState.ARMING:
            return "⏳ Armement en cours"
        elif self._state == AlarmControlPanelState.PENDING:
            return "⚠️ Délai d'entrée"
        elif self._state == AlarmControlPanelState.TRIGGERED:
            return "🚨 ALARME DÉCLENCHÉE"
        return str(self._state)

    def _get_compact_label(self):
        """Return short label for watch complications."""
        if self._state == AlarmControlPanelState.TRIGGERED:
            trig = self._triggered_by or "Intrusion"
            return f"🚨 {trig}"
        if self._pre_alert_active:
            return "⚠️ Pré-alerte NF A2P"
        return self._get_compact_state()

    def _get_installed_config(self):
        """Return the complete dictionary of current configuration settings with secrets masked."""
        data = self._entry.data or {}
        options = self._entry.options or {}

        def _val(key, default=None):
            return options.get(key, data.get(key, default))

        return {
            CONF_NAME: _val(CONF_NAME, DEFAULT_NAME),
            CONF_OPENING_SENSORS: list(_val(CONF_OPENING_SENSORS, []) or []),
            CONF_OPENING_SENSORS_LABELS: list(_val(CONF_OPENING_SENSORS_LABELS, []) or []),
            CONF_NIGHT_SENSORS: list(_val(CONF_NIGHT_SENSORS, []) or []),
            CONF_NIGHT_SENSORS_LABELS: list(_val(CONF_NIGHT_SENSORS_LABELS, []) or []),
            CONF_MOTION_SENSORS: list(_val(CONF_MOTION_SENSORS, []) or []),
            CONF_MOTION_SENSORS_LABELS: list(_val(CONF_MOTION_SENSORS_LABELS, []) or []),
            CONF_CAMERAS: list(_val(CONF_CAMERAS, []) or []),
            CONF_CAMERAS_LABELS: list(_val(CONF_CAMERAS_LABELS, []) or []),
            CONF_CAMERAS_ARM_ENTITIES: list(_val(CONF_CAMERAS_ARM_ENTITIES, []) or []),
            CONF_CAMERAS_ARM_ENTITIES_LABELS: list(_val(CONF_CAMERAS_ARM_ENTITIES_LABELS, []) or []),
            CONF_TAMPER_SENSORS: list(_val(CONF_TAMPER_SENSORS, []) or []),
            CONF_TAMPER_SENSORS_LABELS: list(_val(CONF_TAMPER_SENSORS_LABELS, []) or []),
            CONF_KEYPADS: list(_val(CONF_KEYPADS, []) or []),
            CONF_KEYPADS_LABELS: list(_val(CONF_KEYPADS_LABELS, []) or []),
            CONF_SAFETY_SENSORS: list(_val(CONF_SAFETY_SENSORS, []) or []),
            CONF_SAFETY_SENSORS_LABELS: list(_val(CONF_SAFETY_SENSORS_LABELS, []) or []),
            CONF_SIRENS: list(_val(CONF_SIRENS, []) or []),
            CONF_SIRENS_LABELS: list(_val(CONF_SIRENS_LABELS, []) or []),
            CONF_LIGHTS: list(_val(CONF_LIGHTS, []) or []),
            CONF_LIGHTS_LABELS: list(_val(CONF_LIGHTS_LABELS, []) or []),
            CONF_MEDIA_PLAYERS: list(_val(CONF_MEDIA_PLAYERS, []) or []),
            CONF_MEDIA_PLAYERS_LABELS: list(_val(CONF_MEDIA_PLAYERS_LABELS, []) or []),
            CONF_NOTIFY_SERVICES: list(_val(CONF_NOTIFY_SERVICES, []) or []),
            CONF_NOTIFY_SERVICES_LABELS: list(_val(CONF_NOTIFY_SERVICES_LABELS, []) or []),
            CONF_FREE_MOBILE_USER: str(_val(CONF_FREE_MOBILE_USER, "") or ""),
            CONF_FREE_MOBILE_PASS: mask_secret(str(_val(CONF_FREE_MOBILE_PASS, "") or "")),
            CONF_ICLOUD_ACCOUNT: str(_val(CONF_ICLOUD_ACCOUNT, "") or ""),
            CONF_ICLOUD_DEVICES: list(_val(CONF_ICLOUD_DEVICES, []) or []),
            CONF_EMERGENCY_CONTACT: list(_val(CONF_EMERGENCY_CONTACT, []) or []),
            CONF_EMERGENCY_CONTACT_LABELS: list(_val(CONF_EMERGENCY_CONTACT_LABELS, []) or []),
            CONF_PRESENCE_SIMULATION_ENTITIES: list(_val(CONF_PRESENCE_SIMULATION_ENTITIES, []) or []),
            CONF_PRESENCE_SIMULATION_LABELS: list(_val(CONF_PRESENCE_SIMULATION_LABELS, []) or []),
            CONF_ZONE_LABELS: list(_val(CONF_ZONE_LABELS, []) or []),
            CONF_GLOBAL_CAMERAS: list(_val(CONF_GLOBAL_CAMERAS, []) or []),
            CONF_GLOBAL_CAMERAS_LABELS: list(_val(CONF_GLOBAL_CAMERAS_LABELS, []) or []),
            CONF_PERSONS: list(_val(CONF_PERSONS, []) or []),
            CONF_PERSONS_LABELS: list(_val(CONF_PERSONS_LABELS, []) or []),
            CONF_USERS_CODES: self._get_masked_users_codes(),
            CONF_DURESS_CODE: mask_secret(str(_val(CONF_DURESS_CODE, "") or "")),
            CONF_RFID_TAGS: str(_val(CONF_RFID_TAGS, "") or ""),
            CONF_EXIT_DELAY: int(_val(CONF_EXIT_DELAY, DEFAULT_EXIT_DELAY) or DEFAULT_EXIT_DELAY),
            CONF_ENTRY_DELAY: int(_val(CONF_ENTRY_DELAY, DEFAULT_ENTRY_DELAY) or DEFAULT_ENTRY_DELAY),
            CONF_SIREN_DURATION: int(_val(CONF_SIREN_DURATION, DEFAULT_SIREN_DURATION) or DEFAULT_SIREN_DURATION),
            CONF_BYPASS_ALLOWED: bool(_val(CONF_BYPASS_ALLOWED, DEFAULT_BYPASS_ALLOWED)),
            CONF_HEALTH_CHECK: bool(_val(CONF_HEALTH_CHECK, DEFAULT_HEALTH_CHECK)),
            CONF_GEOFENCE_AUTO_ARM: bool(_val(CONF_GEOFENCE_AUTO_ARM, DEFAULT_GEOFENCE_AUTO_ARM)),
            CONF_GEOFENCE_REMINDER: bool(_val(CONF_GEOFENCE_REMINDER, DEFAULT_GEOFENCE_REMINDER)),
            CONF_GEOFENCE_REMINDER_DELAY: int(_val(CONF_GEOFENCE_REMINDER_DELAY, DEFAULT_GEOFENCE_REMINDER_DELAY) or DEFAULT_GEOFENCE_REMINDER_DELAY),
            CONF_CHIME_MODE: bool(_val(CONF_CHIME_MODE, DEFAULT_CHIME_MODE)),
            CONF_CROSS_ZONING: bool(_val(CONF_CROSS_ZONING, DEFAULT_CROSS_ZONING)),
            CONF_CROSS_ZONING_WINDOW: int(_val(CONF_CROSS_ZONING_WINDOW, DEFAULT_CROSS_ZONING_WINDOW) or DEFAULT_CROSS_ZONING_WINDOW),
            CONF_PRESENCE_SIMULATION_HISTORY_DAYS: int(_val(CONF_PRESENCE_SIMULATION_HISTORY_DAYS, DEFAULT_PRESENCE_SIMULATION_HISTORY_DAYS) or DEFAULT_PRESENCE_SIMULATION_HISTORY_DAYS),
            CONF_SIREN_TEST: bool(_val(CONF_SIREN_TEST, DEFAULT_SIREN_TEST)),
            CONF_SIREN_TEST_DAY: int(_val(CONF_SIREN_TEST_DAY, DEFAULT_SIREN_TEST_DAY) or DEFAULT_SIREN_TEST_DAY),
            CONF_SIREN_TEST_HOUR: int(_val(CONF_SIREN_TEST_HOUR, DEFAULT_SIREN_TEST_HOUR) or DEFAULT_SIREN_TEST_HOUR),
            CONF_SCHEDULE_ENABLED: bool(_val(CONF_SCHEDULE_ENABLED, DEFAULT_SCHEDULE_ENABLED)),
            CONF_SCHEDULE_ARM_TIME: str(_val(CONF_SCHEDULE_ARM_TIME, DEFAULT_SCHEDULE_ARM_TIME) or DEFAULT_SCHEDULE_ARM_TIME),
            CONF_SCHEDULE_DISARM_TIME: str(_val(CONF_SCHEDULE_DISARM_TIME, DEFAULT_SCHEDULE_DISARM_TIME) or DEFAULT_SCHEDULE_DISARM_TIME),
            CONF_SCHEDULE_MODE: str(_val(CONF_SCHEDULE_MODE, DEFAULT_SCHEDULE_MODE) or DEFAULT_SCHEDULE_MODE),
            CONF_MQTT_ENABLED: bool(_val(CONF_MQTT_ENABLED, DEFAULT_MQTT_ENABLED)),
            CONF_MQTT_TOPIC_BASE: str(_val(CONF_MQTT_TOPIC_BASE, DEFAULT_MQTT_TOPIC_BASE) or DEFAULT_MQTT_TOPIC_BASE),
            CONF_MQTT_REQUIRE_CODE: bool(_val(CONF_MQTT_REQUIRE_CODE, DEFAULT_MQTT_REQUIRE_CODE)),
            CONF_TELEGRAM_ENABLED: bool(_val(CONF_TELEGRAM_ENABLED, DEFAULT_TELEGRAM_ENABLED)),
            CONF_TELEGRAM_TOKEN: mask_secret(str(_val(CONF_TELEGRAM_TOKEN, "") or "")),
            CONF_TELEGRAM_CHAT_ID: str(_val(CONF_TELEGRAM_CHAT_ID, "") or ""),
            CONF_FTP_ENABLED: bool(_val(CONF_FTP_ENABLED, DEFAULT_FTP_ENABLED)),
            CONF_FTP_PROTOCOL: str(_val(CONF_FTP_PROTOCOL, DEFAULT_FTP_PROTOCOL) or DEFAULT_FTP_PROTOCOL),
            CONF_FTP_HOST: str(_val(CONF_FTP_HOST, "") or ""),
            CONF_FTP_PORT: int(_val(CONF_FTP_PORT, DEFAULT_FTP_PORT) or DEFAULT_FTP_PORT),
            CONF_FTP_USER: str(_val(CONF_FTP_USER, "") or ""),
            CONF_FTP_PASS: mask_secret(str(_val(CONF_FTP_PASS, "") or "")),
            CONF_FTP_PATH: str(_val(CONF_FTP_PATH, DEFAULT_FTP_PATH) or DEFAULT_FTP_PATH),
            CONF_FTP_ALLOW_INSECURE_TLS: bool(_val(CONF_FTP_ALLOW_INSECURE_TLS, DEFAULT_FTP_ALLOW_INSECURE_TLS)),
            CONF_WEBDAV_ENABLED: bool(_val(CONF_WEBDAV_ENABLED, DEFAULT_WEBDAV_ENABLED)),
            CONF_WEBDAV_URL: str(_val(CONF_WEBDAV_URL, "") or ""),
            CONF_WEBDAV_USER: str(_val(CONF_WEBDAV_USER, "") or ""),
            CONF_WEBDAV_PASS: mask_secret(str(_val(CONF_WEBDAV_PASS, "") or "")),
            CONF_WEBDAV_PATH: str(_val(CONF_WEBDAV_PATH, DEFAULT_WEBDAV_PATH) or DEFAULT_WEBDAV_PATH),
            CONF_NAS_TYPE: str(_val(CONF_NAS_TYPE, DEFAULT_NAS_TYPE) or DEFAULT_NAS_TYPE),
            CONF_NAS_CONFIGS: self._get_safe_nas_configs(),
            CONF_GOOGLE_DRIVE_ENABLED: bool(_val(CONF_GOOGLE_DRIVE_ENABLED, DEFAULT_GOOGLE_DRIVE_ENABLED)),
            CONF_GOOGLE_DRIVE_METHOD: str(_val(CONF_GOOGLE_DRIVE_METHOD, DEFAULT_GOOGLE_DRIVE_METHOD) or DEFAULT_GOOGLE_DRIVE_METHOD),
            CONF_GOOGLE_DRIVE_WEBHOOK_URL: str(_val(CONF_GOOGLE_DRIVE_WEBHOOK_URL, "") or ""),
            CONF_GOOGLE_DRIVE_CLIENT_ID: str(_val(CONF_GOOGLE_DRIVE_CLIENT_ID, "") or ""),
            CONF_GOOGLE_DRIVE_CLIENT_SECRET: mask_secret(str(_val(CONF_GOOGLE_DRIVE_CLIENT_SECRET, "") or "")),
            CONF_GOOGLE_DRIVE_REFRESH_TOKEN: mask_secret(str(_val(CONF_GOOGLE_DRIVE_REFRESH_TOKEN, "") or "")),
            CONF_GOOGLE_DRIVE_FOLDER_ID: str(_val(CONF_GOOGLE_DRIVE_FOLDER_ID, "") or ""),
            CONF_MEDIA_PATH: str(_val(CONF_MEDIA_PATH, DEFAULT_MEDIA_PATH) or DEFAULT_MEDIA_PATH),
            CONF_MEDIA_RETENTION_DAYS: int(_val(CONF_MEDIA_RETENTION_DAYS, DEFAULT_MEDIA_RETENTION_DAYS) or DEFAULT_MEDIA_RETENTION_DAYS),
            CONF_MEDIA_MAX_SIZE_MB: int(_val(CONF_MEDIA_MAX_SIZE_MB, DEFAULT_MEDIA_MAX_SIZE_MB) or DEFAULT_MEDIA_MAX_SIZE_MB),
            # NF A2P
            CONF_NF_A2P_MODE: bool(_val(CONF_NF_A2P_MODE, DEFAULT_NF_A2P_MODE)),
            CONF_NF_A2P_WINDOW: int(_val(CONF_NF_A2P_WINDOW, DEFAULT_NF_A2P_WINDOW) or DEFAULT_NF_A2P_WINDOW),
            CONF_NF_A2P_STRICT_DISTINCT: bool(_val(CONF_NF_A2P_STRICT_DISTINCT, DEFAULT_NF_A2P_STRICT_DISTINCT)),
            CONF_NF_A2P_PRE_ALERT_CHIME: bool(_val(CONF_NF_A2P_PRE_ALERT_CHIME, DEFAULT_NF_A2P_PRE_ALERT_CHIME)),
            # User Profiles
            CONF_USERS_PROFILES: _val(CONF_USERS_PROFILES, getattr(self, "_users_profiles", [])),
            # Predictive Geofencing
            CONF_PROXIMITY_SENSOR: str(_val(CONF_PROXIMITY_SENSOR, "") or ""),
            CONF_GEOFENCE_APPROACH_REMINDER: bool(_val(CONF_GEOFENCE_APPROACH_REMINDER, DEFAULT_GEOFENCE_APPROACH_REMINDER)),
            CONF_GEOFENCE_APPROACH_DISTANCE: int(_val(CONF_GEOFENCE_APPROACH_DISTANCE, DEFAULT_GEOFENCE_APPROACH_DISTANCE) or DEFAULT_GEOFENCE_APPROACH_DISTANCE),
            # Physical Keypads
            CONF_KEYPAD_ENABLED: bool(_val(CONF_KEYPAD_ENABLED, DEFAULT_KEYPAD_ENABLED)),
            CONF_KEYPAD_BEEP_ENTRY: bool(_val(CONF_KEYPAD_BEEP_ENTRY, DEFAULT_KEYPAD_BEEP_ENTRY)),
            CONF_KEYPAD_BEEP_EXIT: bool(_val(CONF_KEYPAD_BEEP_EXIT, DEFAULT_KEYPAD_BEEP_EXIT)),
            # Audio Deterrence
            CONF_DETERRENCE_ENABLED: bool(_val(CONF_DETERRENCE_ENABLED, DEFAULT_DETERRENCE_ENABLED)),
            CONF_DETERRENCE_LEVEL: str(_val(CONF_DETERRENCE_LEVEL, DEFAULT_DETERRENCE_LEVEL) or DEFAULT_DETERRENCE_LEVEL),
            CONF_TTS_PRE_ALERT_MSG: str(_val(CONF_TTS_PRE_ALERT_MSG, DEFAULT_TTS_PRE_ALERT_MSG) or DEFAULT_TTS_PRE_ALERT_MSG),
            CONF_TTS_ALARM_MSG: str(_val(CONF_TTS_ALARM_MSG, DEFAULT_TTS_ALARM_MSG) or DEFAULT_TTS_ALARM_MSG),
            CONF_TTS_VOLUME_ALERT: float(_val(CONF_TTS_VOLUME_ALERT, DEFAULT_TTS_VOLUME_ALERT) or DEFAULT_TTS_VOLUME_ALERT),
            CONF_TTS_VOLUME_INFO: float(_val(CONF_TTS_VOLUME_INFO, DEFAULT_TTS_VOLUME_INFO) or DEFAULT_TTS_VOLUME_INFO),
            # Network Failover
            CONF_FAILOVER_GSM_ENABLED: bool(_val(CONF_FAILOVER_GSM_ENABLED, DEFAULT_FAILOVER_GSM_ENABLED)),
            CONF_FAILOVER_GSM_SERVICE: str(_val(CONF_FAILOVER_GSM_SERVICE, "") or ""),
            CONF_FAILOVER_LOCAL_ALARM: bool(_val(CONF_FAILOVER_LOCAL_ALARM, DEFAULT_FAILOVER_LOCAL_ALARM)),
        }

    async def async_bypass_sensor(self, entity_id: str):
        """Bypass / ignore a sensor temporarily."""
        self._bypassed_sensors.add(entity_id)
        friendly_name = entity_id
        state = self.hass.states.get(entity_id)
        if state and state.name:
            friendly_name = state.name
        self._log_event(f"Capteur ignoré (Bypass): {friendly_name}")
        self.async_write_ha_state()

    async def async_unbypass_sensor(self, entity_id: str):
        """Restore a bypassed sensor."""
        self._bypassed_sensors.discard(entity_id)
        friendly_name = entity_id
        state = self.hass.states.get(entity_id)
        if state and state.name:
            friendly_name = state.name
        self._log_event(f"Capteur réintégré: {friendly_name}")
        self.async_write_ha_state()

    def set_log_sensor(self, sensor):
        """Register the log sensor entity."""
        self._event_sensor = sensor

    def set_watch_sensor(self, sensor):
        """Register the smartwatch status sensor."""
        self._watch_sensor = sensor
        self._sync_watch_sensor()

    def _sync_watch_sensor(self):
        """Sync smartwatch sensor values."""
        if not self._watch_sensor:
            return
        label = self._get_compact_state()
        c_state = str(self._state).upper()
        icon = "mdi:shield-lock" if self._state != AlarmControlPanelState.DISARMED else "mdi:shield-check"
        if self._state == AlarmControlPanelState.TRIGGERED:
            icon = "mdi:shield-alert"
        elif self._state == AlarmControlPanelState.PENDING:
            icon = "mdi:shield-alert-outline"
        self._watch_sensor.async_update_status(label, c_state, icon)

    def _get_french_time(self):
        """Return formatted date and time in French locale."""
        now = dt_now()
        months = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
        return f"{now.day} {months[now.month - 1]} {now.year} à {now.strftime('%Hh%M et %S secondes')}"

    def _log_event(self, message):
        """Log event locally and push to event log sensor."""
        _LOGGER.info("Domolink Event: %s", message)
        time_str = dt_now().strftime("%H:%M:%S")
        if self._event_sensor:
            self._event_sensor.async_add_event(time_str, message)
        self._sync_watch_sensor()

        self._system_events.insert(0, {"time": time_str, "message": message})
        if len(self._system_events) > 50:
            self._system_events = self._system_events[:50]

        if getattr(self, "_mqtt_enabled", False) and "mqtt" in self.hass.config.components:
            from homeassistant.components import mqtt

            self.hass.async_create_task(
                mqtt.async_publish(
                    self.hass,
                    f"{self._mqtt_topic_base}/event",
                    json.dumps({"time": utcnow().isoformat(), "message": message}),
                    retain=False,
                )
            )

    # ─── Lifecycle ────────────────────────────────────────────────

    async def async_added_to_hass(self):
        """Run when entity about to be added."""
        await super().async_added_to_hass()

        last_state = await self.async_get_last_state()
        if last_state and last_state.state in _STATE_MAP:
            self._state = _STATE_MAP[last_state.state]
            if last_state.attributes:
                self._last_triggered_by = last_state.attributes.get("last_triggered_by")
                self._last_user = last_state.attributes.get("last_user")
                self._arm_history = last_state.attributes.get("arm_history", [])
                self._system_events = last_state.attributes.get("system_events", [])

        # Create media directory and purge expired files
        try:
            os.makedirs(self.media_manager.media_dir, exist_ok=True)
            await self.hass.async_add_executor_job(self.media_manager.purge_old_files)
        except Exception as e:
            _LOGGER.error("Domolink: Impossible d'initialiser le stockage médias: %s", e)

        # Track sensor changes
        all_sensors = list(
            set(
                self._opening_sensors
                + self._motion_sensors
                + self._tamper_sensors
                + self._night_sensors
                + self._safety_sensors
                + self._persons
            )
        )
        if all_sensors:
            self.async_on_remove(
                async_track_state_change_event(self.hass, all_sensors, self._async_sensor_changed)
            )

        # MQTT Command Subscription
        if getattr(self, "_mqtt_enabled", False) and "mqtt" in self.hass.config.components:
            from homeassistant.components import mqtt

            async def _mqtt_message_received(msg):
                payload = str(msg.payload).strip()
                _LOGGER.info(
                    "Domolink: Commande MQTT reçue sur %s : %s",
                    msg.topic,
                    sanitize_log_payload(payload),
                )
                action = payload
                code = None
                if payload.startswith("{") and payload.endswith("}"):
                    try:
                        m_data = json.loads(payload)
                        action = m_data.get("action", "")
                        code = m_data.get("code")
                    except Exception:
                        pass

                action_upper = action.upper()
                if action_upper in ("ARM_AWAY", "ARM"):
                    await self.async_alarm_arm_away(code)
                elif action_upper in ("ARM_HOME", "HOME"):
                    await self.async_alarm_arm_home(code)
                elif action_upper in ("ARM_NIGHT", "NIGHT"):
                    await self.async_alarm_arm_night(code)
                elif action_upper in ("DISARM", "OFF"):
                    await self.async_alarm_disarm(code or "MQTT")
                elif action_upper in ("PANIC", "SOS"):
                    await self.async_panic(activate_sirens=True)

            self.async_on_remove(
                await mqtt.async_subscribe(self.hass, f"{self._mqtt_topic_base}/set", _mqtt_message_received)
            )

        # Health check
        if self._health_check:
            self.async_on_remove(
                async_track_time_interval(self.hass, self._async_perform_health_check, timedelta(hours=4))
            )
            self.async_on_remove(async_call_later(self.hass, 15, self._async_perform_health_check))

        # Geofencing
        if self.geofence_manager.auto_arm or self.geofence_manager.reminder_enabled:
            self.async_on_remove(
                async_track_state_change_event(self.hass, ["zone.home"], self.geofence_manager.async_zone_changed)
            )

        # Actionable notifications listener
        self.async_on_remove(
            self.hass.bus.async_listen("mobile_app_notification_action", self.geofence_manager.async_handle_mobile_action)
        )

        # Proximity sensor listener
        proximity_sensor = self._get_config_value(CONF_PROXIMITY_SENSOR)
        if proximity_sensor:
            @callback
            def _proximity_changed(event):
                new_st = event.data.get("new_state")
                if new_st:
                    self.geofence_manager.handle_proximity_update(new_st)

            self.async_on_remove(
                async_track_state_change_event(self.hass, [proximity_sensor], _proximity_changed)
            )

        # Physical Keypads
        if self._keypad_enabled:
            async def _handle_keypad_event(event):
                await self._async_handle_keypad_event(event)

            self.async_on_remove(self.hass.bus.async_listen("zha_event", _handle_keypad_event))
            self.async_on_remove(self.hass.bus.async_listen("deconz_event", _handle_keypad_event))

        # RFID Tags
        if self._rfid_tags:
            self.async_on_remove(self.hass.bus.async_listen("tag_scanned", self._async_handle_tag_scanned))

        # Siren Test Schedule
        if self._siren_test:
            from homeassistant.helpers.event import async_track_time_change

            self.async_on_remove(
                async_track_time_change(
                    self.hass,
                    self._cb_siren_test,
                    hour=self._siren_test_hour,
                    minute=0,
                    second=0,
                )
            )

        # Time-based Auto-Arming
        if self._schedule_enabled:
            from homeassistant.helpers.event import async_track_time_change

            try:
                arm_parts = [int(p) for p in str(self._schedule_arm_time).replace("h", ":").replace("H", ":").split(":") if p.strip().isdigit()]
                disarm_parts = [int(p) for p in str(self._schedule_disarm_time).replace("h", ":").replace("H", ":").split(":") if p.strip().isdigit()]
                if len(arm_parts) >= 2:
                    self.async_on_remove(
                        async_track_time_change(self.hass, self._cb_schedule_arm, hour=arm_parts[0], minute=arm_parts[1], second=0)
                    )
                if len(disarm_parts) >= 2:
                    self.async_on_remove(
                        async_track_time_change(self.hass, self._cb_schedule_disarm, hour=disarm_parts[0], minute=disarm_parts[1], second=0)
                    )
            except Exception as e:
                _LOGGER.error("Domolink: Erreur configuration planification horaire: %s", e)

    # ─── Physical Keypads & RFID ──────────────────────────────────

    async def _async_handle_keypad_event(self, event):
        """Handle physical keypad events (ZHA / Deconz / Ring Keypad)."""
        data = event.data or {}
        command = data.get("command") or data.get("event") or ""
        args = data.get("args") or {}

        code = None
        arm_mode = None
        if isinstance(args, dict):
            arm_mode = args.get("arm_mode")
            code = args.get("code")
        elif isinstance(args, (list, tuple)) and len(args) >= 1:
            arm_mode = args[0]
            if len(args) >= 2:
                code = args[1]

        if command in ("arm", "disarm", "emergency", "panic"):
            _LOGGER.info("Domolink: Événement clavier physique reçu : command=%s, arm_mode=%s", command, arm_mode)
            if command == "disarm" or arm_mode == 0:
                user = self._validate_code(code) if code else None
                if user or not self._users:
                    self._last_user = f"{user or 'Clavier'} (Mur)"
                    await self.async_alarm_disarm(code)
                else:
                    _LOGGER.warning("Domolink: Code clavier physique erroné")
                    self._log_event("Code erroné sur clavier physique")
                    await self._async_sync_keypads("error")
            elif arm_mode in (1, "arm_day_zones"):
                await self.async_alarm_arm_home(code)
            elif arm_mode in (2, "arm_night_zones"):
                await self.async_alarm_arm_night(code)
            elif arm_mode in (3, "arm_all_zones") or command == "arm":
                await self.async_alarm_arm_away(code)
            elif command in ("panic", "emergency") or arm_mode in (4, "emergency"):
                await self.async_panic(activate_sirens=True)

    async def _async_sync_keypads(self, feedback=None):
        """Send state synchronization and audible beeps to physical keypads."""
        if not self._keypad_enabled:
            return

        if getattr(self, "_mqtt_enabled", False) and "mqtt" in self.hass.config.components:
            from homeassistant.components import mqtt

            topic = f"{self._mqtt_topic_base}/keypad/status"
            payload = {
                "state": self._state,
                "feedback": feedback,
                "entry_delay": self._entry_delay,
                "exit_delay": self._exit_delay,
            }
            try:
                await mqtt.async_publish(self.hass, topic, json.dumps(payload))
            except Exception as e:
                _LOGGER.debug("Domolink: Erreur MQTT sync clavier: %s", e)

        if hasattr(self, "_keypads") and self._keypads:
            for kp in self._keypads:
                try:
                    domain = kp.split(".")[0]
                    if self._state == AlarmControlPanelState.ARMING and self._keypad_beep_exit:
                        await self.hass.services.async_call(domain, "turn_on", {"entity_id": kp})
                    elif self._state == AlarmControlPanelState.PENDING and self._keypad_beep_entry:
                        await self.hass.services.async_call(domain, "turn_on", {"entity_id": kp})
                except Exception:
                    pass

    async def _async_handle_tag_scanned(self, event):
        """Handle RFID/NFC tag scans to toggle alarm state."""
        tag_id = event.data.get("tag_id")
        if not tag_id or tag_id not in self._rfid_tags:
            return

        user_name = self._rfid_tags[tag_id]
        _LOGGER.info("RFID Tag scanned by %s", user_name)

        if self._state == AlarmControlPanelState.DISARMED:
            _LOGGER.info("Arming via RFID (User: %s)", user_name)
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

            await self.notification_manager.async_send_notification(
                f"🔒 Alarme activée par {user_name} (Badge)."
            )
        else:
            _LOGGER.info("Disarming via RFID (User: %s)", user_name)
            self._cancel_all_tasks()
            self._state = AlarmControlPanelState.DISARMED
            self._last_user = f"{user_name} (RFID)"
            self._faults.clear()
            self._triggered_by = None
            self.async_write_ha_state()
            await self._async_turn_off_siren()
            self._record_arm_event("disarm", self._last_user)
            self._log_event(f"Alarme Désarmée ({user_name} - Badge)")
            await self.notification_manager.async_send_notification(
                f"✅ Alarme désarmée par {user_name} (Badge)."
            )
            self.hass.async_create_task(
                self.notification_manager.async_play_tts(f"Alarme désarmée. Bienvenue {user_name}.")
            )

    # ─── Health Checks ────────────────────────────────────────────

    def _get_device_battery_level(self, entity_id: str) -> float | None:
        """Find battery level from entity attributes or associated device entities."""
        state = self.hass.states.get(entity_id)
        if not state:
            return None

        battery = state.attributes.get("battery_level") or state.attributes.get("battery")
        if battery is not None:
            try:
                return float(battery)
            except (ValueError, TypeError):
                pass

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
            _LOGGER.debug("Domolink: Erreur lecture batterie pour %s: %s", entity_id, e)

        return None

    async def _async_perform_health_check(self, now=None):
        """Check battery and availability of all linked devices."""
        all_devices = list(
            set(
                self._opening_sensors
                + self._motion_sensors
                + self._tamper_sensors
                + self._night_sensors
                + self._sirens
                + self._cameras
                + self._lights
            )
        )
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
                "last_changed": last_changed,
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
            await self.notification_manager.async_send_notification(notify_msg)

    # ─── Sensor State Monitoring ──────────────────────────────────

    async def _async_handle_person_changed(self):
        """Handle geofencing auto-arm logic."""
        if not self.geofence_manager.auto_arm or not self._persons:
            return

        states = [self.hass.states.get(p) for p in self._persons]
        states = [s.state for s in states if s is not None]

        if all(s != "home" for s in states) and self._state == AlarmControlPanelState.DISARMED:
            self._log_event("Auto-armement (Toutes les personnes sont absentes)")
            await self.async_alarm_arm_away()
        elif any(s == "home" for s in states) and self._state in (AlarmControlPanelState.ARMED_AWAY, AlarmControlPanelState.ARMING):
            self._log_event("Auto-désarmement (Une personne est arrivée)")
            await self.async_alarm_disarm(code=None)

    async def _async_sensor_changed(self, event):
        """Handle sensor state changes."""
        entity_id = event.data.get("entity_id")
        new_state = event.data.get("new_state")
        old_state = event.data.get("old_state")

        if not new_state:
            return
        if old_state and old_state.state == new_state.state:
            return

        if entity_id in self._persons:
            await self._async_handle_person_changed()
            return

        state_val = str(new_state.state).lower()
        if state_val not in ("on", "open", "true", "detected", "unlocked", "1"):
            return

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
            await self.notification_manager.async_send_notification(
                f"🚨 ALERTE D'URGENCE 24/7 🚨\nType : {type_label}\nCapteur : {friendly}",
                is_alert=True,
            )
            self.hass.async_create_task(self.notification_manager.async_play_tts(tts_msg))
            return

        # Tamper triggers immediately (24/7)
        if entity_id in self._tamper_sensors:
            _LOGGER.warning("Tamper / Sabotage détecté sur %s !", entity_id)
            await self._async_trigger_alarm(entity_id)
            return

        # Chime Mode when disarmed
        if self._state == AlarmControlPanelState.DISARMED:
            if self._chime_mode and entity_id in self._opening_sensors:
                friendly = new_state.name or entity_id
                self._log_event(f"Carillon : {friendly} ouverte")
                self.hass.async_create_task(
                    self.notification_manager.async_play_tts(f"{friendly} ouverte.")
                )
            return

        # Ignore sensors during exit delay
        if self._state == AlarmControlPanelState.ARMING:
            return

        # Track sensors during entry delay (PENDING)
        if self._state == AlarmControlPanelState.PENDING:
            if entity_id not in self._faults:
                self._faults.append(entity_id)
                self.async_write_ha_state()
                self._log_event(f"Capteur {new_state.name} ouvert pendant le délai d'entrée")
                self.hass.async_create_task(
                    self.notification_manager.async_send_notification(
                        f"⚠️ Détection pendant délai d'entrée : {new_state.name}\n({dt_now().strftime('%H:%M:%S')})",
                        is_alert=True,
                    )
                )
            return

        # NF A2P Double Detection
        if self._nf_a2p_mode and self._state in (
            AlarmControlPanelState.ARMED_AWAY,
            AlarmControlPanelState.ARMED_NIGHT,
            AlarmControlPanelState.ARMED_HOME,
        ):
            if (entity_id in self._opening_sensors) or (entity_id in self._motion_sensors):
                now_loop = self.hass.loop.time()
                if not self._pre_alert_active:
                    self._pre_alert_active = True
                    self._pre_alert_sensor = entity_id
                    self._pre_alert_sensor_name = new_state.name or entity_id
                    self._pre_alert_expires_at = now_loop + self._nf_a2p_window

                    if self._pre_alert_task:
                        self._pre_alert_task()
                    self._pre_alert_task = async_call_later(
                        self.hass,
                        self._nf_a2p_window,
                        self._cb_nf_a2p_timeout,
                    )

                    self._log_event(f"⚠️ Pré-alerte intrusion (NF A2P) : {self._pre_alert_sensor_name}")
                    self.async_write_ha_state()

                    if self._nf_a2p_pre_alert_chime:
                        self.hass.async_create_task(
                            self.notification_manager.async_play_tts(
                                self._tts_pre_alert_msg, volume=self._tts_volume_info
                            )
                        )

                    action_data = {"actions": [{"action": "DOMOLINK_DISARM", "title": "🔓 Désarmer"}]}
                    self.hass.async_create_task(
                        self.notification_manager.async_send_notification(
                            f"⚠️ Pré-alerte intrusion : {self._pre_alert_sensor_name}.\nEn attente de confirmation (NF A2P - {self._nf_a2p_window}s)...",
                            custom_data=action_data,
                            is_alert=False,
                        )
                    )
                    return
                else:
                    is_distinct = entity_id != self._pre_alert_sensor
                    diff = now_loop - (self._pre_alert_expires_at - self._nf_a2p_window)

                    if not self._nf_a2p_strict_distinct or is_distinct or diff >= 3.0:
                        if self._pre_alert_task:
                            self._pre_alert_task()
                            self._pre_alert_task = None
                        self._pre_alert_active = False

                        self._log_event(
                            f"🚨 Double détection confirmée (NF A2P) : {self._pre_alert_sensor_name} + {new_state.name}"
                        )
                        self._record_incident(
                            "intrusion_double_nf_a2p",
                            {"sensor1": self._pre_alert_sensor, "sensor2": entity_id},
                        )
                        await self._async_trigger_alarm(entity_id)
                        return
                    else:
                        return

        elif self._cross_zoning and entity_id in self._motion_sensors and self._state in (
            AlarmControlPanelState.ARMED_AWAY,
            AlarmControlPanelState.ARMED_NIGHT,
        ):
            now_loop = self.hass.loop.time()
            confirmed = False
            for prev_id, prev_time in list(self._last_motion_detection.items()):
                diff = now_loop - prev_time
                if (diff <= self._cross_zoning_window) and (prev_id != entity_id or diff >= 2.0):
                    confirmed = True
                    break

            self._last_motion_detection[entity_id] = now_loop
            cutoff = now_loop - (self._cross_zoning_window * 2)
            self._last_motion_detection = {k: v for k, v in self._last_motion_detection.items() if v >= cutoff}

            if not confirmed:
                self._log_event(f"Pré-détection mouvement (Cross-Zoning): {new_state.name}")
                return
            else:
                self._log_event(f"Double détection confirmée sur {new_state.name}")

        if self._state == AlarmControlPanelState.TRIGGERED:
            if self._siren_task is None:
                if self._disarm_cooldown_task:
                    self._disarm_cooldown_task()
                    self._disarm_cooldown_task = None
                await self._async_trigger_alarm(entity_id)
            else:
                if entity_id not in self._faults:
                    self._faults.append(entity_id)
                self.async_write_ha_state()
                self._siren_task()
                self._siren_task = async_call_later(
                    self.hass,
                    self._siren_duration,
                    self._cb_turn_off_siren,
                )
                self._log_event(f"Nouvelle détection: {new_state.name} (Sirène prolongée)")
                await self.notification_manager.async_send_notification(
                    f"🚨 Nouvelle détection pendant l'alerte : {new_state.name}\n({dt_now().strftime('%H:%M:%S')})",
                    is_alert=True,
                )
            return

        if self._state == AlarmControlPanelState.ARMED_HOME:
            if entity_id in self._opening_sensors:
                await self._async_trigger_alarm(entity_id)

        elif self._state in (AlarmControlPanelState.ARMED_AWAY, AlarmControlPanelState.ARMED_NIGHT):
            is_valid_sensor = False
            if self._state == AlarmControlPanelState.ARMED_NIGHT:
                is_valid_sensor = entity_id in self._night_sensors
            else:
                is_valid_sensor = (entity_id in self._opening_sensors) or (entity_id in self._motion_sensors)

            if is_valid_sensor:
                if self._cameras:
                    self.hass.async_create_task(self._async_capture_cameras(entity_id))

                if self._state == AlarmControlPanelState.ARMED_AWAY and self._entry_delay > 0 and not getattr(self, "_post_trigger_active", False):
                    if self._pending_task is None:
                        self._pre_trigger_state = self._state
                        self._state = AlarmControlPanelState.PENDING
                        if entity_id not in self._faults:
                            self._faults.append(entity_id)
                        self._triggered_by = new_state.name
                        self.async_write_ha_state()
                        await self.notification_manager.async_pre_alarm_feedback()
                        await self.notification_manager.async_send_notification(
                            f"⏳ Délai d'entrée déclenché par {new_state.name}. Veuillez désarmer.",
                            is_alert=True,
                        )
                        self._pending_task = async_call_later(
                            self.hass,
                            self._entry_delay,
                            self._cb_entry_delay_expired,
                        )
                else:
                    await self._async_trigger_alarm(entity_id)

    # ─── Alarm Triggering ─────────────────────────────────────────

    @callback
    def _cb_entry_delay_expired(self, now=None):
        """Callback when entry delay timer expires."""
        self._pending_task = None
        self.hass.async_create_task(self._async_trigger_alarm(self._triggered_by or "Délai d'entrée expiré"))

    async def _async_trigger_alarm(self, triggering_entity):
        """Trigger the alarm — full alert sequence."""
        if self._state == AlarmControlPanelState.TRIGGERED and self._siren_task is not None:
            return

        self._state = AlarmControlPanelState.TRIGGERED
        self._last_triggered_by = triggering_entity
        self.async_write_ha_state()

        if self._pending_task:
            self._pending_task()
            self._pending_task = None

        if triggering_entity not in self._faults:
            self._faults.append(triggering_entity)

        state = self.hass.states.get(triggering_entity)
        self._triggered_by = state.name if state else triggering_entity

        if triggering_entity in self._tamper_sensors:
            self._log_event(f"🚨 Sabotage DÉCLENCHÉ par {self._triggered_by}")
        else:
            self._log_event(f"🚨 Alarme DÉCLENCHÉE par {self._triggered_by}")

        name = state.name if state else triggering_entity
        self._record_incident(
            "intrusion",
            {
                "sensor": triggering_entity,
                "sensor_name": self._triggered_by,
                "mode": str(self._pre_trigger_state),
            },
        )
        self.hass.async_create_task(self._async_sync_keypads("triggered"))

        should_siren = (
            self._pre_trigger_state == AlarmControlPanelState.ARMED_AWAY
            or triggering_entity in self._tamper_sensors
        )

        if self._siren_task:
            self._siren_task()
        self._siren_task = async_call_later(
            self.hass,
            self._siren_duration,
            self._cb_turn_off_siren,
        )

        if should_siren:
            await self._async_turn_on_siren()

        # Notifications
        french_time = self._get_french_time()
        alarm_name = self.name or "Domolink Alarm"
        self.hass.async_create_task(
            self.notification_manager.async_send_notification(
                f"🚨 INTRUSION DÉTECTÉE 🚨\n{name} a déclenché l'alarme {alarm_name} le {french_time}",
                is_alert=True,
            )
        )

        # TTS voice deterrence
        should_tts = (
            self._pre_trigger_state in (
                AlarmControlPanelState.ARMED_AWAY,
                AlarmControlPanelState.ARMED_NIGHT,
                AlarmControlPanelState.DISARMED,
            )
            or triggering_entity in self._tamper_sensors
        )
        if should_tts:
            self.hass.async_create_task(
                self.notification_manager.async_play_tts(
                    self._tts_alarm_msg, volume=self._tts_volume_alert
                )
            )

        # Camera snapshots and recording
        if self._cameras:
            self.hass.async_create_task(self._async_capture_cameras(triggering_entity))

    async def _async_turn_on_siren(self):
        """Turn on physical sirens and panic lights."""
        if self._sirens:
            self._log_event("Activation des sirènes")
            try:
                await self.hass.services.async_call("homeassistant", "turn_on", {"entity_id": self._sirens})
            except Exception as e:
                _LOGGER.error("Failed to turn on sirens: %s", e)

        if self._lights:
            try:
                await self.hass.services.async_call(
                    "light", "turn_on", {"entity_id": self._lights, "color_name": "red", "brightness": 255}
                )
            except Exception:
                try:
                    await self.hass.services.async_call("homeassistant", "turn_on", {"entity_id": self._lights})
                except Exception:
                    pass

    @callback
    def _cb_turn_off_siren(self, now=None):
        """Sync @callback for async_call_later — schedules async cleanup."""
        self.hass.async_create_task(self._async_turn_off_siren())

    async def _async_turn_off_siren(self):
        """Turn off sirens and panic lights."""
        self._log_event("Arrêt des sirènes et des lumières")
        if self._sirens:
            try:
                await self.hass.services.async_call("homeassistant", "turn_off", {"entity_id": self._sirens})
            except Exception as e:
                _LOGGER.error("Failed to turn off sirens: %s", e)
        if self._lights:
            try:
                await self.hass.services.async_call("homeassistant", "turn_off", {"entity_id": self._lights})
            except Exception as e:
                _LOGGER.error("Failed to turn off lights: %s", e)
        self._siren_task = None

        if self._state == AlarmControlPanelState.TRIGGERED:
            self._log_event("Fin de sonnerie sirène — Attente de désarmement (1 minute avant réarmement)")
            self.async_write_ha_state()
            if self._disarm_cooldown_task:
                self._disarm_cooldown_task()
            self._disarm_cooldown_task = async_call_later(
                self.hass,
                60,
                self._cb_auto_rearm_after_alarm,
            )

    @callback
    def _cb_auto_rearm_after_alarm(self, now=None):
        """Callback when 60s disarm grace period ends."""
        self._disarm_cooldown_task = None
        self.hass.async_create_task(self._async_auto_rearm_after_alarm())

    async def _async_auto_rearm_after_alarm(self):
        """Finalize automatic re-arm after alarm cycle."""
        if self._state != AlarmControlPanelState.TRIGGERED:
            return

        target_state = (
            self._pre_trigger_state
            if self._pre_trigger_state not in (AlarmControlPanelState.DISARMED, AlarmControlPanelState.TRIGGERED)
            else AlarmControlPanelState.ARMED_AWAY
        )
        self._state = target_state
        self._faults.clear()
        self._post_trigger_active = True
        self.async_write_ha_state()

        french_time = self._get_french_time()
        alarm_name = self.name or "Domolink Alarm"
        trigger_name = self._triggered_by or "Un capteur"
        msg = f"Fin d'alerte : {trigger_name} a déclenché l'alarme {alarm_name}. Plus de contact, maison de nouveau sous alarme ({french_time})."
        await self.notification_manager.async_send_notification(msg)
        self._log_event(f"Système ré-armé automatiquement ({target_state.value})")

    def _cancel_all_tasks(self):
        """Cancel any pending timers."""
        self._post_trigger_active = False
        if self._disarm_cooldown_task:
            self._disarm_cooldown_task()
            self._disarm_cooldown_task = None
        if self._arming_task:
            self._arming_task()
            self._arming_task = None
        if self._pending_task:
            self._pending_task()
            self._pending_task = None
        if self._siren_task:
            self._siren_task()
            self._siren_task = None
        self.geofence_manager.cancel_all()
        if not self.presence_simulator.forced:
            self.presence_simulator.stop()
        if self._pre_alert_task:
            self._pre_alert_task()
            self._pre_alert_task = None
        self._pre_alert_active = False
        self._pre_alert_sensor = None

    @callback
    def _cb_nf_a2p_timeout(self, now=None):
        """Handle expiration of NF A2P double detection confirmation window."""
        _LOGGER.info("Domolink NF A2P: Fenêtre de confirmation expirée sans second détecteur.")
        self._pre_alert_active = False
        self._pre_alert_sensor = None
        self._pre_alert_task = None
        self._log_event("NF A2P : Fin de pré-alerte (fausse alerte écartée)")
        self.async_write_ha_state()
        self.hass.async_create_task(self._async_sync_keypads("pre_alert_ended"))

    def _record_incident(self, trigger_type, details=None):
        """Record certified incident report structure for export."""
        now = dt_now()
        timestamp = now.isoformat()
        incident_id = f"INC-{now.strftime('%Y%m%d%H%M%S')}"

        recent_logs = list(self._system_events[:15])

        incident_data = {
            "id": incident_id,
            "timestamp": timestamp,
            "french_date": self._get_french_time(),
            "type": trigger_type,
            "alarm_name": self.name or "Domolink Alarm",
            "state_before": str(getattr(self, "_pre_trigger_state", self._state)),
            "trigger_sensor": getattr(self, "_last_triggered_by", None),
            "trigger_name": getattr(self, "_triggered_by", "Inconnu"),
            "details": details or {},
            "active_faults": list(self._faults),
            "bypassed_sensors": list(self._bypassed_sensors),
            "recent_events": recent_logs,
            "system_version": self._system_version,
        }

        raw_payload = json.dumps(incident_data, sort_keys=True, ensure_ascii=False)
        sha256_hash = hashlib.sha256(raw_payload.encode("utf-8")).hexdigest()
        incident_data["sha256_token"] = sha256_hash.upper()

        self._last_incident_report = incident_data
        _LOGGER.info("Domolink: Rapport d'incident certifié créé: %s (SHA256: %s)", incident_id, sha256_hash[:12])
        return incident_data

    def get_incident_report_data(self):
        """Return latest incident report data or build one from recent state."""
        if self._last_incident_report:
            return self._last_incident_report
        return self._record_incident("system_snapshot", {"reason": "export_manuel"})

    # ─── User Profiles & Code Validation ──────────────────────────

    async def async_add_user_profile(
        self,
        name,
        pin,
        role="guest",
        valid_from=None,
        valid_to=None,
        allowed_days=None,
        allowed_hours=None,
        single_use=False,
        enabled=True,
    ):
        """Add or update a temporary / guest user profile with secure PBKDF2 hashed PIN."""
        if not name or not pin:
            raise HomeAssistantError("Nom et code PIN obligatoires.")

        clean_name = str(name).strip()
        clean_pin = str(pin).strip()

        self._users_profiles = [
            p for p in self._users_profiles
            if p.get("name") != clean_name and not verify_pin(clean_pin, p.get("pin", ""))[0]
        ]

        profile = {
            "id": secrets.token_hex(6),
            "name": clean_name,
            "pin": clean_pin if is_hashed(clean_pin) else hash_pin(clean_pin),
            "role": str(role).strip(),
            "valid_from": valid_from,
            "valid_to": valid_to,
            "allowed_days": allowed_days if allowed_days is not None else [1, 2, 3, 4, 5, 6, 7],
            "allowed_hours": allowed_hours,
            "single_use": bool(single_use),
            "enabled": bool(enabled),
            "created_at": utcnow().isoformat(),
        }
        self._users_profiles.append(profile)
        await self._async_persist_user_profiles()
        self._log_event(f"Profil utilisateur ajouté : {clean_name} ({role})")
        self.async_write_ha_state()

    async def async_delete_user_profile(self, profile_id=None, pin=None, name=None):
        """Delete a user profile by profile_id, name or pin."""
        initial_len = len(self._users_profiles)
        self._users_profiles = [
            p for p in self._users_profiles
            if (profile_id is None or p.get("id") != str(profile_id).strip())
            and (name is None or p.get("name") != str(name).strip())
            and (pin is None or not verify_pin(str(pin).strip(), p.get("pin", ""))[0])
        ]
        if len(self._users_profiles) != initial_len:
            await self._async_persist_user_profiles()
            self._log_event(f"Profil utilisateur supprimé : {name or profile_id or 'Profil'}")
            self.async_write_ha_state()

    async def _async_persist_user_profiles(self):
        """Save user profiles into config entry options."""
        if not self._entry:
            return
        new_options = dict(self._entry.options if self._entry.options else self._entry.data)
        new_options[CONF_USERS_PROFILES] = json.dumps(self._users_profiles)
        self.hass.config_entries.async_update_entry(self._entry, options=new_options)

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
                "GEOFENCE": "Géolocalisation",
            }
            return special_names.get(code, "Système")

        current_time = self.hass.loop.time()

        if self._blocked_until > current_time:
            remaining = int(self._blocked_until - current_time)
            _LOGGER.warning("Keypad blocked for %d more seconds", remaining)
            return None

        if self._duress_code:
            valid_d, migrate_d = verify_pin(code, self._duress_code)
            if valid_d:
                if migrate_d:
                    self._duress_code = hash_pin(code)
                    self._async_persist_users_and_duress()
                return "DURESS"

        matched_user = None
        needs_users_persist = False
        for uname, stored_val in list(self._users.items()):
            valid_u, migrate_u = verify_pin(code, stored_val)
            if valid_u:
                matched_user = uname
                if migrate_u:
                    self._users[uname] = hash_pin(code)
                    needs_users_persist = True
                break

        if matched_user:
            self._failed_attempts = 0
            if needs_users_persist:
                self._async_persist_users_and_duress()
            return matched_user

        if hasattr(self, "_users_profiles") and self._users_profiles:
            now_dt = dt_now()
            for profile in self._users_profiles:
                stored_pin = profile.get("pin")
                if not stored_pin:
                    continue
                valid_p, migrate_p = verify_pin(code, stored_pin)
                if not valid_p:
                    continue

                if migrate_p:
                    profile["pin"] = hash_pin(code)
                    self.hass.async_create_task(self._async_persist_user_profiles())
                if not profile.get("enabled", True):
                    _LOGGER.warning("Domolink: Profil '%s' désactivé", profile.get("name"))
                    break

                valid_from = profile.get("valid_from")
                if valid_from:
                    try:
                        from_dt = dt_util.parse_datetime(valid_from)
                        if from_dt and now_dt < from_dt:
                            _LOGGER.warning("Domolink: Profil '%s' pas encore actif", profile.get("name"))
                            break
                    except Exception:
                        pass

                valid_to = profile.get("valid_to")
                if valid_to:
                    try:
                        to_dt = dt_util.parse_datetime(valid_to)
                        if to_dt and now_dt > to_dt:
                            _LOGGER.warning("Domolink: Profil '%s' expiré", profile.get("name"))
                            break
                    except Exception:
                        pass

                allowed_days = profile.get("allowed_days")
                if allowed_days:
                    today_iso = now_dt.isoweekday()
                    if today_iso not in allowed_days and str(today_iso) not in [str(d) for d in allowed_days]:
                        _LOGGER.warning("Domolink: Profil '%s' non autorisé le jour %s", profile.get("name"), today_iso)
                        break

                allowed_hours = profile.get("allowed_hours")
                if allowed_hours and "-" in allowed_hours:
                    try:
                        sh, sm = map(int, allowed_hours.split("-")[0].strip().split(":"))
                        eh, em = map(int, allowed_hours.split("-")[1].strip().split(":"))
                        cur_minutes = now_dt.hour * 60 + now_dt.minute
                        start_minutes = sh * 60 + sm
                        end_minutes = eh * 60 + em
                        if cur_minutes < start_minutes or cur_minutes > end_minutes:
                            _LOGGER.warning("Domolink: Profil '%s' hors plage horaire (%s)", profile.get("name"), allowed_hours)
                            break
                    except Exception as e:
                        _LOGGER.debug("Domolink: Erreur vérification horaires: %s", e)

                self._failed_attempts = 0
                prof_name = profile.get("name", "Invité")
                prof_role = profile.get("role", "invité")

                if profile.get("single_use", False):
                    profile["enabled"] = False
                    profile["used_at"] = utcnow().isoformat()
                    self.hass.async_create_task(self._async_persist_user_profiles())

                return f"{prof_name} ({prof_role})"

        self._failed_attempts += 1
        _LOGGER.warning("Invalid code attempt %d/3", self._failed_attempts)

        if self._failed_attempts >= 3:
            self._blocked_until = current_time + 300
            self.hass.async_create_task(
                self.notification_manager.async_send_notification(
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

    # ─── Arm / Disarm Commands ────────────────────────────────────

    async def async_alarm_disarm(self, code=None):
        """Send disarm command."""
        user = self._validate_code(code)
        if not user:
            _LOGGER.warning("Invalid code provided for disarm")
            raise HomeAssistantError("Code PIN invalide.")

        if user == "DURESS":
            await self.notification_manager.async_send_notification(
                "🆘 ALERTE SOS SILENCIEUSE (Code de détresse utilisé) 🆘",
                is_alert=True,
                is_emergency=True,
            )

        self._record_arm_event("disarm", user)
        self._cancel_all_tasks()
        self._state = AlarmControlPanelState.DISARMED
        self._last_user = user
        self._faults.clear()
        self._bypassed_sensors.clear()
        self._triggered_by = None
        self._log_event(f"Alarme Désarmée par {user}")
        self.hass.async_create_task(self._async_sync_cameras(False))
        self.async_write_ha_state()

        await self._async_turn_off_siren()
        self.hass.async_create_task(self._async_sync_keypads("disarmed"))

        if user != "DURESS":
            self.hass.async_create_task(
                self.notification_manager.async_play_tts(f"Alarme désarmée. Bienvenue {user}.")
            )

    async def _check_bypass(self, target_mode="AWAY", force=False):
        """Check if sensors are open or unavailable before arming."""
        open_sensors = []
        for sensor in self._opening_sensors:
            if sensor in self._bypassed_sensors:
                continue
            state = self.hass.states.get(sensor)
            if state is None:
                continue
            if str(state.state).lower() in ("on", "open", "true", "detected", "unlocked", "1", "unavailable"):
                name = state.name if state and state.name else sensor
                open_sensors.append(name)

        if target_mode == "NIGHT":
            for sensor in self._night_sensors:
                if sensor in self._bypassed_sensors:
                    continue
                state = self.hass.states.get(sensor)
                if state is None:
                    continue
                if str(state.state).lower() in ("on", "open", "true", "detected", "unlocked", "1", "unavailable"):
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
                await self.notification_manager.async_send_notification(message, custom_data=action_data)
                raise HomeAssistantError(f"Échec armement : {len(open_sensors)} capteur(s) ouvert(s). Consultez vos notifications.")
            else:
                sensor_list = "\n".join(f"• {s}" for s in open_sensors)
                await self.notification_manager.async_send_notification(
                    f"⚠️ Alarme armée avec bypass automatique.\nCapteurs ignorés :\n{sensor_list}"
                )

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
                self.notification_manager.async_send_notification(f"🪫 Attention : Pile faible sur {batt_str}")
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
        self._pre_trigger_state = AlarmControlPanelState.ARMED_HOME
        self._state = AlarmControlPanelState.ARMED_HOME
        self._last_user = user or "Dashboard"
        self._record_arm_event("arm", self._last_user, "HOME")
        self._log_event(f"Alarme Armée (Mode: Présent) par {self._last_user}")
        self.hass.async_create_task(self._async_sync_cameras(True))
        self.hass.async_create_task(self._async_sync_keypads("armed_home"))
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
            self.hass.async_create_task(self._async_sync_keypads("arming"))
            self._arming_task = async_call_later(
                self.hass,
                self._exit_delay,
                self._cb_arm_away_complete,
            )
        else:
            self._cb_arm_away_complete()

    @callback
    def _cb_arm_away_complete(self, now=None):
        """Sync @callback: finalize arm away."""
        self._state = AlarmControlPanelState.ARMED_AWAY
        self._pre_trigger_state = AlarmControlPanelState.ARMED_AWAY
        self._log_event(f"Alarme Armée (Mode: Absent) par {self._last_user}")
        self._start_presence_simulation()
        self.hass.async_create_task(self._async_sync_cameras(True))
        self.hass.async_create_task(self._async_sync_keypads("armed_away"))
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
        self._pre_trigger_state = AlarmControlPanelState.ARMED_NIGHT
        self._state = AlarmControlPanelState.ARMED_NIGHT
        self._last_user = user or "Dashboard"
        self._record_arm_event("arm", self._last_user, "NIGHT")
        self._log_event(f"Alarme Armée (Mode: Nuit) par {self._last_user}")
        self.hass.async_create_task(self._async_sync_cameras(True))
        self.hass.async_create_task(self._async_sync_keypads("armed_night"))
        self.async_write_ha_state()

    async def async_panic(self, activate_sirens=False):
        """Trigger panic mode."""
        self._log_event("🚨 BOUTON PANIQUE SOS ACTIVÉ")
        message = "🚨 ALERTE PANIQUE SOS DÉCLENCHÉE MANUELLEMENT 🚨"

        await self.notification_manager.async_send_notification(
            message,
            is_alert=True,
            is_emergency=True,
        )

        if activate_sirens and self._sirens:
            self._log_event("Activation manuelle des sirènes (Panique)")
            try:
                await self.hass.services.async_call(
                    "homeassistant", "turn_on", {"entity_id": self._sirens}
                )
                self._siren_task = async_call_later(
                    self.hass,
                    self._siren_duration,
                    self._cb_turn_off_siren,
                )
            except Exception as e:
                _LOGGER.error("Failed to turn on sirens for panic: %s", e)

        if self._lights:
            try:
                await self.hass.services.async_call(
                    "light", "turn_on", {"entity_id": self._lights, "color_name": "red", "brightness": 255}
                )
            except Exception:
                try:
                    await self.hass.services.async_call("homeassistant", "turn_on", {"entity_id": self._lights})
                except Exception:
                    pass

    @callback
    def _cb_siren_test(self, now):
        """Run weekly siren test."""
        target_day = (self._siren_test_day - 1) if (1 <= self._siren_test_day <= 7) else self._siren_test_day
        if now.weekday() != (target_day % 7):
            return

        self._log_event("Test automatique des sirènes en cours...")
        self.hass.async_create_task(self.notification_manager.async_run_siren_test())

    @callback
    def _cb_schedule_arm(self, now):
        """Arm alarm on schedule."""
        if self._state == AlarmControlPanelState.DISARMED:
            self._log_event("Auto-armement horaire déclenché")
            if self._schedule_mode == "night":
                self.hass.async_create_task(self.async_alarm_arm_night("AUTO_SCHEDULE"))
            else:
                self.hass.async_create_task(self.async_alarm_arm_home("AUTO_SCHEDULE"))

            self.hass.async_create_task(
                self.notification_manager.async_send_notification(
                    f"⏰ Armement automatique horaire activé (Mode {self._schedule_mode})."
                )
            )

    @callback
    def _cb_schedule_disarm(self, now):
        """Disarm alarm on schedule."""
        if self._state in (AlarmControlPanelState.ARMED_HOME, AlarmControlPanelState.ARMED_NIGHT):
            self._log_event("Auto-désarmement horaire déclenché")
            self.hass.async_create_task(self.async_alarm_disarm("AUTO_SCHEDULE"))
            self.hass.async_create_task(
                self.notification_manager.async_send_notification("⏰ Désarmement automatique horaire effectué.")
            )

    # ─── Settings Update Service ──────────────────────────────────

    async def async_update_settings(self, call):
        """Update settings from frontend."""
        new_options = dict(self._entry.options if self._entry.options else self._entry.data)

        valid_keys = {
            CONF_NAME,
            CONF_OPENING_SENSORS, CONF_OPENING_SENSORS_LABELS,
            CONF_NIGHT_SENSORS, CONF_NIGHT_SENSORS_LABELS,
            CONF_MOTION_SENSORS, CONF_MOTION_SENSORS_LABELS,
            CONF_CAMERAS, CONF_CAMERAS_LABELS,
            CONF_CAMERAS_ARM_ENTITIES, CONF_CAMERAS_ARM_ENTITIES_LABELS,
            CONF_TAMPER_SENSORS, CONF_TAMPER_SENSORS_LABELS,
            CONF_KEYPADS, CONF_KEYPADS_LABELS,
            CONF_SAFETY_SENSORS, CONF_SAFETY_SENSORS_LABELS,
            CONF_SIRENS, CONF_SIRENS_LABELS,
            CONF_LIGHTS, CONF_LIGHTS_LABELS,
            CONF_MEDIA_PLAYERS, CONF_MEDIA_PLAYERS_LABELS,
            CONF_NOTIFY_SERVICES, CONF_NOTIFY_SERVICES_LABELS,
            CONF_FREE_MOBILE_USER, CONF_FREE_MOBILE_PASS,
            CONF_ICLOUD_ACCOUNT, CONF_ICLOUD_DEVICES,
            CONF_EMERGENCY_CONTACT, CONF_EMERGENCY_CONTACT_LABELS,
            CONF_PRESENCE_SIMULATION_ENTITIES, CONF_PRESENCE_SIMULATION_LABELS,
            CONF_ZONE_LABELS, CONF_GLOBAL_CAMERAS, CONF_GLOBAL_CAMERAS_LABELS,
            CONF_PERSONS, CONF_PERSONS_LABELS,
            CONF_USERS_CODES, CONF_DURESS_CODE, CONF_RFID_TAGS,
            CONF_EXIT_DELAY, CONF_ENTRY_DELAY, CONF_SIREN_DURATION,
            CONF_BYPASS_ALLOWED, CONF_HEALTH_CHECK, CONF_GEOFENCE_AUTO_ARM,
            CONF_GEOFENCE_REMINDER, CONF_GEOFENCE_REMINDER_DELAY,
            CONF_CHIME_MODE, CONF_CROSS_ZONING, CONF_CROSS_ZONING_WINDOW,
            CONF_PRESENCE_SIMULATION_HISTORY_DAYS,
            CONF_SIREN_TEST, CONF_SIREN_TEST_DAY, CONF_SIREN_TEST_HOUR,
            CONF_SCHEDULE_ENABLED, CONF_SCHEDULE_ARM_TIME, CONF_SCHEDULE_DISARM_TIME, CONF_SCHEDULE_MODE,
            CONF_MQTT_ENABLED, CONF_MQTT_TOPIC_BASE, CONF_MQTT_REQUIRE_CODE,
            CONF_TELEGRAM_ENABLED, CONF_TELEGRAM_TOKEN, CONF_TELEGRAM_CHAT_ID,
            CONF_FTP_ENABLED, CONF_FTP_PROTOCOL, CONF_FTP_HOST, CONF_FTP_PORT, CONF_FTP_USER, CONF_FTP_PASS, CONF_FTP_PATH,
            CONF_FTP_ALLOW_INSECURE_TLS,
            CONF_WEBDAV_ENABLED, CONF_WEBDAV_URL, CONF_WEBDAV_USER, CONF_WEBDAV_PASS, CONF_WEBDAV_PATH,
            CONF_NAS_TYPE,
            CONF_NAS_CONFIGS,
            CONF_GOOGLE_DRIVE_ENABLED, CONF_GOOGLE_DRIVE_METHOD, CONF_GOOGLE_DRIVE_WEBHOOK_URL,
            CONF_GOOGLE_DRIVE_CLIENT_ID, CONF_GOOGLE_DRIVE_CLIENT_SECRET, CONF_GOOGLE_DRIVE_REFRESH_TOKEN,
            CONF_GOOGLE_DRIVE_FOLDER_ID,
            CONF_MEDIA_PATH, CONF_MEDIA_RETENTION_DAYS, CONF_MEDIA_MAX_SIZE_MB,
            CONF_NF_A2P_MODE, CONF_NF_A2P_WINDOW, CONF_NF_A2P_STRICT_DISTINCT, CONF_NF_A2P_PRE_ALERT_CHIME,
            CONF_USERS_PROFILES,
            CONF_PROXIMITY_SENSOR, CONF_GEOFENCE_APPROACH_REMINDER, CONF_GEOFENCE_APPROACH_DISTANCE,
            CONF_KEYPAD_ENABLED, CONF_KEYPAD_BEEP_ENTRY, CONF_KEYPAD_BEEP_EXIT,
            CONF_DETERRENCE_ENABLED, CONF_DETERRENCE_LEVEL, CONF_TTS_PRE_ALERT_MSG, CONF_TTS_ALARM_MSG, CONF_TTS_VOLUME_ALERT, CONF_TTS_VOLUME_INFO,
            CONF_FAILOVER_GSM_ENABLED, CONF_FAILOVER_GSM_SERVICE, CONF_FAILOVER_LOCAL_ALARM,
        }

        secret_keys = {
            CONF_FREE_MOBILE_PASS,
            CONF_FTP_PASS,
            CONF_WEBDAV_PASS,
            CONF_TELEGRAM_TOKEN,
            CONF_GOOGLE_DRIVE_CLIENT_SECRET,
            CONF_GOOGLE_DRIVE_REFRESH_TOKEN,
        }

        updated = False
        for key, value in call.data.items():
            if key in valid_keys:
                if key in secret_keys:
                    if value in (SECRET_MASK, "••••••••", "••••"):
                        continue
                    if not value and (new_options.get(key) or self._entry.data.get(key)):
                        continue

                elif key == CONF_DURESS_CODE:
                    if value in (SECRET_MASK, "••••••••", "••••"):
                        continue
                    if value and not is_hashed(value):
                        value = hash_pin(value)

                elif key == CONF_USERS_CODES:
                    new_pairs = []
                    for pair in str(value).split(","):
                        pair = pair.strip()
                        if ":" in pair:
                            uname, ucode = pair.split(":", 1)
                            uname, ucode = uname.strip(), ucode.strip()
                            if not uname:
                                continue
                            if ucode in (SECRET_MASK, "••••••••", "••••", ""):
                                existing_code = self._users.get(uname)
                                if existing_code:
                                    new_pairs.append(f"{uname}:{existing_code}")
                                else:
                                    new_pairs.append(f"{uname}:")
                            else:
                                hashed = ucode if is_hashed(ucode) else hash_pin(ucode)
                                new_pairs.append(f"{uname}:{hashed}")
                    value = ", ".join(new_pairs)

                new_options[key] = value
                updated = True

        if CONF_NAS_CONFIGS in call.data:
            nas_cfgs = call.data[CONF_NAS_CONFIGS]
            if isinstance(nas_cfgs, dict):
                orig_cfgs = self._get_config_value(CONF_NAS_CONFIGS, DEFAULT_NAS_CONFIGS) or {}
                for brand, cfg in nas_cfgs.items():
                    if isinstance(cfg, dict) and brand in orig_cfgs:
                        if cfg.get("ftp_pass") in (SECRET_MASK, "••••••••", "••••"):
                            cfg["ftp_pass"] = orig_cfgs[brand].get("ftp_pass", "")
                        if cfg.get("webdav_pass") in (SECRET_MASK, "••••••••", "••••"):
                            cfg["webdav_pass"] = orig_cfgs[brand].get("webdav_pass", "")
                new_options[CONF_NAS_CONFIGS] = nas_cfgs
                cur_nas = str(new_options.get(CONF_NAS_TYPE, self._get_config_value(CONF_NAS_TYPE, DEFAULT_NAS_TYPE))).lower()
                if cur_nas in nas_cfgs and isinstance(nas_cfgs[cur_nas], dict):
                    cur_cfg = nas_cfgs[cur_nas]
                    for k in [
                        "ftp_enabled", "ftp_protocol", "ftp_host", "ftp_port", "ftp_user", "ftp_pass", "ftp_path",
                        "ftp_allow_insecure_tls", "webdav_enabled", "webdav_url", "webdav_user", "webdav_pass", "webdav_path"
                    ]:
                        if k in cur_cfg:
                            new_options[k] = cur_cfg[k]
        elif CONF_NAS_TYPE in call.data:
            cur_nas = str(call.data[CONF_NAS_TYPE]).lower()
            nas_cfgs = new_options.get(CONF_NAS_CONFIGS, self._get_config_value(CONF_NAS_CONFIGS, DEFAULT_NAS_CONFIGS)) or {}
            if cur_nas in nas_cfgs and isinstance(nas_cfgs[cur_nas], dict):
                cur_cfg = nas_cfgs[cur_nas]
                for k in [
                    "ftp_enabled", "ftp_protocol", "ftp_host", "ftp_port", "ftp_user", "ftp_pass", "ftp_path",
                    "webdav_enabled", "webdav_url", "webdav_user", "webdav_pass", "webdav_path"
                ]:
                    if k in cur_cfg:
                        new_options[k] = cur_cfg[k]

        if updated:
            self.hass.config_entries.async_update_entry(self._entry, options=new_options)
            _LOGGER.info("Domolink: Settings updated -> %s", list(call.data.keys()))
            self._log_event("Paramètres mis à jour")

    # ─── Delegated Service & Manager Methods ──────────────────────

    async def async_start_presence_simulation(self):
        """Service handler: start presence simulation."""
        await self.presence_simulator.async_start()

    async def async_stop_presence_simulation(self):
        """Service handler: stop presence simulation."""
        await self.presence_simulator.async_stop()

    async def async_toggle_presence_simulation(self):
        """Service handler: toggle presence simulation."""
        await self.presence_simulator.async_toggle()

    def _start_presence_simulation(self):
        """Internal helper: start presence simulation."""
        self.presence_simulator.start()

    def _stop_presence_simulation(self):
        """Internal helper: stop presence simulation."""
        self.presence_simulator.stop()

    async def async_snooze_reminder(self, duration_minutes=15):
        """Service handler: snooze reminder."""
        await self.geofence_manager.async_snooze_reminder(duration_minutes)

    async def async_clean_media(self, call=None):
        """Service handler: clean media files."""
        return await self.media_manager.async_clean_media(call)

    async def async_media_action(self, call):
        """Service handler: rename or delete media file."""
        await self.media_manager.async_media_action(call)

    async def async_test_cameras_recording(self, call=None):
        """Service handler: test camera recording."""
        await self.media_manager.async_test_cameras_recording(call)

    async def _async_sync_cameras(self, arm: bool):
        """Sync camera arming/privacy state."""
        await self.media_manager.async_sync_cameras(arm)

    async def _async_capture_cameras(self, triggering_entity=None):
        """Capture targeted cameras on detection."""
        target_cameras, matching_zones = self._get_cameras_for_sensor(triggering_entity)
        if not target_cameras:
            target_cameras = list(self._cameras)
        await self.media_manager.async_capture_cameras(target_cameras, matching_zones)

    async def async_test_ftp(self, call=None):
        """Service handler: test FTP connection."""
        return await self.cloud_uploader.async_test_ftp(call)

    async def async_test_webdav(self, call=None):
        """Service handler: test WebDAV connection."""
        return await self.cloud_uploader.async_test_webdav(call)

    async def async_test_google_drive(self, call=None):
        """Service handler: test Google Drive connection."""
        return await self.cloud_uploader.async_test_google_drive(call)

    async def _async_send_notification(self, message, is_alert=False, custom_data=None, is_emergency=False):
        """Dispatch notification across all channels."""
        await self.notification_manager.async_send_notification(message, is_alert, custom_data, is_emergency)

    async def _async_play_tts(self, message, volume=None):
        """Play TTS announcement."""
        await self.notification_manager.async_play_tts(message, volume)
