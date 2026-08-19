"""Button platform for Domolink Alarm."""
from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN, DEFAULT_NAME, CONF_NAME

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Set up the button platform."""
    alarm_entity = hass.data[DOMAIN][entry.entry_id].get("entity")
    name = entry.data.get(CONF_NAME, DEFAULT_NAME)
    
    async_add_entities([DomolinkPanicButton(entry.entry_id, name, alarm_entity)])


class DomolinkPanicButton(ButtonEntity):
    """SOS Panic Button."""

    def __init__(self, entry_id, alarm_name, alarm_entity):
        """Initialize."""
        self._alarm_entity = alarm_entity
        self._attr_name = "SOS Panic"
        self._attr_has_entity_name = True
        self._attr_unique_id = f"domolink_sos_{entry_id}"
        self._attr_icon = "mdi:alert-decagram"
        
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"domolink_alarm_{entry_id}")},
            name=alarm_name,
            manufacturer="Domolink",
            model="Domolink Smart Alarm",
        )

    async def async_press(self) -> None:
        """Handle the button press."""
        if self._alarm_entity:
            await self._alarm_entity._async_trigger_alarm("Bouton Panique SOS")
