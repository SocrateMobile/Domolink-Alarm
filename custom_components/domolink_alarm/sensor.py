"""Sensor platform for Domolink Alarm."""
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN, DEFAULT_NAME, CONF_NAME

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Set up the sensor platform."""
    alarm_entity = hass.data[DOMAIN][entry.entry_id].get("entity")
    name = entry.data.get(CONF_NAME, DEFAULT_NAME)
    
    sensor = DomolinkEventLogSensor(entry.entry_id, name, alarm_entity)
    async_add_entities([sensor])
    
    if alarm_entity:
        alarm_entity.set_log_sensor(sensor)


class DomolinkEventLogSensor(SensorEntity):
    """Event log sensor for Domolink Alarm."""

    def __init__(self, entry_id, alarm_name, alarm_entity):
        """Initialize."""
        self._alarm_entity = alarm_entity
        self._attr_name = "Journal des événements"
        self._attr_has_entity_name = True
        self._attr_unique_id = f"domolink_event_log_{entry_id}"
        self._attr_icon = "mdi:format-list-bulleted"
        
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"domolink_alarm_{entry_id}")},
            name=alarm_name,
            manufacturer="Domolink",
            model="Domolink Smart Alarm",
        )
        
        self._events = []
        self._attr_native_value = "Démarrage"

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {
            "events": self._events,
        }

    @callback
    def async_add_event(self, timestamp, message):
        """Add an event to the log."""
        self._attr_native_value = message
        self._events.insert(0, {"time": timestamp, "message": message})
        
        # Keep only the last 20 events
        if len(self._events) > 20:
            self._events = self._events[:20]
            
        self.async_write_ha_state()
