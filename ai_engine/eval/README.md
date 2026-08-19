# Evaluation data and inference diagnostic

`labels.csv` identifies the clips used by the evaluation tests. The clips
themselves are intentionally untracked; populate `ai_engine/eval/clips/` from
the project research package when you need to run clip-backed evaluation.

## Capacity diagnostic

```bash
uv run python ai_engine/capacity.py
```

`capacity.py` is a lightweight inference-only sweep. It measures batched model
inference on a blank 1280x720 frame and prints rough estimates for 15 and 10
FPS. Use `--sample-frame <image-or-video>` to include one representative frame
instead of the optimistic blank default, and `--model <path>` to measure a
different model artifact.

It does not start camera streams, MediaMTX, or ffmpeg. It writes no report and
never configures or changes the production AI engine. Decode cost, RTSP
contention, camera resolution, and thread scheduling are outside the estimate,
so do not treat it as a confirmed full-system camera limit.

The sweep warms up every batch size before timing it. If a larger batch fails
(for example, because of an out-of-memory error or a fixed-batch TensorRT
engine), it prints the measurements obtained so far and stops. If the estimate
reaches the largest tested batch, increase `BATCH_SIZES` before treating the
number as an upper bound.

## Reading evaluation results

Report standard and hard recall separately. A blended figure hides which
crashes were winnable. Do not quote validation mAP: this dataset is leaked and
can give a misleadingly high number.
