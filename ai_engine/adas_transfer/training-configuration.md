# Training configuration — verified reference

**Purpose.** This file exists to be copied into `adas-capstone` (or any other consumer of this
project, including the capstone paper) as ground truth for how the deployed detector was actually
trained. Every claim below is sourced to a line in this repo — mostly
[`train/adas_train_colab.ipynb`](../train/adas_train_colab.ipynb), the single notebook that
trained both `weights_v2` and `weights_v3`. It exists because the capstone paper drifted from the
code in at least two places (an augmentation list that named "cropping" and "contrast", neither of
which the training call uses; and an annotation-methodology sentence that claimed manual
bounding-box work nothing in the pipeline actually does). Treat every number here as the correction
source for those kinds of drift, and re-derive from the notebook rather than copying this file
forward blindly if the notebook ever changes.

**Do not restate any of this from memory in another document.** If the notebook changes, this file
goes stale silently — re-grep it before trusting a number here past its next training run.

---

## 1. Model

- **Architecture: YOLO26n** (`yolo26n.pt`, COCO-pretrained, nano). Requires `ultralytics >= 8.4`;
  older versions fail to load the architecture at all rather than degrading gracefully.
- **2 classes, only 1 is alerted on:**
  - `0 accident` — the crash and its immediate aftermath. This is the only class the system fires
    an alert on.
  - `1 vehicle` — ordinary cars/motorcycles/buses/trucks/tricycles/jeepneys. A discriminative foil,
    discarded at inference. It exists so a normal vehicle has somewhere to go other than
    `background` or `accident`; without it, "car" and "accident" entangle under single-class
    training because almost every accident image is full of vehicles. This is what happened to
    `accident_detection.pt` (see `CLAUDE.md`).
- **Deployed weights:** `models/weights_v3/epoch50.pt`. Selected by `eval/sweep.py` scoring every
  checkpoint from the run against the labelled Lipa clips — **never by the `best.pt` label**, which
  has lost to a numbered epoch checkpoint on all three runs measured so far (same recall, more false
  positives).

## 2. Input pipeline

- **`imgsz=640`.** Swept against 960 and 1280 on real Lipa footage; recall was identical at all
  three and 1280 was *worse* on false positives. 640 also matches the training resolution.
- **Forced grayscale, at training AND at inference — this is load-bearing, not aesthetic.** The
  accident source (nyanko) is 100% grayscale; the vehicle source (BMD-45) is ~98% colour. Left
  alone, the cheapest rule available to the model is `colour ⇒ vehicle, grayscale ⇒ accident`,
  which would make it silent on colour Lipa CCTV footage. Both sides are greyed and replicated back
  to 3 channels (the COCO-pretrained stem expects 3 channels) so the domains match. `detect/run.py`
  greys every inference frame the same way; there is a `--color` flag but it exists only to
  demonstrate the failure mode, not to run the system.
- **Do not describe this as "colour input with heavy random-grayscale augmentation."** An earlier
  draft of this project's own docs claimed that, and it was never what the code does — see §3.

## 3. Augmentation — the actual `model.train()` call

This is the literal training call from `train/adas_train_colab.ipynb`, reused unchanged between the
v2 and v3 (Philippine vehicle-foil) runs:

```python
model = YOLO('yolo26n.pt')
results = model.train(
    data=f'{DST}/data.yaml',
    epochs=3 if globals().get('SMOKE') else 60, imgsz=640, batch=64, device=0, workers=2,
    patience=15, cache=False, seed=0, save_period=10,
    project=f'{DRIVE}/adas_runs', name=RUN_NAME, exist_ok=True,
    hsv_s=0.0, hsv_v=0.4, fliplr=0.5, flipud=0.0,
    degrees=5.0, translate=0.1, scale=0.9, mosaic=1.0, close_mosaic=10,
    erasing=0.4,
)
```

Real run: `epochs=60`, `batch=64`, `imgsz=640`, `patience=15` (early-stop), `seed=0`.

| Augmentation | Value | What it does | Verified? |
|---|---|---|---|
| `mosaic` | 1.0 | Composites 4 training images into one — the only technique both paper sections agreed on. `close_mosaic=10` turns it off for the last 10 epochs (standard Ultralytics practice, stabilizes late training). | ✅ |
| `hsv_v` | 0.4 | Random brightness (HSV *value* channel) jitter, ±40%. This is what "brightness adjustment" in the paper should point to. | ✅ |
| `hsv_s` | **0.0** | Saturation jitter — deliberately disabled. On grayscale input, scaling zero saturation is a no-op; set to 0 explicitly "to say so honestly" rather than leaving a misleading nonzero default. | ✅ (explicitly off) |
| `degrees` | 5.0 | Random rotation, ±5°. Small — enough to cover minor camera-mount variance, not enough to simulate arbitrary viewing angles. | ✅ |
| `translate` | 0.1 | Random translation, ±10% of image size. | ✅ |
| `scale` | 0.9 | Random scale jitter. The closest thing to "cropping/zooming" that actually runs — but it is scale jitter, not a discrete crop operation, and the paper should not call it "cropping." | ✅ (as scale jitter, not crop) |
| `fliplr` | 0.5 | Horizontal flip, 50% of images. | ✅ |
| `flipud` | 0.0 | Vertical flip — off. CCTV footage has a fixed up/down orientation; flipping it vertically would create physically impossible frames. | ✅ (explicitly off) |
| `erasing` | 0.4 | Random erasing/cutout, 40% probability. | ✅ |

