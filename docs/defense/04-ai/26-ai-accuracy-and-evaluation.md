# 26 — AI accuracy and evaluation

> **One-liner:** The paper’s 85% mAP@0.50 target is met by a qualified validation-split result; the stronger operational evidence is event-level scoring on labelled local clips, where recall is 8/16 overall, 8/10 standard, and 0/6 hard.
> **Panel risk:** high — the panel may hear “95.6%” as field accuracy unless we separate the validation metric from operational event results and state the split limitation plainly.

## 1. What it is

The paper’s Objective 3 sets a minimum mean Average Precision (mAP) of 85% at an
Intersection over Union (IoU) threshold of at least 0.50. It also includes an end-to-end
latency target, covered in Guide 27. This guide focuses on the accuracy clause. [Paper,
Chapter 1, General Objectives; Chapter 1, Table 3, NFR-01]

The tracker records accident mAP@0.50 of 0.956 for `epoch50.pt`. That is above the 0.85
threshold, so the formal validation-split target is met. The tracker calls this a
**qualified validation-split result** and explicitly does not present it as independent
operational detection accuracy. [Tracker, AI Model Validation, AI-VAL-001]

“Qualified” describes the evidence behind the score. The score comes from the recorded
frame-level validation split, and the record discloses incident-level leakage. The split
safeguard did not keep every incident wholly separate between training and validation,
and the original split was unavailable for a fresh rerun. The result meets the stated
benchmark on that split; it does not establish how accurately the system will detect
entirely new operational incidents. [Tracker, AI-VAL-001; Paper, Chapter 3, dataset
preparation and checkpoint selection]

The operational evidence answers a different question: did the complete detection
pipeline emit an event in the labelled window for a crash clip? On the frozen reference
run, the answer was yes for 8 of 16 crash clips: 8/10 standard and 0/6 hard. The clean
footage produced 3 false positives over 11.0 minutes, or 0.27 per minute. These are
project-specific event results, reported with their denominators and limits. [Tracker,
AI Model Validation, AI-VAL-002–004]

Keep the two statements separate when answering the panel:

- **Formal threshold:** 0.956 mAP@0.50 against the 0.85 Objective 3 threshold, recorded
  as a qualified validation-split result.
- **Operational evidence:** event recall of 8/16 overall, with standard and hard results
  split out, plus the measured false-positive rate over the clean observation window.

mAP summarizes frame-level box and class performance on a validation split. Event-level
recall counts labelled crash events for which the running pipeline emitted at least one
alert event in the scoring window. A high split mAP and weaker event recall can coexist
because they use different units and answer different questions.

For claims about what operators experience, the clip-level results are the stronger
ground. The formal target result is reported with its qualification, and the clip-level
outcomes make the hard-scene boundary visible. That is a direct, defensible accuracy
story.

## 2. Where it lives

### In the paper

- **Chapter 1, General Objectives, Objective 3:** minimum 85% mAP at IoU ≥ 0.50.
- **Chapter 1, Table 3, NFR-01 Algorithmic Accuracy:** the system’s stated minimum
  mAP and collision-detection requirement.
- **Chapter 2, “Deep Learning Architectures for Real-Time Traffic Accident Detection”:**
  literature on detection architectures and reported accuracy/latency measures.
- **Chapter 2, “Performance Metrics and Hardware Trade-offs in Edge-Based Computer
  Vision”:** the cited mAP range and the edge-performance rationale for the target.
- **Chapter 3, dataset preparation:** training/validation split procedure and the separate
  labelled Lipa clip set.
- **Chapter 3, “Checkpoint Selection”:** why checkpoint selection uses event-level
  behavior as well as the recorded mAP score.
- **Chapter 3, “Testing and Validation”:** the model-validation method and evidence
  categories. Chapter 4 is the results chapter; use the tracker as the source for the
  recorded AI-VAL outcomes in this guide.

### In the code

- `ai_engine/detector.py:28` converts each frame to grayscale before inference.
- `ai_engine/detector.py:188` runs batched inference; `ai_engine/detector.py:336`
  retains accident-class detections for event formation.
- `ai_engine/accumulate.py:77` updates the per-camera evidence accumulator from
  timestamped boxes and confidences.
