"""Unit tests for Domolink Alarm modular architecture and managers."""
import unittest
import asyncio
import os
import sys
import tempfile
import shutil
import time
from unittest.mock import MagicMock, AsyncMock, patch

# Mock Home Assistant before importing custom components
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "tests")))
import ha_mock
ha_mock.setup_ha_mock()

# Add root directory to path for package imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from homeassistant.core import State
from homeassistant.exceptions import HomeAssistantError
from homeassistant.const import (
    STATE_ALARM_DISARMED,
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_ARMING,
    STATE_ALARM_PENDING,
    STATE_ALARM_TRIGGERED,
)
from custom_components.domolink_alarm.cloud_uploader import CloudUploader
from custom_components.domolink_alarm.media_manager import MediaManager
from custom_components.domolink_alarm.notification_manager import NotificationManager
from custom_components.domolink_alarm.presence_simulation import PresenceSimulator
from custom_components.domolink_alarm.geofencing import GeofenceManager
from custom_components.domolink_alarm.alarm_control_panel import DomolinkAlarm
from custom_components.domolink_alarm.const import (
    CONF_ENTRY_DELAY,
    CONF_EXIT_DELAY,
    CONF_SIREN_DURATION,
    CONF_OPENING_SENSORS,
    CONF_MOTION_SENSORS,
    CONF_SIRENS,
    CONF_LIGHTS,
    CONF_CAMERAS,
    CONF_NF_A2P_MODE,
    CONF_NF_A2P_WINDOW,
    CONF_PRESENCE_SIMULATION_ENTITIES,
    CONF_GEOFENCE_AUTO_ARM,
    CONF_PERSONS,
    CONF_MEDIA_PATH,
    CONF_MEDIA_RETENTION_DAYS,
    CONF_MEDIA_MAX_SIZE_MB,
)


class DummyEvent:
    def __init__(self, data):
        self.data = data


class TestMediaManager(unittest.TestCase):
    """Test MediaManager functionality and path traversal protection."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.hass = ha_mock.sys.modules["homeassistant.core"].HomeAssistant()
        self.hass.config.path = lambda p: self.test_dir
        self.config = {
            CONF_CAMERAS: ["camera.front_door"],
            CONF_MEDIA_PATH: "domolink_media",
            CONF_MEDIA_RETENTION_DAYS: 7,
            CONF_MEDIA_MAX_SIZE_MB: 10,
        }
        self.media_manager = MediaManager(
            hass=self.hass,
            get_config_cb=lambda k, d=None: self.config.get(k, d),
            log_event_cb=MagicMock(),
            write_state_cb=MagicMock(),
            cloud_uploader=MagicMock(),
            send_notification_cb=AsyncMock(),
        )

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_directory_creation(self):
        """Test media directory is initialized."""
        self.assertTrue(os.path.exists(self.test_dir))

    def test_path_traversal_prevention_on_media_action(self):
        """Ensure media_action prevents path traversal attacks."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            # Attempt to delete file outside media dir
            secret_file = os.path.join(tempfile.gettempdir(), "sensitive.txt")
            with open(secret_file, "w") as f:
                f.write("confidential")

            # Try deleting ../sensitive.txt -> Should be blocked with HomeAssistantError
            with self.assertRaises(HomeAssistantError):
                loop.run_until_complete(
                    self.media_manager.async_media_action(
                        DummyEvent({"action": "delete", "filename": "../sensitive.txt"})
                    )
                )
            # File should not be deleted
            self.assertTrue(os.path.exists(secret_file))
            os.remove(secret_file)
        finally:
            loop.close()

    def test_fifo_quota_purge(self):
        """Test FIFO retention purges older files when quota exceeded."""
        # Create 3 dummy video files (4MB each = 12MB total, quota is 10MB)
        f1 = os.path.join(self.test_dir, "video_1.mp4")
        f2 = os.path.join(self.test_dir, "video_2.mp4")
        f3 = os.path.join(self.test_dir, "video_3.mp4")

        with open(f1, "wb") as f:
            f.write(b"0" * (4 * 1024 * 1024))  # 4 MB
        with open(f2, "wb") as f:
            f.write(b"0" * (4 * 1024 * 1024))  # 4 MB
        with open(f3, "wb") as f:
            f.write(b"0" * (4 * 1024 * 1024))  # 4 MB

        # Set distinct timestamps within retention window (7 days)
        now = time.time()
        os.utime(f1, (now - 3600, now - 3600))  # 1 hour ago (oldest)
        os.utime(f2, (now - 1800, now - 1800))  # 30 mins ago
        os.utime(f3, (now - 100, now - 100))    # 100 secs ago (newest)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            res = loop.run_until_complete(self.media_manager.async_clean_media())
            # Oldest file f1 must be purged to fit under 10 MB
            self.assertFalse(os.path.exists(f1))
            self.assertTrue(os.path.exists(f3))
            self.assertGreaterEqual(res.get("deleted", 0), 1)
        finally:
            loop.close()


