# P2 — MFA backend service and inactive API adapter

> **For agentic workers:** Execute inline in this manually started Luna Max conversation. Use applicable execution/TDD skills; do not delegate implementation or activate P4 behavior early.

**Goal:** Build the complete transactional MFA flow behind an API adapter that is not registered in the ordinary application yet.  
**Branch:** `feat/mfa-backend`, from P1's merged main.  
**Read:** Overview, shared contract in full, test matrix, current CLAUDE.md.  
**Prerequisite proof:** P1's migration/models/helper functions and isolated browser harness exist on main and P1's checks are recorded.

**Architecture:** Service-owned one-use state transitions and audit transactions behind a dormant thin FastAPI adapter.  
**Tech stack:** Python 3.12.13/uv, FastAPI, SQLModel/SQLite, PyOTP/Fernet, pytest.  
**Spec:** [01_CONTRACTS.md](01_CONTRACTS.md), especially §§1/3/4/5.

## Owned files and interfaces

Create `backend/app/services/mfa.py`, `backend/app/schemas/mfa.py`, `backend/app/api/routes/mfa.py`, `backend/tests/test_mfa_service.py`, `backend/tests/test_mfa_api.py`, and `backend/tests/test_mfa_concurrency.py`. Update core/rate_limit.py only where needed for distinct MFA failure accounting, and core/redaction.py plus services/audit.py for MFA secret handling. Keep new session-helper parameters backward compatible until P4. Do not register the router in main.py or change production POST /api/auth/login.

Consumes P1's models and pure helper signatures. Produces all service functions/records and exact public bodies from contract §§3–5. The adapter exports `router` with prefix `/api/auth/mfa` and `password_login(request, response, form_data, engine, password_limiter, mfa_limiter)` for P4's thin POST /login wrapper. Adapter cookie/response handling may live in this module; business rules/transactions may not.

The production app still uses its old login and accepts legacy password sessions through P3. Do not make new MFA logic callable via a debug bypass. Isolated API-test apps register the new router and route a test-only login wrapper to password_login using real dependencies and disposable storage; no such wrapper is committed into application routing.

## Task 1 — password/challenge/enrollment flow

- [x] Read the existing auth route, dependencies, sessions/audit services, error handlers, redaction, and limiter. Identify any core/global Settings use the test fixture must patch; do not assume explicit Settings propagates everywhere.
- [x] Write and run failing service/API tests for password stage (no AuthSession/last_login/LOGIN_SUCCESS), generic password failures, enrollment-required absent credentials, challenge expiry and supersession, safe status/QR refresh, and enrollment confirmation outputs. Use the exact routes and discriminants in the contract.
- [x] Implement per-user opaque challenge issuance, pending encryption, purpose/state/version/password-change guards, idempotent cancellation, and safe provisioning. Refresh must reveal the same pending seed with the original deadline; get/status endpoints never create new seeds.
- [x] Implement ordinary TOTP verification and initial confirmation. Accept a step once across all TOTP-protected operations; confirmation stores the pending factor's confirming step as used. No broad PyOTP valid_window check without a persisted accepted step.
- [x] Keep routes thin: gather context/authorization, call the service, apply committed cookie instructions/response body, and close declared WebSockets after commit. Revalidate active account/session inside service writes; do not trust an ORM object loaded earlier as current authority.
- [x] Run the new selectors, including unknown/inactive users, malformed and stale challenge cookies, wrong-purpose submission, and request-validation secret redaction. Preserve existing generic password behavior and origin checks.

## Task 2 — recovery and factor management

- [x] Write failing tests for interrupted recovery using a different unused code; consumed-code replay; recovery_verify refusing password-only enrollment; remaining codes invalidated only after confirmation; and exhaustion of the last recovery code. Exhaustion is a lockout outcome, not permission for a reset endpoint.
- [x] Implement recovery acceptance as one transaction: consume one code, disable old seed, advance version, revoke all sessions, create recovery_enroll challenge/pending seed, audit MFA_RECOVERY_USE. Return no full session. Deleting the challenge or restarting password login never restores the old factor or grants seed access without another unused code.
- [x] Write failing tests for replacement start requiring unused old-factor TOTP, old factor usable until confirmation, expiry/cancellation preserving it, confirmation sign-out everywhere, and replacement one-time codes returned after commit. Implement the exact two-phase semantics.
- [x] Write failing rotation tests: fresh password+TOTP, all old codes invalid, single-use replay accounting, sessions preserved, challenge invalidated, no login-success/timestamp change. Implement rotation.
- [x] Test demo enrollment with a fresh password and subsequent new-seed proof, and demo replacement/rotation with fresh password+active TOTP. Reject unenrolled-normal management sessions and recovery-pending attempts to bypass recovery proof. Service tests may construct explicitly marked demo sessions; normal app wiring waits for P4.
- [x] Implement management status and the session-to-enrollment route. A demo enrollment completion creates a new legitimate totp session only after both proofs and revokes preceding demo sessions; it never relabels a session without verification.

