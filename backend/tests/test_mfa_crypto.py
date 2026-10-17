"""P1 contract tests for MFA secrets, TOTP steps, and recovery proofs."""

from __future__ import annotations

import base64
import hashlib
import re
from datetime import UTC, datetime

import pytest
from app.core.mfa import (
    canonicalize_recovery_code,
    decrypt_totp_secret,
    encrypt_totp_secret,
    generate_recovery_codes,
    generate_totp_secret,
    hash_challenge_token,
    hash_recovery_code,
    matching_totp_step,
)
from cryptography.fernet import Fernet, InvalidToken

_RFC_SHA1_SECRET = base64.b32encode(b"12345678901234567890").decode("ascii").rstrip("=")


def test_rfc_6238_six_digit_vectors_include_leading_zeroes():
    assert (
        matching_totp_step(_RFC_SHA1_SECRET, "287082", datetime.fromtimestamp(59, UTC))
        == 1
    )
    assert (
        matching_totp_step(
            _RFC_SHA1_SECRET, "081804", datetime.fromtimestamp(1_111_111_109, UTC)
        )
        == 37_037_036
    )


def test_matching_totp_returns_the_accepted_adjacent_step():
    now = datetime.fromtimestamp(1_700_000_011, UTC)
    current_step = int(now.timestamp() // 30)
    totp = __import__("pyotp").TOTP(_RFC_SHA1_SECRET, digits=6)

    for candidate_step in (current_step - 1, current_step, current_step + 1):
        candidate_time = datetime.fromtimestamp(candidate_step * 30, UTC)
        code = totp.at(candidate_time)
        assert matching_totp_step(_RFC_SHA1_SECRET, code, now) == candidate_step

    too_old = totp.at(datetime.fromtimestamp((current_step - 2) * 30, UTC))
    too_new = totp.at(datetime.fromtimestamp((current_step + 2) * 30, UTC))
    assert matching_totp_step(_RFC_SHA1_SECRET, too_old, now) is None
    assert matching_totp_step(_RFC_SHA1_SECRET, too_new, now) is None


@pytest.mark.parametrize(
    "code", ["12345", "1234567", "１２３４５６", "12 3456", "abcdef"]
)
def test_matching_totp_rejects_malformed_ascii_input(code: str):
    assert (
        matching_totp_step(
            _RFC_SHA1_SECRET, code, datetime.fromtimestamp(1_700_000_011, UTC)
        )
        is None
    )


def test_matching_totp_requires_explicit_aware_time():
    with pytest.raises(ValueError, match="timezone-aware"):
        matching_totp_step(_RFC_SHA1_SECRET, "287082", datetime(2026, 1, 1))


def test_generated_totp_secret_is_valid_and_encrypts_without_plaintext():
    secret = generate_totp_secret()
    key = Fernet.generate_key().decode("ascii")

    ciphertext = encrypt_totp_secret(secret, key)

    assert re.fullmatch(r"[A-Z2-7]{32}", secret)
    assert secret not in ciphertext
    assert decrypt_totp_secret(ciphertext, key) == secret


def test_totp_decryption_fails_closed_for_wrong_key_and_corrupt_token():
    key = Fernet.generate_key().decode("ascii")
    other_key = Fernet.generate_key().decode("ascii")
    ciphertext = encrypt_totp_secret("JBSWY3DPEHPK3PXP", key)

    with pytest.raises(InvalidToken):
        decrypt_totp_secret(ciphertext, other_key)
    with pytest.raises(InvalidToken):
        decrypt_totp_secret(ciphertext[:-2] + "AA", key)


def test_totp_encryption_rejects_malformed_key_without_echoing_it():
    malformed_key = "this-is-not-a-fernet-key"
    with pytest.raises(ValueError) as exc_info:
        encrypt_totp_secret("JBSWY3DPEHPK3PXP", malformed_key)

    assert malformed_key not in str(exc_info.value)


def test_challenge_token_uses_stable_sha256_of_ascii_token():
    token = "disposable-challenge-token"
    digest = hash_challenge_token(token)

    assert digest == hashlib.sha256(token.encode("ascii")).hexdigest()
    assert len(digest) == 64


def test_recovery_codes_use_unique_grouped_128_bit_values():
    codes = generate_recovery_codes()

    assert len(codes) == 10
    assert len(set(codes)) == 10
    assert all(re.fullmatch(r"[0-9A-F]{8}(?:-[0-9A-F]{8}){3}", code) for code in codes)


def test_recovery_code_canonicalization_and_hash_separation():
    code = "01234567-89ABCDEF-01234567-89ABCDEF"
    canonical = "0123456789ABCDEF0123456789ABCDEF"

    assert canonicalize_recovery_code(f"  {code.lower()}  ") == canonical
    assert (
        hash_recovery_code(17, 3, code.lower())
        == hashlib.sha256(
            f"adas-mfa-recovery-v1:17:3:{canonical}".encode("ascii")
        ).hexdigest()
    )
    assert hash_recovery_code(17, 3, code) == hash_recovery_code(17, 3, canonical)
    assert hash_recovery_code(18, 3, code) != hash_recovery_code(17, 3, code)
    assert hash_recovery_code(17, 4, code) != hash_recovery_code(17, 3, code)


@pytest.mark.parametrize(
    "code",
    ["", "01234567-89ABCDEF-01234567-89ABCDEG", "0123456789ABCDEF", "x" * 40],
)
def test_recovery_code_canonicalization_rejects_invalid_values(code: str):
    with pytest.raises(ValueError):
        canonicalize_recovery_code(code)
