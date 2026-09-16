"""Smart presence simulation manager based on recorder history replay."""
from datetime import timedelta
import logging
import random

from homeassistant.components.alarm_control_panel import AlarmControlPanelState
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util.dt import utcnow

from .const import (
    CONF_PRESENCE_SIMULATION_ENTITIES,
    CONF_PRESENCE_SIMULATION_HISTORY_DAYS,
    DEFAULT_PRESENCE_SIMULATION_HISTORY_DAYS,
)

_LOGGER = logging.getLogger(__name__)


class PresenceSimulator:
    """Manages smart presence simulation by replaying historical entity states."""

    def __init__(
        self,
        hass: HomeAssistant,
        get_config_cb,
        log_event_cb,
        write_state_cb,
        get_alarm_state_cb,
    ):
        """Initialize PresenceSimulator."""
        self.hass = hass
        self._get_config = get_config_cb
        self._log_event = log_event_cb
        self._write_state = write_state_cb
        self._get_alarm_state = get_alarm_state_cb

        self.forced = False
        self.events = []
        self._unsub_interval = None

    def _cfg(self, key, default=None):
        return self._get_config(key, default)

    @property
    def entities(self) -> list[str]:
        """Return configured simulation entities."""
        return self._cfg(CONF_PRESENCE_SIMULATION_ENTITIES, []) or []

    @property
    def history_days(self) -> int:
        """Return number of history days for replay."""
        try:
            return int(
                self._cfg(
                    CONF_PRESENCE_SIMULATION_HISTORY_DAYS,
                    DEFAULT_PRESENCE_SIMULATION_HISTORY_DAYS,
                )
                or DEFAULT_PRESENCE_SIMULATION_HISTORY_DAYS
            )
        except (ValueError, TypeError):
            return DEFAULT_PRESENCE_SIMULATION_HISTORY_DAYS

    @property
    def is_running(self) -> bool:
        """Return True if simulation task is active."""
        return self._unsub_interval is not None

    def start(self):
        """Start presence simulation based on historic recorder data."""
        if not self.entities:
            return

        if self._unsub_interval is None:
            _LOGGER.info(
                "Domolink: Démarrage de la simulation de présence (Replay J-%d sur %d appareils)",
                self.history_days,
                len(self.entities),
            )
            self._log_event(
                f"Démarrage Simulation Présence ({len(self.entities)} appareils)"
            )
            self._unsub_interval = async_track_time_interval(
                self.hass,
                self._async_tick,
                timedelta(minutes=1),
            )
            # Run one tick immediately
            self.hass.async_create_task(self._async_tick())

    def stop(self):
        """Stop running presence simulation."""
        if self._unsub_interval:
            self._unsub_interval()
            self._unsub_interval = None
            _LOGGER.info("Domolink: Arrêt de la simulation de présence")
            self._log_event("Arrêt Simulation Présence")

    async def async_start(self):
        """Service handler to start presence simulation manually."""
        self.forced = True
        self.start()
        self._write_state()

    async def async_stop(self):
        """Service handler to stop presence simulation manually."""
        self.forced = False
        self.stop()
        self._write_state()

    async def async_toggle(self):
        """Service handler to toggle presence simulation."""
        if self.is_running:
            await self.async_stop()
        else:
            await self.async_start()

    async def _async_tick(self, _now=None):
        """Replay historic states of presence simulation entities."""
        is_active = self.forced or (
            self._get_alarm_state() == AlarmControlPanelState.ARMED_AWAY
        )
        if not is_active or not self.entities:
            return

        try:
            from homeassistant.components.recorder import get_instance, history

            now = utcnow()
            # Adding random jitter of +/- 15 minutes to make replay look natural
            jitter_seconds = random.randint(-900, 900)
            past_now = (
                now
                - timedelta(days=self.history_days)
                + timedelta(seconds=jitter_seconds)
            )
            past_start = past_now - timedelta(minutes=2)

            instance = get_instance(self.hass)
            states = await instance.async_add_executor_job(
                history.get_significant_states,
                self.hass,
                past_start,
                past_now,
                self.entities,
            )

            for entity_id, entity_states in (states or {}).items():
                if not entity_states:
                    continue
                target_state = entity_states[-1].state
                if target_state not in ("on", "off"):
                    continue

                current = self.hass.states.get(entity_id)
                if current and current.state != target_state:
                    domain = entity_id.split(".")[0]
                    if domain in ("light", "switch", "cover"):
                        if domain == "cover":
                            service = (
                                "open_cover"
                                if target_state in ("open", "on")
                                else "close_cover"
                            )
                        else:
                            service = "turn_on" if target_state == "on" else "turn_off"

                        _LOGGER.info(
                            "Domolink Simulation Présence: %s -> %s (rejoué depuis J-%d)",
                            entity_id,
                            target_state,
                            self.history_days,
                        )
                        friendly_name = current.name or entity_id
                        self._log_event(
                            f"Simulation Présence: {friendly_name} -> {target_state}"
                        )

                        sim_event = {
                            "time": utcnow().isoformat(),
                            "entity_id": entity_id,
                            "name": friendly_name,
                            "state": target_state,
                            "domain": domain,
                            "history_days": self.history_days,
                        }
                        self.events.insert(0, sim_event)
                        if len(self.events) > 50:
                            self.events = self.events[:50]
                        self._write_state()

                        await self.hass.services.async_call(
                            domain, service, {"entity_id": entity_id}
                        )
        except Exception as e:
            _LOGGER.debug("Domolink: Simulation Présence tick error: %s", e)
