"""Config flow for Domolink Alarm integration."""
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    DOMAIN,
    CONF_OPENING_SENSORS,
    CONF_MOTION_SENSORS,
    CONF_CAMERAS,
    CONF_TAMPER_SENSORS,
    CONF_KEYPADS,
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
    DEFAULT_EXIT_DELAY,
    DEFAULT_ENTRY_DELAY,
    DEFAULT_SIREN_DURATION,
    DEFAULT_BYPASS_ALLOWED,
    DEFAULT_HEALTH_CHECK,
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
        """Step 1: Configure sensors."""
        if user_input is not None:
            self.data.update(user_input)
            return await self.async_step_actuators()

        return self.async_show_form(
            step_id="sensors",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_OPENING_SENSORS, default=[]): selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            domain=["binary_sensor", "sensor"], 
                            device_class=["door", "window", "opening", "garage_door"],
                            multiple=True
                        )
                    ),
                    vol.Optional(CONF_MOTION_SENSORS, default=[]): selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            domain=["binary_sensor", "sensor"],
                            device_class=["motion", "occupancy", "presence"],
                            multiple=True
                        )
                    ),
                    vol.Optional(CONF_CAMERAS, default=[]): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="camera", multiple=True)
                    ),
                    vol.Optional(CONF_TAMPER_SENSORS, default=[]): selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            domain=["binary_sensor", "sensor"],
                            device_class=["tamper", "safety", "problem"],
                            multiple=True
                        )
                    ),
                    vol.Optional(CONF_KEYPADS, default=[]): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain=["alarm_control_panel", "sensor"], multiple=True)
                    ),
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
                    vol.Optional(CONF_LIGHTS, default=[]): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="light", multiple=True)
                    ),
                    vol.Optional(CONF_MEDIA_PLAYERS, default=[]): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="media_player", multiple=True)
                    ),
                    vol.Optional(CONF_NOTIFY_SERVICES, default=[]): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="notify", multiple=True)
                    ),
                }
            ),
        )

    async def async_step_logic(self, user_input=None):
        """Step 3: Configure logic and delays."""
        if user_input is not None:
            self.data.update(user_input)
            return self.async_create_entry(title="Domolink Alarm", data=self.data)

        return self.async_show_form(
            step_id="logic",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERS_CODES): str,
                    vol.Optional(CONF_DURESS_CODE, default=""): str,
                    vol.Optional(CONF_BYPASS_ALLOWED, default=DEFAULT_BYPASS_ALLOWED): bool,
                    vol.Optional(CONF_HEALTH_CHECK, default=DEFAULT_HEALTH_CHECK): bool,
                    vol.Optional(CONF_EXIT_DELAY, default=DEFAULT_EXIT_DELAY): int,
                    vol.Optional(CONF_ENTRY_DELAY, default=DEFAULT_ENTRY_DELAY): int,
                    vol.Optional(CONF_SIREN_DURATION, default=DEFAULT_SIREN_DURATION): int,
                }
            ),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return DomolinkAlarmOptionsFlow(config_entry)


class DomolinkAlarmOptionsFlow(config_entries.OptionsFlow):
    """Handle options."""

    def __init__(self, config_entry):
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERS_CODES, default=self.config_entry.data.get(CONF_USERS_CODES, "")): str,
                    vol.Optional(CONF_DURESS_CODE, default=self.config_entry.data.get(CONF_DURESS_CODE, "")): str,
                    vol.Optional(CONF_BYPASS_ALLOWED, default=self.config_entry.data.get(CONF_BYPASS_ALLOWED, DEFAULT_BYPASS_ALLOWED)): bool,
                    vol.Optional(CONF_HEALTH_CHECK, default=self.config_entry.data.get(CONF_HEALTH_CHECK, DEFAULT_HEALTH_CHECK)): bool,
                    vol.Optional(CONF_EXIT_DELAY, default=self.config_entry.data.get(CONF_EXIT_DELAY, DEFAULT_EXIT_DELAY)): int,
                    vol.Optional(CONF_ENTRY_DELAY, default=self.config_entry.data.get(CONF_ENTRY_DELAY, DEFAULT_ENTRY_DELAY)): int,
                    vol.Optional(CONF_SIREN_DURATION, default=self.config_entry.data.get(CONF_SIREN_DURATION, DEFAULT_SIREN_DURATION)): int,
                }
            ),
        )
