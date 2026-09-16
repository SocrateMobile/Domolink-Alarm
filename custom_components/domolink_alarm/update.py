"""Update platform for Domolink Alarm integration."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from datetime import timedelta

import aiohttp

from homeassistant.components import frontend
from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.event import async_track_time_interval

from .const import CONF_NAME, DEFAULT_NAME, DOMAIN, VERSION

_LOGGER = logging.getLogger(__name__)

GITHUB_REPO = "SocrateMobile/Domolink-Alarm"
GITHUB_LATEST_RELEASE_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
UPDATE_CHECK_INTERVAL = timedelta(hours=4)


def parse_version(ver_str: str) -> tuple:
    """Safely parse semantic versions or release tags into integer tuples."""
    if not ver_str:
        return (0, 0, 0)
    clean = ver_str.lstrip("v").strip()
    parts = []
    for segment in clean.split("."):
        digits = re.match(r"^\d+", segment)
        parts.append(int(digits.group(0)) if digits else 0)
    return tuple(parts)


def get_installed_version() -> str:
    """Read version directly from manifest.json to avoid hardcoding."""
    manifest_path = os.path.join(os.path.dirname(__file__), "manifest.json")
    try:
        if os.path.exists(manifest_path):
            with open(manifest_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return str(data.get("version", VERSION))
    except Exception as err:
        _LOGGER.warning("Could not read manifest.json version: %s", err)
    return VERSION


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up the update platform for Domolink Alarm."""
    entry_data = hass.data.setdefault(DOMAIN, {}).setdefault(entry.entry_id, {})
    alarm_entity = entry_data.get("entity")
    name = entry.data.get(CONF_NAME, DEFAULT_NAME)
    installed_ver = get_installed_version()

    update_entity = DomolinkAlarmUpdateEntity(
        hass=hass,
        entry_id=entry.entry_id,
        alarm_name=name,
        installed_version=installed_ver,
        alarm_entity=alarm_entity,
    )

    entry_data["update_entity"] = update_entity
    async_add_entities([update_entity], False)


