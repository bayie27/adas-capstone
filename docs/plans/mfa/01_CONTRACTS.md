# MFA shared implementation contract

**Status:** Approved behavior plus adopted engineering defaults; implement in P1–P5.  
**Audience:** Every manually started Luna Max executor. Read [00_OVERVIEW.md](00_OVERVIEW.md) first.

This contract fixes cross-package names and outcomes. Preserve these interfaces across sessions; a current-source mismatch is a finding to resolve and record, not permission for frontend/backend to invent separate wire shapes. The public behavior below is active only after P4.

## 1. States and successful authentication

Per-account MFA state is `unenrolled`, `enrolled`, or `recovery_pending`. An absent credential record means unenrolled, including newly created accounts. Create its record transactionally on the first MFA flow; no user-create route needs to mint a seed.

| Event                                    | Required proof                                                     | Committed outcome                                                                                                                                                                                                        |
| ---------------------------------------- | ------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Password stage, enrolled account         | Active account + current password                                  | New `login` challenge; no AuthSession, login timestamp, or login-success event.                                                                                                                                          |
| Password stage, unenrolled account       | Active account + current password                                  | New `enroll` challenge with encrypted pending seed.                                                                                                                                                                      |
| Password stage, recovery-pending account | Active account + current password                                  | New `recovery_verify` challenge; still requires an unused recovery code before a new seed can be shown.                                                                                                                  |
| Ordinary MFA login                       | `login` challenge + unused valid TOTP step                         | Consume challenge/step; create full `totp` session; stamp last_login; LOGIN_SUCCESS.                                                                                                                                     |
| Accept recovery code                     | `login` or `recovery_verify` challenge + unused recovery code      | Consume that code; remove old active seed; mark recovery_pending; advance credential version; revoke all sessions; replace challenge with `recovery_enroll` + new pending seed. Retain other codes. No full session yet. |
| Initial/recovery enrollment confirmation | Corresponding challenge + valid pending-seed TOTP                  | Enable new factor; advance version; store confirming step as used; replace recovery batch; consume challenge; revoke prior sessions; create full totp session; stamp last_login; MFA_ENROLL + LOGIN_SUCCESS.             |
| Replacement start                        | Current full/demo session + current password + unused current TOTP | Create `replace` challenge and pending seed; consume old factor's TOTP step; old factor and sessions remain active.                                                                                                      |
| Replacement confirmation                 | `replace` challenge + valid pending-seed TOTP                      | Atomically swap seeds, advance version, replace recovery batch, consume challenge, revoke all sessions; MFA_REPLACE. Return codes; no new session and no LOGIN_SUCCESS.                                                  |
| Recovery-code rotation                   | Current full/demo session + current password + unused active TOTP  | Consume TOTP step and replace recovery batch atomically; keep sessions, factor/version, and last_login unchanged; MFA_RECOVERY_ROTATE. Invalidate any outstanding MFA challenge to avoid a stale flow.                   |

The full session's maximum lifetime starts at completed authentication, never at password validation. Issuing codes is part of the same transaction as the factor/batch change. Only return plaintext codes after commit. Audit failure rolls everything back, including accepted steps, consumed codes, session creation/revocation, and timestamps.

## 2. Persistence and cryptography — P1 owns the schema

Create `backend/app/models/mfa.py`, export its models through `app.models`, and use named CHECK/unique constraints and UTC-aware stored timestamps throughout.

| Table/model                             | Fields and constraints                                                                                                                                                                                                                                                                                                                                                                                                                    |
| --------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `mfa_credential` / `MfaCredential`      | `user_id` PK/FK to user (CASCADE), `state` constrained to the three states above, `active_secret_ciphertext` nullable, `credential_version` integer >=0, `last_accepted_step` nullable integer >=0, `enrolled_at` nullable UTC, `recovery_started_at` nullable UTC, `recovery_generation` integer >=0, `created_at`, `updated_at`. Enrolled requires active ciphertext and enrolled_at; other states have no active ciphertext/last step. |
| `mfa_challenge` / `MfaChallenge`        | `user_id` PK/FK (CASCADE), `token_hash` unique 64-char digest, `purpose` in `login,enroll,recovery_verify,recovery_enroll,replace`, `credential_version` snapshot, `password_changed_at` nullable UTC snapshot, `pending_secret_ciphertext` nullable, `created_at`, `expires_at`. Only enrollment/replace purposes contain a pending seed. PK enforces one flow per account.                                                              |
| `mfa_recovery_code` / `MfaRecoveryCode` | Integer `recovery_code_id` PK; `user_id` FK (CASCADE), `generation` >=1, `code_hash` 64-char digest, `created_at`, `consumed_at` nullable. Unique `(user_id,generation,code_hash)` and index `(user_id,generation,consumed_at)`. Retain consumed rows until their batch is replaced; never store plaintext.                                                                                                                               |
| Existing `auth_session`                 | Add constrained `auth_method` in `password,totp,demo_impersonation`, initially server-default `password` for P1–P3 compatibility; add nullable `mfa_credential_version`. Require a version for totp sessions. Legacy password rows may remain as revoked history; P4 removes password-only creation paths and rejects that method at runtime.                                                                                             |

