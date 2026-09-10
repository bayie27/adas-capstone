"""Shared frame-materialisation helper. Needed properly in Phase 2 (accident
snapshots must go through here so they never depend on which reader is
running — see AI_ENGINE_GPU_INTEGRATION_PLAN.md section 7.1) but introduced
now so both readers already agree on the contract.
"""


def to_bgr(frame):
    """Materialise an operator-facing BGR image from whatever a reader
    produced.

    The software reader (camera.py) already produces a BGR ndarray, so this
    is identity for it. The GPU reader (gpu_camera.py) produces a device-
    resident NV12 tensor that has no BGR form yet; Phase 2 adds the on-demand
    conversion here, off the hot path, because accidents are rare relative to
    the per-frame loop and converting every frame would reintroduce the
    full-resolution CPU cost this work exists to remove.
    """
    import numpy as np

    if isinstance(frame, np.ndarray):
        return frame
    raise NotImplementedError(
        "GPU-resident frame -> BGR conversion is Phase 2 work "
        "(AI_ENGINE_GPU_INTEGRATION_PLAN.md section 7.1); accident.py does "
        "not call this yet."
    )
