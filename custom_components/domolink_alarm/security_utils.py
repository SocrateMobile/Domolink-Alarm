"""Security and cryptography utilities for Domolink Alarm."""
from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets

SECRET_MASK = "••••••••"
PBKDF2_PREFIX = "pbkdf2:sha256:"
DEFAULT_ITERATIONS = 100_000


def hash_pin(pin: str, iterations: int = DEFAULT_ITERATIONS) -> str:
    """Hash a numeric or alphanumeric PIN using PBKDF2-HMAC-SHA256 with a random salt."""
    if not pin:
        return ""
    clean_pin = str(pin).strip()
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac(
        "sha256",
        clean_pin.encode("utf-8"),
        salt.encode("utf-8"),
        iterations,
    )
    return f"{PBKDF2_PREFIX}{iterations}${salt}${dk.hex()}"


def is_hashed(value: str) -> bool:
    """Check whether a stored value is already a PBKDF2 hash."""
    if not value or not isinstance(value, str):
        return False
    return value.startswith(PBKDF2_PREFIX) and "$" in value


def verify_pin(candidate_pin: str, stored_value: str) -> tuple[bool, bool]:
    """Verify candidate PIN against stored value.

    Returns:
        tuple[bool, bool]: (is_valid, needs_migration)
        needs_migration is True if candidate matched a legacy plain-text stored value.
    """
    if not candidate_pin or not stored_value:
        return False, False

    clean_candidate = str(candidate_pin).strip()
    clean_stored = str(stored_value).strip()

    if is_hashed(clean_stored):
        try:
            # Format: pbkdf2:sha256:iterations$salt$hash
            parts = clean_stored[len(PBKDF2_PREFIX):].split("$")
            if len(parts) != 3:
                return False, False
            iterations = int(parts[0])
            salt = parts[1]
            expected_hash = parts[2]

            candidate_dk = hashlib.pbkdf2_hmac(
                "sha256",
                clean_candidate.encode("utf-8"),
                salt.encode("utf-8"),
                iterations,
            )
            is_valid = hmac.compare_digest(candidate_dk.hex(), expected_hash)
            return is_valid, False
        except Exception:
            return False, False

    # Legacy plain-text verification (constant-time compare)
    matches = hmac.compare_digest(
        clean_candidate.encode("utf-8"),
        clean_stored.encode("utf-8"),
    )
    return matches, matches


def mask_secret(value: str | None, mask: str = SECRET_MASK) -> str:
    """Return a masked placeholder if the value is non-empty, otherwise empty string."""
    if not value:
        return ""
    clean = str(value).strip()
    if not clean:
        return ""
    return mask


def sanitize_log_payload(payload: str) -> str:
    """Sanitize sensitive keys in JSON payloads or strings before logging."""
    if not payload:
        return ""
    text = str(payload).strip()
    if text.startswith("{") and text.endswith("}"):
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                for k in list(data.keys()):
                    lower_k = k.lower()
                    if any(s in lower_k for s in ("code", "pin", "pass", "pwd", "token", "secret")):
                        if data[k]:
                            data[k] = SECRET_MASK
                return json.dumps(data, ensure_ascii=False)
        except Exception:
            pass

    # Regex sanitization for JSON-like fragments or raw patterns
    text = re.sub(
        r'(?i)("?(?:code|pin|password|pass|token|secret)"?\s*[:=]\s*)"([^"]+)"',
        rf'\1"{SECRET_MASK}"',
        text,
    )
    text = re.sub(
        r'(?i)("?(?:code|pin|password|pass|token|secret)"?\s*[:=]\s*)([0-9a-zA-Z_\-]+)',
        rf'\1{SECRET_MASK}',
        text,
    )
    return text
