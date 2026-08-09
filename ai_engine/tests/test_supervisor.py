"""compute_actions() is a pure decision function with no cv2 import — see
supervisor.py's module docstring. Importing `supervisor` here does not
require the `ai` extra.
"""

import supervisor
from supervisor import Action, ReconcileAction


def _snap(camera_id, **overrides):
    base = {
        "camera_id": camera_id,
        "channel_id": camera_id,
        "camera_name": f"Camera {camera_id}",
        "rtsp_url": f"rtsp://backend/channel{camera_id}",
        "is_enabled": True,
        "desired_ai_state": "Active",
        "desired_state_reason": None,
        "cooldown_until": None,
        "config_version": 1,
    }
    base.update(overrides)
    return base


def _local(**overrides):
    base = {
        "is_paused": False,
        "applied_config_version": 1,
        "rtsp_url": "rtsp://backend/channel1",
        "channel_id": 1,
    }
    base.update(overrides)
    return base


def test_disabled_camera_is_not_started():
    snapshot = [_snap(1, is_enabled=False)]
    assert supervisor.compute_actions(snapshot, {}) == []


def test_inactive_desired_state_camera_is_not_started():
    snapshot = [_snap(1, desired_ai_state="Inactive")]
    assert supervisor.compute_actions(snapshot, {}) == []


def test_camera_absent_from_snapshot_is_stopped():
    local = {1: _local()}
    actions = supervisor.compute_actions([], local)
    assert actions == [ReconcileAction(1, Action.STOP)]


def test_disabled_local_camera_is_stopped():
    snapshot = [_snap(1, is_enabled=False)]
    local = {1: _local()}
    actions = supervisor.compute_actions(snapshot, local)
    assert actions == [ReconcileAction(1, Action.STOP)]


def test_missing_enabled_active_camera_is_started():
    snap = _snap(1)
    actions = supervisor.compute_actions([snap], {})
    assert actions == [ReconcileAction(1, Action.START, snap)]


def test_paused_desired_state_pauses_a_running_camera():
    snap = _snap(1, desired_ai_state="Paused")
    local = {1: _local(is_paused=False)}
    actions = supervisor.compute_actions([snap], local)
    assert actions == [ReconcileAction(1, Action.PAUSE)]


def test_already_paused_camera_gets_no_duplicate_pause():
    snap = _snap(1, desired_ai_state="Paused")
    local = {1: _local(is_paused=True)}
    actions = supervisor.compute_actions([snap], local)
    assert actions == []


def test_active_desired_state_resumes_a_paused_camera():
    snap = _snap(1, desired_ai_state="Active")
    local = {1: _local(is_paused=True)}
    actions = supervisor.compute_actions([snap], local)
    assert actions == [ReconcileAction(1, Action.RESUME)]


def test_newer_config_version_without_stream_change_updates_only():
    snap = _snap(1, config_version=2)
    local = {1: _local(applied_config_version=1)}
    actions = supervisor.compute_actions([snap], local)
    assert actions == [ReconcileAction(1, Action.UPDATE_CONFIG, snap)]


def test_newer_config_version_with_channel_change_triggers_reapply():
    snap = _snap(
        1, config_version=2, channel_id=99, rtsp_url="rtsp://backend/channel99"
    )
    local = {
        1: _local(
            applied_config_version=1, channel_id=1, rtsp_url="rtsp://backend/channel1"
        )
    }
    actions = supervisor.compute_actions([snap], local)
    assert actions == [ReconcileAction(1, Action.REAPPLY_CONFIG, snap)]


def test_same_config_version_and_state_is_a_no_op():
    snap = _snap(1)
    local = {1: _local()}
    assert supervisor.compute_actions([snap], local) == []


def test_zero_cameras_registered_yields_no_actions():
    assert supervisor.compute_actions([], {}) == []
