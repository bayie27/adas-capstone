# MFA acceptance and evidence matrix

**Status:** P1–P4 results are recorded in their completion notes. P5 `pnpm full:check` passed on implementation commit `8d4ccfda5ba332f8ec6ec5e54752ebefd6e6c1ef`; physical device, LAN/TLS, and independent escrow prerequisites remain not run.
**Spec:** [01_CONTRACTS.md](01_CONTRACTS.md). Package owners are the five handoffs in [00_OVERVIEW.md](00_OVERVIEW.md).

Tests prove changed behavior, especially boundaries/failures/races. Do not chase a coverage percentage, duplicate the same happy path across five layers, or treat a skipped/manual test as a pass. Test names below are stable suggested names; exact module ownership and asserted outcomes are required. Executors record renamed tests in their package notes.

## Foundation — P1

| ID  | Assertion                                                                                                                             | Primary evidence                                                              |
| --- | ------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------- |
| F01 | Upgrade real preceding revision with populated user/session/audit/camera/incident data; rows/ids/timestamps/indexes preserved.        | test_mfa_migrations.py::test_foundation_preserves_populated_previous_revision |
| F02 | CHECK/FK/unique constraints reject invalid states/methods/duplicate challenges/code hashes; one challenge per user.                   | test_mfa_migrations.py::test_mfa_checks_and_foreign_keys                      |
| F03 | Audit UPDATE/DELETE remain blocked after catalog rebuild; new actions accepted, unknown actions rejected.                             | test_mfa_migrations.py::test_audit_triggers_survive_constraint_rebuild        |
| F04 | Current migration matches model schema; empty downgrade succeeds; populated MFA downgrade refuses before destruction.                 | Schema verifier + named downgrade tests                                       |
| F05 | RFC TOTP vector/leading zero/ASCII input/±1 window and boundaries produce exact matched steps with aware explicit time.               | test_mfa_crypto.py                                                            |
| F06 | Fernet roundtrip, malformed/wrong keys/corrupt tokens fail; secrets do not appear in assertion/error output.                          | test_mfa_crypto.py                                                            |
| F07 | Challenge digest and canonical recovery hashes are stable, user/generation separated; generated batches have 10 unique 128-bit codes. | test_mfa_crypto.py                                                            |
| F08 | Missing key remains staged-config constructible; malformed key rejected without echo; no active startup requirement before cutover.   | test_config.py + existing-login test                                          |

## Isolated integration foundation — P1

| ID  | Assertion                                                                                                                             | Primary evidence                                       |
| --- | ------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------ |
| G01 | Default Playwright run owns unique scratch DB/paths/ports; refuses user DB and unrelated running services.                            | test_e2e_runner.py + isolated functional login         |
| G02 | Test credentials/key flow through environment; no .env mutation or reusable key committed. Fresh Alembic provisioning, no create_all. | Runner tests/source inspection                         |
| G03 | Listed-origin test reads app settings; middleware still rejects unlisted origins. Default login works through P3.                     | test_auth.py::TestOriginValidation + e2e/login.spec.ts |

## Backend state machine — P2

| ID  | Assertion                                                                                                                                                       | Primary evidence                         |
| --- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------- |
| B01 | Correct password returns discriminated challenge, not a session/profile; no last_login/LOGIN_SUCCESS. Generic unknown/inactive/wrong-password behavior remains. | test_mfa_service.py + test_mfa_api.py    |
| B02 | Absent credentials force enrollment; pending QR alone grants no app access; confirmed pending TOTP issues session/codes exactly once.                           | Service/API enrollment tests             |
| B03 | Expiry is inclusive; refresh never extends TTL or changes pending seed; newest password-verified flow invalidates previous challenge.                           | Controlled-clock challenge tests         |
| B04 | Wrong/malformed/expired/replayed TOTP creates no session/timestamp/success audit; codes are single-use across login and management.                             | Verification tests                       |
| B05 | Recovery immediately consumes one code/disables factor/revokes sessions; no full login yet.                                                                     | Recovery acceptance tests                |
| B06 | Interrupted recovery requires another unused code; password-only recovery_pending cannot reveal a new seed; last-code exhaustion is explicit lockout.           | Recovery restart/cancel/exhaustion tests |
| B07 | Recovery confirmation replaces remaining batch and creates a legitimate session/new used-step record.                                                           | Recovery completion tests                |
| B08 | Replacement fresh proofs; old factor remains through pending/cancel/expiry. Confirmation swaps factor/codes and revokes every session without minting another.  | Replacement tests                        |
| B09 | Rotation fresh proofs; old codes invalid, current sessions/version unchanged, outstanding challenge invalidated.                                                | Rotation tests                           |
| B10 | Demo management requires fresh password/TOTP, or password+new enrollment for an unenrolled demo account; no impersonation-based bypass.                         | Management authorization tests           |
| B11 | Independent account/IP failure limits and Retry-After; password success/restart/method switches do not clear MFA limits.                                        | MFA rate-limit tests                     |
| B12 | Exact API discriminants/error envelope/cookie flags/path/deletion/no-store; token confusion and secret-bearing validation errors rejected.                      | test_mfa_api.py                          |
| B13 | Secret sentinels absent from DB plaintext/audit/log/exception output; encrypted seeds and hashed codes only.                                                    | Redaction/storage tests                  |

