"""Reconciles local camera runtimes against the backend's heartbeat snapshot
(D-003 §2.2, 01_CONTRACTS.md §6.2). Replaces sync.py.

compute_actions() is the pure reconciliation decision — it takes plain
dicts and returns a plan, with no side effects and no cv2 import, so it is
directly unit-testable in CI. `camera.CameraStream` (which imports cv2) is
only imported lazily inside _apply_actions(), the one function that
actually touches RTSP streams, so importing this module at all does not
require the `ai` extra.
"""

import logging
import threading
import time
from dataclasses import dataclass
from enum import Enum

import outbox
from backend_client import send_heartbeat
from config import ENGINE_ID, HEARTBEAT_INTERVAL_SECONDS

logger = logging.getLogger("ai_engine")


class Action(Enum):
    START = "start"
    STOP = "stop"
    PAUSE = "pause"
    RESUME = "resume"
    REAPPLY_CONFIG = "reapply_config"  # rtsp_url or channel_id changed: restart
    UPDATE_CONFIG = "update_config"  # config_version bumped, nothing to restart


@dataclass
class ReconcileAction:
    camera_id: int
    action: Action
    camera_snapshot: dict | None = (
        None  # present for START / REAPPLY_CONFIG / UPDATE_CONFIG
    )


def compute_actions(
    snapshot_cameras, local_cameras, pending_outbox_camera_ids=frozenset()
):
    """Pure decision function.

    snapshot_cameras: the heartbeat response's `cameras` list — each dict
        has camera_id, channel_id, rtsp_url, is_enabled, desired_ai_state,
        config_version, ... (01_CONTRACTS.md §6.2).
    local_cameras: dict[camera_id] -> {"is_paused", "applied_config_version",
        "rtsp_url", "channel_id"} describing what the engine currently runs.
    pending_outbox_camera_ids: camera_ids with at least one event still
        queued for delivery (outbox.pending_camera_ids()). The backend's
        snapshot cannot know about an event that hasn't been delivered yet
        — nothing is committed to its DB until then — so it will keep
        reporting the pre-incident `desired_ai_state: Active` for that
        camera. Honoring that resume here would let the engine detect again
        before the original event's outbox retry even fires; the newer
        detection would then win the open-incident race and the backend
        would discard the original as a "redundant" 409 CONFLICT — silently
        losing a genuine, earlier detection (F20, be_audit/00_FINDINGS.md).
        A camera in this set stays paused regardless of what the snapshot
        says, until its outbox entry has actually been delivered or given
        up on.

    The v2 snapshot includes ALL is_active cameras, including disabled ones
    (is_enabled: false) — unlike the legacy poll, which pre-filtered to
    enabled-only. This function does that filtering; callers must not start
    a stream for anything this function didn't return a START for.
    """
    actions: list[ReconcileAction] = []
    snapshot_by_id = {cam["camera_id"]: cam for cam in snapshot_cameras}

    def _wants_runtime(snap: dict) -> bool:
        return (
            bool(snap.get("is_enabled")) and snap.get("desired_ai_state") != "Inactive"
        )

    # Absent from the snapshot, or present but disabled/inactive: stop it.
    for camera_id in local_cameras:
        snap = snapshot_by_id.get(camera_id)
        if snap is None or not _wants_runtime(snap):
            actions.append(ReconcileAction(camera_id, Action.STOP))

    for camera_id, snap in snapshot_by_id.items():
        if not _wants_runtime(snap):
            continue

        local = local_cameras.get(camera_id)
        if local is None:
            actions.append(ReconcileAction(camera_id, Action.START, snap))
            continue

        restart_needed = local.get("rtsp_url") != snap.get("rtsp_url") or local.get(
            "channel_id"
        ) != snap.get("channel_id")
        config_changed = local.get("applied_config_version") != snap.get(
            "config_version"
        )

        # restart_needed is deliberately NOT gated on config_changed: the
        # backend's RTSP_URL_TEMPLATE is a global .env setting, not a
        # per-camera DB write, so it never bumps config_version. Gating the
        # restart on a version bump would mean a template/credential change
        # (e.g. MediaMTX -> DSS cutover) is silently ignored by every
        # already-running stream.
        has_pending_event = camera_id in pending_outbox_camera_ids
        if restart_needed:
            # A fresh stream is constructed in the correct desired state
            # directly, so no separate pause/resume action is needed —
            # except a pending outbox event overrides a stale "Active"
            # the same way it does below, or the restart would silently
            # hand back an unpaused stream (see pending_outbox_camera_ids).
            reapply_snap = snap
            if has_pending_event and snap.get("desired_ai_state") != "Paused":
                reapply_snap = {**snap, "desired_ai_state": "Paused"}
            actions.append(
                ReconcileAction(camera_id, Action.REAPPLY_CONFIG, reapply_snap)
            )
            continue

        if config_changed:
            actions.append(ReconcileAction(camera_id, Action.UPDATE_CONFIG, snap))

        desired = snap.get("desired_ai_state")
        if desired == "Paused" and not local.get("is_paused"):
            actions.append(ReconcileAction(camera_id, Action.PAUSE))
        elif desired == "Active" and local.get("is_paused") and not has_pending_event:
            actions.append(ReconcileAction(camera_id, Action.RESUME))

    return actions


