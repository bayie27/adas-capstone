# P4 — Integrated mandatory MFA cutover

> **For agentic workers:** Execute inline in this manually started Luna Max conversation. This is the activation PR, not authorization to deploy to an operational server, enroll real users, start another conversation, or merge automatically.

**Goal:** Activate the complete contract in one PR while preserving existing auth, demo, restore, audit, and WebSocket guarantees.  
**Branch:** `feat/mfa-cutover`, from P3's merged main.  
**Read:** Overview, the entire shared contract, matrix, CLAUDE.md, CONTRIBUTING.md migrations, current restore/launcher rules.  
**Prerequisites:** P1–P3 merged; verify their real signatures, inactive routing, components, disposable harness, and completion evidence.

**Architecture:** One coordinated activation of the prebuilt services/UI, plus explicit session cutover, startup checks, and offline restore transformation.  
**Tech stack:** FastAPI/SQLModel/Alembic, React/TypeScript, pytest/Vitest/Playwright, existing Python/PowerShell maintenance orchestration.  
**Spec:** [01_CONTRACTS.md](01_CONTRACTS.md), especially §§1/3/6/7.

## Owned surfaces and exported interfaces

| Surface                         | Files to inspect/modify                                                                                                                                                                      |
| ------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Activation and sessions         | `backend/app/api/routes/auth.py`, `api/dependencies.py`, `core/security.py`, `services/sessions.py`, `main.py`, `schemas/auth.py`, config/redaction wiring, and one new cutover migration    |
| User/demo integration           | `api/routes/users.py`, `api/routes/dev.py`, `schemas/dev.py`, `app/dev/service.py`/seed/reseed paths only where necessary; relevant frontend dev session types/label                         |
| Restore safety                  | `backend/app/maintenance/restore.py`, `maintenance/cli.py`, current orchestrator call sites, and tests; preserve unrelated uncommitted maintenance/launcher work                             |
| UI activation                   | Login.tsx, ProfileSettings.tsx, api/auth.ts, useAuthStore integration, error handling, RealtimeAlertsBridge, router root, and new transient code-display host outside protected-route guards |
| Testing and deployment examples | Backend conftest/auth/session/user/dev/realtime/config/maintenance tests; P1 E2E harness, e2e specs, CI, `.env.example`, relevant operations setup notes                                     |

Final session minting takes explicit auth_method and optional mfa_credential_version: real MFA calls use totp plus current version; dev calls use demo_impersonation. Remove the default that could accidentally mint a normal password-only session. Existing low-level test constructors must explicitly state the proof/session method they simulate. Add no production test-only bypass.

## Task 1 — activate auth and perform the development cutover

- [x] Write failing integrated tests for the current password-only bypass: correct password alone must no longer yield a session/profile or access protected REST/WS. Cover initial enrollment and an already enrolled user's login through the actual app factory.
- [x] Add the separate P4 migration at the actual P3 head. Revoke all existing sessions using mfa_rollout, clear staged challenges, and append one system MFA_ROLLOUT event atomically. Preserve historical ids/data/audit triggers. Repeat upgrade head is a no-op; a migration failure leaves no partial rollout.
- [x] Replace POST /api/auth/login with P2's thin password adapter, register mfa.router, and supply distinct app-state password/MFA limiters. Update the active LoginResponse schema to ChallengeState. Remove the legacy user-on-password-success path and any staged response fallback.
- [x] In shared REST/WS authentication, require active DB session/account and either valid enrolled/version-matching totp or explicitly enabled demo impersonation. Correctly signed legacy password sessions fail even if accidentally unrevoked. Keep issuer/audience/expiry/user-id binding and current DB-role authorization.
- [x] Extend logout to invalidate and clear the matching challenge cookie as well as the existing session cookie; retain idempotency and after-commit socket closure. Scope no-store middleware/error handling to all auth responses, including schema/origin/429 failures.
- [x] Wire invalidate_user_challenge into successful password change/reset, disable, and role-change transactions. Show stale challenges cannot survive deactivate→reactivate or reset→old-challenge reuse. Preserve ordinary username-change identity behavior.
- [x] Update auth_headers/login test helpers to complete actual MFA where tests need authentication. Keep explicit unenrolled fixtures for enrollment tests and explicit enrolled fixtures for other domain tests. Use a controllable service clock for step boundaries/repeated logins, not sleep or a bypass flag. Do not suppress audit events to keep old row-count expectations green.

