# P5 — MFA verification, operations, and local paper proposals

> **For agentic workers:** Execute inline in this manually started Luna Max conversation. Verification uses disposable environments unless the human separately authorizes a specific live drill. No Drive writes, production cutover, database repair, automatic merging, or automatic follow-up conversations.

**Goal:** Deliver traceable MFA acceptance evidence and usable operations/help documentation, plus local paper/test proposals reflecting verified implementation.  
**Branch:** `docs/mfa-validation-operations`, from P4's merged main.  
**Read:** All pack completion notes, test matrix, CLAUDE.md, current operations/help/test guides, paper_sync/PROCEDURE.md.  
**Prerequisites:** P1–P4 merged and P4's activation, migration, default E2E, key/restore/demo checks recorded. An unresolved P4 acceptance defect is a task-related blocker to fix or explicitly carry, not a documentation pass.

**Architecture:** Reconcile real implementation evidence with the test matrix, exercise isolated operational recovery, and produce local documentation/proposals.  
**Tech stack:** Existing pytest/Vitest/Playwright and maintenance tooling, Markdown/Prettier, connected Drive reads under paper-sync safeguards.  
**Spec:** [01_CONTRACTS.md](01_CONTRACTS.md), the overview's locked decisions, and current paper_sync/PROCEDURE.md.

## Owned outputs

- Create `docs/operations/MFA.md`: account enrollment, recovery/replacement, code saving, key generation/escrow, deployment preflight, restore, rollback, and lockout consequences.
- Create `docs/validation/mfa-validation.md`: scenario-to-test mapping, exact tested commit, environment, commands/exit results, evidence paths, manual observations, limits, and unexecuted prerequisites. It must distinguish planning baseline from implementation evidence.
- Update relevant help articles under `backend/app/services/help.py`'s actual content source, current operations setup links, and local validation guidance. Inspect the source layout first; do not invent a new competing help system.
- Create a new finding under `paper_sync/findings/` and regenerate the local paper_sync/TRACKER.md only under its procedure. Reuse pending existing MFA findings rather than duplicating sites. Prepare local proposed validation-plan/tracker updates; do not edit the shared Docs/Sheets.
- Fill the pack's completion notes/overview and TEST_MATRIX.md Evidence ledger with actual results. Do not rewrite historical archive evidence or the planning baseline.

## Task 1 — evidence audit and missing acceptance checks

- [x] Verify P4's merged commit and read prior package evidence before running anything. A green pre-PR gate is evidence only for its actual commit/environment. Do not re-run all passing suites just to fill a report.
- [x] Map every TEST_MATRIX row to an actual test/manual result. Inspect assertions rather than accepting a function name as proof. P5 added a narrow recovery-code snapshot-resurrection assertion in the owning restore test module.
- [x] Separate inherited failures, skips, unavailable tools, expected denial cases, and real regressions. The P5 Windows `uv` trampoline/default-temp issues are recorded separately from the passing Python-module test run.
- [x] Verify no MFA-disable/admin-reset/password-only mint route, seed/query token, plaintext DB recovery code, secret-bearing artifact, permanent bypass flag, or reusable committed key was introduced. The conclusion combines source and assertion review; searches alone are not treated as proof.
- [x] Preserve human prerequisites. P5 labels physical phone/authenticator, second-client LAN/TLS, and external offline-escrow checks Not run; no MFA acceptance is described as complete.

## Task 2 — isolated operational drills

- [x] Reuse same-tree P4 disposable browser/backend evidence for enrollment, ordinary login, wrong/replayed proof, logout/password-change/admin revocation, recovery, replacement/rotation, and demo gating; do not rerun the same full suites just to fill the report.
- [x] Reuse P4 replacement/code-display/rotation assertions and demo-factor tests from the recorded P4 full gate; preserve their actual automated evidence type.
- [x] Run the one-laptop snapshot/restore exercise with a separately generated test key and expendable recovery code. The safe result shows snapshot state and code resurrection, invalidation, and unchanged backup/manifest.
- [x] Run missing/malformed/wrong/corrupt-key and pre-MFA schema refusal cases in the disposable restore suite. Exercise emergency rollback, then start a fresh loopback backend and confirm the pre-restore cookie is rejected with `401 AUTH_REVOKED`.
- [ ] Physical QR/manual entry, device storage/cloud-sync settings, phone clock, second-client LAN HTTPS/Secure-cookie/WebSocket, and mobile-width observation were Not run because the authorized scope was one laptop and no phone/client was available.
- [x] Record actual elapsed observations: 130.31 ms for the restore function, 95.46 ms for rollback, and 4.279 s for fresh backend readiness. AI heartbeat and end-to-end restore-to-alert timing were not measured; the existing 60-second recovery target is not claimed as passed.

## Task 3 — operations and user guidance

