# Luna Max conversation kickoff prompts

Start each prompt manually in a **new Luna Max conversation** at the repository root. Select Luna and Max yourself; these prompts do not change models or start agents. Execute one package per conversation, inline, with one PR per package. The next package waits for its predecessor to merge.

Before starting, inspect [00_OVERVIEW.md](00_OVERVIEW.md)'s status/merge evidence and your current working tree. The planning baseline had unrelated staged, unstaged, and untracked work. A package is never permission to stash/drop it, stage everything, reseed a live database, or overwrite another person's changes.

Each prompt defines the implementation scope. Commit owned changes after appropriate verification. Prepare a review-ready PR description; push/create the package PR when authorized by the human's executing conversation. Do not assume authorization to merge. When a push is authorized, let its hook run pnpm check; do not run it manually first. Always run the required pnpm full:check pre-PR gate and separate migration checks when applicable.

## P1 — storage and test foundation

```text
Implement only P1 from docs/plans/mfa/02_PKG_foundation.md.

Read AGENTS.md, CLAUDE.md, CONTRIBUTING.md's migration procedure,
docs/plans/mfa/00_OVERVIEW.md, 01_CONTRACTS.md, the P1 handoff, and P1 rows
in TEST_MATRIX.md. Inspect current main and working-tree changes first.
Use branch feat/mfa-foundation from the updated main, isolated from unrelated
work according to repository/worktree rules. Do not discard or include that work.

Execute inline in this conversation, without automatic implementer agents,
new chats, or model changes. Add the additive storage/dependencies/helpers
and isolated E2E harness exactly as P1 specifies. Keep existing login working:
no live-session revocation, no registered MFA router, no startup key requirement
yet, no password-only bypass flag, and no real .env/database changes.

Use meaningful test-first steps for code changes; run from repo root with
uv run python, never bare Python. Prove migration preservation, trigger/index
survival, safe downgrade refusal, and schema equivalence on disposable DBs.
Fix the specific global/app CORS test mismatch without weakening middleware.
The browser gate must not reuse or enroll the developer's running database.

Complete P1's checks, matrix walk, and pnpm full:check at the pre-PR point.
Record actual results/dependency versions/limitations in P1 completion notes
and the overview row. Commit only owned files and prepare the package PR.
Push/create it only with this conversation's authorization; never merge it.
Report its verification and PR-ready summary, then stop. Do not start P2.
```

## P2 — backend flow and dormant API

```text
Implement only P2 from docs/plans/mfa/03_PKG_backend.md.

Read AGENTS.md, CLAUDE.md, docs/plans/mfa/00_OVERVIEW.md, 01_CONTRACTS.md
in full, the P2 handoff, and matrix B/C rows. Verify P1 is actually merged
and its models/helpers/harness and completion results exist on current main.
Use branch feat/mfa-backend from that merged state, preserving unrelated work.

Execute inline in this manually started conversation; do not dispatch automatic
implementer agents or start other chats. Implement the exact service/API contract
with service-owned transactions, audited one-use TOTP/recovery acceptance, and
file-backed independent-connection concurrency tests. Token/seed/code/log leakage,
audit rollback, interrupted recovery, replacement, and rotation are required.

The MFA router remains unregistered in the normal app. Test the adapter with
an isolated test app; keep actual POST /api/auth/login behavior unchanged until P4.
No debug auth endpoint, automatic MFA enrollment, plaintext fallback, reset route,
or permanent bypass flag. Demo proof checks follow the frozen contract.

Run from repo root; use uv run python. Do the package's focused red/green checks,
matrix walk, relevant lint/format, then pnpm full:check at the pre-PR gate.
Update P2 completion notes/overview with real results and deviations; commit only
owned changes and prepare the package PR. Push/create it only within this
conversation's authorization; never merge. Report and stop; do not start P3.
```

## P3 — inactive frontend screens

