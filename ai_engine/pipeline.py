"""Fixed-cadence batched multi-camera scheduling, and the accumulator
lifecycle that makes SPEC.md section 6's fired-region defect harmless.

Pure module: no cv2, no ultralytics. `detector` and the camera objects are
collaborators passed in, so this whole file is testable in CI with fakes.
That mirrors supervisor.py, where compute_actions() is a side-effect-free
decision and only _apply_actions() touches streams.
"""

import logging
import time

import config
from accumulate import Accumulator

logger = logging.getLogger("ai_engine")


def target_fps(capacity: int, active_count: int) -> float:
    """Pick a per-camera frame rate inside the paper's 10-15 FPS band.

    Per-camera frame rate is the FIXED quantity and camera count the free
    one. Letting cadence sag as cameras are added would degrade detection
    for every camera at once, invisibly — the failure mode hardest to
    notice and hardest to explain afterwards.
    """
    if active_count <= capacity:
        return config.FPS_BAND_MAX
    return config.FPS_BAND_MIN


class AccumulatorRegistry:
    """One Accumulator per camera, reset whenever its stream discontinues.

    SPEC.md section 6: a fired region is retained forever and keeps
    absorbing detections at that location, so the place goes permanently
    deaf and `regions` grows without bound. Rather than edit accumulate.py
    (which would invalidate every measurement in SPEC.md section 4), the
    engine resets at the three integration seams — reconnect, resume after
    the self-blindfold, and stream restart — all of which increment the
    stream's segment_id.
    """

    def __init__(self):
        self._entries: dict[int, tuple[object, Accumulator, int]] = {}

    def resolve(self, camera_id: int, stream, segment_id: int) -> Accumulator:
        entry = self._entries.get(camera_id)
        if entry is not None:
            known_stream, accumulator, known_segment = entry
            # The identity check catches a REAPPLY_CONFIG restart, whose new
            # CameraStream starts at segment 0 and would otherwise look
            # unchanged.
            if known_stream is stream and known_segment == segment_id:
                return accumulator

        accumulator = Accumulator(
            iou_link=config.ACC_IOU_LINK,
            threshold=config.ACC_THRESHOLD,
            decay=config.ACC_DECAY,
            ema=config.ACC_EMA,
        )
        self._entries[camera_id] = (stream, accumulator, segment_id)
        return accumulator

    def prune(self, live_camera_ids) -> None:
        live = set(live_camera_ids)
        for camera_id in list(self._entries):
            if camera_id not in live:
                del self._entries[camera_id]

    def camera_ids(self):
        return list(self._entries)


class InferencePipeline:
    """The tick loop. One batched forward pass per tick over the newest
    frame from every eligible camera.
    """

    def __init__(self, cameras: dict, detector, on_event, *, capacity: int):
        self.cameras = cameras
        self.detector = detector
        self.on_event = on_event
        self.capacity = capacity
        self.registry = AccumulatorRegistry()
        self.degraded = False
        self.last_batch_latency_ms: float | None = None
        self._isolated: set[int] = set()
        self._running = False

    # -- collection -------------------------------------------------------

    def _collect(self):
        """Newest frame from every eligible camera. Returns (camera, read)
        pairs in a stable order."""
        collected = []
        now = time.monotonic()
        for camera in list(self.cameras.values()):
            if camera.is_paused or camera.camera_id in self._isolated:
                continue
            read = camera.read()
            if read is None:
                continue
            if now - read.t > config.MAX_FRAME_AGE_SECONDS:
                # Connected but stalled. Skip rather than treat an old frame
                # as current.
                continue
            collected.append((camera, read))
        return collected

    # -- inference --------------------------------------------------------

    def _infer(self, collected):
        """Batched predict, falling back to per-frame isolation on failure.

        TC-R-302 requires that a fatal error in one camera's AI processing
        leave the others running. A shared inference thread does not give
        that for free, so a failing batch is re-run frame by frame to find
        the culprit.
        """
        self.last_batch_latency_ms = None
        frames = [read.frame for _, read in collected]
        started = time.perf_counter()
        try:
            detections = self.detector.predict_batch(frames)
            self.last_batch_latency_ms = (time.perf_counter() - started) * 1000
            return list(zip(collected, detections, strict=True))
        except Exception:
            logger.exception("Batched inference failed; isolating by re-run")

        paired = []
        for camera, read in collected:
            try:
                detections = self.detector.predict_batch([read.frame])
            except Exception:
                logger.exception(
                    "Inference failed for camera %s; excluding it", camera.camera_id
                )
                camera.error_code = "INFERENCE_FAILED"
                camera.error_message = "Inference raised on this camera's frame"
                self._isolated.add(camera.camera_id)
                continue
            paired.append(((camera, read), detections[0]))
        return paired

    # -- tick -------------------------------------------------------------

    def tick_once(self) -> None:
        self.registry.prune(self.cameras.keys())

        collected = self._collect()
        if not collected:
            return

        self.degraded = len(collected) > self.capacity

        inferred = self._infer(collected)

        if self.last_batch_latency_ms is not None and collected:
            # TC-AI-401 budgets "under 100 ms per FRAME". Reporting whole-batch
            # latency to every camera overstates per-frame cost by exactly the
            # batch size, so the system would fail a criterion it meets.
            per_camera = self.last_batch_latency_ms / len(collected)
            for camera, _ in collected:
                camera.inference_latency_ms = per_camera

        for (camera, read), detection in inferred:
            accumulator = self.registry.resolve(
                camera.camera_id, camera, read.segment_id
            )
            events = accumulator.update(read.t, detection.boxes, detection.confs)
            if not events:
                continue

            # One incident per camera per tick. On a clip several events mean
            # several distinct places; live, the camera pauses on the first,
            # so one incident per pause cycle is the right semantics.
            best = max(events, key=lambda e: e.peak_conf)
            if len(events) > 1:
                logger.info(
                    "Camera %s produced %d simultaneous events; reporting the "
                    "highest-confidence one",
                    camera.camera_id,
                    len(events),
                )

            # The self-blindfold, before any disk or network work.
            camera.pause()
            self.on_event(camera, read.frame, best)

    # -- loop -------------------------------------------------------------

    def run(self) -> None:
        self._running = True
        next_tick = time.monotonic()
        while self._running:
            active = sum(
                1
                for c in list(self.cameras.values())
                if not c.is_paused and c.camera_id not in self._isolated
            )
            period = 1.0 / target_fps(self.capacity, active)

            self.tick_once()

            next_tick += period
            sleep_for = next_tick - time.monotonic()
            if sleep_for > 0:
                time.sleep(sleep_for)
            else:
                # Overran the budget. Slip rather than accumulate backlog.
                next_tick = time.monotonic()

    def stop(self) -> None:
        self._running = False