## Task 3 — failure accounting, transaction rollback, and concurrency

- [x] Use a separate MFA limiter with independent per-user_id and IP dimensions. A correct password, new cookie, cancellation, or QR fetch cannot reset its failures. Apply the configured threshold/window and Retry-After; do not add a new limiter service/dependency.
- [x] Test account/IP isolation, exact expiry/limit boundaries, missing/invalid Retry-After UI-independent API semantics, denied/failure audit results, and no credential/session changes for rejected attempts. State the inherited in-process restart limitation honestly.
- [x] Add tests that force audit.record to fail during login, recovery consumption, enrollment, replacement, and rotation. Assert the entire primary action rolls back and failure recording happens only after rollback. Never use an unrelated committed action to compensate for audit failure.
- [x] Use a real temporary file-backed SQLite engine, separate Sessions/connections, and a barrier to race two submissions of the same TOTP, recovery code, and enrollment confirmation. Exactly one action wins; the loser receives a controlled error and no duplicate session/batch/audit success. Do not use StaticPool's one connection to claim race safety.
- [x] Implement writer reservation and atomic acceptance under contract §4, reloading password/account/version state after acquiring it. Reproduce and handle busy failures with the existing error envelope; never retry an already-committed one-time action blindly.
- [x] Expand redaction to configured MFA keys and nested audit secret keys; test log/error/audit output with sentinel passwords, seeds, OTPs, recovery codes, provisioning URIs, ciphertext, and challenge tokens. Avoid dynamically retaining every OTP in global redaction state; prevent logging proof payloads at the source.
- [x] Remove any unintended seed/code repr logging from service records. Store neither secrets nor plaintext one-time codes in durable response caches.

## Task 4 — adapter verification while dormant

- [x] Test body contracts, cookie paths/flags/deletion, GET no-mutation, no-store including error responses in the isolated adapter app, challenge copied into a full-session cookie, and full-session cookie used where a challenge is required. Reject token confusion.
- [x] Add composable challenge invalidation and startup decryption validators for P4. They must not commit an existing user's password-change transaction or silently provision the schema.
- [x] Prove the ordinary app still exposes no new MFA endpoints and its existing login behavior/browser test is unchanged. Main.py does not include mfa.router yet. No unguarded helper endpoint may mint challenges or reveal seeds.

## Verification and completion

```powershell
uv run pytest backend/tests/test_mfa_service.py backend/tests/test_mfa_api.py backend/tests/test_mfa_concurrency.py
uv run pytest backend/tests/test_auth.py backend/tests/test_sessions.py
```

Use targeted selectors during red/green work. Run relevant lint/format checks, walk matrix B01–B13 and C01–C05, then run `pnpm full:check` at the pre-PR gate. Shared core edits get full backend scope through that gate. Do not run the separate migration procedure unless schema actually changed; a discovered schema defect must be repaired with a new reviewed/tested migration, not an edited historical revision.

## Completion notes — executor fills

