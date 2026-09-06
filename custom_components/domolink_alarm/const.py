"""Constants for the Domolink Alarm integration."""

DOMAIN = "domolink_alarm"

CONF_NAME = "name"
DEFAULT_NAME = "Domolink Alarm"

CONF_OPENING_SENSORS = "opening_sensors"
CONF_OPENING_SENSORS_LABELS = "opening_sensors_labels"
CONF_NIGHT_SENSORS = "night_sensors"
CONF_NIGHT_SENSORS_LABELS = "night_sensors_labels"
CONF_MOTION_SENSORS = "motion_sensors"
CONF_MOTION_SENSORS_LABELS = "motion_sensors_labels"
CONF_CAMERAS = "cameras"
CONF_CAMERAS_LABELS = "cameras_labels"
CONF_TAMPER_SENSORS = "tamper_sensors"
CONF_TAMPER_SENSORS_LABELS = "tamper_sensors_labels"
CONF_KEYPADS = "keypads"
CONF_KEYPADS_LABELS = "keypads_labels"
CONF_PERSONS = "persons"
CONF_PERSONS_LABELS = "persons_labels"

CONF_SIRENS = "sirens"
CONF_SIRENS_LABELS = "sirens_labels"
CONF_LIGHTS = "lights"
CONF_LIGHTS_LABELS = "lights_labels"
CONF_MEDIA_PLAYERS = "media_players"
CONF_MEDIA_PLAYERS_LABELS = "media_players_labels"
CONF_NOTIFY_SERVICES = "notify_services"
CONF_NOTIFY_SERVICES_LABELS = "notify_services_labels"
CONF_FREE_MOBILE_USER = "free_mobile_user"
CONF_FREE_MOBILE_PASS = "free_mobile_pass"

CONF_USERS_CODES = "users_codes"
CONF_DURESS_CODE = "duress_code"
CONF_RFID_TAGS = "rfid_tags"
CONF_BYPASS_ALLOWED = "bypass_allowed"
CONF_HEALTH_CHECK = "health_check"
CONF_GEOFENCE_AUTO_ARM = "geofence_auto_arm"
CONF_EXIT_DELAY = "exit_delay"
CONF_ENTRY_DELAY = "entry_delay"
CONF_SIREN_DURATION = "siren_duration"
CONF_CHIME_MODE = "chime_mode"

CONF_SAFETY_SENSORS = "safety_sensors"
CONF_SAFETY_SENSORS_LABELS = "safety_sensors_labels"
CONF_PRESENCE_SIMULATION_ENTITIES = "presence_simulation_entities"
CONF_PRESENCE_SIMULATION_LABELS = "presence_simulation_labels"
CONF_PRESENCE_SIMULATION_HISTORY_DAYS = "presence_simulation_history_days"

CONF_CROSS_ZONING = "cross_zoning"
CONF_CROSS_ZONING_WINDOW = "cross_zoning_window"
CONF_GEOFENCE_REMINDER = "geofence_reminder"
CONF_GEOFENCE_REMINDER_DELAY = "geofence_reminder_delay"

CONF_EMERGENCY_CONTACT = "emergency_contact"
CONF_EMERGENCY_CONTACT_LABELS = "emergency_contact_labels"

CONF_SIREN_TEST = "siren_test"
CONF_SIREN_TEST_DAY = "siren_test_day"
CONF_SIREN_TEST_HOUR = "siren_test_hour"

CONF_SCHEDULE_ENABLED = "schedule_enabled"
CONF_SCHEDULE_ARM_TIME = "schedule_arm_time"
CONF_SCHEDULE_DISARM_TIME = "schedule_disarm_time"
CONF_SCHEDULE_MODE = "schedule_mode"

DEFAULT_EXIT_DELAY = 30
DEFAULT_ENTRY_DELAY = 30
DEFAULT_SIREN_DURATION = 180
DEFAULT_BYPASS_ALLOWED = False
DEFAULT_HEALTH_CHECK = True
DEFAULT_GEOFENCE_AUTO_ARM = False
DEFAULT_CHIME_MODE = False
DEFAULT_CROSS_ZONING = False
DEFAULT_CROSS_ZONING_WINDOW = 60
DEFAULT_GEOFENCE_REMINDER = False
DEFAULT_GEOFENCE_REMINDER_DELAY = 15
DEFAULT_PRESENCE_SIMULATION_HISTORY_DAYS = 7
DEFAULT_SIREN_TEST = False
DEFAULT_SIREN_TEST_DAY = 5
DEFAULT_SIREN_TEST_HOUR = 12
DEFAULT_SCHEDULE_ENABLED = False
DEFAULT_SCHEDULE_ARM_TIME = "23:00"
DEFAULT_SCHEDULE_DISARM_TIME = "06:00"
DEFAULT_SCHEDULE_MODE = "night"

CONF_ICLOUD_ACCOUNT = "icloud_account"
CONF_ICLOUD_DEVICES = "icloud_devices"

CONF_MQTT_ENABLED = "mqtt_enabled"
CONF_MQTT_TOPIC_BASE = "mqtt_topic_base"
CONF_MQTT_REQUIRE_CODE = "mqtt_require_code"

DEFAULT_MQTT_ENABLED = False
DEFAULT_MQTT_TOPIC_BASE = "domolink/alarme"
DEFAULT_MQTT_REQUIRE_CODE = False

# Cloud Backup Settings
CONF_TELEGRAM_ENABLED = "telegram_enabled"
CONF_TELEGRAM_TOKEN = "telegram_token"
CONF_TELEGRAM_CHAT_ID = "telegram_chat_id"