Extend session revocation reasons with `mfa_rollout`, `mfa_recovery`, `mfa_replacement`, `mfa_enrollment`, and `mfa_restore`. Preserve existing reasons. Extend both the audit catalog and its CHECK constraint with `MFA_CHALLENGE_START`, `MFA_CHALLENGE_CANCEL`, `MFA_ENROLL`, `MFA_REPLACE`, `MFA_RECOVERY_USE`, `MFA_RECOVERY_ROTATE`, `MFA_ROLLOUT`, and `MFA_RESTORE_INVALIDATE`.

Use a new additive migration for P1. Rebuild SQLite constraints safely and restore audit immutability triggers; never rewrite historical audit values. P4 adds a separate cutover migration for session/challenge revocation and one system MFA_ROLLOUT row in the same transaction. Downgrade must refuse removal of MFA storage once any enrolled/recovering credential, recovery code, or totp session exists; safe empty-foundation upgrade/downgrade remains testable. Roll back a deployed MFA release with its verified backup and matching code, not a destructive downgrade of live MFA data.

Add direct backend dependencies `pyotp` and `cryptography`; frontend `qrcode.react` belongs to P3. Resolve supported versions with current upstream docs and the pinned environment, update lockfiles, and record the selected versions. Never install a floating package at runtime.

`MFA_ENCRYPTION_KEY` is a `SecretStr` environment setting, independent of SECRET_KEY. P1–P3 may construct Settings without it because no MFA flow is publicly active. Crypto helpers always require a valid key when called. P4 requires it at application startup in every environment; migration/config inspection can still construct Settings without starting the app. No bypass setting remains in the final application.

Fernet encrypts seeds without a token-age TTL; application challenge expiry governs pending seeds. Verify structure and decrypt every stored active and pending ciphertext at startup and candidate-restore preflight. Empty MFA storage can validate only key structure. Missing/wrong keys or corrupt ciphertext yield a secret-free diagnostic and fail closed. Do not silently replace, skip, or clear bad credentials.

Use 32 CSPRNG bytes for each challenge token (`secrets.token_urlsafe(32)`); store SHA-256 of its ASCII bytes. Recovery codes use 16 CSPRNG bytes encoded as 32 uppercase hex characters displayed in four groups of eight separated by hyphens. Accept case-insensitive codes, trim outer whitespace, remove display hyphens, then require exactly 32 hex characters. Hash the domain-separated ASCII value `adas-mfa-recovery-v1:{user_id}:{generation}:{canonical_code}` with SHA-256. High entropy makes password-style stretching unnecessary; compare digests in constant time and never query another user's batch.

## 3. HTTP API — P2 implements; P4 registers

All routes below are relative to `/api/auth`. Existing password login keeps its form-urlencoded username/password input. New mutation bodies are JSON. Return the existing ApiError envelope on errors, with no submitted secret in validation details.

Shared response shapes:

```typescript
type ChallengePurpose = "login" | "enroll" | "recovery_verify" | "recovery_enroll" | "replace"
type ChallengeState = {
  status: "mfa_required" | "enrollment_required"
  purpose: ChallengePurpose
  expires_at: string // UTC ISO 8601; server authority
}
type CompletedLogin = { status: "authenticated"; user: CurrentUserResponse }
type CompletedEnrollment = CompletedLogin & { recovery_codes: string[] }
type CompletedReplacement = {
  status: "reauthentication_required"
  recovery_codes: string[]
}
```

