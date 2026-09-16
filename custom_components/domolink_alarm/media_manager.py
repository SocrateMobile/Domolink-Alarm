"""Media storage, retention and camera recording manager for Domolink Alarm."""
import asyncio
import logging
import os
import re
import shutil
import time

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util.dt import now as dt_now

from .cloud_uploader import CloudUploader
from .const import (
    CONF_CAMERAS,
    CONF_CAMERAS_ARM_ENTITIES,
    CONF_MEDIA_MAX_SIZE_MB,
    CONF_MEDIA_PATH,
    CONF_MEDIA_RETENTION_DAYS,
    DEFAULT_MEDIA_MAX_SIZE_MB,
    DEFAULT_MEDIA_PATH,
    DEFAULT_MEDIA_RETENTION_DAYS,
)

_LOGGER = logging.getLogger(__name__)


class MediaManager:
    """Manages local alarm media files, quotas, purges and camera captures."""

    def __init__(
        self,
        hass: HomeAssistant,
        get_config_cb,
        log_event_cb,
        write_state_cb,
        cloud_uploader: CloudUploader,
        send_notification_cb,
    ):
        """Initialize MediaManager."""
        self.hass = hass
        self._get_config = get_config_cb
        self._log_event = log_event_cb
        self._write_state = write_state_cb
        self.cloud_uploader = cloud_uploader
        self._send_notification = send_notification_cb

        self.storage_stats = {
            "bytes": 0,
            "mb": 0.0,
            "max_mb": DEFAULT_MEDIA_MAX_SIZE_MB,
            "retention_days": DEFAULT_MEDIA_RETENTION_DAYS,
            "count": 0,
            "percent": 0.0,
        }
        self.is_testing_cameras = False
        self.camera_test_info = {}
        self.media_files_cache_ts = 0
        self.cameras_armed = False

    def _cfg(self, key, default=None):
        return self._get_config(key, default)

    @property
    def media_path(self) -> str:
        """Return relative media folder path under www/."""
        return str(self._cfg(CONF_MEDIA_PATH, DEFAULT_MEDIA_PATH) or DEFAULT_MEDIA_PATH).strip()

    @property
    def media_dir(self) -> str:
        """Return absolute path to local media directory."""
        return self.hass.config.path(f"www/{self.media_path}")

    @property
    def retention_days(self) -> int:
        """Return media retention in days."""
        try:
            return int(self._cfg(CONF_MEDIA_RETENTION_DAYS, DEFAULT_MEDIA_RETENTION_DAYS) or 0)
        except (ValueError, TypeError):
            return DEFAULT_MEDIA_RETENTION_DAYS

    @property
    def max_size_mb(self) -> int:
        """Return max media storage quota in MB."""
        try:
            return int(self._cfg(CONF_MEDIA_MAX_SIZE_MB, DEFAULT_MEDIA_MAX_SIZE_MB) or 0)
        except (ValueError, TypeError):
            return DEFAULT_MEDIA_MAX_SIZE_MB

    def update_storage_stats(self):
        """Update media storage usage statistics."""
        try:
            total_bytes = 0
            count = 0
            if os.path.exists(self.media_dir):
                for fname in os.listdir(self.media_dir):
                    if not fname.startswith(".") and fname.lower().endswith(
                        (".jpg", ".jpeg", ".png", ".mp4", ".webm", ".ogg")
                    ):
                        fpath = os.path.join(self.media_dir, fname)
                        if os.path.isfile(fpath):
                            total_bytes += os.path.getsize(fpath)
                            count += 1
            mb = round(total_bytes / (1024 * 1024), 2)
            max_mb = self.max_size_mb if self.max_size_mb > 0 else 1024
            percent = round((mb / max_mb) * 100, 1) if max_mb > 0 else 0.0
            self.storage_stats = {
                "bytes": total_bytes,
                "mb": mb,
                "max_mb": self.max_size_mb,
                "retention_days": self.retention_days,
                "count": count,
                "percent": min(100.0, percent),
            }
        except Exception as e:
            _LOGGER.debug("Domolink: Erreur stats stockage: %s", e)

    def purge_old_files(self) -> dict:
        """Purge media files exceeding retention days and max storage MB quota (FIFO)."""
        if not os.path.exists(self.media_dir):
            self.update_storage_stats()
            return {"deleted": 0, "freed_bytes": 0}

        deleted_count = 0
        freed_bytes = 0
        now_ts = time.time()
        retention_sec = (self.retention_days * 86400) if self.retention_days > 0 else 0
        max_bytes = (self.max_size_mb * 1024 * 1024) if self.max_size_mb > 0 else 0

        # Collect all valid alarm media files with stats
        all_files = []
        try:
            for fname in os.listdir(self.media_dir):
                if not fname.startswith(".") and fname.lower().endswith(
                    (".jpg", ".jpeg", ".png", ".mp4", ".webm", ".ogg")
                ):
                    fpath = os.path.join(self.media_dir, fname)
                    if os.path.isfile(fpath):
                        try:
                            st = os.stat(fpath)
                            all_files.append(
                                {
                                    "path": fpath,
                                    "name": fname,
                                    "size": st.st_size,
                                    "mtime": st.st_mtime,
                                }
                            )
                        except Exception:
                            pass
        except Exception as e:
            _LOGGER.error("Domolink: Erreur lors du scan pour purge: %s", e)
            return {"deleted": 0, "freed_bytes": 0}

        # 1. Purge by retention days (if configured)
        remaining_files = []
        if retention_sec > 0:
            for item in all_files:
                if (now_ts - item["mtime"]) > retention_sec:
                    try:
                        os.remove(item["path"])
                        deleted_count += 1
                        freed_bytes += item["size"]
                        _LOGGER.info(
                            "Domolink: Purge média expiré (> %d j): %s",
                            self.retention_days,
                            item["name"],
                        )
                    except Exception as err:
                        _LOGGER.debug("Domolink: Erreur suppression %s: %s", item["path"], err)
                else:
                    remaining_files.append(item)
        else:
            remaining_files = all_files

        # 2. Purge by quota MB (FIFO - delete oldest until below 90% quota)
        if max_bytes > 0:
            total_remaining_bytes = sum(f["size"] for f in remaining_files)
            target_bytes = int(max_bytes * 0.90)  # Aim for 90% of quota
            if total_remaining_bytes > max_bytes:
                remaining_files.sort(key=lambda x: x["mtime"])
                for item in remaining_files:
                    if total_remaining_bytes <= target_bytes:
                        break
                    try:
                        os.remove(item["path"])
                        deleted_count += 1
                        freed_bytes += item["size"]
                        total_remaining_bytes -= item["size"]
                        _LOGGER.info("Domolink: Purge quota FIFO: %s", item["name"])
                    except Exception as err:
                        _LOGGER.debug("Domolink: Erreur suppression FIFO %s: %s", item["path"], err)

        self.media_files_cache_ts = 0
        self.update_storage_stats()

        if deleted_count > 0:
            freed_mb = round(freed_bytes / (1024 * 1024), 1)
            self._log_event(
                f"🧹 Purge médias : {deleted_count} fichier(s) supprimé(s) ({freed_mb} Mo libérés)"
            )

        return {"deleted": deleted_count, "freed_bytes": freed_bytes}

    async def async_clean_media(self, call=None) -> dict:
        """Service handler to clean / purge old media files on demand."""
        result = await self.hass.async_add_executor_job(self.purge_old_files)
        self._write_state()
        return result

    def list_media_files(self) -> list:
        """List all media files in the configured media directory (for the JS gallery)."""
        try:
            if not os.path.exists(self.media_dir):
                self.update_storage_stats()
                return []
            files = []
            for fname in sorted(os.listdir(self.media_dir), reverse=True):
                if not fname.startswith("."):
                    fpath = os.path.join(self.media_dir, fname)
                    if os.path.isfile(fpath) and fname.lower().endswith(
                        (".jpg", ".jpeg", ".png", ".mp4", ".webm", ".ogg")
                    ):
                        files.append(
                            {
                                "name": fname,
                                "size": os.path.getsize(fpath),
                                "modified": os.path.getmtime(fpath),
                            }
                        )
            self.update_storage_stats()
            return files[:200]  # Cap at 200 to avoid huge HA state
        except Exception as e:
            _LOGGER.debug("Domolink: Erreur lecture médias: %s", e)
            return []

    def get_media_filenames(self, camera_entity: str) -> tuple[str, str]:
        """Construct media filenames: [nom de la caméra] - [Année] - [jour] - [heure du déclenchement]."""
        st = self.hass.states.get(camera_entity)
        cam_name = (st.attributes.get("friendly_name") if st else None) or camera_entity
        if cam_name.startswith("camera."):
            cam_name = cam_name[7:]
        safe_cam = re.sub(r'[\\/*?:"<>|]', "-", cam_name).strip()
        safe_cam = re.sub(r"\s+", " ", safe_cam)
        if not safe_cam:
            safe_cam = "Camera"

        now = dt_now()
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%Hh%Mm%Ss")
        base_name = f"{safe_cam} - {date_str} - {time_str}"
        return f"{base_name}.jpg", f"{base_name}.mp4"

    async def async_watch_and_fix_video(
        self, expected_mp4_path: str, duration: int = 30, timeout: int = 90
    ):
        """Watch for .mp4.tmp files written by HA and ensure valid finalized .mp4."""
        await asyncio.sleep(duration + 4)

        tmp_path = expected_mp4_path + ".tmp"
        alt_tmp = expected_mp4_path.replace(".mp4", ".mp4.tmp")

        remaining = max(10, timeout - duration - 4)
        for _ in range(int(remaining * 2)):
            if os.path.exists(expected_mp4_path) and os.path.getsize(expected_mp4_path) > 10240:
                self.media_files_cache_ts = 0
                _LOGGER.debug("Domolink: Video OK: %s", expected_mp4_path)
                await self.cloud_uploader.async_upload_file(expected_mp4_path, upload_telegram=True)
                return

            for tmp in (tmp_path, alt_tmp):
                if os.path.exists(tmp):
                    try:
                        size1 = os.stat(tmp).st_size
                        await asyncio.sleep(2.5)
                        size2 = os.stat(tmp).st_size
                        if size1 == size2 and size1 > 10240:
                            os.rename(tmp, expected_mp4_path)
                            self.media_files_cache_ts = 0
                            _LOGGER.info("Domolink: .mp4.tmp finalisé en .mp4: %s", expected_mp4_path)
                            self._log_event(f"Vidéo sauvegardée: {os.path.basename(expected_mp4_path)}")
                            await self.cloud_uploader.async_upload_file(
                                expected_mp4_path, upload_telegram=True
                            )
                            return
                    except Exception as e:
                        _LOGGER.debug("Domolink: Erreur finalisation tmp: %s", e)
            await asyncio.sleep(0.5)
        _LOGGER.warning("Domolink: Timeout attente vidéo: %s", expected_mp4_path)

    async def async_media_action(self, call):
        """Handle rename or delete of media files."""
        action = str(call.data.get("action", "")).lower()
        filename = str(call.data.get("filename", "")).strip()
        new_name = str(call.data.get("new_name", "")).strip()

        if ".." in filename or "/" in filename or "\\" in filename:
            _LOGGER.error("Domolink: Tentative d'accès hors-répertoire bloquée: %s", filename)
            raise HomeAssistantError("Accès refusé: nom de fichier invalide.")

        file_path = os.path.join(self.media_dir, filename)
        if not os.path.exists(file_path):
            raise HomeAssistantError(f"Fichier introuvable: {filename}")

        if action == "delete":
            try:
                os.remove(file_path)
                self.media_files_cache_ts = 0
                self.update_storage_stats()
                self._log_event(f"Média supprimé: {filename}")
                _LOGGER.info("Domolink: Fichier supprimé: %s", file_path)
                self._write_state()
            except Exception as e:
                raise HomeAssistantError(f"Impossible de supprimer: {e}")

        elif action == "rename":
            if not new_name or ".." in new_name or "/" in new_name or "\\" in new_name:
                raise HomeAssistantError("Nouveau nom invalide.")
            new_path = os.path.join(self.media_dir, new_name)
            try:
                os.rename(file_path, new_path)
                self.media_files_cache_ts = 0
                self.update_storage_stats()
                self._log_event(f"Média renommé: {filename} → {new_name}")
                _LOGGER.info("Domolink: Fichier renommé: %s → %s", file_path, new_path)
                self._write_state()
            except Exception as e:
                raise HomeAssistantError(f"Impossible de renommer: {e}")
        else:
            raise HomeAssistantError(f"Action inconnue: {action}")

    async def async_test_cameras_recording(self, call=None):
        """Trigger sequential test of all cameras: photo + 30s video one by one."""
        if self.is_testing_cameras:
            _LOGGER.warning("Domolink: Un test d'enregistrement caméra est déjà en cours.")
            return

        cameras = self._cfg(CONF_CAMERAS, [])
        if not cameras:
            self._log_event("Test vidéo impossible : Aucune caméra configurée.")
            return

        self.hass.async_create_task(self._async_run_cameras_test())

    async def _async_run_cameras_test(self):
        """Run sequential snapshot and 30s video recording for each camera."""
        cameras = self._cfg(CONF_CAMERAS, [])
        self.is_testing_cameras = True
        total_cams = len(cameras)

        try:
            os.makedirs(self.media_dir, exist_ok=True)
        except Exception as e:
            _LOGGER.error("Domolink: Impossible de créer le répertoire média %s: %s", self.media_dir, e)

        self._log_event(f"🎬 Début du test d'enregistrement sur {total_cams} caméra(s)")

        try:
            for idx, camera in enumerate(cameras):
                st = self.hass.states.get(camera)
                cam_name = st.attributes.get("friendly_name", camera) if st else camera
                snapshot_filename, video_filename = self.get_media_filenames(camera)

                self.camera_test_info = {
                    "total": total_cams,
                    "current": idx + 1,
                    "camera_entity": camera,
                    "camera_name": cam_name,
                    "step": "photo",
                    "video_start": 0,
                    "video_duration": 34,
                }
                self._write_state()

                try:
                    await self.hass.services.async_call("camera", "turn_on", {"entity_id": camera})
                except Exception:
                    pass

                # 1. Snapshot
                self._log_event(f"📸 Test ({idx+1}/{total_cams}) : Capture photo sur {cam_name}")
                snapshot_path = os.path.join(self.media_dir, snapshot_filename)

                try:
                    if camera.startswith("camera.aarlo"):
                        await asyncio.wait_for(
                            self.hass.services.async_call(
                                "aarlo",
                                "camera_request_snapshot_to_file",
                                {"entity_id": camera, "filename": snapshot_path},
                                blocking=True,
                            ),
                            timeout=15.0,
                        )
                    else:
                        await asyncio.wait_for(
                            self.hass.services.async_call(
                                "camera",
                                "snapshot",
                                {"entity_id": camera, "filename": snapshot_path},
                                blocking=True,
                            ),
                            timeout=15.0,
                        )

                    if os.path.exists(snapshot_path):
                        self.media_files_cache_ts = 0
                        alert_path = self.hass.config.path("www/domolink_alarm_alert.jpg")
                        try:
                            shutil.copy2(snapshot_path, alert_path)
                        except Exception:
                            pass
                        await self.cloud_uploader.async_upload_file(snapshot_path)
                    self._log_event(f"✅ Photo test enregistrée ({cam_name})")
                except asyncio.TimeoutError:
                    self._log_event(f"⚠️ Timeout photo (15s) sur {cam_name}")
                except Exception as e:
                    self._log_event(f"⚠️ Erreur photo sur {cam_name} : {e}")

                # 2. 30-second Video Recording
                self.camera_test_info = {
                    "total": total_cams,
                    "current": idx + 1,
                    "camera_entity": camera,
                    "camera_name": cam_name,
                    "step": "video",
                    "video_start": time.time(),
                    "video_duration": 34,
                }
                self._write_state()

                self._log_event(f"🎥 Test ({idx+1}/{total_cams}) : Enregistrement 30s sur {cam_name}...")
                record_path = os.path.join(self.media_dir, video_filename)

                try:
                    await self.hass.services.async_call(
                        "camera",
                        "record",
                        {"entity_id": camera, "duration": 30, "filename": record_path},
                    )
                    await self.async_watch_and_fix_video(record_path, duration=30, timeout=60)
                    self._log_event(f"✅ Vidéo 30s test enregistrée ({cam_name})")
                except Exception as e:
                    self._log_event(f"⚠️ Erreur vidéo sur {cam_name} : {e}")

                await asyncio.sleep(1.0)

            self._log_event("🎉 Test d'enregistrement terminé pour toutes les caméras ! Rendez-vous dans la Médiathèque.")
            try:
                await self._send_notification(
                    "🎬 Test caméras terminé avec succès. Les photos et vidéos sont disponibles dans la Médiathèque.",
                    is_alert=False,
                )
            except Exception:
                pass
        finally:
            self.is_testing_cameras = False
            self.camera_test_info = {}
            self._write_state()

    async def async_sync_cameras(self, arm: bool):
        """Sync camera motion detection or alarm panels."""
        arm_entities = self._cfg(CONF_CAMERAS_ARM_ENTITIES, [])
        if not arm_entities:
            self.cameras_armed = False
            return

        for entity_id in arm_entities:
            domain = entity_id.split(".")[0]
            try:
                if arm:
                    if domain == "switch":
                        await self.hass.services.async_call("switch", "turn_on", {"entity_id": entity_id}, blocking=False)
                    elif domain == "alarm_control_panel":
                        await self.hass.services.async_call("alarm_control_panel", "alarm_arm_away", {"entity_id": entity_id}, blocking=False)
                    elif domain == "camera":
                        await self.hass.services.async_call("camera", "turn_on", {"entity_id": entity_id}, blocking=False)
                else:
                    if domain == "switch":
                        await self.hass.services.async_call("switch", "turn_off", {"entity_id": entity_id}, blocking=False)
                    elif domain == "alarm_control_panel":
                        await self.hass.services.async_call("alarm_control_panel", "alarm_disarm", {"entity_id": entity_id}, blocking=False)
                    elif domain == "camera":
                        await self.hass.services.async_call("camera", "turn_off", {"entity_id": entity_id}, blocking=False)
            except Exception as e:
                _LOGGER.error("Domolink: Erreur synchronisation caméra %s: %s", entity_id, e)

        self.cameras_armed = arm
        self._write_state()

    async def async_capture_cameras(self, target_cameras: list[str], matching_zones: set[str] = None):
        """Asynchronously capture photos and trigger recordings with targeted zone cameras (parallel & robust)."""
        if not target_cameras:
            _LOGGER.debug("Domolink: Aucune caméra ciblée pour la capture.")
            return

        try:
            os.makedirs(self.media_dir, exist_ok=True)
        except Exception as e:
            _LOGGER.error("Domolink: Impossible de créer %s: %s", self.media_dir, e)

        zone_desc = f" (Zone: {', '.join(matching_zones)})" if matching_zones else ""
        self._log_event(f"Capture photo & vidéo{zone_desc} sur {len(target_cameras)} caméra(s)")

        async def _capture_single_camera(camera, idx):
            snapshot_filename, video_filename = self.get_media_filenames(camera)
            snapshot_path = os.path.join(self.media_dir, snapshot_filename)
            record_path = os.path.join(self.media_dir, video_filename)

            try:
                await self.hass.services.async_call("camera", "turn_on", {"entity_id": camera})
            except Exception:
                pass

            # 1. Snapshot
            try:
                if camera.startswith("camera.aarlo"):
                    await asyncio.wait_for(
                        self.hass.services.async_call(
                            "aarlo",
                            "camera_request_snapshot_to_file",
                            {"entity_id": camera, "filename": snapshot_path},
                            blocking=True,
                        ),
                        timeout=12.0,
                    )
                else:
                    await asyncio.wait_for(
                        self.hass.services.async_call(
                            "camera",
                            "snapshot",
                            {"entity_id": camera, "filename": snapshot_path},
                            blocking=True,
                        ),
                        timeout=12.0,
                    )

                if idx == 0 and os.path.exists(snapshot_path):
                    alert_path = self.hass.config.path("www/domolink_alarm_alert.jpg")
                    try:
                        shutil.copy2(snapshot_path, alert_path)
                    except Exception as e:
                        _LOGGER.debug("Domolink: Erreur copie alert_path: %s", e)

                if os.path.exists(snapshot_path):
                    self.media_files_cache_ts = 0
                    await self.cloud_uploader.async_upload_file(snapshot_path, upload_telegram=True)
            except asyncio.TimeoutError:
                _LOGGER.warning("Domolink: Timeout photo (12s) sur %s", camera)
            except Exception as e:
                _LOGGER.error("Domolink: Erreur photo sur %s: %s", camera, e)

            # 2. Video recording
            try:
                await self.hass.services.async_call(
                    "camera",
                    "record",
                    {"entity_id": camera, "duration": 30, "filename": record_path},
                )
                self.hass.async_create_task(
                    self.async_watch_and_fix_video(record_path, timeout=90)
                )
            except Exception as e:
                _LOGGER.error("Domolink: Erreur enregistrement vidéo %s: %s", camera, e)

        tasks = [_capture_single_camera(cam, i) for i, cam in enumerate(target_cameras)]
        await asyncio.gather(*tasks, return_exceptions=True)
        self.hass.async_create_task(self.hass.async_add_executor_job(self.purge_old_files))