## Transactions and races — P2

| ID  | Assertion                                                                                                                                                 | Primary evidence                                  |
| --- | --------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------- |
| C01 | Two independent SQLite connections submit one TOTP step: one successful session/action only.                                                              | test_mfa_concurrency.py, file-backed barrier test |
| C02 | One recovery code submitted concurrently: one consumption/transition; no duplicate challenge or success audit.                                            | Same, recovery race                               |
| C03 | Concurrent enrollment confirmations: one factor/batch/session; loser controlled, no plaintext redisplay.                                                  | Same, enrollment race                             |
| C04 | Injected audit failure rolls back login, consumed code/step, factor/batch change, session revoke/create, and timestamps; failure row only after rollback. | test_mfa_service.py rollback parametrization      |
| C05 | Password/state/version changed during proof verification or challenge lifetime causes safe rejection; busy handling does not partly commit.               | State-race/busy tests                             |

## Frontend components — P3

| ID  | Assertion                                                                                                                              | Primary evidence                               |
| --- | -------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------- |
| U01 | Typed adapters use cookies and exact form/JSON contract; password success is not treated as completed login.                           | src/api/mfa.test.ts                            |
| U02 | Accessible password→TOTP/recovery/enrollment flow; input/paste/leading-zero behavior and no pre-completion auth callback.              | MfaLoginFlow/MfaChallengePanel tests           |
| U03 | QR/manual key consistency, local app instructions, safe refresh/expiry/cancel, no provisioning in cache/storage/URL.                   | MfaEnrollmentPanel tests                       |
| U04 | Retry-After countdown persists across input/method changes; generic proof failures stay inline; true session expiry remains effective. | MFA/API error tests                            |
| U05 | Codes displayed once; explicit copy/download, object URL cleanup, failure handling, acknowledgment gating, memory cleanup.             | RecoveryCodesPanel tests                       |
| U06 | Replacement canceled vs confirmed, demo fresh proofs, rotation preserving session, safe status/remaining-count display.                | MfaSettingsCard tests                          |
| U07 | Lost response/reload offers login/rotation, not redisplay; no persisted plaintext or credential.                                       | Flow/component storage assertions              |
| U08 | Inactive components do not change ordinary production Login/Profile before P4; existing focused tests pass.                            | Existing Login/Profile tests + P3 browser gate |

## Integrated cutover — P4

| ID  | Assertion                                                                                                                                                       | Primary evidence                                       |
| --- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------ |
| X01 | Migration revokes all legacy/demo sessions once, clears staged challenges, atomically audits rollout, and preserves historical data/triggers.                   | test_mfa_cutover.py seeded real-revision tests         |
| X02 | Actual protected REST/WS reject password-only, pending challenge, copied challenge token, and legacy password sessions.                                         | Integrated API/WS tests + browser denial               |
| X03 | Valid MFA reaches role-correct dashboard with HttpOnly session; deadline remains <=8 hours from completed authentication.                                       | Auth/session + e2e login                               |
| X04 | Logout/password change/reset/deactivation/role change revoke sessions, invalidate challenges, and close sockets. Reactivation does not revive stale challenges. | Auth/user/realtime regressions                         |
| X05 | Wrong, used, expired, canceled, or superseded challenge never updates last_login or emits LOGIN_SUCCESS.                                                        | Integrated negative tests                              |
| X06 | Startup requires key in every environment; correct-shape wrong key/corrupt ciphertext refuses readiness before camera/background work.                          | Startup/config tests                                   |
| X07 | Demo paths remain authorized/flag-gated and labeled; disabling tooling rejects existing impersonation sessions for HTTP/WS.                                     | Dev/realtime tests                                     |
| X08 | Profile replacement code screen survives either socket/HTTP ordering and client sign-out; suspension is released; rotation does not log out.                    | Provider/route/realtime integration tests              |
| X09 | Browser genuinely exercises enrollment, ordinary login, recovery, replacement, and rotation with isolated accounts; no impersonation/mocked API substitute.     | e2e/login.spec.ts + e2e/mfa.spec.ts                    |
| X10 | CI/default E2E never touches root DB; live-mode destructive specs refuse; secrets absent from traces/screenshots/reports; no reset/disable/bypass path.         | Harness/artifact checks + tracked mint-route inventory |

