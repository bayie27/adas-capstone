"""Environment-independent cryptographic primitives for MFA.

These helpers are deliberately stateless: callers supply keys and timestamps,
and no helper reads Settings, persists data, or logs authentication material.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import re
import secrets
from datetime import UTC, datetime

import pyotp
from cryptography.fernet import Fernet

_FERNET_KEY_BYTES = 32
_RECOVERY_CODE_BYTES = 16
_RECOVERY_CODE_DOMAIN = "adas-mfa-recovery-v1"
_SIX_ASCII_DIGITS = re.compile(r"[0-9]{6}\Z")
_RECOVERY_HEX = re.compile(r"[0-9A-F]{32}\Z")


def validate_encryption_key(key: str) -> str:
    """Return a structurally valid canonical Fernet key or a safe error."""
    try:
        encoded = key.encode("ascii")
        decoded = base64.urlsafe_b64decode(encoded)
    except (AttributeError, UnicodeEncodeError, binascii.Error, ValueError):
        raise ValueError("MFA_ENCRYPTION_KEY must be a valid Fernet key.") from None

    if (
        len(decoded) != _FERNET_KEY_BYTES
        or base64.urlsafe_b64encode(decoded) != encoded
    ):
        raise ValueError("MFA_ENCRYPTION_KEY must be a valid Fernet key.")
    return key


def _fernet(key: str) -> Fernet:
    return Fernet(validate_encryption_key(key).encode("ascii"))


def generate_totp_secret() -> str:
    """Generate a 160-bit Base32 secret suitable for authenticator apps."""
    return pyotp.random_base32(length=32)


def encrypt_totp_secret(secret: str, key: str) -> str:
    """Encrypt a TOTP seed with the caller-supplied stable Fernet key."""
    return _fernet(key).encrypt(secret.encode("ascii")).decode("ascii")


def decrypt_totp_secret(ciphertext: str, key: str) -> str:
    """Decrypt a stored seed; Fernet's InvalidToken fails closed for bad data."""
    try:
        token = ciphertext.encode("ascii")
    except (AttributeError, UnicodeEncodeError):
        raise ValueError("MFA ciphertext must be valid ASCII.") from None
    return _fernet(key).decrypt(token).decode("ascii")


def matching_totp_step(secret: str, code: str, now: datetime) -> int | None:
    """Return the exact matching 30-second SHA-1 TOTP step within ±1 step."""
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware.")
    if not isinstance(code, str) or _SIX_ASCII_DIGITS.fullmatch(code) is None:
        return None

    current_step = int(now.astimezone(UTC).timestamp() // 30)
    totp = pyotp.TOTP(secret, digits=6, interval=30, digest=hashlib.sha1)
    matching_steps = [
        step
        for step in range(current_step - 1, current_step + 2)
        if totp.at(datetime.fromtimestamp(step * 30, UTC)) == code
    ]
    return max(matching_steps, default=None)


def generate_recovery_codes(count: int = 10) -> list[str]:
    """Generate unique 128-bit recovery codes in the contract's display form."""
    if not isinstance(count, int) or isinstance(count, bool) or count < 1:
        raise ValueError("count must be a positive integer.")

    codes: set[str] = set()
    while len(codes) < count:
        hexadecimal = secrets.token_bytes(_RECOVERY_CODE_BYTES).hex().upper()
        codes.add(
            "-".join(hexadecimal[offset : offset + 8] for offset in range(0, 32, 8))
        )
    return list(codes)


def canonicalize_recovery_code(code: str) -> str:
    """Normalize display separators/case and require one 128-bit hex value."""
    if not isinstance(code, str):
        raise ValueError("Recovery code must contain 32 hexadecimal characters.")
    canonical = code.strip().replace("-", "").upper()
    if _RECOVERY_HEX.fullmatch(canonical) is None:
        raise ValueError("Recovery code must contain 32 hexadecimal characters.")
    return canonical


def hash_recovery_code(user_id: int, generation: int, code: str) -> str:
    """Return a domain-separated digest bound to one user and code batch."""
    if user_id < 1 or generation < 1:
        raise ValueError("user_id and generation must be positive integers.")
    canonical = canonicalize_recovery_code(code)
    value = f"{_RECOVERY_CODE_DOMAIN}:{user_id}:{generation}:{canonical}"
    return hashlib.sha256(value.encode("ascii")).hexdigest()


def hash_challenge_token(token: str) -> str:
    """Return SHA-256 of the opaque challenge token's ASCII bytes."""
    return hashlib.sha256(token.encode("ascii")).hexdigest()