class TestCloudUploader(unittest.TestCase):
    """Test CloudUploader isolation and diagnostic helpers."""

    def setUp(self):
        self.hass = ha_mock.sys.modules["homeassistant.core"].HomeAssistant()
        self.config = {
            "ftp_enabled": True,
            "ftp_host": "192.168.1.50",
            "ftp_user": "nas_user",
            "ftp_pass": "super_secret_ftp_password",
        }
        self.uploader = CloudUploader(
            hass=self.hass,
            get_config_cb=lambda k, d=None: self.config.get(k, d),
            log_event_cb=MagicMock(),
            write_state_cb=MagicMock(),
        )

    def test_cloud_uploader_init(self):
        self.assertIsNotNone(self.uploader)
        self.assertEqual(self.uploader._get_config("ftp_host"), "192.168.1.50")


class TestNotificationManager(unittest.TestCase):
    """Test NotificationManager dispatching and failover structures."""

    def setUp(self):
        self.hass = ha_mock.sys.modules["homeassistant.core"].HomeAssistant()
        self.config = {
            "notify_services": ["notify.mobile_app_iphone"],
            "free_mobile_user": "",
            CONF_SIRENS: ["switch.siren_indoor"],
            CONF_LIGHTS: ["light.living_room"],
        }
        self.notif_mgr = NotificationManager(
            hass=self.hass,
            get_config_cb=lambda k, d=None: self.config.get(k, d),
            log_event_cb=MagicMock(),
            write_state_cb=MagicMock(),
            turn_on_siren_cb=AsyncMock(),
        )

    def test_dispatch_notification(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            self.hass.services.async_call = AsyncMock()
            loop.run_until_complete(
                self.notif_mgr.async_send_notification(
                    message="Intrusion détectée !",
                    is_alert=True,
                )
            )
            # Should have attempted calling notification service
            self.assertTrue(self.hass.services.async_call.called)
        finally:
            loop.close()


class TestPresenceSimulation(unittest.TestCase):
    """Test presence simulator lifecycle and jitter calculation."""

    def setUp(self):
        self.hass = ha_mock.sys.modules["homeassistant.core"].HomeAssistant()
        self.config = {
            CONF_PRESENCE_SIMULATION_ENTITIES: ["light.living_room", "light.kitchen"],
        }
        self.sim = PresenceSimulator(
            hass=self.hass,
            get_config_cb=lambda k, d=None: self.config.get(k, d),
            log_event_cb=MagicMock(),
            write_state_cb=MagicMock(),
            get_alarm_state_cb=lambda: STATE_ALARM_ARMED_AWAY,
        )

    def test_start_stop_simulation(self):
        self.assertFalse(self.sim.is_running)
        self.sim.start()
        self.assertTrue(self.sim.is_running)
        self.sim.stop()
        self.assertFalse(self.sim.is_running)


class TestGeofencing(unittest.TestCase):
    """Test GeofenceManager zone and departure tracking."""

    def setUp(self):
        self.hass = ha_mock.sys.modules["homeassistant.core"].HomeAssistant()
        self.alarm_mock = MagicMock()
        self.alarm_mock.alarm_state = STATE_ALARM_DISARMED
        self.config = {
            CONF_GEOFENCE_AUTO_ARM: True,
            CONF_PERSONS: ["person.jean", "person.marie"],
        }
        self.geofence = GeofenceManager(
            hass=self.hass,
            alarm_entity=self.alarm_mock,
            get_config_cb=lambda k, d=None: self.config.get(k, d),
            log_event_cb=MagicMock(),
            write_state_cb=MagicMock(),
        )

    def test_snooze_reminder(self):
        self.assertEqual(self.geofence.snooze_until, 0.0)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self.geofence.async_snooze_reminder(duration_minutes=15))
            self.assertGreater(self.geofence.snooze_until, 0.0)
        finally:
            loop.close()


