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
            return await self.async_step_logic()

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
                        selector.EntitySelectorConfig(domain="notify", multiple=True)
                    ),
                    vol.Optional(CONF_NOTIFY_SERVICES_LABELS, default=[]): selector.LabelSelector(selector.LabelSelectorConfig(multiple=True)),
                    vol.Optional(CONF_PRESENCE_SIMULATION_ENTITIES, default=[]): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain=["light", "switch", "cover"], multiple=True)
                    ),
                    vol.Optional(CONF_PRESENCE_SIMULATION_LABELS, default=[]): selector.LabelSelector(selector.LabelSelectorConfig(multiple=True)),
                }
            ),
        )

    async def async_step_logic(self, user_input=None):
        """Step 3: Configure logic and delays."""
        if user_input is not None:
            self.data.update(user_input)
            title = self.data.get(CONF_NAME, DEFAULT_NAME)
            return self.async_create_entry(title=title, data=self.data)

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
            return await self.async_step_logic()

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
                        selector.EntitySelectorConfig(domain="notify", multiple=True)
                    ),
                    vol.Optional(CONF_NOTIFY_SERVICES_LABELS, default=self.options.get(CONF_NOTIFY_SERVICES_LABELS, [])): selector.LabelSelector(selector.LabelSelectorConfig(multiple=True)),
                    vol.Optional(CONF_PRESENCE_SIMULATION_ENTITIES, default=self.options.get(CONF_PRESENCE_SIMULATION_ENTITIES, [])): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain=["light", "switch", "cover"], multiple=True)
                    ),
                    vol.Optional(CONF_PRESENCE_SIMULATION_LABELS, default=self.options.get(CONF_PRESENCE_SIMULATION_LABELS, [])): selector.LabelSelector(selector.LabelSelectorConfig(multiple=True)),
                }
            ),
        )

    async def async_step_logic(self, user_input=None):
        """Step 3: Configure logic and delays."""
        if user_input is not None:
            self.options.update(user_input)
            return self.async_create_entry(title="", data=self.options)

        return self.async_show_form(
            step_id="logic",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_PERSONS, default=self.options.get(CONF_PERSONS, [])): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="person", multiple=True)
                    ),
                    vol.Optional(CONF_PERSONS_LABELS, default=self.options.get(CONF_PERSONS_LABELS, [])): selector.LabelSelector(selector.LabelSelectorConfig(multiple=True)),
                    vol.Required(CONF_USERS_CODES, default=self.options.get(CONF_USERS_CODES, "")): str,
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
                    vol.Optional(CONF_EXIT_DELAY, default=self.options.get(CONF_EXIT_DELAY, DEFAULT_EXIT_DELAY)): int,
                    vol.Optional(CONF_ENTRY_DELAY, default=self.options.get(CONF_ENTRY_DELAY, DEFAULT_ENTRY_DELAY)): int,
                    vol.Optional(CONF_SIREN_DURATION, default=self.options.get(CONF_SIREN_DURATION, DEFAULT_SIREN_DURATION)): int,
                    vol.Optional(CONF_CHIME_MODE, default=self.options.get(CONF_CHIME_MODE, DEFAULT_CHIME_MODE)): bool,
                }
            ),
        )