- [x] Document Fernet key generation, restricted local storage, ACLs, separate physical escrow, and secret-injection guidance without exposing a key in shell history, process arguments, logs, screenshots, backups, PR text, or this pack. The P5 exercise verified only the laptop-local ACL; physical escrow remains Not run.
- [x] Explain stable-key v1, retention, replacement-host requirements, wrong-key failure, and absence of a rotation CLI or unapproved lost-key reset.
- [x] Document development cutover preflight, explicit operational `DEV_TOOLS_ENABLED=false`, non-demo accounts, time sync, backup/key readiness, and that production scheduling remains a human decision.
- [x] Explain restore snapshot semantics, reauthentication, old factor/code return, and why a compromised factor must not be restored as routine recovery.
- [x] Document current-head restore, pre-MFA refusal, compatible-code rollback, and no silent schema migration or destructive downgrade.
- [x] Add role-visible user help for one-time codes, recovery storage, final-code interruption, next-code waiting, replacement vs recovery, and no in-app/Admin reset. No database-edit instructions appear in the user article.

## Task 4 — local paper and validation proposals

- [x] Apply adas-paper-sync to the P4 implementation range, triage claim-bearing surfaces, inspect current local findings/comments and live audit tracker, and read the live defense Doc and current validation Doc/Sheet. The supplied PDF was treated only as a pre-MFA reference snapshot.
- [x] Prepare exact local OLD/NEW proposals for authentication FR-01/FR-03/FR-19, audit FR-20/NFR-21, session NFR-19, localization NFR-20, login/UI/use-case flow, active MFA schema wording, dependencies, restore/key custody, and validation evidence. Figure 4/8 redraw requirements are recorded; the existing P1 Figure 7 redraw is carried forward without duplication because current PDF inspection is blocked.
- [x] State the NFR-20 authenticator-device exception and distinguish user/operations cloud-sync policy from anything ADAS can inspect or enforce.
- [x] Keep implementation behavior, measured one-laptop results, and not-run device/LAN/escrow prerequisites separate in the local proposals.
- [x] Prepare additive live validation Doc and tracker proposals after reading current structures; existing case IDs remain unchanged. No live Sheet rows were invented as written evidence.
- [x] Follow `paper_sync/PROCEDURE.md`: current Doc revision and Sheet values are recorded, page mapping is pending after the live PDF export 403, local tracker was regenerated, and no Drive writes/comments were made.

## Verification and completion

For prose-only changes run scoped Prettier/reference checks and any existing generators whose source content changed. Run help tests when help content/seeding changes. If code/tests changed, run narrow checks and the applicable pre-PR full:check gate. Every package PR still has the required `pnpm full:check`; avoid separate redundant full-suite confirmation runs.

Walk matrix V01–V05 and reconcile all earlier rows. Keep sensitive raw material outside tracked evidence. Final report lists verified implementation behavior, evidence locations, failed/unavailable checks, remaining real-device/deployment work, and local proposals awaiting human approval. An evidence checklist with Not run items is honest documentation, not completed MFA release acceptance.

## Completion notes — executor fills

- Status: P5 implementation and scoped evidence prepared; required full gate pending.
- Base: updated `origin/main` at P4 merge `38a5c5d0d9d2a3abeae6df2470b52e76e1bf4ba8`; P4 branch tree `d39f0ba12d0d1dc7e855ecac522c3ad0b65587d4` matches. Reused P4 full-gate evidence: backend 1,375 passed/5 skipped, frontend 395 passed, build passed, Chromium E2E 6/6.
- P5 environment: Windows 10.0.26200.0, Python 3.12.13, Node 22.23.1, pnpm 11.17.0; one laptop only. `test_help.py` + `test_mfa_restore.py`: 40 passed. A second targeted restore run after adding the rollback-cookie assertion: 8 passed. Ruff format/lint, scoped Prettier, local relative-link reference check, and paper tracker generator passed.
- One-laptop drill: restore 130.31 ms, rollback 95.46 ms, fresh loopback backend readiness 4.279 s; the pre-restore cookie was rejected with 401 `AUTH_REVOKED`. The 60-second restore-to-alert target is not established because no AI heartbeat was measured. Laptop-local key ACL and backup/manifest exclusion passed. Physical phone, cloud-sync setting, second LAN client/TLS, and independent offline escrow/replacement host remain Not run.
- Safe evidence: `var/test-evidence/mfa-p5-one-laptop-e0bd670e26.json` and `var/test-evidence/mfa-p5-loopback-76edf34f0d.json`; disposable secrets and databases were removed. No production or working database was opened.
- Documentation/help and local paper/validation proposals are in `docs/operations/MFA.md`, `backend/content/help/`, `docs/validation/mfa-validation.md`, and `paper_sync/findings/2026-10-19-mfa-validation-operations.md`; tracker regenerated at `paper_sync/TRACKER.md` (35 findings).
- Paper-sync package: `PS-20261019-MFA-VALIDATION-OPERATIONS`. Current live Doc and validation Doc/Sheet were read; live PDF export returned 403, so current page mapping is pending. No Drive writes/comments were made.
- Pre-PR `pnpm full:check`, exact tested commit, push, and PR: pending. No manual `pnpm check` was run; the authorized push hook owns that check.
- Remaining human prerequisites: physical authenticator/storage and cloud-sync policy observation, second-client LAN HTTPS/Secure-cookie/WebSocket and clock check, independent offline escrow custody and replacement-host drill, and end-to-end restore-to-AI-heartbeat timing. Do not treat the package as release acceptance.

Update the overview row honestly. Stop after this handoff's work and report; do not merge, deploy, repair user factors, or apply shared-document proposals automatically.
