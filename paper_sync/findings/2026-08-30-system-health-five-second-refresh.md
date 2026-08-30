---
section: Use Case 6 and System Health telemetry
page/s: "unconfirmed"
required_revision: Align the documented live System Health polling cadence with the five-second implementation.
notes: NFR-05 already correctly requires a five-second refresh; this package corrects the conflicting UC-6 and audit wording only.
status: In progress
assigned_to: Daniboy
synced: false
---

## Changes

### 1. Defense paper — Use Case 6: Monitor System Health and Performance, step 3

Page/s: unconfirmed

#### OLD

> Every 15 seconds, the frontend client executes an asynchronous REST API poll to retrieve the latest in-memory rolling metrics for host hardware utilization, GPU telemetry, system uptime, and AI inference latency/FPS.

#### NEW

Every 5 seconds, the frontend client executes an asynchronous REST API poll to retrieve the latest in-memory rolling metrics for host hardware utilization, GPU telemetry, system uptime, and AI inference latency/FPS.

#### Evidence

Live paper read on 2026-08-30, Doc index 116601-116817, confirmed the OLD text. PR #191 changed `frontend/src/pages/SystemHealth.tsx` from `15_000` to `5_000` for the `system-health-live` query; the current implementation is at lines 526-532. The live NFR-05 paragraph at Doc index 100092-100374 already requires that live system health figures refresh every 5 seconds. A live PDF export succeeded, but this runtime could not expose its returned file reference to the PDF page-mapping tools, so no rendered page number is asserted.

#### Proposed comment (same gate as associated replacement)

Previous: Every 15 seconds, the frontend client executes an asynchronous REST API poll to retrieve the latest in-memory rolling metrics for host hardware utilization, GPU telemetry, system uptime, and AI inference latency/FPS.

Codex ID: PS-20260830-SYSTEM-HEALTH-FIVE-SECOND-REFRESH

Done by Codex.

### 2. ADAS_Paper_Audit — §1.11, telemetry transport and cadence explanation

Page/s: unconfirmed

#### OLD

> Change to: telemetry is REST-polled by the client, not pushed. The seven WebSocket event types (backend/app/schemas/events.py:21-31) are CONNECTION_READY, NEW_DETECTION, ALERT_STATUS_UPDATE, CAMERA_STATUS_UPDATE, SNOOZE_ACTIVATED, RE_ALARM, MAINTENANCE_NOTICE. None carries health data. The System Health page polls live metrics every 15 s and the status pill every 30 s (frontend/src/pages/SystemHealth.tsx:176, 181-184), while the backend samples into memory every 5 s (HEALTH_SAMPLE_SECONDS). See §4.4 for NFR-05.

#### NEW

Change to: telemetry is REST-polled by the client, not pushed. The seven WebSocket event types (backend/app/schemas/events.py:21-31) are CONNECTION_READY, NEW_DETECTION, ALERT_STATUS_UPDATE, CAMERA_STATUS_UPDATE, SNOOZE_ACTIVATED, RE_ALARM, MAINTENANCE_NOTICE. None carries health data. The System Health page polls live metrics every 5 s and displays the sample's refresh state; the backend samples into memory every 5 s (HEALTH_SAMPLE_SECONDS). See §4.4 for NFR-05.

#### Evidence

Live audit read on 2026-08-30, Doc index 30897-31413, confirmed the OLD text. `frontend/src/pages/SystemHealth.tsx:177-202` renders the sample refresh state from `collected_at` and `stale`; `:526-532` polls the live endpoint every 5 seconds. `backend/app/core/config.py:91-95` and `backend/app/main.py:186-190` retain the five-second backend sampler. No WebSocket or backend cadence changed in PR #191.

#### Proposed comment (same gate as associated replacement)

Previous: Change to: telemetry is REST-polled by the client, not pushed. The seven WebSocket event types (backend/app/schemas/events.py:21-31) are CONNECTION_READY, NEW_DETECTION, ALERT_STATUS_UPDATE, CAMERA_STATUS_UPDATE, SNOOZE_ACTIVATED, RE_ALARM, MAINTENANCE_NOTICE. None carries health data. The System Health page polls live metrics every 15 s and the status pill every 30 s (frontend/src/pages/SystemHealth.tsx:176, 181-184), while the backend samples into memory every 5 s (HEALTH_SAMPLE_SECONDS). See §4.4 for NFR-05.

Codex ID: PS-20260830-SYSTEM-HEALTH-FIVE-SECOND-REFRESH

Done by Codex.

### 3. ADAS_Paper_Audit_Tracker — `🚩 Action Stream`!A72:G72

Page/s: `🚩 Action Stream`!A72:G72

#### OLD

> No existing row. Live `userEnteredValue` cells A72:H72 are blank.

#### NEW

| Change Type | Section / Chapter                                                         | Page Number | Required Revision                                            | Notes                                                                                                           | Status      | Assigned to |
| ----------- | ------------------------------------------------------------------------- | ----------- | ------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------- | ----------- | ----------- |
| Minor       | Use Case 6: Monitor System Health and Performance; ADAS_Paper_Audit §1.11 | unconfirmed | Align the live System Health poll cadence with five seconds. | UC-6 says 15 seconds; audit §1.11 also states 15 s and an obsolete 30 s status pill. NFR-05 is already correct. | In progress | Daniboy     |

#### Evidence

Live tracker read on 2026-08-30. `🚩 Action Stream` row 30 is a completed REST-versus-WebSocket correction, while the live WSS definition is already correct and does not require a new edit. The first fully blank row after the current entries is row 72. Block 1 and Block 2 identify the distinct five-second cadence drift.

#### Proposed comment (same gate as associated replacement)

Previous: No existing row

Codex ID: PS-20260830-SYSTEM-HEALTH-FIVE-SECOND-REFRESH

Done by Codex.

## Approval / sync ledger

Package ID: `PS-20260830-SYSTEM-HEALTH-FIVE-SECOND-REFRESH`

| Target                        | Approved scope                         | Applied/read back                                                         | Skipped/pending | Blocked                                                                            |
| ----------------------------- | -------------------------------------- | ------------------------------------------------------------------------- | --------------- | ---------------------------------------------------------------------------------- |
| Defense paper                 | Block 1 and its attached comment       | Block 1 and comment `AAACGNyib9g`                                         | —               | —                                                                                  |
| ADAS_Paper_Audit plus tracker | Blocks 2-3 and their attached comments | Block 2 and comment `AAACAYXrzQk`; Block 3 row `🚩 Action Stream`!A72:G72 | —               | Block 3 attached Sheet comment: connector returned no provider-valid native anchor |
| Standalone comments           | None                                   | —                                                                         | None            | —                                                                                  |
