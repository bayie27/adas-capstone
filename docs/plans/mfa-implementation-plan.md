# ADAS MFA Implementation Plan

> **Superseded implementation handoff:** Follow [MFA execution overview](mfa/00_OVERVIEW.md), [shared contracts](mfa/01_CONTRACTS.md), and [Luna Max kickoff prompts](mfa/PROMPTS.md). The five-package pack incorporates the 2026-10-17 interview and is authoritative where this earlier plan differs. In particular, unused recovery codes survive interrupted recovery until replacement enrollment completes, voluntary replacement preserves the old factor until confirmation, and server-only localization wording needs an explicit authenticator-device exception. The planning baseline tests are recorded in the overview; the historical “no tests” statement below applies only to this original document's authoring task.

**Status:** Historical high-level plan; executable handoff pack authored; MFA code implementation has not started.  
**Plan date:** 2026-10-16  
**Scope:** Local ADAS authentication only; no paper or application code edits in this task.

## Recommendation and options

| Option                                | Fit for ADAS                                                                                                                                    | Security and effort                                                                                                  |
| ------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| **TOTP authenticator app (selected)** | Fits the existing local FastAPI login; generates codes offline and needs no delivery provider.                                                  | Lowest implementation effort among the suitable self-hosted MFA options. Manually entered codes are phishable.       |
| WebAuthn passkey/security key         | Can remain on-premises, but requires credential registration and assertion flows, browser support, origin/RP configuration, and device support. | Phishing-resistant; greater implementation and rollout effort. Consider if that becomes a hard security requirement. |
| SMS                                   | Requires phone-number collection, an SMS gateway, network connectivity, and delivery operations.                                                | External dependency and carrier risks; conflicts with the paper's local-only constraint.                             |
| Email code                            | No email address or mail-delivery integration exists in the current account model.                                                              | Adds external delivery and is not an appropriate out-of-band authentication method under current NIST guidance.      |
| Managed identity provider             | Would replace or substantially change the custom local account/session model.                                                                   | Poor fit for the local-only architecture and disproportionate to this feature.                                       |

