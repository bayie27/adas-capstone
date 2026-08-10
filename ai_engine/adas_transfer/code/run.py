"""Run the detector + accumulator over a video and emit detection events.

Per frame: detect `accident` boxes at a deliberately LOW confidence, then let the accumulator
supply precision through persistence. That split is the point — recall comes from the low
threshold, precision from evidence over time, and neither from a tracker.

GRAYSCALE IS MANDATORY AND MUST MATCH TRAINING. Frames are converted to grayscale and
replicated back to 3 channels before inference. The training set pairs a 100%-grayscale
accident source (nyanko) against a 98%-colour vehicle source (BMD-45), so unless every image
is forced to grayscale the cheapest available rule is "colour => vehicle, grayscale =>
accident" — which on colour Lipa footage means the model never fires. Graying only the
training set and not inference (or the reverse) just swaps one domain mismatch for another.
`--color` exists to demonstrate the failure, not to run the system.

Usage:
    prototype/.venv/Scripts/python.exe detect/run.py --video prototype/samples/car_car.mp4 \
        --weights runs/train/weights/best.pt
    ... --show          # live window
    ... --events out.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

import cv2

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from accumulate import Accumulator  # noqa: E402
from sources import FrameSource  # noqa: E402

ACCIDENT_CLS = 0


def to_gray(frame):
    """BGR -> grayscale, replicated back to 3 channels (the COCO-pretrained stem expects 3)."""
    return cv2.cvtColor(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), cv2.COLOR_GRAY2BGR)


FONT = cv2.FONT_HERSHEY_SIMPLEX


def _label(img, text, org, colour, scale=0.6, thick=2):
    """Text with a dark outline so it stays readable over any footage."""
    cv2.putText(img, text, org, FONT, scale, (0, 0, 0), thick + 3, cv2.LINE_AA)
    cv2.putText(img, text, org, FONT, scale, colour, thick, cv2.LINE_AA)


def annotate(canvas, t, boxes, confs, regions, threshold, fps_now, since_event, gray_input):
    """Draw detections, accumulator progress, and a HUD onto `canvas` in place."""
    h, w = canvas.shape[:2]
    s = w / 1280.0                                   # scale text with resolution

    for b, cf in zip(boxes, confs):
        x1, y1, x2, y2 = (int(v) for v in b)
        cv2.rectangle(canvas, (x1, y1), (x2, y2), (0, 165, 255), max(1, int(2 * s)))
        _label(canvas, f"{cf:.2f}", (x1, max(18, y1 - 6)), (0, 165, 255), 0.6 * s, max(1, int(2 * s)))

    # Evidence still accumulating - the part that explains WHY it fires when it does.
    for reg in regions:
        x1, y1, x2, y2 = (int(v) for v in reg.box)
        frac = min(1.0, reg.score / threshold) if threshold > 0 else 0.0
        if reg.fired:
            cv2.rectangle(canvas, (x1, y1), (x2, y2), (0, 0, 255), max(2, int(4 * s)))
            _label(canvas, "ACCIDENT", (x1, min(h - 8, y2 + int(26 * s))), (0, 0, 255),
                   0.8 * s, max(2, int(2 * s)))
        else:
            bw = x2 - x1
            by = min(h - 4, y2 + int(8 * s))
            cv2.rectangle(canvas, (x1, by), (x1 + bw, by + int(8 * s)), (60, 60, 60), -1)
            cv2.rectangle(canvas, (x1, by), (x1 + int(bw * frac), by + int(8 * s)),
                          (0, 215, 255), -1)

    # Banner first, then the HUD beneath it - otherwise the banner covers the clock.
    top = 0
    if since_event is not None and since_event < 3.0:
        top = int(72 * s)
        cv2.rectangle(canvas, (0, 0), (w, top), (0, 0, 200), -1)
        _label(canvas, f"DETECTION  t = {t - since_event:.2f}s", (int(w * 0.28), int(50 * s)),
               (255, 255, 255), 1.1 * s, max(2, int(3 * s)))

    _label(canvas, f"t = {t:5.2f}s", (12, top + int(30 * s)), (255, 255, 255), 0.8 * s,
           max(1, int(2 * s)))
    _label(canvas, f"{fps_now:.1f} FPS   model input: {'grayscale' if gray_input else 'colour'}",
           (12, top + int(56 * s)), (200, 200, 200), 0.55 * s, max(1, int(1 * s)))
    return canvas


def main() -> None:
    ap = argparse.ArgumentParser(description="Detect accidents in a video or a live stream.")
    ap.add_argument("--source", default=None,
                    help="video file path OR a live stream URL (rtsp://..., http://...)")
    # Kept as an alias, not deprecated: eval/run_clips.py, eval/sweep.py and every command in
    # CLAUDE.md pass --video. Renaming it would break the evaluation harness.
    ap.add_argument("--video", default=None, help="alias for --source")
    ap.add_argument("--weights", required=True)
    ap.add_argument("--conf", type=float, default=0.15)
    # 640 matches the training resolution. The 640/960/1280 sweep found 640 and 960 identical
    # (4/5 recall, 2 FPs) and 1280 worse (5 FPs), so 960 bought nothing while feeding the model
    # objects ~1.5x larger than anything it trained on. The old 960 default was inherited from
    # the deleted tracking prototype, where losing distant vehicles broke track IDs.
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--device", default=0)
    ap.add_argument("--threshold", type=float, default=1.0, help="accumulator fire threshold")
    ap.add_argument("--decay", type=float, default=0.3)
    ap.add_argument("--iou-link", type=float, default=0.30)
    ap.add_argument("--cooldown", type=float, default=60.0)
    ap.add_argument("--show", action="store_true")
    ap.add_argument("--events", default=None, help="write events JSON here")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--color", action="store_true",
                    help="feed colour frames - MISMATCHES the grayscale training set, "
                         "for demonstrating the failure only")
    ap.add_argument("--save-video", default=None,
                    help="write the annotated video here (mp4). Safer than a live demo.")
    ap.add_argument("--display-gray", action="store_true",
                    help="draw on the grayscale frame the model actually sees, not the colour one")
    ap.add_argument("--realtime", action="store_true",
                    help="pace playback to the source frame rate instead of running flat out")
    args = ap.parse_args()

    from ultralytics import YOLO

    source = args.source or args.video
    if not source:
        ap.error("give --source (a file path or a stream URL); --video is an alias")

    model = YOLO(args.weights)
    # `realtime` is deliberately NOT passed through: --realtime is implemented below via
    # cv2.waitKey inside the --show branch, exactly as it was before sources.py existed.
    # Pacing in both places would double-sleep and halve the playback rate.
    src = FrameSource(source)
    fps = src.fps
    acc = Accumulator(iou_link=args.iou_link, threshold=args.threshold,
                      decay=args.decay, cooldown_s=args.cooldown)
    stop = {"now": False}
    if src.stream:
        print(f"[info] live stream: {source} - t is wall-clock seconds, and a reconnect RESETS "
              "the accumulator", flush=True)
        # A stream never ends, so without this Ctrl-C kills the process before the events file is
        # written and the whole session is lost. Installed ONLY for streams: on a file run this
        # would silently turn an interrupted evaluation into a short-but-complete-looking events
        # file, and eval/score.py would score it without knowing. Files keep the old behaviour.
        import signal

        def _on_sigint(_sig, _frm):
            stop["now"] = True
            print("\n[info] stopping - writing events before exit", flush=True)

        signal.signal(signal.SIGINT, _on_sigint)

    events, t0, n_frames = [], time.time(), 0
    writer, last_ev_t, frame_t = None, None, time.time()
    for frame, t, new_segment in src:
        if stop["now"]:
            break
        n_frames += 1
        if new_segment:
            # Reconnected after an outage. dt across the gap would be huge, and the accumulator
            # integrates conf * dt, so a single detection could clear the threshold instantly and
            # turn a network blip into an accident alert. Start clean instead.
            acc.reset()
            print(f"[info] stream reconnected at t={t:.1f}s - accumulator reset", flush=True)
        # The model always sees grayscale (see docstring); `frame` stays colour for display,
        # so the demo is legible to a human without changing what the detector is fed.
        net_in = frame if args.color else to_gray(frame)
        r = model.predict(net_in, conf=args.conf, imgsz=args.imgsz, device=args.device,
                          verbose=False)[0]
        boxes, confs = [], []
        if r.boxes is not None:
            for b, c, cf in zip(r.boxes.xyxy.tolist(), r.boxes.cls.int().tolist(),
                                r.boxes.conf.tolist()):
                if int(c) == ACCIDENT_CLS:
                    boxes.append(tuple(b))
                    confs.append(float(cf))
        for ev in acc.update(t, boxes, confs):
            events.append({"t": round(ev.t, 2), "box": [round(v, 1) for v in ev.box],
                           "score": ev.score, "peak_conf": ev.peak_conf, "age_s": ev.age_s})
            last_ev_t = ev.t
            if not args.quiet:
                print(f"[DETECTION] t={ev.t:.2f}s score={ev.score} peak_conf={ev.peak_conf}",
                      flush=True)

        if args.show or args.save_video:
            now = time.time()
            fps_now = 1.0 / max(now - frame_t, 1e-6)
            frame_t = now
            canvas = annotate((net_in if args.display_gray else frame).copy(), t, boxes, confs,
                              acc.regions, args.threshold, fps_now,
                              None if last_ev_t is None else t - last_ev_t, not args.color)
            if args.save_video:
                if writer is None:
                    os.makedirs(os.path.dirname(os.path.abspath(args.save_video)), exist_ok=True)
                    h, w = canvas.shape[:2]
                    writer = cv2.VideoWriter(args.save_video,
                                             cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
                    if not writer.isOpened():
                        print(f"[error] could not open {args.save_video} for writing")
                        raise SystemExit(1)
                writer.write(canvas)
            if args.show:
                cv2.imshow("ADAS detection  (q = quit)", canvas)
                wait = 1
                if args.realtime:
                    wait = max(1, int(1000.0 / fps - (time.time() - now) * 1000.0))
                if (cv2.waitKey(wait) & 0xFF) == ord("q"):
                    break
    src.release()
    if writer is not None:
        writer.release()
        print(f"[info] annotated video -> {args.save_video}")
    if args.show:
        cv2.destroyAllWindows()

    el = time.time() - t0
    if not args.quiet:
        print(f"[info] {os.path.basename(str(source))}  frames={n_frames}  "
              f"{n_frames/max(el,1e-6):.1f} FPS  events={len(events)}")
    if args.events:
        # `frames` and `fps` are load-bearing, not decoration: eval/score.py derives each clip's
        # duration from them, and that duration is the denominator of FP/min.
        payload = {"video": os.path.basename(str(source)), "fps": fps,
                   "frames": n_frames, "gray": not args.color, "conf": args.conf,
                   "imgsz": args.imgsz, "events": events}
        if src.stream:
            # A stream's `frames`/`fps` do NOT describe a fixed duration the way a file's do, so
            # anything deriving a clip length from them (eval/score.py) would be wrong. Say so in
            # the file rather than letting it look like a clip result.
            payload["source"] = "stream"
            payload["interrupted"] = stop["now"]
        json.dump(payload,
                  open(args.events, "w", encoding="utf-8"), indent=1)


if __name__ == "__main__":
    main()