class TestDomolinkAlarmCore(unittest.TestCase):
    """Test DomolinkAlarm state machine, NF A2P double detection, and delegation."""

    def setUp(self):
        self.hass = ha_mock.sys.modules["homeassistant.core"].HomeAssistant()
        self.config_entry = ha_mock.sys.modules["homeassistant.config_entries"].ConfigEntry(
            entry_id="test_domolink_entry",
            data={
                "users_codes": {"Jean": "1234"},
                CONF_ENTRY_DELAY: 0,
                CONF_EXIT_DELAY: 0,
                CONF_SIREN_DURATION: 10,
                CONF_OPENING_SENSORS: ["binary_sensor.front_door"],
                CONF_MOTION_SENSORS: ["binary_sensor.living_room_motion"],
                CONF_NF_A2P_MODE: True,
                CONF_NF_A2P_WINDOW: 30,
            },
            options={},
        )
        self.alarm = DomolinkAlarm(self.hass, self.config_entry)
        self.alarm.hass = self.hass

    def test_initial_state_and_managers(self):
        """Verify alarm starts disarmed and has all 5 managers instantiated."""
        self.assertEqual(self.alarm.state, STATE_ALARM_DISARMED)
        self.assertIsNotNone(self.alarm.cloud_uploader)
        self.assertIsNotNone(self.alarm.media_manager)
        self.assertIsNotNone(self.alarm.notification_manager)
        self.assertIsNotNone(self.alarm.presence_simulator)
        self.assertIsNotNone(self.alarm.geofence_manager)

    def test_arming_and_disarming_cycle(self):
        """Test disarmed -> armed_away -> disarmed with valid code."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            # Arm Away
            loop.run_until_complete(self.alarm.async_alarm_arm_away())
            self.assertEqual(self.alarm.state, STATE_ALARM_ARMED_AWAY)

            # Disarm with correct code
            loop.run_until_complete(self.alarm.async_alarm_disarm(code="1234"))
            self.assertEqual(self.alarm.state, STATE_ALARM_DISARMED)
        finally:
            loop.close()

    def test_nf_a2p_double_detection_logic(self):
        """
        Under NF A2P mode:
        1. First sensor trigger -> Pending confirmation (alarm not triggered immediately)
        2. Second distinct sensor trigger -> Confirmed intrusion -> Alarm Triggered!
        """
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            # Arm away
            loop.run_until_complete(self.alarm.async_alarm_arm_away())
            self.assertEqual(self.alarm.state, STATE_ALARM_ARMED_AWAY)

            # First sensor tripped
            ev1 = DummyEvent({
                "entity_id": "binary_sensor.front_door",
                "new_state": State("binary_sensor.front_door", "on"),
                "old_state": State("binary_sensor.front_door", "off"),
            })
            loop.run_until_complete(self.alarm._async_sensor_changed(ev1))

            # Under NF A2P with 2 sensors configured, single sensor waits for 2nd confirmation
            self.assertIn(self.alarm.state, [STATE_ALARM_ARMED_AWAY, STATE_ALARM_PENDING])

            # Second sensor tripped within window
            ev2 = DummyEvent({
                "entity_id": "binary_sensor.living_room_motion",
                "new_state": State("binary_sensor.living_room_motion", "on"),
                "old_state": State("binary_sensor.living_room_motion", "off"),
            })
            loop.run_until_complete(self.alarm._async_sensor_changed(ev2))

            # Confirmed -> Alarm triggered
            self.assertEqual(self.alarm.state, STATE_ALARM_TRIGGERED)

            # Disarm
            loop.run_until_complete(self.alarm.async_alarm_disarm(code="1234"))
            self.assertEqual(self.alarm.state, STATE_ALARM_DISARMED)
        finally:
            loop.close()

    def test_attributes_export(self):
        """Test extra_state_attributes contains all keys expected by domolink-panel.js."""
        attrs = self.alarm.extra_state_attributes
        self.assertIn("user_profiles", attrs)
        self.assertIn("system_events", attrs)
        self.assertIn("media_storage_mb", attrs)
        self.assertIn("nf_a2p_mode", attrs)
        self.assertIn("bypassed_sensors", attrs)
        self.assertIn("presence_simulation_active", attrs)
        self.assertIn("installed_config", attrs)


if __name__ == "__main__":
    unittest.main()