**Decision:** Require TOTP for every Operator and Administrator. This is the easiest option that fits the current on-premises system. TOTP is not phishing-resistant; WebAuthn is the future alternative if that becomes mandatory. The [PyOTP project](https://github.com/pyauth/pyotp) implements the [RFC 6238 TOTP standard](https://www.rfc-editor.org/rfc/rfc6238.html). NIST distinguishes OTP from phishing-resistant WebAuthn, and OWASP recommends single-use recovery codes for recovery ([NIST SP 800-63B](https://pages.nist.gov/800-63-4/sp800-63b.html?locale=en), [OWASP MFA Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Multifactor_Authentication_Cheat_Sheet.html)).

### Confirmed product choices

- MFA is mandatory for all current and future user accounts.
- Every covered user has a phone and may use a standard authenticator app.
- Recovery uses single-use recovery codes only; there is no in-app or administrator MFA reset.
- Keep the existing dev account-switching/reseed exception for isolated demos. Those impersonation sessions are explicitly outside the all-user MFA guarantee and are not operational login paths.
- The system is still in development, so require enrollment immediately and revoke existing local sessions at cutover. A production cutover is a later operations decision.

**Lockout consequence:** If a user loses their phone and all unused recovery codes, they cannot recover through the application. The account remains locked unless a separately authorized, out-of-band database repair is performed; no such repair endpoint is part of this plan.

## Current requirements and paper impact

The supplied final paper says:

- **FR-01, p. 66:** users authenticate with username and password.
- **FR-20, p. 69:** successful and failed logins are audited.
- **NFR-19 and NFR-20, p. 73:** sessions last at most eight hours and can be revoked; system data is kept and processed locally without external cloud services.
- **Login use case, pp. 74-75:** password validation against the local database immediately establishes the session.
- **User and AuthSession descriptions, pp. 119 and 128; login figure, p. 133:** the current model and UI have no MFA state or second step.
- **Security results, pp. 218 and 220:** recorded authentication tests do not cover MFA.

The implementation will change those claims. Preserve the local-only requirement by stating that ADAS provisions the TOTP seed to the user's authenticator app over the local application, stores its server-side copy encrypted, and does not send MFA data to an external delivery or identity service. Users must use local authenticator storage with cloud sync disabled. Update the defense paper only after implementation and verification; this plan does not edit the paper.

## Proposed implementation contract

**Engineering defaults for the later implementation:** use six-digit TOTP codes on a 30-second step, accept one adjacent step on either side, expire login challenges after five minutes and enrollment challenges after fifteen minutes, and issue ten recovery codes with at least 128 bits of CSPRNG entropy each. These are implementation defaults, not additional product choices; change them only if implementation evidence or a system requirement warrants it.

### Authentication flow and API

1. `POST /api/auth/login` validates the username and password using the existing generic-failure and rate-limit behavior. On valid credentials it returns a discriminated status of `mfa_required` or `enrollment_required` and sets a separate short-lived HttpOnly MFA challenge cookie. It does **not** create an `AuthSession`, issue `adas_session`, update `last_login`, or record `LOGIN_SUCCESS` yet.
2. The `adas_mfa_challenge` cookie is distinct from `adas_session`, `SameSite=Strict`, `Secure` under HTTPS, HttpOnly, and `Cache-Control: no-store`. Give TOTP challenges a five-minute lifetime and initial enrollment challenges fifteen minutes. Only MFA endpoints accept it. Normal HTTP dependencies and the WebSocket handshake continue to accept only the completed session cookie.
3. Enrollment endpoints create a pending TOTP seed, return an `otpauth://` provisioning value for an SVG QR code and manual-entry fallback, then confirm it using a valid code. Keep the pending secret encrypted and expire it if enrollment is abandoned. On confirmation, enable MFA, issue the normal eight-hour session, return the user profile, and display a fresh recovery-code batch exactly once. Render the QR in the React UI with `qrcode.react`; never cache or log the provisioning value.
4. `POST /api/auth/mfa/verify` accepts a TOTP code for ordinary login. It creates the normal session and records successful login only after verification. It may also accept a recovery code; consuming one invalidates the old TOTP seed and remaining codes and requires immediate TOTP re-enrollment before dashboard access.
5. Add a status endpoint for Profile Settings and a recovery-code rotation endpoint. Rotating codes requires the current password and current TOTP, invalidates every previous code, and displays the replacements once. Allow authenticator replacement only after current password and TOTP verification. Do not add disable-MFA or administrator-reset endpoints.

### TOTP, persistence, and secrets

- Use PyOTP with RFC 6238 defaults: six digits and a 30-second step. Accept at most one adjacent time step in either direction for clock drift, and persist the last accepted time step so a code cannot be replayed, including by concurrent requests.
- Add a one-to-one per-user MFA credential record for status, encrypted active/pending TOTP seed, enrollment timestamps, and last accepted step. Add recovery-code records containing only one-way hashes and consumed state. Generate ten unique, high-entropy, single-use recovery codes per batch.
- Encrypt TOTP seeds with `cryptography.fernet.Fernet` using a dedicated `MFA_ENCRYPTION_KEY` in the server's local environment; do not reuse the JWT signing key. Add the dependency and configuration in the implementation. Keep the key out of the database and normal backup artifacts, and document secure local key escrow and restore requirements. If the key is unavailable or invalid, fail closed rather than accepting password-only login.
- Use Alembic for the schema changes and `UtcDateTime` for stored timestamps. New and existing users without an enrolled factor must enter enrollment before receiving a full session.

### Security and auditing

- Apply the existing configured login-attempt thresholds to MFA with separate per-user and per-IP limiter keys. Do not reset the MFA limiter when the password stage succeeds.
- Record `LOGIN_SUCCESS` only after complete MFA; record password and MFA failures as `LOGIN_FAILURE`. Add audited actions for MFA enrollment, recovery-code use, and code rotation. Extend the audit action catalog and its database constraint in the migration.
- Keep the existing atomic audited-state-change rule. Never place a TOTP code, seed, provisioning URI, or recovery code in logs, audit details, URLs, or error messages. Return generic MFA failures and `no-store` responses.
- Preserve the existing eight-hour revocable session behavior, current database-role authorization, HttpOnly cookie contract, and cookie-authenticated WebSocket behavior.

## Development exception and rollout

- Preserve `/api/dev/login-as` and `/api/dev/reseed` only as explicit demo tooling behind `DEV_TOOLS_ENABLED`. Mark sessions they mint as demo impersonation (for example, an `auth_method=demo_impersonation` session attribute), and clearly label them as outside normal MFA. Operational deployment configuration must keep `DEV_TOOLS_ENABLED=false` and must not use demo seed profiles or impersonation sessions.
- Apply the migration in development, revoke current local sessions with an explicit `mfa_rollout` reason, then require TOTP enrollment on every user's next login. Add that revocation reason to the existing `auth_session` constraint.
- Before any operational deployment, schedule a separate cutover with the CDRRMO. Do not introduce a production grace period or claim a live deployment rollout in this development plan.

## Acceptance and verification plan

The implementation is complete only when the following behavior is verified:

- A correct password without TOTP cannot access protected REST routes or `/ws/alerts`; a valid TOTP produces the normal session cookie and dashboard response.
- Existing and newly created accounts are forced through enrollment. Pending enrollment alone grants no application access.
- Invalid, expired, replayed, and over-limit TOTP attempts fail without creating a session, updating `last_login`, or writing `LOGIN_SUCCESS`. Two simultaneous submissions of one time step cannot both succeed.
- Recovery codes are shown only once, stored only as hashes, work once each, and force authenticator re-enrollment. Rotating the batch invalidates every earlier code. There is no MFA-disable or admin-reset route.
- Audit rows distinguish completed login, failed login, enrollment, recovery use, and rotation without containing secrets. Existing RBAC, logout, password-change revocation, account deactivation, and WebSocket closure behavior still works.
- The demo switch/reseed path is explicitly identifiable as impersonation, operates only when demo tooling is enabled, and is absent from operational deployment configuration.
- The migration and restore path work with the local encryption key present; missing or invalid key material fails closed.

**No tests are being run in this documentation-only task.** Run the narrow auth, session, migration, and frontend login/profile checks during the later implementation; follow `CLAUDE.md` for exact test and migration procedure.

## Implementation sequence

1. Add configuration and dependencies (`pyotp`, `cryptography`, and frontend QR rendering), then add the MFA schema and audit-catalog migration.
2. Implement the service-layer TOTP enrollment, verification, replay prevention, recovery-code, limiter, and audit rules.
3. Change login API responses and challenge-cookie handling; ensure normal authentication dependencies reject challenge tokens.
4. Add password-to-code and enrollment/QR screens; add recovery-code display and rotation in Profile Settings.
5. Constrain and mark the demo session-minting exception; enforce `DEV_TOOLS_ENABLED=false` for operational deployments.
6. Run targeted verification, update operational secret/restore documentation, then reconcile the defense paper and its test results.

## Source references

- Supplied paper: _REVISED_FINAL_PAPEL.pdf_, cited pages listed above.
- [RFC 6238: TOTP](https://www.rfc-editor.org/rfc/rfc6238.html)
- [PyOTP](https://github.com/pyauth/pyotp)
- [NIST SP 800-63B-4](https://pages.nist.gov/800-63-4/sp800-63b.html?locale=en)
- [OWASP Multifactor Authentication Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Multifactor_Authentication_Cheat_Sheet.html)
- [qrcode.react](https://github.com/zpao/qrcode.react)

## Starting-state note

The repository had unrelated modified and untracked files when this plan was written. Preserve those changes during later implementation; do not stage or overwrite them as part of this MFA work.
