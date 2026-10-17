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

- [ ] Write failing integrated tests for the current password-only bypass: correct password alone must no longer yield a session/profile or access protected REST/WS. Cover initial enrollment and an already enrolled user's login through the actual app factory.
- [ ] Add the separate P4 migration at the actual P3 head. Revoke all existing sessions using mfa_rollout, clear staged challenges, and append one system MFA_ROLLOUT event atomically. Preserve historical ids/data/audit triggers. Repeat upgrade head is a no-op; a migration failure leaves no partial rollout.
- [ ] Replace POST /api/auth/login with P2's thin password adapter, register mfa.router, and supply distinct app-state password/MFA limiters. Update the active LoginResponse schema to ChallengeState. Remove the legacy user-on-password-success path and any staged response fallback.
- [ ] In shared REST/WS authentication, require active DB session/account and either valid enrolled/version-matching totp or explicitly enabled demo impersonation. Correctly signed legacy password sessions fail even if accidentally unrevoked. Keep issuer/audience/expiry/user-id binding and current DB-role authorization.
- [ ] Extend logout to invalidate and clear the matching challenge cookie as well as the existing session cookie; retain idempotency and after-commit socket closure. Scope no-store middleware/error handling to all auth responses, including schema/origin/429 failures.
- [ ] Wire invalidate_user_challenge into successful password change/reset, disable, and role-change transactions. Show stale challenges cannot survive deactivate→reactivate or reset→old-challenge reuse. Preserve ordinary username-change identity behavior.
- [ ] Update auth_headers/login test helpers to complete actual MFA where tests need authentication. Keep explicit unenrolled fixtures for enrollment tests and explicit enrolled fixtures for other domain tests. Use a controllable service clock for step boundaries/repeated logins, not sleep or a bypass flag. Do not suppress audit events to keep old row-count expectations green.

## Task 2 — activate the frontend and protect one-time output

- [ ] Mount MfaLoginFlow at the existing /login entry point and MfaSettingsCard in Profile. Replace active legacy login types/adapters and remove stale assumptions that password success contains user. Client auth-store population waits for completed MFA and any initial code acknowledgment.
- [ ] Mount P3's MfaSensitiveFlowProvider at the router root, outside protected-route guards. It owns only in-memory recovery-code presentation and completion callbacks; it never persists secrets. Wire Profile's onSessionRevoked to immediate auth/query clearing and onSignedOut to navigation after acknowledgment. The host survives the intervening route change.
- [ ] During replacement confirmation, acquire the existing scoped redirect suspension before sending the request. After success, keep the host mounted with the returned codes, clear auth/query state, honor the server cookie removal, and release suspension on acknowledgment/unmount. Failure releases it promptly. Test socket-close-before-response and response-before-close; neither may discard codes or leave expiry permanently suppressed.
- [ ] Initial/recovery enrollment returns a real server session; the /login flow keeps client role unset until acknowledgment. Rotation displays new codes and preserves login. Cancellation and invalid proof stay inline. Lost output/reload directs users to fresh login/rotation, never a backend redisplay route.
- [ ] Add visible demo impersonation labeling using the server's session method, including switches/reseeds. Do not store a server credential in the existing display-only auth cache. GET /mfa/status supplies current method after refresh.
- [ ] Run focused Login/Profile/provider/realtime tests before broad integration. Preserve accessible labels, manual provisioning, deadline/countdown behavior, and generic failures from P3.

## Task 3 — enforce key configuration and constrain demo sessions

- [ ] Fail startup on missing/malformed MFA_ENCRYPTION_KEY in every environment. Validate key structure before runtime startup writes and validate stored ciphertext after schema availability but before camera resets, schedulers, background workers, or traffic. A structurally valid wrong key with existing ciphertext is also a startup failure. Never print its value or a raw Pydantic error carrying it.
- [ ] Make tests/CI supply fresh disposable key material where an app starts. Do not commit a working default key in .env.example. Preserve migration-only/config-only construction without startup and without key invention.
- [ ] Inventory every create_session/create_session_token/AuthSession call, including dev/UAT helpers. Normal paths can mint only after completed MFA; demo paths preserve current caller gates and mark their rows as demo_impersonation. Demo challenges never satisfy full auth.
- [ ] When DEV_TOOLS_ENABLED is false, dev routes are absent and existing demo sessions fail both REST and WS. When true on a LAN production build, the intentional switch/reseed workflow still works. Do not treat ENVIRONMENT=production as synonymous with operational deployment.
- [ ] Operational setup examples explicitly use DEV_TOOLS_ENABLED=false and non-demo accounts. Demo examples explain the exception. Demo MFA management requires fresh proofs exactly as the normal management endpoints do.

## Task 4 — restore and rollback safeguards

