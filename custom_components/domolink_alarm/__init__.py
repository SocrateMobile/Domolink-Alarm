"""The Domolink Alarm integration."""
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN

PLATFORMS = ["alarm_control_panel", "button", "sensor"]


import os
from homeassistant.components import frontend

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Domolink Alarm from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    # Register frontend panel
    frontend_dir = hass.config.path("custom_components/domolink_alarm/frontend")
    if os.path.exists(frontend_dir):
        hass.http.register_static_path(
            "/domolink_alarm_panel",
            frontend_dir,
            cache_headers=False,
        )
        try:
            frontend.async_register_panel(
                hass,
                "domolink_alarm",
                "domolink-panel",
                sidebar_title="Domolink Alarm",
                sidebar_icon="mdi:shield-home",
                module_url="/domolink_alarm_panel/domolink-panel.js",
                require_admin=False,
                config={},
            )
        except ValueError:
            # Panel already registered
            pass

    # Listen for options updates so changes take effect without restarting HA (Fix #5)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update — automatically reload the integration."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        try:
            frontend.async_remove_panel(hass, "domolink_alarm")
        except Exception:
            pass

    return unload_ok
