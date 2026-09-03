"""Config flow for Domolink Alarm integration."""
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

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
    CONF_KEYPADS,
    CONF_KEYPADS_LABELS,
    CONF_SIRENS,
    CONF_SIRENS_LABELS,
    CONF_LIGHTS,
    CONF_LIGHTS_LABELS,
    CONF_MEDIA_PLAYERS,
    CONF_MEDIA_PLAYERS_LABELS,
    CONF_NOTIFY_SERVICES,
    CONF_NOTIFY_SERVICES_LABELS,
    CONF_FREE_MOBILE_USER,
    CONF_FREE_MOBILE_PASS,
    CONF_ICLOUD_ACCOUNT,
    CONF_ICLOUD_DEVICES,
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
    CONF_EMERGENCY_CONTACT,
    CONF_EMERGENCY_CONTACT_LABELS,
    CONF_SIREN_TEST,
    CONF_SIREN_TEST_DAY,
    CONF_SIREN_TEST_HOUR,
    CONF_SCHEDULE_ENABLED,
    CONF_SCHEDULE_ARM_TIME,
    CONF_SCHEDULE_DISARM_TIME,
    CONF_SCHEDULE_MODE,
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
    CONF_MQTT_ENABLED,
    CONF_MQTT_TOPIC_BASE,
    CONF_MQTT_REQUIRE_CODE,
    DEFAULT_MQTT_ENABLED,
    DEFAULT_MQTT_TOPIC_BASE,
    DEFAULT_MQTT_REQUIRE_CODE,
    CONF_TELEGRAM_ENABLED,
    CONF_TELEGRAM_TOKEN,
    CONF_TELEGRAM_CHAT_ID,
    CONF_FTP_ENABLED,
    CONF_FTP_HOST,
    CONF_FTP_PORT,
    CONF_FTP_USER,
    CONF_FTP_PASS,
    CONF_FTP_PATH,
    DEFAULT_TELEGRAM_ENABLED,
    DEFAULT_FTP_ENABLED,
    DEFAULT_FTP_PORT,
    DEFAULT_FTP_PATH,
    CONF_MEDIA_PATH,
    DEFAULT_MEDIA_PATH,
    CONF_CAMERAS_ARM_ENTITIES,
    CONF_ZONE_LABELS,
    CONF_GLOBAL_CAMERAS,
    CONF_GLOBAL_CAMERAS_LABELS,
)


class DomolinkAlarmConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Domolink Alarm."""

    VERSION = 1

    def __init__(self):
        """Initialize."""
        self.data = {}

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        return await self.async_step_sensors()

    async def async_step_sensors(self, user_input=None):
        """Step 1: Configure sensors and system name."""
        if user_input is not None:
            self.data.update(user_input)
            return await self.async_step_actuators()

        return self.async_show_form(
            step_id="sensors",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
                    vol.Optional(CONF_NIGHT_SENSORS, default=[]): selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            domain=["binary_sensor", "sensor"],
                            multiple=True
                        )
                    ),
                    vol.Optional(CONF_NIGHT_SENSORS_LABELS, default=[]): selector.LabelSelector(selector.LabelSelectorConfig(multiple=True)),
                    vol.Optional(CONF_OPENING_SENSORS, default=[]): selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            domain=["binary_sensor", "sensor"], 
                            device_class=["door", "window", "opening", "garage_door"],
                            multiple=True
                        )
                    ),
                    vol.Optional(CONF_OPENING_SENSORS_LABELS, default=[]): selector.LabelSelector(selector.LabelSelectorConfig(multiple=True)),
                    vol.Optional(CONF_MOTION_SENSORS, default=[]): selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            domain=["binary_sensor", "sensor"],
                            device_class=["motion", "occupancy", "presence"],
                            multiple=True
                        )
                    ),
                    vol.Optional(CONF_MOTION_SENSORS_LABELS, default=[]): selector.LabelSelector(selector.LabelSelectorConfig(multiple=True)),
                    vol.Optional(CONF_CAMERAS_ARM_ENTITIES, default=[]): selector.EntitySelector(selector.EntitySelectorConfig(multiple=True)),
                    vol.Optional(CONF_CAMERAS, default=[]): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="camera", multiple=True)
                    ),
                    vol.Optional(CONF_CAMERAS_LABELS, default=[]): selector.LabelSelector(selector.LabelSelectorConfig(multiple=True)),
                    vol.Optional(CONF_TAMPER_SENSORS, default=[]): selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            domain=["binary_sensor", "sensor"],
                            device_class=["tamper", "safety", "problem"],
                            multiple=True
                        )
                    ),
                    vol.Optional(CONF_TAMPER_SENSORS_LABELS, default=[]): selector.LabelSelector(selector.LabelSelectorConfig(multiple=True)),
                    vol.Optional(CONF_KEYPADS, default=[]): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain=["alarm_control_panel", "sensor"], multiple=True)
                    ),
                    vol.Optional(CONF_KEYPADS_LABELS, default=[]): selector.LabelSelector(selector.LabelSelectorConfig(multiple=True)),
                    vol.Optional(CONF_SAFETY_SENSORS, default=[]): selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            domain=["binary_sensor", "sensor"],
                            device_class=["smoke", "gas", "moisture", "carbon_monoxide", "safety", "problem"],
                            multiple=True
                        )
                    ),
                    vol.Optional(CONF_SAFETY_SENSORS_LABELS, default=[]): selector.LabelSelector(selector.LabelSelectorConfig(multiple=True)),
                }
            ),
        )

    async def async_step_actuators(self, user_input=None):
        """Step 2: Configure actuators."""
        if user_input is not None:
            self.data.update(user_input)
            return await self.async_step_zones()

        return self.async_show_form(
            step_id="actuators",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_SIRENS, default=[]): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain=["switch", "siren"], multiple=True)
                    ),
                    vol.Optional(CONF_SIRENS_LABELS, default=[]): selector.LabelSelector(selector.LabelSelectorConfig(multiple=True)),
                    vol.Optional(CONF_LIGHTS, default=[]): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="light", multiple=True)
                    ),
                    vol.Optional(CONF_LIGHTS_LABELS, default=[]): selector.LabelSelector(selector.LabelSelectorConfig(multiple=True)),
                    vol.Optional(CONF_MEDIA_PLAYERS, default=[]): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="media_player", multiple=True)
                    ),
                    vol.Optional(CONF_MEDIA_PLAYERS_LABELS, default=[]): selector.LabelSelector(selector.LabelSelectorConfig(multiple=True)),
                    vol.Optional(CONF_NOTIFY_SERVICES, default=[]): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain=["notify", "script"], multiple=True)
                    ),
                    vol.Optional(CONF_NOTIFY_SERVICES_LABELS, default=[]): selector.LabelSelector(selector.LabelSelectorConfig(multiple=True)),
                    vol.Optional(CONF_FREE_MOBILE_USER, default=""): str,
                    vol.Optional(CONF_FREE_MOBILE_PASS, default=""): selector.TextSelector(selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)),
                    
                    vol.Optional(CONF_ICLOUD_DEVICES, default=[]): selector.DeviceSelector(selector.DeviceSelectorConfig(integration="icloud", multiple=True)),
                    vol.Optional(CONF_EMERGENCY_CONTACT, default=[]): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain=["notify", "script"], multiple=True)
                    ),
                    vol.Optional(CONF_EMERGENCY_CONTACT_LABELS, default=[]): selector.LabelSelector(selector.LabelSelectorConfig(multiple=True)),
                    vol.Optional(CONF_PRESENCE_SIMULATION_ENTITIES, default=[]): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain=["light", "switch", "cover"], multiple=True)
                    ),
                    vol.Optional(CONF_PRESENCE_SIMULATION_LABELS, default=[]): selector.LabelSelector(selector.LabelSelectorConfig(multiple=True)),
                }
            ),
        )

    async def async_step_zones(self, user_input=None):
        """Step 3: Configure surveillance zones and targeted cameras."""
        if user_input is not None:
            self.data.update(user_input)
            return await self.async_step_logic()

        return self.async_show_form(
            step_id="zones",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_ZONE_LABELS, default=[]): selector.LabelSelector(
                        selector.LabelSelectorConfig(multiple=True)
                    ),
                    vol.Optional(CONF_GLOBAL_CAMERAS, default=[]): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="camera", multiple=True)
                    ),
                    vol.Optional(CONF_GLOBAL_CAMERAS_LABELS, default=[]): selector.LabelSelector(
                        selector.LabelSelectorConfig(multiple=True)
                    ),
                }
            ),
        )

    async def async_step_logic(self, user_input=None):
        """Step 3: Configure logic and delays."""
        if user_input is not None:
            self.data.update(user_input)
            return await self.async_step_mqtt()

        return self.async_show_form(
            step_id="logic",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_PERSONS, default=[]): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="person", multiple=True)
                    ),
                    vol.Optional(CONF_PERSONS_LABELS, default=[]): selector.LabelSelector(selector.LabelSelectorConfig(multiple=True)),
                    vol.Optional(CONF_USERS_CODES, default=""): str,
                    vol.Optional(CONF_DURESS_CODE, default=""): str,
                    vol.Optional(CONF_RFID_TAGS, default=""): str,
                    vol.Optional(CONF_BYPASS_ALLOWED, default=DEFAULT_BYPASS_ALLOWED): bool,
                    vol.Optional(CONF_HEALTH_CHECK, default=DEFAULT_HEALTH_CHECK): bool,
                    vol.Optional(CONF_GEOFENCE_AUTO_ARM, default=DEFAULT_GEOFENCE_AUTO_ARM): bool,
                    vol.Optional(CONF_GEOFENCE_REMINDER, default=DEFAULT_GEOFENCE_REMINDER): bool,
                    vol.Optional(CONF_GEOFENCE_REMINDER_DELAY, default=DEFAULT_GEOFENCE_REMINDER_DELAY): int,
                    vol.Optional(CONF_CROSS_ZONING, default=DEFAULT_CROSS_ZONING): bool,
                    vol.Optional(CONF_CROSS_ZONING_WINDOW, default=DEFAULT_CROSS_ZONING_WINDOW): int,
                    vol.Optional(CONF_PRESENCE_SIMULATION_HISTORY_DAYS, default=DEFAULT_PRESENCE_SIMULATION_HISTORY_DAYS): int,
                    vol.Optional(CONF_SIREN_TEST, default=DEFAULT_SIREN_TEST): bool,
                    vol.Optional(CONF_SIREN_TEST_DAY, default=DEFAULT_SIREN_TEST_DAY): int,
                    vol.Optional(CONF_SIREN_TEST_HOUR, default=DEFAULT_SIREN_TEST_HOUR): int,
                    vol.Optional(CONF_SCHEDULE_ENABLED, default=DEFAULT_SCHEDULE_ENABLED): bool,
                    vol.Optional(CONF_SCHEDULE_ARM_TIME, default=DEFAULT_SCHEDULE_ARM_TIME): str,
                    vol.Optional(CONF_SCHEDULE_DISARM_TIME, default=DEFAULT_SCHEDULE_DISARM_TIME): str,
                    vol.Optional(CONF_SCHEDULE_MODE, default=DEFAULT_SCHEDULE_MODE): str,
                    vol.Optional(CONF_EXIT_DELAY, default=DEFAULT_EXIT_DELAY): int,
                    vol.Optional(CONF_ENTRY_DELAY, default=DEFAULT_ENTRY_DELAY): int,
                    vol.Optional(CONF_SIREN_DURATION, default=DEFAULT_SIREN_DURATION): int,
                    vol.Optional(CONF_CHIME_MODE, default=DEFAULT_CHIME_MODE): bool,
                }
            ),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return DomolinkAlarmOptionsFlow()


    async def async_step_mqtt(self, user_input=None):
        """Step 4: Configure MQTT."""
        if user_input is not None:
            self.data.update(user_input)
            return await self.async_step_backup()

        return self.async_show_form(
            step_id="mqtt",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_MQTT_ENABLED, default=DEFAULT_MQTT_ENABLED): bool,
                    vol.Optional(CONF_MQTT_TOPIC_BASE, default=DEFAULT_MQTT_TOPIC_BASE): str,
                    vol.Optional(CONF_MQTT_REQUIRE_CODE, default=DEFAULT_MQTT_REQUIRE_CODE): bool,
                }
            ),
        )

    async def async_step_backup(self, user_input=None):
        """Step 5: Configure external backup."""
        if user_input is not None:
            self.data.update(user_input)
            title = self.data.get(CONF_NAME, DEFAULT_NAME)
            return self.async_create_entry(title=title, data=self.data)

        return self.async_show_form(
            step_id="backup",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_TELEGRAM_ENABLED, default=DEFAULT_TELEGRAM_ENABLED): bool,
                    vol.Optional(CONF_TELEGRAM_TOKEN, default=""): str,
                    vol.Optional(CONF_TELEGRAM_CHAT_ID, default=""): str,
                    vol.Optional(CONF_FTP_ENABLED, default=DEFAULT_FTP_ENABLED): bool,
                    vol.Optional(CONF_FTP_HOST, default=""): str,
                    vol.Optional(CONF_FTP_PORT, default=DEFAULT_FTP_PORT): int,
                    vol.Optional(CONF_FTP_USER, default=""): str,
                    vol.Optional(CONF_FTP_PASS, default=""): str,
                    vol.Optional(CONF_FTP_PATH, default=DEFAULT_FTP_PATH): str,
                }
            ),
        )

class DomolinkAlarmOptionsFlow(config_entries.OptionsFlow):
    """Handle options."""

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        self.options = dict(self.config_entry.options) if self.config_entry.options else dict(self.config_entry.data)
        return await self.async_step_sensors()

    async def async_step_sensors(self, user_input=None):
        """Step 1: Configure sensors and system name."""
        if user_input is not None:
            self.options.update(user_input)
            return await self.async_step_actuators()

        return self.async_show_form(
            step_id="sensors",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_NAME, default=self.options.get(CONF_NAME, DEFAULT_NAME)): str,
                    vol.Optional(CONF_NIGHT_SENSORS, default=self.options.get(CONF_NIGHT_SENSORS, [])): selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            domain=["binary_sensor", "sensor"],
                            multiple=True
                        )
                    ),
                    vol.Optional(CONF_NIGHT_SENSORS_LABELS, default=self.options.get(CONF_NIGHT_SENSORS_LABELS, [])): selector.LabelSelector(selector.LabelSelectorConfig(multiple=True)),
                    vol.Optional(CONF_OPENING_SENSORS, default=self.options.get(CONF_OPENING_SENSORS, [])): selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            domain=["binary_sensor", "sensor"], 
                            device_class=["door", "window", "opening", "garage_door"],
                            multiple=True
                        )
                    ),
                    vol.Optional(CONF_OPENING_SENSORS_LABELS, default=self.options.get(CONF_OPENING_SENSORS_LABELS, [])): selector.LabelSelector(selector.LabelSelectorConfig(multiple=True)),
                    vol.Optional(CONF_MOTION_SENSORS, default=self.options.get(CONF_MOTION_SENSORS, [])): selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            domain=["binary_sensor", "sensor"],
                            device_class=["motion", "occupancy", "presence"],
                            multiple=True
                        )
                    ),
                    vol.Optional(CONF_MOTION_SENSORS_LABELS, default=self.options.get(CONF_MOTION_SENSORS_LABELS, [])): selector.LabelSelector(selector.LabelSelectorConfig(multiple=True)),
                    vol.Optional(CONF_CAMERAS_ARM_ENTITIES, default=self.options.get(CONF_CAMERAS_ARM_ENTITIES, [])): selector.EntitySelector(selector.EntitySelectorConfig(multiple=True)),
                    vol.Optional(CONF_CAMERAS, default=self.options.get(CONF_CAMERAS, [])): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="camera", multiple=True)
                    ),
                    vol.Optional(CONF_CAMERAS_LABELS, default=self.options.get(CONF_CAMERAS_LABELS, [])): selector.LabelSelector(selector.LabelSelectorConfig(multiple=True)),
                    vol.Optional(CONF_TAMPER_SENSORS, default=self.options.get(CONF_TAMPER_SENSORS, [])): selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            domain=["binary_sensor", "sensor"],
                            device_class=["tamper", "safety", "problem"],
                            multiple=True
                        )
                    ),
                    vol.Optional(CONF_TAMPER_SENSORS_LABELS, default=self.options.get(CONF_TAMPER_SENSORS_LABELS, [])): selector.LabelSelector(selector.LabelSelectorConfig(multiple=True)),
                    vol.Optional(CONF_KEYPADS, default=self.options.get(CONF_KEYPADS, [])): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain=["alarm_control_panel", "sensor"], multiple=True)
                    ),
                    vol.Optional(CONF_KEYPADS_LABELS, default=self.options.get(CONF_KEYPADS_LABELS, [])): selector.LabelSelector(selector.LabelSelectorConfig(multiple=True)),
                    vol.Optional(CONF_SAFETY_SENSORS, default=self.options.get(CONF_SAFETY_SENSORS, [])): selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            domain=["binary_sensor", "sensor"],
                            device_class=["smoke", "gas", "moisture", "carbon_monoxide", "safety", "problem"],
                            multiple=True
                        )
                    ),
                    vol.Optional(CONF_SAFETY_SENSORS_LABELS, default=self.options.get(CONF_SAFETY_SENSORS_LABELS, [])): selector.LabelSelector(selector.LabelSelectorConfig(multiple=True)),
                }
            ),
        )

    async def async_step_actuators(self, user_input=None):
        """Step 2: Configure actuators."""
        if user_input is not None:
            self.options.update(user_input)
            return await self.async_step_zones()

        return self.async_show_form(
            step_id="actuators",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_SIRENS, default=self.options.get(CONF_SIRENS, [])): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain=["switch", "siren"], multiple=True)
                    ),
                    vol.Optional(CONF_SIRENS_LABELS, default=self.options.get(CONF_SIRENS_LABELS, [])): selector.LabelSelector(selector.LabelSelectorConfig(multiple=True)),
                    vol.Optional(CONF_LIGHTS, default=self.options.get(CONF_LIGHTS, [])): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="light", multiple=True)
                    ),
                    vol.Optional(CONF_LIGHTS_LABELS, default=self.options.get(CONF_LIGHTS_LABELS, [])): selector.LabelSelector(selector.LabelSelectorConfig(multiple=True)),
                    vol.Optional(CONF_MEDIA_PLAYERS, default=self.options.get(CONF_MEDIA_PLAYERS, [])): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="media_player", multiple=True)
                    ),
                    vol.Optional(CONF_MEDIA_PLAYERS_LABELS, default=self.options.get(CONF_MEDIA_PLAYERS_LABELS, [])): selector.LabelSelector(selector.LabelSelectorConfig(multiple=True)),
                    vol.Optional(CONF_NOTIFY_SERVICES, default=self.options.get(CONF_NOTIFY_SERVICES, [])): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain=["notify", "script"], multiple=True)
                    ),
                    vol.Optional(CONF_NOTIFY_SERVICES_LABELS, default=self.options.get(CONF_NOTIFY_SERVICES_LABELS, [])): selector.LabelSelector(selector.LabelSelectorConfig(multiple=True)),
                    vol.Optional(CONF_FREE_MOBILE_USER, default=self.options.get(CONF_FREE_MOBILE_USER, "")): str,
                    vol.Optional(CONF_FREE_MOBILE_PASS, default=self.options.get(CONF_FREE_MOBILE_PASS, "")): selector.TextSelector(selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)),
                    
                    vol.Optional(CONF_ICLOUD_DEVICES, default=self.options.get(CONF_ICLOUD_DEVICES, [])): selector.DeviceSelector(selector.DeviceSelectorConfig(integration="icloud", multiple=True)),
                    vol.Optional(CONF_EMERGENCY_CONTACT, default=self.options.get(CONF_EMERGENCY_CONTACT, [])): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain=["notify", "script"], multiple=True)
                    ),
                    vol.Optional(CONF_EMERGENCY_CONTACT_LABELS, default=self.options.get(CONF_EMERGENCY_CONTACT_LABELS, [])): selector.LabelSelector(selector.LabelSelectorConfig(multiple=True)),
                    vol.Optional(CONF_PRESENCE_SIMULATION_ENTITIES, default=self.options.get(CONF_PRESENCE_SIMULATION_ENTITIES, [])): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain=["light", "switch", "cover"], multiple=True)
                    ),
                    vol.Optional(CONF_PRESENCE_SIMULATION_LABELS, default=self.options.get(CONF_PRESENCE_SIMULATION_LABELS, [])): selector.LabelSelector(selector.LabelSelectorConfig(multiple=True)),
                }
            ),
        )

    async def async_step_zones(self, user_input=None):
        """Step 3: Configure surveillance zones and targeted cameras."""
        if user_input is not None:
            self.options.update(user_input)
            return await self.async_step_logic()

        return self.async_show_form(
            step_id="zones",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_ZONE_LABELS, default=self.options.get(CONF_ZONE_LABELS, [])): selector.LabelSelector(
                        selector.LabelSelectorConfig(multiple=True)
                    ),
                    vol.Optional(CONF_GLOBAL_CAMERAS, default=self.options.get(CONF_GLOBAL_CAMERAS, [])): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="camera", multiple=True)
                    ),
                    vol.Optional(CONF_GLOBAL_CAMERAS_LABELS, default=self.options.get(CONF_GLOBAL_CAMERAS_LABELS, [])): selector.LabelSelector(
                        selector.LabelSelectorConfig(multiple=True)
                    ),
                }
            ),
        )

    async def async_step_logic(self, user_input=None):
        """Step 3: Configure logic and delays."""
        if user_input is not None:
            self.options.update(user_input)
            return await self.async_step_mqtt()

        return self.async_show_form(
            step_id="logic",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_PERSONS, default=self.options.get(CONF_PERSONS, [])): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="person", multiple=True)
                    ),
                    vol.Optional(CONF_PERSONS_LABELS, default=self.options.get(CONF_PERSONS_LABELS, [])): selector.LabelSelector(selector.LabelSelectorConfig(multiple=True)),
                    vol.Optional(CONF_USERS_CODES, default=self.options.get(CONF_USERS_CODES, "")): str,
                    vol.Optional(CONF_DURESS_CODE, default=self.options.get(CONF_DURESS_CODE, "")): str,
                    vol.Optional(CONF_RFID_TAGS, default=self.options.get(CONF_RFID_TAGS, "")): str,
                    vol.Optional(CONF_BYPASS_ALLOWED, default=self.options.get(CONF_BYPASS_ALLOWED, DEFAULT_BYPASS_ALLOWED)): bool,
                    vol.Optional(CONF_HEALTH_CHECK, default=self.options.get(CONF_HEALTH_CHECK, DEFAULT_HEALTH_CHECK)): bool,
                    vol.Optional(CONF_GEOFENCE_AUTO_ARM, default=self.options.get(CONF_GEOFENCE_AUTO_ARM, DEFAULT_GEOFENCE_AUTO_ARM)): bool,
                    vol.Optional(CONF_GEOFENCE_REMINDER, default=self.options.get(CONF_GEOFENCE_REMINDER, DEFAULT_GEOFENCE_REMINDER)): bool,
                    vol.Optional(CONF_GEOFENCE_REMINDER_DELAY, default=self.options.get(CONF_GEOFENCE_REMINDER_DELAY, DEFAULT_GEOFENCE_REMINDER_DELAY)): int,
                    vol.Optional(CONF_CROSS_ZONING, default=self.options.get(CONF_CROSS_ZONING, DEFAULT_CROSS_ZONING)): bool,
                    vol.Optional(CONF_CROSS_ZONING_WINDOW, default=self.options.get(CONF_CROSS_ZONING_WINDOW, DEFAULT_CROSS_ZONING_WINDOW)): int,
                    vol.Optional(CONF_PRESENCE_SIMULATION_HISTORY_DAYS, default=self.options.get(CONF_PRESENCE_SIMULATION_HISTORY_DAYS, DEFAULT_PRESENCE_SIMULATION_HISTORY_DAYS)): int,
                    vol.Optional(CONF_SIREN_TEST, default=self.options.get(CONF_SIREN_TEST, DEFAULT_SIREN_TEST)): bool,
                    vol.Optional(CONF_SIREN_TEST_DAY, default=self.options.get(CONF_SIREN_TEST_DAY, DEFAULT_SIREN_TEST_DAY)): int,
                    vol.Optional(CONF_SIREN_TEST_HOUR, default=self.options.get(CONF_SIREN_TEST_HOUR, DEFAULT_SIREN_TEST_HOUR)): int,
                    vol.Optional(CONF_SCHEDULE_ENABLED, default=self.options.get(CONF_SCHEDULE_ENABLED, DEFAULT_SCHEDULE_ENABLED)): bool,
                    vol.Optional(CONF_SCHEDULE_ARM_TIME, default=self.options.get(CONF_SCHEDULE_ARM_TIME, DEFAULT_SCHEDULE_ARM_TIME)): str,
                    vol.Optional(CONF_SCHEDULE_DISARM_TIME, default=self.options.get(CONF_SCHEDULE_DISARM_TIME, DEFAULT_SCHEDULE_DISARM_TIME)): str,
                    vol.Optional(CONF_SCHEDULE_MODE, default=self.options.get(CONF_SCHEDULE_MODE, DEFAULT_SCHEDULE_MODE)): str,
                    vol.Optional(CONF_EXIT_DELAY, default=self.options.get(CONF_EXIT_DELAY, DEFAULT_EXIT_DELAY)): int,
                    vol.Optional(CONF_ENTRY_DELAY, default=self.options.get(CONF_ENTRY_DELAY, DEFAULT_ENTRY_DELAY)): int,
                    vol.Optional(CONF_SIREN_DURATION, default=self.options.get(CONF_SIREN_DURATION, DEFAULT_SIREN_DURATION)): int,
                    vol.Optional(CONF_CHIME_MODE, default=self.options.get(CONF_CHIME_MODE, DEFAULT_CHIME_MODE)): bool,
                }
            ),
        )


    async def async_step_mqtt(self, user_input=None):
        """Step 4: Configure MQTT options."""
        if user_input is not None:
            self.options.update(user_input)
            return await self.async_step_backup()

        return self.async_show_form(
            step_id="mqtt",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_MQTT_ENABLED, default=self.options.get(CONF_MQTT_ENABLED, DEFAULT_MQTT_ENABLED)): bool,
                    vol.Optional(CONF_MQTT_TOPIC_BASE, default=self.options.get(CONF_MQTT_TOPIC_BASE, DEFAULT_MQTT_TOPIC_BASE)): str,
                    vol.Optional(CONF_MQTT_REQUIRE_CODE, default=self.options.get(CONF_MQTT_REQUIRE_CODE, DEFAULT_MQTT_REQUIRE_CODE)): bool,
                }
            ),
        )


    async def async_step_backup(self, user_input=None):
        """Step 5: Configure external backup options."""
        if user_input is not None:
            self.options.update(user_input)
            return self.async_create_entry(title="", data=self.options)

        return self.async_show_form(
            step_id="backup",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_TELEGRAM_ENABLED, default=self.options.get(CONF_TELEGRAM_ENABLED, DEFAULT_TELEGRAM_ENABLED)): bool,
                    vol.Optional(CONF_TELEGRAM_TOKEN, default=self.options.get(CONF_TELEGRAM_TOKEN, "")): str,
                    vol.Optional(CONF_TELEGRAM_CHAT_ID, default=self.options.get(CONF_TELEGRAM_CHAT_ID, "")): str,
                    vol.Optional(CONF_FTP_ENABLED, default=self.options.get(CONF_FTP_ENABLED, DEFAULT_FTP_ENABLED)): bool,
                    vol.Optional(CONF_FTP_HOST, default=self.options.get(CONF_FTP_HOST, "")): str,
                    vol.Optional(CONF_FTP_PORT, default=self.options.get(CONF_FTP_PORT, DEFAULT_FTP_PORT)): int,
                    vol.Optional(CONF_FTP_USER, default=self.options.get(CONF_FTP_USER, "")): str,
                    vol.Optional(CONF_FTP_PASS, default=self.options.get(CONF_FTP_PASS, "")): str,
                    vol.Optional(CONF_FTP_PATH, default=self.options.get(CONF_FTP_PATH, DEFAULT_FTP_PATH)): str,
                    vol.Optional(CONF_MEDIA_PATH, default=self.options.get(CONF_MEDIA_PATH, DEFAULT_MEDIA_PATH)): str,
                }
            ),
        )