- [ ] Write failing disposable-file tests for restoring a post-MFA snapshot with the right key, missing/wrong key, corrupt ciphertext, older/pre-MFA schema, restored active sessions/challenges, and automatic emergency rollback. Preserve selected-backup checksums and contents throughout.
- [ ] Add candidate preflight/transform helpers within maintenance/restore.py, using explicit key/config input from its CLI call sites rather than hidden environment values in shell commands. A candidate must have the current MFA-capable Alembic head and decryptable stored seeds before swap. Reject earlier known revisions before replacement; do not silently upgrade them or rely on readiness to discover the problem after swap.
- [ ] On the temporary candidate, revoke all sessions with mfa_restore, remove challenges/pending seeds, and append MFA_RESTORE_INVALIDATE in one transaction. Preserve snapshot active credentials/recovery rows and recovery_pending state. Recheck integrity/foreign keys after transformation; checksum validation of the original artifact precedes transformation.
- [ ] Use the same transformation on the emergency rollback copy before swapping it back. Missing key/schema/decryption failure never selects a password-only fallback or silently discards MFA. Preserve leases, restore identities, protection tiers, readiness state, post-restore audit, and failure cleanup.
- [ ] Extend current CLI/coordinator/PowerShell tests only for changed integration boundaries. The working tree had unrelated edits in these files at planning time: do not replace entire files from an archived example or discard current changes.

## Task 5 — browser/CI verification against disposable accounts

- [ ] Update e2e/login.spec.ts and add e2e/mfa.spec.ts plus shared test-only helpers. Exercise real UI enrollment and ordinary login; do not stub /mfa responses or use impersonation as evidence of normal MFA. Assert protected REST/WS denial before completion.
- [ ] Give each MFA scenario its own disposable account so tests never compete for the single account challenge or accepted step. Seed those accounts only through the guarded isolated runner's setup, with no application bypass endpoint. Use ordinary authenticated APIs/UI where the behavior itself is under test.
- [ ] Cover recovery→new enrollment→fresh login; replacement→one-time codes surviving sign-out→login; rotation invalidating old codes without logout; and wrong-code countdown/error behavior. Keep clocks deterministic in backend tests and avoid browser assertions tied to a just-expiring TOTP second.
- [ ] Generate test TOTP through an independent test helper implementing RFC 6238 or a pinned test dependency; assert it against a published known vector. Read only disposable provisioning values. Disable trace/video/screenshot capture during secret-entry/display flows; on failure keep redacted assertions/status evidence instead of secret-bearing network dumps.
- [ ] Refuse destructive/enrollment MFA specs in E2E_LIVE_DEPLOYMENT mode. Update optional visual authentication helpers to complete MFA on isolated data without rebasing Linux screenshots from Windows. Existing YAML/security/UAT scripts using password-only login also need a compatible test-auth helper or explicit instructions; scan them rather than fixing only the first failing test.
- [ ] Update CI so generated ephemeral keys/credentials and isolated DB paths are provided before startup. Remove the default e2e job's root-DB reset dependency once the isolated runner owns provisioning. Preserve separate migration CI and no secret artifacts in uploads.

## Verification and completion

Use narrow red/green selectors first, including new `backend/tests/test_mfa_cutover.py` and `backend/tests/test_mfa_restore.py`. Then:

```powershell
uv run pytest backend/tests/test_mfa_cutover.py backend/tests/test_mfa_restore.py backend/tests/test_auth.py backend/tests/test_sessions.py backend/tests/test_realtime.py backend/tests/test_dev_tools.py
pnpm --filter frontend test:run src/pages/Login.test.tsx src/pages/ProfileSettings.test.tsx src/pages/auth src/pages/profile/MfaSettingsCard.test.tsx
```

Run the separate disposable migration checks in CONTRIBUTING.md; include seeded pre-cutover upgrade and a failed-upgrade rollback assertion. Walk matrix X01–X10 and R01–R06. Run `pnpm full:check` once at the pre-PR gate; its full backend suite supplies the broad core/conftest/app-factory regression scope. E2E must actually execute, not skip for missing credentials. Do not claim physical-phone, LAN-TLS, protected-device restore, or production rollout from loopback tests.

## Completion notes — executor fills

- Status: Not started.
- Rollout migration revision, minted-session inventory, API/WS cutover results: Not recorded.
- UI sign-out/code-display ordering, demo gating, key startup failures: Not executed.
- Candidate/rollback transformation, backward-schema rejection, backup immutability: Not executed.
- Migration/pre-PR/E2E results, branch/commit/PR, blockers/deviations: Not recorded.

Update the overview and this section. Prepare release/operations prerequisites for P5; do not execute a real operational cutover or start P5 automatically.
