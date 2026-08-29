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
