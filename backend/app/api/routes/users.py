from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, func, select

from app.api.dependencies import get_current_admin, get_current_user, require_admin
from app.core.db import get_session
from app.core.security import get_password_hash, verify_password
from app.models import AuditResult, User, UserRole
from app.schemas import (
    UserAdminUpdate,
    UserCreate,
    UserListResponse,
    UserOperatorUpdate,
    UserRead,
    UserResetPassword,
    UserUpdatePassword,
)
from app.services import audit
from app.services.sessions import revoke_all_for_user

router = APIRouter(
    prefix="/api/users",
    tags=["User Management"],
)

# Module-level singletons (ruff B008 — a Depends() default must not call a
# function inline) so a 403 from each admin-only route audits the specific
# catalog action that was being attempted.
_require_admin_for_create = require_admin("USER_CREATE")
_require_admin_for_update = require_admin("USER_UPDATE")
_require_admin_for_password_reset = require_admin("USER_PASSWORD_RESET")
_require_admin_for_disable = require_admin("USER_DISABLE")


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


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
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> UserRead:
    """Operator self-service: update own username, first name, or last name.
    Never revokes sessions — identity is user_id, not username (D-006)."""
    update_data = update_in.model_dump(exclude_unset=True)

    # Snapshot the actor *before* mutating — a self-rename must not audit
    # under the new username, since the actor performing the action was
    # still identified by the old one (D-007 actor-snapshot intent).
    if update_data:
        audit.record(
            session,
            action="USER_PROFILE_UPDATE",
            result=AuditResult.SUCCESS,
            actor=current_user,
            target_type="user",
            target_ref=str(current_user.user_id),
            detail={"changed_fields": sorted(update_data.keys())},
            source_ip=_client_ip(request),
        )

    for key, value in update_data.items():
        setattr(current_user, key, value)

    try:
        session.add(current_user)
        session.commit()
        session.refresh(current_user)
        return UserRead.model_validate(current_user)
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken.",
        ) from exc


@router.patch("/me/password", status_code=status.HTTP_204_NO_CONTENT, tags=["Profile"])
def change_my_password(
    passwords_in: UserUpdatePassword,
    request: Request,
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
    current_user.password_changed_at = datetime.now(UTC)
    session.add(current_user)
    # D-006 — a self password change revokes every session for this user,
    # including the one making this request. The user must log in again.
    revoke_all_for_user(session, current_user.user_id, "password_change")
    audit.record(
        session,
        action="USER_PASSWORD_CHANGE",
        result=AuditResult.SUCCESS,
        actor=current_user,
        target_type="user",
        target_ref=str(current_user.user_id),
        source_ip=_client_ip(request),
    )
    session.commit()


# ---------------------------------------------------------
# ADMIN-ONLY
# ---------------------------------------------------------


@router.get(
    "/", response_model=UserListResponse, dependencies=[Depends(get_current_admin)]
)
def get_all_users(
    search: str | None = Query(default=None, min_length=1, max_length=100),
    limit: int = Query(default=10, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
) -> UserListResponse:
    """Admin: paginated, searchable user directory. Not audited — there is
    no catalog action for viewing, and D-007 excludes routine viewing."""
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
)
def create_user(
    user_in: UserCreate,
    request: Request,
    session: Session = Depends(get_session),
    current_admin: User = Depends(_require_admin_for_create),
) -> UserRead:
    """Admin: create a new user account."""
    new_user = User(
        username=user_in.username,
        first_name=user_in.first_name,
        last_name=user_in.last_name,
        role=user_in.role,
        password_hash=get_password_hash(user_in.password),
        password_changed_at=datetime.now(UTC),
    )

    try:
        session.add(new_user)
        # Flush (not commit) to assign the autoincrement PK so the audit
        # row's target_ref can be known before the two commit together.
        session.flush()
        audit.record(
            session,
            action="USER_CREATE",
            result=AuditResult.SUCCESS,
            actor=current_admin,
            target_type="user",
            target_ref=str(new_user.user_id),
            detail={"username": new_user.username, "role": str(new_user.role)},
            source_ip=_client_ip(request),
        )
        session.commit()
        session.refresh(new_user)
        return UserRead.model_validate(new_user)
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken.",
        ) from exc