- `ai_engine/accumulate.py:87` links detections to spatial regions;
  `ai_engine/accumulate.py:112` decays unsupported evidence and checks whether a region
  should emit an event.
- `ai_engine/eval/run_clips.py:45` reads the clip list from the label file;
  `ai_engine/eval/run_clips.py:105` resolves the full labelled set;
  `ai_engine/eval/run_clips.py:117` runs each clip through its own worker process.
- `ai_engine/eval/run_one_clip.py:104` performs inference on selected frames and
  `ai_engine/eval/run_one_clip.py:111` keeps timestamps on the source clip clock.
- `ai_engine/eval/score.py:127` applies the labelled crash window;
  `ai_engine/eval/score.py:131` counts events outside every crash window as false
  positives; `ai_engine/eval/score.py:136` calculates the clean-footage denominator.
- `ai_engine/eval/score.py:165` derives event recall and
  `ai_engine/eval/score.py:167` derives false positives per clean minute.

## 3. How it works

### Two accuracy views

The tracker records the validation-split result first. The model checkpoint and
configuration are frozen, mAP@0.50 and accident-class metrics are recorded, and the split
composition and incident-leakage limitation are disclosed. The recorded value is
0.956 at epoch 50 for `epoch50.pt`; the tracker notes that the original split could not
be rerun. [Tracker, AI Model Validation, AI-VAL-001]

The separate operational run uses the frozen `epoch50.pt` reference pipeline on the
labelled clip corpus without retuning. The detector processes each clip and the temporal
evidence accumulator turns recurring, spatially related accident detections into emitted
events. This means the measured result includes preprocessing, class filtering, and event
formation, rather than scoring isolated bounding boxes alone. [Tracker, AI-VAL-002;
`ai_engine/detector.py:188`; `ai_engine/accumulate.py:77`]

A labelled crash is a hit when one or more emitted events fall in the fixed window from
2 seconds before labelled onset through 15 seconds after labelled end. No event in that
window is a miss. Events outside all crash windows count as false positives. Clean footage
includes the declared negative clip and the ordinary portions of crash clips. [Tracker,
AI Model Validation, AI-VAL-002–004; `ai_engine/eval/score.py:127`;
`ai_engine/eval/score.py:131`]

The run therefore reports more than one aggregate percentage. It retains per-clip
hit/miss outcomes, separates standard and hard crashes, counts false positives, and shows
the clean footage duration behind the rate. The 17-clip corpus contains 16 crash-labelled
clips and one declared negative clip. [Tracker, AI-VAL-002–004, AI-VAL-007]

### All nine AI model validation cases

The tracker marks each AI-VAL row **Pass**. Read each status with its acceptance criterion:
several cases pass by completing and disclosing a descriptive measurement, not by proving
a pre-set recall, nighttime, false-alarm, or deployment-wide accuracy threshold. No
post-hoc event-recall threshold is invented. [Tracker, AI Model Validation, AI-VAL-001–009]

#### AI-VAL-001 — Validation-split mAP

**Acceptance criterion.** Complete the recorded evaluation at IoU 0.50, report mAP and
class metrics, and disclose split composition and leakage. If the Objective 3 threshold is
applied, record mAP@0.50 ≥ 0.85 as a qualified validation-split result; do not present it
as independent operational detection accuracy.

**Recorded outcome.** Pass. The recorded v3 full-retrain accident mAP@0.50 is 0.956 at
epoch 50. The original split was unavailable for rerun, and frame-level incident leakage
is disclosed. The tracker classifies the result as qualified, not an independent estimate
of operational detection accuracy. [Tracker, AI Model Validation, AI-VAL-001]

#### AI-VAL-002 — Event recall on the labelled clip corpus

**Acceptance criterion.** Run the frozen reference pipeline on all labelled crash clips
without retuning, preserve the per-clip hits and misses, and report aggregate event
recall. Since no event-recall threshold was approved before execution, the rate is
reported descriptively.

**Recorded outcome.** Pass. The completed frozen run processed 17 labelled clips,
including 16 crash clips and the declared negative. Overall crash recall was 8/16 (50%);
standard recall was 8/10 (80%); hard recall was 0/6 (0%). The clean-footage analysis
records 3 false positives over 11.0 clean minutes, or 0.27 false positives per minute.
The negative clip produced 0 events. [Tracker, AI Model Validation, AI-VAL-002]