class DomolinkAlarmUpdateEntity(UpdateEntity):
    """Representation of the Domolink Alarm update entity."""

    _attr_has_entity_name = True
    _attr_device_class = UpdateDeviceClass.FIRMWARE
    _attr_supported_features = UpdateEntityFeature.RELEASE_NOTES

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        alarm_name: str,
        installed_version: str,
        alarm_entity=None,
    ) -> None:
        """Initialize the update entity."""
        self.hass = hass
        self._entry_id = entry_id
        self._alarm_entity = alarm_entity
        self._attr_name = "Mise à jour"
        self._attr_unique_id = f"domolink_alarm_update_{entry_id}"
        self._attr_title = "Domolink Alarm"

        self._attr_installed_version = installed_version
        self._attr_latest_version = installed_version
        self._attr_release_summary: str | None = None
        self._attr_release_url: str | None = None
        self._release_body: str | None = None
        self._zip_download_url: str | None = None

        self._attr_in_progress = False
        self._attr_update_percentage: int | None = None

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"domolink_alarm_{entry_id}")},
            name=alarm_name,
            manufacturer="Domolink",
            model="Domolink Smart Alarm",
            sw_version=installed_version,
        )

        self._unsub_interval = None

    async def async_added_to_hass(self) -> None:
        """Register periodic update checks and initial check."""
        await super().async_added_to_hass()
        self._unsub_interval = async_track_time_interval(
            self.hass, self._async_periodic_check, UPDATE_CHECK_INTERVAL
        )
        # Perform initial check in background
        self.hass.async_create_task(self.async_update())

    async def async_will_remove_from_hass(self) -> None:
        """Clean up when entity is removed."""
        if self._unsub_interval:
            self._unsub_interval()
            self._unsub_interval = None
        await super().async_will_remove_from_hass()

    async def _async_periodic_check(self, _now=None) -> None:
        """Periodic check called by timer."""
        await self.async_update()

    async def async_update(self) -> None:
        """Check GitHub for the latest release."""
        try:
            session = async_get_clientsession(self.hass)
            headers = {
                "User-Agent": "Domolink-Alarm-HA",
                "Accept": "application/vnd.github.v3+json",
            }
            async with session.get(
                GITHUB_LATEST_RELEASE_URL, headers=headers, timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                if resp.status != 200:
                    _LOGGER.debug(
                        "GitHub release check returned HTTP %s for %s",
                        resp.status,
                        GITHUB_REPO,
                    )
                    return

                data = await resp.json()
                tag = data.get("tag_name", "").strip()
                clean_tag = re.sub(r"^[vV]", "", tag)
                if not clean_tag:
                    return

                self._attr_latest_version = clean_tag
                self._attr_release_summary = data.get("name") or f"Version {clean_tag}"
                self._release_body = data.get("body") or ""
                self._attr_release_url = data.get("html_url")
                self._zip_download_url = (
                    f"https://github.com/{GITHUB_REPO}/archive/refs/tags/{tag}.zip"
                )

                has_update = parse_semver(clean_tag) > parse_semver(self._attr_installed_version)

                # Update left sidebar panel badge & icon
                self._update_sidebar_panel(has_update)

                # Sync update state to main alarm entity attributes if available
                alarm_ent = self._alarm_entity or self.hass.data.get(DOMAIN, {}).get(self._entry_id, {}).get("entity")
                if alarm_ent:
                    alarm_ent._update_available = has_update
                    alarm_ent._latest_version = clean_tag
                    alarm_ent._release_notes = self._release_body
                    alarm_ent._release_url = self._attr_release_url
                    try:
                        alarm_ent.async_write_ha_state()
                    except Exception:
                        pass

                if getattr(self, "hass", None) and getattr(self, "entity_id", None):
                    try:
                        self.async_write_ha_state()
                    except Exception:
                        pass
                _LOGGER.info(
                    "Domolink Alarm update check: installed=%s, latest=%s, update_available=%s",
                    self._attr_installed_version,
                    clean_tag,
                    has_update,
                )
        except asyncio.TimeoutError:
            _LOGGER.debug("Timeout checking GitHub releases for Domolink Alarm")
        except Exception as err:
            _LOGGER.warning("Error checking GitHub releases for Domolink Alarm: %s", err)

    def _update_sidebar_panel(self, update_available: bool) -> None:
        """Update the Home Assistant left sidebar panel badge/title."""
        try:
            title = "Domolink Alarm 🔴" if update_available else "Domolink Alarm"
            icon = "mdi:shield-alert" if update_available else "mdi:shield-home"
            frontend.async_register_built_in_panel(
                self.hass,
                component_name="custom",
                sidebar_title=title,
                sidebar_icon=icon,
                frontend_url_path="domolink_alarm",
                config={
                    "_panel_custom": {
                        "name": "domolink-panel",
                        "module_url": f"/domolink_alarm_panel/domolink-panel.js?v={self._attr_installed_version}",
                    }
                },
                require_admin=False,
                update=True,
            )
        except Exception as err:
            _LOGGER.debug("Could not update sidebar panel registration: %s", err)

    async def async_release_notes(self) -> str | None:
        """Return release notes in markdown."""
        return self._release_body

    async def async_install(
        self, version: str | None = None, backup: bool = True, **kwargs
    ) -> None:
        """Inform user to perform update safely via HACS to maintain system security."""
        await self.async_update()

        target_version = version or self._attr_latest_version
        clean_tag = re.sub(r"^[vV]", "", target_version)
        release_url = self._attr_release_url or f"https://github.com/{GITHUB_REPO}/releases/tag/v{clean_tag}"

        _LOGGER.warning(
            "Domolink Alarm: Les mises à jour directes par écrasement de fichiers ont été désactivées pour des raisons de sécurité. Veuillez mettre à jour via HACS (%s)",
            release_url,
        )

        # Notify user in Home Assistant UI
        if "persistent_notification" in self.hass.config.components:
            await self.hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "title": "Mise à jour Domolink Alarm",
                    "message": (
                        f"Une nouvelle version **{clean_tag}** de **Domolink Alarm** est disponible.\n\n"
                        f"Pour garantir la sécurité et l'intégrité de votre serveur Home Assistant, "
                        f"veuillez appliquer cette mise à jour depuis **HACS** (Home Assistant Community Store).\n\n"
                        f"[Voir les notes de version sur GitHub]({release_url})"
                    ),
                    "notification_id": "domolink_alarm_update_notice",
                },
            )