| Method/path                         | Authorization and input                                                                                                          | Successful output                                                                                                                                                                                                                            |
| ----------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| POST `/login`                       | Current username/password form. Preserve generic inactive/unknown/wrong-password behavior.                                       | 200 ChallengeState; set new challenge cookie. Never return a user profile/full-session credential here.                                                                                                                                      |
| GET `/mfa/challenge`                | Challenge cookie only.                                                                                                           | 200 ChallengeState; no seed, code, user profile, or deadline extension.                                                                                                                                                                      |
| DELETE `/mfa/challenge`             | Challenge cookie when present; idempotent if missing/expired.                                                                    | 204; delete matching challenge and clear cookie. Recovery-pending state never reverts; replacement cancellation preserves active seed.                                                                                                       |
| POST `/mfa/enrollment/start`        | `enroll`, `recovery_enroll`, or `replace` challenge; empty JSON body.                                                            | 200 `{ provisioning_uri, manual_key, issuer: "ADAS", account_name, expires_at }`. Reveal the existing pending seed; repeated calls/refresh do not generate a different seed or extend expiry.                                                |
| POST `/mfa/enrollment/confirm`      | Same purposes; `{ code: string }`, exactly six ASCII digits.                                                                     | 200 CompletedEnrollment for enroll/recovery_enroll; CompletedReplacement for replace. Clear challenge cookie. Set normal session cookie only for CompletedEnrollment.                                                                        |
| POST `/mfa/verify`                  | `login` or `recovery_verify` challenge; `{ method: "totp" \| "recovery", code: string }`. recovery_verify accepts recovery only. | 200 CompletedLogin for totp; ChallengeState with purpose recovery_enroll and new cookie for recovery.                                                                                                                                        |
| GET `/mfa/status`                   | Existing authenticated normal/demo session.                                                                                      | 200 `{ state, recovery_codes_remaining, enrolled_at, auth_method }`; count current batch only; no secrets.                                                                                                                                   |
| POST `/mfa/recovery-codes/rotate`   | Existing session; `{ password: string, code: string }` (active TOTP).                                                            | 200 `{ recovery_codes: string[] }`; keep full-session cookie, clear invalidated challenge cookie.                                                                                                                                            |
| POST `/mfa/replacement/start`       | Existing session; `{ password: string, code: string }` (active TOTP).                                                            | 200 ChallengeState with purpose replace and a challenge cookie. New seed retrieved through enrollment/start.                                                                                                                                 |
| POST `/mfa/enrollment/from-session` | Existing demo session for an unenrolled account only; `{ password: string }`.                                                    | 200 enroll ChallengeState after fresh password proof. Enrolled accounts use replacement; recovery-pending accounts must log in and use recovery. Confirmation makes a real totp session after all proofs, never by relabeling impersonation. |

`mfa_required` covers login/recovery_verify; `enrollment_required` covers enroll/recovery_enroll/replace. Provisioning uses PyOTP's URI builder and issuer ADAS, never hand-built URLs. Use the current username as the label when the pending seed is issued; username is descriptive, immutable user_id is identity.

MFA cookie: `adas_mfa_challenge`, HttpOnly, SameSite Strict, host-only, Path `/api/auth`, Secure from the same HTTPS/cookie setting as normal sessions. Max-Age is remaining challenge lifetime. Normal cookie remains configured `adas_session`, Path `/`. Clear each cookie with its exact attributes/path. No bearer/header/query fallback. A raw challenge copied into adas_session is invalid.

Use `Cache-Control: no-store` on all `/api/auth` success/error responses after cutover, including 422 validation, rate-limit, and origin rejection. Preserve origin checks on all unsafe browser requests, CORS credential handling, and exposed Retry-After. `/logout` also invalidates the matching challenge (if sent), clears both cookies, and preserves existing idempotent full-session logout behavior.

| Failure                                                | Status/code                           | Client behavior                                                                                                  |
| ------------------------------------------------------ | ------------------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| Unknown/inactive user or wrong password                | Existing 401 AUTH_INVALID_CREDENTIALS | Inline generic error; do not reset valid sessions merely because a step-up password was wrong.                   |
| Wrong/used TOTP or unusable recovery code              | 401 MFA_INVALID_CODE                  | Generic inline failure; no code/step distinction or global session redirect.                                     |
| Missing/expired/replaced/wrong-purpose/stale challenge | 401 MFA_CHALLENGE_INVALID             | Clear challenge cookie; restart password flow. Do not reveal account existence or why the token failed.          |
| Per-user/IP MFA limit                                  | 429 AUTH_RATE_LIMITED + Retry-After   | Show server-driven countdown that input changes and password restarts cannot bypass.                             |
| Body shape/size errors                                 | 422 existing validation envelope      | No echoed password/code/seed, including Pydantic context.                                                        |
| Wrong account state for authenticated management       | 409 MFA_STATE_CONFLICT                | Refetch safe status and show a restart instruction.                                                              |
| Missing/bad runtime key or DB busy                     | 503 TEMPORARILY_UNAVAILABLE           | Fail closed; no factor/session mutation or secret-bearing diagnostic. Normal startup prevents bad-key operation. |

