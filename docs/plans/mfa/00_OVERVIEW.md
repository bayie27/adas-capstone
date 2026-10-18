# MFA implementation — Luna Max execution overview

**Status:** P1–P4 are merged. P5 has one-laptop restore/help evidence and local paper/validation proposals on `docs/mfa-validation-operations`; its required full:check and PR are pending. Physical authenticator, second-client LAN/TLS, and independent offline-escrow checks remain not run.
**Approved scope:** Mandatory TOTP for normal local ADAS authentication.  
**Execution:** Five sequential, manually started Luna Max conversations; one PR per package.  
**Planning baseline:** 2026-10-17, main at `9bc7a29`. Reinspect the repository before execution.

This directory is the implementation handoff. The [original high-level plan](../mfa-implementation-plan.md) is historical context; its conflicting recovery rules and documentation-only test statement do not govern this pack. Archive documents supplied the handoff format, not current implementation rules.

## Read order and authority

1. The human's latest explicit instructions and the accepted decisions below.
2. Current [AGENTS.md](../../../AGENTS.md) and [CLAUDE.md](../../../CLAUDE.md), including migration, audit, UTC, service-layer, and verification rules.
3. [01_CONTRACTS.md](01_CONTRACTS.md), the shared technical contract.
4. Your package and its rows in [TEST_MATRIX.md](TEST_MATRIX.md).
5. [CONTRIBUTING.md](../../../CONTRIBUTING.md), current source, and prior packages' completion notes.

Facts in these documents describe the inspected baseline, not an instruction to overwrite intervening changes. Reconcile file moves and implementation details against current code. Preserve the accepted behavior; report material contract changes rather than silently replacing decisions.

## Locked product decisions

| ID  | Decision                                                                                                                                                                                                                                                               |
| --- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| D01 | All existing and future normal Operator/Admin accounts require an authenticator app. No remembered-device, password-only grace period, MFA-disable route, or administrator MFA-reset route.                                                                            |
| D02 | Password validation creates only a restricted challenge. A full session, `last_login`, and `LOGIN_SUCCESS` occur only after completed MFA. The normal eight-hour maximum, cookie contract, DB role checks, and revocation remain.                                      |
| D03 | A recovery code disables the old authenticator immediately and revokes all sessions. Consume only the submitted code initially; retain unused codes so interrupted recovery can restart. Successful enrollment invalidates the remaining batch and issues a new batch. |
| D04 | Voluntary replacement preserves the working old factor until new-factor confirmation. Confirmation replaces recovery codes and signs out everywhere. Cancellation/expiry leaves the old factor intact.                                                                 |
| D05 | Recovery-code rotation requires the password and a fresh current TOTP, replaces the batch, and leaves sessions active.                                                                                                                                                 |
| D06 | Recovery codes have Copy and Download .txt controls and an acknowledgment before continuing. Plaintext lives only in component memory and the user's explicit saved copy. Acknowledgment is a UI step, not proof that the user stored the codes.                       |
| D07 | Preserve demo switching/reseed behind `DEV_TOOLS_ENABLED`, explicitly mark their sessions as impersonation, and reject those sessions when demo tooling is off. Demo sessions may manage MFA only after the same fresh factor proofs required of a normal user.        |
| D08 | After cutover, missing/malformed key material prevents startup. Use a dedicated stable Fernet key, securely escrowed locally and excluded from normal backups. No rotation utility in v1. Wrong-key and corrupt-ciphertext checks also fail closed.                    |
| D09 | Restore the selected backup's MFA snapshot. Invalidate restored sessions/challenges; document that older seeds/codes can revive. No external anti-rollback credential ledger in v1.                                                                                    |
| D10 | Separate sequential PRs. No package auto-merges itself or starts the next conversation. New behavior activates together in P4.                                                                                                                                         |
| D11 | P5 prepares local evidence-backed paper/tracker proposals only. Live Drive writes require separate explicit approval.                                                                                                                                                  |

If the phone and all usable codes are lost, there is no application recovery path. An interrupted recovery using the final available code can also exhaust that path if its challenge is lost. Out-of-band database repair is separately authorized work, not a hidden endpoint or a procedure automated by this pack.

## Engineering defaults adopted after the interview

The user ended the interview and requested recommended defaults for remaining engineering details. These are implementation defaults, not additional answers attributed to the user:

