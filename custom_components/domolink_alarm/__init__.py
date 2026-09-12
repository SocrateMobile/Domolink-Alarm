import os
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.components import frontend

from .const import DOMAIN

PLATFORMS = ["alarm_control_panel", "button", "sensor", "update"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Domolink Alarm from a config entry."""
    hass.data.setdefault(DOMAIN, {}).setdefault(entry.entry_id, {})

    # Register frontend panel
    frontend_dir = hass.config.path("custom_components/domolink_alarm/frontend")
    if os.path.exists(frontend_dir):
        if hasattr(hass.http, "async_register_static_paths"):
            from homeassistant.components.http import StaticPathConfig
            await hass.http.async_register_static_paths([
                StaticPathConfig("/domolink_alarm_panel", frontend_dir, False)
            ])
        else:
            hass.http.register_static_path(
                "/domolink_alarm_panel",
                frontend_dir,
                cache_headers=False,
            )
            
        try:
            frontend.async_register_built_in_panel(
                hass,
                component_name="custom",
                sidebar_title="Domolink Alarm",
                sidebar_icon="mdi:shield-home",
                frontend_url_path="domolink_alarm",
                config={
                    "_panel_custom": {
                        "name": "domolink-panel",
                        "module_url": "/domolink_alarm_panel/domolink-panel.js?v=0.9.79",
                    }
                },
                require_admin=False,
            )
        except ValueError:
            # Panel already registered
            pass

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def _async_handle_check_updates(call):
        """Handle manual update check."""
        for ed in hass.data.get(DOMAIN, {}).values():
            if isinstance(ed, dict) and "update_entity" in ed:
                await ed["update_entity"].async_update()

    async def _async_handle_install_update(call):
        """Handle install update request."""
        backup = call.data.get("backup", True)
        for ed in hass.data.get(DOMAIN, {}).values():
            if isinstance(ed, dict) and "update_entity" in ed:
                await ed["update_entity"].async_install(backup=backup)
                break

    if not hass.services.has_service(DOMAIN, "check_updates"):
        hass.services.async_register(DOMAIN, "check_updates", _async_handle_check_updates)
    if not hass.services.has_service(DOMAIN, "install_update"):
        hass.services.async_register(DOMAIN, "install_update", _async_handle_install_update)

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