## 4. Service interfaces, transactions, and replay

P1 creates `backend/app/core/mfa.py`: `generate_totp_secret() -> str`, `encrypt_totp_secret(secret: str, key: str) -> str`, `decrypt_totp_secret(ciphertext: str, key: str) -> str`, `matching_totp_step(secret: str, code: str, now: datetime) -> int | None`, `generate_recovery_codes(count: int = 10) -> list[str]`, `hash_recovery_code(user_id: int, generation: int, code: str) -> str`, and `hash_challenge_token(token: str) -> str`. It also owns input canonicalization and structurally validating a key. Functions do no persistence, logging, or environment lookup; time is explicit.

P2 creates `backend/app/services/mfa.py` and `backend/app/schemas/mfa.py`. Keep the existing session creation/revocation helpers composable within its transactions. Introduce these frozen service records in mfa.py:

- `MfaRequestContext(source_ip: str | None, user_agent: str | None)`.
- `MfaServiceResult(body: BaseModel | None, challenge_token: str | None = None, challenge_expires_at: datetime | None = None, clear_challenge: bool = False, session_token: str | None = None, clear_session: bool = False, close_user_id: int | None = None, close_reason: str | None = None)`. Tokens/codes are transient; disable generated repr for the record and sensitive body fields and never log the result. Body models implement section 3 exactly.

Route-facing functions take `engine: Engine` first and keyword-only arguments:

| Function                        | Further arguments                                                                 |
| ------------------------------- | --------------------------------------------------------------------------------- |
| `begin_password_login`          | `username, password, context, settings, password_limiter, mfa_limiter`            |
| `get_challenge`                 | `challenge_token, settings`                                                       |
| `cancel_challenge`              | `challenge_token` (nullable), `context, settings`                                 |
| `get_enrollment`                | `challenge_token, settings`                                                       |
| `confirm_enrollment`            | `challenge_token, code, context, settings, mfa_limiter`                           |
| `verify_challenge`              | `challenge_token, method, code, context, settings, mfa_limiter`                   |
| `get_mfa_status`                | `session_id, user_id, settings`                                                   |
| `rotate_recovery_codes`         | `session_id, user_id, password, code, context, settings, mfa_limiter`             |
| `begin_replacement`             | Same arguments as rotate_recovery_codes                                           |
| `begin_enrollment_from_session` | `session_id, user_id, password, context, settings, password_limiter, mfa_limiter` |

All return MfaServiceResult. Use explicit annotations: token/username/password/code/method/session_id are strings, user_id is int, context is MfaRequestContext, settings is Settings, limiters are SlidingWindowLimiter, engine is SQLAlchemy Engine. `method` is a Literal totp/recovery. Route dependencies verify normal JWT/session identity before passing management ids; services reload current active session/account/state before mutation. Challenges themselves never satisfy normal authentication dependencies.

Also expose composable helpers `invalidate_user_challenge(session: Session, user_id: int) -> None` for existing audited user/password transactions and `validate_stored_mfa_secrets(engine: Engine, key: str) -> None` for startup. These do not secretly commit caller-owned transactions.

Each mutating route-facing service owns a fresh short transaction. On SQLite, take a writer reservation with BEGIN IMMEDIATE before reading/accepting one-use state; use file-backed connections and the existing busy timeout in concurrency tests. Do password hashing work before acquiring the writer reservation, then re-read and compare the verified password hash/account state inside it; a changed hash causes generic rejection. Never perform network/file/WebSocket I/O inside the transaction. Read-only helpers use ordinary short sessions.