CONF_FTP_ENABLED = "ftp_enabled"
CONF_FTP_HOST = "ftp_host"
CONF_FTP_PORT = "ftp_port"
CONF_FTP_USER = "ftp_user"
CONF_FTP_PASS = "ftp_pass"
CONF_FTP_PATH = "ftp_path"

DEFAULT_TELEGRAM_ENABLED = False
DEFAULT_FTP_ENABLED = False
DEFAULT_FTP_PORT = 21
DEFAULT_FTP_PATH = "/"
CONF_CAMERAS_ARM_ENTITIES = "cameras_arm_entities"
CONF_CAMERAS_ARM_ENTITIES_LABELS = "cameras_arm_entities_labels"

# WebDAV Cloud Backup
CONF_WEBDAV_ENABLED = "webdav_enabled"
CONF_WEBDAV_URL = "webdav_url"
CONF_WEBDAV_USER = "webdav_user"
CONF_WEBDAV_PASS = "webdav_pass"
CONF_WEBDAV_PATH = "webdav_path"

DEFAULT_WEBDAV_ENABLED = False
DEFAULT_WEBDAV_PATH = "domolink/alarm"

# Media Storage & Retention
CONF_MEDIA_PATH = "media_path"
DEFAULT_MEDIA_PATH = "domolink_media"
CONF_MEDIA_RETENTION_DAYS = "media_retention_days"
CONF_MEDIA_MAX_SIZE_MB = "media_max_size_mb"
DEFAULT_MEDIA_RETENTION_DAYS = 30
DEFAULT_MEDIA_MAX_SIZE_MB = 1024

# Zones & Targeted Cameras
CONF_ZONE_LABELS = "zone_labels"
CONF_GLOBAL_CAMERAS = "global_cameras"
CONF_GLOBAL_CAMERAS_LABELS = "global_cameras_labels"

# NAS Profiles & Presets
CONF_NAS_TYPE = "nas_type"
DEFAULT_NAS_TYPE = "asustor"
CONF_NAS_CONFIGS = "nas_configs"
DEFAULT_NAS_CONFIGS = {
    "asustor": {
        "ftp_enabled": True,
        "ftp_host": "",
        "ftp_port": 21,
        "ftp_user": "",
        "ftp_pass": "",
        "ftp_path": "/",
        "webdav_enabled": False,
        "webdav_url": "",
        "webdav_user": "",
        "webdav_pass": "",
        "webdav_path": "domolink/alarm",
    },
    "synology": {
        "ftp_enabled": True,
        "ftp_host": "",
        "ftp_port": 21,
        "ftp_user": "",
        "ftp_pass": "",
        "ftp_path": "/",
        "webdav_enabled": False,
        "webdav_url": "",
        "webdav_user": "",
        "webdav_pass": "",
        "webdav_path": "domolink/alarm",
    },
    "qnap": {
        "ftp_enabled": True,
        "ftp_host": "",
        "ftp_port": 21,
        "ftp_user": "",
        "ftp_pass": "",
        "ftp_path": "/",
        "webdav_enabled": False,
        "webdav_url": "",
        "webdav_user": "",
        "webdav_pass": "",
        "webdav_path": "domolink/alarm",
    },
    "truenas": {
        "ftp_enabled": False,
        "ftp_host": "",
        "ftp_port": 21,
        "ftp_user": "",
        "ftp_pass": "",
        "ftp_path": "/",
        "webdav_enabled": True,
        "webdav_url": "",
        "webdav_user": "",
        "webdav_pass": "",
        "webdav_path": "domolink/alarm",
    },
    "freebox": {
        "ftp_enabled": True,
        "ftp_host": "mafreebox.freebox.fr",
        "ftp_port": 21,
        "ftp_user": "freebox",
        "ftp_pass": "",
        "ftp_path": "/",
        "webdav_enabled": False,
        "webdav_url": "",
        "webdav_user": "",
        "webdav_pass": "",
        "webdav_path": "domolink/alarm",
    },
    "unraid": {
        "ftp_enabled": True,
        "ftp_host": "",
        "ftp_port": 21,
        "ftp_user": "",
        "ftp_pass": "",
        "ftp_path": "/",
        "webdav_enabled": False,
        "webdav_url": "",
        "webdav_user": "",
        "webdav_pass": "",
        "webdav_path": "domolink/alarm",
    },
    "generic": {
        "ftp_enabled": True,
        "ftp_host": "",
        "ftp_port": 21,
        "ftp_user": "",
        "ftp_pass": "",
        "ftp_path": "/",
        "webdav_enabled": False,
        "webdav_url": "",
        "webdav_user": "",
        "webdav_pass": "",
        "webdav_path": "domolink/alarm",
    },
}

# Google Drive Cloud Backup
CONF_GOOGLE_DRIVE_ENABLED = "google_drive_enabled"
CONF_GOOGLE_DRIVE_METHOD = "google_drive_method"
CONF_GOOGLE_DRIVE_WEBHOOK_URL = "google_drive_webhook_url"
CONF_GOOGLE_DRIVE_CLIENT_ID = "google_drive_client_id"
CONF_GOOGLE_DRIVE_CLIENT_SECRET = "google_drive_client_secret"
CONF_GOOGLE_DRIVE_REFRESH_TOKEN = "google_drive_refresh_token"
CONF_GOOGLE_DRIVE_FOLDER_ID = "google_drive_folder_id"

DEFAULT_GOOGLE_DRIVE_ENABLED = False
DEFAULT_GOOGLE_DRIVE_METHOD = "webhook"

