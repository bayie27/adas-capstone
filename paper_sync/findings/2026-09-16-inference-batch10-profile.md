---
section: Definition of Terms; Deep Learning Implementation and Training Protocol; Testing and Validation
page/s: "p. 19; p. 176; p. 177; p. 181 (fresh PDF rendered 2026-09-16; Table 23 begins p. 180)"
required_revision: Align all inference/export batch claims with the adopted batch-10 TensorRT profile
notes: Training batch=64 remains unchanged. The current optimization report identifies epoch50.engine as the batch-10 export and defers fifteen-camera qualification.
status: Applied and verified
assigned_to: Daniboy
synced: 2026-09-16
---

## Changes

### 1. Defense paper — Definition of Terms, Batched Inference

Page/s: p. 19 (fresh PDF rendered 2026-09-16; live native range `t.y7ms6bhlk4qn:22580–22904`)

#### Change metadata

Operation: replace
Scope: span
Changed target: the second sentence of the `Batched Inference` definition
Preserve: the first sentence defining batched inference and the surrounding Definition of Terms entries
Comment target: the replacement second sentence only

#### OLD

> The grouping of frames from all active camera feeds into a single inference call per scheduling tick, allowing the edge server to serve multiple streams without incurring a separate forward pass for each. Measured on the prototype hardware, per-batch latency scaled from 16.5 ms at a batch of 1 to 114.1 ms at a batch of 16.

#### NEW

The grouping of frames from all active camera feeds into a single inference call per scheduling tick, allowing the edge server to serve multiple streams without incurring a separate forward pass for each. In the adopted demonstration configuration, the TensorRT profile supports batches up to 10 cameras; measured per-batch latency depends on the selected engine, host, and number of active cameras.

#### Evidence

The live paper is `Group7_Capstone Project Defense Document - ITCAPROJ2`, main tab `t.y7ms6bhlk4qn`, read on 2026-09-16 at revision `ANLCKQn5LEAjjdN1elo5c3C3swYeGmr6OpxqJFB4VLzXw9wHDgU4jhQY21LS1UX_MsJaQtNWu51ufyuztWQn20StGvUZC87vxBa_-qkqi3k`. The current definition is at native range `22580–22904`.

`ai_engine/docs/AI_ENGINE_PIPELINE_OPTIMIZATION_PLAN_REVIEW.md:15-41` records the preserved batch-32 export and the new batch-10 `epoch50.engine` export. The new profile's maximum input dimension is 10, and the report explicitly says not to attempt batch 15 with the new export. The paper's existing batch-16 latency sentence is not identified as a historical result from the preserved artifact and is not reproducible by the adopted batch-10 profile; the replacement keeps the definition while removing an unqualified obsolete measurement.

The working environment's `.env` selects `epoch50.engine`, and the present `ai_engine/epoch50.engine` file is 8,824,086 bytes with SHA-256 `79cf3165113f6b4f185f9bbbac37422c078ea5eaff9bb61695d3929def13bee8`, matching the optimization report's new batch-10 artifact hash. The preserved batch-32 artifact is not present in the current working tree.

#### Proposed comment (same gate as replacement)

Comment scope: span; OLD `Measured on the prototype hardware, per-batch latency scaled from 16.5 ms at a batch of 1 to 114.1 ms at a batch of 16.`; NEW `In the adopted demonstration configuration, the TensorRT profile supports batches up to 10 cameras; measured per-batch latency depends on the selected engine, host, and number of active cameras.`

Previous: Measured on the prototype hardware, per-batch latency scaled from 16.5 ms at a batch of 1 to 114.1 ms at a batch of 16.

Codex ID: PS-20260916-INFERENCE-BATCH10-PROFILE

Done by Codex.

### 2. Defense paper — Table 22, YOLO26n Training Configuration and Methodological Purpose

Page/s: p. 176 (fresh PDF rendered 2026-09-16; live native cell range `t.y7ms6bhlk4qn:221322–221451`)

#### Change metadata