Within that reservation, recheck expiry (inclusive), active account, password_changed_at snapshot, credential version, purpose, and origin-derived authorized context. For a TOTP match require its step > last_accepted_step; select the highest matching eligible step if a rare adjacent-step collision occurs. Store the accepted step in the same transaction as the protected action/audit. A pending seed's confirming step becomes the new active factor's used step. Every TOTP-protected action uses the same replay state; users may need the next code after login or replacement.

Use a separate app-state MFA limiter with the existing 10 failures/300 seconds settings, keyed by immutable user_id and source IP; never reset it on password success, new challenge, cancellation, or QR refresh. Preserve password-stage limiter behavior except defer its success reset until full login. MFA success may reset that account's MFA key, not its aggregate IP history. Failed proofs and 429s are audited; infrastructure busy/key errors are not invalid-code guesses. Reuse the configured single-worker deployment assumption; no Redis/new limiter dependency. Document existing in-process limiter restart behavior rather than claiming durable lockout.

On recovery acceptance, replacement/enrollment confirmation, password change/reset, account disable, or role change, revoke appropriate sessions and invalidate relevant challenges in the same successful transaction. Existing user mutations call invalidate_user_challenge before their commit. After commit the route closes affected WebSockets with the declared reason. No close or cookie is issued for a rolled-back mutation. Full totp sessions require an enrolled credential whose version matches the session row; impersonation additionally requires enabled demo tooling. DB role is authoritative.

## 5. Auditing and sensitive output

Use existing audit.record with the primary transaction and audit.record_out_of_band only after rollback for denials/failures. Preserve append-only storage. Use action phases in detail rather than new actions for every internal write:

- MFA_CHALLENGE_START for a new password-verified login/initial/recovery-verify challenge; no LOGIN_SUCCESS yet. Supersession/pending-seed creation is internal to that action.
- MFA_CHALLENGE_CANCEL for cancellation of an existing challenge; idempotent empty cancellation needs no row.
- MFA_ENROLL with source initial/recovery/demo on successful enrollment, plus LOGIN_SUCCESS for the created session.
- MFA_REPLACE with phase started or confirmed; starting is not described as factor replacement completed.
- MFA_RECOVERY_USE when a code is consumed; no LOGIN_SUCCESS until new enrollment completes.
- MFA_RECOVERY_ROTATE for batch rotation; MFA_ROLLOUT and MFA_RESTORE_INVALIDATE for system transitions.
- LOGIN_FAILURE for password/challenge-login/enrollment proof denials, with safe stage/reason values. Management denials use the management action, not a fictitious login attempt.

Never store/log codes, raw challenge tokens, seed/ciphertext, provisioning URIs, password values, or encryption keys. Extend core redaction's configured secret list and audit banned keys to MFA names. Validation errors, exception reprs, traces, screenshots, and browser attachments are also potential leaks; use only disposable test factors and suppress sensitive-screen tracing/attachments. Safe operational audit fields are user identity, action/phase/source, counts, and coarse failure reason, never submitted proof.

## 6. Frontend integration — P3 components, P4 activation

Keep `/login` as the public authentication entry point and use its local state machine: password → TOTP/recovery choice → enrollment → one-time codes → dashboard. Use the challenge-status endpoint on refresh; no seeds, codes, tokens, or provisioning URIs in URL parameters, Zustand persistence, localStorage/sessionStorage, TanStack Query caches, analytics, or console output. Clear the password field on password-stage success.

Create focused components under `frontend/src/pages/auth/`: `MfaChallengePanel.tsx`, `MfaEnrollmentPanel.tsx`, `RecoveryCodesPanel.tsx`. Profile uses `frontend/src/pages/profile/MfaSettingsCard.tsx` with status, remaining count, replace and rotate actions, and fresh proof inputs. QR rendering uses QRCodeSVG from qrcode.react plus manual key, app setup guidance, and cloud-sync-disabled instructions. Existing house components remain authoritative; no new design system.

P3 also creates `frontend/src/components/auth/MfaSensitiveFlowProvider.tsx`, activated at the router root only in P4. Its exported `useMfaSensitiveFlow()` exposes `showCodes({ codes, accountName, onAcknowledged })` and `clearCodes()`; codes are string[], accountName is string, and the callback returns void. The provider renders RecoveryCodesPanel outside protected-route guards and clears its in-memory state on acknowledgment/unmount. MfaSettingsCard receives `onSessionRevoked()` for immediate client auth clearing after replacement confirmation and `onSignedOut()` for navigation after code acknowledgment. Register the code display before calling onSessionRevoked. Proof failures invoke neither callback. Ordinary rotation invokes neither callback and uses the same display with an acknowledgment that stays on Profile.

