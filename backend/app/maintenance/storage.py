"""P30 storage-target discovery and physical-device safety checks.

The backup code deliberately knows about *artifact roots*, not removable
media.  A protected root is safe only when an injected provider can prove
that it is writable, has space, and is on a different physical device from
the live database.  This module keeps that policy small and testable.

No device identifier or configured path is part of :class:`StorageProbe`'s
public representation.  The private identifier is retained only long enough
for the same-device comparison and is never returned by the API or written to
an audit row.
"""

from __future__ import annotations

import ctypes
import errno
import os
import shutil
import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

STORAGE_TIER_PROTECTED = "protected"
STORAGE_TIER_DEGRADED = "degraded"
VALID_STORAGE_TIERS = frozenset({STORAGE_TIER_PROTECTED, STORAGE_TIER_DEGRADED})
_SAFE_REASON_PATTERN = r"^[a-z0-9_]{1,64}$"

# These are stable, deliberately path-free values.  They are suitable for a
# response message, a manifest's degraded reason, or an audit detail value.
STORAGE_REASON_NOT_CONFIGURED = "not_configured"
STORAGE_REASON_NOT_ABSOLUTE = "not_absolute"
STORAGE_REASON_UNC_UNSUPPORTED = "unc_unsupported"
STORAGE_REASON_MISSING = "missing"
STORAGE_REASON_NOT_DIRECTORY = "not_directory"
STORAGE_REASON_UNWRITABLE = "unwritable"
STORAGE_REASON_FULL = "full"
STORAGE_REASON_SAME_DEVICE = "same_device"
STORAGE_REASON_UNVERIFIABLE = "unverifiable"
STORAGE_REASON_PUBLISH_FAILED = "publish_failed"
STORAGE_REASON_UNKNOWN = "unavailable"


@dataclass(frozen=True)
class StorageProbe:
    """The result of checking one configured protected artifact root.

    ``device_id`` is intentionally excluded from ``repr`` and is not exposed
    by any serializer.  It exists solely so callers that need to compare
    identities can do so without re-probing.
    """

    available: bool
    reason: str | None = None
    free_bytes: int | None = None
    device_id: Any = field(default=None, repr=False, compare=False)

    @property
    def public_reason(self) -> str | None:
        return self.reason


class StorageTargetProvider(Protocol):
    def probe(
        self,
        target_path: Path,
        *,
        live_db_path: Path,
        required_bytes: int = 0,
    ) -> StorageProbe: ...


def validate_storage_tier(storage_tier: str) -> str:
    if storage_tier not in VALID_STORAGE_TIERS:
        raise ValueError(f"Unknown storage tier: {storage_tier!r}")
    return storage_tier


def sanitize_storage_reason(reason: Any) -> str | None:
    if not isinstance(reason, str):
        return None
    import re

    return reason if re.fullmatch(_SAFE_REASON_PATTERN, reason) else None


def _is_unc_path(path: Path) -> bool:
    value = str(path)
    return value.startswith("\\\\") or value.startswith("//")


def _nearest_existing_ancestor(path: Path) -> Path | None:
    """Return the nearest existing path without creating anything."""
    candidate = Path(path)
    try:
        candidate = candidate.resolve(strict=False)
    except (OSError, RuntimeError):
        return None
    while not candidate.exists():
        parent = candidate.parent
        if parent == candidate:
            return None
        candidate = parent
    return candidate


def _posix_device_identity(path: Path) -> int | None:
    existing = _nearest_existing_ancestor(path)
    if existing is None:
        return None
    try:
        return int(os.stat(existing).st_dev)
    except OSError:
        return None


def _windows_volume_path(path: Path) -> str | None:
    """Resolve a path through junctions/SUBST to its Windows volume root."""
    if os.name != "nt":
        return None
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        get_volume_path = kernel32.GetVolumePathNameW
        buffer = ctypes.create_unicode_buffer(32768)
        ok = get_volume_path(str(path), buffer, len(buffer))
        if not ok:
            return None
        return buffer.value or None
    except (AttributeError, OSError, TypeError):
        return None