```text
Implement only P3 from docs/plans/mfa/04_PKG_frontend.md.

Read AGENTS.md, CLAUDE.md, docs/plans/mfa/00_OVERVIEW.md, 01_CONTRACTS.md,
the P3 handoff, and matrix U rows. Verify P1/P2 are merged and inspect their
actual exported API/types first. Use branch feat/mfa-frontend from updated main;
preserve all unrelated changes. Execute inline without automatic agents/chats.

Build the typed MFA adapters and focused Login/enrollment/recovery/Profile
components using current house UI patterns and qrcode.react. Match the shared
discriminants exactly. Leave production Login/Profile wiring unchanged until P4.
Secrets stay only in component memory and explicit user copy/download; no query
cache, storage, URL, console, remote QR service, or durable response redisplay.

Test meaningful interactions and failures: QR/manual consistency, challenge
refresh/expiry, persistent rate limit, code acknowledgment/download failure,
replacement cancellation/sign-out handoff, and proof errors that do not erase a
valid session. Physical device/TLS behavior is not proven by component mocks.

Run the focused tests/typecheck/lint/format and the required pnpm full:check
pre-PR gate. Update P3 notes/overview, commit owned files, and prepare the PR.
Push/create it only within this conversation's authorization; do not merge or
start P4. Report tested behavior, exact results, and known limitations.
```

## P4 — integrated cutover

```text
Implement only P4 from docs/plans/mfa/05_PKG_cutover.md.

Read AGENTS.md, CLAUDE.md, CONTRIBUTING.md migrations, docs/plans/mfa/
00_OVERVIEW.md, 01_CONTRACTS.md in full, the P4 handoff, matrix X/R rows,
and current maintenance/restore rules. Verify P1-P3 are merged, with their
actual service/type/component contracts. Use branch feat/mfa-cutover from
updated main. Preserve unrelated launcher/maintenance/operations edits.

Execute inline in this manually started Luna Max conversation. Activate both
stacks together: mandatory MFA, exact login responses, explicit session methods,
legacy-session revocation migration, challenge invalidation, no-store/error rules,
startup key checks, constrained/labeled demo sessions, and restore/rollback safety.
No permanent bypass flag, disabled audit, relaxed origin checks, or fixture-only
production authentication path. Do not deploy/enroll operational users.

The replacement recovery-code screen must survive auth clearing and either
WebSocket/HTTP completion order. Put transient code presentation outside protected
route guards; do not persist it or leave auth redirection suppressed indefinitely.
Restore uses compatible candidate copies, validates the stable key, invalidates
sessions/challenges on restore and emergency rollback, and never changes backups.

Migrate test helpers/CI/scripts and run real browser MFA on disposable accounts.
Never use dev impersonation or mocked MFA endpoints as proof of normal login.
Do not capture seeds/codes/cookies in browser traces or artifacts. Run narrow
checks, the separate migration procedure, matrix walk, and pnpm full:check.

Record actual results/blockers in P4/overview, commit only owned files, and prepare
the package PR. Push/create only within this conversation's authorization.
Never merge, perform operational cutover, start P5, or write Drive. Report and stop.
```

## P5 — validation, operations, and local proposals

```text
Implement only P5 from docs/plans/mfa/06_PKG_validation_ops.md.

Read AGENTS.md, CLAUDE.md, docs/plans/mfa/00_OVERVIEW.md, 01_CONTRACTS.md,
the P5 handoff, the whole TEST_MATRIX.md, prior completion notes, current help/
operations/validation sources, and paper_sync/PROCEDURE.md. Verify P4 is merged.
Use branch docs/mfa-validation-operations from updated main; preserve unrelated work.
Execute inline; do not automatically dispatch implementers or start conversations.

Audit actual acceptance assertions/evidence, fill genuine gaps, perform isolated
restore/escrow/security drills, and document user/operations procedures and results.
Reuse already passing evidence for the same commit when appropriate; do not run
redundant full-suite confirmation checks. This package PR still needs full:check.
Never call an unrun physical-phone/LAN-TLS/protected-device drill a pass.

Use adas-paper-sync for the actual implementation range. Read current live paper/
trackers, deduplicate existing findings, and prepare exact local proposals plus
validation updates. NFR-20 needs an explicit authenticator-device storage exception;
cloud sync disabled is policy, not something ADAS can verify. The supplied PDF is
a reference snapshot. No Drive writes/comments, production cutover, or DB repair
are authorized. Missing connector/device evidence blocks only dependent conclusions.

Complete scoped documentation/help/generator/code checks and the pre-PR gate.
Update P5/overview/matrix evidence with real commit/environment/results/blockers,
commit owned files, and prepare the PR. Push/create only within this conversation's
authorization. Never merge or apply live-document proposals automatically.
Report deliverables and remaining human prerequisites, then stop.
```
