"""Tests for Settings-level validators in app.core.config (A2 F2)."""

import pytest
from app.api.routes.internal import _build_rtsp_url
from app.core.config import Settings
from cryptography.fernet import Fernet
from pydantic import ValidationError


def _build_settings(**overrides) -> Settings:
    return Settings(
        _env_file=None,
        SECRET_KEY="test-secret-key-not-for-production-use",
        INTERNAL_API_KEY="test-internal-api-key-not-for-production",
        DEFAULT_ADMIN_PASSWORD="test-admin-password-123",
        **overrides,
    )


class TestRtspUrlTemplateValidation:
    def test_unknown_placeholder_raises_at_construction(self):
        """F2 — a typo'd placeholder must fail at boot, not on the first
        heartbeat in production."""
        with pytest.raises(ValidationError) as exc_info:
            _build_settings(RTSP_URL_TEMPLATE="rtsp://localhost:8554/{channelid}")

        message = str(exc_info.value)
        assert "channelid" in message

    def test_unbalanced_brace_raises(self):
        with pytest.raises(ValidationError):
            _build_settings(RTSP_URL_TEMPLATE="rtsp://localhost:8554/{channel_id")

    def test_default_template_constructs_fine(self):
        s = _build_settings()
        assert s.RTSP_URL_TEMPLATE == "rtsp://localhost:8554/channel{channel_id}"

    def test_realistic_dss_template_constructs_fine(self):
        s = _build_settings(
            RTSP_URL_TEMPLATE=(
                "rtsp://{dss_username}:{dss_password}@{dss_ip}:{dss_port}"
                "/channel{channel_id}"
            )
        )
        assert "{dss_username}" in s.RTSP_URL_TEMPLATE

    def test_build_rtsp_url_still_produces_expected_url(self, monkeypatch):
        from app.core.config import settings as app_settings

        monkeypatch.setattr(
            app_settings,
            "RTSP_URL_TEMPLATE",
            "rtsp://localhost:8554/channel{channel_id}",
        )
        assert _build_rtsp_url(3) == "rtsp://localhost:8554/channel3"


class TestMfaEncryptionKeyConfiguration:
    def test_missing_key_remains_valid_before_cutover(self):
        settings = _build_settings()
        assert settings.MFA_ENCRYPTION_KEY is None

    def test_well_formed_fernet_key_is_stored_as_secret(self):
        key = Fernet.generate_key().decode("ascii")
        settings = _build_settings(MFA_ENCRYPTION_KEY=key)

        assert settings.MFA_ENCRYPTION_KEY.get_secret_value() == key
        assert key not in repr(settings)

    @pytest.mark.parametrize("key", ["bad-key-material", "not-a-base64-key", "☃"])
    def test_malformed_key_is_rejected_without_echoing_the_value(self, key: str):
        with pytest.raises(ValidationError) as exc_info:
            _build_settings(MFA_ENCRYPTION_KEY=key)

        assert key not in str(exc_info.value)
