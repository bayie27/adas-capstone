"""05_PKG_incidents_cameras.md Step 9 — authenticated snapshot retrieval
(01_CONTRACTS.md §7.1, D-012). Replaces the public /snapshots static mount:
evidence images are only reachable through GET /api/alerts/{log_id}/snapshot,
session-authenticated like every other operator-facing route.
"""

import re
from pathlib import Path

_DRIVE_LETTER = re.compile(r"^[A-Za-z]:")


def _looks_hostile(key: str) -> bool:
    """Fast, filesystem-free rejection of the obviously malicious shapes
    (01_CONTRACTS.md §7.1): absolute paths, `..` segments, drive letters,
    UNC prefixes, and null bytes."""
    if not key or "\x00" in key:
        return True
    if key.startswith("/") or key.startswith("\\"):
        return True
    if _DRIVE_LETTER.match(key):
        return True
    return any(segment == ".." for segment in key.replace("\\", "/").split("/"))


def resolve(snapshot_key: str, *, snapshot_root: Path, legacy_dir: Path) -> Path | None:
    """Resolves `snapshot_key` to an existing file inside one of the two
    configured roots, or None if it's hostile, unresolvable, or missing.

    Checking the input string is not enough — symlinks and Path.resolve()
    normalization can escape the configured root, so every candidate is
    also checked for actual containment *after* resolution, which is what
    catches a symlink pointing outside it.
    """
    if _looks_hostile(snapshot_key):
        return None

    resolved_root = snapshot_root.resolve()
    resolved_legacy = legacy_dir.resolve()
    roots = [resolved_root, resolved_legacy]

    candidates = [snapshot_root / snapshot_key]
    has_separator = "/" in snapshot_key or "\\" in snapshot_key
    if not has_separator:
        candidates.append(legacy_dir / snapshot_key)

    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except (OSError, RuntimeError):
            continue
        if not any(resolved.is_relative_to(root) for root in roots):
            continue
        if resolved.is_file():
            return resolved
    return None