#### AI-VAL-003 — Standard and hard difficulty strata

**Acceptance criterion.** Report hits, misses, denominators, and visible miss conditions
for the 10 preclassified standard clips and 6 preclassified hard clips. The hard result is
a limitation finding unless a hard-recall minimum was approved before execution.

**Recorded outcome.** Pass. Standard recall was 8/10 (80%); hard recall was 0/6 (0%);
overall recall was 8/16 (50%). Every preclassified hard clip was missed. No hard-recall
minimum had been approved, so the tracker treats this as descriptive evidence and a
limitation, not a failed threshold. [Tracker, AI Model Validation, AI-VAL-003]

The clip notes identify one hard collision as far from the camera; the remaining hard
clips are preclassified difficult cases. The aggregate result does not establish one
shared visual cause for all six misses. The defensible explanation is that the current
system misses every event in this hard stratum, and the set needs broader local hard-scene
evidence for diagnosis. [Tracker, AI-VAL-003; `ai_engine/eval/labels.csv`]

#### AI-VAL-004 — False positives and the negative clip

**Acceptance criterion.** Include clean portions of labelled crash clips and the declared
negative clip; record the false-positive count, clean minutes, rate, and inspection notes.
Without an approved FP/min or negative-footage threshold, treat the result as descriptive.
One negative clip does not establish deployment-wide specificity.

**Recorded outcome.** Pass. The frozen run had 3 false positives over 11.0 clean minutes,
for 0.27 false positives per minute. The airbase negative clip produced 0 events. All
three false positives were inspected and retained in the record. [Tracker, AI Model
Validation, AI-VAL-004; AI-VAL-002]

#### AI-VAL-005 — Checkpoint selection

**Acceptance criterion.** Evaluate all retained checkpoints under the same recorded rule,
compare event recall, false-positive count/rate, and latency, and document why the selected
checkpoint is supported by the evidence.

**Recorded outcome.** Pass. The archival sweep evaluated eight exported v3 checkpoints
with the labelled-clip event harness. `epoch50.pt` matched `best.pt` on recall and produced
3 false positives versus 5 for `best.pt`, so `epoch50.pt` was selected. No fresh checkpoint
sweep was run for this evidence update. [Tracker, AI Model Validation, AI-VAL-005]

#### AI-VAL-006 — Night conditions

**Acceptance criterion.** Report the night subset’s denominator, hits, misses, false
positives, and visible conditions. Limit the conclusion to the tested subset unless a
nighttime acceptance threshold was approved.

**Recorded outcome.** Pass. The archival analysis identifies 8 of 17 clips as night
footage and records night recall as higher than day recall. The exact per-clip night
numerator is not recoverable from the current machine-readable labels. All 3 residual false
positives occurred at night and involved nearby vehicles. No universal nighttime
robustness claim is made. [Tracker, AI Model Validation, AI-VAL-006]

#### AI-VAL-007 — Corpus completeness and source strata

**Acceptance criterion.** Account for every labelled clip and every reported subset, with
hits, misses, false positives, denominators, clean duration, and corpus limitations. Do not
silently exclude clips or generalize the aggregate beyond the tested footage.

**Recorded outcome.** Pass. All 17 clips are accounted for: 16 crash-labelled clips and
one negative. The recorded subsets include standard 8/10, hard 0/6, and standard NVR
exports 7/8. The tracker records source types and corpus limitations; lighting is reported
separately under AI-VAL-006. [Tracker, AI Model Validation, AI-VAL-007]

#### AI-VAL-008 — Deployed-artifact equivalence

**Acceptance criterion.** At the declared operating point, the deployed TensorRT engine
must show no unapproved per-clip recall regression against the frozen reference. Record
false-positive, latency, or numerical drift and its disposition.

**Recorded outcome.** Pass. The archival parity run matched the epoch50 checkpoint’s
hit/miss outcome on all 17 clips. Native-rate TensorRT produced 4 false positives versus
3 for the checkpoint; the same engine sampled at 10 FPS produced 3, matching the
checkpoint. No recall regression was observed; the native-rate false-positive difference
is disclosed. [Tracker, AI Model Validation, AI-VAL-008]

#### AI-VAL-009 — Cadence and source-resolution sensitivity

