from datetime import UTC, datetime
from typing import TYPE_CHECKING

from pydantic import field_validator
from sqlalchemy import Column, DateTime
from sqlmodel import Field, Relationship, SQLModel

from app.models.enums import UserRole

if TYPE_CHECKING:
    from app.models.detection import DetectionLog


class UserBase(SQLModel):
    username: str = Field(unique=True, index=True, min_length=3, max_length=20)
    first_name: str = Field(min_length=1, max_length=20)
    last_name: str = Field(min_length=1, max_length=20)
    role: UserRole

    @field_validator("username", "first_name", "last_name", mode="before")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip()
        return v


class User(UserBase, table=True):
    user_id: int | None = Field(default=None, primary_key=True)
    password_hash: str
    is_active: bool = Field(default=True)

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(
        default=None,
        sa_column=Column(
            DateTime(timezone=True),
            default=lambda: datetime.now(UTC),
            onupdate=lambda: datetime.now(UTC),
            nullable=False,
        ),
    )
    password_changed_at: datetime | None = Field(default=None)
    last_login: datetime | None = Field(default=None)

    # Relationships
    verified_detections: list["DetectionLog"] = Relationship(
        back_populates="verified_by",
        sa_relationship_kwargs={"foreign_keys": "DetectionLog.verified_by_id"},
    )
    closed_detections: list["DetectionLog"] = Relationship(
        back_populates="closed_by",
        sa_relationship_kwargs={"foreign_keys": "DetectionLog.closed_by_id"},
    )
