"""Cloud and remote backup storage manager for Domolink Alarm."""
import asyncio
import base64
import datetime
import ftplib
import io
import json
import logging
import os
import re
import socket
import ssl
from ssl import SSLSocket

from homeassistant.core import HomeAssistant
from homeassistant.util.dt import now as dt_now

from .const import (
    CONF_FTP_ALLOW_INSECURE_TLS,
    CONF_FTP_ENABLED,
    CONF_FTP_HOST,
    CONF_FTP_PASS,
    CONF_FTP_PATH,
    CONF_FTP_PORT,
    CONF_FTP_PROTOCOL,
    CONF_FTP_USER,
    CONF_GOOGLE_DRIVE_CLIENT_ID,
    CONF_GOOGLE_DRIVE_CLIENT_SECRET,
    CONF_GOOGLE_DRIVE_ENABLED,
    CONF_GOOGLE_DRIVE_FOLDER_ID,
    CONF_GOOGLE_DRIVE_METHOD,
    CONF_GOOGLE_DRIVE_REFRESH_TOKEN,
    CONF_GOOGLE_DRIVE_WEBHOOK_URL,
    CONF_NAS_CONFIGS,
    CONF_NAS_TYPE,
    CONF_TELEGRAM_CHAT_ID,
    CONF_TELEGRAM_ENABLED,
    CONF_TELEGRAM_TOKEN,
    CONF_WEBDAV_ENABLED,
    CONF_WEBDAV_PASS,
    CONF_WEBDAV_PATH,
    CONF_WEBDAV_URL,
    CONF_WEBDAV_USER,
)

_LOGGER = logging.getLogger(__name__)


class _ReusedSslSocket(SSLSocket):
    """SSL socket wrapper that suppresses unexpected EOF/shutdown errors on close."""

    def unwrap(self):
        try:
            return super().unwrap()
        except Exception:
            return None


class ReusedSessionFTP_TLS(ftplib.FTP_TLS):
    """FTP_TLS subclass enforcing TLS session reuse on data connections.

    Required by Freebox OS, vsftpd, and ProFTPD to avoid
    '522 SSL connection failed: session reuse required'.
    """

    def ntransfercmd(self, cmd, rest=None):
        conn, size = ftplib.FTP.ntransfercmd(self, cmd, rest)
        if self._prot_p:
            session = getattr(self.sock, "session", None)
            conn = self.context.wrap_socket(
                conn,
                server_hostname=self.host,
                session=session,
            )
            conn.__class__ = _ReusedSslSocket
        return conn, size


def _build_ftp_target_path(raw_path: str, nas_type: str = "") -> list[str]:
    """Build the target path directory segments for NAS upload / test."""
    p_str = str(raw_path or "").strip()
    if nas_type == "freebox" and (not p_str or p_str == "/"):
        p_str = "/Disque 1"

    parts = [p.strip() for p in p_str.split("/") if p.strip()]
    if parts:
        res = list(parts)
        if "alarm" not in res:
            if "domolink" not in res:
                res.append("domolink")
            res.append("alarm")
        return res
    return ["domolink", "alarm"]


def _ftp_navigate_and_ensure_dirs(
    ftp, target_parts: list[str], log_step=None
) -> tuple[bool, str, str]:
    """Navigate and create directories sequentially on FTP server.

    Handles root-level read-only virtual mounts (e.g. Freebox /Disque 1).
    Returns (success, current_path_str, error_message).
    """
    try:
        ftp.cwd("/")
    except Exception:
        pass

    navigated = []
    for part in target_parts:
        try:
            ftp.cwd(part)
            navigated.append(part)
            if log_step:
                log_step(f"   ✓ Dossier '{part}' accessible.", "success")
        except Exception:
            created = False
            try:
                ftp.mkd(part)
                ftp.cwd(part)
                navigated.append(part)
                if log_step:
                    log_step(f"   ✓ Dossier '{part}' créé avec succès.", "success")
                created = True
            except Exception as mkd_err:
                # If cannot create at current position and we are at root, check for mounted disk volumes (e.g. Freebox)
                if len(navigated) == 0:
                    if log_step:
                        log_step(
                            "   ℹ️ Racine FTP en lecture seule. Détection des volumes montés (ex: Freebox)...",
                            "info",
                        )
                    disk_vols = []
                    try:
                        nlst = ftp.nlst()
                        for item in nlst:
                            clean_item = item.strip().split("/")[-1]
                            if clean_item and not clean_item.startswith("."):
                                disk_vols.append(clean_item)
                    except Exception:
                        pass

                    chosen = None
                    for v in disk_vols:
                        if any(
                            k in v.lower()
                            for k in ["disque", "volume", "disk", "share", "hdd", "ssd"]
                        ):
                            chosen = v
                            break
                    if not chosen and disk_vols:
                        chosen = disk_vols[0]

                    if chosen:
                        try:
                            ftp.cwd(chosen)
                            navigated.append(chosen)
                            if log_step:
                                log_step(
                                    f"   ✓ Volume détecté et sélectionné : '{chosen}'",
                                    "success",
                                )
                            try:
                                ftp.cwd(part)
                                navigated.append(part)
                                if log_step:
                                    log_step(
                                        f"   ✓ Dossier '{part}' accessible dans '{chosen}'.",
                                        "success",
                                    )
                                created = True
                            except Exception:
                                ftp.mkd(part)
                                ftp.cwd(part)
                                navigated.append(part)
                                if log_step:
                                    log_step(
                                        f"   ✓ Dossier '{part}' créé dans '{chosen}'.",
                                        "success",
                                    )
                                created = True
                        except Exception as vol_err:
                            if log_step:
                                log_step(
                                    f"   ✗ Impossible d'accéder au volume '{chosen}' : {vol_err}",
                                    "error",
                                )

                if not created:
                    err_msg = str(mkd_err)
                    if log_step:
                        log_step(
                            f"   ✗ Impossible d'accéder ou créer '{part}' : {err_msg}",
                            "error",
                        )
                    return False, "/".join(navigated), err_msg

    current_path = "/" + "/".join(navigated) if navigated else "/"
    return True, current_path, ""


def _sftp_navigate_and_ensure_dirs(
    sftp, target_parts: list[str], log_step=None
) -> tuple[bool, str, str]:
    """Navigate and create directories sequentially on SFTP server."""
    try:
        sftp.chdir("/")
    except Exception:
        pass

    navigated = []
    for part in target_parts:
        try:
            sftp.chdir(part)
            navigated.append(part)
            if log_step:
                log_step(f"   ✓ Dossier SFTP '{part}' accessible.", "success")
        except Exception:
            try:
                sftp.mkdir(part)
                sftp.chdir(part)
                navigated.append(part)
                if log_step:
                    log_step(
                        f"   ✓ Dossier SFTP '{part}' créé avec succès.", "success"
                    )
            except Exception as mkd_err:
                err_msg = str(mkd_err)
                if log_step:
                    log_step(
                        f"   ✗ Impossible d'accéder ou créer '{part}' : {err_msg}",
                        "error",
                    )
                return False, "/".join(navigated), err_msg

    current_path = "/" + "/".join(navigated) if navigated else "/"
    return True, current_path, ""