Operation: replace
Scope: span
Changed target: the batch-profile number in the `Training batch` methodological-purpose cell
Preserve: `batch=64` as the training batch, the rest of the cell, and the table formatting
Comment target: the replacement number only

#### OLD

> Provide efficient batched optimization in the recorded Colab environment; this is distinct from the TensorRT export profile of 32

#### NEW

Provide efficient batched optimization in the recorded Colab environment; this is distinct from the TensorRT export profile of 10

#### Evidence

The live Table 22 cell is `t.y7ms6bhlk4qn:221322–221451`. The adjacent `Training batch` value remains `batch=64` at `221312–221320`; only its comparison with the TensorRT export profile changes. The current optimization report identifies the adopted export as the new batch-10 profile and the preserved older artifact as batch 32.

#### Proposed comment (same gate as replacement)

Comment scope: span; OLD `32`; NEW `10`

Previous: 32

Codex ID: PS-20260916-INFERENCE-BATCH10-PROFILE

Done by Codex.

### 3. Defense paper — Runtime Optimization and TensorRT Export, export batch profile

Page/s: p. 177 (fresh PDF rendered 2026-09-16; live native range `t.y7ms6bhlk4qn:223281–223479`)

#### Change metadata

Operation: replace
Scope: logical paragraph
Changed target: the complete `Export batch profile` bullet
Preserve: the TensorRT export explanation, dynamic-profile qualification, and the statement that the batch value is not a tested camera count
Comment target: the complete revised logical paragraph

#### OLD

> Export batch profile (batch=32). Defines 32 as the maximum or configured batch dimension for the exported TensorRT optimization profile; it does not claim that 32 cameras were tested simultaneously.

#### NEW

Export batch profile (batch=10). Defines 10 as the maximum or configured batch dimension for the exported TensorRT optimization profile; it does not claim that 10 cameras were tested simultaneously.

#### Evidence

The live paragraph is `t.y7ms6bhlk4qn:223281–223479`. The current optimization report's measured profile table identifies the new export's minimum/optimum/maximum batch dimensions as 1/10/10, while the old preserved export is 1/32/32. The current `.env` selects the new `epoch50.engine`, whose file hash matches the report's new-artifact hash. The paper must describe the adopted new artifact consistently; changing the batch profile does not turn the statement into a claim that ten cameras were tested simultaneously.

#### Proposed comment (same gate as replacement)

Comment scope: logical paragraph; the complete revised `Export batch profile` bullet

Previous (marked, intentionally non-verbatim): Export batch profile ([[batch=32]]). [[Defines 32]] as the maximum or configured batch dimension for the exported TensorRT optimization profile; it does not claim that [[32 cameras]] were tested simultaneously.

Codex ID: PS-20260916-INFERENCE-BATCH10-PROFILE

Done by Codex.

### 4. Defense paper — Table 23, Test Environment Summary, AI Batch Size & Configuration

Page/s: p. 181 (fresh PDF rendered 2026-09-16; Table 23 begins on p. 180; live native cell range `t.y7ms6bhlk4qn:228964–229141`)

#### Change metadata

Operation: replace
Scope: span
Changed target: the export batch number in the `AI Batch Size & Configuration` description cell
Preserve: the FP16, image-size, confidence-threshold, and ten-stream operating-point details
Comment target: the replacement number only

#### OLD

> YOLO26n TensorRT engine exported with dynamic shapes at batch 15 (FP16). Inference size 640. Detection threshold 0.15. Target operating point is 10 concurrent streams at 15 FPS.

#### NEW

YOLO26n TensorRT engine exported with dynamic shapes at batch 10 (FP16). Inference size 640. Detection threshold 0.15. Target operating point is 10 concurrent streams at 15 FPS.

#### Evidence

