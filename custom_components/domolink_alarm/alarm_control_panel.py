"""Interfaces with Domolink Alarm."""
import os
import re
import random
import logging
import datetime
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
from homeassistant.util.dt import utcnow, now as dt_now

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
    CONF_CAMERAS_ARM_ENTITIES,
    CONF_CAMERAS_ARM_ENTITIES_LABELS,
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
    CONF_ZONE_LABELS,
    CONF_GLOBAL_CAMERAS,
    CONF_GLOBAL_CAMERAS_LABELS,
    CONF_KEYPADS,
    CONF_KEYPADS_LABELS,
    CONF_PRESENCE_SIMULATION_ENTITIES,
    CONF_PRESENCE_SIMULATION_LABELS,
    CONF_PRESENCE_SIMULATION_HISTORY_DAYS,
    CONF_CROSS_ZONING,
    CONF_CROSS_ZONING_WINDOW,
    CONF_GEOFENCE_REMINDER,
    CONF_GEOFENCE_REMINDER_DELAY,
    CONF_FREE_MOBILE_USER,
    CONF_FREE_MOBILE_PASS,
    CONF_ICLOUD_ACCOUNT,
    CONF_ICLOUD_DEVICES,
    CONF_EMERGENCY_CONTACT,
    CONF_EMERGENCY_CONTACT_LABELS,
    CONF_SIREN_TEST,
    CONF_SIREN_TEST_DAY,
    CONF_SIREN_TEST_HOUR,
    CONF_SCHEDULE_ENABLED,
    CONF_SCHEDULE_ARM_TIME,
    CONF_SCHEDULE_DISARM_TIME,
    CONF_SCHEDULE_MODE,
    CONF_MQTT_ENABLED,
    CONF_MQTT_TOPIC_BASE,
    CONF_MQTT_REQUIRE_CODE,
    CONF_TELEGRAM_ENABLED,
    CONF_TELEGRAM_TOKEN,
    CONF_TELEGRAM_CHAT_ID,
    CONF_FTP_ENABLED,
    CONF_FTP_HOST,
    CONF_FTP_PORT,
    CONF_FTP_USER,
    CONF_FTP_PASS,
    CONF_FTP_PATH,
    CONF_WEBDAV_ENABLED,
    CONF_WEBDAV_URL,
    CONF_WEBDAV_USER,
    CONF_WEBDAV_PASS,
    CONF_WEBDAV_PATH,
    DEFAULT_WEBDAV_ENABLED,
    DEFAULT_WEBDAV_PATH,
    CONF_MEDIA_PATH,
    CONF_MEDIA_RETENTION_DAYS,
    CONF_MEDIA_MAX_SIZE_MB,
    DEFAULT_MEDIA_RETENTION_DAYS,
    DEFAULT_MEDIA_MAX_SIZE_MB,
    CONF_NAS_TYPE,
    DEFAULT_NAS_TYPE,
    CONF_NAS_CONFIGS,
    DEFAULT_NAS_CONFIGS,
    CONF_GOOGLE_DRIVE_ENABLED,
    CONF_GOOGLE_DRIVE_METHOD,
    CONF_GOOGLE_DRIVE_WEBHOOK_URL,
    CONF_GOOGLE_DRIVE_CLIENT_ID,
    CONF_GOOGLE_DRIVE_CLIENT_SECRET,
    CONF_GOOGLE_DRIVE_REFRESH_TOKEN,
    CONF_GOOGLE_DRIVE_FOLDER_ID,
    DEFAULT_GOOGLE_DRIVE_ENABLED,
    DEFAULT_GOOGLE_DRIVE_METHOD,
    DEFAULT_EXIT_DELAY,
    DEFAULT_ENTRY_DELAY,
    DEFAULT_SIREN_DURATION,
    DEFAULT_BYPASS_ALLOWED,
    DEFAULT_HEALTH_CHECK,
    DEFAULT_GEOFENCE_AUTO_ARM,
    DEFAULT_CHIME_MODE,
    DEFAULT_CROSS_ZONING,
    DEFAULT_CROSS_ZONING_WINDOW,
    DEFAULT_GEOFENCE_REMINDER,
    DEFAULT_GEOFENCE_REMINDER_DELAY,
    DEFAULT_PRESENCE_SIMULATION_HISTORY_DAYS,
    DEFAULT_SIREN_TEST,
    DEFAULT_SIREN_TEST_DAY,
    DEFAULT_SIREN_TEST_HOUR,
    DEFAULT_SCHEDULE_ENABLED,
    DEFAULT_SCHEDULE_ARM_TIME,
    DEFAULT_SCHEDULE_DISARM_TIME,
    DEFAULT_SCHEDULE_MODE,
    DEFAULT_MQTT_ENABLED,
    DEFAULT_MQTT_TOPIC_BASE,
    DEFAULT_MQTT_REQUIRE_CODE,
    DEFAULT_TELEGRAM_ENABLED,
    DEFAULT_FTP_ENABLED,
    DEFAULT_FTP_PORT,
    DEFAULT_FTP_PATH,
    DEFAULT_MEDIA_PATH,
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

    async def async_handle_update_settings(call):
        """Handle update settings service call."""
        await entity.async_update_settings(call)

    async def async_handle_media_action(call):
        """Handle media file actions (rename/delete)."""
        await entity.async_media_action(call)

    hass.services.async_register(
        DOMAIN, "update_settings", async_handle_update_settings
    )
    async def async_handle_test_cameras(call):
        """Handle camera test recording service call."""
        await entity.async_test_cameras_recording(call)

    async def async_handle_test_ftp(call):
        """Handle FTP test service call."""
        return await entity.async_test_ftp(call)

    async def async_handle_test_webdav(call):
        """Handle WebDAV test service call."""
        return await entity.async_test_webdav(call)

    async def async_handle_test_google_drive(call):
        """Handle Google Drive test service call."""
        return await entity.async_test_google_drive(call)

    async def async_handle_clean_media(call):
        """Handle clean media service call."""
        await entity.async_clean_media(call)

    hass.services.async_register(
        DOMAIN, "media_action", async_handle_media_action
    )
    hass.services.async_register(
        DOMAIN, "test_cameras_recording", async_handle_test_cameras
    )

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
    else:
        hass.services.async_register(
            DOMAIN, "test_ftp", async_handle_test_ftp
        )
        hass.services.async_register(
            DOMAIN, "test_webdav", async_handle_test_webdav
        )
        hass.services.async_register(
            DOMAIN, "test_google_drive", async_handle_test_google_drive
        )
    hass.services.async_register(
        DOMAIN, "clean_media", async_handle_clean_media
    )
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
        # Read version from manifest.json
        _sw_version = "0.9.51"
        try:
            import json as _json
            _manifest_path = os.path.join(os.path.dirname(__file__), "manifest.json")
            with open(_manifest_path) as _mf:
                _sw_version = _json.load(_mf).get("version", _sw_version)
        except Exception:
            pass

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._unique_id)},
            name=self._attr_name,
            manufacturer="Domolink",
            model="Domolink Smart Alarm",
            sw_version=_sw_version,
        )

        self._siren_task = None
        self._arming_task = None
        self._pending_task = None
        self._post_trigger_active = False
        self._disarm_cooldown_task = None
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
        self._system_events = []
        self._sensor_health = {}
        self._presence_simulation_events = []
        self._presence_simulation_forced = False

        self._telegram_status = "Désactivé"
        self._ftp_status = "Désactivé"
        self._webdav_status = "Désactivé"
        self._google_drive_status = "Désactivé"
        self._nas_type = DEFAULT_NAS_TYPE
        self._nas_configs = {k: dict(v) for k, v in DEFAULT_NAS_CONFIGS.items()}
        self._cameras_armed = False
        self._is_testing_cameras = False
        self._camera_test_info = {}
        self._ftp_test_running = False
        self._ftp_test_logs = []
        self._ftp_test_result = {}
        self._webdav_test_running = False
        self._webdav_test_logs = []
        self._webdav_test_result = {}
        self._nas_test_results = {}
        self._google_drive_test_running = False
        self._google_drive_test_logs = []
        self._google_drive_test_result = {}
        self._media_storage_stats = {
            "bytes": 0,
            "mb": 0.0,
            "max_mb": 1024,
            "retention_days": 30,
            "count": 0,
            "percent": 0.0,
        }

        self._load_config()

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
        
        # Find cameras that share at least one matching zone
        zone_cameras = []
        for cam in self._cameras:
            cam_labels = self._get_entity_labels(cam)
            if cam_labels.intersection(matching_zones):
                zone_cameras.append(cam)
        
        # Add global cameras
        combined = list(zone_cameras)
        for g_cam in self._global_cameras:
            if g_cam in self._cameras and g_cam not in combined:
                combined.append(g_cam)
                
        # Fallback to all cameras if no camera in this zone
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
        self._notify_services = get_merged(CONF_NOTIFY_SERVICES, CONF_NOTIFY_SERVICES_LABELS, ["notify", "script"])
        self._emergency_contact = get_merged("emergency_contact", "emergency_contact_labels", ["notify", "script"])
        self._presence_simulation_entities = get_merged(CONF_PRESENCE_SIMULATION_ENTITIES, CONF_PRESENCE_SIMULATION_LABELS, ["light", "switch", "cover"])
        
        self._free_mobile_user = options.get("free_mobile_user", data.get("free_mobile_user", ""))
        self._free_mobile_pass = options.get("free_mobile_pass", data.get("free_mobile_pass", ""))
        self._mqtt_enabled = options.get("mqtt_enabled", data.get("mqtt_enabled", False))
        self._mqtt_topic_base = options.get("mqtt_topic_base", data.get("mqtt_topic_base", "domolink/alarme"))
        self._mqtt_require_code = options.get("mqtt_require_code", data.get("mqtt_require_code", False))
        self._mqtt_unsub = None
        self._telegram_enabled = options.get("telegram_enabled", data.get("telegram_enabled", False))
        self._telegram_token = options.get("telegram_token", data.get("telegram_token", ""))
        self._telegram_chat_id = options.get("telegram_chat_id", data.get("telegram_chat_id", ""))
        self._cameras_arm_entities = get_merged(CONF_CAMERAS_ARM_ENTITIES, CONF_CAMERAS_ARM_ENTITIES_LABELS, ["switch", "alarm_control_panel", "camera"])
        self._zone_labels = options.get("zone_labels", data.get("zone_labels", [])) or []
        self._global_cameras = get_merged("global_cameras", "global_cameras_labels", ["camera"])
        self._media_path = options.get("media_path", data.get("media_path", "domolink_media")).strip().strip("/")

        # Multi-NAS Configurations
        raw_nas_configs = options.get(CONF_NAS_CONFIGS, data.get(CONF_NAS_CONFIGS, {})) or {}
        self._nas_configs = {}
        for brand, defaults in DEFAULT_NAS_CONFIGS.items():
            self._nas_configs[brand] = dict(defaults)
            if isinstance(raw_nas_configs, dict) and brand in raw_nas_configs and isinstance(raw_nas_configs[brand], dict):
                self._nas_configs[brand].update(raw_nas_configs[brand])

        self._nas_type = str(options.get(CONF_NAS_TYPE, data.get(CONF_NAS_TYPE, DEFAULT_NAS_TYPE)) or DEFAULT_NAS_TYPE).lower()
        if self._nas_type not in self._nas_configs:
            self._nas_configs[self._nas_type] = dict(DEFAULT_NAS_CONFIGS.get("asustor", {}))

        # Backward compatibility / fallback migration: if raw_nas_configs was empty or missing active brand, migrate from top-level options
        if not raw_nas_configs or self._nas_type not in raw_nas_configs:
            top_level_ftp_host = options.get("ftp_host", data.get("ftp_host", ""))
            if top_level_ftp_host:
                self._nas_configs[self._nas_type]["ftp_enabled"] = bool(options.get("ftp_enabled", data.get("ftp_enabled", True)))
                self._nas_configs[self._nas_type]["ftp_host"] = top_level_ftp_host
                self._nas_configs[self._nas_type]["ftp_port"] = int(options.get("ftp_port", data.get("ftp_port", 21)) or 21)
                self._nas_configs[self._nas_type]["ftp_user"] = str(options.get("ftp_user", data.get("ftp_user", "")) or "")
                self._nas_configs[self._nas_type]["ftp_pass"] = str(options.get("ftp_pass", data.get("ftp_pass", "")) or "")
                self._nas_configs[self._nas_type]["ftp_path"] = str(options.get("ftp_path", data.get("ftp_path", "/")) or "/")
            top_level_webdav_url = options.get("webdav_url", data.get("webdav_url", ""))
            if top_level_webdav_url:
                self._nas_configs[self._nas_type]["webdav_enabled"] = bool(options.get("webdav_enabled", data.get("webdav_enabled", True)))
                self._nas_configs[self._nas_type]["webdav_url"] = top_level_webdav_url
                self._nas_configs[self._nas_type]["webdav_user"] = str(options.get("webdav_user", data.get("webdav_user", "")) or "")
                self._nas_configs[self._nas_type]["webdav_pass"] = str(options.get("webdav_pass", data.get("webdav_pass", "")) or "")
                self._nas_configs[self._nas_type]["webdav_path"] = str(options.get("webdav_path", data.get("webdav_path", DEFAULT_WEBDAV_PATH)) or DEFAULT_WEBDAV_PATH)

        active_nas_cfg = self._nas_configs.get(self._nas_type, self._nas_configs["asustor"])
        self._ftp_enabled = bool(active_nas_cfg.get("ftp_enabled", False))
        self._ftp_host = str(active_nas_cfg.get("ftp_host", "") or "").strip()
        self._ftp_port = int(active_nas_cfg.get("ftp_port", 21) or 21)
        self._ftp_user = str(active_nas_cfg.get("ftp_user", "") or "").strip()
        self._ftp_pass = str(active_nas_cfg.get("ftp_pass", "") or "").strip()
        self._ftp_path = str(active_nas_cfg.get("ftp_path", "/") or "/").strip()
        self._ftp_status = "Connecté" if (self._ftp_enabled and self._ftp_host) else "Désactivé"

        self._webdav_enabled = bool(active_nas_cfg.get("webdav_enabled", False))
        self._webdav_url = str(active_nas_cfg.get("webdav_url", "") or "").strip()
        self._webdav_user = str(active_nas_cfg.get("webdav_user", "") or "").strip()
        self._webdav_pass = str(active_nas_cfg.get("webdav_pass", "") or "").strip()
        self._webdav_path = str(active_nas_cfg.get("webdav_path", DEFAULT_WEBDAV_PATH) or DEFAULT_WEBDAV_PATH).strip().strip("/")
        self._webdav_status = "Connecté" if (self._webdav_enabled and self._webdav_url) else "Désactivé"
        self._google_drive_enabled = bool(options.get(CONF_GOOGLE_DRIVE_ENABLED, data.get(CONF_GOOGLE_DRIVE_ENABLED, DEFAULT_GOOGLE_DRIVE_ENABLED)))
        self._google_drive_method = str(options.get(CONF_GOOGLE_DRIVE_METHOD, data.get(CONF_GOOGLE_DRIVE_METHOD, DEFAULT_GOOGLE_DRIVE_METHOD)) or DEFAULT_GOOGLE_DRIVE_METHOD).lower()
        self._google_drive_webhook_url = str(options.get(CONF_GOOGLE_DRIVE_WEBHOOK_URL, data.get(CONF_GOOGLE_DRIVE_WEBHOOK_URL, "")) or "").strip()
        self._google_drive_client_id = str(options.get(CONF_GOOGLE_DRIVE_CLIENT_ID, data.get(CONF_GOOGLE_DRIVE_CLIENT_ID, "")) or "").strip()
        self._google_drive_client_secret = str(options.get(CONF_GOOGLE_DRIVE_CLIENT_SECRET, data.get(CONF_GOOGLE_DRIVE_CLIENT_SECRET, "")) or "").strip()
        self._google_drive_refresh_token = str(options.get(CONF_GOOGLE_DRIVE_REFRESH_TOKEN, data.get(CONF_GOOGLE_DRIVE_REFRESH_TOKEN, "")) or "").strip()
        self._google_drive_folder_id = str(options.get(CONF_GOOGLE_DRIVE_FOLDER_ID, data.get(CONF_GOOGLE_DRIVE_FOLDER_ID, "")) or "").strip()
        
        has_gdrive = (self._google_drive_method == "webhook" and self._google_drive_webhook_url) or (self._google_drive_method == "oauth" and self._google_drive_refresh_token)
        self._google_drive_status = "Connecté" if (self._google_drive_enabled and has_gdrive) else "Désactivé"

        self._media_retention_days = int(options.get(CONF_MEDIA_RETENTION_DAYS, data.get(CONF_MEDIA_RETENTION_DAYS, DEFAULT_MEDIA_RETENTION_DAYS)) or 0)
        self._media_max_size_mb = int(options.get(CONF_MEDIA_MAX_SIZE_MB, data.get(CONF_MEDIA_MAX_SIZE_MB, DEFAULT_MEDIA_MAX_SIZE_MB)) or 0)
        
        # Migration & Loading of iCloud devices
        icloud_devs = options.get("icloud_devices", data.get("icloud_devices", []))
        self._icloud_devices = icloud_devs if isinstance(icloud_devs, list) else []

        # Pre-compute entity zones map (only changes on config reload)
        self._entity_zones_cache = self._get_entity_zones_map()
        # Initialize media files cache
        self._media_files_cache = []
        self._media_files_cache_ts = 0

    @callback
    def async_update_options(self):
        """Reload config when options change (called from __init__.py listener)."""
        self._load_config()
        self.async_write_ha_state()

    # ─── Properties ───────────────────────────────────────────────

    @callback
    def async_write_ha_state(self):
        """Write state to HA and push to MQTT if enabled."""
        super().async_write_ha_state()
        if hasattr(self, "_mqtt_enabled") and self._mqtt_enabled and "mqtt" in self.hass.config.components:
            from homeassistant.components import mqtt
            state_str = self.state if hasattr(self, "state") and self.state else "unknown"
            self.hass.async_create_task(
                mqtt.async_publish(self.hass, f"{self._mqtt_topic_base}/state", state_str, retain=True)
            )
            
            # Also publish attributes
            if hasattr(self, "state_attributes") and self.state_attributes:
                import json
                self.hass.async_create_task(
                    mqtt.async_publish(self.hass, f"{self._mqtt_topic_base}/attributes", json.dumps(self.state_attributes), retain=True)
                )

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
        # Use cached media files (30s TTL) to avoid repeated disk I/O
        now_ts = self.hass.loop.time()
        if not hasattr(self, '_media_files_cache') or (now_ts - getattr(self, '_media_files_cache_ts', 0)) > 30:
            self._media_files_cache = self._list_media_files()
            self._media_files_cache_ts = now_ts

        return {
            "domolink_alarm": True,
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
            "system_events": list(self._system_events),
            "sensor_health": self._sensor_health,
            "telegram_status": self._telegram_status,
            "ftp_status": self._ftp_status,
            "cameras_armed": self._cameras_armed,
            "cameras_arm_entities": self._cameras_arm_entities,
            "media_path": self._media_path,
            "media_files": self._media_files_cache,
            "zone_labels": self._zone_labels,
            "global_cameras": self._global_cameras,
            "entity_zones": self._entity_zones_cache,
            "disarm_cooldown": self._disarm_cooldown_task is not None,
            "camera_test_running": getattr(self, "_is_testing_cameras", False),
            "camera_test_info": dict(getattr(self, "_camera_test_info", {})),
            "ftp_host": getattr(self, "_ftp_host", ""),
            "ftp_test_running": getattr(self, "_ftp_test_running", False),
            "ftp_test_logs": list(getattr(self, "_ftp_test_logs", [])),
            "ftp_test_result": dict(getattr(self, "_ftp_test_result", {})),
            "webdav_status": getattr(self, "_webdav_status", "Désactivé"),
            "webdav_url": getattr(self, "_webdav_url", ""),
            "webdav_path": getattr(self, "_webdav_path", ""),
            "webdav_test_running": getattr(self, "_webdav_test_running", False),
            "webdav_test_logs": list(getattr(self, "_webdav_test_logs", [])),
            "webdav_test_result": dict(getattr(self, "_webdav_test_result", {})),
            "nas_type": getattr(self, "_nas_type", "asustor"),
            "nas_configs": dict(getattr(self, "_nas_configs", {})),
            "nas_test_results": dict(getattr(self, "_nas_test_results", {})),
            "google_drive_status": getattr(self, "_google_drive_status", "Désactivé"),
            "google_drive_method": getattr(self, "_google_drive_method", "webhook"),
            "google_drive_test_running": getattr(self, "_google_drive_test_running", False),
            "google_drive_test_logs": list(getattr(self, "_google_drive_test_logs", [])),
            "google_drive_test_result": dict(getattr(self, "_google_drive_test_result", {})),
            "media_storage_bytes": self._media_storage_stats.get("bytes", 0),
            "media_storage_mb": self._media_storage_stats.get("mb", 0.0),
            "media_storage_max_mb": self._media_max_size_mb,
            "media_storage_retention_days": self._media_retention_days,
            "media_storage_count": self._media_storage_stats.get("count", 0),
            "media_storage_percent": self._media_storage_stats.get("percent", 0.0),
            "installed_config": self._get_installed_config(),
        }

    def _get_installed_config(self):
        """Return the complete dictionary of current configuration settings."""
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
            CONF_FREE_MOBILE_PASS: str(_val(CONF_FREE_MOBILE_PASS, "") or ""),
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
            CONF_USERS_CODES: str(_val(CONF_USERS_CODES, "") or ""),
            CONF_DURESS_CODE: str(_val(CONF_DURESS_CODE, "") or ""),
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
            CONF_TELEGRAM_TOKEN: str(_val(CONF_TELEGRAM_TOKEN, "") or ""),
            CONF_TELEGRAM_CHAT_ID: str(_val(CONF_TELEGRAM_CHAT_ID, "") or ""),
            CONF_FTP_ENABLED: bool(_val(CONF_FTP_ENABLED, DEFAULT_FTP_ENABLED)),
            CONF_FTP_HOST: str(_val(CONF_FTP_HOST, "") or ""),
            CONF_FTP_PORT: int(_val(CONF_FTP_PORT, DEFAULT_FTP_PORT) or DEFAULT_FTP_PORT),
            CONF_FTP_USER: str(_val(CONF_FTP_USER, "") or ""),
            CONF_FTP_PASS: str(_val(CONF_FTP_PASS, "") or ""),
            CONF_FTP_PATH: str(_val(CONF_FTP_PATH, DEFAULT_FTP_PATH) or DEFAULT_FTP_PATH),
            CONF_WEBDAV_ENABLED: bool(_val(CONF_WEBDAV_ENABLED, DEFAULT_WEBDAV_ENABLED)),
            CONF_WEBDAV_URL: str(_val(CONF_WEBDAV_URL, "") or ""),
            CONF_WEBDAV_USER: str(_val(CONF_WEBDAV_USER, "") or ""),
            CONF_WEBDAV_PASS: str(_val(CONF_WEBDAV_PASS, "") or ""),
            CONF_WEBDAV_PATH: str(_val(CONF_WEBDAV_PATH, DEFAULT_WEBDAV_PATH) or DEFAULT_WEBDAV_PATH),
            CONF_NAS_TYPE: str(_val(CONF_NAS_TYPE, DEFAULT_NAS_TYPE) or DEFAULT_NAS_TYPE),
            CONF_NAS_CONFIGS: dict(_val(CONF_NAS_CONFIGS, getattr(self, "_nas_configs", DEFAULT_NAS_CONFIGS)) or getattr(self, "_nas_configs", DEFAULT_NAS_CONFIGS)),
            CONF_GOOGLE_DRIVE_ENABLED: bool(_val(CONF_GOOGLE_DRIVE_ENABLED, DEFAULT_GOOGLE_DRIVE_ENABLED)),
            CONF_GOOGLE_DRIVE_METHOD: str(_val(CONF_GOOGLE_DRIVE_METHOD, DEFAULT_GOOGLE_DRIVE_METHOD) or DEFAULT_GOOGLE_DRIVE_METHOD),
            CONF_GOOGLE_DRIVE_WEBHOOK_URL: str(_val(CONF_GOOGLE_DRIVE_WEBHOOK_URL, "") or ""),
            CONF_GOOGLE_DRIVE_CLIENT_ID: str(_val(CONF_GOOGLE_DRIVE_CLIENT_ID, "") or ""),
            CONF_GOOGLE_DRIVE_CLIENT_SECRET: str(_val(CONF_GOOGLE_DRIVE_CLIENT_SECRET, "") or ""),
            CONF_GOOGLE_DRIVE_REFRESH_TOKEN: str(_val(CONF_GOOGLE_DRIVE_REFRESH_TOKEN, "") or ""),
            CONF_GOOGLE_DRIVE_FOLDER_ID: str(_val(CONF_GOOGLE_DRIVE_FOLDER_ID, "") or ""),
            CONF_MEDIA_PATH: str(_val(CONF_MEDIA_PATH, DEFAULT_MEDIA_PATH) or DEFAULT_MEDIA_PATH),
            CONF_MEDIA_RETENTION_DAYS: int(_val(CONF_MEDIA_RETENTION_DAYS, DEFAULT_MEDIA_RETENTION_DAYS) or DEFAULT_MEDIA_RETENTION_DAYS),
            CONF_MEDIA_MAX_SIZE_MB: int(_val(CONF_MEDIA_MAX_SIZE_MB, DEFAULT_MEDIA_MAX_SIZE_MB) or DEFAULT_MEDIA_MAX_SIZE_MB),
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

    def _get_french_time(self):
        """Retourne la date et l'heure formatée en français."""
        now_dt = dt_now()
        months = ["Janvier", "Février", "Mars", "Avril", "Mai", "Juin", "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"]
        return f"{now_dt.day} {months[now_dt.month-1]} {now_dt.year} à {now_dt.strftime('%Hh%M')}"

    def _log_event(self, message):
        """Log an event and notify sensor."""
        event_item = {"time": utcnow().isoformat(), "message": message}
        self._system_events.insert(0, event_item)
        if len(self._system_events) > 50:
            self._system_events = self._system_events[:50]
        if self._event_sensor:
            self._event_sensor.async_add_event(utcnow().isoformat(), message)
        try:
            self.async_write_ha_state()
        except Exception as err:
            _LOGGER.debug("Domolink: Échec async_write_ha_state dans _log_event: %s", err)
        if hasattr(self, "_mqtt_enabled") and self._mqtt_enabled and "mqtt" in self.hass.config.components:
            from homeassistant.components import mqtt
            import json
            self.hass.async_create_task(
                mqtt.async_publish(self.hass, f"{self._mqtt_topic_base}/event", json.dumps({"time": utcnow().isoformat(), "message": message}), retain=False)
            )

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
                self._system_events = last_state.attributes.get("system_events", [])

        # Create media storage directory
        try:
            media_abs = self.hass.config.path(f"www/{self._media_path}")
            if not os.path.exists(media_abs):
                os.makedirs(media_abs, exist_ok=True)
                _LOGGER.info("Domolink: Répertoire médias créé: %s", media_abs)
            await self.hass.async_add_executor_job(self._purge_old_media_files)
        except Exception as e:
            _LOGGER.error("Domolink: Impossible d'initialiser le stockage médias: %s", e)


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

        # MQTT Command Subscription
        if getattr(self, "_mqtt_enabled", False) and "mqtt" in self.hass.config.components:
            from homeassistant.components import mqtt
            
            async def _mqtt_message_received(msg):
                """Handle incoming MQTT command."""
                payload = str(msg.payload).strip()
                _LOGGER.info("Domolink: Commande MQTT reçue sur %s : %s", msg.topic, payload)
                
                action = payload
                code = None
                
                if payload.startswith("{") and payload.endswith("}"):
                    try:
                        import json
                        data = json.loads(payload)
                        action = data.get("action", "")
                        code = data.get("code")
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
                else:
                    _LOGGER.warning("Domolink: Commande MQTT inconnue: %s", payload)

            self.async_on_remove(
                await mqtt.async_subscribe(
                    self.hass, f"{self._mqtt_topic_base}/set", _mqtt_message_received
                )
            )

        # Health check periodic task + initial startup check
        if self._health_check:
            self.async_on_remove(
                async_track_time_interval(
                    self.hass, self._async_perform_health_check, timedelta(hours=4)
                )
            )
            self.async_on_remove(
                async_call_later(self.hass, 15, self._async_perform_health_check)
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

        # Time-based Auto-Arming (safe format parsing)
        if getattr(self, "_schedule_enabled", False):
            from homeassistant.helpers.event import async_track_time_change
            try:
                arm_parts = [int(p) for p in str(self._schedule_arm_time).replace("h", ":").replace("H", ":").split(":") if p.strip().isdigit()]
                disarm_parts = [int(p) for p in str(self._schedule_disarm_time).replace("h", ":").replace("H", ":").split(":") if p.strip().isdigit()]
                if len(arm_parts) >= 2:
                    self.async_on_remove(
                        async_track_time_change(
                            self.hass,
                            self._cb_schedule_arm,
                            hour=arm_parts[0],
                            minute=arm_parts[1],
                            second=0
                        )
                    )
                if len(disarm_parts) >= 2:
                    self.async_on_remove(
                        async_track_time_change(
                            self.hass,
                            self._cb_schedule_disarm,
                            hour=disarm_parts[0],
                            minute=disarm_parts[1],
                            second=0
                        )
                    )
            except Exception as e:
                _LOGGER.error("Domolink: Erreur configuration planification horaire: %s", e)

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
            self._record_arm_event("disarm", self._last_user)
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

        # Cloud backup health check
        if getattr(self, "_telegram_enabled", False) and self._telegram_token:
            try:
                from homeassistant.helpers.aiohttp_client import async_get_clientsession
                session = async_get_clientsession(self.hass)
                async with session.get(f"https://api.telegram.org/bot{self._telegram_token}/getMe", timeout=5) as resp:
                    if resp.status == 200:
                        self._telegram_status = "Connecté"
                    else:
                        self._telegram_status = "Erreur"
            except Exception:
                self._telegram_status = "Hors ligne"
        else:
            self._telegram_status = "Désactivé"

        if getattr(self, "_ftp_enabled", False) and self._ftp_host:
            def check_ftp():
                import ftplib
                try:
                    with ftplib.FTP() as ftp:
                        ftp.encoding = "utf-8"
                        ftp.connect(self._ftp_host, int(self._ftp_port), timeout=10)
                        ftp.login(str(self._ftp_user or ""), str(self._ftp_pass or ""))
                        # Ensure domolink/alarm exists
                        for base_folder in ["domolink", "alarm"]:
                            try:
                                ftp.cwd(base_folder)
                            except Exception:
                                try:
                                    ftp.mkd(base_folder)
                                    ftp.cwd(base_folder)
                                except Exception:
                                    pass
                        ftp.quit()
                    return "Connecté"
                except Exception as e:
                    _LOGGER.debug("Domolink FTP health check error: %s", e)
                    return "Erreur"
            self._ftp_status = await self.hass.async_add_executor_job(check_ftp)
        else:
            self._ftp_status = "Désactivé"

        self._sensor_health = health_data
        self.async_write_ha_state()

        if warnings:
            self._log_event(f"Diagnostic : {len(warnings)} alerte(s) équipement(s)")
            notify_msg = "🔋 Diagnostic Domolink :\n" + "\n".join(warnings)
            await self._async_send_notification(notify_msg)

    # ─── Notifications ────────────────────────────────────────────

    async def _async_send_notification(self, message, is_alert=False, custom_data=None, is_emergency=False):
        """Send notifications to configured services/entities with universal compatibility."""
        sent_targets = []
        
        # ─── NATIVE FREE MOBILE SMS BACKUP ─────────────────────────────────────
        if hasattr(self, "_free_mobile_user") and self._free_mobile_user and self._free_mobile_pass:
            # We send native SMS for alerts and emergencies, or if explicitly requested.
            if is_alert or is_emergency or ("Désarmement" in message or "Armement" in message):
                try:
                    import urllib.parse
                    from homeassistant.helpers.aiohttp_client import async_get_clientsession
                    
                    # Clean emojis that crash the Free API
                    safe_msg = message.replace("🚨", "").replace("🟢", "").replace("🔴", "").replace("🟠", "").replace("🛡️", "").replace("⚠️", "")
                    safe_msg = f"Domolink: {safe_msg.strip()}"
                    encoded_msg = urllib.parse.quote(safe_msg)
                    url = f"https://smsapi.free-mobile.fr/sendmsg?user={self._free_mobile_user}&pass={self._free_mobile_pass}&msg={encoded_msg}"
                    
                    session = async_get_clientsession(self.hass)
                    
                    async def _send_sms_task():
                        try:
                            async with session.get(url) as response:
                                if response.status == 200:
                                    _LOGGER.info("Domolink: SMS natif Free Mobile envoyé avec succès")
                                    self._log_event("SMS d'alerte envoyé via Free Mobile")
                                else:
                                    _LOGGER.error("Domolink: Erreur API Free Mobile (%s)", response.status)
                        except Exception as e:
                            _LOGGER.error("Domolink: Exception lors de l'envoi SMS Free Mobile: %s", e)
                    
                    self.hass.async_create_task(_send_sms_task())
                except Exception as e:
                    _LOGGER.error("Domolink: Impossible de préparer le SMS natif: %s", e)
        # ───────────────────────────────────────────────────────────────────────

        # ─── NATIVE APPLE ICLOUD FIND MY ALERT ─────────────────────────────────
        if hasattr(self, "_icloud_devices") and self._icloud_devices:
            from homeassistant.helpers import device_registry as dr
            dev_reg = dr.async_get(self.hass)
            for device_id in self._icloud_devices:
                try:
                    device_entry = dev_reg.async_get(device_id)
                    if not device_entry:
                        continue
                    
                    # iCloud integration creates devices using the exact Apple 'Find My' device name.
                    device_name = device_entry.name
                    if not device_name:
                        continue
                        
                    # Extract the account (Apple ID username) dynamically from the device's config entry
                    account = None
                    for entry_id in device_entry.config_entries:
                        config_entry = self.hass.config_entries.async_get_entry(entry_id)
                        if config_entry and config_entry.domain == "icloud":
                            account = config_entry.data.get("username")
                            break
                            
                    if not account:
                        continue

                    self.hass.async_create_task(
                        self.hass.services.async_call(
                            "icloud", "display_message",
                            {"account": account, "device_name": device_name, "message": message, "sound": is_alert or is_emergency}
                        )
                    )
                    if is_alert or is_emergency:
                        self.hass.async_create_task(
                            self.hass.services.async_call(
                                "icloud", "play_sound",
                                {"account": account, "device_name": device_name}
                            )
                        )
                        sent_targets.append(f"iCloud ({device_name})")
                except Exception as e:
                    _LOGGER.error("Domolink: Impossible de déclencher l'alerte iCloud: %s", e)
        # ───────────────────────────────────────────────────────────────────────

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
            if target.startswith("notify.") and self.hass.services.has_service("notify", "send_message"):
                try:
                    # Nettoyage des émojis pour Free Mobile (qui plante souvent sur les caractères spéciaux)
                    safe_message = message
                    if "free_mobile" in target or "sms" in target:
                        safe_message = message.replace("🚨", "").replace("🟢", "").replace("🔴", "").replace("🟠", "").replace("🛡️", "").replace("⚠️", "")
                        
                    payload = {"message": safe_message}
                    if data:
                        payload["data"] = data
                    
                    # Rétrocompatibilité maximale : entity_id dans payload ET target
                    payload["entity_id"] = target
                    await self.hass.services.async_call(
                        "notify", 
                        "send_message", 
                        service_data=payload,
                        target={"entity_id": target}
                    )
                    sent = True
                    sent_targets.append(target)
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
                        sent_targets.append(f"{domain}.{service}")
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
                        sent_targets.append(f"notify.mobile_app_{service}")
                        _LOGGER.debug("Domolink: Notification envoyée à notify.mobile_app_%s", service)
                    except Exception as e:
                        _LOGGER.error("Domolink: Échec d'envoi vers notify.mobile_app_%s: %s", service, e)

            if not sent:
                _LOGGER.warning("Domolink: Impossible de trouver un service de notification valide pour %s", target)
                
        if sent_targets:
            # Nettoyer un peu le message pour le log (enlever les sauts de ligne)
            clean_msg = message.replace("\n", " - ")
            self._log_event(f"Message envoyé à {', '.join(sent_targets)} : {clean_msg}")

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
            
        # Ignore attribute changes where the core state didn't actually change
        if old_state and old_state.state == new_state.state:
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

        # Track sensors during entry delay (PENDING)
        if self._state == AlarmControlPanelState.PENDING:
            if entity_id not in self._faults:
                self._faults.append(entity_id)
                self.async_write_ha_state()
                self._log_event(f"Capteur {new_state.name} ouvert pendant le délai d'entrée")
                from homeassistant.util.dt import now as dt_now
                self.hass.async_create_task(
                    self._async_send_notification(
                        f"⚠️ Détection pendant délai d'entrée : {new_state.name}\n({dt_now().strftime('%H:%M:%S')})",
                        is_alert=True
                    )
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
            # Purge expired entries to prevent memory leak
            cutoff = now_loop - (self._cross_zoning_window * 2)
            self._last_motion_detection = {k: v for k, v in self._last_motion_detection.items() if v >= cutoff}

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

        # Already triggered: if sirens stopped (or in 1-min cooldown), re-trigger full sequence; otherwise notify additional detection
        if self._state == AlarmControlPanelState.TRIGGERED:
            if self._siren_task is None:
                _LOGGER.info("Domolink: Nouveau déclenchement après arrêt sirène sur %s", entity_id)
                if self._disarm_cooldown_task:
                    self._disarm_cooldown_task()
                    self._disarm_cooldown_task = None
                await self._async_trigger_alarm(entity_id)
            else:
                if entity_id not in self._faults:
                    self._faults.append(entity_id)
                self.async_write_ha_state()
                                # Extend siren duration
                self._siren_task() # cancel old timer
                from homeassistant.helpers.event import async_call_later
                self._siren_task = async_call_later(
                    self.hass,
                    self._siren_duration,
                    self._cb_turn_off_siren,
                )
                self._log_event(f"Nouvelle détection: {new_state.name} (Sirène prolongée)")
                await self._async_send_notification(f"🚨 Nouvelle détection pendant l'alerte : {new_state.name}\n({dt_now().strftime('%H:%M:%S')})", is_alert=True)
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
                # SYSTEMATIC IMMEDIATE CAMERA CAPTURE
                if self._cameras:
                    self.hass.async_create_task(self._async_capture_cameras(entity_id))

                # Entry delay only for ARMED_AWAY
                if self._state == AlarmControlPanelState.ARMED_AWAY and self._entry_delay > 0 and not getattr(self, '_post_trigger_active', False):
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
                            self._cb_entry_delay_expired,
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
            played = False
            # Strategy 1: modern tts.speak
            if self.hass.services.has_service("tts", "speak"):
                tts_entities = [e for e in self.hass.states.async_entity_ids("tts")]
                if tts_entities:
                    try:
                        await self.hass.services.async_call(
                            "tts", "speak",
                            {"entity_id": tts_entities[0], "media_player_entity_id": player, "message": message}
                        )
                        played = True
                    except Exception:
                        pass
            # Strategy 2: google_translate_say
            if not played and self.hass.services.has_service("tts", "google_translate_say"):
                try:
                    await self.hass.services.async_call(
                        "tts", "google_translate_say",
                        {"entity_id": player, "message": message}
                    )
                    played = True
                except Exception:
                    pass
            # Strategy 3: cloud_say
            if not played and self.hass.services.has_service("tts", "cloud_say"):
                try:
                    await self.hass.services.async_call(
                        "tts", "cloud_say",
                        {"entity_id": player, "message": message}
                    )
                    played = True
                except Exception:
                    pass

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

    @callback
    def _cb_entry_delay_expired(self, now=None):
        """Callback when entry delay timer expires — triggers full alarm."""
        self._pending_task = None
        target = self._faults[0] if self._faults else self._last_triggered_by
        self.hass.async_create_task(self._async_trigger_alarm(target))

    async def _async_trigger_alarm(self, triggering_entity):
        """Trigger the alarm — full alert sequence, ultra-fast and non-blocking."""
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
        
        if triggering_entity in getattr(self, "_tamper_sensors", []):
            self._log_event(f"🚨 Sabotage DÉCLENCHÉ par {self._triggered_by}")
        else:
            self._log_event(f"🚨 Alarme DÉCLENCHÉE par {self._triggered_by}")
        name = state.name if state else triggering_entity

        # ─── 1. INSTANT SIRENS & PANIC LIGHTS (Priority #1: Immediate deterrent) ───
        should_siren = (
            self._pre_trigger_state == AlarmControlPanelState.ARMED_AWAY
            or triggering_entity in self._tamper_sensors
        )
        
        # ALWAYS schedule auto-rearm / siren turn off after siren_duration (even if 0 sirens)
        if self._siren_task:
            self._siren_task()
        self._siren_task = async_call_later(
            self.hass,
            self._siren_duration,
            self._cb_turn_off_siren,
        )
        
        if should_siren:
            if self._sirens:
                self._log_event("Activation des sirènes")
                try:
                    await self.hass.services.async_call(
                        "homeassistant", "turn_on",
                        {"entity_id": self._sirens},
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

        # ─── 2. INSTANT NOTIFICATIONS (Priority #2: Push, Free SMS, iCloud) ────
        french_time = self._get_french_time()
        alarm_name = self.name or "Domolink Alarm"
        self.hass.async_create_task(
            self._async_send_notification(
                f"🚨 INTRUSION DÉTECTÉE 🚨\n{name} a déclenché l'alarme {alarm_name} le {french_time}",
                is_alert=True,
            )
        )

        # ─── 3. TTS VOICE DISSUASION (Priority #3: Non-blocking background) ──────
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

        # ─── 4. NON-BLOCKING CAMERA SNAPSHOTS & RECORDINGS ────────────────────────
        if self._cameras:
            self.hass.async_create_task(self._async_capture_cameras(triggering_entity))

    def _update_media_storage_stats(self):
        """Update media storage usage statistics."""
        try:
            media_dir = self.hass.config.path(f"www/{self._media_path}")
            total_bytes = 0
            count = 0
            if os.path.exists(media_dir):
                for fname in os.listdir(media_dir):
                    if not fname.startswith('.') and fname.lower().endswith(('.jpg', '.jpeg', '.png', '.mp4', '.webm', '.ogg')):
                        fpath = os.path.join(media_dir, fname)
                        if os.path.isfile(fpath):
                            total_bytes += os.path.getsize(fpath)
                            count += 1
            mb = round(total_bytes / (1024 * 1024), 2)
            max_mb = self._media_max_size_mb if self._media_max_size_mb > 0 else 1024
            percent = round((mb / max_mb) * 100, 1) if max_mb > 0 else 0.0
            self._media_storage_stats = {
                "bytes": total_bytes,
                "mb": mb,
                "max_mb": self._media_max_size_mb,
                "retention_days": self._media_retention_days,
                "count": count,
                "percent": min(100.0, percent),
            }
        except Exception as e:
            _LOGGER.debug("Domolink: Erreur stats stockage: %s", e)

    def _purge_old_media_files(self) -> dict:
        """Purge media files exceeding retention days and max storage MB quota (FIFO)."""
        import time
        media_dir = self.hass.config.path(f"www/{self._media_path}")
        if not os.path.exists(media_dir):
            self._update_media_storage_stats()
            return {"deleted": 0, "freed_bytes": 0}

        deleted_count = 0
        freed_bytes = 0
        now_ts = time.time()
        retention_sec = (self._media_retention_days * 86400) if self._media_retention_days > 0 else 0
        max_bytes = (self._media_max_size_mb * 1024 * 1024) if self._media_max_size_mb > 0 else 0

        # Collect all valid alarm media files with stats
        all_files = []
        try:
            for fname in os.listdir(media_dir):
                if not fname.startswith('.') and fname.lower().endswith(('.jpg', '.jpeg', '.png', '.mp4', '.webm', '.ogg')):
                    fpath = os.path.join(media_dir, fname)
                    if os.path.isfile(fpath):
                        try:
                            st = os.stat(fpath)
                            all_files.append({
                                "path": fpath,
                                "name": fname,
                                "size": st.st_size,
                                "mtime": st.st_mtime,
                            })
                        except Exception:
                            pass
        except Exception as e:
            _LOGGER.error("Domolink: Erreur lors du scan pour purge: %s", e)
            return {"deleted": 0, "freed_bytes": 0}

        # 1. Purge by retention days (if configured)
        remaining_files = []
        if retention_sec > 0:
            for item in all_files:
                if (now_ts - item["mtime"]) > retention_sec:
                    try:
                        os.remove(item["path"])
                        deleted_count += 1
                        freed_bytes += item["size"]
                        _LOGGER.info("Domolink: Purge média expiré (> %d j): %s", self._media_retention_days, item["name"])
                    except Exception as err:
                        _LOGGER.debug("Domolink: Erreur suppression %s: %s", item["path"], err)
                else:
                    remaining_files.append(item)
        else:
            remaining_files = all_files

        # 2. Purge by quota MB (FIFO - delete oldest until below 90% quota)
        if max_bytes > 0:
            total_remaining_bytes = sum(f["size"] for f in remaining_files)
            target_bytes = int(max_bytes * 0.90)  # Aim for 90% of quota
            if total_remaining_bytes > max_bytes:
                # Sort oldest first (FIFO)
                remaining_files.sort(key=lambda x: x["mtime"])
                for item in remaining_files:
                    if total_remaining_bytes <= target_bytes:
                        break
                    try:
                        os.remove(item["path"])
                        deleted_count += 1
                        freed_bytes += item["size"]
                        total_remaining_bytes -= item["size"]
                        _LOGGER.info("Domolink: Purge quota FIFO: %s", item["name"])
                    except Exception as err:
                        _LOGGER.debug("Domolink: Erreur suppression FIFO %s: %s", item["path"], err)

        # Invalidate media cache and update storage stats
        self._media_files_cache_ts = 0
        self._update_media_storage_stats()
        
        if deleted_count > 0:
            freed_mb = round(freed_bytes / (1024 * 1024), 1)
            self._log_event(f"🧹 Purge médias : {deleted_count} fichier(s) supprimé(s) ({freed_mb} Mo libérés)")

        return {"deleted": deleted_count, "freed_bytes": freed_bytes}

    async def async_clean_media(self, call=None):
        """Service handler to clean / purge old media files on demand."""
        result = await self.hass.async_add_executor_job(self._purge_old_media_files)
        self.async_write_ha_state()
        return result

    def _list_media_files(self):
        """List all media files in the configured media directory (for the JS gallery)."""
        try:
            media_dir = self.hass.config.path(f"www/{self._media_path}")
            if not os.path.exists(media_dir):
                self._update_media_storage_stats()
                return []
            files = []
            for fname in sorted(os.listdir(media_dir), reverse=True):
                if not fname.startswith('.'):
                    fpath = os.path.join(media_dir, fname)
                    if os.path.isfile(fpath) and fname.lower().endswith(('.jpg', '.jpeg', '.png', '.mp4', '.webm', '.ogg')):
                        files.append({
                            "name": fname,
                            "size": os.path.getsize(fpath),
                            "modified": os.path.getmtime(fpath),
                        })
            self._update_media_storage_stats()
            return files[:200]  # Cap at 200 to avoid huge HA state
        except Exception as e:
            _LOGGER.debug("Domolink: Erreur lecture médias: %s", e)
            return []

    def _get_media_filenames(self, camera_entity: str):
        """Construct media filenames: [nom de la caméra] - [Année] - [jour] - [heure du déclenchement]."""
        st = self.hass.states.get(camera_entity)
        cam_name = (st.attributes.get("friendly_name") if st else None) or camera_entity
        if cam_name.startswith("camera."):
            cam_name = cam_name[7:]
        safe_cam = re.sub(r'[\\/*?:"<>|]', '-', cam_name).strip()
        safe_cam = re.sub(r'\s+', ' ', safe_cam)
        if not safe_cam:
            safe_cam = "Camera"

        now = dt_now()
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%Hh%Mm%Ss")
        base_name = f"{safe_cam} - {date_str} - {time_str}"
        return f"{base_name}.jpg", f"{base_name}.mp4"

    async def _async_watch_and_fix_video(self, expected_mp4_path, duration=30, timeout=90):
        """Watch for .mp4.tmp files written by HA and ensure valid finalized .mp4."""
        # Wait for the recording duration to finish before inspecting or touching files
        # camera.record takes `duration` seconds + a few seconds for ffmpeg to write moov atom
        await asyncio.sleep(duration + 4)

        tmp_path = expected_mp4_path + ".tmp"
        alt_tmp = expected_mp4_path.replace(".mp4", ".mp4.tmp")
        
        remaining = max(10, timeout - duration - 4)
        for _ in range(int(remaining * 2)):  # check every 0.5s
            # If .mp4 already exists and is finalized, we're done
            if os.path.exists(expected_mp4_path) and os.path.getsize(expected_mp4_path) > 10240:
                self._media_files_cache_ts = 0
                _LOGGER.debug("Domolink: Video OK: %s", expected_mp4_path)
                if getattr(self, "_ftp_enabled", False):
                    self.hass.async_create_task(self._async_upload_to_ftp(expected_mp4_path))
                if getattr(self, "_webdav_enabled", False):
                    self.hass.async_create_task(self._async_upload_to_webdav(expected_mp4_path))
                if getattr(self, "_google_drive_enabled", False):
                    self.hass.async_create_task(self._async_upload_to_google_drive(expected_mp4_path))
                return
            # If HA left a .tmp file after recording finished, check stability and rename
            for tmp in (tmp_path, alt_tmp):
                if os.path.exists(tmp):
                    try:
                        size1 = os.path.getsize(tmp)
                        await asyncio.sleep(2.5)
                        size2 = os.path.getsize(tmp)
                        if size1 == size2 and size1 > 10240:
                            os.rename(tmp, expected_mp4_path)
                            self._media_files_cache_ts = 0
                            _LOGGER.info("Domolink: .mp4.tmp finalisé en .mp4: %s", expected_mp4_path)
                            self._log_event(f"Vidéo sauvegardée: {os.path.basename(expected_mp4_path)}")
                            if getattr(self, "_ftp_enabled", False):
                                self.hass.async_create_task(self._async_upload_to_ftp(expected_mp4_path))
                            if getattr(self, "_webdav_enabled", False):
                                self.hass.async_create_task(self._async_upload_to_webdav(expected_mp4_path))
                            if getattr(self, "_google_drive_enabled", False):
                                self.hass.async_create_task(self._async_upload_to_google_drive(expected_mp4_path))
                            return
                    except Exception as e:
                        _LOGGER.debug("Domolink: Erreur finalisation tmp: %s", e)
            await asyncio.sleep(0.5)
        _LOGGER.warning("Domolink: Timeout attente vidéo: %s", expected_mp4_path)

    async def async_media_action(self, call):
        """Handle rename or delete of media files."""
        action = str(call.data.get("action", "")).lower()
        filename = str(call.data.get("filename", "")).strip()
        new_name = str(call.data.get("new_name", "")).strip()
        
        # Security: reject path traversal
        if ".." in filename or "/" in filename or "\\" in filename:
            _LOGGER.error("Domolink: Tentative d'accès hors-répertoire bloquée: %s", filename)
            raise HomeAssistantError("Accès refusé: nom de fichier invalide.")
        
        media_dir = self.hass.config.path(f"www/{self._media_path}")
        file_path = os.path.join(media_dir, filename)
        
        if not os.path.exists(file_path):
            raise HomeAssistantError(f"Fichier introuvable: {filename}")
        
        if action == "delete":
            try:
                os.remove(file_path)
                self._media_files_cache_ts = 0  # Invalidate cache
                self._update_media_storage_stats()
                self._log_event(f"Média supprimé: {filename}")
                _LOGGER.info("Domolink: Fichier supprimé: %s", file_path)
                self.async_write_ha_state()
            except Exception as e:
                raise HomeAssistantError(f"Impossible de supprimer: {e}")
        
        elif action == "rename":
            if not new_name or ".." in new_name or "/" in new_name:
                raise HomeAssistantError("Nouveau nom invalide.")
            new_path = os.path.join(media_dir, new_name)
            try:
                os.rename(file_path, new_path)
                self._media_files_cache_ts = 0  # Invalidate cache
                self._update_media_storage_stats()
                self._log_event(f"Média renommé: {filename} → {new_name}")
                _LOGGER.info("Domolink: Fichier renommé: %s → %s", file_path, new_path)
                self.async_write_ha_state()
            except Exception as e:
                raise HomeAssistantError(f"Impossible de renommer: {e}")
        else:
            raise HomeAssistantError(f"Action inconnue: {action}")

    async def async_test_cameras_recording(self, call=None):
        """Trigger sequential test of all cameras: photo + 30s video one by one."""
        if getattr(self, "_is_testing_cameras", False):
            _LOGGER.warning("Domolink: Un test d'enregistrement caméra est déjà en cours.")
            return

        if not self._cameras:
            self._log_event("Test vidéo impossible : Aucune caméra configurée.")
            return

        self.hass.async_create_task(self._async_run_cameras_test())

    async def _async_run_cameras_test(self):
        """Run sequential snapshot and 30s video recording for each camera."""
        import shutil
        import time

        self._is_testing_cameras = True
        total_cams = len(self._cameras)
        media_dir = self.hass.config.path(f"www/{self._media_path}")
        try:
            os.makedirs(media_dir, exist_ok=True)
        except Exception as e:
            _LOGGER.error("Domolink: Impossible de créer le répertoire média %s: %s", media_dir, e)

        self._log_event(f"🎬 Début du test d'enregistrement sur {total_cams} caméra(s)")

        try:
            for idx, camera in enumerate(self._cameras):
                st = self.hass.states.get(camera)
                cam_name = st.attributes.get("friendly_name", camera) if st else camera
                snapshot_filename, video_filename = self._get_media_filenames(camera)
                
                self._camera_test_info = {
                    "total": total_cams,
                    "current": idx + 1,
                    "camera_entity": camera,
                    "camera_name": cam_name,
                    "step": "photo",
                    "video_start": 0,
                    "video_duration": 34
                }
                self.async_write_ha_state()

                # Wake up camera
                try:
                    await self.hass.services.async_call("camera", "turn_on", {"entity_id": camera})
                except Exception:
                    pass

                # 1. Snapshot
                self._log_event(f"📸 Test ({idx+1}/{total_cams}) : Capture photo sur {cam_name}")
                snapshot_path = os.path.join(media_dir, snapshot_filename)

                try:
                    if camera.startswith("camera.aarlo"):
                        await asyncio.wait_for(
                            self.hass.services.async_call(
                                "aarlo", "camera_request_snapshot_to_file",
                                {"entity_id": camera, "filename": snapshot_path},
                                blocking=True,
                            ),
                            timeout=15.0,
                        )
                    else:
                        await asyncio.wait_for(
                            self.hass.services.async_call(
                                "camera", "snapshot",
                                {"entity_id": camera, "filename": snapshot_path},
                                blocking=True,
                            ),
                            timeout=15.0,
                        )

                    if os.path.exists(snapshot_path):
                        self._media_files_cache_ts = 0
                        alert_path = self.hass.config.path("www/domolink_alarm_alert.jpg")
                        try:
                            shutil.copy2(snapshot_path, alert_path)
                        except Exception:
                            pass
                        if getattr(self, "_ftp_enabled", False):
                            self.hass.async_create_task(self._async_upload_to_ftp(snapshot_path))
                        if getattr(self, "_webdav_enabled", False):
                            self.hass.async_create_task(self._async_upload_to_webdav(snapshot_path))
                        if getattr(self, "_google_drive_enabled", False):
                            self.hass.async_create_task(self._async_upload_to_google_drive(snapshot_path))
                    self._log_event(f"✅ Photo test enregistrée ({cam_name})")
                except asyncio.TimeoutError:
                    self._log_event(f"⚠️ Timeout photo (15s) sur {cam_name}")
                except Exception as e:
                    self._log_event(f"⚠️ Erreur photo sur {cam_name} : {e}")

                # 2. 30-second Video Recording
                self._camera_test_info = {
                    "total": total_cams,
                    "current": idx + 1,
                    "camera_entity": camera,
                    "camera_name": cam_name,
                    "step": "video",
                    "video_start": time.time(),
                    "video_duration": 34
                }
                self.async_write_ha_state()
                
                self._log_event(f"🎥 Test ({idx+1}/{total_cams}) : Enregistrement 30s sur {cam_name}...")
                record_path = os.path.join(media_dir, video_filename)

                try:
                    await self.hass.services.async_call(
                        "camera", "record",
                        {"entity_id": camera, "duration": 30, "filename": record_path},
                    )
                    # Wait for 30s recording duration + 4s finalization
                    await self._async_watch_and_fix_video(record_path, duration=30, timeout=60)
                    self._log_event(f"✅ Vidéo 30s test enregistrée ({cam_name})")
                except Exception as e:
                    self._log_event(f"⚠️ Erreur vidéo sur {cam_name} : {e}")

                await asyncio.sleep(1.0)

            self._log_event("🎉 Test d'enregistrement terminé pour toutes les caméras ! Rendez-vous dans la Médiathèque.")
            try:
                await self._async_send_notification(
                    "🎬 Test caméras terminé avec succès. Les photos et vidéos sont disponibles dans la Médiathèque.",
                    is_alert=False,
                )
            except Exception:
                pass
        finally:
            self._is_testing_cameras = False
            self._camera_test_info = {}
            self.async_write_ha_state()

    async def _async_sync_cameras(self, arm: bool):
        """Sync camera motion detection or alarm panels."""
        if not self._cameras_arm_entities:
            self._cameras_armed = False
            return
            
        for entity_id in self._cameras_arm_entities:
            domain = entity_id.split('.')[0]
            try:
                if arm:
                    if domain == "switch":
                        await self.hass.services.async_call("switch", "turn_on", {"entity_id": entity_id}, blocking=False)
                    elif domain == "alarm_control_panel":
                        await self.hass.services.async_call("alarm_control_panel", "alarm_arm_away", {"entity_id": entity_id}, blocking=False)
                    elif domain == "camera":
                        await self.hass.services.async_call("camera", "turn_on", {"entity_id": entity_id}, blocking=False)
                else:
                    if domain == "switch":
                        await self.hass.services.async_call("switch", "turn_off", {"entity_id": entity_id}, blocking=False)
                    elif domain == "alarm_control_panel":
                        await self.hass.services.async_call("alarm_control_panel", "alarm_disarm", {"entity_id": entity_id}, blocking=False)
                    elif domain == "camera":
                        await self.hass.services.async_call("camera", "turn_off", {"entity_id": entity_id}, blocking=False)
            except Exception as e:
                _LOGGER.error("Domolink: Erreur synchronisation caméra %s: %s", entity_id, e)
                    
        self._cameras_armed = arm
        self.async_write_ha_state()

    async def _async_upload_to_telegram(self, file_path):
        """Send photo to Telegram asynchronously."""
        if not self._telegram_enabled or not self._telegram_token or not self._telegram_chat_id:
            return
        
        try:
            import aiohttp
            from homeassistant.helpers.aiohttp_client import async_get_clientsession

            def _read_file():
                with open(file_path, 'rb') as pf:
                    return pf.read()

            photo_bytes = await self.hass.async_add_executor_job(_read_file)
            session = async_get_clientsession(self.hass)
            data = aiohttp.FormData()
            data.add_field('chat_id', str(self._telegram_chat_id))
            data.add_field('photo', photo_bytes, filename=os.path.basename(file_path), content_type='image/jpeg')
            async with session.post(f"https://api.telegram.org/bot{self._telegram_token}/sendPhoto", data=data, timeout=10) as resp:
                if resp.status == 200:
                    _LOGGER.info("Domolink: Snapshot envoyé sur Telegram avec succès")
                    self._log_event("Sauvegarde photo Telegram réussie")
                    self._telegram_status = "Connecté"
                else:
                    _LOGGER.error("Domolink: Échec envoi Telegram - Code %s", resp.status)
                    self._telegram_status = "Erreur"
        except Exception as e:
            _LOGGER.error("Domolink: Erreur lors de l'envoi Telegram : %s", e)
            self._telegram_status = "Erreur"
        self.async_write_ha_state()

    def _upload_to_ftp_sync(self, file_path):
        """Upload photo or video to FTP in domolink/alarm/[custom_path]."""
        import ftplib
        try:
            with ftplib.FTP() as ftp:
                ftp.encoding = "utf-8"
                ftp.connect(self._ftp_host, int(self._ftp_port), timeout=25)
                ftp.login(str(self._ftp_user or ""), str(self._ftp_pass or ""))

                # 1. Ensure domolink/alarm directory structure exists on FTP
                for base_dir in ["domolink", "alarm"]:
                    try:
                        ftp.cwd(base_dir)
                    except Exception:
                        try:
                            ftp.mkd(base_dir)
                            ftp.cwd(base_dir)
                        except Exception as err:
                            _LOGGER.warning("Domolink FTP: Impossible de créer/accéder à '%s': %s", base_dir, err)

                # 2. If user configured a custom path in settings, append it inside domolink/alarm/
                custom_dir = str(self._ftp_path or "").strip()
                if custom_dir and custom_dir != "/":
                    parts = [p for p in custom_dir.split('/') if p and p not in ("domolink", "alarm")]
                    for part in parts:
                        try:
                            ftp.cwd(part)
                        except Exception:
                            try:
                                ftp.mkd(part)
                                ftp.cwd(part)
                            except Exception as mkd_err:
                                _LOGGER.warning("Domolink FTP: Impossible d'accéder au sous-dossier '%s': %s", part, mkd_err)

                filename = os.path.basename(file_path)
                with open(file_path, "rb") as f:
                    ftp.storbinary(f"STOR {filename}", f)
            return True
        except Exception as e:
            _LOGGER.error("Domolink: Erreur lors de l'envoi FTP de %s : %s", file_path, e)
            return False

    async def _async_upload_to_ftp(self, file_path):
        """Handle FTP upload in executor job."""
        if not self._ftp_enabled or not self._ftp_host:
            return

        is_video = file_path.lower().endswith(('.mp4', '.webm', '.ogg'))
        media_type = "vidéo" if is_video else "photo"
        filename = os.path.basename(file_path)

        success = await self.hass.async_add_executor_job(self._upload_to_ftp_sync, file_path)
        if success:
            _LOGGER.info("Domolink: %s envoyé(e) sur FTP avec succès: %s", media_type.capitalize(), filename)
            self._log_event(f"Sauvegarde {media_type} FTP réussie: {filename}")
            self._ftp_status = "Connecté"
        else:
            _LOGGER.error("Domolink: Échec sauvegarde %s sur FTP: %s", media_type, filename)
            self._log_event(f"⚠️ Échec transfert FTP {media_type}: {filename}")
            self._ftp_status = "Erreur"
        self.async_write_ha_state()

    def _append_ftp_log(self, message: str, level: str = "info"):
        """Append an entry to FTP test log and notify state change."""
        now_str = dt_now().strftime("%H:%M:%S")
        if not hasattr(self, "_ftp_test_logs") or self._ftp_test_logs is None:
            self._ftp_test_logs = []
        self._ftp_test_logs.append({
            "time": now_str,
            "message": message,
            "level": level,
        })
        if len(self._ftp_test_logs) > 60:
            self._ftp_test_logs = self._ftp_test_logs[-60:]
        try:
            self.async_write_ha_state()
        except Exception:
            pass

    async def async_test_ftp(self, call=None):
        """Force a connection test to the FTP server with real-time log steps."""
        if getattr(self, "_ftp_test_running", False):
            _LOGGER.debug("Domolink: Un test FTP est déjà en cours.")
            return {
                "success": False,
                "code": 429,
                "result_label": "Erreur 429",
                "message": "Un test FTP est déjà en cours.",
            }

        data = call.data if (call and hasattr(call, "data")) else {}
        return await self._async_run_ftp_test(data)

    async def _async_run_ftp_test(self, data=None):
        """Run FTP test in executor and report logs thread-safely."""
        if data is None:
            data = {}

        nas_labels = {
            "asustor": "ASUSTOR",
            "synology": "Synology",
            "qnap": "QNAP",
            "truenas": "TrueNAS",
            "freebox": "Freebox",
            "unraid": "Unraid",
            "generic": "Autre NAS",
        }
        cur_nas = data.get("nas_type") or getattr(self, "_nas_type", "asustor")
        nas_name = nas_labels.get(cur_nas, "NAS")

        self._ftp_test_running = True
        self._ftp_test_logs = []
        self._ftp_test_result = {}
        self._append_ftp_log(f"🚀 Démarrage du diagnostic de connexion FTP ({nas_name})...", "info")

        def log_step(msg, level="info"):
            _LOGGER.info("Domolink FTP test: %s", msg)
            self.hass.loop.call_soon_threadsafe(self._append_ftp_log, msg, level)

        nas_cfg = getattr(self, "_nas_configs", {}).get(cur_nas, {})
        is_cur_active = (cur_nas == getattr(self, "_nas_type", "asustor"))

        host = data.get("ftp_host") or nas_cfg.get("ftp_host") or (getattr(self, "_ftp_host", "") if is_cur_active else "")
        if not host and cur_nas == "freebox":
            host = "mafreebox.freebox.fr"
        port = data.get("ftp_port") or nas_cfg.get("ftp_port") or (getattr(self, "_ftp_port", 21) if is_cur_active else 21)
        user = data.get("ftp_user") if "ftp_user" in data else (nas_cfg.get("ftp_user") if "ftp_user" in nas_cfg else (getattr(self, "_ftp_user", "") if is_cur_active else ""))
        if not user and cur_nas == "freebox":
            user = "freebox"
        password = data.get("ftp_pass") if "ftp_pass" in data else (nas_cfg.get("ftp_pass") if "ftp_pass" in nas_cfg else (getattr(self, "_ftp_pass", "") if is_cur_active else ""))
        path = data.get("ftp_path") if "ftp_path" in data else (nas_cfg.get("ftp_path") if "ftp_path" in nas_cfg else (getattr(self, "_ftp_path", "/") if is_cur_active else "/"))

        def run_test_sync():
            import ftplib
            import time
            import io
            import re
            import socket

            time.sleep(0.2)
            if not host:
                log_step("Aucune adresse de serveur FTP renseignée.", "error")
                return False, 400, "Adresse du serveur FTP manquante.", ""

            try:
                port_int = int(port or 21)
            except (ValueError, TypeError):
                port_int = 21

            clean_host = str(host).strip()
            clean_user = str(user or "").strip()
            clean_pass = str(password or "")

            log_step(f"1. Profil {nas_name} : Hôte={clean_host}, Port={port_int}, Utilisateur='{clean_user}'", "info")
            time.sleep(0.25)

            log_step(f"2. Connexion réseau au serveur {clean_host}:{port_int}...", "info")
            ftp = ftplib.FTP()
            ftp.encoding = "utf-8"
            try:
                ftp.connect(clean_host, port_int, timeout=10)
                log_step("   ✓ Connexion TCP établie avec succès.", "success")
            except Exception as e:
                err_str = str(e)
                log_step(f"   ✗ Échec de connexion réseau : {err_str}", "error")
                try:
                    ftp.close()
                except Exception:
                    pass

                code = None
                if hasattr(e, "errno") and e.errno is not None:
                    code = abs(e.errno)
                elif isinstance(e, socket.gaierror):
                    code = getattr(e, "errno", None) or 2
                elif isinstance(e, (socket.timeout, TimeoutError)):
                    code = 110
                if code is None:
                    m = re.search(r'\[Errno\s*(-?\d+)\]', err_str)
                    if m:
                        code = abs(int(m.group(1)))
                    else:
                        m_rfc = re.search(r'\b([1-5]\d{2})\b', err_str)
                        code = int(m_rfc.group(1)) if m_rfc else 111

                return False, code, f"Impossible de joindre le serveur {clean_host}:{port_int} ({err_str})", ""

            time.sleep(0.25)
            log_step(f"3. Authentification de l'utilisateur '{clean_user}'...", "info")
            try:
                ftp.login(clean_user, clean_pass)
                log_step("   ✓ Authentification acceptée par le serveur FTP.", "success")
            except Exception as e:
                err_str = str(e)
                log_step(f"   ✗ Échec d'authentification : {err_str}", "error")
                try:
                    ftp.quit()
                except Exception:
                    pass

                code = None
                m_rfc = re.search(r'\b([1-5]\d{2})\b', err_str)
                if m_rfc:
                    code = int(m_rfc.group(1))
                elif hasattr(e, "errno") and e.errno is not None:
                    code = abs(e.errno)
                if code is None:
                    code = 530
                return False, code, f"Identifiants incorrects ou refusés ({err_str})", ""

            time.sleep(0.2)
            log_step("4. Contrôle de l'arborescence des répertoires...", "info")

            # Verify / create 'domolink'
            try:
                ftp.cwd("domolink")
                log_step("   ✓ Dossier 'domolink' accessible.", "success")
            except Exception:
                try:
                    ftp.mkd("domolink")
                    ftp.cwd("domolink")
                    log_step("   ✓ Dossier 'domolink' créé avec succès.", "success")
                except Exception as mkd_err:
                    err_str = str(mkd_err)
                    log_step(f"   ✗ Impossible d'accéder ou créer 'domolink' : {err_str}", "error")
                    try:
                        ftp.quit()
                    except Exception:
                        pass
                    m_rfc = re.search(r'\b([1-5]\d{2})\b', err_str)
                    code = int(m_rfc.group(1)) if m_rfc else 550
                    return False, code, f"Permissions insuffisantes pour créer 'domolink' ({err_str})", ""

            time.sleep(0.2)
            # Verify / create 'alarm'
            try:
                ftp.cwd("alarm")
                log_step("   ✓ Sous-dossier 'alarm' accessible.", "success")
            except Exception:
                try:
                    ftp.mkd("alarm")
                    ftp.cwd("alarm")
                    log_step("   ✓ Sous-dossier 'alarm' créé avec succès.", "success")
                except Exception as mkd_err:
                    err_str = str(mkd_err)
                    log_step(f"   ✗ Impossible d'accéder ou créer 'alarm' : {err_str}", "error")
                    try:
                        ftp.quit()
                    except Exception:
                        pass
                    m_rfc = re.search(r'\b([1-5]\d{2})\b', err_str)
                    code = int(m_rfc.group(1)) if m_rfc else 550
                    return False, code, f"Permissions insuffisantes pour créer 'alarm' ({err_str})", ""

            time.sleep(0.2)
            # Verify / create custom path if configured
            save_path = "domolink/alarm"
            custom_dir = str(path or "").strip()
            if custom_dir and custom_dir != "/":
                parts = [p for p in custom_dir.split('/') if p and p not in ("domolink", "alarm")]
                for part in parts:
                    try:
                        ftp.cwd(part)
                        log_step(f"   ✓ Sous-dossier personnalisé '{part}' accessible.", "info")
                    except Exception:
                        try:
                            ftp.mkd(part)
                            ftp.cwd(part)
                            log_step(f"   ✓ Sous-dossier personnalisé '{part}' créé.", "success")
                        except Exception as custom_err:
                            log_step(f"   ✗ Impossible d'accéder ou créer '{part}' : {custom_err}", "warning")
                if parts:
                    save_path = f"domolink/alarm/{'/'.join(parts)}"

            time.sleep(0.2)
            log_step("5. Test des permissions d'écriture...", "info")
            try:
                probe_data = io.BytesIO(b"Domolink Alarm write probe test")
                ftp.storbinary("STOR .domolink_test_probe", probe_data)
                try:
                    ftp.delete(".domolink_test_probe")
                except Exception:
                    pass
                log_step("   ✓ Droits d'écriture validés (fichier test créé et nettoyé).", "success")
            except Exception as write_err:
                err_str = str(write_err)
                log_step(f"   ✗ Erreur d'écriture sur le serveur : {err_str}", "error")
                try:
                    ftp.quit()
                except Exception:
                    pass
                m_rfc = re.search(r'\b([1-5]\d{2})\b', err_str)
                code = int(m_rfc.group(1)) if m_rfc else 553
                return False, code, f"Droits d'écriture insuffisants ({err_str})", save_path

            time.sleep(0.2)
            try:
                ftp.quit()
            except Exception:
                pass

            log_step(f"6. Chemin de sauvegarde validé : {save_path}", "success")
            log_step(f"🎉 Connexion FTP acceptée et validée avec succès sur {nas_name} !", "success")
            return True, 200, "Connexion acceptée", save_path

        import time as _t
        try:
            success, code, msg, save_path = await self.hass.async_add_executor_job(run_test_sync)
            result_label = "Connecté" if success else f"Erreur {code}"
            self._ftp_test_running = False
            self._ftp_status = "Connecté" if success else "Erreur"
            res_dict = {
                "success": success,
                "code": code,
                "result_label": result_label,
                "message": msg,
                "save_path": save_path,
                "nas_type": cur_nas,
                "protocol": "ftp",
                "timestamp": int(_t.time()),
            }
            self._ftp_test_result = res_dict
            if not hasattr(self, "_nas_test_results"):
                self._nas_test_results = {}
            self._nas_test_results[cur_nas] = res_dict
            self._nas_test_results[f"{cur_nas}_ftp"] = res_dict
            self._nas_test_results["last_ftp"] = res_dict

            if success:
                self._log_event(f"Test FTP {nas_name} réussi : Connecté ({save_path})")
            else:
                self._log_event(f"⚠️ Test FTP {nas_name} échoué : {result_label} - {msg}")
            return res_dict
        except Exception as e:
            err_str = str(e)
            code = 500
            result_label = f"Erreur {code}"
            self._ftp_test_running = False
            self._ftp_status = "Erreur"
            res_dict = {
                "success": False,
                "code": code,
                "result_label": result_label,
                "message": err_str,
                "save_path": "",
                "nas_type": cur_nas,
                "protocol": "ftp",
                "timestamp": int(_t.time()),
            }
            self._ftp_test_result = res_dict
            if not hasattr(self, "_nas_test_results"):
                self._nas_test_results = {}
            self._nas_test_results[cur_nas] = res_dict
            self._nas_test_results[f"{cur_nas}_ftp"] = res_dict
            self._nas_test_results["last_ftp"] = res_dict

            self._append_ftp_log(f"Erreur inattendue : {e}", "error")
            self._log_event(f"⚠️ Erreur test FTP {nas_name} : {e}")
            return res_dict
        finally:
            self.async_write_ha_state()

    async def _async_upload_to_webdav(self, file_path):
        """Upload photo or video to WebDAV / Nextcloud asynchronously."""
        if not getattr(self, "_webdav_enabled", False) or not getattr(self, "_webdav_url", ""):
            return

        is_video = file_path.lower().endswith(('.mp4', '.webm', '.ogg'))
        media_type = "vidéo" if is_video else "photo"
        filename = os.path.basename(file_path)

        try:
            import aiohttp
            from homeassistant.helpers.aiohttp_client import async_get_clientsession

            session = async_get_clientsession(self.hass)
            auth = None
            if self._webdav_user and self._webdav_pass:
                auth = aiohttp.BasicAuth(self._webdav_user, self._webdav_pass)

            base_url = self._webdav_url.rstrip("/")
            
            # Ensure target directories exist via MKCOL
            target_path = getattr(self, "_webdav_path", "domolink/alarm").strip().strip("/")
            dirs = [d for d in target_path.split("/") if d]
            cur_url = base_url
            for d in dirs:
                cur_url = f"{cur_url}/{d}"
                try:
                    async with session.request("MKCOL", cur_url, auth=auth, timeout=aiohttp.ClientTimeout(total=8)) as mkcol_resp:
                        pass
                except Exception:
                    pass

            file_url = f"{cur_url}/{filename}"
            content_type = "video/mp4" if is_video else "image/jpeg"

            def _read_file():
                with open(file_path, "rb") as f:
                    return f.read()

            file_data = await self.hass.async_add_executor_job(_read_file)

            async with session.put(
                file_url,
                data=file_data,
                headers={"Content-Type": content_type},
                auth=auth,
                timeout=aiohttp.ClientTimeout(total=60 if is_video else 20)
            ) as put_resp:
                if put_resp.status in (200, 201, 204):
                    self._webdav_status = "Connecté"
                    _LOGGER.info("Domolink: %s téléversée sur WebDAV avec succès: %s", media_type.capitalize(), filename)
                    self._log_event(f"Sauvegarde {media_type} WebDAV : {filename}")
                else:
                    self._webdav_status = "Erreur"
                    _LOGGER.error("Domolink: Échec téléversement WebDAV (%s): Code %s", filename, put_resp.status)
                    self._log_event(f"⚠️ Échec transfert WebDAV {media_type}: {filename} (HTTP {put_resp.status})")
        except Exception as e:
            self._webdav_status = "Erreur"
            _LOGGER.error("Domolink: Erreur lors de l'envoi WebDAV de %s: %s", file_path, e)
            self._log_event(f"⚠️ Erreur envoi WebDAV : {e}")

        self.async_write_ha_state()

    def _append_webdav_log(self, message: str, level: str = "info"):
        """Append an entry to WebDAV test log and notify state change."""
        now_str = dt_now().strftime("%H:%M:%S")
        if not hasattr(self, "_webdav_test_logs") or self._webdav_test_logs is None:
            self._webdav_test_logs = []
        self._webdav_test_logs.append({
            "time": now_str,
            "message": message,
            "level": level,
        })
        if len(self._webdav_test_logs) > 60:
            self._webdav_test_logs = self._webdav_test_logs[-60:]
        try:
            self.async_write_ha_state()
        except Exception:
            pass

    async def async_test_webdav(self, call=None):
        """Force a connection test to the WebDAV server with real-time log steps."""
        if getattr(self, "_webdav_test_running", False):
            _LOGGER.debug("Domolink: Un test WebDAV est déjà en cours.")
            return {
                "success": False,
                "code": 429,
                "result_label": "Erreur 429",
                "message": "Un test WebDAV est déjà en cours.",
            }

        data = call.data if (call and hasattr(call, "data")) else {}
        return await self._async_run_webdav_test(data)

    async def _async_run_webdav_test(self, data=None):
        """Run step-by-step diagnostic of WebDAV server asynchronously."""
        import time
        import aiohttp
        import re
        from homeassistant.helpers.aiohttp_client import async_get_clientsession

        if data is None:
            data = {}

        nas_labels = {
            "asustor": "ASUSTOR",
            "synology": "Synology",
            "qnap": "QNAP",
            "truenas": "TrueNAS",
            "freebox": "Freebox",
            "unraid": "Unraid",
            "generic": "Autre NAS",
        }
        cur_nas = data.get("nas_type") or getattr(self, "_nas_type", "asustor")
        nas_name = nas_labels.get(cur_nas, "NAS")

        self._webdav_test_running = True
        self._webdav_test_logs = []
        self._webdav_test_result = {}
        self._append_webdav_log(f"🚀 Démarrage du diagnostic WebDAV ({nas_name})...", "info")

        start_time = time.time()
        nas_cfg = getattr(self, "_nas_configs", {}).get(cur_nas, {})
        is_cur_active = (cur_nas == getattr(self, "_nas_type", "asustor"))

        url = str(data.get("webdav_url") or nas_cfg.get("webdav_url") or (getattr(self, "_webdav_url", "") if is_cur_active else "") or "").strip()
        user = str(data.get("webdav_user") if "webdav_user" in data else (nas_cfg.get("webdav_user") if "webdav_user" in nas_cfg else (getattr(self, "_webdav_user", "") if is_cur_active else "") or "")).strip()
        passwd = str(data.get("webdav_pass") if "webdav_pass" in data else (nas_cfg.get("webdav_pass") if "webdav_pass" in nas_cfg else (getattr(self, "_webdav_pass", "") if is_cur_active else "") or ""))
        path = str(data.get("webdav_path") if "webdav_path" in data else (nas_cfg.get("webdav_path") if "webdav_path" in nas_cfg else (getattr(self, "_webdav_path", "domolink/alarm") if is_cur_active else "domolink/alarm")) or "domolink/alarm").strip().strip("/")

        def record_result(success, code, msg, save_p=""):
            elapsed = round(time.time() - start_time, 2)
            result_label = "Connecté" if success else f"Erreur {code}"
            self._webdav_test_running = False
            self._webdav_status = "Connecté" if success else "Erreur"
            res = {
                "success": success,
                "code": code,
                "result_label": result_label,
                "message": msg,
                "save_path": save_p or path,
                "elapsed": elapsed,
                "nas_type": cur_nas,
                "protocol": "webdav",
                "timestamp": int(time.time()),
            }
            self._webdav_test_result = res
            if not hasattr(self, "_nas_test_results"):
                self._nas_test_results = {}
            self._nas_test_results[cur_nas] = res
            self._nas_test_results[f"{cur_nas}_webdav"] = res
            self._nas_test_results["last_webdav"] = res
            if success:
                self._log_event(f"Test WebDAV {nas_name} réussi : Connecté ({elapsed}s)")
            else:
                self._log_event(f"⚠️ Test WebDAV {nas_name} échoué : {result_label} - {msg}")
            return res

        try:
            await asyncio.sleep(0.2)
            if not url:
                self._append_webdav_log("Aucune URL WebDAV configurée.", "error")
                return record_result(False, 400, "URL WebDAV manquante.")

            if not (url.startswith("http://") or url.startswith("https://")):
                self._append_webdav_log("URL invalide (doit débuter par http:// ou https://)", "error")
                return record_result(False, 400, "URL invalide (http:// ou https:// requis).")

            self._append_webdav_log(f"1. Profil {nas_name} : URL={url}, Utilisateur='{user}'", "info")
            await asyncio.sleep(0.25)

            # Step 2: Connection & Auth
            self._append_webdav_log("2. Connexion réseau et authentification...", "info")
            session = async_get_clientsession(self.hass)
            auth = aiohttp.BasicAuth(user, passwd) if user and passwd else None
            base_url = url.rstrip("/")

            try:
                async with session.request("PROPFIND", base_url, headers={"Depth": "0"}, auth=auth, timeout=aiohttp.ClientTimeout(total=12)) as resp:
                    if resp.status in (401, 403):
                        self._append_webdav_log(f"   ✗ Authentification rejetée (Code {resp.status})", "error")
                        return record_result(False, resp.status, f"Identifiants invalides (HTTP {resp.status})")
                    elif resp.status in (200, 207, 405):
                        self._append_webdav_log(f"   ✓ Connexion et accès autorisés (HTTP {resp.status})", "success")
                    elif resp.status == 404:
                        self._append_webdav_log(f"   ✗ Chemin ou serveur WebDAV introuvable (Code {resp.status})", "error")
                        return record_result(False, 404, "Chemin introuvable (HTTP 404)")
                    else:
                        self._append_webdav_log(f"   ⚠️ Réponse serveur inattendue (HTTP {resp.status}), poursuite...", "warning")
            except Exception as conn_err:
                err_str = str(conn_err)
                self._append_webdav_log(f"   ✗ Impossible de joindre le serveur WebDAV : {err_str}", "error")
                code = 111
                if hasattr(conn_err, "os_error") and getattr(conn_err.os_error, "errno", None):
                    code = abs(conn_err.os_error.errno)
                elif isinstance(conn_err, asyncio.TimeoutError):
                    code = 110
                else:
                    m = re.search(r'\[Errno\s*(-?\d+)\]', err_str)
                    if m:
                        code = abs(int(m.group(1)))
                    else:
                        m_http = re.search(r'\b([1-5]\d{2})\b', err_str)
                        if m_http:
                            code = int(m_http.group(1))
                return record_result(False, code, f"Erreur réseau: {err_str}")

            await asyncio.sleep(0.25)
            # Step 3: Directory creation
            self._append_webdav_log(f"3. Vérification de l'arborescence '{path}'...", "info")
            dirs = [d for d in path.split("/") if d]
            cur_url = base_url
            for d in dirs:
                cur_url = f"{cur_url}/{d}"
                try:
                    async with session.request("MKCOL", cur_url, auth=auth, timeout=aiohttp.ClientTimeout(total=8)) as mk_resp:
                        pass
                except Exception:
                    pass
            self._append_webdav_log("   ✓ Arborescence distante vérifiée.", "success")

            await asyncio.sleep(0.25)
            # Step 4: Write test
            self._append_webdav_log("4. Test des permissions d'écriture (PUT)...", "info")
            test_file = f"domolink_probe_{int(time.time())}.txt"
            test_url = f"{cur_url}/{test_file}"
            test_data = b"Domolink Alarm WebDAV Probe Test"

            try:
                async with session.put(test_url, data=test_data, headers={"Content-Type": "text/plain"}, auth=auth, timeout=aiohttp.ClientTimeout(total=12)) as put_resp:
                    if put_resp.status not in (200, 201, 204):
                        self._append_webdav_log(f"   ✗ Échec écriture fichier test (Code {put_resp.status})", "error")
                        return record_result(False, put_resp.status, f"Écriture refusée (HTTP {put_resp.status})")
                    self._append_webdav_log("   ✓ Droits d'écriture validés.", "success")
            except Exception as put_err:
                err_str = str(put_err)
                self._append_webdav_log(f"   ✗ Erreur d'écriture : {err_str}", "error")
                return record_result(False, 500, f"Erreur d'écriture: {err_str}")

            await asyncio.sleep(0.2)
            # Step 5: Clean test file
            self._append_webdav_log("5. Nettoyage du fichier de test (DELETE)...", "info")
            try:
                async with session.delete(test_url, auth=auth, timeout=aiohttp.ClientTimeout(total=8)) as del_resp:
                    self._append_webdav_log("   ✓ Nettoyage effectué.", "success")
            except Exception:
                self._append_webdav_log("   ℹ Nettoyage ignoré (non critique).", "info")

            elapsed = round(time.time() - start_time, 2)
            self._append_webdav_log(f"6. Chemin de sauvegarde validé : {path}", "success")
            self._append_webdav_log(f"🎉 Connexion WebDAV acceptée et validée avec succès sur {nas_name} ({elapsed}s) !", "success")
            return record_result(True, 200, "Connexion acceptée", path)

        except Exception as global_err:
            _LOGGER.error("Domolink: Erreur test WebDAV: %s", global_err)
            self._append_webdav_log(f"Erreur inattendue : {global_err}", "error")
            return record_result(False, 500, str(global_err))
        finally:
            self.async_write_ha_state()

    async def _async_upload_to_google_drive(self, file_path):
        """Upload photo or video to Google Drive asynchronously."""
        if not getattr(self, "_google_drive_enabled", False):
            return

        method = getattr(self, "_google_drive_method", "webhook")
        is_video = file_path.lower().endswith(('.mp4', '.webm', '.ogg'))
        media_type = "vidéo" if is_video else "photo"
        filename = os.path.basename(file_path)
        mime_type = "video/mp4" if is_video else "image/jpeg"

        import aiohttp
        import base64
        import json
        from homeassistant.helpers.aiohttp_client import async_get_clientsession

        session = async_get_clientsession(self.hass)

        try:
            def _read_file():
                with open(file_path, "rb") as f:
                    return f.read()

            file_bytes = await self.hass.async_add_executor_job(_read_file)

            if method == "webhook":
                webhook_url = getattr(self, "_google_drive_webhook_url", "").strip()
                if not webhook_url:
                    _LOGGER.warning("Domolink Google Drive: URL Webhook manquante.")
                    return

                payload = {
                    "filename": filename,
                    "mime_type": mime_type,
                    "file_base64": base64.b64encode(file_bytes).decode("utf-8"),
                    "folder_id": getattr(self, "_google_drive_folder_id", "").strip(),
                }

                timeout = aiohttp.ClientTimeout(total=90 if is_video else 30)
                async with session.post(webhook_url, json=payload, timeout=timeout, allow_redirects=True) as resp:
                    if resp.status in (200, 201):
                        self._google_drive_status = "Connecté"
                        _LOGGER.info("Domolink: %s téléversée sur Google Drive via Webhook: %s", media_type.capitalize(), filename)
                        self._log_event(f"Sauvegarde {media_type} Google Drive : {filename}")
                    else:
                        self._google_drive_status = "Erreur"
                        _LOGGER.error("Domolink: Échec envoi Google Drive Webhook (%s): HTTP %s", filename, resp.status)
                        self._log_event(f"⚠️ Échec Google Drive {media_type}: {filename} (HTTP {resp.status})")

            elif method == "oauth":
                client_id = getattr(self, "_google_drive_client_id", "").strip()
                client_secret = getattr(self, "_google_drive_client_secret", "").strip()
                refresh_token = getattr(self, "_google_drive_refresh_token", "").strip()
                folder_id = getattr(self, "_google_drive_folder_id", "").strip()

                if not (client_id and client_secret and refresh_token):
                    _LOGGER.warning("Domolink Google Drive: Identifiants OAuth2 incomplets.")
                    return

                token_url = "https://oauth2.googleapis.com/token"
                token_data = {
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                }
                async with session.post(token_url, data=token_data, timeout=aiohttp.ClientTimeout(total=15)) as token_resp:
                    if token_resp.status != 200:
                        self._google_drive_status = "Erreur"
                        _LOGGER.error("Domolink Google Drive: Échec rafraîchissement token OAuth: HTTP %s", token_resp.status)
                        return
                    token_json = await token_resp.json()
                    access_token = token_json.get("access_token")

                metadata = {"name": filename}
                if folder_id:
                    metadata["parents"] = [folder_id]

                boundary = "==================DomolinkDriveBoundary=="
                headers = {
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": f"multipart/related; boundary={boundary}",
                }
                metadata_str = json.dumps(metadata)
                body = (
                    f"--{boundary}\r\n"
                    f"Content-Type: application/json; charset=UTF-8\r\n\r\n"
                    f"{metadata_str}\r\n"
                    f"--{boundary}\r\n"
                    f"Content-Type: {mime_type}\r\n\r\n"
                ).encode("utf-8") + file_bytes + f"\r\n--{boundary}--\r\n".encode("utf-8")

                upload_url = "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart"
                timeout = aiohttp.ClientTimeout(total=90 if is_video else 30)
                async with session.post(upload_url, data=body, headers=headers, timeout=timeout) as up_resp:
                    if up_resp.status in (200, 201):
                        self._google_drive_status = "Connecté"
                        _LOGGER.info("Domolink: %s téléversée sur Google Drive via API OAuth: %s", media_type.capitalize(), filename)
                        self._log_event(f"Sauvegarde {media_type} Google Drive : {filename}")
                    else:
                        self._google_drive_status = "Erreur"
                        _LOGGER.error("Domolink: Échec envoi Google Drive API (%s): HTTP %s", filename, up_resp.status)
                        self._log_event(f"⚠️ Échec Google Drive {media_type}: {filename} (HTTP {up_resp.status})")

        except Exception as e:
            self._google_drive_status = "Erreur"
            _LOGGER.error("Domolink: Erreur téléversement Google Drive de %s: %s", file_path, e)
            self._log_event(f"⚠️ Erreur envoi Google Drive : {e}")

        self.async_write_ha_state()

    def _append_google_drive_log(self, message: str, level: str = "info"):
        """Append an entry to Google Drive test log and notify state change."""
        now_str = dt_now().strftime("%H:%M:%S")
        if not hasattr(self, "_google_drive_test_logs") or self._google_drive_test_logs is None:
            self._google_drive_test_logs = []
        self._google_drive_test_logs.append({
            "time": now_str,
            "message": message,
            "level": level,
        })
        if len(self._google_drive_test_logs) > 60:
            self._google_drive_test_logs = self._google_drive_test_logs[-60:]
        try:
            self.async_write_ha_state()
        except Exception:
            pass

    async def async_test_google_drive(self, call=None):
        """Force a connection test to Google Drive with real-time log steps."""
        if getattr(self, "_google_drive_test_running", False):
            _LOGGER.debug("Domolink: Un test Google Drive est déjà en cours.")
            return

        self._google_drive_test_running = True
        self._google_drive_test_logs = []
        self._google_drive_test_result = {}
        self._append_google_drive_log("🚀 Démarrage du diagnostic Google Drive...", "info")

        self.hass.async_create_task(self._async_run_google_drive_test())

    async def _async_run_google_drive_test(self):
        """Run step-by-step diagnostic of Google Drive asynchronously."""
        import time
        import aiohttp
        import base64
        import json
        from homeassistant.helpers.aiohttp_client import async_get_clientsession

        start_time = time.time()
        method = getattr(self, "_google_drive_method", "webhook")
        folder_id = str(getattr(self, "_google_drive_folder_id", "") or "").strip()

        try:
            await asyncio.sleep(0.2)
            if not getattr(self, "_google_drive_enabled", False):
                self._append_google_drive_log("Le service Google Drive est désactivé dans la configuration.", "error")
                self._google_drive_status = "Erreur"
                self._google_drive_test_running = False
                self._google_drive_test_result = {"success": False, "message": "Service désactivé."}
                self.async_write_ha_state()
                return

            session = async_get_clientsession(self.hass)

            if method == "webhook":
                webhook_url = str(getattr(self, "_google_drive_webhook_url", "") or "").strip()
                if not webhook_url:
                    self._append_google_drive_log("Aucune URL Webhook Google Apps Script configurée.", "error")
                    self._google_drive_status = "Erreur"
                    self._google_drive_test_running = False
                    self._google_drive_test_result = {"success": False, "message": "URL Webhook manquante."}
                    self.async_write_ha_state()
                    return

                self._append_google_drive_log(f"1. Configuration Webhook : {webhook_url[:40]}...", "info")
                await asyncio.sleep(0.3)

                self._append_google_drive_log("2. Envoi de la sonde de test vers le script Google Drive...", "info")
                probe_payload = {
                    "probe": True,
                    "filename": "domolink_probe.txt",
                    "file_base64": base64.b64encode(b"Domolink Alarm Google Drive Probe Test").decode("utf-8"),
                    "mime_type": "text/plain",
                    "folder_id": folder_id,
                }

                try:
                    async with session.post(webhook_url, json=probe_payload, timeout=aiohttp.ClientTimeout(total=20), allow_redirects=True) as resp:
                        if resp.status in (200, 201):
                            self._append_google_drive_log(f"   ✓ Réponse reçue du script Google Drive (HTTP {resp.status})", "success")
                            self._append_google_drive_log("3. Validation de l'accès et des permissions de stockage...", "info")
                            await asyncio.sleep(0.3)
                            self._append_google_drive_log("   ✓ Droits de téléversement validés sur Google Drive.", "success")
                        else:
                            self._append_google_drive_log(f"   ✗ Le Webhook a retourné une erreur (HTTP {resp.status})", "error")
                            self._google_drive_status = "Erreur"
                            self._google_drive_test_running = False
                            self._google_drive_test_result = {"success": False, "message": f"Erreur Webhook HTTP {resp.status}"}
                            self.async_write_ha_state()
                            return
                except Exception as net_err:
                    self._append_google_drive_log(f"   ✗ Impossible de joindre l'URL Webhook : {net_err}", "error")
                    self._google_drive_status = "Erreur"
                    self._google_drive_test_running = False
                    self._google_drive_test_result = {"success": False, "message": str(net_err)}
                    self.async_write_ha_state()
                    return

            elif method == "oauth":
                client_id = str(getattr(self, "_google_drive_client_id", "") or "").strip()
                client_secret = str(getattr(self, "_google_drive_client_secret", "") or "").strip()
                refresh_token = str(getattr(self, "_google_drive_refresh_token", "") or "").strip()

                if not (client_id and client_secret and refresh_token):
                    self._append_google_drive_log("Paramètres OAuth2 incomplets (Client ID, Secret ou Refresh Token manquant).", "error")
                    self._google_drive_status = "Erreur"
                    self._google_drive_test_running = False
                    self._google_drive_test_result = {"success": False, "message": "Identifiants OAuth2 incomplets."}
                    self.async_write_ha_state()
                    return

                self._append_google_drive_log("1. Échange du Refresh Token avec l'API OAuth2 Google...", "info")
                token_url = "https://oauth2.googleapis.com/token"
                token_data = {
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                }
                try:
                    async with session.post(token_url, data=token_data, timeout=aiohttp.ClientTimeout(total=15)) as token_resp:
                        if token_resp.status != 200:
                            self._append_google_drive_log(f"   ✗ Échec de l'authentification OAuth2 (HTTP {token_resp.status})", "error")
                            self._google_drive_status = "Erreur"
                            self._google_drive_test_running = False
                            self._google_drive_test_result = {"success": False, "message": f"Erreur OAuth2 HTTP {token_resp.status}"}
                            self.async_write_ha_state()
                            return
                        token_json = await token_resp.json()
                        access_token = token_json.get("access_token")
                        self._append_google_drive_log("   ✓ Access Token OAuth2 généré avec succès.", "success")
                except Exception as oauth_err:
                    self._append_google_drive_log(f"   ✗ Erreur connexion OAuth2 : {oauth_err}", "error")
                    self._google_drive_status = "Erreur"
                    self._google_drive_test_running = False
                    self._google_drive_test_result = {"success": False, "message": str(oauth_err)}
                    self.async_write_ha_state()
                    return

                await asyncio.sleep(0.3)
                if folder_id:
                    self._append_google_drive_log(f"2. Vérification du dossier distant ({folder_id})...", "info")
                    check_url = f"https://www.googleapis.com/drive/v3/files/{folder_id}?fields=id,name,mimeType"
                    async with session.get(check_url, headers={"Authorization": f"Bearer {access_token}"}, timeout=aiohttp.ClientTimeout(total=10)) as f_resp:
                        if f_resp.status == 200:
                            f_info = await f_resp.json()
                            self._append_google_drive_log(f"   ✓ Dossier trouvé : '{f_info.get('name', folder_id)}'", "success")
                        else:
                            self._append_google_drive_log(f"   ⚠️ Dossier introuvable ou inaccessible (HTTP {f_resp.status}), racine utilisée.", "warning")

                await asyncio.sleep(0.3)
                self._append_google_drive_log("3. Test d'écriture fichier sonde (multipart upload)...", "info")
                probe_filename = f"domolink_probe_{int(time.time())}.txt"
                boundary = "==================DomolinkDriveBoundary=="
                headers = {
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": f"multipart/related; boundary={boundary}",
                }
                meta = {"name": probe_filename}
                if folder_id:
                    meta["parents"] = [folder_id]
                probe_content = b"Domolink Probe Test File"
                body = (
                    f"--{boundary}\r\n"
                    f"Content-Type: application/json; charset=UTF-8\r\n\r\n"
                    f"{json.dumps(meta)}\r\n"
                    f"--{boundary}\r\n"
                    f"Content-Type: text/plain\r\n\r\n"
                ).encode("utf-8") + probe_content + f"\r\n--{boundary}--\r\n".encode("utf-8")

                upload_url = "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart"
                created_file_id = None
                async with session.post(upload_url, data=body, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as up_resp:
                    if up_resp.status not in (200, 201):
                        self._append_google_drive_log(f"   ✗ Échec téléversement test (HTTP {up_resp.status})", "error")
                        self._google_drive_status = "Erreur"
                        self._google_drive_test_running = False
                        self._google_drive_test_result = {"success": False, "message": f"Écriture refusée (HTTP {up_resp.status})"}
                        self.async_write_ha_state()
                        return
                    up_json = await up_resp.json()
                    created_file_id = up_json.get("id")
                    self._append_google_drive_log("   ✓ Fichier test créé avec succès sur Google Drive.", "success")

                if created_file_id:
                    await asyncio.sleep(0.2)
                    self._append_google_drive_log("4. Nettoyage du fichier test...", "info")
                    del_url = f"https://www.googleapis.com/drive/v3/files/{created_file_id}"
                    async with session.delete(del_url, headers={"Authorization": f"Bearer {access_token}"}, timeout=aiohttp.ClientTimeout(total=8)) as del_resp:
                        self._append_google_drive_log("   ✓ Nettoyage effectué.", "success")

            elapsed = round(time.time() - start_time, 2)
            dest_desc = f"Dossier: {folder_id}" if folder_id else "Racine Google Drive"
            self._append_google_drive_log(f"🎉 Connexion Google Drive validée avec succès ({elapsed}s) !", "success")
            self._google_drive_status = "Connecté"
            self._google_drive_test_running = False
            self._google_drive_test_result = {
                "success": True,
                "message": "Connexion acceptée",
                "save_path": dest_desc,
                "elapsed": elapsed,
            }
            self._log_event(f"Test Google Drive réussi ({elapsed}s) : {dest_desc}")

        except Exception as global_err:
            _LOGGER.error("Domolink: Erreur test Google Drive: %s", global_err)
            self._append_google_drive_log(f"Erreur inattendue : {global_err}", "error")
            self._google_drive_status = "Erreur"
            self._google_drive_test_running = False
            self._google_drive_test_result = {"success": False, "message": str(global_err)}
            self._log_event(f"⚠️ Erreur test Google Drive : {global_err}")
        finally:
            self.async_write_ha_state()

    async def _async_capture_cameras(self, triggering_entity=None):
        """Asynchronously capture photos and trigger recordings with targeted zone cameras (parallel & robust)."""
        if not self._cameras:
            _LOGGER.debug("Domolink: Aucune caméra configurée.")
            return

        target_cameras, matching_zones = self._get_cameras_for_sensor(triggering_entity)
        if not target_cameras:
            target_cameras = list(self._cameras)

        import shutil

        media_dir = self.hass.config.path(f"www/{self._media_path}")
        try:
            os.makedirs(media_dir, exist_ok=True)
        except Exception as e:
            _LOGGER.error("Domolink: Impossible de créer %s: %s", media_dir, e)

        zone_desc = f" (Zone: {', '.join(matching_zones)})" if matching_zones else ""
        self._log_event(f"Capture photo & vidéo{zone_desc} sur {len(target_cameras)} caméra(s)")

        async def _capture_single_camera(camera, idx):
            snapshot_filename, video_filename = self._get_media_filenames(camera)
            snapshot_path = os.path.join(media_dir, snapshot_filename)
            record_path = os.path.join(media_dir, video_filename)

            # Wake up camera
            try:
                await self.hass.services.async_call("camera", "turn_on", {"entity_id": camera})
            except Exception:
                pass

            # 1. Snapshot with generous 12s timeout for Blink/cloud cameras
            try:
                if camera.startswith("camera.aarlo"):
                    await asyncio.wait_for(
                        self.hass.services.async_call(
                            "aarlo", "camera_request_snapshot_to_file",
                            {"entity_id": camera, "filename": snapshot_path},
                            blocking=True,
                        ),
                        timeout=12.0,
                    )
                else:
                    await asyncio.wait_for(
                        self.hass.services.async_call(
                            "camera", "snapshot",
                            {"entity_id": camera, "filename": snapshot_path},
                            blocking=True,
                        ),
                        timeout=12.0,
                    )

                # Keep latest alert copy for push notifications
                if idx == 0 and os.path.exists(snapshot_path):
                    alert_path = self.hass.config.path("www/domolink_alarm_alert.jpg")
                    try:
                        shutil.copy2(snapshot_path, alert_path)
                    except Exception as e:
                        _LOGGER.debug("Domolink: Erreur copie alert_path: %s", e)

                if os.path.exists(snapshot_path):
                    self._media_files_cache_ts = 0
                    if getattr(self, "_telegram_enabled", False):
                        self.hass.async_create_task(self._async_upload_to_telegram(snapshot_path))
                    if getattr(self, "_ftp_enabled", False):
                        self.hass.async_create_task(self._async_upload_to_ftp(snapshot_path))
                    if getattr(self, "_webdav_enabled", False):
                        self.hass.async_create_task(self._async_upload_to_webdav(snapshot_path))
                    if getattr(self, "_google_drive_enabled", False):
                        self.hass.async_create_task(self._async_upload_to_google_drive(snapshot_path))
            except asyncio.TimeoutError:
                _LOGGER.warning("Domolink: Timeout photo (12s) sur %s", camera)
            except Exception as e:
                _LOGGER.error("Domolink: Erreur photo sur %s: %s", camera, e)

            # 2. Video recording with watcher for .mp4.tmp
            try:
                await self.hass.services.async_call(
                    "camera", "record",
                    {"entity_id": camera, "duration": 30, "filename": record_path},
                )
                self.hass.async_create_task(
                    self._async_watch_and_fix_video(record_path, timeout=90)
                )
            except Exception as e:
                _LOGGER.error("Domolink: Erreur enregistrement vidéo %s: %s", camera, e)

        # Launch all camera captures in parallel
        tasks = [_capture_single_camera(cam, i) for i, cam in enumerate(target_cameras)]
        await asyncio.gather(*tasks, return_exceptions=True)
        # Purge storage after new captures
        self.hass.async_create_task(self.hass.async_add_executor_job(self._purge_old_media_files))

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

        # If sirens turned off after cycle and alarm was not disarmed:
        # Enter 1-minute disarm grace period, then auto-rearm
        if self._state == AlarmControlPanelState.TRIGGERED:
            self._log_event("Fin de sonnerie sirène — Attente de désarmement (1 minute avant réarmement)")
            self.async_write_ha_state()
            from homeassistant.helpers.event import async_call_later
            if self._disarm_cooldown_task:
                self._disarm_cooldown_task()
            self._disarm_cooldown_task = async_call_later(
                self.hass,
                60,
                self._cb_auto_rearm_after_alarm,
            )

    @callback
    def _cb_auto_rearm_after_alarm(self, now=None):
        """Callback when 60s disarm grace period ends — automatically re-arms the alarm."""
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
        await self._async_send_notification(msg)
        self._log_event(f"Système ré-armé automatiquement ({target_state.value})")

    # ─── Helper: Cancel All Tasks ─────────────────────────────────

    def _cancel_all_tasks(self):
        """Cancel any pending timers."""
        self._post_trigger_active = False
        if hasattr(self, "_disarm_cooldown_task") and self._disarm_cooldown_task:
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
        if self._geofence_reminder_task:
            self._geofence_reminder_task()
            self._geofence_reminder_task = None
        # Only cancel presence simulation if it was NOT forced manually
        if self._presence_simulation_task and not self._presence_simulation_forced:
            self._presence_simulation_task()
            self._presence_simulation_task = None

    # ─── Presence Simulation Engine ───────────────────────────────


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
            CONF_FTP_ENABLED, CONF_FTP_HOST, CONF_FTP_PORT, CONF_FTP_USER, CONF_FTP_PASS, CONF_FTP_PATH,
            CONF_WEBDAV_ENABLED, CONF_WEBDAV_URL, CONF_WEBDAV_USER, CONF_WEBDAV_PASS, CONF_WEBDAV_PATH,
            CONF_NAS_TYPE,
            CONF_NAS_CONFIGS,
            CONF_GOOGLE_DRIVE_ENABLED, CONF_GOOGLE_DRIVE_METHOD, CONF_GOOGLE_DRIVE_WEBHOOK_URL,
            CONF_GOOGLE_DRIVE_CLIENT_ID, CONF_GOOGLE_DRIVE_CLIENT_SECRET, CONF_GOOGLE_DRIVE_REFRESH_TOKEN,
            CONF_GOOGLE_DRIVE_FOLDER_ID,
            CONF_MEDIA_PATH, CONF_MEDIA_RETENTION_DAYS, CONF_MEDIA_MAX_SIZE_MB,
        }
        
        updated = False
        for key, value in call.data.items():
            if key in valid_keys:
                new_options[key] = value
                updated = True

        if CONF_NAS_CONFIGS in call.data:
            nas_cfgs = call.data[CONF_NAS_CONFIGS]
            if isinstance(nas_cfgs, dict):
                new_options[CONF_NAS_CONFIGS] = nas_cfgs
                cur_nas = str(new_options.get(CONF_NAS_TYPE, getattr(self, "_nas_type", DEFAULT_NAS_TYPE))).lower()
                if cur_nas in nas_cfgs and isinstance(nas_cfgs[cur_nas], dict):
                    cur_cfg = nas_cfgs[cur_nas]
                    for k in ["ftp_enabled", "ftp_host", "ftp_port", "ftp_user", "ftp_pass", "ftp_path",
                              "webdav_enabled", "webdav_url", "webdav_user", "webdav_pass", "webdav_path"]:
                        if k in cur_cfg:
                            new_options[k] = cur_cfg[k]
        elif CONF_NAS_TYPE in call.data:
            cur_nas = str(call.data[CONF_NAS_TYPE]).lower()
            nas_cfgs = new_options.get(CONF_NAS_CONFIGS, getattr(self, "_nas_configs", {}))
            if cur_nas in nas_cfgs and isinstance(nas_cfgs[cur_nas], dict):
                cur_cfg = nas_cfgs[cur_nas]
                for k in ["ftp_enabled", "ftp_host", "ftp_port", "ftp_user", "ftp_pass", "ftp_path",
                          "webdav_enabled", "webdav_url", "webdav_user", "webdav_pass", "webdav_path"]:
                    if k in cur_cfg:
                        new_options[k] = cur_cfg[k]
                
        if updated:
            self.hass.config_entries.async_update_entry(self._entry, options=new_options)
            _LOGGER.info("Domolink: Settings updated -> %s", list(call.data.keys()))
            self._log_event("Paramètres mis à jour")

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
            # Adding random jitter of +/- 15 minutes to make replay look natural
            jitter_seconds = random.randint(-900, 900)
            past_now = now - timedelta(days=self._presence_simulation_history_days) + timedelta(seconds=jitter_seconds)
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
        self.hass.async_create_task(self._async_sync_cameras(False))
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
            if state is None:
                continue  # Entity no longer exists in HA, do not block arming
            if str(state.state).lower() in ("on", "open", "true", "detected", "unlocked", "1", "unavailable"):
                name = state.name if state and state.name else sensor
                open_sensors.append(name)

        # Also for NIGHT mode, check night sensors
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
        self.hass.async_create_task(self._async_sync_cameras(True))
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
        self.hass.async_create_task(self._async_sync_cameras(True))
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
        self.hass.async_create_task(self._async_sync_cameras(True))
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
        # Convert 1-7 or 0-6 to Python weekday (0=Monday, 6=Sunday)
        target_day = (self._siren_test_day - 1) if (1 <= self._siren_test_day <= 7) else self._siren_test_day
        if now.weekday() != (target_day % 7):
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
