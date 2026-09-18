---
section: "Chapter 4 — AI Detection Results"
page/s: "pp. 197–205; rendered PDF verified 2026-09-16"
required_revision: "Use strengths-first discussion while preserving event-level results and qualifications."
notes: "Applied to the live ITCAPROJ2 Doc after structural read; Figure 35 was preserved and the affected pages were visually verified."
status: Applied and verified
assigned_to: Daniboy
synced: 2026-09-16
---

## Changes

### 1. Defense paper — Figures 36–38, representative positive-clip evidence

Page/s: pp. 200–202 in the current rendered export; verified 2026-09-16. Page 199 remains an existing blank separator page before Figure 36.

#### Change metadata

Operation: insert and reformat
Scope: figure
Changed target: Figures 36–38 caption/image/source blocks at native range 254905–255633 in tab t.y7ms6bhlk4qn
Preserve: the existing Figure 35 chart and source attribution, the preceding event-level interpretation paragraph, the mAP and event-level result paragraphs, and Tables 26–27
Comment target: no standalone comment proposed for this analysis-only review

#### Applied revision

The existing Figure 35 chart was retained. Figures 36 and 37 present the standard-condition clips in two readable collages, and Figure 38 presents the six hard-condition clips. The captions and source notes identify the labelled CCTV corpus and the pre-execution hard-condition classification. The later SUS chart remains Figure 39.

#### Figure contents

The collages use unaltered frames from the project-labelled Lipa CDRRMO CCTV clip corpus, selected at the labelled onset plus 0.5 seconds. Outcome badges reflect the epoch50 event-level baseline: eight standard clips are hits, two standard clips are misses, and all six hard clips are misses; the three additional false-positive badges remain visible on the applicable standard tiles. The hard-clip subtitle identifies the pre-execution classification that these events were difficult to see from CCTV. No generated accident imagery was used.

#### Evidence

Live paper identity: Group7_Capstone Project Defense Document - ITCAPROJ2, native Google Doc, tab **main**, live revision read during the 2026-09-16 review. Native read-back confirms Figure 35 object `kix.co53ubnr4z8v` remains present, Figure 36 object `kix.jlmsg170zcka` is 370 × 477.55 pt, Figure 37 object `kix.i0xs6de1cufr` is 370 × 477.55 pt, Figure 38 object `kix.dnescou9uygr` is 468 × 296.32 pt, and the former collage objects are absent. The current export shows Figure 35 on p. 198, Figure 36 on p. 200, Figure 37 on p. 201, and Figure 38 on p. 202 without clipping. The underlying verified event totals are 8/16 overall, 8/10 standard, 0/6 hard, three false positives over 11.0 clean minutes, and zero events on the airbase negative clip.

### 2. Defense paper — Evaluation Basis and Adopted Detection Core

Page/s: p. 197 in the current rendered export; native range 252610–253446 in tab t.y7ms6bhlk4qn

#### Change metadata

Operation: replace
Scope: logical paragraph
Changed target: the complete Evaluation Basis and Adopted Detection Core paragraph
Preserve: the heading, the following Event-Level Detection Performance paragraph, all verified metrics, and the existing table structure and formatting
Comment target: the complete revised logical paragraph after replacement

#### OLD

> AI model validation used the adopted epoch50 checkpoint and the complete detection core: grayscale preprocessing, YOLO inference, accident-class filtering, spatial-temporal evidence accumulation, and event emission. The evaluation was performed with fixed configuration on the labelled Lipa CDRRMO clip corpus, with an event counted only within the defined collision window. The tracker recorded nine AI validation cases as Pass, but the acceptance basis in the tracker describes the event-level results as descriptive unless a recall or false-positive threshold had been approved before execution. This distinction is important because event-level behavior represents the operational detection unit, whereas frame-level mAP describes a different measurement.

#### NEW

AI model validation used the adopted epoch50 checkpoint and the complete detection core: grayscale preprocessing, YOLO inference, accident-class filtering, spatial-temporal evidence accumulation, and event emission. The evaluation used a fixed configuration on the labelled Lipa CDRRMO clip corpus, with an event counted only within the defined collision window. The 17 clips were excluded from training but also informed checkpoint selection, so they are not an untouched post-selection test set. The tracker records nine AI-validation evidence rows as Pass because their required evidence or archival comparisons were recorded; this status is distinct from an independent event-recall acceptance result. Event-level behaviour is the operational detection unit, while frame-level mAP is a separate qualified validation-split indicator.