**Acceptance criterion.** Evaluate cadence and source resolution separately. At every
profile intended for deployment, there must be no unapproved per-clip recall regression;
record any profile-specific loss instead of averaging it away.

**Recorded outcome.** Pass. Reset-aware TensorRT preserved the native hit/miss pattern at
10, 8, 6, 5, and 3 FPS. At 4 FPS it missed `motor-motor-night`; false-positive totals
varied by cadence. At a 720p source profile (640×360), recall fell from 8/16 to 6/16,
losing `dpwh-red-car-motor` and `red-car-motor`. The tracker says source downscaling is
not accuracy-neutral and requires full re-evaluation for any selected profile.
[Tracker, AI Model Validation, AI-VAL-009]

The **Pass** records completion and disclosure under each case’s stated criterion. It does
not turn the 0/6 hard result into success against a hard-recall target, because no such
target was approved; it does not make one negative clip a deployment-wide false-alarm
study; and it does not erase the disclosed TensorRT or resolution effects.

## 4. Why it was built this way

The formal Objective 3 mAP target belongs to frame-level validation. IoU describes how
closely a predicted box overlaps the labelled box; mAP summarizes detection precision
across confidence cutoffs. It is useful for checking model performance on a split, and it
is the measure named by the paper’s threshold. [Paper, Chapter 1, Objective 3; Chapter 1,
Table 3, NFR-01]

The clip-level test measures a different operational unit: a crash event. It includes the
preprocessing, class filtering, and temporal accumulation that must all succeed before an
alert event is emitted. A frame may contain a weak accident box without the full pipeline
emitting an event, so event recall tests the behavior the operator actually receives.
[Tracker, AI-VAL-002–004; `ai_engine/detector.py:202`; `ai_engine/accumulate.py:123`]

The fixed scoring window gives the team one repeatable rule for calling a clip hit or miss.
The clean-footage denominator prevents false-positive counts from being quoted without
showing how much ordinary video was observed. Reporting standard and hard strata prevents
the aggregate from hiding a subset where the model did not emit an event. [Tracker,
AI-VAL-002–004]

Checkpoint selection uses event behavior alongside the frame-level metric because the
checkpoint with the strongest validation score is not necessarily the checkpoint with the
best event/false-alarm trade-off on local labelled footage. Here, epoch50 and `best.pt`
matched on recall, while epoch50 had fewer false positives; that is the tracker’s reason
for selecting it. [Paper, Chapter 3, “Checkpoint Selection”; Tracker, AI-VAL-005]

Artifact-equivalence and profile-sensitivity tests answer whether conversion or operating
conditions change what the operator sees. The parity case shows that hit/miss outcomes
matched while the false-positive count differed at native rate. The sensitivity case shows
that the tested lower-resolution source profile lost two standard detections. These
findings are kept visible by comparing per-clip outcomes instead of only average scores.
[Tracker, AI-VAL-008–009]

For literature context, use the accuracy rows in [Guide 03 — Chapter 2 RRL](../01-paper/03-chapter2-rrl.md).
The paper reports 83.3% mAP for Ahmed et al.’s YOLOv5 system, 82.4% mAP50 for Li et
al.’s YOLOv5n, and 88.7% mAP for Gurusamy et al.’s improved YOLOv5 work. It also reports
YOLO11-AMF mAP50–95 of 66.0% and YOLOv12 mAP@0.5 of 93.8%. These results help place the
formal threshold and qualified split score beside the literature. They use other datasets
and, in some cases, different metrics; they are not direct estimates of ADAS event recall.
[Paper, Chapter 2, “Performance Metrics and Hardware Trade-offs in Edge-Based Computer
Vision”; Chapter 2, “Deep Learning Architectures for Real-Time Traffic Accident Detection”]

## 5. What changed since the 28 April defense

The current defense record gives the team a more complete accuracy account: a qualified
validation-split mAP result, a frozen event-level run with standard and hard denominators,
a clean-footage false-alarm rate, and separate checkpoint, night, artifact-parity, and
profile-sensitivity cases. The current evidence is organized in the tracker’s nine
AI-VAL cases. [Tracker, AI Model Validation, AI-VAL-001–009]