## Task 2 — activate the frontend and protect one-time output

- [x] Mount MfaLoginFlow at the existing /login entry point and MfaSettingsCard in Profile. Replace active legacy login types/adapters and remove stale assumptions that password success contains user. Client auth-store population waits for completed MFA and any initial code acknowledgment.
- [x] Mount P3's MfaSensitiveFlowProvider at the router root, outside protected-route guards. It owns only in-memory recovery-code presentation and completion callbacks; it never persists secrets. Wire Profile's onSessionRevoked to immediate auth/query clearing and onSignedOut to navigation after acknowledgment. The host survives the intervening route change.
- [x] During replacement confirmation, acquire the existing scoped redirect suspension before sending the request. After success, keep the host mounted with the returned codes, clear auth/query state, honor the server cookie removal, and release suspension on acknowledgment/unmount. Failure releases it promptly. Test socket-close-before-response and response-before-close; neither may discard codes or leave expiry permanently suppressed.
- [x] Initial/recovery enrollment returns a real server session; the /login flow keeps client role unset until acknowledgment. Rotation displays new codes and preserves login. Cancellation and invalid proof stay inline. Lost output/reload directs users to fresh login/rotation, never a backend redisplay route.
- [x] Add visible demo impersonation labeling using the server's session method, including switches/reseeds. Do not store a server credential in the existing display-only auth cache. GET /mfa/status supplies current method after refresh.
- [x] Run focused Login/Profile/provider/realtime tests before broad integration. Preserve accessible labels, manual provisioning, deadline/countdown behavior, and generic failures from P3.

## Task 3 — enforce key configuration and constrain demo sessions

- [x] Fail startup on missing/malformed MFA_ENCRYPTION_KEY in every environment. Validate key structure before runtime startup writes and validate stored ciphertext after schema availability but before camera resets, schedulers, background workers, or traffic. A structurally valid wrong key with existing ciphertext is also a startup failure. Never print its value or a raw Pydantic error carrying it.
- [x] Make tests/CI supply fresh disposable key material where an app starts. Do not commit a working default key in .env.example. Preserve migration-only/config-only construction without startup and without key invention.
- [x] Inventory every create_session/create_session_token/AuthSession call, including dev/UAT helpers. Normal paths can mint only after completed MFA; demo paths preserve current caller gates and mark their rows as demo_impersonation. Demo challenges never satisfy full auth.
- [x] When DEV_TOOLS_ENABLED is false, dev routes are absent and existing demo sessions fail both REST and WS. When true on a LAN production build, the intentional switch/reseed workflow still works. Do not treat ENVIRONMENT=production as synonymous with operational deployment.
- [x] Operational setup examples explicitly use DEV_TOOLS_ENABLED=false and non-demo accounts. Demo examples explain the exception. Demo MFA management requires fresh proofs exactly as the normal management endpoints do.

## Task 4 — restore and rollback safeguards