#### Evidence

The live ADAS Test Execution tracker, AI Model Validation tab, rows AI-VAL-001 through AI-VAL-009, currently marks all nine evidence rows Pass. The same rows identify archival or derived evidence and recorded clip-run results; their acceptance wording says event recall and false-positive results are descriptive unless a threshold was approved before execution. The frozen evidence records that the 17 clips were excluded from training but used for checkpoint selection, so they are not an untouched post-selection test set.

#### Proposed comment (same gate as replacement)

Comment scope: logical paragraph; the complete revised Evaluation Basis and Adopted Detection Core paragraph

Previous (marked, intentionally non-verbatim): AI model validation used the adopted epoch50 checkpoint and the complete detection core. The evaluation was performed on the labelled Lipa CDRRMO clip corpus. [[The tracker recorded nine AI validation cases as Pass]] but the acceptance basis described event-level results as descriptive unless a threshold had been approved. [[The paragraph did not state that the clips also informed checkpoint selection.]]

Codex ID: PS-20260916-AI-DETECTION-RESULTS-REVIEW

Done by Codex.

### 3. Defense paper — AI Detection Results introduction

Page/s: p. 197 in the current rendered export; native tab t.y7ms6bhlk4qn.

#### Change metadata

Operation: replace
Scope: logical paragraph
Changed target: the generic introductory paragraph under `AI Detection Results`
Preserve: the heading, the following evaluation-basis paragraph, and the existing paragraph style
Comment target: the complete revised logical paragraph

#### OLD

> The following section details the performance of the trained deep learning model, evaluating its accuracy and reliability in detecting collision events across various environmental conditions.

#### NEW

This section evaluates the complete detection core on labelled Lipa CDRRMO CCTV footage and interprets its results by scene difficulty, runtime consistency, and the limits of the available evidence.

#### Evidence

The paragraph was read back at native range 252367–252565. It preserves the section's purpose while previewing the discussion dimensions used below.

#### Proposed comment (same gate as replacement)

Comment scope: logical paragraph; OLD and NEW above

Previous: The following section details the performance of the trained deep learning model, evaluating its accuracy and reliability in detecting collision events across various environmental conditions.

Codex ID: PS-20260916-AI-DETECTION-RESULTS-REVIEW

Done by Codex.

### 4. Defense paper — Event-Level Detection Performance

Page/s: pp. 197–198 in the current rendered export; native range 253481–254685 in tab t.y7ms6bhlk4qn.

#### Change metadata

Operation: replace
Scope: logical paragraph
Changed target: the complete Event-Level Detection Performance paragraph
Preserve: the heading, Figure 35, Tables 26–27, and all established result values
Comment target: the complete revised logical paragraph

#### OLD

> All 17 labelled clips were accounted for: 16 crash-labelled clips and one negative airbase clip. The frozen epoch50 pipeline detected 8 of 16 crash events overall, corresponding to 50% event-level recall. The standard subset produced 8 of 10 hits, or 80% recall, while all six hard-condition clips were missed. Three false positives occurred over 11.0 clean minutes, equivalent to 0.27 false positives per minute, and the negative airbase clip produced no event. The tracker also recorded 7 of 8 for the NVR-only standard subset. The result is therefore strongest on the standard subset and weakest on the hard subset; the hard-case misses prevent a general claim that the detector is robust across all tested conditions.

#### NEW

The event-level results are interpreted using two difficulty groups defined before model execution. The ten standard-condition clips represent the more observable comparison cases in the available CCTV footage. The six hard-condition clips were classified by the project owner in advance as hard or nearly impossible to see from the available CCTV view; the group includes a collision far from the camera and difficult views such as a vehicle making a U-turn. Because the classifications preceded testing, the split reflects scene difficulty rather than a post-hoc explanation of misses. The detector identified 8 of 10 standard-condition crashes (80%), while all six hard-condition clips were missed (0/6). This indicates that the current model is most effective when the collision signal is observable in the camera view, while difficult or low-salience events remain outside its present coverage. Across the full labelled corpus, the result was 8 of 16 crash events (50%), with three false positives over 11.0 clean minutes (0.27 FP/min). The negative airbase clip produced no event, supporting the recorded negative-control observation without being treated as a deployment-wide specificity estimate.

#### Evidence

