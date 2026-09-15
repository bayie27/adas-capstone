---
section: NFR-03 Frame Rate Maintenance
page/s: "70 and 165"
required_revision: Change the NFR-03 operating band to 5 to 15 FPS.
notes: User-selected requirement wording; 5 FPS is the lowest tested cadence retaining the native per-clip hit/miss pattern in the reset-aware TensorRT evaluation.
status: Not started
assigned_to: Daniboy
synced: 2026-09-14
---

## Changes

### 1. Defense paper — Table 7, NFR-03 Frame Rate Maintenance

Page/s: 70 (rendered PDF exported 2026-09-14)

#### Change metadata

Operation: replace
Scope: logical paragraph
Changed target: the requirement text in the NFR-03 row
Preserve: the row label, table structure, and every other NFR row
Comment target: the complete replacement requirement text; resolve native indexes before writing

#### OLD

> The system shall analyze each connected camera feed at a minimum of 10 to 15 frames per second, which is enough to catch collisions as they happen without overloading the server.

#### NEW

The system shall analyze each connected camera feed at a minimum of 5 to 15 frames per second which is enough to catch collisions as they happen without overloading the server.

#### Evidence

Live defense paper, Table 7 NFR-03, read 2026-09-14: native range 100136–100314 in tab `t.y7ms6bhlk4qn`, revision `ANLCKQnuMTSOLaPx6dFTFuayKifGxCOPIpuUtiVMjzFUs_DZ1lot3PPDmfp9IsdmBrR7kCSUPG-UmXZDUiteSzv9DTDlTletEkz3iZ8KYg8`.

The reset-aware TensorRT evaluation recorded the native per-clip hit/miss pattern at 10, 8, 6, 5, and 3 FPS; 4 FPS missed `motor-motor-night`. The user selected the 5-to-15 wording as the NFR requirement. False-positive totals vary by sampled cadence and are not represented as an equivalence claim.

#### Proposed comment (same gate as replacement)

Comment scope: logical paragraph; OLD and NEW are the complete NFR-03 requirement text

Previous: The system shall analyze each connected camera feed at a minimum of 10 to 15 frames per second, which is enough to catch collisions as they happen without overloading the server.

Codex ID: PS-20260914-NFR03-FIVE-TO-FIFTEEN-FPS

Done by Codex.

### 2. Defense paper — Deployment Architecture, Hardware Utilization & Computational Load Balancing

Page/s: 165 (rendered PDF exported 2026-09-14)

#### Change metadata

Operation: replace
Scope: span
Changed target: `below 10 FPS` in the hardware-utilization paragraph
Preserve: the 15-FPS target, paragraph structure, and surrounding deployment text
Comment target: `below 5 FPS`; resolve native indexes before writing

#### OLD

> Hardware Utilization & Computational Load Balancing: The target production design uses an inference target of 15 FPS per camera, with rates below 10 FPS defined as a performance warning.

#### NEW

Hardware Utilization & Computational Load Balancing: The target production design uses an inference target of 15 FPS per camera, with rates below 5 FPS defined as a performance warning.

#### Evidence

Live defense paper, native range 196265–196451 in tab `t.y7ms6bhlk4qn`, revision `ANLCKQnuMTSOLaPx6dFTFuayKifGxCOPIpuUtiVMjzFUs_DZ1lot3PPDmfp9IsdmBrR7kCSUPG-UmXZDUiteSzv9DTDlTletEkz3iZ8KYg8`, read 2026-09-14.

The warning threshold is currently implemented as `config.FPS_BAND_MIN = 10.0`, used by both `ai_engine/camera.py` and `ai_engine/gpu_camera.py` to emit `INFERENCE_FPS_BELOW_MIN`. Changing the paper claim to 5 FPS requires a separately approved implementation change to that constant and its tests. Existing historical design documents and the AI engine README also quote the 10-FPS threshold; they should be reconciled when the implementation change is approved, not treated as live-paper edits now.

#### Proposed comment (same gate as replacement)

Comment scope: span; OLD `below 10 FPS`; NEW `below 5 FPS`

Previous: below 10 FPS

Codex ID: PS-20260914-NFR03-FIVE-TO-FIFTEEN-FPS

Done by Codex.

## Approval / sync ledger

Package ID: PS-20260914-NFR03-FIVE-TO-FIFTEEN-FPS
Approval source: user approved the defense-paper write and PDF export on 2026-09-14

| Target              | Approved scope                            | Applied/read back                                 | Skipped/pending | Blocked |
| ------------------- | ----------------------------------------- | ------------------------------------------------- | --------------- | ------- |
| Defense paper       | blocks 1–2 and their replacement comments | blocks 1–2 and both comments read back 2026-09-14 | —               | —       |
| Tracker Sheet       | Not applicable                            | —                                                 | —               | —       |
| Standalone comments | Not applicable                            | —                                                 | —               | —       |
