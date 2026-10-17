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

- [ ] Read the existing auth route, dependencies, sessions/audit services, error handlers, redaction, and limiter. Identify any core/global Settings use the test fixture must patch; do not assume explicit Settings propagates everywhere.
- [ ] Write and run failing service/API tests for password stage (no AuthSession/last_login/LOGIN_SUCCESS), generic password failures, enrollment-required absent credentials, challenge expiry and supersession, safe status/QR refresh, and enrollment confirmation outputs. Use the exact routes and discriminants in the contract.
- [ ] Implement per-user opaque challenge issuance, pending encryption, purpose/state/version/password-change guards, idempotent cancellation, and safe provisioning. Refresh must reveal the same pending seed with the original deadline; get/status endpoints never create new seeds.
- [ ] Implement ordinary TOTP verification and initial confirmation. Accept a step once across all TOTP-protected operations; confirmation stores the pending factor's confirming step as used. No broad PyOTP valid_window check without a persisted accepted step.
- [ ] Keep routes thin: gather context/authorization, call the service, apply committed cookie instructions/response body, and close declared WebSockets after commit. Revalidate active account/session inside service writes; do not trust an ORM object loaded earlier as current authority.
- [ ] Run the new selectors, including unknown/inactive users, malformed and stale challenge cookies, wrong-purpose submission, and request-validation secret redaction. Preserve existing generic password behavior and origin checks.

## Task 2 — recovery and factor management

- [ ] Write failing tests for interrupted recovery using a different unused code; consumed-code replay; recovery_verify refusing password-only enrollment; remaining codes invalidated only after confirmation; and exhaustion of the last recovery code. Exhaustion is a lockout outcome, not permission for a reset endpoint.
- [ ] Implement recovery acceptance as one transaction: consume one code, disable old seed, advance version, revoke all sessions, create recovery_enroll challenge/pending seed, audit MFA_RECOVERY_USE. Return no full session. Deleting the challenge or restarting password login never restores the old factor or grants seed access without another unused code.
- [ ] Write failing tests for replacement start requiring unused old-factor TOTP, old factor usable until confirmation, expiry/cancellation preserving it, confirmation sign-out everywhere, and replacement one-time codes returned after commit. Implement the exact two-phase semantics.
- [ ] Write failing rotation tests: fresh password+TOTP, all old codes invalid, single-use replay accounting, sessions preserved, challenge invalidated, no login-success/timestamp change. Implement rotation.
- [ ] Test demo enrollment with a fresh password and subsequent new-seed proof, and demo replacement/rotation with fresh password+active TOTP. Reject unenrolled-normal management sessions and recovery-pending attempts to bypass recovery proof. Service tests may construct explicitly marked demo sessions; normal app wiring waits for P4.
- [ ] Implement management status and the session-to-enrollment route. A demo enrollment completion creates a new legitimate totp session only after both proofs and revokes preceding demo sessions; it never relabels a session without verification.

## Task 3 — failure accounting, transaction rollback, and concurrency

- [ ] Use a separate MFA limiter with independent per-user_id and IP dimensions. A correct password, new cookie, cancellation, or QR fetch cannot reset its failures. Apply the configured threshold/window and Retry-After; do not add a new limiter service/dependency.
- [ ] Test account/IP isolation, exact expiry/limit boundaries, missing/invalid Retry-After UI-independent API semantics, denied/failure audit results, and no credential/session changes for rejected attempts. State the inherited in-process restart limitation honestly.
- [ ] Add tests that force audit.record to fail during login, recovery consumption, enrollment, replacement, and rotation. Assert the entire primary action rolls back and failure recording happens only after rollback. Never use an unrelated committed action to compensate for audit failure.
- [ ] Use a real temporary file-backed SQLite engine, separate Sessions/connections, and a barrier to race two submissions of the same TOTP, recovery code, and enrollment confirmation. Exactly one action wins; the loser receives a controlled error and no duplicate session/batch/audit success. Do not use StaticPool's one connection to claim race safety.
- [ ] Implement writer reservation and atomic acceptance under contract §4, reloading password/account/version state after acquiring it. Reproduce and handle busy failures with the existing error envelope; never retry an already-committed one-time action blindly.
- [ ] Expand redaction to configured MFA keys and nested audit secret keys; test log/error/audit output with sentinel passwords, seeds, OTPs, recovery codes, provisioning URIs, ciphertext, and challenge tokens. Avoid dynamically retaining every OTP in global redaction state; prevent logging proof payloads at the source.
- [ ] Remove any unintended seed/code repr logging from service records. Store neither secrets nor plaintext one-time codes in durable response caches.

## Task 4 — adapter verification while dormant

- [ ] Test body contracts, cookie paths/flags/deletion, GET no-mutation, no-store including error responses in the isolated adapter app, challenge copied into a full-session cookie, and full-session cookie used where a challenge is required. Reject token confusion.
- [ ] Add composable challenge invalidation and startup decryption validators for P4. They must not commit an existing user's password-change transaction or silently provision the schema.
- [ ] Prove the ordinary app still exposes no new MFA endpoints and its existing login behavior/browser test is unchanged. Main.py does not include mfa.router yet. No unguarded helper endpoint may mint challenges or reveal seeds.

## Verification and completion

```powershell
uv run pytest backend/tests/test_mfa_service.py backend/tests/test_mfa_api.py backend/tests/test_mfa_concurrency.py
uv run pytest backend/tests/test_auth.py backend/tests/test_sessions.py
```

Use targeted selectors during red/green work. Run relevant lint/format checks, walk matrix B01–B13 and C01–C05, then run `pnpm full:check` at the pre-PR gate. Shared core edits get full backend scope through that gate. Do not run the separate migration procedure unless schema actually changed; a discovered schema defect must be repaired with a new reviewed/tested migration, not an edited historical revision.

## Completion notes — executor fills

- Status: Not started.
- Service/API signatures and any approved corrections: Not verified by implementation.
- Red/green and independent-connection race results: Not executed.
- Redaction/rollback/API contracts and ordinary-login regression results: Not executed.
- Pre-PR gate, branch/commit/PR, baseline failures and blockers: Not recorded.

Update this section and the overview. Do not activate the router, start P3, or merge automatically.