The hard/standard stratification is pre-execution evidence in `ai_engine/eval/labels.csv`: the hard group was owner-classified as hard or nearly impossible to see from CCTV before model execution, including far-from-camera and U-turn cases. The frozen event harness records 8/10 standard, 0/6 hard, 8/16 overall, three false positives over 11.0 clean minutes, and zero events on the negative airbase clip.

#### Proposed comment (same gate as replacement)

Comment scope: logical paragraph; OLD and NEW above

Previous (marked, intentionally non-verbatim): The paragraph reported [[8 of 16 overall]] and [[8 of 10 standard]] while describing all hard-condition clips as missed. It did not explain that the hard group was [[preclassified as difficult before model execution]] or identify the camera-view difficulty.

Codex ID: PS-20260916-AI-DETECTION-RESULTS-REVIEW

Done by Codex.

### 5. Defense paper — Model-stage mAP and checkpoint qualification

Page/s: p. 202 in the current rendered export; native tab t.y7ms6bhlk4qn.

#### Change metadata

Operation: replace
Scope: logical paragraph
Changed target: the frame-level mAP and checkpoint-selection discussion
Preserve: the recorded 0.956 value, the 0.85 objective, and the event-level measures
Comment target: the complete revised logical paragraph

#### OLD

> The event-level result should not be replaced by the archived mAP value. AI-VAL-001 recorded an accident mAP@0.50 of 0.956 at epoch 50, exceeding the 0.85 numerical objective, but the original validation split was not available for rerun and the frame-level split retained incident leakage. The value is consequently reported as a qualified validation-split result rather than independent operational accuracy. The checkpoint-selection evidence likewise remains qualified: eight exported checkpoints were compared historically, and epoch50 was selected because it matched the best recall while producing three rather than five false positives; no fresh sweep was conducted during the current execution.

#### NEW

Two complementary evidence levels are reported. The recorded frame-level validation result, accident mAP@0.50 = 0.956 at epoch 50, exceeded the numerical 0.85 objective. Because the original validation split was frame-level, retained incident leakage, and was unavailable for rerun, this result is treated as a qualified model-stage indicator rather than a standalone measure of operational accuracy. The event-level results are the operational measures for the labelled local footage. The checkpoint comparison was historical: eight exported checkpoints were compared, and epoch50 matched the best recall while producing three rather than five false positives; no fresh checkpoint sweep was conducted during the current execution.

#### Evidence

The current evidence separates frame-level model-stage reporting from event-level operational reporting. The mAP value is retained with its leakage/no-rerun qualification, and checkpoint selection remains historical rather than a newly executed sweep.

#### Proposed comment (same gate as replacement)

Comment scope: logical paragraph; OLD and NEW above

Previous (marked, intentionally non-verbatim): [[The event-level result should not be replaced by the archived mAP value.]] The paragraph reported the 0.956 value and leakage limitation, but framed the result as [[a qualified validation-split result rather than independent operational accuracy]] and described the checkpoint comparison as [[likewise remains qualified]].

Codex ID: PS-20260916-AI-DETECTION-RESULTS-REVIEW

Done by Codex.

### 6. Defense paper — Runtime rate and cadence discussion

Page/s: p. 203 in the current rendered export; native tab t.y7ms6bhlk4qn.

#### Change metadata

Operation: replace
Scope: logical paragraph
Changed target: the TensorRT parity and cadence paragraph
Preserve: the 17/17 hit/miss agreement, false-positive counts, and tested cadence results
Comment target: the complete revised logical paragraph

#### OLD

> TensorRT parity testing found that all 17 per-clip hit or miss outcomes matched the epoch50 reference checkpoint. The native engine produced four false positives compared with three for the checkpoint at one operating point, while the 10-FPS native run produced three and matched the checkpoint count. This supports the absence of a recall regression but also documents false-positive drift. Cadence sensitivity preserved the per-clip pattern at 10, 8, 6, 5, and 3 FPS, while 4 FPS missed the motor-motor-night clip. Separately, reducing the source resolution to 640 by 360 lowered recall from 8 of 16 to 6 of 16, showing that source downscaling is not accuracy-neutral.

#### NEW

At the source video's normal delivery rate (the native rate, approximately 25–30 frames per second), the TensorRT engine preserved all 17 clip-level hit/miss decisions relative to the epoch50 reference. It produced four false positives in that run. In a separate diagnostic run, the same engine was deliberately evaluated using 10 sampled frames per second; it produced three false positives, matching the reference count. This difference is recorded as a sampling-condition variation, and no recall regression was observed. Cadence testing at 10, 8, 6, 5, and 3 FPS retained the reference per-clip pattern, while the tested 4-FPS profile missed one clip.