def _windows_device_identity(path: Path) -> tuple[int, ...] | None:
    """Return the physical disk numbers for a Windows volume.

    ``GetVolumePathNameW`` resolves a folder mount, junction, or SUBST path
    to the mounted volume.  ``IOCTL_VOLUME_GET_VOLUME_DISK_EXTENTS`` then
    identifies the physical disk(s), so another partition on the same disk is
    correctly rejected as unprotected.
    """
    if os.name != "nt":
        return None
    volume_root = _windows_volume_path(path)
    if not volume_root:
        return None
    if len(volume_root) >= 2 and volume_root[1] == ":":
        device_path = f"\\\\.\\{volume_root[0]}:"
    else:
        # Volume GUID mount paths are not UNC shares, but CreateFileW needs
        # the device namespace form.  The native path is still safer to treat
        # as unverifiable if it cannot be converted deterministically.
        return None

    IOCTL_VOLUME_GET_VOLUME_DISK_EXTENTS = 0x00560000
    INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        handle = kernel32.CreateFileW(
            device_path,
            0,
            0x00000001 | 0x00000002 | 0x00000004,
            None,
            3,  # OPEN_EXISTING
            0,
            None,
        )
        if handle == INVALID_HANDLE_VALUE:
            return None
        try:
            output = ctypes.create_string_buffer(65536)
            returned = ctypes.c_ulong(0)
            ok = kernel32.DeviceIoControl(
                handle,
                IOCTL_VOLUME_GET_VOLUME_DISK_EXTENTS,
                None,
                0,
                output,
                len(output),
                ctypes.byref(returned),
                None,
            )
            if not ok or returned.value < 4:
                return None
            extent_count = struct.unpack_from("<I", output.raw, 0)[0]
            # DISK_EXTENT is DWORD + LARGE_INTEGER + LARGE_INTEGER.  The
            # first field is the physical disk number; the structure is 24
            # bytes on Windows because the two 64-bit fields are aligned.
            extent_size = 24
            disk_numbers: list[int] = []
            for index in range(extent_count):
                offset = 4 + index * extent_size
                if offset + 4 > returned.value:
                    return None
                disk_numbers.append(struct.unpack_from("<I", output.raw, offset)[0])
            return tuple(sorted(set(disk_numbers))) or None
        finally:
            kernel32.CloseHandle(handle)
    except (AttributeError, OSError, TypeError, ValueError):
        return None


def _shares_physical_device(left: Any, right: Any) -> bool:
    """Treat multi-disk volume identities as overlapping when appropriate."""
    if isinstance(left, (tuple, list, set, frozenset)) and isinstance(
        right, (tuple, list, set, frozenset)
    ):
        return bool(set(left).intersection(right))
    return left == right


class PhysicalDeviceProvider:
    """Default platform-specific protected-root provider.

    Tests should inject a provider rather than requiring a second CI disk.
    The public ``probe`` result contains only stable reason codes; the
    platform-specific identity remains an internal comparison detail.
    """

    def identify(self, path: Path) -> Any:
        if os.name == "nt":
            return _windows_device_identity(path)
        return _posix_device_identity(path)

    def probe(
        self,
        target_path: Path,
        *,
        live_db_path: Path,
        required_bytes: int = 0,
    ) -> StorageProbe:
        target_path = Path(target_path)
        live_db_path = Path(live_db_path)

        if _is_unc_path(target_path):
            return StorageProbe(False, STORAGE_REASON_UNC_UNSUPPORTED)
        if not target_path.is_absolute():
            return StorageProbe(False, STORAGE_REASON_NOT_ABSOLUTE)
        try:
            if not target_path.exists():
                return StorageProbe(False, STORAGE_REASON_MISSING)
            if not target_path.is_dir():
                return StorageProbe(False, STORAGE_REASON_NOT_DIRECTORY)
            if not os.access(target_path, os.W_OK) or not (
                target_path.stat().st_mode & 0o222
            ):
                return StorageProbe(False, STORAGE_REASON_UNWRITABLE)

            target_id = self.identify(target_path)
            live_id = self.identify(live_db_path)
            if target_id is None or live_id is None:
                return StorageProbe(False, STORAGE_REASON_UNVERIFIABLE)
            if _shares_physical_device(target_id, live_id):
                return StorageProbe(
                    False,
                    STORAGE_REASON_SAME_DEVICE,
                    device_id=target_id,
                )

            usage = shutil.disk_usage(target_path)
            free_bytes = int(usage.free)
            if free_bytes < max(1, int(required_bytes)):
                return StorageProbe(
                    False,
                    STORAGE_REASON_FULL,
                    free_bytes=free_bytes,
                    device_id=target_id,
                )
            return StorageProbe(
                True,
                free_bytes=free_bytes,
                device_id=target_id,
            )
        except PermissionError:
            return StorageProbe(False, STORAGE_REASON_UNWRITABLE)
        except OSError as exc:
            if exc.errno == errno.ENOSPC:
                return StorageProbe(False, STORAGE_REASON_FULL)
            return StorageProbe(False, STORAGE_REASON_UNVERIFIABLE)


# Descriptive alias for callers/tests that use the P30 wording.
StorageTargetPhysicalDeviceProvider = PhysicalDeviceProvider