@router.patch(
    "/{user_id}",
    response_model=UserRead,
)
def update_user(
    user_id: int,
    update_in: UserAdminUpdate,
    request: Request,
    session: Session = Depends(get_session),
    current_admin: User = Depends(_require_admin_for_update),
) -> UserRead:
    """Admin: edit a user's profile, role, or active status.
    Guards against demoting or deactivating the last active admin."""
    target = _get_active_user_or_404(user_id, session)
    update_data = update_in.model_dump(exclude_unset=True)
    source_ip = _client_ip(request)

    # Guard: cannot demote or deactivate the last active admin
    is_last_admin = (
        target.role == UserRole.ADMIN and _get_active_admin_count(session) <= 1
    )

    if is_last_admin:
        if update_data.get("role") == UserRole.OPERATOR:
            audit.record_out_of_band(
                session.get_bind(),
                action="USER_ROLE_CHANGE",
                result=AuditResult.DENIED,
                actor=current_admin,
                target_type="user",
                target_ref=str(target.user_id),
                detail={"reason": "last_admin_demote"},
                source_ip=source_ip,
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot demote the last active Administrator.",
            )
        if update_data.get("is_active") is False:
            audit.record_out_of_band(
                session.get_bind(),
                action="USER_DISABLE",
                result=AuditResult.DENIED,
                actor=current_admin,
                target_type="user",
                target_ref=str(target.user_id),
                detail={"reason": "last_admin_deactivate"},
                source_ip=source_ip,
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot deactivate the last active Administrator.",
            )

    # D-006 revocation cascade and D-007 multi-action audit — both computed
    # from the *pre-mutation* target before setattr below changes it.
    # Username/first_name/last_name never revoke: identity is user_id, so a
    # rename invalidates nothing.
    role_changed = "role" in update_data and update_data["role"] != target.role
    being_deactivated = (
        "is_active" in update_data
        and update_data["is_active"] is False
        and target.is_active is True
    )
    being_enabled = (
        "is_active" in update_data
        and update_data["is_active"] is True
        and target.is_active is False
    )
    old_role = target.role

    for key, value in update_data.items():
        setattr(target, key, value)

    if being_deactivated:
        revoke_all_for_user(session, target.user_id, "account_disabled")
    elif role_changed:
        revoke_all_for_user(session, target.user_id, "role_change")

    # USER_UPDATE is the base action for this route ("USER_UPDATE, plus ...
    # as applicable" — 01_CONTRACTS.md §10); role/enable/disable are
    # additional semantic rows on top, all in the same transaction.
    audit.record(
        session,
        action="USER_UPDATE",
        result=AuditResult.SUCCESS,
        actor=current_admin,
        target_type="user",
        target_ref=str(target.user_id),
        detail={"changed_fields": sorted(update_data.keys())},
        source_ip=source_ip,
    )
    if role_changed:
        audit.record(
            session,
            action="USER_ROLE_CHANGE",
            result=AuditResult.SUCCESS,
            actor=current_admin,
            target_type="user",
            target_ref=str(target.user_id),
            detail={"from": str(old_role), "to": str(target.role)},
            source_ip=source_ip,
        )
    if being_deactivated:
        audit.record(
            session,
            action="USER_DISABLE",
            result=AuditResult.SUCCESS,
            actor=current_admin,
            target_type="user",
            target_ref=str(target.user_id),
            source_ip=source_ip,
        )
    elif being_enabled:
        audit.record(
            session,
            action="USER_ENABLE",
            result=AuditResult.SUCCESS,
            actor=current_admin,
            target_type="user",
            target_ref=str(target.user_id),
            source_ip=source_ip,
        )

    try:
        session.add(target)
        session.commit()
        session.refresh(target)
        return UserRead.model_validate(target)
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken.",
        ) from exc


@router.post(
    "/{user_id}/reset-password",
    status_code=status.HTTP_204_NO_CONTENT,
)
def reset_user_password(
    user_id: int,
    passwords_in: UserResetPassword,
    request: Request,
    session: Session = Depends(get_session),
    current_admin: User = Depends(_require_admin_for_password_reset),
) -> None:
    """Admin: force-reset any user's password."""
    target = _get_active_user_or_404(user_id, session)

    target.password_hash = get_password_hash(passwords_in.new_password)
    target.password_changed_at = datetime.now(UTC)
    session.add(target)
    revoke_all_for_user(session, target.user_id, "password_reset")
    audit.record(
        session,
        action="USER_PASSWORD_RESET",
        result=AuditResult.SUCCESS,
        actor=current_admin,
        target_type="user",
        target_ref=str(target.user_id),
        source_ip=_client_ip(request),
    )
    session.commit()


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_user(
    user_id: int,
    request: Request,
    session: Session = Depends(get_session),
    current_admin: User = Depends(_require_admin_for_disable),
) -> None:
    """Admin: soft-delete a user. Guards against deleting the last active admin
    and against self-deletion."""
    target = _get_active_user_or_404(user_id, session)
    source_ip = _client_ip(request)

    # Guard: cannot delete yourself
    if target.user_id == current_admin.user_id:
        audit.record_out_of_band(
            session.get_bind(),
            action="USER_DISABLE",
            result=AuditResult.DENIED,
            actor=current_admin,
            target_type="user",
            target_ref=str(target.user_id),
            detail={"reason": "self_delete"},
            source_ip=source_ip,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot delete your own account.",
        )

    # Guard: cannot delete the last active admin
    if target.role == UserRole.ADMIN and _get_active_admin_count(session) <= 1:
        audit.record_out_of_band(
            session.get_bind(),
            action="USER_DISABLE",
            result=AuditResult.DENIED,
            actor=current_admin,
            target_type="user",
            target_ref=str(target.user_id),
            detail={"reason": "last_admin_delete"},
            source_ip=source_ip,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete the last active Administrator.",
        )

    target.is_active = False
    session.add(target)
    revoke_all_for_user(session, target.user_id, "account_disabled")
    audit.record(
        session,
        action="USER_DISABLE",
        result=AuditResult.SUCCESS,
        actor=current_admin,
        target_type="user",
        target_ref=str(target.user_id),
        source_ip=source_ip,
    )
    session.commit()
