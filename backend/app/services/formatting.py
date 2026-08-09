from app.models import User


def format_user_name(user: User | None) -> str | None:
    if not user:
        return None
    full_name = f"{user.first_name} {user.last_name}".strip()
    return full_name or user.username
