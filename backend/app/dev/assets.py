"""Placeholder snapshot images for seeded detections.

dev_plan/01_PKG_seed_core.md Step 6. The seeder has always built
`snapshot_key` strings in 01_CONTRACTS.md §7.1's nested format but never
written a file at them, so `GET /api/alerts/{log_id}/snapshot` 404s for
every row in a seeded database — the alert detail view has no evidence
image to show.

No new dependency. Pillow is only a transitive of the `ai` extra, so a
plain `uv sync` has no image generation available; the fallback is an
embedded constant instead. Dropping real frames into
`backend/app/dev/assets/snapshots/` gives a better-looking demo and takes
precedence over it.
"""

from __future__ import annotations

import base64
from functools import lru_cache
from pathlib import Path

ASSETS_DIR = Path(__file__).resolve().parent / "assets" / "snapshots"

# A 160x90 JPEG, ~1.2 KB, dark grey with a border and a "SEED SNAPSHOT"
# label. Deliberately obvious: nobody should mistake one of these for real
# evidence during a demo.
_PLACEHOLDER_JPEG_B64 = (
    "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAA0JCgsKCA0LCgsODg0PEyAVExISEyccHhcgLikxMC4p"
    "LSwzOko+MzZGNywtQFdBRkxOUlNSMj5aYVpQYEpRUk//2wBDAQ4ODhMREyYVFSZPNS01T09PT09P"
    "T09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT0//wAARCABaAKADASIA"
    "AhEBAxEB/8QAGgABAQEBAQEBAAAAAAAAAAAAAAQDAgUBBv/EAC0QAAIBAwIGAQQBBQEAAAAAAAAB"
    "AgMEERRTEiExgaKxNBMiQVFhFTJxkaHS/8QAFQEBAQAAAAAAAAAAAAAAAAAAAAH/xAAUEQEAAAAA"
    "AAAAAAAAAAAAAAAA/9oADAMBAAIRAxEAPwD8QAXXd1Xp3M4QniKxhYX6KIQUa653PFDXXO54oCcF"
    "GuudzxQ11zueKAnBRrrnc8UNdc7nigJwUa653PFDXXO54oCcFGuudzxQ11zueKAnBRrrnc8UNdc7"
    "nigJwUa653PFDXXO54oCcFGuudzxQ11zueKAnBdaXVepcwhOeYvOVhfohAFF/wDMqdvSJyi/+ZU7"
    "ekBOAAAAAAAAAAAAAAAAAAAAAosPmU+/pk5RYfMp9/TJwBRf/MqdvSJyi/8AmVO3pATgAAAb2kaU"
    "py+rw/2/bxZ4c5XXHP8AYGAPRq28KdDiVvS4nOSfHV6Lhi1w81nq/wB/g+q3pam1pOjS4KjpcTVR"
    "8T4km+XFy6v8AeaCicadS1daNJU5Rmo4i21LKb/Lf6/6WQoWrq8apRqUI8bzGbTeISaUk+j5fjl1"
    "A8sF+igpUIvmpVZ5nnHFTUYyT/jk2du2pxVaapUZLipuKnVxGKkpNpPPPmsfnoB5oL5UbaVOoreK"
    "qYU3zk1PCbw1+GsYz+epp/T4O8uqf2KCnwwxUTcc1Ix6Zz0b6geYCtfRqQrSjbxh9HEknKX3LKWH"
    "z68/xjoc3v041Ixp0YU1wQk2nJ5bim+rf7AmAAFFh8yn39MnKLD5lPv6ZOAKL/5lTt6ROUX/AMyp"
    "29ICcAADulVnSbcGuaw00mmv8M4AG7u6zi4ycJLLf3U4vHJLllcuSX+hrK3FCWYcVPh4ZfTjlcOM"
    "c8fwjAAaVK9SqkpNKMeaUYqKz/hHcryvLOZrLzlqKWcpp55c3hvn/JgANdVXdKNJz+yCaisLkn19"
    "Hx16kqKouX2LGFhfjP8A6f8AszAGquaqpfTUlw4aX2rKT6rPXB8deq51Zuf3Vf73jrzT9pGYA1q3"
    "NWrFxnJYby8RS4n+3jr3OJzlUkpTeWko9ksL/iOQAAAFFh8yn39MnKLD5lPv6ZOAKL/5lTt6ROUX"
    "/wAyp29ICcAAAAAAAAAAAAAAAAAAAABRYfMp9/TJyiw+ZT7+mTgCjXXO54onAFGuudzxQ11zueKJ"
    "wBRrrnc8UNdc7niicAUa653PFDXXO54onAFGuudzxQ11zueKJwBRrrnc8UNdc7niicAUa653PFDX"
    "XO54onAFGuudzxQ11zueKJwBRrrnc8UNdc7niicAUa653PFE4AH/2Q=="
)


@lru_cache(maxsize=1)
def _image_pool() -> tuple[bytes, ...]:
    """Real frames from ASSETS_DIR if any were dropped there, else the
    single embedded placeholder. Cached because a profile writes one image
    per detection and re-reading the directory each time is pointless."""
    if ASSETS_DIR.is_dir():
        real = sorted(
            path
            for path in ASSETS_DIR.iterdir()
            if path.is_file() and path.suffix.lower() in (".jpg", ".jpeg")
        )
        if real:
            return tuple(path.read_bytes() for path in real)
    return (base64.b64decode(_PLACEHOLDER_JPEG_B64),)


def write_snapshot(snapshot_key: str, *, snapshot_root: Path, index: int = 0) -> bool:
    """Writes a placeholder image at `snapshot_root / snapshot_key`,
    creating parent directories. Returns False if the key escapes
    `snapshot_root`, is unresolvable, or if a file is already there.

    `index` picks which pooled image to use, so a caller enumerating its
    detections gets them round-robin rather than the same frame every time.
    """
    # The seeder builds these keys itself, but this is also reachable from
    # Package B's injector with a caller-supplied one — same containment
    # pattern as services/snapshots.resolve(). A pathological key makes
    # .resolve() raise instead of returning: OSError/RuntimeError for a
    # symlink loop, ValueError for an embedded null byte (verified directly —
    # it is NOT an OSError on this platform). Any of those must reject
    # cleanly, not propagate as an unhandled 500.
    try:
        root = snapshot_root.resolve()
        target = (snapshot_root / snapshot_key).resolve()
    except (OSError, RuntimeError, ValueError):
        return False

    if not target.is_relative_to(root):
        return False
    if target.exists():
        return False

    pool = _image_pool()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(pool[index % len(pool)])
    return True
