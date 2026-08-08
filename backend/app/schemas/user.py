from datetime import datetime

from pydantic import field_validator
from sqlmodel import Field, SQLModel

from app.models import UserBase, UserRole
from app.schemas.common import validate_password_strength


class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        return validate_password_strength(v)


class UserRead(UserBase):
    user_id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    password_changed_at: datetime | None = None
    last_login: datetime | None = None


class UserListResponse(SQLModel):
    total_filtered: int
    users: list[UserRead]


class UserOperatorUpdate(SQLModel):
    username: str | None = Field(default=None, min_length=3, max_length=20)
    first_name: str | None = Field(default=None, min_length=1, max_length=20)
    last_name: str | None = Field(default=None, min_length=1, max_length=20)

    @field_validator("username", "first_name", "last_name", mode="before")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        if v is not None and isinstance(v, str):
            return v.strip()
        return v


class UserAdminUpdate(UserOperatorUpdate):
    role: UserRole | None = None
    is_active: bool | None = None


class UserUpdatePassword(SQLModel):
    old_password: str = Field(min_length=8)
    new_password: str = Field(min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        return validate_password_strength(v)


class UserResetPassword(SQLModel):
    new_password: str = Field(min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        return validate_password_strength(v)