def _build_report(cameras: dict) -> list[dict]:
    return [cam.observed_state() for cam in cameras.values()]


def _local_camera_states(cameras: dict) -> dict:
    return {
        camera_id: {
            "is_paused": cam.is_paused,
            "applied_config_version": cam.applied_config_version,
            "rtsp_url": cam.url,
            "channel_id": cam.channel_id,
        }
        for camera_id, cam in cameras.items()
    }


def _start_stream(camera_id: int, snap: dict):
    from camera import CameraStream

    new_cam = CameraStream(
        channel_id=snap["channel_id"], camera_id=camera_id, rtsp_url=snap["rtsp_url"]
    )
    new_cam.applied_config_version = snap.get("config_version")
    if snap.get("desired_ai_state") == "Paused":
        new_cam.pause()
    return new_cam


def _apply_actions(actions: list[ReconcileAction], cameras: dict) -> None:
    for action in actions:
        cam = cameras.get(action.camera_id)

        if action.action is Action.STOP:
            if cam is not None:
                print(
                    f"[SUPERVISOR] Camera {action.camera_id} absent/disabled. "
                    "Stopping runtime and releasing socket..."
                )
                cam.stop()
                del cameras[action.camera_id]

        elif action.action is Action.START:
            snap = action.camera_snapshot
            print(
                f"[SUPERVISOR] New camera detected! Starting Channel "
                f"{snap['channel_id']} (camera {action.camera_id})..."
            )
            cameras[action.camera_id] = _start_stream(action.camera_id, snap)

        elif action.action is Action.REAPPLY_CONFIG:
            snap = action.camera_snapshot
            print(
                f"[SUPERVISOR] Config changed for camera {action.camera_id}; "
                "restarting stream..."
            )
            if cam is not None:
                cam.stop()
            cameras[action.camera_id] = _start_stream(action.camera_id, snap)

        elif action.action is Action.UPDATE_CONFIG:
            if cam is not None:
                cam.applied_config_version = action.camera_snapshot.get(
                    "config_version"
                )

        elif action.action is Action.PAUSE and cam is not None:
            cam.pause()

        elif action.action is Action.RESUME and cam is not None:
            cam.resume()


def heartbeat_loop(cameras: dict) -> None:
    """Runs forever. A backend outage or an exception mid-cycle must never
    tear down running cameras — log it, keep what's running, retry."""
    interval = HEARTBEAT_INTERVAL_SECONDS
    while True:
        try:
            response = send_heartbeat(ENGINE_ID, _build_report(cameras))
            if response is not None:
                snapshot_cameras = response.get("cameras", [])
                actions = compute_actions(
                    snapshot_cameras,
                    _local_camera_states(cameras),
                    outbox.pending_camera_ids(),
                )
                _apply_actions(actions, cameras)
                interval = response.get(
                    "heartbeat_interval_seconds", HEARTBEAT_INTERVAL_SECONDS
                )
        except Exception:
            logger.exception("Heartbeat/reconciliation cycle failed")

        time.sleep(interval)


def start_supervisor_thread(cameras: dict) -> threading.Thread:
    """Starts the heartbeat/reconciliation loop in a daemon thread."""
    thread = threading.Thread(target=heartbeat_loop, args=(cameras,), daemon=True)
    thread.start()
    return thread