## Restore and key escrow — P4 implementation, P5 drill

| ID  | Assertion                                                                                                                                     | Primary evidence                          |
| --- | --------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------- |
| R01 | Current-head snapshot + correct stable key restores enrolled/recovery-pending state; all restored sessions/challenges invalidated atomically. | test_mfa_restore.py                       |
| R02 | Missing/malformed/wrong key and corrupt ciphertext reject before swap; primary and selected backup unchanged.                                 | Candidate failure tests                   |
| R03 | Earlier/pre-MFA schema rejected before swap without auto-upgrade; compatible-code rollback instructions documented.                           | Schema preflight tests                    |
| R04 | Emergency rollback also invalidates sessions/challenges; no pre-outage authentication revival.                                                | Restore/coordinator rollback tests        |
| R05 | Snapshot semantics demonstrably revive that snapshot's old factor/code state; limitation documented rather than claimed prevented.            | Disposable snapshot regression + P5 drill |
| R06 | Key excluded from backup/manifest/log/args; escrow can decrypt replacement-host copy; retention/key-custody guidance exists.                  | Backup inspection + isolated escrow drill |

## Final documentation and human-dependent checks — P5

| ID  | Assertion                                                                                                                               | Primary evidence                                       |
| --- | --------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------ |
| V01 | Manual app/QR entry and local-storage instructions work on a real authenticator; no claim that ADAS can inspect cloud-sync policy.      | Human-device observation, or explicit Not run          |
| V02 | LAN HTTPS Secure cookies/WS and real clock synchronization verified; no localhost test described as a TLS/device pass.                  | Authorized disposable LAN drill, or explicit Not run   |
| V03 | Operations/help explain key escrow, no reset, interrupted recovery, stable-key/old-backup limitations, and later production scheduling. | MFA.md + help verification                             |
| V04 | Fresh live-paper/tracker evidence, per-site changes/redraws, and NFR-20 authenticator-device exception; no Drive writes.                | Local paper-sync finding + proposed validation updates |
| V05 | Actual commands/commits/results/manual timings recorded; unexecuted requirements stay blocked/not run, not passed.                      | docs/validation/mfa-validation.md                      |

## Commands and lifecycle gates

Run from repository root. Module paths named as future tests become executable in their owning package, not during handoff authoring.

```powershell
# Focused development: choose only relevant existing/new selectors.
uv run pytest backend/tests/test_mfa_crypto.py backend/tests/test_mfa_migrations.py
uv run pytest backend/tests/test_mfa_service.py backend/tests/test_mfa_api.py backend/tests/test_mfa_concurrency.py
pnpm --filter frontend test:run src/api/mfa.test.ts src/pages/auth src/pages/profile/MfaSettingsCard.test.tsx

# Code-package pre-PR lifecycle gate; contains broad backend/frontend tests, build, and functional E2E.
pnpm full:check
```

Schema-changing packages additionally follow CONTRIBUTING.md's exact temporary DATABASE_URL try/finally procedure: upgrade head, empty downgrade base, and `uv run python backend/scripts/verify_migration_schema.py`. Separate populated-database upgrade/refusal tests prove production-data behavior. Never point these commands at the working adas.db. Restore the prior environment afterward.

Full backend scope is required for models/core/conftest/app-factory changes; use the full backend scope included in the pre-PR gate rather than duplicating a successful broad run solely for reassurance. Run a standalone full backend suite earlier only when diagnosing a failure or when required before another actual lifecycle event. An authorized push runs pnpm check via its hook; do not manually pre-run it. Optional visual baselines are Linux-only and separate from full:check.

## P5 result walk — V01–V05

