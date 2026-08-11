"""Request/response models for the dev-tools routes.

Request bodies use `extra="forbid"` (as DetectionLogCreateV2 does), so a
typo'd field is a 422 rather than a silently ignored one.
"""

from pydantic import BaseModel


class DevProfileInfo(BaseModel):
    name: str
    description: str


class DevStatusResponse(BaseModel):
    enabled: bool
    profiles: list[DevProfileInfo]