The exact accuracy metric and result shown to the panel on 28 April are
**[UNSOURCED — verify]** from the available authoritative record. Do not invent an
April-versus-current percentage or imply a measured trend. State the current baseline and
its qualification clearly; if asked what was shown before, say the earlier numerical
result needs to be checked against the April defense record.

The current benchmark is the 0.956 qualified validation-split result against the 0.85
Objective 3 target. The current operational evidence is the separate 17-clip event result
and its stratified outcomes. [Paper, Chapter 1, Objective 3; Tracker, AI-VAL-001–009]

## 6. Limits and honest caveats

- The 0.956 mAP@0.50 result is qualified by the recorded split limitation. It meets the
  paper’s validation-split threshold; it is not presented as independent operational
  detection accuracy. The original split could not be rerun. [Tracker, AI-VAL-001]
- Event-level evidence comes from a project-specific clip corpus, not an independent
  post-selection test-set estimate. The record does not establish that every crash clip
  represents a distinct incident. [Tracker, AI-VAL-002, AI-VAL-007]
- The overall event recall is 8/16 (50%). Standard recall is 8/10 (80%); hard recall is
  0/6 (0%). Hard recall is a clear limitation even though no hard-recall acceptance
  threshold had been approved. [Tracker, AI-VAL-002–003]
- The false-positive rate is 0.27/min over 11.0 clean minutes. That observation window
  does not support a shift-long count. Airbase produced no event, but one negative clip
  cannot establish deployment-wide specificity. [Tracker, AI-VAL-002, AI-VAL-004]
- The night analysis covers 8 of 17 clips. It records higher night recall than day recall,
  but no recoverable night numerator; all 3 residual false positives occurred at night
  around nearby vehicles. Do not promise universal 2 a.m. robustness. [Tracker, AI-VAL-006]
- The checkpoint sweep and TensorRT parity evidence are archival results; no fresh sweep
  was run for this evidence update. Native-rate TensorRT had 4 false positives versus 3
  for the reference, while all 17 per-clip hit/miss outcomes matched. [Tracker,
  AI-VAL-005, AI-VAL-008]
- The reported 720p/640×360 source-resolution profile dropped recall from 8/16 to 6/16.
  Downscaling must be re-evaluated as its own profile. Cadence changes also changed false-
  positive totals; 4 FPS missed one clip. [Tracker, AI-VAL-009]
- No measured result in this guide establishes automatic dispatch. The paper describes
  AI alerts as support for a human-in-the-loop workflow; an authorized operator verifies
  the alert. [Paper, Chapter 3, system workflow; Chapter 5, Recommendations]

## 7. Likely panel questions

### “Did you meet your 85% accuracy target?”

Yes. The tracker records 0.956 mAP@0.50 against the paper’s 0.85 target as a qualified
validation-split result. The tracker does not present it as independent operational
detection accuracy; on the labelled clips, event recall was 8/16 overall, including 8/10
standard and 0/6 hard. [Paper, Chapter 1, Objective 3; Tracker, AI-VAL-001–003]

### “What does a qualified validation-split result actually mean?”

It means the 0.956 score was measured on the recorded frame-level validation split, whose
incident-leakage limitation is disclosed. The safeguard to separate whole incidents did
not complete, and the original split was unavailable for rerun. The score meets the stated
split threshold; our local event-level evidence is reported separately. [Tracker,
AI-VAL-001; Paper, Chapter 3, dataset preparation]

### “Is 95.6% really your operational accuracy?”

No. It is the qualified accident mAP@0.50 on the validation split. For operational
behavior we report event recall on labelled local clips: 8/16 overall, with standard and
hard strata shown separately, plus false positives per clean minute. [Tracker,
AI-VAL-001–004]

### “Why is hard-case recall zero?”

All six clips preclassified as hard produced no event inside their scoring windows. The
record identifies a far-camera collision among the difficult cases but does not establish
one shared visual cause for all six. We report 0/6 as the observed limitation and would
expand the hard-scene footage before claiming improvement. [Tracker, AI-VAL-003;
`ai_engine/eval/labels.csv`]

### “Why report recall by difficulty instead of one number?”

The overall 8/16 result alone would hide the difference between 8/10 standard cases and
0/6 hard cases. The difficulty split was set before model execution, and the tracker
requires the denominators and miss conditions to be shown. It makes the boundary of the
current evidence clear. [Tracker, AI-VAL-002–003]