- [x] Write failing disposable-file tests for restoring a post-MFA snapshot with the right key, missing/wrong key, corrupt ciphertext, older/pre-MFA schema, restored active sessions/challenges, and automatic emergency rollback. Preserve selected-backup checksums and contents throughout.
- [x] Add candidate preflight/transform helpers within maintenance/restore.py, using explicit key/config input from its CLI call sites rather than hidden environment values in shell commands. A candidate must have the current MFA-capable Alembic head and decryptable stored seeds before swap. Reject earlier known revisions before replacement; do not silently upgrade them or rely on readiness to discover the problem after swap.
- [x] On the temporary candidate, revoke all sessions with mfa_restore, remove challenges/pending seeds, and append MFA_RESTORE_INVALIDATE in one transaction. Preserve snapshot active credentials/recovery rows and recovery_pending state. Recheck integrity/foreign keys after transformation; checksum validation of the original artifact precedes transformation.
- [x] Use the same transformation on the emergency rollback copy before swapping it back. Missing key/schema/decryption failure never selects a password-only fallback or silently discards MFA. Preserve leases, restore identities, protection tiers, readiness state, post-restore audit, and failure cleanup.
- [x] Extend current CLI/coordinator/PowerShell tests only for changed integration boundaries. The working tree had unrelated edits in these files at planning time: do not replace entire files from an archived example or discard current changes.

## Task 5 — browser/CI verification against disposable accounts

- [x] Update e2e/login.spec.ts and add e2e/mfa.spec.ts plus shared test-only helpers. Exercise real UI enrollment and ordinary login; do not stub /mfa responses or use impersonation as evidence of normal MFA. Assert protected REST/WS denial before completion.
- [x] Give each MFA scenario its own disposable account so tests never compete for the single account challenge or accepted step. Seed those accounts only through the guarded isolated runner's setup, with no application bypass endpoint. Use ordinary authenticated APIs/UI where the behavior itself is under test.
- [x] Cover recovery→new enrollment→fresh login; replacement→one-time codes surviving sign-out→login; rotation invalidating old codes without logout; and wrong-code countdown/error behavior. Keep clocks deterministic in backend tests and avoid browser assertions tied to a just-expiring TOTP second.
- [x] Generate test TOTP through an independent test helper implementing RFC 6238 or a pinned test dependency; assert it against a published known vector. Read only disposable provisioning values. Disable trace/video/screenshot capture during secret-entry/display flows; on failure keep redacted assertions/status evidence instead of secret-bearing network dumps.
- [x] Refuse destructive/enrollment MFA specs in E2E_LIVE_DEPLOYMENT mode. Update optional visual authentication helpers to complete MFA on isolated data without rebasing Linux screenshots from Windows. Existing YAML/security/UAT scripts using password-only login also need a compatible test-auth helper or explicit instructions; scan them rather than fixing only the first failing test.
- [x] Update CI so generated ephemeral keys/credentials and isolated DB paths are provided before startup. Remove the default e2e job's root-DB reset dependency once the isolated runner owns provisioning. Preserve separate migration CI and no secret artifacts in uploads.

## Verification and completion

Use narrow red/green selectors first, including new `backend/tests/test_mfa_cutover.py` and `backend/tests/test_mfa_restore.py`. Then:

```powershell
uv run pytest backend/tests/test_mfa_cutover.py backend/tests/test_mfa_restore.py backend/tests/test_auth.py backend/tests/test_sessions.py backend/tests/test_realtime.py backend/tests/test_dev_tools.py
pnpm --filter frontend test:run src/pages/Login.test.tsx src/pages/ProfileSettings.test.tsx src/pages/auth src/pages/profile/MfaSettingsCard.test.tsx
```

Run the separate disposable migration checks in CONTRIBUTING.md; include seeded pre-cutover upgrade and a failed-upgrade rollback assertion. Walk matrix X01–X10 and R01–R06. Run `pnpm full:check` once at the pre-PR gate; its full backend suite supplies the broad core/conftest/app-factory regression scope. E2E must actually execute, not skip for missing credentials. Do not claim physical-phone, LAN-TLS, protected-device restore, or production rollout from loopback tests.

## Completion notes — P4 execution record