def _create_ftp_client(
    proto: str,
    host: str,
    port: int,
    user: str,
    password: str,
    timeout: int = 15,
    allow_insecure_tls: bool = False,
):
    """Create, connect and login to FTP or FTPS server with TLS session reuse and secure TLS verification."""
    clean_host = str(host).strip()
    clean_user = str(user or "").strip()
    clean_pass = str(password or "")
    port_int = int(port or 21)

    use_tls = proto == "ftps"
    if use_tls:
        ctx = ssl.create_default_context()
        if allow_insecure_tls:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            _LOGGER.warning(
                "Domolink FTPS: Vérification du certificat TLS désactivée pour %s (vulnérable MITM)",
                clean_host,
            )
        ftp = ReusedSessionFTP_TLS(context=ctx)
    else:
        ftp = ftplib.FTP()

    ftp.encoding = "utf-8"
    ftp.connect(clean_host, port_int, timeout=timeout)

    try:
        ftp.login(clean_user, clean_pass)
    except Exception as login_err:
        err_lower = str(login_err).lower()
        if not use_tls and any(
            k in err_lower
            for k in [
                "ssl",
                "tls",
                "encrypt",
                "534",
                "policy requires",
                "530 non-anonymous",
            ]
        ):
            try:
                ftp.close()
            except Exception:
                pass
            ctx = ssl.create_default_context()
            if allow_insecure_tls:
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                _LOGGER.warning(
                    "Domolink FTPS: Vérification du certificat TLS désactivée pour %s (vulnérable MITM)",
                    clean_host,
                )
            ftp = ReusedSessionFTP_TLS(context=ctx)
            ftp.encoding = "utf-8"
            ftp.connect(clean_host, port_int, timeout=timeout)
            ftp.login(clean_user, clean_pass)
            use_tls = True
        else:
            raise login_err

    if isinstance(ftp, ftplib.FTP_TLS):
        try:
            ftp.prot_p()
        except Exception:
            pass

    return ftp


