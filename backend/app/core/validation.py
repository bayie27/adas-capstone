def reject_null_bytes(v: str | None) -> str | None:
    """Edge case 4.6 — SQLite stores an embedded NUL faithfully, but plenty
    of downstream consumers (CSV/PDF export, C-string-based tooling, even
    some drivers) truncate at it, so reject it at the validation boundary
    rather than relying on every consumer to be NUL-safe."""
    if isinstance(v, str) and "\x00" in v:
        raise ValueError("must not contain a null byte")
    return v
