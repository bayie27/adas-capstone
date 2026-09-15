---
section: Target Deployment Architecture; Testing and Validation
page/s: "pp. 27, 60, 63, 166, 196 (live PDF rendered 2026-09-15); local validation-plan row"
required_revision: Replace current substream and subtype=1/720p wording with the authorized main RTSP feed deployment target
notes: The VMS-fed edge architecture remains viable. The current defense paper should present authorized main RTSP feed ingestion as the target and omit prior candidate-profile language. Fresh 704x480 testing remains internal evidence for why the target was selected. This supersedes the fixed-target wording in the 2026-09-09 finding; its separate capacity and cadence evidence remains separately reviewable.
status: Applied and verified
assigned_to: Daniboy
synced: 2026-09-15
---

## Changes

### 1. Defense paper — Deployment Architecture, stream-ingestion bullet

Page/s: p. 166 (live PDF rendered 2026-09-15); native range 196049–196343 at the pre-write revision

#### Change metadata

Operation: replace
Scope: logical paragraph
Changed target: the complete stream-ingestion bullet currently titled "Substream Targeting"
Preserve: the surrounding deployment bullets, list formatting, and the VMS/media-gateway architecture
Comment target: the complete replacement paragraph; resolve native indexes after the replacement

#### OLD

> Substream Targeting: In the target VMS integration, stream requests would use the subtype=1 parameter to request a 720p substream instead of a 2K main stream. This approach would reduce inbound network traffic on the edge server and avoid interference with continuous 2K NVR archival recording.

#### NEW

Main RTSP Feed Ingestion: In the target VMS integration, the edge server would request the authorized main RTSP feed from the Dahua DSS Pro media gateway for AI processing.

#### Evidence

The fresh matched run on 2026-09-14 used the ten pre-registered `standard` clips from `ai_engine/eval/labels.csv`, the same `.pt` detector, CPU device, confidence 0.15, 640 model input, threshold 1, decay 0.3, and native frame sampling in both arms. The source-resolution arm scored 8/10 recall and 3 false positives; the lossless 704x480 derived arm scored 6/10 and 3 false positives. `dpwh-red-car-motor.mp4` and `red-car-motor.mp4` hit natively and produced no event after the 704x480 conversion. Results are recorded in `/tmp/adas-d1-standard-20260914/baseline-score.txt` and `/tmp/adas-d1-standard-20260914/d1-score.txt`. This is a `.pt` CPU resolution probe, not a TensorRT production certification; the evidence supports treating the main feed as the current accuracy baseline. The active runtime has no hardcoded `subtype=1`; stream selection remains configurable.

#### Proposed comment (same gate as replacement)

Comment scope: logical paragraph; the complete replacement "Main RTSP Feed Ingestion" paragraph

Previous: Substream Targeting: In the target VMS integration, stream requests would use the subtype=1 parameter to request a 720p substream instead of a 2K main stream. This approach would reduce inbound network traffic on the edge server and avoid interference with continuous 2K NVR archival recording.

Codex ID: PS-20260914-STREAM-PROFILE-TARGET-REFRAME

Done by Codex.

### 2. Defense paper — Phase 5 Deployment and Implementation, target-production paragraph

Page/s: p. 60 (live PDF rendered 2026-09-15); native range 89208–89830 at the pre-write revision

#### Change metadata

Operation: replace
Scope: logical paragraph
Changed target: the sentence that specifies passive ingestion of authorized video substreams
Preserve: the proof-of-concept boundary, authorization caveat, and all pilot/handover limitations
Comment target: the complete replacement paragraph; resolve native indexes after the replacement

#### OLD

> The parallel development tracks formally unified in a target production deployment plan. The completed proof of concept was evaluated on researcher-controlled hardware; it was not installed in the Lipa CDRRMO command center or connected to the agency's CCTV VLAN. If CDRRMO later adopts the system, it could operate as a headless client that passively ingests authorized video substreams from the Dahua VMS. Pilot activation, scaling beyond the demonstration environment, formal handover, staff training, AI retraining, and hardware maintenance would require separate CDRRMO authorization and post-capstone implementation.

#### NEW

The parallel development tracks formally unified in a target production deployment plan. The completed proof of concept was evaluated on researcher-controlled hardware; it was not installed in the Lipa CDRRMO command center or connected to the agency's CCTV VLAN. If CDRRMO later adopts the system, it could operate as a headless client that passively ingests the authorized main RTSP feed from the Dahua VMS. Pilot activation, scaling beyond the demonstration environment, formal handover, staff training, AI retraining, and hardware maintenance would require separate CDRRMO authorization and post-capstone implementation.

#### Evidence

The live paragraph currently names a lower-resolution source as the target, while the matched resolution experiment above shows that a D1-like 704x480 source is not detection-equivalent to the native source. The architecture and authorization statements are still valid; the current target should be stated as the main RTSP feed.

#### Proposed comment (same gate as replacement)

