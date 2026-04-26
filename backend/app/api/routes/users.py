from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, func, select

from app.api.dependencies import get_current_admin, get_current_user
from app.core.db import get_session
from app.core.security import get_password_hash, verify_password
from app.models import (
    User,
    UserAdminUpdate,
    UserCreate,
    UserListResponse,
    UserOperatorUpdate,
    UserRead,
    UserResetPassword,
    UserRole,
    UserUpdatePassword,
)

router = APIRouter(
    prefix="/api/users",
    tags=["User Management"],
)


def _get_active_admin_count(session: Session) -> int:
    return session.exec(
        select(func.count())
        .select_from(User)
        .where(
            col(User.is_active).is_(True),
            col(User.role) == UserRole.ADMIN.value,
        )
    ).one()


def _get_active_user_or_404(user_id: int, session: Session) -> User:
    user = session.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=404, detail="User not found.")
    return user


# ---------------------------------------------------------
# SELF-SERVICE (Operator & Admin)
# ---------------------------------------------------------

@router.get("/me", response_model=UserRead, tags=["Profile"])
def get_my_profile(
    current_user: User = Depends(get_current_user),
) -> UserRead:
    """Returns the currently authenticated user's own profile."""
    return UserRead.model_validate(current_user)


@router.patch("/me", response_model=UserRead, tags=["Profile"])
def update_my_profile(
    update_in: UserOperatorUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> UserRead:
    """Operator self-service: update own username, first name, or last name."""
    update_data = update_in.model_dump(exclude_unset=True)

    for key, value in update_data.items():
        setattr(current_user, key, value)

    try:
        session.add(current_user)
        session.commit()
        session.refresh(current_user)
        return UserRead.model_validate(current_user)
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken.",
        )


@router.patch("/me/password", status_code=status.HTTP_204_NO_CONTENT, tags=["Profile"])
def change_my_password(
    passwords_in: UserUpdatePassword,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> None:
    """Operator self-service: change own password after verifying current one."""
    if not verify_password(passwords_in.old_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect.",
        )

    current_user.password_hash = get_password_hash(passwords_in.new_password)
    current_user.password_changed_at = datetime.now(timezone.utc)
    session.add(current_user)
    session.commit()


# ---------------------------------------------------------
# ADMIN-ONLY
# ---------------------------------------------------------

@router.get("/", response_model=UserListResponse, dependencies=[Depends(get_current_admin)])
def get_all_users(
    search: Optional[str] = Query(default=None, min_length=1, max_length=100),
    limit: int = Query(default=10, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
) -> UserListResponse:
    """Admin: paginated, searchable user directory."""
    query = select(User).where(col(User.is_active).is_(True))

    if search:
        query = query.where(
            col(User.username).icontains(search)
            | col(User.first_name).icontains(search)
            | col(User.last_name).icontains(search)
        )

    query = query.order_by(col(User.created_at).desc())

    total_filtered = session.exec(
        select(func.count()).select_from(query.subquery())
    ).one()

    users = session.exec(query.offset(offset).limit(limit)).all()

    return UserListResponse(
        total_filtered=total_filtered,
        users=[UserRead.model_validate(u) for u in users],
    )


@router.post(
    "/",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(get_current_admin)],
)
def create_user(
    user_in: UserCreate,
    session: Session = Depends(get_session),
) -> UserRead:
    """Admin: create a new user account."""
    new_user = User(
        username=user_in.username,
        first_name=user_in.first_name,
        last_name=user_in.last_name,
        role=user_in.role,
        password_hash=get_password_hash(user_in.password),
        password_changed_at=datetime.now(timezone.utc),
    )

    try:
        session.add(new_user)
        session.commit()
        session.refresh(new_user)
        return UserRead.model_validate(new_user)
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken.",
        )


@router.patch(
    "/{user_id}",
    response_model=UserRead,
    dependencies=[Depends(get_current_admin)],
)
def update_user(
    user_id: int,
    update_in: UserAdminUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> UserRead:
    """Admin: edit a user's profile, role, or active status.
    Guards against demoting or deactivating the last active admin."""
    target = _get_active_user_or_404(user_id, session)
    update_data = update_in.model_dump(exclude_unset=True)

    # Guard: cannot demote or deactivate the last active admin
    is_last_admin = (
        target.role == UserRole.ADMIN
        and _get_active_admin_count(session) <= 1
    )

    if is_last_admin:
        if update_data.get("role") == UserRole.OPERATOR:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot demote the last active Administrator.",
            )
        if update_data.get("is_active") is False:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot deactivate the last active Administrator.",
            )

    for key, value in update_data.items():
        setattr(target, key, value)

    try:
        session.add(target)
        session.commit()
        session.refresh(target)
        return UserRead.model_validate(target)
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken.",
        )


@router.post(
    "/{user_id}/reset-password",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(get_current_admin)],
)
def reset_user_password(
    user_id: int,
    passwords_in: UserResetPassword,
    session: Session = Depends(get_session),
) -> None:
    """Admin: force-reset any user's password."""
    target = _get_active_user_or_404(user_id, session)

    target.password_hash = get_password_hash(passwords_in.new_password)
    target.password_changed_at = datetime.now(timezone.utc)
    session.add(target)
    session.commit()


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(get_current_admin)],
)
def delete_user(
    user_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> None:
    """Admin: soft-delete a user. Guards against deleting the last active admin
    and against self-deletion."""
    target = _get_active_user_or_404(user_id, session)

    # Guard: cannot delete yourself
    if target.user_id == current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot delete your own account.",
        )

    # Guard: cannot delete the last active admin
    if target.role == UserRole.ADMIN and _get_active_admin_count(session) <= 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete the last active Administrator.",
        )

    target.is_active = False
    session.add(target)
    session.commit()