def _normalise_probe(value: Any) -> StorageProbe:
    if isinstance(value, StorageProbe):
        probe = value
    elif isinstance(value, bool):
        probe = StorageProbe(value, None if value else STORAGE_REASON_UNKNOWN)
    elif isinstance(value, dict):
        probe = StorageProbe(
            bool(value.get("available")),
            value.get("reason"),
            value.get("free_bytes"),
            value.get("device_id"),
        )
    else:
        raise TypeError("Storage target provider returned an unsupported result.")

    # Providers are an injection seam, so normalize even test doubles before
    # a reason can reach a manifest, audit detail, CLI response, or API.  A
    # malformed reason is an unavailable target, never a path-bearing error.
    reason = sanitize_storage_reason(probe.reason)
    if not probe.available:
        reason = reason or (
            STORAGE_REASON_UNVERIFIABLE
            if probe.reason is not None
            else STORAGE_REASON_UNKNOWN
        )
    return StorageProbe(
        bool(probe.available),
        reason,
        probe.free_bytes,
        probe.device_id,
    )


def probe_protected_storage(
    protected_path: Path | None,
    *,
    live_db_path: Path,
    required_bytes: int = 0,
    provider: StorageTargetProvider | Any | None = None,
) -> StorageProbe:
    """Probe an explicit protected root; never discover removable media."""
    if protected_path is None:
        return StorageProbe(False, STORAGE_REASON_NOT_CONFIGURED)
    target_path = Path(protected_path)
    if _is_unc_path(target_path):
        return StorageProbe(False, STORAGE_REASON_UNC_UNSUPPORTED)
    if not target_path.is_absolute():
        return StorageProbe(False, STORAGE_REASON_NOT_ABSOLUTE)

    selected_provider = provider or PhysicalDeviceProvider()
    try:
        probe_method = getattr(selected_provider, "probe", None)
        if probe_method is not None:
            try:
                raw = probe_method(
                    target_path,
                    live_db_path=Path(live_db_path),
                    required_bytes=required_bytes,
                )
            except TypeError:
                # Small injected fakes often use the simpler positional
                # signature; keep the production contract keyword-only.
                raw = probe_method(target_path, Path(live_db_path), required_bytes)
        else:
            raw = selected_provider(target_path, Path(live_db_path), required_bytes)
        return _normalise_probe(raw)
    except PermissionError:
        return StorageProbe(False, STORAGE_REASON_UNWRITABLE)
    except OSError as exc:
        reason = (
            STORAGE_REASON_FULL
            if exc.errno == errno.ENOSPC
            else STORAGE_REASON_UNVERIFIABLE
        )
        return StorageProbe(False, reason)
    except (RuntimeError, TypeError, ValueError):
        return StorageProbe(False, STORAGE_REASON_UNVERIFIABLE)


def reason_for_publish_failure(exc: BaseException) -> str:
    """Map an internal target failure to a path-free manifest reason."""
    if isinstance(exc, PermissionError):
        return STORAGE_REASON_UNWRITABLE
    if isinstance(exc, OSError) and exc.errno == errno.ENOSPC:
        return STORAGE_REASON_FULL
    return STORAGE_REASON_PUBLISH_FAILED


# Short aliases keep the injected seam discoverable to callers without
# encouraging direct use of platform-specific helpers.
probe_storage_target = probe_protected_storage


def get_physical_device_identity(path: Path) -> Any:
    return PhysicalDeviceProvider().identify(path)


# Descriptive alias for schema/test code that calls the result a status.
StorageTargetStatus = StorageProbe


__all__ = [
    "PhysicalDeviceProvider",
    "StorageProbe",
    "StorageTargetStatus",
    "StorageTargetPhysicalDeviceProvider",
    "StorageTargetProvider",
    "STORAGE_REASON_FULL",
    "STORAGE_REASON_MISSING",
    "STORAGE_REASON_NOT_ABSOLUTE",
    "STORAGE_REASON_NOT_CONFIGURED",
    "STORAGE_REASON_NOT_DIRECTORY",
    "STORAGE_REASON_PUBLISH_FAILED",
    "STORAGE_REASON_SAME_DEVICE",
    "STORAGE_REASON_UNC_UNSUPPORTED",
    "STORAGE_REASON_UNWRITABLE",
    "STORAGE_REASON_UNVERIFIABLE",
    "STORAGE_TIER_DEGRADED",
    "STORAGE_TIER_PROTECTED",
    "VALID_STORAGE_TIERS",
    "get_physical_device_identity",
    "probe_protected_storage",
    "probe_storage_target",
    "reason_for_publish_failure",
    "sanitize_storage_reason",
    "validate_storage_tier",
]
