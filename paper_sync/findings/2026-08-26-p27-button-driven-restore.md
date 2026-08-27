---
section: System Maintenance / Database Restoration
page/s: "pp. 152–154; 🚩 Action Stream!A67:H67"
required_revision: Mark the existing button-driven database-restore tracker item complete
notes: The live defense paper already describes dashboard initiation, external Windows/Linux orchestration, rollback, and audit logging. Only the existing tracker row needs completion; no duplicate row or defense-paper replacement is proposed.
status: Not started
assigned_to: Daniboy
synced: false
---

## Changes

### 1. Tracker Sheet — `🚩 Action Stream`!A67:H67

Page/s: `🚩 Action Stream`!A67:H67; related defense-paper restore architecture is on printed pp. 152–154 (PDF page mapping not re-exported for this check).

#### OLD

> A67:H67 = [blank, blank, blank, "restore should be button and no need to run command", blank, "In progress", "Daniboy", blank]

#### NEW

Major | Use Case 13, System Maintenance and Database Restoration Architecture | 152–154 | Complete the dashboard-driven database restore flow with password and exact phrase confirmation, independently supervised coordination, and automatic rollback on readiness failure. | Windows dashboard restore and readiness-failure rollback drills passed without terminal intervention after the button click; Linux/systemd artifacts are complete but reviewed-not-tested in this Windows session. | Completed | Daniboy | [preserve blank]

#### Evidence

The live tracker was read immediately before this proposal from native range `🚩 Action Stream`!A67:H67. The row contains only the existing requirement note, `In progress`, and `Daniboy`; the other cells are blank.

The live defense Doc already states that restoration is initiated through the administrator interface and executed offline by an external platform orchestrator (native paragraph range 184040–184785), supports Windows PowerShell and Linux systemd (184786–185232), creates a safety snapshot, replaces the database, verifies integrity, rolls back automatically, resumes services, and records the outcome (185233–186123). No defense-paper replacement is required for P27.

The implementation evidence is recorded in `be_plan/MANUAL_TESTS.md`: the successful local Windows button-only restore and the post-swap AI-readiness-failure drill both completed with no terminal intervention after the dashboard click. The Linux service and runner syntax passed `bash -n`; `systemd-analyze` and WSL execution were unavailable on this Windows host and remain unverified.

#### Proposed comment (same gate as associated tracker update)

Previous: A67:H67 = [blank, blank, blank, "restore should be button and no need to run command", blank, "In progress", "Daniboy", blank]

Codex ID: PS-20260826-P27-BUTTON-RESTORE

Done by Codex.

## Verified no additional paper or audit-Doc replacement

The current native defense Doc already matches the settled P27 behavior, including the retained Administrator password and exact confirmation-string requirement in Use Case 13 (native paragraph range 129575–131491). It does not require a user to enter, copy, or understand a backup ID, and it does not instruct dashboard users to run a command. The current `ADAS_Paper_Audit` backup/restore note (native range `t.0:65607–66242`) is an existing audit record rather than a new P27 drift site; no duplicate audit-Doc block is proposed.

## Approval / sync ledger

Package ID: `PS-20260826-P27-BUTTON-RESTORE`

| Target                        | Approved scope                       | Applied/read back | Skipped/pending | Blocked |
| ----------------------------- | ------------------------------------ | ----------------- | --------------- | ------- |
| Defense paper                 | none; no replacement proposed        | —                 | —               | —       |
| ADAS_Paper_Audit plus tracker | block 1 only after explicit approval | —                 | block 1         | —       |
| Standalone comments           | none                                 | —                 | —               | —       |