- Six digits, 30-second TOTP step, SHA-1 interoperability default, acceptance at current step ±1, and global per-factor replay prevention.
- Five-minute login challenges; fifteen-minute initial/recovery/replacement enrollment challenges. Deadlines do not slide on refresh or invalid submissions.
- One active challenge per account. A new password-verified flow replaces the older challenge and pending seed; it never clears recovery-pending account state.
- Opaque 256-bit challenge tokens, stored only as SHA-256 digests server-side. Challenge status can resume the flow on refresh without browser storage of credentials.
- Ten unique 128-bit recovery codes per batch; exact encoding and hashing are fixed in the contract.
- No permanent MFA bypass flag, plaintext seed fallback, auto-generated production encryption key, or automatic key rotation.
- Keep ordinary password-change/admin-password-reset behavior; invalidate MFA challenges along with the existing session revocations. Do not add TOTP to unrelated privileged actions in this release.

## Package order

| Package | Handoff                                              | Branch                           | Depends on   | Application state after merge                                                                                                  |
| ------- | ---------------------------------------------------- | -------------------------------- | ------------ | ------------------------------------------------------------------------------------------------------------------------------ |
| P1      | [02_PKG_foundation.md](02_PKG_foundation.md)         | `feat/mfa-foundation`            | Current main | Additive schema/helpers and safe E2E harness; existing login still works.                                                      |
| P2      | [03_PKG_backend.md](03_PKG_backend.md)               | `feat/mfa-backend`               | P1 merged    | Complete service/API flow tested in isolated apps; MFA router remains unregistered in normal app.                              |
| P3      | [04_PKG_frontend.md](04_PKG_frontend.md)             | `feat/mfa-frontend`              | P2 merged    | Tested MFA components and API adapters; current login/profile remain wired to their existing flow.                             |
| P4      | [05_PKG_cutover.md](05_PKG_cutover.md)               | `feat/mfa-cutover`               | P3 merged    | MFA enforced end to end, rollout revocation, startup/restore/demo/CI integration complete.                                     |
| P5      | [06_PKG_validation_ops.md](06_PKG_validation_ops.md) | `docs/mfa-validation-operations` | P4 merged    | Verification evidence, operations/help documentation, and local paper/test proposals complete to the extent actually executed. |

Create each branch from the updated merged predecessor, not from another unfinished feature branch. Inspect attached/current worktrees and follow the worktree skill when isolation is needed. Existing uncommitted work is not permission to stash, discard, reseed, or include it. Never run integration tests against the operator's live database.

## Execution rules for every conversation

- Start with the package's prompt in [PROMPTS.md](PROMPTS.md); execute inline in that manually started conversation. Do not automatically create chats, dispatch implementer agents, change models, or merge PRs.
- Run from the repo root. Use `uv run python`, never bare Python. Use narrow meaningful red/green behavior tests for application changes; prose-only work needs formatting/reference verification.
- Services own transactions and business rules. New authentication endpoints must not extend the existing inline login implementation with more route-owned business logic.
- Use real Alembic migrations and `UtcDateTime`. Test upgrade/downgrade and schema equivalence with disposable databases. Preserve append-only audit triggers and existing indexes/rows.
- Do not edit `ai_engine/`, frozen research artifacts, real `.env`, live databases, or historical archives. Operations files already have unrelated edits at the planning baseline: preserve them and integrate only relevant MFA changes.
- Each code package includes the narrow tests it needs. Schema/core/conftest/app-factory changes require the full backend scope under CLAUDE.md. `pnpm full:check` is required once at the pre-PR gate; it is not a per-step check. Do not separately rerun a passing full suite just because the PR is next.
- If a push is authorized in the executing conversation, the pre-push hook runs `pnpm check`; do not run that command manually before it. Never skip hooks. Migration checks are additional to `full:check`.
- Commit only owned files with Conventional Commits. Prepare the package PR after its checks; push/create it only within that conversation's authorization. Never merge it automatically. Attach a created PR with the app tool when available.
- Report baseline failures, unavailable checks, and unexecuted manual drills honestly. They are not passes. Fix regressions introduced by this work without broadening into unrelated repairs.

## Review focus across packages

Review these seams explicitly rather than accepting happy-path completion: interrupted recovery must require another unused proof (B06); independent-connection one-use races must have one winner (C01–C03); wrong-key restore and emergency rollback must never revive sessions (R02/R04); code display must survive sign-out/socket ordering without persisting secrets (X08); and staged PRs must keep the old app usable without publicly activating unfinished MFA (G03/U08). Each has an owning test row and package.

## Completion ledger

The completion ledger reflects current execution state. The planning tests below are not implementation evidence.