Comment scope: logical paragraph; the complete target-production paragraph

Previous (marked, intentionally non-verbatim): The parallel development tracks formally unified in a target production deployment plan. The completed proof of concept was evaluated on researcher-controlled hardware; it was not installed in the Lipa CDRRMO command center or connected to the agency's CCTV VLAN. If CDRRMO later adopts the system, it could operate as a headless client that passively ingests [[authorized video substreams]] from the Dahua VMS. Pilot activation, scaling beyond the demonstration environment, formal handover, staff training, AI retraining, and hardware maintenance would require separate CDRRMO authorization and post-capstone implementation.

Codex ID: PS-20260914-STREAM-PROFILE-TARGET-REFRAME

Done by Codex.

### 3. Defense paper — implementation timeline milestone

Page/s: p. 63 (live PDF rendered 2026-09-15); native range 91440–91477 at the pre-write revision

#### Change metadata

Operation: replace
Scope: span
Changed target: the milestone label "Activate live VMS substream inference"
Preserve: the timeline item, ordering, and formatting
Comment target: the replacement milestone label

#### OLD

> Activate live VMS substream inference

#### NEW

Activate live VMS inference from the authorized main RTSP feed

#### Evidence

The milestone can remain as a live-VMS activation step, with the target source stated directly as the authorized main RTSP feed. The live Doc's target deployment is conditional and not a claim of completed CDRRMO installation.

#### Proposed comment (same gate as replacement)

Comment scope: span; OLD `Activate live VMS substream inference`; NEW `Activate live VMS inference from the authorized main RTSP feed`

Previous: Activate live VMS substream inference

Codex ID: PS-20260914-STREAM-PROFILE-TARGET-REFRAME

Done by Codex.

### 4. Defense paper — Deployment Architecture, "VMS Integration" bullet

Page/s: p. 196 (live PDF rendered 2026-09-15); native paragraph observed at the pre-write revision

#### Change metadata

Operation: replace
Scope: logical paragraph
Changed target: the complete "VMS Integration" bullet
Preserve: headless-client authentication, Dahua DSS Pro, passive RTSP requests, and the target-production qualifier
Comment target: the complete replacement paragraph; resolve native indexes after the replacement

#### OLD

> VMS Integration: The system is securely authenticated as a headless client to the Dahua DSS Pro server, configuring it to passively request 720p substreams rather than pulling massive 2K main streams.

#### NEW

VMS Integration: The system is securely authenticated as a headless client to the Dahua DSS Pro server, configuring it to passively request the authorized main RTSP feed for AI processing.

#### Evidence

The current sentence hard-codes an unvalidated lower-resolution-versus-main-feed choice. The same VMS handshake and passive-ingestion architecture remains the intended design; the current deployment target is the authorized main RTSP feed.

#### Proposed comment (same gate as replacement)

Comment scope: logical paragraph; the complete replacement "VMS Integration" paragraph

Previous: VMS Integration: The system is securely authenticated as a headless client to the Dahua DSS Pro server, configuring it to passively request 720p substreams rather than pulling massive 2K main streams.

Codex ID: PS-20260914-STREAM-PROFILE-TARGET-REFRAME

Done by Codex.

### 5. Defense paper — Definition of Terms, Dahua DSS Pro

Page/s: p. 27 (live PDF rendered 2026-09-15); native range 34060–34251 at the pre-write revision

#### Change metadata

Operation: replace
Scope: logical paragraph
Changed target: the VMS definition that names RTSP camera substreams
Preserve: Dahua DSS Pro's identity, media-gateway role, and the AI edge-server relationship
Comment target: the complete replacement definition

#### OLD

> The enterprise-level software (specifically Dahua DSS Pro) utilized by the Lipa CDRRMO, which acts as the media gateway proxy providing the RTSP camera substreams to the AI edge server.

#### NEW

The enterprise-level software (specifically Dahua DSS Pro) utilized by the Lipa CDRRMO, which acts as the media gateway proxy providing the authorized main RTSP feed to the AI edge server.

#### Evidence

This is a current definition in the defense paper, not a historical experiment record. Replacing the capability wording makes the paper consistently present main RTSP feed ingestion as the deployment target.

#### Proposed comment (same gate as replacement)

Comment scope: logical paragraph; the complete replacement Dahua DSS Pro definition

Previous: The enterprise-level software (specifically Dahua DSS Pro) utilized by the Lipa CDRRMO, which acts as the media gateway proxy providing the RTSP camera substreams to the AI edge server.

Codex ID: PS-20260914-STREAM-PROFILE-TARGET-REFRAME

Done by Codex.

### 6. Repository validation plan — production/test topology comparison

File: `docs/validation/test-execution-validation-plan.md:292`

#### Change metadata

Operation: replace
Scope: cell
Changed target: the production-target cell `Dahua DSS Pro, RTSP substreams`
Preserve: the same-protocol/URL-shape verdict and the MediaMTX test-environment cell
Comment target: none; this is a local documentation cell

