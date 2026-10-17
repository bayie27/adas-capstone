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

- [ ] Verify P4's merged commit and read prior package evidence before running anything. A green pre-PR gate is evidence only for its actual commit/environment. Do not re-run all passing suites just to fill a report.
- [ ] Map every TEST_MATRIX row to an actual test/manual result. Inspect assertions rather than accepting a function name as proof. Add/fix a narrowly scoped test for an uncovered behavior in the owning module if needed; record any resulting code change and run its applicable checks.
- [ ] Separate inherited failures, skips, unavailable tools, expected denial cases, and real regressions. The planning baseline's global/isolated CORS mismatch is not a permanent waiver for auth test failure.
- [ ] Verify no MFA-disable/admin-reset/password-only mint route, seed/query token, plaintext DB recovery code, secret-bearing artifact, permanent bypass flag, or reusable committed key was introduced. Use tracked-source searches plus tests, not an assertion that grep alone proves security.
- [ ] Preserve human prerequisites. If no real phone/TLS client/protected backup device is available, label the exact drill Not run with the requirement and expected evidence; finish independent documentation/proposals. Do not call all MFA acceptance complete while required checks remain unresolved.

## Task 2 — isolated operational drills

- [ ] On disposable DB/accounts and a stable separately generated test key, run initial enrollment, ordinary login, wrong/replayed proof, logout/password-change/admin revocation, recovery interrupted before confirmation, and recovery completion. Capture only safe metadata and test ids; do not capture QR/manual keys/codes.
- [ ] Demonstrate voluntary replacement cancel leaves old factor working; confirm signs out everywhere and preserves code display until acknowledgment. Demonstrate code rotation keeps sessions and invalidates the old batch. Include an enabled-demo session using fresh factor proofs and a disabled-demo denial.
- [ ] Run an isolated backup/restore drill: take snapshot A, change factor/recovery state, restore A with its stable key, verify sessions/challenges are unusable, and verify A's factor/recovery state returns. Use an expendable code to demonstrate rollback resurrection explicitly; do not claim used-code invalidity across database restores.
- [ ] Repeat candidate preflight with key missing, structurally malformed, well-formed wrong, corrupt ciphertext, and pre-MFA/older schema. The live disposable primary remains untouched on rejection. Exercise emergency rollback and prove its pre-outage sessions also fail after restart.
- [ ] Where a human phone/client is available, verify QR and manual setup, local authenticator storage/cloud-sync-disabled instructions, real clock synchronization, HTTPS Secure cookie/WS operation, and keyboard/mobile-width usability. A browser-generated TOTP proves protocol behavior, not physical-device policy enforcement.
- [ ] Record actual elapsed readiness/restore observations. The paper's existing 60-second recovery target is not automatically satisfied because unit tests pass. Do not invent performance results or alter that requirement to match a slow drill.

## Task 3 — operations and user guidance

- [ ] Document a key-generation command using `uv run python` with Fernet.generate_key and a secure local operator workflow. Do not put the key into shell history, PR descriptions, screenshots, process arguments, normal backup manifests, shared cloud notes, or this pack. Use restricted local storage and an independently secured offline escrow copy; document the chosen deployment's ACL/physical custody requirements without pretending ADAS enforces them.
- [ ] Explain the stable-key v1 lifecycle: retain the correct escrow key for retained backups; copying only the DB to a replacement host is insufficient. Wrong key causes startup/preflight failure. No rotation CLI or unapproved lost-key reset is included.
- [ ] Write development-cutover prerequisites: verified backup, escrow test, matching migration head, required key, explicit operational DEV_TOOLS_ENABLED=false, non-demo users, time sync, and planned enrollment access. Real production scheduling with CDRRMO remains a later human decision.
- [ ] Explain restore's snapshot semantics and reauthentication requirement. An old factor or recovery code can return; review restored accounts and replace retired factors/batches through valid normal proofs before operational acceptance. Do not advise restoring a compromised factor as a routine recovery technique.
- [ ] Document supported current-head restore and refusal of older/pre-MFA snapshots. Rollback across application versions uses a verified compatible backup and matching code under a separate operator procedure; no silent schema migration or destructive downgrade.
- [ ] User help must explain one-time codes, storing them away from the phone, the final-code/interrupted-flow consequence, next-code waiting after reuse, replacement vs recovery, and no in-app/admin reset. No debug/database editing instructions appear in end-user UI.

## Task 4 — local paper and validation proposals

- [ ] Invoke adas-paper-sync for the actual MFA implementation range, following the current procedure. First triage claim-bearing changes and deduplicate local findings/live tracker. Read the live defense Doc and paper audit tracker through configured tools; the supplied PDF is a reference, not current live state.
- [ ] Propose exact per-site OLD/NEW blocks and required redraws for authentication FR-01, audit FR-20/NFR-21, session NFR-19, localization NFR-20, login use case/UI/flows, schema/data dictionary, dependencies/deployment/key escrow, help, and authentication/security validation. Reverify every page/site, including any changes since the PDF.
- [ ] NFR-20 needs an explicit authenticator-device exception: the app provisions a seed locally to the user's authenticator, keeps its encrypted server copy, and uses no external delivery/identity service. Phone storage falls outside the current server-drives-only sentence. Cloud sync disabled is an operational/user policy, not an enforceable ADAS guarantee or a statement that all authenticator products lack cloud services.
- [ ] Distinguish implemented security behavior from measured validation outcomes and future operational rollout. Local proposals must not rewrite an unexecuted device/restore/performance test as a pass.
- [ ] Prepare corresponding local proposals for the live test execution/validation Doc and execution tracker only after reading their current structure. Use actual new MFA test ids/evidence and preserve existing case ids/rows; do not fabricate sheet ranges from an old snapshot.
- [ ] Follow paper_sync's exact evidence, revision/page-mapping, finding, tracker-generation, and approval-manifest rules. If a connector/artifact/page mapping is unavailable, retain independent evidence and label affected proposals draft/blocked. No Drive writes or comments are authorized by this package.

## Verification and completion

For prose-only changes run scoped Prettier/reference checks and any existing generators whose source content changed. Run help tests when help content/seeding changes. If code/tests changed, run narrow checks and the applicable pre-PR full:check gate. Every package PR still has the required `pnpm full:check`; avoid separate redundant full-suite confirmation runs.

Walk matrix V01–V05 and reconcile all earlier rows. Keep sensitive raw material outside tracked evidence. Final report lists verified implementation behavior, evidence locations, failed/unavailable checks, remaining real-device/deployment work, and local proposals awaiting human approval. An evidence checklist with Not run items is honest documentation, not completed MFA release acceptance.

## Completion notes — executor fills

- Status: Not started.
- Tested merged commit/environment and reused prior gate evidence: Not recorded.
- Isolated drills, measured timings, real-device/TLS observations: Not executed.
- Documentation/help/reference/generator/pre-PR results: Not executed.
- Paper finding id, live revisions/page mapping, validation proposal locations: Not recorded.
- Drive writes: Not authorized; none should be performed.
- Remaining blockers, human prerequisites, branch/commit/PR: Not recorded.

Update the overview row honestly. Stop after this handoff's work and report; do not merge, deploy, repair user factors, or apply shared-document proposals automatically.