| Package | Status      | Branch/PR                                                                         | Merge commit | Evidence                                                                                                                                                                                                                                                                                                                                                      |
| ------- | ----------- | --------------------------------------------------------------------------------- | ------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| P1      | Merged      | `feat/mfa-foundation` / [#241](https://github.com/bayie27/adas-capstone/pull/241) | `8b6778c`    | Merged into main; P1 completion notes record migration, matrix, isolated E2E, and `pnpm full:check` results.                                                                                                                                                                                                                                                  |
| P2      | Merged      | `feat/mfa-backend` / [#242](https://github.com/bayie27/adas-capstone/pull/242)    | `796ea43`    | Merged into main; the P2 implementation commit is `a013139`.                                                                                                                                                                                                                                                                                                  |
| P3      | Merged      | `feat/mfa-frontend` / [#243](https://github.com/bayie27/adas-capstone/pull/243)   | `59b32a8`    | Implementation commit `b12176a`; merged into updated main. P3's typed adapters and MFA components were still inactive before P4.                                                                                                                                                                                                                              |
| P4      | Merged      | `feat/mfa-cutover` / [#244](https://github.com/bayie27/adas-capstone/pull/244)    | `38a5c5d`    | P4 branch tree `d39f0ba12d0d1dc7e855ecac522c3ad0b65587d4`; recorded `pnpm full:check` passed: backend 1,375/5 skipped, frontend 395/62 files, build passed, isolated Chromium 6/6. P5 reuses this evidence.                                                                                                                                                   |
| P5      | In progress | `docs/mfa-validation-operations` / PR pending                                     | —            | Implementation commit `8d4ccfd` passed `pnpm full:check`: backend 1,377/5 skipped, frontend 395, build passed, Chromium E2E 6/6. Scoped help/restore selectors: 40 passed. One-laptop restore/rollback and fresh-backend cookie rejection recorded. Physical device, second-client LAN/TLS, AI heartbeat, and offline escrow remain not run; push/PR pending. |

Each executor fills its package's Completion notes and its row here with actual commands, exit results, deviations, unresolved blockers, and PR URL. Do not invent a merge SHA; the next conversation verifies the merge and can record it. P5 assembles final evidence from those notes rather than repeating passing checks without cause.

## Planning baseline — existing behavior only

Observed during this planning conversation on 2026-10-17:

- `pnpm --filter frontend test:run src/pages/Login.test.tsx src/pages/ProfileSettings.test.tsx`: **2 files, 11 tests passed**. Existing jsdom media-method messages and a Vite config warning were emitted.
- `uv run --no-sync pytest backend/tests/test_auth.py backend/tests/test_sessions.py -q`: exited 1 with one reported failure, `TestOriginValidation::test_listed_origin_allowed` (403 instead of 204). The test takes an origin from process-global settings while its app uses isolated Settings defaults.
- Rerunning only that failure with process-local `CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173` passed. This diagnoses an environment/fixture mismatch; no source fix was made and no all-green backend-suite claim follows from it.
- Sandbox cache/runtime/path restrictions initially prevented the commands from launching. The actual test runs used approved execution outside that restriction; no application configuration was edited.

At this 2026-10-17 planning baseline, MFA tests, migration drills, browser MFA flows, real-device enrollment, and production rollout had **not** been executed. P4 execution and disposable migration/browser evidence are recorded in [05_PKG_cutover.md](05_PKG_cutover.md); real-device enrollment and production rollout remain unexecuted. No Drive writes were made.

## Paper boundary

On 2026-10-19, the current live `REVISED_FINAL_PAPEL` Doc was read at revision `AHj4eMQav9NTp-JdnzxZPpnhaBQpO7QY5xTbQwF6Uydfi0KNP2-Y6Kabt2tzkZIwQnzDTqFaRl_nKPMgIhEn1__RLrTYxZ2OUvh6BdXOhFE`. Its NFR-20 still says all data is stored/processed exclusively on the edge server's physical drives. TOTP also provisions a seed to the user's authenticator device. The live PDF export returned 403; the supplied repository PDF is a 246-page pre-MFA snapshot and cannot establish current page numbers. P5's draft proposes an explicit authenticator-device exception and states that cloud-sync policy is not technically enforceable by ADAS.

Use [paper_sync/PROCEDURE.md](../../../paper_sync/PROCEDURE.md) and fresh live artifact reads before any later write. Exact OLD passages were re-read; current rendered pages remain pending. No Drive writes or comments were made.