- **Status:** Implemented and verified on `feat/mfa-cutover`; commit `6677bb3` is in draft PR [#244](https://github.com/bayie27/adas-capstone/pull/244). No operational cutover, user enrollment, merge, Drive write, or P5 work was performed.
- **Base/prerequisites:** Branch started from updated `origin/main` at `59b32a82ddf6556c763c375eba362e5ea4e27862`. Confirmed P1 #241 merged at `8b6778c`, P2 #242 at `796ea43`, and P3 #243 at `59b32a8` (P3 implementation commit `b12176a`).
- **Predecessor contracts checked against that main:** P1 revision `5b87b6564753` supplies `MfaCredential`, `MfaChallenge`, and `MfaRecoveryCode` plus encrypted TOTP/recovery helpers. P2's `app.services.mfa` owns `begin_password_login`, `get_challenge`, `cancel_challenge`, `get_enrollment`, `confirm_enrollment`, `verify_challenge`, `get_mfa_status`, `begin_replacement`, `begin_enrollment_from_session`, `rotate_recovery_codes`, `invalidate_user_challenge`, and stored-secret validation; the router and password adapter were dormant in the normal app. P3 supplies the typed `ChallengeState`, `ChallengeVerificationResponse`, `EnrollmentConfirmationResponse`, and `MfaStatusResponse` API contracts with `MfaLoginFlow`, challenge/enrollment panels, `RecoveryCodesPanel`, and `MfaSensitiveFlowProvider`; Login/Profile were still using their old active flow. P4 wires these real contracts into the application rather than adding a parallel auth path.
- **Activation:** `POST /api/auth/login` returns the P2 challenge contract; only completed TOTP/enrollment returns a normal session. `create_session` now requires an explicit `Literal["password", "totp", "demo_impersonation"]`; dependencies reject password-only sessions and require an enrolled matching credential version for TOTP. Demo sessions require the existing flag and expose their method to the client for visible labeling. Logout clears both cookie types, scoped no-store/error handling remains on auth responses, and successful identity/security transitions invalidate challenges.
- **Restore:** The CLI supplies the configured stable key and current Alembic head in process memory. Restore and emergency rollback verify the original artifact, transform only a checksum-verified compatible candidate copy, decrypt its stored MFA secrets, invalidate sessions/challenges with an audit row, and recheck integrity/foreign keys. The selected and emergency backup artifacts are not modified. `docs/operations/README.md` describes restored factor/recovery state and the separate key-escrow boundary.

### Verification results

- Focused P4 backend coverage: **217 passed** across the cutover/MFA/auth/session/realtime/dev/user/app-factory/report/internal selectors; `backend/tests/test_mfa_cutover.py`: **8 passed**. Focused frontend Login/Profile/authenticator/dev coverage: **48 passed**.
- Separate disposable migration procedure passed: Alembic `upgrade head`, empty-database `downgrade base`, and `uv run python backend/scripts/verify_migration_schema.py` reported exact metadata/schema agreement. The documented console-script invocation hit a Windows trampoline path-canonicalization error; `uv run python -m alembic` completed the same migration procedure. `DATABASE_URL` was restored in `finally`; no repository/root database was used. Seeded previous-revision preservation and injected migration rollback are covered by the migration tests.
- The first full gate run failed only in the timing-sensitive, untouched `ai_engine/tests/test_camera.py::test_segment_id_increments_on_reconnect` under unconstrained xdist: **1,374 passed, 5 skipped**. That selector passed alone (**1 passed**). The full gate rerun with `PYTEST_XDIST_AUTO_NUM_WORKERS=4` passed: `pnpm full:check` exit 0; **1,375 backend passed / 5 skipped**, **395 frontend passed / 62 files**, frontend lint/typecheck/build passed, and Chromium E2E passed **6/6**.
- The six isolated Chromium cases used randomized disposable accounts and a UUID-scoped DB/key. They exercised ordinary enrollment/login, recovery and re-enrollment, replacement through sign-out and socket close, recovery-code rotation/invalidation, wrong-code countdown, and the independent RFC 6238 vector. No dev impersonation or mocked MFA endpoint was used as normal-login evidence. Live-mode enrollment specs remain refused. Traces, screenshots, video, and Playwright automatic page snapshots are disabled; after the passing run, `test-results` contained **0** error-context, trace, screenshot, or video files.
- Restore coverage passes for current-head state preservation and factor/code revival, missing/malformed/wrong key and corrupt ciphertext, pre-MFA schema refusal, unchanged backups, and emergency rollback invalidation. These are disposable-file tests, not an operational restore or key-escrow drill.

### Matrix walk

| Row | Result                              | Evidence or limit                                                                                                                                                                                                             |
| --- | ----------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| X01 | Verified                            | `test_mfa_cutover.py` proves one-time migration revocation/challenge clearing/audit, history preservation, failure rollback, and populated downgrade refusal.                                                                 |
| X02 | Verified                            | Integrated legacy password-session denial covers protected REST and WebSocket; auth/session tests reject incomplete challenge/session material.                                                                               |
| X03 | Verified                            | Completed enrollment/TOTP login, session method/version checks, auth/session tests, and disposable Chromium login pass.                                                                                                       |
| X04 | Verified                            | Auth, user, session, MFA challenge invalidation, logout, and realtime regressions pass in the full suite.                                                                                                                     |
| X05 | Verified                            | Challenge and service tests cover wrong, expired, superseded, replayed, and canceled proofs without successful-login state; full backend suite passes.                                                                        |
| X06 | Verified                            | Missing key and malformed/wrong stored ciphertext fail startup before runtime resets; config/main/startup tests pass.                                                                                                         |
| X07 | Verified                            | Dev route/session gating and HTTP/WS rejection with tools disabled pass; the client labels `demo_impersonation`.                                                                                                              |
| X08 | Verified                            | `MfaSettingsCard` tests exercise socket-close-before-response and response-before-socket-close; browser replacement confirms one-time output survives auth clearing and a closed live socket.                                 |
| X09 | Verified                            | All six Chromium functional tests passed against the isolated disposable runner; no dev impersonation or MFA API mocks are used for ordinary login.                                                                           |
| X10 | Verified                            | Runner/CI tests and source checks confirm unique DB/keys/accounts, no root DB reset, live-mode refusal, and no secret-bearing browser artifacts in the passing run.                                                           |
| R01 | Verified                            | Restore tests preserve snapshot enrolled/recovery-pending state while invalidating all restored sessions/challenges.                                                                                                          |
| R02 | Verified                            | Candidate failures for missing/malformed/wrong key and corrupt ciphertext leave primary, selected backup, and manifest unchanged.                                                                                             |
| R03 | Verified                            | Earlier/pre-MFA schema is refused before swap or auto-upgrade; matching current schema is required.                                                                                                                           |
| R04 | Verified                            | Emergency rollback uses the same invalidation/audit transformation and preserves its source backup.                                                                                                                           |
| R05 | Verified                            | Disposable restore test proves snapshot factor, generation, and recovery-code state can revive; this is documented in operations guidance.                                                                                    |
| R06 | Partial — operational drill not run | Code and tests require the stable key in process and exclude it from the backup transformation; the deployment's escrow/replacement-host decryption and custody exercise is human/operational P5 work and remains unverified. |

### Deferred and paper boundary

- Not run: physical authenticator/device/cloud-sync observation, LAN HTTPS/Secure-cookie/clock exercise, operational backup restore or emergency rollback, key-escrow/replacement-host drill, live-user enrollment, and deployment. P5 has not started.
- Read-only paper check found current defense-document drift in FR-01/login use-case wording, staged-MFA ERD/backend wording, the `auth_method` default statement, restore behavior, dependency description, and the NFR-20 local-authenticator boundary. PDF page mapping was blocked by the Drive export returning 403. No Drive files or tracker rows were written and no P5 proposal was created.

The completion ledger in [00_OVERVIEW.md](00_OVERVIEW.md) records the package result. Do not execute an operational cutover or start P5 automatically.