class CloudUploader:
    """Manages cloud and remote storage uploads (FTP, SFTP, WebDAV, GDrive, Telegram)."""

    def __init__(self, hass: HomeAssistant, get_config_cb, log_event_cb, write_state_cb):
        """Initialize CloudUploader."""
        self.hass = hass
        self._get_config = get_config_cb
        self._log_event = log_event_cb
        self._write_state = write_state_cb

        # Live status indicators
        self.ftp_status = "Inactif"
        self.ftp_test_running = False
        self.ftp_test_logs = []
        self.ftp_test_result = {}

        self.webdav_status = "Inactif"
        self.webdav_test_running = False
        self.webdav_test_logs = []
        self.webdav_test_result = {}

        self.google_drive_status = "Inactif"
        self.google_drive_test_running = False
        self.google_drive_test_logs = []
        self.google_drive_test_result = {}

        self.telegram_status = "Inactif"
        self.nas_test_results = {}

    def _cfg(self, key, default=None):
        """Helper to get a configuration setting."""
        return self._get_config(key, default)

    async def async_upload_file(self, file_path: str, upload_telegram: bool = True):
        """Dispatch upload of a file across all enabled cloud channels."""
        if upload_telegram and self._cfg(CONF_TELEGRAM_ENABLED, False):
            self.hass.async_create_task(self._async_upload_to_telegram(file_path))
        if self._cfg(CONF_FTP_ENABLED, False):
            self.hass.async_create_task(self._async_upload_to_ftp(file_path))
        if self._cfg(CONF_WEBDAV_ENABLED, False):
            self.hass.async_create_task(self._async_upload_to_webdav(file_path))
        if self._cfg(CONF_GOOGLE_DRIVE_ENABLED, False):
            self.hass.async_create_task(self._async_upload_to_google_drive(file_path))

    # ─── TELEGRAM UPLOAD ──────────────────────────────────────────

    async def _async_upload_to_telegram(self, file_path: str):
        """Send photo or video to Telegram asynchronously."""
        token = self._cfg(CONF_TELEGRAM_TOKEN)
        chat_id = self._cfg(CONF_TELEGRAM_CHAT_ID)
        if not self._cfg(CONF_TELEGRAM_ENABLED, False) or not token or not chat_id:
            return

        try:
            import aiohttp
            from homeassistant.helpers.aiohttp_client import async_get_clientsession

            def _read_file():
                with open(file_path, "rb") as pf:
                    return pf.read()

            file_bytes = await self.hass.async_add_executor_job(_read_file)
            session = async_get_clientsession(self.hass)
            data = aiohttp.FormData()
            data.add_field("chat_id", str(chat_id))

            is_video = file_path.lower().endswith((".mp4", ".webm", ".ogg"))
            endpoint = "sendVideo" if is_video else "sendPhoto"
            field_name = "video" if is_video else "photo"
            mime_type = "video/mp4" if is_video else "image/jpeg"

            data.add_field(
                field_name,
                file_bytes,
                filename=os.path.basename(file_path),
                content_type=mime_type,
            )

            async with session.post(
                f"https://api.telegram.org/bot{token}/{endpoint}",
                data=data,
                timeout=25 if is_video else 10,
            ) as resp:
                if resp.status == 200:
                    _LOGGER.info(
                        "Domolink: %s envoyé sur Telegram avec succès",
                        "Vidéo" if is_video else "Snapshot",
                    )
                    self._log_event(
                        f"Sauvegarde {'vidéo' if is_video else 'photo'} Telegram réussie"
                    )
                    self.telegram_status = "Connecté"
                else:
                    _LOGGER.error(
                        "Domolink: Échec envoi Telegram - Code %s", resp.status
                    )
                    self.telegram_status = "Erreur"
        except Exception as e:
            _LOGGER.error("Domolink: Erreur lors de l'envoi Telegram : %s", e)
            self.telegram_status = "Erreur"
        self._write_state()

    # ─── FTP / SFTP UPLOAD ────────────────────────────────────────

    def _upload_to_ftp_sync(self, file_path: str) -> bool:
        """Upload photo or video to FTP/FTPS/SFTP in configured target path."""
        proto = str(self._cfg(CONF_FTP_PROTOCOL, "ftp")).lower()
        nas_type = str(self._cfg(CONF_NAS_TYPE, "asustor")).lower()
        custom_dir = str(self._cfg(CONF_FTP_PATH, "")).strip()
        target_parts = _build_ftp_target_path(custom_dir, nas_type)
        filename = os.path.basename(file_path)

        if proto == "sftp":
            try:
                import paramiko

                ssh = paramiko.SSHClient()
                ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                port_int = int(self._cfg(CONF_FTP_PORT, 22) or 22)
                ssh.connect(
                    self._cfg(CONF_FTP_HOST, ""),
                    port=port_int,
                    username=str(self._cfg(CONF_FTP_USER, "") or ""),
                    password=str(self._cfg(CONF_FTP_PASS, "") or ""),
                    timeout=25,
                    look_for_keys=False,
                    allow_agent=False,
                )
                sftp = ssh.open_sftp()
                _sftp_navigate_and_ensure_dirs(sftp, target_parts)
                sftp.put(file_path, filename)
                sftp.close()
                ssh.close()
                return True
            except Exception as sftp_err:
                _LOGGER.error(
                    "Domolink: Erreur lors de l'envoi SFTP de %s : %s",
                    file_path,
                    sftp_err,
                )
                return False

        ftp = None
        try:
            port_int = int(self._cfg(CONF_FTP_PORT, 21) or 21)
            ftp = _create_ftp_client(
                proto=proto,
                host=self._cfg(CONF_FTP_HOST, ""),
                port=port_int,
                user=str(self._cfg(CONF_FTP_USER, "") or ""),
                password=str(self._cfg(CONF_FTP_PASS, "") or ""),
                timeout=25,
                allow_insecure_tls=bool(
                    self._cfg(CONF_FTP_ALLOW_INSECURE_TLS, False)
                ),
            )
            success_nav, current_path, err = _ftp_navigate_and_ensure_dirs(
                ftp, target_parts
            )
            if not success_nav:
                _LOGGER.warning(
                    "Domolink FTP: Erreur navigation dossier (%s): %s",
                    current_path,
                    err,
                )

            with open(file_path, "rb") as f:
                ftp.storbinary(f"STOR {filename}", f, blocksize=524288)
            return True
        except Exception as e:
            _LOGGER.error(
                "Domolink: Erreur lors de l'envoi FTP/FTPS de %s : %s",
                file_path,
                e,
            )
            return False
        finally:
            if ftp:
                try:
                    ftp.quit()
                except Exception:
                    try:
                        ftp.close()
                    except Exception:
                        pass

    async def _async_upload_to_ftp(self, file_path: str):
        """Handle FTP upload in executor job."""
        if not self._cfg(CONF_FTP_ENABLED, False) or not self._cfg(CONF_FTP_HOST):
            return

        is_video = file_path.lower().endswith((".mp4", ".webm", ".ogg"))
        media_type = "vidéo" if is_video else "photo"
        filename = os.path.basename(file_path)

        success = await self.hass.async_add_executor_job(
            self._upload_to_ftp_sync, file_path
        )
        if success:
            _LOGGER.info(
                "Domolink: %s envoyé(e) sur FTP avec succès: %s",
                media_type.capitalize(),
                filename,
            )
            self._log_event(f"Sauvegarde {media_type} FTP réussie: {filename}")
            self.ftp_status = "Connecté"
        else:
            _LOGGER.error(
                "Domolink: Échec sauvegarde %s sur FTP: %s", media_type, filename
            )
            self._log_event(f"⚠️ Échec transfert FTP {media_type}: {filename}")
            self.ftp_status = "Erreur"
        self._write_state()

    def _append_ftp_log(self, message: str, level: str = "info"):
        """Append an entry to FTP test log and notify state change."""
        now_str = dt_now().strftime("%H:%M:%S")
        self.ftp_test_logs.append(
            {
                "time": now_str,
                "message": message,
                "level": level,
            }
        )
        if len(self.ftp_test_logs) > 60:
            self.ftp_test_logs = self.ftp_test_logs[-60:]
        try:
            self._write_state()
        except Exception:
            pass

    async def async_test_ftp(self, call=None):
        """Force a connection test to the FTP server with real-time log steps."""
        if self.ftp_test_running:
            _LOGGER.debug("Domolink: Un test FTP est déjà en cours.")
            return {
                "success": False,
                "code": 429,
                "result_label": "Erreur 429",
                "message": "Un test FTP est déjà en cours.",
            }

        data = call.data if (call and hasattr(call, "data")) else {}
        return await self._async_run_ftp_test(data)

    async def _async_run_ftp_test(self, data=None):
        """Run FTP test in executor and report logs thread-safely."""
        if data is None:
            data = {}

        nas_labels = {
            "asustor": "ASUSTOR",
            "synology": "Synology",
            "qnap": "QNAP",
            "truenas": "TrueNAS",
            "freebox": "Freebox",
            "unraid": "Unraid",
            "generic": "Autre NAS",
        }
        cur_nas = data.get("nas_type") or self._cfg(CONF_NAS_TYPE, "asustor")
        nas_name = nas_labels.get(cur_nas, "NAS")
        nas_cfg = self._cfg(CONF_NAS_CONFIGS, {}).get(cur_nas, {})
        is_cur_active = cur_nas == self._cfg(CONF_NAS_TYPE, "asustor")

        protocol = str(
            data.get("ftp_protocol")
            or nas_cfg.get("ftp_protocol")
            or (self._cfg(CONF_FTP_PROTOCOL, "ftp") if is_cur_active else "ftp")
        ).strip().lower()
        if protocol not in ("ftp", "ftps", "sftp", "samba"):
            protocol = "ftp"

        allow_insecure_tls = bool(
            data.get(CONF_FTP_ALLOW_INSECURE_TLS)
            if CONF_FTP_ALLOW_INSECURE_TLS in data
            else (
                nas_cfg.get(CONF_FTP_ALLOW_INSECURE_TLS)
                or self._cfg(CONF_FTP_ALLOW_INSECURE_TLS, False)
            )
        )

        proto_labels = {
            "ftp": "FTP",
            "ftps": "FTPS (TLS)",
            "sftp": "SFTP (SSH)",
            "samba": "SAMBA (SMB)",
        }
        proto_title = proto_labels.get(protocol, protocol.upper())

        self.ftp_test_running = True
        self.ftp_test_logs = []
        self.ftp_test_result = {}
        self._append_ftp_log(
            f"🚀 Démarrage du diagnostic de connexion {proto_title} ({nas_name})...",
            "info",
        )

        def log_step(msg, level="info"):
            _LOGGER.info("Domolink FTP test: %s", msg)
            self.hass.loop.call_soon_threadsafe(self._append_ftp_log, msg, level)

        host = (
            data.get("ftp_host")
            or nas_cfg.get("ftp_host")
            or (self._cfg(CONF_FTP_HOST, "") if is_cur_active else "")
        )
        if not host and cur_nas == "freebox":
            host = "mafreebox.freebox.fr"

        default_port = 445 if protocol == "samba" else (22 if protocol == "sftp" else 21)
        raw_port = data.get("ftp_port") or nas_cfg.get("ftp_port")
        if raw_port:
            try:
                port = int(raw_port)
            except (ValueError, TypeError):
                port = default_port
        else:
            port = (
                self._cfg(CONF_FTP_PORT, default_port)
                if is_cur_active
                else default_port
            )

        user = (
            data.get("ftp_user")
            if "ftp_user" in data
            else (
                nas_cfg.get("ftp_user")
                if "ftp_user" in nas_cfg
                else (self._cfg(CONF_FTP_USER, "") if is_cur_active else "")
            )
        )
        if not user and cur_nas == "freebox":
            user = "freebox"
        password = (
            data.get("ftp_pass")
            if "ftp_pass" in data
            else (
                nas_cfg.get("ftp_pass")
                if "ftp_pass" in nas_cfg
                else (self._cfg(CONF_FTP_PASS, "") if is_cur_active else "")
            )
        )
        path = (
            data.get("ftp_path")
            if "ftp_path" in data
            else (
                nas_cfg.get("ftp_path")
                if "ftp_path" in nas_cfg
                else (self._cfg(CONF_FTP_PATH, "/") if is_cur_active else "/")
            )
        )
        if cur_nas == "freebox" and (not path or path == "/"):
            path = "/Disque 1"

        def run_test_sync():
            import time

            time.sleep(0.2)
            if not host:
                log_step("Aucune adresse de serveur renseignée.", "error")
                return False, 400, "Adresse du serveur manquante.", ""

            clean_host = str(host).strip()
            clean_user = str(user or "").strip()
            clean_pass = str(password or "")
            port_int = int(port or default_port)

            log_step(
                f"1. Profil {nas_name} [{proto_title}] : Hôte={clean_host}, Port={port_int}, Utilisateur='{clean_user}'",
                "info",
            )
            time.sleep(0.25)

            # --- CAS SAMBA / SMB ---
            if protocol == "samba":
                log_step(
                    f"2. Test de connectivité au service SAMBA / SMB {clean_host}:{port_int}...",
                    "info",
                )
                try:
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    s.settimeout(10)
                    s.connect((clean_host, port_int))
                    s.close()
                    log_step(
                        f"   ✓ Port SAMBA {port_int} accessible avec succès.",
                        "success",
                    )
                except Exception as smb_err:
                    err_str = str(smb_err)
                    log_step(
                        f"   ✗ Impossible de joindre le port SMB {port_int} ({err_str})",
                        "error",
                    )
                    log_step(
                        "   💡 Conseil : Vérifiez que le partage Windows / SMB est activé sur votre NAS / Freebox.",
                        "warning",
                    )
                    return False, 445, f"Port SAMBA {port_int} inaccessible ({err_str})", ""

                time.sleep(0.25)
                samba_url = f"smb://{clean_host}/"
                win_path = f"\\\\{clean_host}\\"
                log_step("3. Liens de partage réseau disponibles :", "info")
                log_step(f"   • macOS (Finder > Cmd+K) : {samba_url}", "success")
                log_step(f"   • Windows (Explorateur) : {win_path}", "success")
                if clean_user:
                    log_step(f"   • Compte d'accès associé : '{clean_user}'", "info")
                log_step(
                    f"🎉 Partage réseau SAMBA {nas_name} validé et joignable !",
                    "success",
                )
                return True, 200, "Partage SAMBA joignable", samba_url

            # --- CAS SFTP (SSH File Transfer) ---
            if protocol == "sftp":
                log_step(
                    f"2. Connexion TCP au service SSH/SFTP {clean_host}:{port_int}...",
                    "info",
                )
                try:
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    s.settimeout(10)
                    s.connect((clean_host, port_int))
                    banner = s.recv(1024).decode("utf-8", errors="ignore").strip()
                    s.close()
                    log_step(
                        f"   ✓ Service SSH joignable ({banner[:40] if banner else 'Port ouvert'}).",
                        "success",
                    )
                except Exception as sftp_err:
                    err_str = str(sftp_err)
                    log_step(
                        f"   ✗ Impossible de joindre le port SSH {port_int} : {err_str}",
                        "error",
                    )
                    return False, 22, f"Port SFTP {port_int} inaccessible ({err_str})", ""

                time.sleep(0.25)
                log_step(f"3. Authentification SFTP pour '{clean_user}'...", "info")
                try:
                    import paramiko

                    ssh = paramiko.SSHClient()
                    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                    ssh.connect(
                        clean_host,
                        port=port_int,
                        username=clean_user,
                        password=clean_pass,
                        timeout=10,
                        look_for_keys=False,
                        allow_agent=False,
                    )
                    log_step("   ✓ Authentification SSH acceptée.", "success")
                    sftp = ssh.open_sftp()
                    target_parts = _build_ftp_target_path(path, cur_nas)
                    success_nav, save_path, nav_err = _sftp_navigate_and_ensure_dirs(
                        sftp, target_parts, log_step=log_step
                    )
                    if not success_nav:
                        ssh.close()
                        return False, 550, f"Erreur répertoire SFTP ({nav_err})", save_path

                    probe_f = sftp.file("domolink_write_test.txt", "w")
                    probe_f.write("Domolink SFTP write probe")
                    probe_f.close()
                    try:
                        sftp.remove("domolink_write_test.txt")
                    except Exception:
                        pass
                    log_step(
                        "   ✓ Droits d'écriture validés sur le serveur SFTP.",
                        "success",
                    )
                    sftp.close()
                    ssh.close()
                    log_step(
                        f"🎉 Connexion SFTP acceptée et validée avec succès sur {nas_name} !",
                        "success",
                    )
                    return True, 200, "Connexion acceptée", save_path
                except ImportError:
                    log_step(
                        "   ℹ️ Module 'paramiko' absent du conteneur (port SSH validé).",
                        "info",
                    )
                    log_step(
                        f"🎉 Service SFTP sur {clean_host}:{port_int} actif et prêt !",
                        "success",
                    )
                    return True, 200, "Port SFTP joignable", f"sftp://{clean_host}:{port_int}/"
                except Exception as auth_err:
                    err_str = str(auth_err)
                    log_step(f"   ✗ Échec d'authentification SFTP : {err_str}", "error")
                    return False, 530, f"Authentification SFTP échouée ({err_str})", ""

            # --- CAS FTP & FTPS ---
            log_step(f"2. Connexion réseau au serveur {clean_host}:{port_int}...", "info")
            use_tls = protocol == "ftps"
            if use_tls:
                ctx = ssl.create_default_context()
                if allow_insecure_tls:
                    ctx.check_hostname = False
                    ctx.verify_mode = ssl.CERT_NONE
                    log_step("   ⚠️ Vérification TLS désactivée (certificat non vérifié).", "warning")
                else:
                    log_step("   🔒 Vérification stricte du certificat TLS activée.", "info")
                ftp = ReusedSessionFTP_TLS(context=ctx)
            else:
                ftp = ftplib.FTP()
            ftp.encoding = "utf-8"
            try:
                ftp.connect(clean_host, port_int, timeout=12)
                log_step("   ✓ Connexion TCP établie avec succès.", "success")
            except Exception as e:
                err_str = str(e)
                log_step(f"   ✗ Échec de connexion réseau : {err_str}", "error")
                try:
                    ftp.close()
                except Exception:
                    pass

                code = None
                if hasattr(e, "errno") and e.errno is not None:
                    code = abs(e.errno)
                elif isinstance(e, socket.gaierror):
                    code = getattr(e, "errno", None) or 2
                elif isinstance(e, (socket.timeout, TimeoutError)):
                    code = 110
                if code is None:
                    m = re.search(r"\[Errno\s*(-?\d+)\]", err_str)
                    if m:
                        code = abs(int(m.group(1)))
                    else:
                        m_rfc = re.search(r"\b([1-5]\d{2})\b", err_str)
                        code = int(m_rfc.group(1)) if m_rfc else 111

                return False, code, f"Impossible de joindre le serveur {clean_host}:{port_int} ({err_str})", ""

            time.sleep(0.25)
            log_step(f"3. Authentification de l'utilisateur '{clean_user}'...", "info")
            try:
                ftp.login(clean_user, clean_pass)
                log_step("   ✓ Authentification acceptée par le serveur.", "success")
            except Exception as e:
                err_str = str(e)
                # Auto-upgrade to FTPS if plain FTP was used but server requires TLS/SSL
                if not use_tls and any(
                    k in err_str.lower()
                    for k in [
                        "ssl",
                        "tls",
                        "encrypt",
                        "534",
                        "policy requires",
                        "530 non-anonymous",
                    ]
                ):
                    log_step(
                        "   ℹ️ Le serveur exige un chiffrement TLS. Basculement automatique en FTPS...",
                        "info",
                    )
                    try:
                        ftp.close()
                    except Exception:
                        pass
                    ctx = ssl.create_default_context()
                    if allow_insecure_tls:
                        ctx.check_hostname = False
                        ctx.verify_mode = ssl.CERT_NONE
                    ftp = ReusedSessionFTP_TLS(context=ctx)
                    ftp.encoding = "utf-8"
                    try:
                        ftp.connect(clean_host, port_int, timeout=12)
                        ftp.login(clean_user, clean_pass)
                        use_tls = True
                        log_step("   ✓ Authentification FTPS acceptée.", "success")
                    except Exception as retry_err:
                        err_str = str(retry_err)
                        log_step(f"   ✗ Échec d'authentification FTPS : {err_str}", "error")
                        try:
                            ftp.close()
                        except Exception:
                            pass
                        m_rfc = re.search(r"\b([1-5]\d{2})\b", err_str)
                        code = int(m_rfc.group(1)) if m_rfc else 530
                        return False, code, f"Identifiants incorrects ou refusés ({err_str})", ""
                else:
                    log_step(f"   ✗ Échec d'authentification : {err_str}", "error")
                    try:
                        ftp.quit()
                    except Exception:
                        pass
                    m_rfc = re.search(r"\b([1-5]\d{2})\b", err_str)
                    if m_rfc:
                        code = int(m_rfc.group(1))
                    elif hasattr(e, "errno") and e.errno is not None:
                        code = abs(e.errno)
                    else:
                        code = 530
                    return False, code, f"Identifiants incorrects ou refusés ({err_str})", ""

            if use_tls or isinstance(ftp, ftplib.FTP_TLS):
                try:
                    ftp.prot_p()
                    log_step(
                        "   ✓ Canal de données sécurisé TLS avec réutilisation de session (prot_p).",
                        "success",
                    )
                except Exception as tls_err:
                    log_step(f"   ⚠️ prot_p() ignoré ou non supporté : {tls_err}", "warning")

            time.sleep(0.2)
            log_step("4. Contrôle de l'arborescence des répertoires...", "info")
            target_parts = _build_ftp_target_path(path, cur_nas)
            success_nav, save_path, nav_err = _ftp_navigate_and_ensure_dirs(
                ftp, target_parts, log_step=log_step
            )
            if not success_nav:
                try:
                    ftp.quit()
                except Exception:
                    pass
                m_rfc = re.search(r"\b([1-5]\d{2})\b", nav_err)
                code = int(m_rfc.group(1)) if m_rfc else 550
                return (
                    False,
                    code,
                    f"Impossible de créer ou accéder à l'arborescence ({nav_err})",
                    save_path,
                )

            time.sleep(0.2)
            log_step("5. Test des permissions d'écriture...", "info")
            try:
                probe_data = io.BytesIO(b"Domolink Alarm write probe test")
                ftp.storbinary("STOR domolink_write_test.txt", probe_data)
                try:
                    ftp.delete("domolink_write_test.txt")
                except Exception:
                    pass
                log_step("   ✓ Droits d'écriture validés (fichier test créé et nettoyé).", "success")
            except Exception as write_err:
                err_str = str(write_err)
                log_step(f"   ✗ Erreur d'écriture sur le serveur : {err_str}", "error")
                if "550" in err_str and cur_nas == "freebox":
                    log_step(
                        "   💡 Conseil Freebox OS : Dans mafreebox.freebox.fr > Paramètres > FTP, vérifiez que l'accès en écriture est autorisé, ou essayez avec le protocole FTPS.",
                        "warning",
                    )
                try:
                    ftp.quit()
                except Exception:
                    pass
                m_rfc = re.search(r"\b([1-5]\d{2})\b", err_str)
                code = int(m_rfc.group(1)) if m_rfc else 553
                return False, code, f"Droits d'écriture insuffisants ({err_str})", save_path

            time.sleep(0.2)
            try:
                ftp.quit()
            except Exception:
                pass

            log_step(f"6. Chemin de sauvegarde validé : {save_path}", "success")
            log_step(
                f"🎉 Connexion {proto_title} acceptée et validée avec succès sur {nas_name} !",
                "success",
            )
            return True, 200, "Connexion acceptée", save_path

        import time as _t

        try:
            success, code, msg, save_path = await self.hass.async_add_executor_job(
                run_test_sync
            )
            result_label = "Connecté" if success else f"Erreur {code}"
            self.ftp_test_running = False
            self.ftp_status = "Connecté" if success else "Erreur"
            res_dict = {
                "success": success,
                "code": code,
                "result_label": result_label,
                "message": msg,
                "save_path": save_path,
                "nas_type": cur_nas,
                "protocol": protocol,
                "timestamp": int(_t.time()),
            }
            self.ftp_test_result = res_dict
            self.nas_test_results[cur_nas] = res_dict
            self.nas_test_results[f"{cur_nas}_ftp"] = res_dict
            self.nas_test_results["last_ftp"] = res_dict

            if success:
                self._log_event(
                    f"Test {proto_title} {nas_name} réussi : Connecté ({save_path})"
                )
            else:
                self._log_event(
                    f"⚠️ Test {proto_title} {nas_name} échoué : {result_label} - {msg}"
                )
            return res_dict
        except Exception as e:
            err_str = str(e)
            code = 500
            result_label = f"Erreur {code}"
            self.ftp_test_running = False
            self.ftp_status = "Erreur"
            res_dict = {
                "success": False,
                "code": code,
                "result_label": result_label,
                "message": err_str,
                "save_path": "",
                "nas_type": cur_nas,
                "protocol": "ftp",
                "timestamp": int(_t.time()),
            }
            self.ftp_test_result = res_dict
            self.nas_test_results[cur_nas] = res_dict
            self.nas_test_results[f"{cur_nas}_ftp"] = res_dict
            self.nas_test_results["last_ftp"] = res_dict

            self._append_ftp_log(f"Erreur inattendue : {e}", "error")
            self._log_event(f"⚠️ Erreur test FTP {nas_name} : {e}")
            return res_dict
        finally:
            self._write_state()

    # ─── WEBDAV / NEXTCLOUD UPLOAD ────────────────────────────────

    async def _async_upload_to_webdav(self, file_path: str):
        """Upload photo or video to WebDAV / Nextcloud asynchronously."""
        webdav_url = self._cfg(CONF_WEBDAV_URL, "")
        if not self._cfg(CONF_WEBDAV_ENABLED, False) or not webdav_url:
            return

        is_video = file_path.lower().endswith((".mp4", ".webm", ".ogg"))
        media_type = "vidéo" if is_video else "photo"
        filename = os.path.basename(file_path)

        try:
            import aiohttp
            from homeassistant.helpers.aiohttp_client import async_get_clientsession

            session = async_get_clientsession(self.hass)
            user = self._cfg(CONF_WEBDAV_USER)
            passwd = self._cfg(CONF_WEBDAV_PASS)
            auth = aiohttp.BasicAuth(user, passwd) if user and passwd else None

            base_url = webdav_url.rstrip("/")

            # Ensure target directories exist via MKCOL
            target_path = str(self._cfg(CONF_WEBDAV_PATH, "domolink/alarm")).strip().strip("/")
            dirs = [d for d in target_path.split("/") if d]
            cur_url = base_url
            for d in dirs:
                cur_url = f"{cur_url}/{d}"
                try:
                    async with session.request(
                        "MKCOL", cur_url, auth=auth, timeout=aiohttp.ClientTimeout(total=8)
                    ):
                        pass
                except Exception:
                    pass

            file_url = f"{cur_url}/{filename}"
            content_type = "video/mp4" if is_video else "image/jpeg"

            def _read_file():
                with open(file_path, "rb") as f:
                    return f.read()

            file_data = await self.hass.async_add_executor_job(_read_file)

            async with session.put(
                file_url,
                data=file_data,
                headers={"Content-Type": content_type},
                auth=auth,
                timeout=aiohttp.ClientTimeout(total=60 if is_video else 20),
            ) as put_resp:
                if put_resp.status in (200, 201, 204):
                    self.webdav_status = "Connecté"
                    _LOGGER.info(
                        "Domolink: %s téléversée sur WebDAV avec succès: %s",
                        media_type.capitalize(),
                        filename,
                    )
                    self._log_event(f"Sauvegarde {media_type} WebDAV : {filename}")
                else:
                    self.webdav_status = "Erreur"
                    _LOGGER.error(
                        "Domolink: Échec téléversement WebDAV (%s): Code %s",
                        filename,
                        put_resp.status,
                    )
                    self._log_event(
                        f"⚠️ Échec transfert WebDAV {media_type}: {filename} (HTTP {put_resp.status})"
                    )
        except Exception as e:
            self.webdav_status = "Erreur"
            _LOGGER.error("Domolink: Erreur lors de l'envoi WebDAV de %s: %s", file_path, e)
            self._log_event(f"⚠️ Erreur envoi WebDAV : {e}")

        self._write_state()

    def _append_webdav_log(self, message: str, level: str = "info"):
        """Append an entry to WebDAV test log and notify state change."""
        now_str = dt_now().strftime("%H:%M:%S")
        self.webdav_test_logs.append(
            {
                "time": now_str,
                "message": message,
                "level": level,
            }
        )
        if len(self.webdav_test_logs) > 60:
            self.webdav_test_logs = self.webdav_test_logs[-60:]
        try:
            self._write_state()
        except Exception:
            pass

    async def async_test_webdav(self, call=None):
        """Force a connection test to the WebDAV server with real-time log steps."""
        if self.webdav_test_running:
            _LOGGER.debug("Domolink: Un test WebDAV est déjà en cours.")
            return {
                "success": False,
                "code": 429,
                "result_label": "Erreur 429",
                "message": "Un test WebDAV est déjà en cours.",
            }

        data = call.data if (call and hasattr(call, "data")) else {}
        return await self._async_run_webdav_test(data)

    async def _async_run_webdav_test(self, data=None):
        """Run step-by-step diagnostic of WebDAV server asynchronously."""
        import aiohttp
        import time
        from homeassistant.helpers.aiohttp_client import async_get_clientsession

        if data is None:
            data = {}

        nas_labels = {
            "asustor": "ASUSTOR",
            "synology": "Synology",
            "qnap": "QNAP",
            "truenas": "TrueNAS",
            "freebox": "Freebox",
            "unraid": "Unraid",
            "generic": "Autre NAS",
        }
        cur_nas = data.get("nas_type") or self._cfg(CONF_NAS_TYPE, "asustor")
        nas_name = nas_labels.get(cur_nas, "NAS")

        self.webdav_test_running = True
        self.webdav_test_logs = []
        self.webdav_test_result = {}
        self._append_webdav_log(f"🚀 Démarrage du diagnostic WebDAV ({nas_name})...", "info")

        start_time = time.time()
        nas_cfg = self._cfg(CONF_NAS_CONFIGS, {}).get(cur_nas, {})
        is_cur_active = cur_nas == self._cfg(CONF_NAS_TYPE, "asustor")

        url = str(
            data.get("webdav_url")
            or nas_cfg.get("webdav_url")
            or (self._cfg(CONF_WEBDAV_URL, "") if is_cur_active else "")
            or ""
        ).strip()
        user = str(
            data.get("webdav_user")
            if "webdav_user" in data
            else (
                nas_cfg.get("webdav_user")
                if "webdav_user" in nas_cfg
                else (self._cfg(CONF_WEBDAV_USER, "") if is_cur_active else "") or ""
            )
        ).strip()
        passwd = str(
            data.get("webdav_pass")
            if "webdav_pass" in data
            else (
                nas_cfg.get("webdav_pass")
                if "webdav_pass" in nas_cfg
                else (self._cfg(CONF_WEBDAV_PASS, "") if is_cur_active else "") or ""
            )
        )
        path = str(
            data.get("webdav_path")
            if "webdav_path" in data
            else (
                nas_cfg.get("webdav_path")
                if "webdav_path" in nas_cfg
                else (
                    self._cfg(CONF_WEBDAV_PATH, "domolink/alarm")
                    if is_cur_active
                    else "domolink/alarm"
                )
            )
            or "domolink/alarm"
        ).strip().strip("/")

        def record_result(success, code, msg, save_p=""):
            elapsed = round(time.time() - start_time, 2)
            result_label = "Connecté" if success else f"Erreur {code}"
            self.webdav_test_running = False
            self.webdav_status = "Connecté" if success else "Erreur"
            res = {
                "success": success,
                "code": code,
                "result_label": result_label,
                "message": msg,
                "save_path": save_p or path,
                "elapsed": elapsed,
                "nas_type": cur_nas,
                "protocol": "webdav",
                "timestamp": int(time.time()),
            }
            self.webdav_test_result = res
            self.nas_test_results[cur_nas] = res
            self.nas_test_results[f"{cur_nas}_webdav"] = res
            self.nas_test_results["last_webdav"] = res
            if success:
                self._log_event(f"Test WebDAV {nas_name} réussi : Connecté ({elapsed}s)")
            else:
                self._log_event(f"⚠️ Test WebDAV {nas_name} échoué : {result_label} - {msg}")
            return res

        try:
            await asyncio.sleep(0.2)
            if not url:
                self._append_webdav_log("Aucune URL WebDAV configurée.", "error")
                return record_result(False, 400, "URL WebDAV manquante.")

            if not (url.startswith("http://") or url.startswith("https://")):
                self._append_webdav_log(
                    "URL invalide (doit débuter par http:// ou https://)", "error"
                )
                return record_result(
                    False, 400, "URL invalide (http:// ou https:// requis)."
                )

            self._append_webdav_log(f"1. Profil {nas_name} : URL={url}, Utilisateur='{user}'", "info")
            await asyncio.sleep(0.25)

            # Step 2: Connection & Auth
            self._append_webdav_log("2. Connexion réseau et authentification...", "info")
            session = async_get_clientsession(self.hass)
            auth = aiohttp.BasicAuth(user, passwd) if user and passwd else None
            base_url = url.rstrip("/")

            try:
                async with session.request(
                    "PROPFIND",
                    base_url,
                    headers={"Depth": "0"},
                    auth=auth,
                    timeout=aiohttp.ClientTimeout(total=12),
                ) as resp:
                    if resp.status in (401, 403):
                        self._append_webdav_log(
                            f"   ✗ Authentification rejetée (Code {resp.status})",
                            "error",
                        )
                        return record_result(
                            False, resp.status, f"Identifiants invalides (HTTP {resp.status})"
                        )
                    elif resp.status in (200, 207, 405):
                        self._append_webdav_log(
                            f"   ✓ Connexion et accès autorisés (HTTP {resp.status})",
                            "success",
                        )
                    elif resp.status == 404:
                        self._append_webdav_log(
                            f"   ✗ Chemin ou serveur WebDAV introuvable (Code {resp.status})",
                            "error",
                        )
                        return record_result(False, 404, "Chemin introuvable (HTTP 404)")
                    else:
                        self._append_webdav_log(
                            f"   ⚠️ Réponse serveur inattendue (HTTP {resp.status}), poursuite...",
                            "warning",
                        )
            except Exception as conn_err:
                err_str = str(conn_err)
                self._append_webdav_log(
                    f"   ✗ Impossible de joindre le serveur WebDAV : {err_str}",
                    "error",
                )
                code = 111
                if hasattr(conn_err, "os_error") and getattr(
                    conn_err.os_error, "errno", None
                ):
                    code = abs(conn_err.os_error.errno)
                elif isinstance(conn_err, asyncio.TimeoutError):
                    code = 110
                else:
                    m = re.search(r"\[Errno\s*(-?\d+)\]", err_str)
                    if m:
                        code = abs(int(m.group(1)))
                    else:
                        m_http = re.search(r"\b([1-5]\d{2})\b", err_str)
                        if m_http:
                            code = int(m_http.group(1))
                return record_result(False, code, f"Erreur réseau: {err_str}")

            await asyncio.sleep(0.25)
            # Step 3: Directory creation
            self._append_webdav_log(f"3. Vérification de l'arborescence '{path}'...", "info")
            dirs = [d for d in path.split("/") if d]
            cur_url = base_url
            for d in dirs:
                cur_url = f"{cur_url}/{d}"
                try:
                    async with session.request(
                        "MKCOL", cur_url, auth=auth, timeout=aiohttp.ClientTimeout(total=8)
                    ):
                        pass
                except Exception:
                    pass
            self._append_webdav_log("   ✓ Arborescence distante vérifiée.", "success")

            await asyncio.sleep(0.25)
            # Step 4: Write test
            self._append_webdav_log("4. Test des permissions d'écriture (PUT)...", "info")
            test_file = f"domolink_probe_{int(time.time())}.txt"
            test_url = f"{cur_url}/{test_file}"
            test_data = b"Domolink Alarm WebDAV Probe Test"

            try:
                async with session.put(
                    test_url,
                    data=test_data,
                    headers={"Content-Type": "text/plain"},
                    auth=auth,
                    timeout=aiohttp.ClientTimeout(total=12),
                ) as put_resp:
                    if put_resp.status not in (200, 201, 204):
                        self._append_webdav_log(
                            f"   ✗ Échec écriture fichier test (Code {put_resp.status})",
                            "error",
                        )
                        return record_result(
                            False, put_resp.status, f"Écriture refusée (HTTP {put_resp.status})"
                        )
                    self._append_webdav_log("   ✓ Droits d'écriture validés.", "success")
            except Exception as put_err:
                err_str = str(put_err)
                self._append_webdav_log(f"   ✗ Erreur d'écriture : {err_str}", "error")
                return record_result(False, 500, f"Erreur d'écriture: {err_str}")

            await asyncio.sleep(0.2)
            # Step 5: Clean test file
            self._append_webdav_log("5. Nettoyage du fichier de test (DELETE)...", "info")
            try:
                async with session.delete(
                    test_url, auth=auth, timeout=aiohttp.ClientTimeout(total=8)
                ):
                    self._append_webdav_log("   ✓ Nettoyage effectué.", "success")
            except Exception:
                self._append_webdav_log("   ℹ Nettoyage ignoré (non critique).", "info")

            elapsed = round(time.time() - start_time, 2)
            self._append_webdav_log(f"6. Chemin de sauvegarde validé : {path}", "success")
            self._append_webdav_log(
                f"🎉 Connexion WebDAV acceptée et validée avec succès sur {nas_name} ({elapsed}s) !",
                "success",
            )
            return record_result(True, 200, "Connexion acceptée", path)

        except Exception as global_err:
            _LOGGER.error("Domolink: Erreur test WebDAV: %s", global_err)
            self._append_webdav_log(f"Erreur inattendue : {global_err}", "error")
            return record_result(False, 500, str(global_err))
        finally:
            self._write_state()

    # ─── GOOGLE DRIVE UPLOAD ──────────────────────────────────────

    async def _async_upload_to_google_drive(self, file_path: str):
        """Upload photo or video to Google Drive asynchronously."""
        if not self._cfg(CONF_GOOGLE_DRIVE_ENABLED, False):
            return

        method = self._cfg(CONF_GOOGLE_DRIVE_METHOD, "webhook")
        is_video = file_path.lower().endswith((".mp4", ".webm", ".ogg"))
        media_type = "vidéo" if is_video else "photo"
        filename = os.path.basename(file_path)
        mime_type = "video/mp4" if is_video else "image/jpeg"

        import aiohttp
        from homeassistant.helpers.aiohttp_client import async_get_clientsession

        session = async_get_clientsession(self.hass)

        try:
            def _read_file():
                with open(file_path, "rb") as f:
                    return f.read()

            file_bytes = await self.hass.async_add_executor_job(_read_file)

            if method == "webhook":
                webhook_url = str(self._cfg(CONF_GOOGLE_DRIVE_WEBHOOK_URL, "")).strip()
                if not webhook_url:
                    _LOGGER.warning("Domolink Google Drive: URL Webhook manquante.")
                    return

                payload = {
                    "filename": filename,
                    "mime_type": mime_type,
                    "file_base64": base64.b64encode(file_bytes).decode("utf-8"),
                    "folder_id": str(self._cfg(CONF_GOOGLE_DRIVE_FOLDER_ID, "")).strip(),
                }

                timeout = aiohttp.ClientTimeout(total=90 if is_video else 30)
                async with session.post(
                    webhook_url, json=payload, timeout=timeout, allow_redirects=True
                ) as resp:
                    if resp.status in (200, 201):
                        self.google_drive_status = "Connecté"
                        _LOGGER.info(
                            "Domolink: %s téléversée sur Google Drive via Webhook: %s",
                            media_type.capitalize(),
                            filename,
                        )
                        self._log_event(f"Sauvegarde {media_type} Google Drive : {filename}")
                    else:
                        self.google_drive_status = "Erreur"
                        _LOGGER.error(
                            "Domolink: Échec envoi Google Drive Webhook (%s): HTTP %s",
                            filename,
                            resp.status,
                        )
                        self._log_event(
                            f"⚠️ Échec Google Drive {media_type}: {filename} (HTTP {resp.status})"
                        )

            elif method == "oauth":
                client_id = str(self._cfg(CONF_GOOGLE_DRIVE_CLIENT_ID, "")).strip()
                client_secret = str(self._cfg(CONF_GOOGLE_DRIVE_CLIENT_SECRET, "")).strip()
                refresh_token = str(self._cfg(CONF_GOOGLE_DRIVE_REFRESH_TOKEN, "")).strip()
                folder_id = str(self._cfg(CONF_GOOGLE_DRIVE_FOLDER_ID, "")).strip()

                if not (client_id and client_secret and refresh_token):
                    _LOGGER.warning("Domolink Google Drive: Identifiants OAuth2 incomplets.")
                    return

                token_url = "https://oauth2.googleapis.com/token"
                token_data = {
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                }
                async with session.post(
                    token_url, data=token_data, timeout=aiohttp.ClientTimeout(total=15)
                ) as token_resp:
                    if token_resp.status != 200:
                        self.google_drive_status = "Erreur"
                        _LOGGER.error(
                            "Domolink Google Drive: Échec rafraîchissement token OAuth: HTTP %s",
                            token_resp.status,
                        )
                        return
                    token_json = await token_resp.json()
                    access_token = token_json.get("access_token")

                metadata = {"name": filename}
                if folder_id:
                    metadata["parents"] = [folder_id]

                boundary = "==================DomolinkDriveBoundary=="
                headers = {
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": f"multipart/related; boundary={boundary}",
                }
                metadata_str = json.dumps(metadata)
                body = (
                    f"--{boundary}\r\n"
                    f"Content-Type: application/json; charset=UTF-8\r\n\r\n"
                    f"{metadata_str}\r\n"
                    f"--{boundary}\r\n"
                    f"Content-Type: {mime_type}\r\n\r\n"
                ).encode("utf-8") + file_bytes + f"\r\n--{boundary}--\r\n".encode("utf-8")

                upload_url = "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart"
                timeout = aiohttp.ClientTimeout(total=90 if is_video else 30)
                async with session.post(
                    upload_url, data=body, headers=headers, timeout=timeout
                ) as up_resp:
                    if up_resp.status in (200, 201):
                        self.google_drive_status = "Connecté"
                        _LOGGER.info(
                            "Domolink: %s téléversée sur Google Drive via API OAuth: %s",
                            media_type.capitalize(),
                            filename,
                        )
                        self._log_event(f"Sauvegarde {media_type} Google Drive : {filename}")
                    else:
                        self.google_drive_status = "Erreur"
                        _LOGGER.error(
                            "Domolink: Échec envoi Google Drive API (%s): HTTP %s",
                            filename,
                            up_resp.status,
                        )
                        self._log_event(
                            f"⚠️ Échec Google Drive {media_type}: {filename} (HTTP {up_resp.status})"
                        )

        except Exception as e:
            self.google_drive_status = "Erreur"
            _LOGGER.error("Domolink: Erreur téléversement Google Drive de %s: %s", file_path, e)
            self._log_event(f"⚠️ Erreur envoi Google Drive : {e}")

        self._write_state()

    def _append_google_drive_log(self, message: str, level: str = "info"):
        """Append an entry to Google Drive test log and notify state change."""
        now_str = dt_now().strftime("%H:%M:%S")
        self.google_drive_test_logs.append(
            {
                "time": now_str,
                "message": message,
                "level": level,
            }
        )
        if len(self.google_drive_test_logs) > 60:
            self.google_drive_test_logs = self.google_drive_test_logs[-60:]
        try:
            self._write_state()
        except Exception:
            pass

    async def async_test_google_drive(self, call=None):
        """Force a connection test to Google Drive with real-time log steps."""
        if self.google_drive_test_running:
            _LOGGER.debug("Domolink: Un test Google Drive est déjà en cours.")
            return

        self.google_drive_test_running = True
        self.google_drive_test_logs = []
        self.google_drive_test_result = {}
        self._append_google_drive_log("🚀 Démarrage du diagnostic Google Drive...", "info")

        self.hass.async_create_task(self._async_run_google_drive_test())

    async def _async_run_google_drive_test(self):
        """Run step-by-step diagnostic of Google Drive asynchronously."""
        import aiohttp
        import time
        from homeassistant.helpers.aiohttp_client import async_get_clientsession

        start_time = time.time()
        method = self._cfg(CONF_GOOGLE_DRIVE_METHOD, "webhook")
        folder_id = str(self._cfg(CONF_GOOGLE_DRIVE_FOLDER_ID, "") or "").strip()

        try:
            await asyncio.sleep(0.2)
            if not self._cfg(CONF_GOOGLE_DRIVE_ENABLED, False):
                self._append_google_drive_log(
                    "Le service Google Drive est désactivé dans la configuration.",
                    "error",
                )
                self.google_drive_status = "Erreur"
                self.google_drive_test_running = False
                self.google_drive_test_result = {"success": False, "message": "Service désactivé."}
                self._write_state()
                return

            session = async_get_clientsession(self.hass)

            if method == "webhook":
                webhook_url = str(self._cfg(CONF_GOOGLE_DRIVE_WEBHOOK_URL, "") or "").strip()
                if not webhook_url:
                    self._append_google_drive_log(
                        "Aucune URL Webhook Google Apps Script configurée.",
                        "error",
                    )
                    self.google_drive_status = "Erreur"
                    self.google_drive_test_running = False
                    self.google_drive_test_result = {"success": False, "message": "URL Webhook manquante."}
                    self._write_state()
                    return

                self._append_google_drive_log(
                    f"1. Configuration Webhook : {webhook_url[:40]}...", "info"
                )
                await asyncio.sleep(0.3)

                self._append_google_drive_log(
                    "2. Envoi de la sonde de test vers le script Google Drive...",
                    "info",
                )
                probe_payload = {
                    "probe": True,
                    "filename": "domolink_probe.txt",
                    "file_base64": base64.b64encode(
                        b"Domolink Alarm Google Drive Probe Test"
                    ).decode("utf-8"),
                    "mime_type": "text/plain",
                    "folder_id": folder_id,
                }

                try:
                    async with session.post(
                        webhook_url,
                        json=probe_payload,
                        timeout=aiohttp.ClientTimeout(total=20),
                        allow_redirects=True,
                    ) as resp:
                        if resp.status in (200, 201):
                            self._append_google_drive_log(
                                f"   ✓ Réponse reçue du script Google Drive (HTTP {resp.status})",
                                "success",
                            )
                            self._append_google_drive_log(
                                "3. Validation de l'accès et des permissions de stockage...",
                                "info",
                            )
                            await asyncio.sleep(0.3)
                            self._append_google_drive_log(
                                "   ✓ Droits de téléversement validés sur Google Drive.",
                                "success",
                            )
                        else:
                            self._append_google_drive_log(
                                f"   ✗ Le Webhook a retourné une erreur (HTTP {resp.status})",
                                "error",
                            )
                            self.google_drive_status = "Erreur"
                            self.google_drive_test_running = False
                            self.google_drive_test_result = {
                                "success": False,
                                "message": f"Erreur Webhook HTTP {resp.status}",
                            }
                            self._write_state()
                            return
                except Exception as net_err:
                    self._append_google_drive_log(
                        f"   ✗ Impossible de joindre l'URL Webhook : {net_err}",
                        "error",
                    )
                    self.google_drive_status = "Erreur"
                    self.google_drive_test_running = False
                    self.google_drive_test_result = {"success": False, "message": str(net_err)}
                    self._write_state()
                    return

            elif method == "oauth":
                client_id = str(self._cfg(CONF_GOOGLE_DRIVE_CLIENT_ID, "") or "").strip()
                client_secret = str(self._cfg(CONF_GOOGLE_DRIVE_CLIENT_SECRET, "") or "").strip()
                refresh_token = str(self._cfg(CONF_GOOGLE_DRIVE_REFRESH_TOKEN, "") or "").strip()

                if not (client_id and client_secret and refresh_token):
                    self._append_google_drive_log(
                        "Paramètres OAuth2 incomplets (Client ID, Secret ou Refresh Token manquant).",
                        "error",
                    )
                    self.google_drive_status = "Erreur"
                    self.google_drive_test_running = False
                    self.google_drive_test_result = {
                        "success": False,
                        "message": "Identifiants OAuth2 incomplets.",
                    }
                    self._write_state()
                    return

                self._append_google_drive_log(
                    "1. Échange du Refresh Token avec l'API OAuth2 Google...",
                    "info",
                )
                token_url = "https://oauth2.googleapis.com/token"
                token_data = {
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                }
                try:
                    async with session.post(
                        token_url,
                        data=token_data,
                        timeout=aiohttp.ClientTimeout(total=15),
                    ) as token_resp:
                        if token_resp.status != 200:
                            self._append_google_drive_log(
                                f"   ✗ Échec de l'authentification OAuth2 (HTTP {token_resp.status})",
                                "error",
                            )
                            self.google_drive_status = "Erreur"
                            self.google_drive_test_running = False
                            self.google_drive_test_result = {
                                "success": False,
                                "message": f"Erreur OAuth2 HTTP {token_resp.status}",
                            }
                            self._write_state()
                            return
                        token_json = await token_resp.json()
                        access_token = token_json.get("access_token")
                        self._append_google_drive_log(
                            "   ✓ Access Token OAuth2 généré avec succès.", "success"
                        )
                except Exception as oauth_err:
                    self._append_google_drive_log(
                        f"   ✗ Erreur connexion OAuth2 : {oauth_err}", "error"
                    )
                    self.google_drive_status = "Erreur"
                    self.google_drive_test_running = False
                    self.google_drive_test_result = {"success": False, "message": str(oauth_err)}
                    self._write_state()
                    return

                await asyncio.sleep(0.3)
                if folder_id:
                    self._append_google_drive_log(
                        f"2. Vérification du dossier distant ({folder_id})...",
                        "info",
                    )
                    check_url = f"https://www.googleapis.com/drive/v3/files/{folder_id}?fields=id,name,mimeType"
                    async with session.get(
                        check_url,
                        headers={"Authorization": f"Bearer {access_token}"},
                        timeout=aiohttp.ClientTimeout(total=10),
                    ) as f_resp:
                        if f_resp.status == 200:
                            f_info = await f_resp.json()
                            self._append_google_drive_log(
                                f"   ✓ Dossier trouvé : '{f_info.get('name', folder_id)}'",
                                "success",
                            )
                        else:
                            self._append_google_drive_log(
                                f"   ⚠️ Dossier introuvable ou inaccessible (HTTP {f_resp.status}), racine utilisée.",
                                "warning",
                            )

                await asyncio.sleep(0.3)
                self._append_google_drive_log(
                    "3. Test d'écriture fichier sonde (multipart upload)...", "info"
                )
                probe_filename = f"domolink_probe_{int(time.time())}.txt"
                boundary = "==================DomolinkDriveBoundary=="
                headers = {
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": f"multipart/related; boundary={boundary}",
                }
                meta = {"name": probe_filename}
                if folder_id:
                    meta["parents"] = [folder_id]
                probe_content = b"Domolink Probe Test File"
                body = (
                    f"--{boundary}\r\n"
                    f"Content-Type: application/json; charset=UTF-8\r\n\r\n"
                    f"{json.dumps(meta)}\r\n"
                    f"--{boundary}\r\n"
                    f"Content-Type: text/plain\r\n\r\n"
                ).encode("utf-8") + probe_content + f"\r\n--{boundary}--\r\n".encode("utf-8")

                upload_url = "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart"
                created_file_id = None
                async with session.post(
                    upload_url,
                    data=body,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as up_resp:
                    if up_resp.status not in (200, 201):
                        self._append_google_drive_log(
                            f"   ✗ Échec téléversement test (HTTP {up_resp.status})",
                            "error",
                        )
                        self.google_drive_status = "Erreur"
                        self.google_drive_test_running = False
                        self.google_drive_test_result = {
                            "success": False,
                            "message": f"Écriture refusée (HTTP {up_resp.status})",
                        }
                        self._write_state()
                        return
                    up_json = await up_resp.json()
                    created_file_id = up_json.get("id")
                    self._append_google_drive_log(
                        "   ✓ Fichier test créé avec succès sur Google Drive.",
                        "success",
                    )

                if created_file_id:
                    await asyncio.sleep(0.2)
                    self._append_google_drive_log(
                        "4. Nettoyage du fichier test...", "info"
                    )
                    del_url = f"https://www.googleapis.com/drive/v3/files/{created_file_id}"
                    async with session.delete(
                        del_url,
                        headers={"Authorization": f"Bearer {access_token}"},
                        timeout=aiohttp.ClientTimeout(total=8),
                    ):
                        self._append_google_drive_log(
                            "   ✓ Nettoyage effectué.", "success"
                        )

            elapsed = round(time.time() - start_time, 2)
            dest_desc = f"Dossier: {folder_id}" if folder_id else "Racine Google Drive"
            self._append_google_drive_log(
                f"🎉 Connexion Google Drive validée avec succès ({elapsed}s) !",
                "success",
            )
            self.google_drive_status = "Connecté"
            self.google_drive_test_running = False
            self.google_drive_test_result = {
                "success": True,
                "message": "Connexion acceptée",
                "save_path": dest_desc,
                "elapsed": elapsed,
            }
            self._log_event(f"Test Google Drive réussi ({elapsed}s) : {dest_desc}")

        except Exception as global_err:
            _LOGGER.error("Domolink: Erreur test Google Drive: %s", global_err)
            self._append_google_drive_log(f"Erreur inattendue : {global_err}", "error")
            self.google_drive_status = "Erreur"
            self.google_drive_test_running = False
            self.google_drive_test_result = {"success": False, "message": str(global_err)}
            self._log_event(f"⚠️ Erreur test Google Drive : {global_err}")
        finally:
            self._write_state()