For initial/recovery enrollment, the server session exists after confirmation, but defer client auth-store/navigation changes until code acknowledgment so `/login` does not immediately redirect. This is a UX gate only. For voluntary replacement, clear local auth state/query data after server success but keep the code-display component mounted until acknowledgment, then navigate to login. Ensure post-commit WebSocket closure does not discard that response or unmount its codes screen; use the existing narrowly scoped auth-redirect suspension pattern, released on completion/unmount. Never suppress real auth loss indefinitely.

MFA error codes use an authentication-specific API client or the existing interceptor's explicit non-session-loss exclusions; wrong MFA input must not clear an otherwise valid Profile session. True AUTH_REQUIRED/AUTH_EXPIRED/AUTH_REVOKED still clear it. Do not change behavior by treating every 401 as harmless.

Copy/download actions require explicit user clicks. Downloads contain the ADAS label, account name, date, codes, and offline-storage warning; create a local Blob, then revoke its object URL. Handle clipboard/download failure inline without dismissing the codes. Acknowledgment means the user accepts responsibility, not that ADAS verified a file. Reload/lost-response cannot retrieve a displayed batch: sign in with the working authenticator and regenerate codes with fresh proofs. No backend acknowledgment endpoint or encrypted recovery-code redisplay cache.

## 7. Activation, demo behavior, and restore — P4

P1–P3 are staged additive changes. P2's production app does not register its MFA router or replace POST login. P3 exports components/adapters without wiring login/Profile to them. P4 switches both stacks and removes legacy response fallback branches; no feature flag remains to mint normal password-only sessions. Preserve legacy session rows only as revoked history.

The P4 migration revokes all extant sessions, including demo sessions, with mfa_rollout; clears staged challenges; and records the system rollout atomically. It never enrolls users, edits password hashes, or manufactures login successes. Startup refuses legacy password sessions even if their JWT is correctly signed and their row is accidentally unrevoked.

Demo login-as/reseed keep existing caller authorization and flag gates; mint auth_method demo_impersonation and expose it through `/mfa/status` and the existing dev session response/display so the current session is visibly labeled. Do not ban DEV_TOOLS_ENABLED solely because ENVIRONMENT=production: LAN demos intentionally use production builds. Operational config examples set it false explicitly; authentication rejects existing demo sessions when it becomes false. Review every session-minting path, including UAT/reseed helpers and scripts, not just these two routes.

Restore hooks operate on the temporary candidate database before swap, using its direct read-only/preflight connection and a short explicit write transaction for invalidation. Require its schema revision to equal the running MFA-capable head; reject older/pre-MFA revisions before swap with an actionable compatibility message. Do not auto-migrate backups or mutate the selected backup artifact. Check key decryption for every stored seed, revoke all candidate auth_session rows with mfa_restore, remove candidate challenge rows/pending seeds, and append MFA_RESTORE_INVALIDATE atomically. Enrolled active factors/recovery batch state remain from the snapshot; recovery_pending remains recovery_pending. Validate the transformed candidate again before swap.

Apply the same session/challenge invalidation policy to the emergency rollback copy before its swap: a failed restore must not revive sessions from before the outage. Preserve the existing restore lease, emergency backup, state machine, readiness, and failure handling. CLI and orchestrator call sites must use the configured key without putting it in process arguments/logs. Missing/wrong-key/invalid-schema checks fail before destructive replacement. Key escrow must accompany recovery to a replacement host; the key is never bundled into normal backup artifacts.

## 8. References and verification ownership

Upstream technical references: [RFC 6238](https://www.rfc-editor.org/rfc/rfc6238.html), [PyOTP](https://pyauth.github.io/pyotp/), [Fernet](https://cryptography.io/en/stable/fernet/), [qrcode.react](https://github.com/zpao/qrcode.react), and [OWASP MFA guidance](https://cheatsheetseries.owasp.org/cheatsheets/Multifactor_Authentication_Cheat_Sheet.html). Check current upstream APIs during implementation; do not label TOTP phishing-resistant or claim NIST certification.

Acceptance ownership, required commands, and evidence rules live in [TEST_MATRIX.md](TEST_MATRIX.md). P5 documents the supplied paper's server-only-localization conflict and fresh live-paper proposals; this contract does not authorize edits to Drive or measured-results fabrication.