| ID  | Result                                          | Evidence / limitation                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| --- | ----------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| V01 | Not run                                         | No physical phone/authenticator was available in the one-laptop scope. QR/manual entry, device clock, device storage, and any cloud-sync behavior remain human-observed prerequisites.                                                                                                                                                                                                                                                                                                                        |
| V02 | Not run                                         | No second LAN client was used. P4 localhost browser E2E is not HTTPS/WSS Secure-cookie or real-device clock evidence.                                                                                                                                                                                                                                                                                                                                                                                         |
| V03 | Verified                                        | `docs/operations/MFA.md`, the operator-visible Help Center article, setup links, and `backend/tests/test_help.py` cover code saving, next-code timing, interrupted/final-code recovery, replacement vs. recovery, stable-key custody, restore semantics, and no in-app/Admin reset.                                                                                                                                                                                                                           |
| V04 | Draft prepared; page mapping blocked            | Current live Doc and trackers were read; local proposals are in `paper_sync/findings/2026-10-19-mfa-validation-operations.md` and `docs/validation/mfa-validation.md`. Live PDF export returned 403; the supplied 246-page PDF is a pre-MFA snapshot. No Drive writes/comments.                                                                                                                                                                                                                               |
| V05 | Scoped gate passed; manual prerequisites remain | `pnpm full:check` passed on `8d4ccfda5ba332f8ec6ec5e54752ebefd6e6c1ef`: backend 1,377 passed/5 skipped, frontend 395 across 62 files, build passed, Chromium E2E 6/6. P5 help/restore selectors passed (40 tests). One-laptop restore/rollback function timings were 130.31/95.46 ms; a fresh loopback backend became ready in 4.279 s and rejected the pre-restore cookie with 401 `AUTH_REVOKED`. No AI heartbeat/end-to-end 60-second timing was measured. See the safe records under `var/test-evidence`. |

## Evidence ledger

P1–P4 add results to their own completion notes. P5 links final evidence here, with actual commit/environment/command/exit status, safe artifact location, and failed/skipped/manual prerequisites. Do not put secrets or unredacted auth responses into the ledger.

| Group                          | Status                  | Evidence                                                                                                                                                                                                                                                                                                                                                                                           |
| ------------------------------ | ----------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Foundation/harness             | Verified (P1)           | `pnpm full:check`: backend 1,215 passed/19 skipped, frontend 357 passed, build passed, isolated Chromium login passed; disposable migration preservation/downgrade/schema checks passed. See `02_PKG_foundation.md`.                                                                                                                                                                               |
| Backend/transactions           | Verified (P2)           | B01–B13 and C01–C05 assertions/results are mapped row by row in `03_PKG_backend.md`; P2 full gate passed with its recorded test defaults.                                                                                                                                                                                                                                                          |
| Frontend components            | Verified (P3)           | U01–U08 are mapped in `04_PKG_frontend.md`; focused adapter/component/provider and regression tests passed.                                                                                                                                                                                                                                                                                        |
| Cutover/browser/demo           | Verified (P4)           | X01–X10 are mapped in `05_PKG_cutover.md`; exact merged source tree passed P4 `pnpm full:check` (backend 1,375 passed/5 skipped, frontend 395 passed, build passed, Chromium E2E 6/6).                                                                                                                                                                                                             |
| Validation/operations          | Scoped gate passed (P5) | P5 implementation commit `8d4ccfda5ba332f8ec6ec5e54752ebefd6e6c1ef`: `pnpm full:check` exit 0, backend 1,377 passed/5 skipped, frontend 395 passed, build passed, Chromium E2E 6/6. Windows 10.0.26200.0, Python 3.12.13, Node 22.23.1, pnpm 11.17.0. Physical authenticator, second-client LAN/TLS, AI-heartbeat recovery timing, and independent offline escrow/replacement host remain not run. |
| Restore/escrow                 | Partial (P4/P5)         | R01–R05 tests passed. P5 added a consumed-code resurrection assertion and one-laptop restore/rollback/key-file exercise; a fresh backend rejected the pre-restore cookie with 401 `AUTH_REVOKED`. Local ACL and backup/manifest exclusion passed. Independent offline escrow/replacement host remains not run.                                                                                     |
| Physical authenticator/LAN TLS | Not run                 | V01/V02: one laptop only; no physical phone/authenticator or second LAN client. Local browser TOTP is not device or LAN/TLS evidence.                                                                                                                                                                                                                                                              |
| Operations/paper proposals     | Prepared                | V03/V04 proposals and help are local. Live Doc export returned 403; current page mapping is pending. No Drive writes/comments were made. P5 full gate passed; remaining physical prerequisites are not release acceptance.                                                                                                                                                                         |

The planning baseline is in the overview and proves only the pre-MFA implementation's existing tests, not any row of this acceptance matrix.
