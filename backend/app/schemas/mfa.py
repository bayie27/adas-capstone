"""Request and response contracts for the integrated MFA API."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.user import UserRead

ChallengePurpose = Literal[
    "login", "enroll", "recovery_verify", "recovery_enroll", "replace"
]


class ChallengeState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["mfa_required", "enrollment_required"]
    purpose: ChallengePurpose
    expires_at: datetime


class EnrollmentStartResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provisioning_uri: str = Field(repr=False)
    manual_key: str = Field(repr=False)
    issuer: Literal["ADAS"] = "ADAS"
    account_name: str
    expires_at: datetime


class CompletedLogin(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["authenticated"] = "authenticated"
    user: UserRead


class CompletedEnrollment(CompletedLogin):
    recovery_codes: list[str] = Field(repr=False)


class CompletedReplacement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["reauthentication_required"] = "reauthentication_required"
    recovery_codes: list[str] = Field(repr=False)


class EnrollmentStartRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EnrollmentConfirmRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=6, max_length=6, repr=False)

    @field_validator("code")
    @classmethod
    def six_ascii_digits(cls, value: str) -> str:
        if len(value) != 6 or any(char < "0" or char > "9" for char in value):
            raise ValueError("Enter a six-digit authenticator code.")
        return value


class VerifyChallengeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    method: Literal["totp", "recovery"]
    code: str = Field(min_length=1, max_length=64, repr=False)


class RecoveryCodeRotationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    password: str = Field(min_length=1, max_length=128, repr=False)
    code: str = Field(min_length=1, max_length=64, repr=False)


class ReplacementStartRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    password: str = Field(min_length=1, max_length=128, repr=False)
    code: str = Field(min_length=1, max_length=64, repr=False)


class EnrollmentFromSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    password: str = Field(min_length=1, max_length=128, repr=False)


class MfaStatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: Literal["unenrolled", "enrolled", "recovery_pending"]
    recovery_codes_remaining: int
    enrolled_at: datetime | None
    auth_method: Literal["totp", "demo_impersonation"]


class RecoveryCodesResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recovery_codes: list[str] = Field(repr=False)
