from sqlmodel import SQLModel

from app.schemas.user import UserRead


class LoginResponse(SQLModel):
    user: UserRead