#### Evidence

“Native rate” is the source video's normal delivery rate, approximately 25–30 frames per second in this run. “10 sampled frames per second” is a separate diagnostic profile that deliberately processes ten frames each second. The frozen parity record shows all 17 per-clip outcomes matched; false positives were 4 at native rate and 3 at the 10-FPS diagnostic profile. The requested source-resolution comparison was omitted from the paper discussion.

#### Proposed comment (same gate as replacement)

Comment scope: logical paragraph; OLD and NEW above

Previous (marked, intentionally non-verbatim): [[TensorRT parity testing found]] all 17 per-clip outcomes matched. The paragraph compared [[four false positives with three]] and described the 10-FPS run, then included the removed [[source downscaling]] result.

Codex ID: PS-20260916-AI-DETECTION-RESULTS-REVIEW

Done by Codex.

### 7. Defense paper — AI result tables and source line

Page/s: pp. 203–205 in the current rendered export; native tab t.y7ms6bhlk4qn.

#### Change metadata

Operation: replace and reformat
Scope: table-cell text and page layout
Changed target: Table 26 interpretation cells, Table 27 qualification/profile wording, and the source line beneath Table 27
Preserve: table structure, denominators, measured values, Figure 35, and the document's existing table style
Comment target: the source line and cadence row; the remaining compact interpretations are display wording for the same verified results

#### Applied revision

Table 26 now uses concise interpretations: `Full-corpus descriptive baseline; no pre-set recall threshold.`, `Best observed subset; corpus-bound.`, `Coverage boundary; 0/6.`, `One negative-control observation; not deployment-wide specificity.`, and `Supplementary source-specific result; not an independent set.` Table 27 now labels the mAP, checkpoint, TensorRT, and cadence entries as qualified, archival, or recorded profile comparisons without changing their measured values. The source line now distinguishes frame-level mAP, event-level recall, engine parity, and cadence without mentioning source resolution. A page break before Table 27 keeps that table intact on p. 205.

#### Evidence

Live table read-back confirms Table 26 retains 8/16 overall, 8/10 standard, 0/6 hard, 0 events on the negative control, and 7/8 for the NVR-only standard subset. Table 27 retains the recorded 0.956 mAP, eight-checkpoint comparison, 17/17 parity, false-positive variation, and cadence profiles. The exported pages show Table 26 with a repeated header across its continuation and Table 27 fully visible on p. 205.

#### Proposed comment (same gate as replacement)

Comment scope: source line and cadence row; exact OLD/NEW evidence is preserved in the live review comments

Previous: Source and cadence wording as recorded before the revision.

Codex ID: PS-20260916-AI-DETECTION-RESULTS-REVIEW

Done by Codex.

## No change in this package

- The reported event-level values are supported: 8/16 overall recall, 8/10 standard recall, 0/6 hard recall, three false positives over 11.0 clean minutes, and zero events on the airbase negative clip.
- The archived 0.956 accident mAP@0.50 value is appropriately qualified as a leaked frame-level validation result rather than independent operational accuracy.
- Table 26 reports the correct denominators and limits; the NVR-only 7/8 row is explicitly identified as source-specific and descriptive.
- The TensorRT parity paragraph correctly discloses 17/17 per-clip hit/miss agreement together with the native-rate false-positive drift.
- The live Google Doc now contains the strengths-first AI-results discussion, the standard/hard scene-difficulty explanation, the qualified model-stage/runtime wording, the table cleanup, and the page-layout repair.

## Approval / sync ledger

Package ID: PS-20260916-AI-DETECTION-RESULTS-REVIEW
Approval source: User authorization to inspect the live document structure and apply the AI-detection-results revisions directly in the native Google Doc.

| Target              | Approved scope                                                                            | Applied/read back                                                                    | Skipped/pending | Blocked |
| ------------------- | ----------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------ | --------------- | ------- |
| Defense paper       | Figures 36–38 and AI Detection Results discussion, tables, source line, and layout repair | Applied and verified in the live Doc; native read-back and rendered PDF QA completed | —               | —       |
| Tracker Sheet       | None requested                                                                            | —                                                                                    | Out of scope    | —       |
| Standalone comments | Comments attached to the applied review package                                           | Eight package comments read back; each ends with `Done by Codex.`                    | —               | —       |