The live Table 23 cell is `t.y7ms6bhlk4qn:228964–229141`, and the visible caption is `Test Environment Summary` (the connector reports raw table number 24). The browser-selected cell currently says batch 15. `ai_engine/docs/AI_ENGINE_PIPELINE_OPTIMIZATION_PLAN_REVIEW.md:15-41` records the new batch-10 export, the ten-camera immediate target, and the deferral of fifteen-camera qualification. The ten-stream operating point is already 10 and is preserved; this block changes only the TensorRT profile value.

#### Proposed comment (same gate as replacement)

Comment scope: span; OLD `15`; NEW `10`

Previous: 15

Codex ID: PS-20260916-INFERENCE-BATCH10-PROFILE

Done by Codex.

## Scope notes

- The live paper's `batch=64` training value remains correct and is not changed.
- The current repository's generic `ai_engine/README.md:81` export example and `docs/validation/test-execution-validation-plan.md:138,185,200,215-223,434` still contain older batch-15 wording. They are companion documentation targets, not defense-paper sites, and are not changed in this paper-scoped finding.
- `ai_engine/machine_profile.json` is machine-specific and marked `verification: unverified`; it is not used to invent a new capacity number. The finding changes configuration wording only and does not claim ten-camera performance success.
- The direct native PDF export endpoint returned HTTP 403, but the live browser tab's Google Workspace export produced a fresh PDF. Its rendered pages were visually inspected for p. 19, p. 176, p. 177, p. 180, and p. 181; the updated passages and table rows are legible with no clipping or overlap.

## Post-write verification — 2026-09-16

- Defense paper write completed under a required-revision guard. Final live document revision: `ANLCKQneLuj6Xkw238NQrHxTitW6sEpnTrpInkQ3A2sax69LCWZDqbXnGrpBHJk2HlolPcQhz_ASBgFAzX4HrfZ1PfL_LsKzPlrbTzBd1yw`.
- Fresh native text and table reads confirm each NEW passage occurs once and each OLD passage occurs zero times in the main tab. Native read-back ranges are: Definition of Terms second sentence `22580–22979`; Table 22 purpose cell `221397–221526`; export bullet `223356–223554`; Table 23 AI Batch Size cell `229039–229216`. The adjacent training value remains `batch=64` at `221387–221395`.
- Four open native comments were created and read back with the package ID and anchors: `AAACAlv6E-4` / `kix.qq19ug5vfot5` (Definition of Terms span), `AAACAlv6E-8` / `kix.99lxob4j8a17` (Table 22 replacement number), `AAACAlv6E_A` / `kix.r8qra6snhpt3` (export bullet), and `AAACAlv6E_E` / `kix.bihpz2maw514` (Table 23 replacement number). Each comment ends with `Done by Codex.` and quotes the new target text or number.
- Tracker row `🚩 Action Stream!A88:G88` was written and read back with the planned values and orange `#E67E22` text. `H88` remains blank and retains its existing `ONE_OF_LIST` validation for the reviewer field.
- The direct native PDF export endpoint still returns HTTP 403. The browser-exported PDF fallback was rendered and visually inspected for p. 19, p. 176, p. 177, p. 180, and p. 181; the updated passages and table rows are legible with no clipping or overlap.

## Approval / sync ledger

Package ID: PS-20260916-INFERENCE-BATCH10-PROFILE
Approval source: User message “approved” on 2026-09-16 following the proposed manifest; covers Defense paper blocks 1–4 with attached comments and tracker block 5 (`🚩 Action Stream!A88:G88`).

| Target                   | Approved scope                                           | Applied/read back                                                                | Skipped/pending | Blocked |
| ------------------------ | -------------------------------------------------------- | -------------------------------------------------------------------------------- | --------------- | ------- |
| Defense paper            | blocks 1–4, including attached replacement comments      | applied/read back; comment IDs, anchors, and fresh rendered pages recorded above | —               | —       |
| ADAS_Paper_Audit_Tracker | block 5, row `🚩 Action Stream!A88:G88` with orange text | applied/read back; `H88` blank and its validation preserved                      | —               | —       |
| Standalone comments      | Not applicable; comments are bundled with blocks 1–4     | —                                                                                | —               | —       |
