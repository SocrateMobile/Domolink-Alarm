"""Unit tests for Domolink Alarm security hardening."""
import unittest
import json
import sys
import os

# Add custom_components to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "custom_components", "domolink_alarm")))

from security_utils import (
    hash_pin,
    verify_pin,
    is_hashed,
    mask_secret,
    sanitize_log_payload,
    SECRET_MASK,
)


class TestSecurityUtils(unittest.TestCase):
    """Test cryptographic functions and sanitization."""

    def test_hash_pin_format_and_salt(self):
        pin = "1234"
        h1 = hash_pin(pin)
        h2 = hash_pin(pin)

        self.assertTrue(is_hashed(h1))
        self.assertTrue(is_hashed(h2))
        self.assertTrue(h1.startswith("pbkdf2:sha256:100000$"))
        # Salts should be random and distinct
        self.assertNotEqual(h1, h2)

    def test_verify_pin_valid_and_invalid(self):
        pin = "4321"
        hashed = hash_pin(pin)

        # Valid match
        valid, needs_mig = verify_pin("4321", hashed)
        self.assertTrue(valid)
        self.assertFalse(needs_mig)

        # Invalid match
        invalid, _ = verify_pin("0000", hashed)
        self.assertFalse(invalid)

        # Empty / None
        self.assertFalse(verify_pin("", hashed)[0])
        self.assertFalse(verify_pin("4321", "")[0])
        self.assertFalse(verify_pin(None, hashed)[0])

    def test_verify_pin_legacy_migration(self):
        legacy_plain = "5678"

        # Correct legacy PIN
        valid, needs_mig = verify_pin("5678", legacy_plain)
        self.assertTrue(valid)
        self.assertTrue(needs_mig)  # Flagged for automatic migration

        # Wrong legacy PIN
        invalid, _ = verify_pin("1111", legacy_plain)
        self.assertFalse(invalid)

    def test_mask_secret(self):
        self.assertEqual(mask_secret("my_secret_token"), SECRET_MASK)
        self.assertEqual(mask_secret("password123"), SECRET_MASK)
        self.assertEqual(mask_secret(""), "")
        self.assertEqual(mask_secret(None), "")
        self.assertEqual(mask_secret("   "), "")

    def test_sanitize_log_payload_json(self):
        raw_json = json.dumps({"action": "DISARM", "code": "1234", "user": "Jean"})
        sanitized = sanitize_log_payload(raw_json)

        self.assertNotIn("1234", sanitized)
        self.assertIn(SECRET_MASK, sanitized)
        self.assertIn("Jean", sanitized)
        self.assertIn("DISARM", sanitized)

    def test_sanitize_log_payload_nested_passwords(self):
        raw = json.dumps({"ftp_user": "admin", "ftp_pass": "super_secret_nas_password"})
        sanitized = sanitize_log_payload(raw)

        self.assertNotIn("super_secret_nas_password", sanitized)
        self.assertIn(SECRET_MASK, sanitized)
        self.assertIn("admin", sanitized)

    def test_sanitize_log_payload_raw_string(self):
        raw_str = "Received command code: 9876 for panel"
        sanitized = sanitize_log_payload(raw_str)

        self.assertNotIn("9876", sanitized)
        self.assertIn(SECRET_MASK, sanitized)


class TestValidationAndAutoMigration(unittest.TestCase):
    """Simulate validation logic as executed inside Alarm entity."""

    def setUp(self):
        # Initial state with legacy plain-text codes
        self.users = {
            "Jean": "1234",
            "Marie": hash_pin("5678"),  # Already hashed
        }
        self.duress_code = "9999"  # Legacy plain
        self.user_profiles = [
            {"id": "prof1", "name": "Invité", "pin": "0000", "enabled": True}
        ]

    def validate_code(self, code):
        """Simulate _validate_code logic."""
        if not code:
            return None

        # Duress
        if self.duress_code:
            valid_d, mig_d = verify_pin(code, self.duress_code)
            if valid_d:
                if mig_d:
                    self.duress_code = hash_pin(code)
                return "DURESS"

        # Users
        for uname, stored in list(self.users.items()):
            valid_u, mig_u = verify_pin(code, stored)
            if valid_u:
                if mig_u:
                    self.users[uname] = hash_pin(code)
                return uname

        # Profiles
        for p in self.user_profiles:
            valid_p, mig_p = verify_pin(code, p.get("pin"))
            if valid_p:
                if mig_p:
                    p["pin"] = hash_pin(code)
                return p.get("name")

        return None

    def test_successful_validation_and_auto_migration_for_users(self):
        # 1. Jean logs in with legacy PIN "1234"
        self.assertFalse(is_hashed(self.users["Jean"]))
        res = self.validate_code("1234")
        self.assertEqual(res, "Jean")
        # Jean's PIN must now be automatically migrated to PBKDF2
        self.assertTrue(is_hashed(self.users["Jean"]))

        # 2. Jean logs in again with "1234" -> Still works from hashed state
        res2 = self.validate_code("1234")
        self.assertEqual(res2, "Jean")

        # 3. Marie logs in with "5678" -> Works directly
        res_m = self.validate_code("5678")
        self.assertEqual(res_m, "Marie")

        # 4. Wrong code
        self.assertIsNone(self.validate_code("9991"))

    def test_duress_code_migration(self):
        self.assertFalse(is_hashed(self.duress_code))
        res = self.validate_code("9999")
        self.assertEqual(res, "DURESS")
        self.assertTrue(is_hashed(self.duress_code))

        # Subsequent verification works
        res2 = self.validate_code("9999")
        self.assertEqual(res2, "DURESS")

    def test_user_profiles_migration(self):
        self.assertFalse(is_hashed(self.user_profiles[0]["pin"]))
        res = self.validate_code("0000")
        self.assertEqual(res, "Invité")
        self.assertTrue(is_hashed(self.user_profiles[0]["pin"]))


if __name__ == "__main__":
    unittest.main()