### “How often does it false-alarm in a shift?”

The measured rate is 0.27 false positives per minute over 11.0 clean minutes, including
the negative clip and clean portions of crash clips. That is the observed window, not a
shift-length run, so we do not convert it into a shift-wide forecast. [Tracker,
AI-VAL-002, AI-VAL-004]

### “What does the negative clip prove?”

The declared airbase clip produced 0 events. The tracker includes it in the clean-footage
analysis, but one negative clip does not establish deployment-wide specificity. The
false-alarm rate also includes clean portions of the labelled crash clips. [Tracker,
AI-VAL-004]

### “Would you trust this at 2 a.m.?”

We can say what the tested night subset shows: 8 of 17 clips were labelled night, recorded
night recall exceeded day recall, and all 3 residual false positives occurred at night
around nearby vehicles. The exact night recall numerator is not recoverable, so we do not
claim universal nighttime robustness; alerts remain subject to operator verification.
[Tracker, AI-VAL-006; Paper, Chapter 5, Recommendations]

### “Did TensorRT change the results?”

All 17 clip hit/miss outcomes matched the epoch50 reference. Native-rate TensorRT produced
4 false positives versus 3 for the checkpoint; at 10 FPS, the engine produced 3. We
report the false-positive difference with the parity result. [Tracker, AI-VAL-008]

### “Can you lower the resolution or frame rate to improve capacity?”

The tested 720p source profile reduced event recall from 8/16 to 6/16, so downscaling is
not accuracy-neutral. The cadence run preserved the native hit/miss pattern at 10, 8, 6,
5, and 3 FPS, while 4 FPS missed `motor-motor-night`; each selected profile needs its own
evaluation. [Tracker, AI-VAL-009]

### “How does this compare with the systems in your literature review?”

Guide 03’s comparison table puts our Objective 3 threshold beside reported study metrics:
the paper cites 82.4% mAP50 for YOLOv5n, 83.3% mAP for one YOLOv5 system, and 88.7% mAP
for improved YOLOv5. Our 0.956 result is a qualified validation-split mAP@0.50, while
8/16 is event recall on local clips; compare like measures and state the dataset and
qualification. [Guide 03 — Chapter 2 RRL](../01-paper/03-chapter2-rrl.md); [Paper,
Chapter 2, “Performance Metrics and Hardware Trade-offs in Edge-Based Computer Vision”]

### “Why did you select epoch50 instead of best.pt?”

The archival event-level sweep found equal recall for the two checkpoints, with 3 false
positives for epoch50 and 5 for `best.pt`. The tracker records that comparison as the
selection rationale; no new checkpoint sweep was run for this evidence update. [Tracker,
AI-VAL-005]

## 8. Cram summary

- **Objective 3:** mAP ≥ 0.85 at IoU ≥ 0.50. The tracker records 0.956 mAP@0.50 for
  `epoch50.pt`, meeting the formal threshold as a qualified validation-split result.
- **Say “qualified” plainly:** the recorded split has incident-level leakage disclosed;
  its original version was unavailable for a fresh rerun. This is not independent
  operational detection accuracy.
- **Operational evidence:** event recall is 8/16 overall: 8/10 standard and 0/6 hard.
- **False alarms:** 3 over 11.0 clean minutes, or 0.27/min; the airbase negative clip
  produced 0 events. Do not extrapolate this window to a full shift.
- **Night:** 8/17 clips were night; reported night recall exceeded day recall, but the
  exact night numerator is unavailable and all 3 residual FPs occurred at night near
  other vehicles.
- **Checkpoint:** epoch50 matched `best.pt` recall and had 3 rather than 5 FPs.
- **TensorRT:** all 17 hit/miss outcomes matched; native-rate FP count was 4 versus 3.
- **Profile sensitivity:** 720p/640×360 changed recall from 8/16 to 6/16; 4 FPS missed
  `motor-motor-night`.
- **Literature:** use Guide 03’s comparison table; distinguish mAP, mAP50–95, precision,
  recall, and event-level recall, and name the dataset/qualification.
- **Panel answer:** the Objective 3 split threshold is met; the operational clip results
  show exactly where performance is strong and where the hard-scene limitation remains.
