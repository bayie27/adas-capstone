from fastapi import HTTPException


class AppHTTPException(HTTPException):
    """An `HTTPException` carrying an explicit machine-readable `code`
    (01_CONTRACTS.md §1.3) instead of falling back to the generic default
    for its status code — needed wherever one status code covers several
    distinct error codes, e.g. 401 splits into AUTH_REQUIRED / AUTH_EXPIRED
    / AUTH_REVOKED. `extra` merges additional fields into the JSON body,
    e.g. the 409 CONFLICT_STATE payload's current_status/handled_by fields.
    """

    def __init__(
        self,
        status_code: int,
        detail: str,
        *,
        code: str,
        headers: dict[str, str] | None = None,
        extra: dict | None = None,
    ) -> None:
        super().__init__(status_code=status_code, detail=detail, headers=headers)
        self.code = code
        self.extra = extra or {}