**What is NOT verified or NOT used, despite appearing in some draft of the paper:**

- **"Contrast" adjustment** — not a native Ultralytics hyperparameter in this call. The only path
  by which contrast-style augmentation could enter training is Ultralytics' *optional*
  albumentations integration (`A.RandomBrightnessContrast`-style transforms), which is skipped
  entirely if the `albumentations` package isn't installed in the Colab environment, and even when
  present applies at low probability. The notebook's own comment (directly above the training
  call) flags that an earlier draft overclaimed here and says explicitly: verify via the
  environment-probe cell, don't assume. **Do not write "contrast adjustment" as a training claim
  without checking that cell's printed output for the run in question.**
- **"Cropping" as a distinct augmentation** — no such parameter is passed. `scale`/`translate`
  jitter and mosaic's own tile-compositing are the closest analogues, but neither is a discrete
  crop step, and describing them as "cropping" overstates precision about what's happening.

## 4. Data sources and how they were combined

| Source | Role | Size | Provenance |
|---|---|---|---|
| **nyanko** (`enjeys-workspace/vehicle-accident-m2ryw-qqdie`) | accident + some vehicle | Roboflow fork, downloaded fresh inside Colab each run | Pre-annotated by original creators; heterogeneous (contains AI-generated crash images, Sri Lankan road photos, PASCAL VOC files, some duplicates) — see `CLAUDE.md` "nyanko contains AI-generated accident images." |
| **BMD-45** | vehicle only, zero accidents | 35,792 images per annotation file (5,000 local subset; full set pulled from HuggingFace in Colab) | Ships with its own COCO annotations. 1920×1080, 0% low-light, 46% two-wheeler / 18% three-wheeler. |
| **`traffic-vehicle-detection-e6kgi`** | vehicle only (Philippine foil) | 776 images, ~10,000 instances | Roboflow Universe, CC BY 4.0, forked into `enjeys-workspace`. Elevated fixed CCTV, tricycle-dominant, daytime only. |
| **`kent-rafiel/vehicle-5kcdl`** | vehicle only (Philippine foil) | 688 images | Roboflow Universe, CC BY 4.0, forked into `enjeys-workspace`. Real jeepneys, ~50% night. |

**None of these arrive as raw/unannotated images.** Every source is pre-annotated by its original
creators (or, for nyanko's bystander-vehicle gap, patched by an automated pseudo-labeling step —
see §5). There is no manual bounding-box drawing anywhere in this pipeline.

### Class collapsing

[`dataset/collapse_classes.py`](../dataset/collapse_classes.py) programmatically remaps every
source's original class names onto the 2-class scheme via a `classify()` function, matching against
a `VEHICLE_WORDS` substring list plus a `VEHICLE_EXACT` set for short tokens (`uv`, `suv`, `lcv`,
…) and negation markers (`no-accident`, `Non Accident`, `NoAcciednt` — a real typo seen in public
data) that must be dropped rather than kept. **This is remapping of existing labels, not new
annotation.** It has one documented historical bug worth keeping in institutional memory: it used
to silently drop `tricycle` and `jeepney` (no matching word in `VEHICLE_WORDS`), which would have
silently discarded the majority class of the Philippine vehicle-foil datasets. Fixed 2026-08-09,
verified against 59 cases. **Any new dataset must have its class list run through `classify()`
before import** — a dropped class produces no error, just vanishes.

### Quality gating

[`dataset/check_cooccurrence.py`](../dataset/check_cooccurrence.py) — checks whether accident
images also carry vehicle boxes for the bystander vehicles in frame. If they systematically don't,
merging with BMD-45 (which boxes every vehicle) teaches the model `crash scene ⇒ suppress vehicle`,
which is the opposite of what the `vehicle` foil is for.

- Pre-registered thresholds: ≤25% bare accident images → OK; 25–60% → borderline; >60% →
  **SYSTEMATIC**, must fix before training.
