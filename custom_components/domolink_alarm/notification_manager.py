"""Notification, alert dispatching and deterrence manager for Domolink Alarm."""
import asyncio
import logging
import urllib.parse

from homeassistant.core import HomeAssistant

from .const import (
    CONF_CAMERAS,
    CONF_EMERGENCY_CONTACT,
    CONF_FAILOVER_GSM_ENABLED,
    CONF_FAILOVER_GSM_SERVICE,
    CONF_FAILOVER_LOCAL_ALARM,
    CONF_FREE_MOBILE_PASS,
    CONF_FREE_MOBILE_USER,
    CONF_ICLOUD_DEVICES,
    CONF_LIGHTS,
    CONF_MEDIA_PLAYERS,
    CONF_NOTIFY_SERVICES,
    CONF_PERSONS,
    CONF_SIRENS,
)

_LOGGER = logging.getLogger(__name__)


class NotificationManager:
    """Manages multi-channel notification dispatch, SMS, iCloud alerts, TTS deterrence, and siren tests."""

    def __init__(
        self,
        hass: HomeAssistant,
        get_config_cb,
        log_event_cb,
        write_state_cb,
        turn_on_siren_cb=None,
    ):
        """Initialize NotificationManager."""
        self.hass = hass
        self._get_config = get_config_cb
        self._log_event = log_event_cb
        self._write_state = write_state_cb
        self._turn_on_siren = turn_on_siren_cb

        self.network_failover_active = False

    def _cfg(self, key, default=None):
        return self._get_config(key, default)

    async def async_send_notification(
        self, message: str, is_alert: bool = False, custom_data: dict = None, is_emergency: bool = False
    ):
        """Send notifications to configured services/entities with universal compatibility."""
        sent_targets = []

        # ─── NATIVE FREE MOBILE SMS BACKUP ─────────────────────────────
        free_user = self._cfg(CONF_FREE_MOBILE_USER)
        free_pass = self._cfg(CONF_FREE_MOBILE_PASS)
        if free_user and free_pass:
            if is_alert or is_emergency or ("Désarmement" in message or "Armement" in message):
                try:
                    from homeassistant.helpers.aiohttp_client import async_get_clientsession

                    safe_msg = (
                        message.replace("🚨", "")
                        .replace("🟢", "")
                        .replace("🔴", "")
                        .replace("🟠", "")
                        .replace("🛡️", "")
                        .replace("⚠️", "")
                    )
                    safe_msg = f"Domolink: {safe_msg.strip()}"
                    encoded_msg = urllib.parse.quote(safe_msg)
                    url = f"https://smsapi.free-mobile.fr/sendmsg?user={free_user}&pass={free_pass}&msg={encoded_msg}"

                    session = async_get_clientsession(self.hass)

                    async def _send_sms_task():
                        try:
                            async with session.get(url) as response:
                                if response.status == 200:
                                    _LOGGER.info("Domolink: SMS natif Free Mobile envoyé avec succès")
                                    self._log_event("SMS d'alerte envoyé via Free Mobile")
                                else:
                                    _LOGGER.error("Domolink: Erreur API Free Mobile (%s)", response.status)
                        except Exception as e:
                            _LOGGER.error("Domolink: Exception lors de l'envoi SMS Free Mobile: %s", e)

                    self.hass.async_create_task(_send_sms_task())
                except Exception as e:
                    _LOGGER.error("Domolink: Impossible de préparer le SMS natif: %s", e)

        # ─── NATIVE APPLE ICLOUD FIND MY ALERT ─────────────────────────
        icloud_devices = self._cfg(CONF_ICLOUD_DEVICES, [])
        if icloud_devices:
            from homeassistant.helpers import device_registry as dr

            dev_reg = dr.async_get(self.hass)
            for device_id in icloud_devices:
                try:
                    device_entry = dev_reg.async_get(device_id)
                    if not device_entry:
                        continue

                    device_name = device_entry.name
                    if not device_name:
                        continue

                    account = None
                    for entry_id in device_entry.config_entries:
                        config_entry = self.hass.config_entries.async_get_entry(entry_id)
                        if config_entry and config_entry.domain == "icloud":
                            account = config_entry.data.get("username")
                            break

                    if not account:
                        continue

                    self.hass.async_create_task(
                        self.hass.services.async_call(
                            "icloud",
                            "display_message",
                            {
                                "account": account,
                                "device_name": device_name,
                                "message": message,
                                "sound": is_alert or is_emergency,
                            },
                        )
                    )
                    if is_alert or is_emergency:
                        self.hass.async_create_task(
                            self.hass.services.async_call(
                                "icloud",
                                "play_sound",
                                {"account": account, "device_name": device_name},
                            )
                        )
                        sent_targets.append(f"iCloud ({device_name})")
                except Exception as e:
                    _LOGGER.error("Domolink: Impossible de déclencher l'alerte iCloud: %s", e)

        # ─── NOTIFY TARGETS DISPATCH ──────────────────────────────────
        notify_services = self._cfg(CONF_NOTIFY_SERVICES, [])
        emergency_contacts = self._cfg(CONF_EMERGENCY_CONTACT, [])
        targets = []
        if notify_services:
            targets.extend(notify_services)
        if is_emergency and emergency_contacts:
            for ec in emergency_contacts:
                if ec not in targets:
                    targets.append(ec)

        if not targets:
            if sent_targets:
                clean_msg = message.replace("\n", " - ")
                self._log_event(f"Message envoyé à {', '.join(sent_targets)} : {clean_msg}")
            return

        data = {
            "url": "/",
            "clickAction": "/",
        }

        if is_alert:
            cameras = self._cfg(CONF_CAMERAS, [])
            alert_data = {
                "push": {
                    "category": "camera",
                    "sound": {
                        "name": "default",
                        "critical": 1,
                        "volume": 1.0,
                    },
                },
                "actions": [
                    {
                        "action": "DOMOLINK_DISARM",
                        "title": "🔓 Désarmer l'alarme",
                        "destructive": True,
                    }
                ],
            }
            if cameras:
                alert_data["entity_id"] = cameras[0]
                alert_data["image"] = "/local/domolink_alarm_alert.jpg"
                alert_data["attachment"] = {
                    "url": "/local/domolink_alarm_alert.jpg",
                    "content-type": "jpeg",
                    "hide-thumbnail": False,
                }
            data.update(alert_data)

        if custom_data:
            data.update(custom_data)

        if is_emergency:
            persons = self._cfg(CONF_PERSONS, [])
            for person_id in persons:
                state = self.hass.states.get(person_id)
                if state and state.attributes.get("latitude") and state.attributes.get("longitude"):
                    data["location"] = {
                        "latitude": state.attributes.get("latitude"),
                        "longitude": state.attributes.get("longitude"),
                    }
                    break

        for target in targets:
            sent = False

            # Strategy 1: Modern HA Notify Entity
            if target.startswith("notify.") and self.hass.services.has_service("notify", "send_message"):
                try:
                    safe_message = message
                    if "free_mobile" in target or "sms" in target:
                        safe_message = (
                            message.replace("🚨", "")
                            .replace("🟢", "")
                            .replace("🔴", "")
                            .replace("🟠", "")
                            .replace("🛡️", "")
                            .replace("⚠️", "")
                        )

                    payload = {"message": safe_message}
                    if data:
                        payload["data"] = data

                    payload["entity_id"] = target
                    await self.hass.services.async_call(
                        "notify",
                        "send_message",
                        service_data=payload,
                        target={"entity_id": target},
                    )
                    sent = True
                    sent_targets.append(target)
                    _LOGGER.debug("Domolink: Notification envoyée via notify.send_message à %s", target)
                except Exception as e:
                    _LOGGER.debug("Domolink: notify.send_message échoué pour %s: %s", target, e)

            # Strategy 2: Direct service call
            if not sent:
                if "." in target:
                    domain, service = target.split(".", 1)
                else:
                    domain, service = "notify", target

                if self.hass.services.has_service(domain, service):
                    try:
                        payload = {"message": message}
                        if data:
                            payload["data"] = data
                        await self.hass.services.async_call(domain, service, payload)
                        sent = True
                        sent_targets.append(f"{domain}.{service}")
                        _LOGGER.debug("Domolink: Notification envoyée directement à %s.%s", domain, service)
                    except Exception as e:
                        _LOGGER.error("Domolink: Échec d'envoi vers %s.%s: %s", domain, service, e)

                # Strategy 3: Target is notify.iphone -> try notify.mobile_app_iphone
                elif domain == "notify" and self.hass.services.has_service("notify", f"mobile_app_{service}"):
                    try:
                        payload = {"message": message}
                        if data:
                            payload["data"] = data
                        await self.hass.services.async_call("notify", f"mobile_app_{service}", payload)
                        sent = True
                        sent_targets.append(f"notify.mobile_app_{service}")
                        _LOGGER.debug("Domolink: Notification envoyée à notify.mobile_app_%s", service)
                    except Exception as e:
                        _LOGGER.error("Domolink: Échec d'envoi vers notify.mobile_app_%s: %s", service, e)

            if not sent:
                _LOGGER.warning("Domolink: Impossible de trouver un service de notification valide pour %s", target)

        # ─── FAILOVER GSM / LOCAL BACKUP ──────────────────────────────
        failover_enabled = bool(self._cfg(CONF_FAILOVER_GSM_ENABLED, False))
        if (is_alert or is_emergency) and failover_enabled:
            failover_svc = self._cfg(CONF_FAILOVER_GSM_SERVICE, "")
            failover_siren = bool(self._cfg(CONF_FAILOVER_LOCAL_ALARM, False))

            if not sent_targets and targets:
                self.network_failover_active = True
                _LOGGER.warning("Domolink: Déclenchement alerte secours Réseau / GSM")
                self._log_event("Secours Réseau actif : tentative alerte locale/GSM")

                if failover_svc:
                    try:
                        if failover_svc.startswith("notify."):
                            fo_svc = failover_svc.split(".", 1)[1]
                            await self.hass.services.async_call("notify", fo_svc, {"message": f"[SECOURS GSM] {message}"})
                        elif "." in failover_svc:
                            fo_dom, fo_svc = failover_svc.split(".", 1)
                            await self.hass.services.async_call(fo_dom, fo_svc, {"message": f"[SECOURS GSM] {message}"})
                        sent_targets.append(f"Secours ({failover_svc})")
                    except Exception as e:
                        _LOGGER.error("Domolink: Échec alerte secours %s: %s", failover_svc, e)

                if failover_siren and self._turn_on_siren:
                    self.hass.async_create_task(self._turn_on_siren())
            else:
                self.network_failover_active = False

        if sent_targets:
            clean_msg = message.replace("\n", " - ")
            self._log_event(f"Message envoyé à {', '.join(sent_targets)} : {clean_msg}")

    async def async_play_tts(self, message: str, volume: float = None):
        """Prepare media players and play TTS message in background."""
        media_players = self._cfg(CONF_MEDIA_PLAYERS, [])
        if not media_players:
            return

        target_vol = volume if volume is not None else 0.5
        for player in media_players:
            try:
                await self.hass.services.async_call(
                    "media_player",
                    "turn_on",
                    {"entity_id": player},
                )
            except Exception:
                pass

            try:
                await self.hass.services.async_call(
                    "media_player",
                    "volume_set",
                    {"entity_id": player, "volume_level": target_vol},
                )
            except Exception:
                pass

        await asyncio.sleep(2.5)

        for player in media_players:
            played = False
            if self.hass.services.has_service("tts", "speak"):
                tts_entities = [e for e in self.hass.states.async_entity_ids("tts")]
                if tts_entities:
                    try:
                        await self.hass.services.async_call(
                            "tts",
                            "speak",
                            {
                                "entity_id": tts_entities[0],
                                "media_player_entity_id": player,
                                "message": message,
                            },
                        )
                        played = True
                    except Exception:
                        pass
            if not played and self.hass.services.has_service("tts", "google_translate_say"):
                try:
                    await self.hass.services.async_call(
                        "tts",
                        "google_translate_say",
                        {"entity_id": player, "message": message},
                    )
                    played = True
                except Exception:
                    pass
            if not played and self.hass.services.has_service("tts", "cloud_say"):
                try:
                    await self.hass.services.async_call(
                        "tts",
                        "cloud_say",
                        {"entity_id": player, "message": message},
                    )
                    played = True
                except Exception:
                    pass

    async def async_pre_alarm_feedback(self):
        """Flash lights and warn during pending state."""
        lights = self._cfg(CONF_LIGHTS, [])
        if lights:
            try:
                await self.hass.services.async_call(
                    "light",
                    "turn_on",
                    {"entity_id": lights, "flash": "short"},
                )
            except Exception:
                try:
                    await self.hass.services.async_call(
                        "homeassistant",
                        "turn_on",
                        {"entity_id": lights},
                    )
                except Exception as e:
                    _LOGGER.error("Failed to flash panic lights: %s", e)

        self.hass.async_create_task(
            self.async_play_tts("Veuillez désarmer l'alarme immédiatement.")
        )

    async def async_run_siren_test(self):
        """Execute the weekly siren test asynchronously."""
        sirens = self._cfg(CONF_SIRENS, [])
        if not sirens:
            return

        failed_sirens = []
        for siren in sirens:
            try:
                await self.hass.services.async_call(
                    "homeassistant", "turn_on", {"entity_id": siren}
                )
                await asyncio.sleep(1.0)
                await self.hass.services.async_call(
                    "homeassistant", "turn_off", {"entity_id": siren}
                )
            except Exception:
                failed_sirens.append(siren)

        if failed_sirens:
            msg = f"⚠️ Le test automatique des sirènes a échoué sur : {', '.join(failed_sirens)}."
            self._log_event("Échec du test sirène")
            await self.async_send_notification(msg)
        else:
            self._log_event("Test sirène OK")
            await self.async_send_notification("✅ Test automatique hebdomadaire des sirènes réussi.")
