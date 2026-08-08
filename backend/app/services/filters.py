from datetime import datetime

from fastapi import HTTPException


def validate_common_filters(
    *,
    start_date: datetime | None,
    end_date: datetime | None,
    camera_ids: list[int] | None = None,
    user_ids: list[int] | None = None,
) -> None:
    """Raise 422 for invalid shared list-endpoint filters.

    Shared by alerts and analytics (and, per P6, exports) so the date-range
    and positive-id rules never drift between endpoints.
    """
    if start_date and end_date and start_date > end_date:
        raise HTTPException(
            status_code=422,
            detail="Invalid date range: `start_date` must be earlier than or equal to `end_date`.",
        )

    if camera_ids and any(camera_id <= 0 for camera_id in camera_ids):
        raise HTTPException(
            status_code=422,
            detail="Invalid `camera_id` value(s): values must be positive integers.",
        )

    if user_ids and any(user_id <= 0 for user_id in user_ids):
        raise HTTPException(
            status_code=422,
            detail="Invalid `user_id` value(s): values must be positive integers.",
        )