#### OLD

> Dahua DSS Pro, RTSP substreams

#### NEW

Dahua DSS Pro, authorized main RTSP feed

#### Evidence

The validation plan must present the authorized main RTSP feed as the production target. The protocol and URL-shape comparison remains useful and is not invalidated.

## Out of scope by user direction

The older test-case tab `t.gcwpcc67rsrk` is intentionally excluded from this revision. TC-I-101, TC-I-102, and TC-AI-401 are legacy test cases in that separate tab; no replacement, deletion, or comment is proposed for them.

## Post-write verification — 2026-09-15

The live defense Doc was re-read after all writes at revision `ANLCKQlLmr1j56tIZfI4qUuzhCWBxcubAEzLd-zJ0pXK6sum-IYhZ9gENhx_bGddHPCyH0KnshmIuQOX4OVa1_IIfgvV72p8AZ4YkkWqkX0`. Each of the five NEW passages occurs exactly once in the main tab `t.y7ms6bhlk4qn`, and each attached comment is open, anchored, and has the expected package ID and quoted NEW text:

- Block 1: `AAACHJx-ysE`, anchor `kix.lktaq68ltt2w`
- Block 2: `AAACHJx-ysM`, anchor `kix.1i8q3tqvsm7t`
- Block 3: `AAACHJ11Qao`, anchor `kix.v71r51ap0x41`
- Block 4: `AAACHJ11Qaw`, anchor `kix.uocwyn9snoat`
- Block 5: `AAACHJ11Qa4`, anchor `kix.sif8wur8lm3h`

The only remaining `substream`, `subtype=1`, and `720p` hits in the live Doc are the five explicitly excluded legacy test-case paragraphs in tab `t.gcwpcc67rsrk`. The local validation-plan row in block 6 was applied and passes `git diff --check`. No Tracker Sheet write was requested or performed.

## Implicated but not changed here

- `ai_engine/README.md:97-102` and `ai_engine/capacity.py:25-31` use a synthetic 720p frame for a standalone capacity diagnostic. They explicitly say the command is not a production scheduler or RTSP test, so they are not stale deployment claims.
- `ai_engine/docs/AI_ENGINE_LIVE_SESSION_REPORT.md` and `AI_ENGINE_PIPELINE_OPTIMIZATION_PLAN_REVIEW.md` are historical experiment records. Preserve the negative substream finding and its provenance; do not erase it.
- The headless VMS/DSS Pro architecture, RTSP protocol, authorization boundary, segmented-network design, and conditional target-production server remain valid. This revision does not require a wholesale architecture rewrite.
- No active runtime code currently hard-codes `subtype=1`; no code change is proposed by this finding. If a future deployment configuration adds a fixed profile, it must be gated by the selected-profile evaluation.

## Decision and evidence boundary

The requested current claim is: **the target deployment ingests the authorized main RTSP feed from the Dahua VMS.** The concrete resolution, codec, and bitrate remain deployment configuration details to be recorded during validation. This is a deliberately simple target statement; it does not claim that CDRRMO is already connected or that the proof-of-concept host has production-scale capacity.

The 2026-09-14 run used the repository `.pt` detector on CPU and a lossless 704x480 derivation, so it is internal rationale for the main-feed choice, not TensorRT/GPU production certification. The current TensorRT/AI-GPU path still needs its native-feed baseline before NFR or deployment acceptance is updated.

## Relationship to the 2026-09-09 finding

Do not apply the 2026-09-09 finding's Block 1 as written: its continued assertion that the target is `subtype=1` at 720p is superseded by blocks 1–5 here. Preserve that older finding as historical provenance. Its proof-of-concept capacity and frame-cadence blocks remain distinct claims and may be applied or revised independently after their own approval and verification.

## Approval / sync ledger

Package ID: PS-20260914-STREAM-PROFILE-TARGET-REFRAME
Approval source: User message on 2026-09-15, “alright then I approve these chanegs,” following the scoped reply that authorized Defense paper blocks 1–5 and repository validation-plan block 6; legacy test-case tab blocks remain out of scope.

| Target                     | Approved scope                                            | Applied/read back                                                                                                                   | Skipped/pending | Blocked |
| -------------------------- | --------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- | --------------- | ------- |
| Defense paper              | blocks 1–5, including their attached replacement comments | blocks 1–5 + comment threads `AAACHJx-ysE`, `AAACHJx-ysM`, `AAACHJ11Qao`, `AAACHJ11Qaw`, `AAACHJ11Qa4` applied/read back 2026-09-15 | —               | —       |
| Repository validation plan | block 6                                                   | block 6 applied/read back 2026-09-15                                                                                                | —               | —       |
| Tracker Sheet              | Not applicable; no tracker row was proposed               | —                                                                                                                                   | —               | —       |
| Standalone comments        | Not applicable; comments are bundled with blocks 1–5      | —                                                                                                                                   | —               | —       |
