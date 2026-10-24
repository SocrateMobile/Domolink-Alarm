import mimetypes
import os

from aiohttp import web
from homeassistant.components import frontend
from homeassistant.components.http import HomeAssistantView
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, VERSION

PLATFORMS = ["alarm_control_panel", "button", "sensor"]


class DomolinkMediaView(HomeAssistantView):
    """Authenticated HTTP view to serve Domolink Alarm media files outside www."""

    url = "/api/domolink_alarm/media/{filename:.*}"
    name = "api:domolink_alarm:media"
    requires_auth = True

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the media view."""
        self.hass = hass

    async def get(self, request: web.Request, filename: str) -> web.StreamResponse:
        """Serve the requested media file after path traversal checks."""
        if not filename or ".." in filename or filename.startswith("/") or "\\" in filename:
            return web.Response(status=403, text="Forbidden")

        base_dir = os.path.realpath(self.hass.config.path("domolink_alarm_media"))
        target_path = os.path.realpath(os.path.join(base_dir, filename))

        if not (target_path == base_dir or target_path.startswith(base_dir + os.sep)):
            return web.Response(status=403, text="Forbidden")

        def _check_file() -> bool:
            return os.path.isfile(target_path)

        exists = await self.hass.async_add_executor_job(_check_file)
        if not exists:
            return web.Response(status=404, text="Not found")

        content_type, _ = mimetypes.guess_type(target_path)
        headers = {}
        if content_type:
            headers["Content-Type"] = content_type

        return web.FileResponse(target_path, headers=headers)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Domolink Alarm from a config entry."""
    hass.data.setdefault(DOMAIN, {}).setdefault(entry.entry_id, {})

    if not hass.data[DOMAIN].get("_media_view_registered"):
        hass.http.register_view(DomolinkMediaView(hass))
        hass.data[DOMAIN]["_media_view_registered"] = True

    # Register frontend panel
    frontend_dir = hass.config.path("custom_components/domolink_alarm/frontend")
    if await hass.async_add_executor_job(os.path.exists, frontend_dir):
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
                        "module_url": f"/domolink_alarm_panel/domolink-panel.js?v={VERSION}",
                    }
                },
                require_admin=False,
            )
        except ValueError:
            # Panel already registered
            pass

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Listen for options updates so changes take effect without restarting HA (Fix #5)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update in-place without destroying active alarm state/listeners."""
    entry_data = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if isinstance(entry_data, dict) and entry_data.get("entity") is not None:
        alarm_entity = entry_data["entity"]
        alarm_entity._load_config()
        alarm_entity.async_write_ha_state()
    else:
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