- Status: P2 implementation and verification complete; [PR #242](https://github.com/bayie27/adas-capstone/pull/242) is open and unmerged. Branch `feat/mfa-backend` is based on merged P1 main at `8b6778cf61c654d78a337f1a302fea2a8ba88f3a` (PR #241); implementation commit `a0131395c9d94683a6e1aa7620f5047a7260ebc7`.
- Service/API contract: implemented the service records and operations for password staging, challenge reads/cancel, enrollment confirmation, TOTP/recovery verification, replacement, recovery-code rotation, management status, and demo session enrollment. The adapter exports `/api/auth/mfa` and `password_login(...)`; it is only included by the isolated test app. `backend/app/main.py` does not register it and production `POST /api/auth/login` remains unchanged. No migration/schema change was needed.
- Red/green evidence: the initial targeted red run failed at the missing P2 service/schema as expected. Focused final test set: **102 tests passed** across `test_mfa_service.py`, `test_mfa_api.py`, `test_mfa_concurrency.py`, and the updated `test_users.py`; existing `test_auth.py` + `test_sessions.py`: **100 passed**. The incremental inactive-user, Retry-After, and malformed-cookie assertions passed (**3 targeted tests**).
- Matrix walk:

  | Row | Evidence                                                                                                                                                                                                                                                                  |
  | --- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
  | B01 | Password-stage challenge, generic wrong/unknown/inactive failures, and isolated login adapter: `test_password_stage_creates_enrollment_challenge_without_authenticating`, `test_password_failures_are_generic_and_password_limiter_success_is_deferred`, API login tests. |
  | B02 | Stable pending seed, confirmed enrollment, recovery batch, and session: `test_enrollment_refresh_reuses_encrypted_pending_seed_and_deadline`, `test_enrollment_confirmation_commits_factor_codes_session_and_audits`, isolated enrollment API test.                       |
  | B03 | Inclusive deadline, expired rejection, refresh stability, supersession: `test_challenge_deadline_is_inclusive_and_new_password_flow_supersedes_old`, refresh test.                                                                                                        |
  | B04 | TOTP acceptance and cross-operation step replay guard: `test_totp_login_accepts_a_new_step_and_creates_only_a_totp_session`, `test_enrollment_confirmation_consumes_its_totp_step_globally`, invalid-code and log-sentinel tests.                                         |
  | B05 | Recovery acceptance consumes one code, disables factor, revokes sessions, and creates no full login: `test_interrupted_recovery_requires_another_unused_code`.                                                                                                            |
  | B06 | Interrupted recovery requires another code; password-only seed access is refused; last-code exhaustion is explicit: interrupted-recovery and exhausted-code tests.                                                                                                        |
  | B07 | Recovery confirmation replaces the old batch and creates a versioned TOTP session: `test_recovery_enrollment_replaces_old_batch_and_creates_totp_session`.                                                                                                                |
  | B08 | Fresh-proof replacement, old factor preservation, cancellation/expiry, confirmation revocation: replacement confirmation/cancel/expiry tests.                                                                                                                             |
  | B09 | Rotation requires fresh proofs, invalidates old codes/challenge, and preserves sessions: `test_recovery_rotation_requires_fresh_proofs_and_preserves_sessions`.                                                                                                           |
  | B10 | Demo enrollment/replacement/rotation require the specified fresh proofs: three demo management tests in `test_mfa_service.py`.                                                                                                                                            |
  | B11 | Per-account/IP isolation, no reset on password restart, numeric `Retry-After`, and deferred password-limiter reset: limiter service and API tests.                                                                                                                        |
  | B12 | Isolated API body/cookie/no-store/validation/token-confusion/origin coverage; ordinary app still returns legacy login and has no MFA route: `test_mfa_api.py`.                                                                                                            |
  | B13 | Secret repr, nested audit, log, validation error, ciphertext-storage sentinels: redaction/storage tests and API validation test.                                                                                                                                          |
  | C01 | Two file-backed SQLite connections race one TOTP: exactly one accepted result.                                                                                                                                                                                            |
  | C02 | Two file-backed connections race one recovery code: one recovery transition/audit success.                                                                                                                                                                                |
  | C03 | Two file-backed connections race enrollment confirmation: one factor/batch/session.                                                                                                                                                                                       |
  | C04 | Audit failure rollback tests cover login, recovery, enrollment, replacement, and rotation.                                                                                                                                                                                |
  | C05 | Password hash, challenge expiry, version rechecks, and real writer-busy `503` are covered by state-race/busy tests.                                                                                                                                                       |

- Redaction/rollback/concurrency: no raw proof, seed, provisioning URI, recovery code, ciphertext, challenge token, or session token is written to audit/log output; seeded secrets remain encrypted/hashed. All five injected audit failures roll back the business action before the separate failure audit. Four file-backed independent-connection concurrency tests passed, including controlled SQLite writer-busy handling.
- Relevant checks: Ruff check and format passed for all touched Python files. The final `pnpm full:check` exited 0 with explicit test defaults (`RTSP_URL_TEMPLATE=rtsp://localhost:8554/channel{channel_id}`, no protected backup directory) and `PYTEST_XDIST_AUTO_NUM_WORKERS=2`: backend **1,359 passed, 5 skipped**; frontend **357 passed**; TypeScript, ESLint, Ruff, Prettier, production build, and isolated Chromium login **1 passed**. The push-triggered `pnpm check` hook also exited 0 with backend **1,359 passed, 5 skipped** and frontend **357 passed**. Existing Passlib, SQLite-reflection, Vite config-loader, and jsdom media-method notices remain.
- Gate retries/deviations: the first full-check attempt inherited machine RTSP/protected-backup settings and had two unrelated existing-test failures; both failing tests passed when rerun with test defaults. The next run used unrestricted xdist and Vitest reported all 350 assertions passed but failed to start one worker under concurrent resource pressure. The final run bounded backend xdist to two workers and completed the full gate successfully. No repository config was changed for this environment workaround.
- Paper sync: checked the current `REVISED_FINAL_PAPEL` document and `ADAS_Paper_Audit_Tracker` read-only. P2 leaves public password login unchanged and keeps the router unregistered; the paper's FR-01, password-only login flow, and statement that staged MFA storage is unused before cutover remain accurate. No P2 paper finding or Drive edit was needed. The existing local P1 paper-sync proposal remains a separate pending item.
- Branch/commit/PR: `feat/mfa-backend`, implementation commit `a0131395c9d94683a6e1aa7620f5047a7260ebc7`, [PR #242](https://github.com/bayie27/adas-capstone/pull/242) open and unmerged. No P3 work or merge was performed.

Update this section and the overview. Do not activate the router, start P3, or merge automatically.