- **Run on nyanko, returned SYSTEMATIC.** Fix applied: pseudo-label bystander vehicles using the
  COCO-pretrained `yolo26s.pt` (COCO has car/motorcycle/bus/truck/bicycle), at high confidence
  (~0.4+, favouring precision since a wrong pseudo-box is injected noise), dropping any pseudo-box
  that overlaps an existing accident box (IoU > ~0.2) so crashed vehicles are never double-labelled
  as `vehicle`. Implemented in the notebook's pseudo-labeling cell, which runs before the
  ratio-capping cell.
- **This gate does NOT apply to, and was never run on, the Philippine vehicle-foil sources**
  (`e6kgi`, `vehicle-5kcdl`) — they contain no accident images, so the script exits with "no
  accident images at all" if pointed at them. An earlier version of this project's own docs
  incorrectly listed it as a pre-flight step for that data; that was a misreading.

### Class-imbalance capping (the 8:1 ratio)

Uncapped, vehicle:accident is roughly 70:1 — enough to train the model toward silence, the worst
failure direction for a recall-first system. `reserve_quota_ph()` (mirrored between
`dataset/pipeline.py` and the notebook) caps the **vehicle** budget at `ratio=8.0` vehicle boxes per
accident box, and splits that vehicle budget three ways:

- `bmd_share=0.5` — up to half the vehicle budget from BMD-45
- `ph_share=0.25` — up to a quarter from the Philippine sets (`e6kgi` + `vehicle-5kcdl`)
- the remainder from nyanko's own vehicle-only images and pseudo-labelled bystander boxes

**The Philippine sets DISPLACE budget already earmarked for BMD-45/nyanko — they do not add on
top.** Appending them instead would blow the 8:1 ratio and push the model toward silence. This is a
load-bearing design decision, not an implementation detail — do not "simplify" it back into a
straight append.

## 5. Train/val split

- **Split by incident/clip, never by frame**, for nyanko. Roboflow's native export is a
  **frame-level** split, which lets near-duplicate frames of the same crash sit on both sides of
  train/val — that leakage is what made the earlier `accident_detection.pt` report a meaningless
  mAP50 of 0.986. The notebook has a dedicated "INCIDENT-LEVEL VAL SPLIT" cell that groups images by
  a derived `incident_key()` and holds out whole incidents, with a guard (`20 <= n_groups <=
  0.5 * n_images`) meant to catch a badly-collapsing key before it silently reduces training data to
  ~175 images.
- **⚠️ That guard bounds group COUNT, not group SIZE.** One over-aggressive `incident_key()` match
  can pass the guard while still dumping most of the dataset into one giant group. **On the v3 run,
  this guard tripped and the cell was skipped**, so v3's split fell back to Roboflow's frame-level
  split. **v3's reported validation mAP50 (0.956) is leaked and must never be quoted** — it is
  measuring memorisation of near-duplicate frames, exactly the failure mode that made the original
  `accident_detection.pt` untrustworthy. This is a per-run risk, not a fixed property of the
  pipeline: check the printed guard output ("clean: ... no overlap" vs a skip notice) for whichever
  run's number you're about to cite.
- BMD-45 and the Philippine sets are **not** split by incident — they carry no accidents, so there
  is nothing to hold out whole. They also intentionally share near-duplicate frames of the same
  ~4-8 camera scenes between train and val; this is accepted because they're the foil class and the
  project's real success metric is event-level recall/FP-rate on the fully held-out Lipa clips, not
  their own validation mAP.
- **The 17 Lipa CDRRMO clips are never trained on, under any circumstances.** They are the only
  measurement instrument this project has and are gitignored/irreplaceable.

## 6. Checkpoint selection

**Never trust the `best.pt` label or validation mAP to pick a checkpoint.** Every checkpoint saved
during a run (`save_period=10`) is scored with `eval/sweep.py` against the labelled Lipa clips, and
the checkpoint is chosen on event-level recall + false-positives/minute — not on whatever Ultralytics
decided was "best" internally. `best.pt` has lost to a numbered epoch checkpoint on the last three
runs scored this way.

## 7. Deployed result (for context, not a training-config claim)

`models/weights_v3/epoch50.pt`, adopted 2026-08-10: 80% standard recall, 0% hard-clip recall, 3
genuine false alarms (0.27/min), +3.02s median latency versus onset, silent on the one confirmed
crash-free clip. Full numbers and caveats: [`docs/results.md`](results.md).

## 8. Sources for every claim in this file

- `train/adas_train_colab.ipynb` — the training call (§1, §3), pseudo-labeling cell (§4), incident
  split cell (§5), Drive-mount / `RUN_NAME` guard cell (§1).
- `dataset/collapse_classes.py`, `dataset/check_cooccurrence.py`, `dataset/pipeline.py` — §4.
- `CLAUDE.md` (this repo's root) — cross-checked against all of the above; flagged the historical
  drift in this project's own docs that this file exists to prevent recurring.
- `docs/results.md`, `docs/philippine-vehicle-gap.md` — §7 and the Philippine-source provenance in
  §4.
