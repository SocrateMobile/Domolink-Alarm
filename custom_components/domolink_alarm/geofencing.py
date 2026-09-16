"""Geofencing, proximity tracking and reminder manager for Domolink Alarm."""
import logging

from homeassistant.components.alarm_control_panel import AlarmControlPanelState
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_call_later

from .const import (
    CONF_GEOFENCE_APPROACH_DISTANCE,
    CONF_GEOFENCE_APPROACH_REMINDER,
    CONF_GEOFENCE_AUTO_ARM,
    CONF_GEOFENCE_REMINDER,
    CONF_GEOFENCE_REMINDER_DELAY,
    CONF_PERSONS,
    DEFAULT_GEOFENCE_APPROACH_DISTANCE,
    DEFAULT_GEOFENCE_APPROACH_REMINDER,
    DEFAULT_GEOFENCE_AUTO_ARM,
    DEFAULT_GEOFENCE_REMINDER,
    DEFAULT_GEOFENCE_REMINDER_DELAY,
)

_LOGGER = logging.getLogger(__name__)


class GeofenceManager:
    """Manages zone tracking, auto-arm on departure, proximity approach and actionable reminders."""

    def __init__(
        self,
        hass: HomeAssistant,
        alarm_entity,
        get_config_cb,
        log_event_cb,
        write_state_cb,
    ):
        """Initialize GeofenceManager."""
        self.hass = hass
        self.alarm_entity = alarm_entity
        self._get_config = get_config_cb
        self._log_event = log_event_cb
        self._write_state = write_state_cb

        self.reminder_task = None
        self.snooze_until = 0.0
        self.last_approach_notif_ts = 0.0

    def _cfg(self, key, default=None):
        return self._get_config(key, default)

    @property
    def auto_arm(self) -> bool:
        return bool(self._cfg(CONF_GEOFENCE_AUTO_ARM, DEFAULT_GEOFENCE_AUTO_ARM))

    @property
    def reminder_enabled(self) -> bool:
        return bool(self._cfg(CONF_GEOFENCE_REMINDER, DEFAULT_GEOFENCE_REMINDER))

    @property
    def reminder_delay(self) -> int:
        try:
            return int(
                self._cfg(CONF_GEOFENCE_REMINDER_DELAY, DEFAULT_GEOFENCE_REMINDER_DELAY)
                or DEFAULT_GEOFENCE_REMINDER_DELAY
            )
        except (ValueError, TypeError):
            return DEFAULT_GEOFENCE_REMINDER_DELAY

    @property
    def approach_reminder(self) -> bool:
        return bool(
            self._cfg(
                CONF_GEOFENCE_APPROACH_REMINDER,
                DEFAULT_GEOFENCE_APPROACH_REMINDER,
            )
        )

    @property
    def approach_distance(self) -> float:
        try:
            return float(
                self._cfg(
                    CONF_GEOFENCE_APPROACH_DISTANCE,
                    DEFAULT_GEOFENCE_APPROACH_DISTANCE,
                )
                or DEFAULT_GEOFENCE_APPROACH_DISTANCE
            )
        except (ValueError, TypeError):
            return DEFAULT_GEOFENCE_APPROACH_DISTANCE

    def cancel_all(self):
        """Cancel all pending geofencing tasks."""
        if self.reminder_task:
            self.reminder_task()
            self.reminder_task = None

    async def async_zone_changed(self, event):
        """Handle zone.home state changes for auto arm/disarm and reminders."""
        new_state = event.data.get("new_state")
        old_state = event.data.get("old_state")

        if not new_state or not old_state:
            return

        try:
            old_count = int(old_state.state)
            new_count = int(new_state.state)
        except (ValueError, TypeError):
            return

        current_state = self.alarm_entity.alarm_state

        if old_count > 0 and new_count == 0:
            # Everyone left
            if current_state == AlarmControlPanelState.DISARMED:
                if self.auto_arm:
                    _LOGGER.info("Geofencing: Plus personne à la maison, auto armement en Absence")
                    await self.alarm_entity.notification_manager.async_send_notification(
                        "🏠 Domolink: Plus personne à la maison, armement automatique activé."
                    )
                    await self.alarm_entity.async_alarm_arm_away()
                elif self.reminder_enabled:
                    if not self.reminder_task:
                        _LOGGER.info(
                            "Geofencing: Plus personne à la maison, planification rappel dans %d min",
                            self.reminder_delay,
                        )
                        self.reminder_task = async_call_later(
                            self.hass,
                            self.reminder_delay * 60,
                            self._cb_geofence_reminder,
                        )

        elif old_count == 0 and new_count > 0:
            # Someone arrived
            if self.reminder_task:
                self.reminder_task()
                self.reminder_task = None

            if self.auto_arm and current_state in (
                AlarmControlPanelState.ARMED_AWAY,
                AlarmControlPanelState.ARMED_NIGHT,
                AlarmControlPanelState.ARMING,
            ):
                _LOGGER.info("Geofencing: Quelqu'un est arrivé, auto désarmement")
                self.alarm_entity._cancel_all_tasks()
                self.alarm_entity._state = AlarmControlPanelState.DISARMED
                self.alarm_entity._last_user = "Géolocalisation"
                self._write_state()
                await self.alarm_entity._async_turn_off_siren()
                await self.alarm_entity.notification_manager.async_send_notification(
                    "🏠 Domolink: Retour détecté, désarmement automatique."
                )

    @callback
    def _cb_geofence_reminder(self, _now):
        """Send actionable reminder notification to arm the alarm."""
        self.reminder_task = None
        if self.alarm_entity.alarm_state != AlarmControlPanelState.DISARMED:
            return

        persons = self._cfg(CONF_PERSONS, [])
        states = [self.hass.states.get(p) for p in persons]
        states = [s.state for s in states if s is not None]
        if all(s != "home" for s in states):
            _LOGGER.info("Geofencing: Envoi notification rappel d'oubli d'armement")
            self._log_event("Rappel d'armement envoyé (Absence prolongée)")
            action_data = {
                "actions": [
                    {
                        "action": "DOMOLINK_REMINDER_ARM_AWAY",
                        "title": "⚡ Armer en Absence",
                    },
                    {
                        "action": "DOMOLINK_CANCEL_ARM",
                        "title": "❌ Ignorer",
                        "destructive": True,
                    },
                ]
            }
            self.hass.async_create_task(
                self.alarm_entity.notification_manager.async_send_notification(
                    "📍 Vous semblez avoir quitté la maison sans activer l'alarme.\n\nVoulez-vous l'armer maintenant ?",
                    custom_data=action_data,
                )
            )

    async def async_handle_mobile_action(self, event):
        """Handle actionable notification button clicks."""
        action = event.data.get("action")
        reply_text = event.data.get("reply_text")

        if action == "DOMOLINK_DISARM":
            _LOGGER.info("Disarm triggered via mobile actionable notification")
            self.alarm_entity._cancel_all_tasks()
            user_name = "App Mobile"
            if event.context and event.context.user_id:
                user_obj = await self.hass.auth.async_get_user(event.context.user_id)
                if user_obj and user_obj.name:
                    user_name = f"{user_obj.name} (Mobile)"
            self._log_event(f"Alarme Désarmée par {user_name}")
            self.alarm_entity._record_arm_event("disarm", user_name)
            await self.alarm_entity.async_alarm_disarm("MOBILE_APP")
            await self.alarm_entity.notification_manager.async_send_notification(
                "✅ Alarme désarmée via Apple Watch / Mobile."
            )

        elif action == "DOMOLINK_REMINDER_ARM_AWAY":
            _LOGGER.info("Arming Away via geofencing reminder notification")
            self._log_event("Armement suite au rappel de géolocalisation")
            await self.alarm_entity.async_alarm_arm_away()

        elif action in (
            "DOMOLINK_FORCE_ARM_AWAY",
            "DOMOLINK_FORCE_ARM_HOME",
            "DOMOLINK_FORCE_ARM_NIGHT",
        ):
            user = "Mobile App"
            if reply_text:
                user = self.alarm_entity._validate_code(str(reply_text).strip())
                if not user:
                    _LOGGER.warning("Invalid code for forced arming from mobile app")
                    await self.alarm_entity.notification_manager.async_send_notification(
                        "⛔ Code erroné. Armement forcé refusé."
                    )
                    return

            mode_map = {
                "DOMOLINK_FORCE_ARM_AWAY": (
                    AlarmControlPanelState.ARMED_AWAY,
                    "Absent",
                ),
                "DOMOLINK_FORCE_ARM_HOME": (
                    AlarmControlPanelState.ARMED_HOME,
                    "Présent",
                ),
                "DOMOLINK_FORCE_ARM_NIGHT": (
                    AlarmControlPanelState.ARMED_NIGHT,
                    "Nuit",
                ),
            }
            target_state, mode_name = mode_map[action]
            self.alarm_entity._cancel_all_tasks()
            self.alarm_entity._state = target_state
            self.alarm_entity._pre_trigger_state = target_state
            self.alarm_entity._last_user = user
            self._write_state()
            self._log_event(
                f"Alarme Armée avec Bypass forcé ({mode_name}) par {user}"
            )
            await self.alarm_entity.notification_manager.async_send_notification(
                f"⚠️ Alarme armée avec mise en marche forcée (Mode: {mode_name})."
            )

        elif action == "DOMOLINK_CANCEL_ARM":
            self._log_event("Armement annulé par l'utilisateur")
            await self.alarm_entity.notification_manager.async_send_notification(
                "❌ Armement annulé."
            )

        elif action == "DOMOLINK_SNOOZE_15M":
            _LOGGER.info("Domolink: Rappel d'armement reporté de 15 minutes")
            self._log_event("Rappel d'armement reporté de 15 minutes")
            self.reminder_task = async_call_later(
                self.hass,
                15 * 60,
                self._cb_geofence_reminder,
            )
            await self.alarm_entity.notification_manager.async_send_notification(
                "⏳ Rappel d'armement reporté de 15 minutes."
            )

    def handle_proximity_update(self, state):
        """Predictive geofencing: check if approaching home while armed."""
        if not self.approach_reminder:
            return
        if self.alarm_entity.alarm_state not in (
            AlarmControlPanelState.ARMED_AWAY,
            AlarmControlPanelState.ARMED_NIGHT,
        ):
            return

        try:
            distance = float(state.state)
            unit = state.attributes.get("unit_of_measurement", "m")
            dist_meters = distance * 1000 if unit == "km" else distance
            dir_of_travel = state.attributes.get("dir_of_travel", "")

            if (
                dir_of_travel in ("towards", "approaching", "")
                and dist_meters <= self.approach_distance
            ):
                now_loop = self.hass.loop.time()
                if self.last_approach_notif_ts + 1800 < now_loop:
                    self.last_approach_notif_ts = now_loop
                    _LOGGER.info(
                        "Domolink Proximity: Arrivée imminente (%d m), envoi rappel de désarmement",
                        dist_meters,
                    )
                    self._log_event(
                        f"Rappel d'approche envoyé (distance: {int(dist_meters)}m)"
                    )
                    action_data = {
                        "actions": [
                            {
                                "action": "DOMOLINK_DISARM",
                                "title": "🔓 Désarmer l'alarme",
                            },
                            {
                                "action": "DOMOLINK_SNOOZE_15M",
                                "title": "⏳ Reporter (15 min)",
                            },
                        ]
                    }
                    self.hass.async_create_task(
                        self.alarm_entity.notification_manager.async_send_notification(
                            f"🚗 Retour imminent détecté ({int(dist_meters)} m). Souhaitez-vous désarmer l'alarme ?",
                            custom_data=action_data,
                        )
                    )
        except Exception as e:
            _LOGGER.debug("Domolink: Proximity check error: %s", e)

    async def async_snooze_reminder(self, duration_minutes: int = 15):
        """Snooze geofencing departure reminder."""
        _LOGGER.info(
            "Domolink: Rappel d'armement mis en pause pour %s minutes",
            duration_minutes,
        )
        self.snooze_until = self.hass.loop.time() + (int(duration_minutes) * 60)
        self._log_event(f"Rappel départ reporté de {duration_minutes} min")
        self._write_state()
