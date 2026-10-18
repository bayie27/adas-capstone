---
section: Authentication, Security, Database, Deployment, and Validation
page/s: "Pending current live-PDF export and rendered-page mapping"
required_revision: Align the live paper with mandatory MFA behavior, restore/key handling, and bounded validation evidence.
notes: P5 proposal only; device/LAN/physical escrow checks remain not run.
status: Not started
assigned_to: Daniboy
synced: false
---

# P5 MFA operations and validation — active-flow paper proposals

## Analysis

**Implementation range:** P4 from the pre-cutover main commit `59b32a82ddf6556c763c375eba362e5ea4e27862` through branch head `598049a84e4fe20732a0feeec5b35658b469b783`, merged by PR #244 as `38a5c5d0d9d2a3abeae6df2470b52e76e1bf4ba8`. The merge tree is identical to the recorded P4 test tree `d39f0ba12d0d1dc7e855ecac522c3ad0b65587d4`. The P4 range activates the mandatory MFA router/login flow, removes the password-only session path, adds the rollout migration, gates demo sessions, and adds candidate-restore and emergency-rollback MFA invalidation.

**Current defense Doc:** `REVISED_FINAL_PAPEL`, native ID `1tCbJglHEobGee_KXKMWmghMLne0nroWNnbj2MDh8240`, main tab `t.y7ms6bhlk4qn`, revision `AHj4eMQav9NTp-JdnzxZPpnhaBQpO7QY5xTbQwF6Uydfi0KNP2-Y6Kabt2tzkZIwQnzDTqFaRl_nKPMgIhEn1__RLrTYxZ2OUvh6BdXOhFE`, read 2026-10-19. Native paragraph indexes identify the sites below. Google's PDF export returned HTTP 403. The supplied repository PDF is a 246-page pre-MFA snapshot and contains none of the current MFA text, so it is not used for current page numbers. All page references remain pending; this finding is a draft, not approval-ready for page-dependent work.

**Existing MFA findings and live tracker:** P1 finding `PS-20261018-MFA-FOUNDATION` and P3 finding `PS-20261018-MFA-FRONTEND` were read. The current Doc has 11 anchored comments with the P1 package ID on schema/dependency insertions; Tables 31–33 and MFA/AuthSession field descriptions are present. This is evidence that the P1 text was later applied, although its local ledger was not updated. The P1 Figure 7 redraw and live Sheet row remain unresolved; the current Figure 7 image cannot be verified without a current PDF. P3's `qrcode.react` proposal remains absent from the frontend-library paragraph and has no matching current Doc comment. Older findings are left untouched. One duplicate `mfa_recovery_code` paragraph is present at native starts 169008 and 169160; only one copy is needed.

The live `ADAS_Paper_Audit_Tracker` (`1iTt2K-t9Jyae-lqApCY0PX9N7HXCrKE850pvJLHzfoQ`, tab `🚩 Action Stream`) has no MFA row. `userEnteredValue` is absent in A89:H99; A89:H89 is the first blank row. Earlier local P1/P3 proposals name A89 and A90, so a future Sheet append must reconcile their order and re-read the first blank row before any write. No Doc, Sheet, or comment was written in this task.

**Ground truth:** `backend/app/services/mfa.py`, `backend/app/api/routes/mfa.py`, `backend/app/api/dependencies.py`, `backend/app/services/sessions.py`, `backend/app/models/user.py`, migration `8d4e7a2c9f10_mfa_mandatory_cutover.py`, `backend/app/maintenance/restore.py`, `backend/app/maintenance/cli.py`, `frontend/src/pages/auth/`, `frontend/src/pages/profile/MfaSettingsCard.tsx`, and `backend/content/help/*.md`. The prior P1–P4 assertions and their real test results are mapped in `docs/plans/mfa/02_PKG_foundation.md` through `05_PKG_cutover.md`; P5 results and unrun prerequisites are in `docs/validation/mfa-validation.md`.

## Changes

### 1. Defense paper — Functional Requirements, Table 3, FR-01 User Authentication

Page/s: Pending current live-PDF mapping; main tab description paragraph starting at native index 105931.

#### Change metadata

Operation: replace
Scope: span
Changed target: FR-01 description
Preserve: FR-02 and all surrounding requirement rows and formatting
Comment target: the exact changed FR-01 description

#### OLD

> The system shall require all users to securely log in using a valid username and password before accessing the web dashboard.

#### NEW

The system shall require every normal user session to complete a valid username/password check and a registered TOTP proof before the web dashboard is accessible. Accounts without a factor must complete authenticator enrollment and confirm a TOTP code before access; a recovery code starts recovery and does not itself grant a full session. Development-only demo impersonation is separately gated and visibly labeled.

#### Evidence

`backend/app/api/routes/auth.py` routes password submission through the MFA service; `backend/app/services/mfa.py` returns a restricted challenge until TOTP or enrollment confirmation; `backend/app/api/dependencies.py` rejects password-method full sessions. P4 E2E evidence is in `e2e/mfa.spec.ts` and the P4 completion record.

#### Proposed comment (same gate as replacement)

Comment scope: logical paragraph; replace the full FR-01 description.

Previous: The system shall require all users to securely log in using a valid username and password before accessing the web dashboard.

Codex ID: PS-20261019-MFA-VALIDATION-OPERATIONS

Done by Codex.

### 2. Defense paper — Functional Requirements, Table 3, FR-03 User Account Management

Page/s: Pending current live-PDF mapping; main tab paragraph following FR-03.

#### Change metadata

Operation: replace
Scope: logical paragraph
Changed target: FR-03 description
Preserve: existing account creation, role, profile, and password-management requirements
Comment target: the exact updated FR-03 paragraph

#### OLD

> The system shall provide account management appropriate to each access level. Administrators shall be able to create, edit, deactivate, and restore user accounts, assign roles, change user passwords, and search the list of users. Operators shall be able to update only their own account details and their own password.

#### NEW

The system shall provide account management appropriate to each access level. Administrators shall be able to create, edit, deactivate, and restore user accounts, assign roles, reset user passwords, and search the list of users. A password reset changes only the password and does not reset or bypass MFA. Operators shall be able to update only their own account details and their own password.

#### Evidence

P4 has no MFA-reset route. Password reset remains in `backend/app/api/routes/users.py`; all normal sessions still pass through `backend/app/api/dependencies.py`'s MFA method/version check. The new Operator/Admin help explicitly distinguishes password reset from MFA recovery.

#### Proposed comment (same gate as replacement)

Comment scope: logical paragraph; replace the full FR-03 description.

Previous (marked, intentionally non-verbatim): The system shall provide account management appropriate to each access level. Administrators shall be able to [[change user passwords]]. Operators shall be able to update only their own account details and their own password.

Codex ID: PS-20261019-MFA-VALIDATION-OPERATIONS

Done by Codex.

### 3. Defense paper — Functional Requirements, Table 3, FR-19 Help Center

Page/s: Pending current live-PDF mapping; main tab description paragraph starting at native index 111942.

#### Change metadata

Operation: replace
Scope: logical paragraph
Changed target: FR-19 description
Preserve: searchable help, access-level filtering, SOPs, and existing FAQs
Comment target: the exact updated FR-19 paragraph

#### OLD

> The system shall provide a centralized, searchable Help Center to support user onboarding and routine system navigation. This module must include comprehensive digital documentation tailored to each user's access level, including standard operating procedures (SOPs) for incident handling, general dashboard navigation guides, and frequently asked questions (FAQs).

#### NEW

The system shall provide a centralized, searchable Help Center to support user onboarding and routine system navigation. This module must include comprehensive digital documentation tailored to each user's access level, including standard operating procedures (SOPs) for incident handling, general dashboard navigation guides, authenticator enrollment and recovery guidance, and frequently asked questions (FAQs).

#### Evidence

The new role-visible article is `backend/content/help/managing-your-authenticator-and-recovery.md`. It covers setup, one-time code handling, code storage, replacement, recovery interruption, and the absence of an in-app or Administrator MFA reset. `backend/tests/test_help.py::TestRoleFilter::test_mfa_guidance_is_operator_visible_and_covers_recovery_boundaries` asserts the content and Operator visibility.

#### Proposed comment (same gate as replacement)

Comment scope: logical paragraph; replace the full FR-19 description.

Previous: The system shall provide a centralized, searchable Help Center to support user onboarding and routine system navigation. This module must include comprehensive digital documentation tailored to each user's access level, including standard operating procedures (SOPs) for incident handling, general dashboard navigation guides, and frequently asked questions (FAQs).

Codex ID: PS-20261019-MFA-VALIDATION-OPERATIONS

Done by Codex.

### 4. Defense paper — Security Requirements, Table 7, NFR-19 Session Security

Page/s: Pending current live-PDF mapping; main tab paragraph starting at native index 118736.

#### Change metadata

Operation: replace
Scope: logical paragraph
Changed target: NFR-19 description
Preserve: the existing eight-hour upper bound
Comment target: the exact updated NFR-19 paragraph

#### OLD

> A user's login session shall last no longer than 8 hours and shall be protected so that it cannot be read or reused by anything other than the user's own browser session. The system shall be able to end a session immediately when the user logs out, when their password is changed, or when an Administrator revokes their access.

#### NEW

A user's authenticated session shall last no longer than 8 hours and shall use an HttpOnly, Secure cookie backed by a server-side session record. Each request shall revalidate the current account role and, for TOTP sessions, the active MFA credential version; demo impersonation shall require enabled demo tooling. Logout, password or account-state changes, role changes, recovery, factor replacement, rollout, and restore shall invalidate affected sessions immediately. A restored snapshot shall not revive its prior sessions.

#### Evidence

`backend/app/services/sessions.py::create_session` sets expiry at session creation and requires an explicit authentication method. `backend/app/api/dependencies.py::authenticate_session_token` rechecks the user, role, TOTP credential state/version, and demo flag. P4 migration and restore assertions cover rollout/restore invalidation.

#### Proposed comment (same gate as replacement)

Comment scope: logical paragraph; replace the full NFR-19 paragraph.

Previous (marked, intentionally non-verbatim): A user's login session shall last no longer than [[8 hours]] and shall be protected so that it cannot be read or reused by anything other than the user's own browser session. The system shall be able to end a session immediately when the user logs out, when their password is changed, or when an Administrator revokes their access.

Codex ID: PS-20261019-MFA-VALIDATION-OPERATIONS

Done by Codex.

### 5. Defense paper — Security Requirements, Table 7, NFR-20 Data Localization

Page/s: Pending current live-PDF mapping; main tab paragraph starting at native index 119092.

#### Change metadata

Operation: replace
Scope: logical paragraph
Changed target: NFR-20 description
Preserve: server-side storage and processing localization requirement
Comment target: the exact updated NFR-20 paragraph

#### OLD

> To ensure data privacy and compliance with government security standards, all data shall be stored and processed exclusively on the edge server's physical drives and shall not be transmitted to external cloud services.

#### NEW

To ensure data privacy and compliance with government security standards, application data shall be stored and processed on the edge server's physical drives and shall not be transmitted to external cloud services. During TOTP enrollment, the setup secret is displayed locally for entry into the user's authenticator app; that app keeps its own device copy while ADAS retains an encrypted server-side copy. Authenticator-device storage is outside this server-side localization requirement. ADAS cannot inspect or enforce an authenticator provider's cloud-sync setting; disabling sync is user and operational policy.

#### Evidence

The backend provisions the secret through the MFA enrollment response; `frontend/src/pages/auth/MfaEnrollmentPanel.tsx` renders its QR locally and displays the manual key. `backend/app/core/mfa.py` encrypts the stored seed with Fernet. No external identity or QR service is used. The application cannot inspect the user's authenticator app or its sync configuration.

#### Proposed comment (same gate as replacement)

Comment scope: logical paragraph; replace the full NFR-20 paragraph.

Previous: To ensure data privacy and compliance with government security standards, all data shall be stored and processed exclusively on the edge server's physical drives and shall not be transmitted to external cloud services.

Codex ID: PS-20261019-MFA-VALIDATION-OPERATIONS

Done by Codex.

### 6. Defense paper — Security Requirements, Table 7, NFR-21 Audit Trail Integrity

Page/s: Pending current live-PDF mapping; main tab paragraph starting at native index 119343.

#### Change metadata

Operation: replace
Scope: logical paragraph
Changed target: NFR-21 description
Preserve: append-only audit history and failure recording
Comment target: the exact updated NFR-21 paragraph

#### OLD

> Every action that changes system data shall be recorded at the same time as the change itself, so that no action can go unrecorded. Failed or unauthorized attempts shall also be recorded, with sensitive values hidden. No user, including an Administrator, shall be able to edit or delete these records.

#### NEW

Every successful audited state change and its audit entry shall commit in the same transaction. Failed or unauthorized attempts, including failed MFA proofs, shall be recorded after the attempted action rolls back. Passwords, authenticator and recovery codes, seeds, ciphertext, provisioning URIs, challenge tokens, and encryption keys shall be excluded or redacted from audit details. Audit history shall remain append-only, and database update or delete attempts shall be refused.

#### Evidence

`backend/app/services/audit.py` couples audit inserts to the caller transaction, records denials after rollback, and bans MFA secret keys in details. `backend/app/models/audit.py` and the migrations install append-only triggers. P2 audit-failure rollback tests and P4 cutover/restore tests assert the transaction boundaries.

#### Proposed comment (same gate as replacement)

Comment scope: logical paragraph; replace the full NFR-21 paragraph.

Previous (marked, intentionally non-verbatim): Every action that changes system data shall be recorded [[at the same time as the change itself]]. Failed or unauthorized attempts shall also be recorded, with [[sensitive values hidden]]. No user, including an Administrator, shall be able to edit or delete these records.

Codex ID: PS-20261019-MFA-VALIDATION-OPERATIONS

Done by Codex.

### 7. Defense paper — Use Case: Log In, Main Flow, step 2

Page/s: Pending current live-PDF mapping; main tab paragraph starting at native index 120418.

#### Change metadata

Operation: replace
Scope: span
Changed target: Main Flow step 2
Preserve: step number and surrounding use-case structure
Comment target: the changed step 2 text

#### OLD

> The user enters their valid username and password.

#### NEW

The user enters a valid username and password.

#### Evidence

Password submission starts a restricted P2/P4 challenge; it is not a completed session. `backend/app/services/mfa.py::begin_password_login` and the active auth route implement this stage.

#### Proposed comment (same gate as replacement)

Comment scope: span; OLD `The user enters their valid username and password.`; NEW `The user enters a valid username and password.`

Previous: The user enters their valid username and password.

Codex ID: PS-20261019-MFA-VALIDATION-OPERATIONS

Done by Codex.

### 8. Defense paper — Use Case: Log In, Main Flow, step 3

Page/s: Pending current live-PDF mapping; main tab paragraph starting at native index 120469.

#### Change metadata

Operation: replace
Scope: span
Changed target: Main Flow step 3
Preserve: step number and surrounding use-case structure
Comment target: the changed step 3 text

#### OLD

> The system validates the credentials against the local database.

#### NEW

The system validates the credentials and returns only a restricted enrollment or MFA challenge; this response does not create a normal session.

#### Evidence

P4's password adapter returns the challenge state, and `backend/app/api/dependencies.py` rejects incomplete/password-only sessions.

#### Proposed comment (same gate as replacement)

Comment scope: span; OLD `The system validates the credentials against the local database.`; NEW `The system validates the credentials and returns only a restricted enrollment or MFA challenge; this response does not create a normal session.`

Previous: The system validates the credentials against the local database.

Codex ID: PS-20261019-MFA-VALIDATION-OPERATIONS

Done by Codex.

### 9. Defense paper — Use Case: Log In, Main Flow, step 4

Page/s: Pending current live-PDF mapping; main tab paragraph starting at native index 120534.

#### Change metadata

Operation: replace
Scope: span
Changed target: Main Flow step 4
Preserve: step number and surrounding use-case structure
Comment target: the changed step 4 text

#### OLD

> The system determines the assigned role (Operator or Administrator).

#### NEW

The system checks the account's MFA state and requests a current TOTP proof, or requires authenticator enrollment and confirmation when no factor exists.

#### Evidence

Enrollment and login challenges have distinct purposes; confirmation of a new seed is required before the first normal session. See `backend/app/services/mfa.py` and `backend/tests/test_mfa_service.py`.

#### Proposed comment (same gate as replacement)

Comment scope: span; OLD `The system determines the assigned role (Operator or Administrator).`; NEW `The system checks the account's MFA state and requests a current TOTP proof, or requires authenticator enrollment and confirmation when no factor exists.`

Previous: The system determines the assigned role (Operator or Administrator).

Codex ID: PS-20261019-MFA-VALIDATION-OPERATIONS

Done by Codex.

### 10. Defense paper — Use Case: Log In, Main Flow, step 5

Page/s: Pending current live-PDF mapping; main tab paragraph starting at native index 120603.

#### Change metadata

Operation: replace
Scope: span
Changed target: Main Flow step 5
Preserve: role-based dashboard destination
Comment target: the changed step 5 text

#### OLD

> The system logs the user in and loads the web app restricted to their clearance level.

#### NEW

After a valid TOTP proof, the system creates a server-backed session, determines the current role, and loads the web app with the permitted access level.

#### Evidence

`create_session` requires an explicit method; normal TOTP sessions bind to the current credential version. Demo impersonation remains a separate flag-gated path.

#### Proposed comment (same gate as replacement)

Comment scope: span; OLD `The system logs the user in and loads the web app restricted to their clearance level.`; NEW `After a valid TOTP proof, the system creates a server-backed session, determines the current role, and loads the web app with the permitted access level.`

Previous: The system logs the user in and loads the web app restricted to their clearance level.

Codex ID: PS-20261019-MFA-VALIDATION-OPERATIONS

Done by Codex.

### 11. Defense paper — Use Case: Log In, Alternative Flows

Page/s: Pending current live-PDF mapping; insert after the current deactivated-account alternative flow.

#### Change metadata

Operation: insert
Scope: logical paragraph
Changed target: additional MFA proof, recovery, and interrupted-recovery alternatives
Preserve: existing missing-input, generic invalid-password, and inactive-account alternatives
Comment target: the exact inserted alternatives

#### OLD

> N/A

#### NEW

4a. Invalid, expired, or already used TOTP: Keep the user unauthenticated, show a generic inline failure, and retain the server-driven retry limit.

4b. Recovery code accepted: Consume that one code, disable the old authenticator, and revoke all sessions. Require enrollment and confirmation of a new TOTP before creating a normal session.

4c. Recovery interrupted: Require another unused code to restart. If the final code was consumed and the enrollment challenge is lost or expires, no in-app or Administrator MFA reset is available.

#### Evidence

`backend/tests/test_mfa_service.py` asserts recovery consumption/revocation, interrupted recovery, and final-code exhaustion. The current user article covers these consequences.

#### Proposed comment (same gate as replacement)

Comment scope: logical paragraph; highlight the inserted MFA alternative-flow group.

Previous: N/A

Codex ID: PS-20261019-MFA-VALIDATION-OPERATIONS

Done by Codex.

### 12. Defense paper — Use Case: Log In, Postconditions

Page/s: Pending current live-PDF mapping; main tab paragraph starting at native index 121515.

#### Change metadata

Operation: replace
Scope: span
Changed target: first postcondition
Preserve: role access postcondition
Comment target: the changed first postcondition

#### OLD

> A secure, persistent, timed session is established.

#### NEW

A secure, timed normal session is established only after a valid TOTP proof or confirmed enrollment.

#### Evidence

The password stage returns only a challenge; session creation occurs in successful TOTP/enrollment service transactions.

#### Proposed comment (same gate as replacement)

Comment scope: span; OLD `A secure, persistent, timed session is established.`; NEW `A secure, timed normal session is established only after a valid TOTP proof or confirmed enrollment.`

Previous: A secure, persistent, timed session is established.

Codex ID: PS-20261019-MFA-VALIDATION-OPERATIONS

Done by Codex.

### 13. Defense paper — Use Case Diagram narrative, Secure Access and Session Management

Page/s: Pending current live-PDF mapping; main tab paragraph starting at native index 159344.

#### Change metadata

Operation: replace
Scope: logical paragraph
Changed target: login, session, and factor-management narrative
Preserve: existing profile/password and logout actions
Comment target: the updated logical paragraph

#### OLD

> Secure Access and Session Management. The operational workflow begins with the Log In use case. Upon login, the system validates the user's credentials and determines the appropriate user role before granting access. If authentication fails, the system displays a login error. Once authenticated, users may Edit User Profile and Change Own Password according to their permissions. The Log Out use case terminates the active session through Revoke Session, ensuring that authenticated access is properly closed when the user leaves the system. This provides controlled session management while maintaining the security of the command center.

#### NEW

Secure Access and Session Management. The Log In use case validates a username and password, then requires a registered TOTP proof or completed authenticator enrollment before creating a normal session. A recovery code starts recovery and requires a new TOTP-confirmed enrollment; it does not grant dashboard access. Users may edit their profile, change their password, replace an authenticator, or rotate recovery codes according to their permissions. The Log Out use case revokes the active session and closes its authenticated access.

#### Evidence

The live paragraph currently describes password validation and role selection before access. The active Login flow and Profile MFA settings card implement the TOTP, recovery, replacement, rotation, and session-revocation behavior.

#### Proposed comment (same gate as replacement)

Comment scope: logical paragraph; replace the full Secure Access and Session Management paragraph.

Previous (marked, intentionally non-verbatim): Secure Access and Session Management. The operational workflow begins with the Log In use case. Upon login, the system [[validates the user's credentials and determines the appropriate user role before granting access]]. If authentication fails, the system displays a login error. Once authenticated, users may Edit User Profile and Change Own Password according to their permissions. The Log Out use case terminates the active session through Revoke Session, ensuring that authenticated access is properly closed when the user leaves the system. This provides controlled session management while maintaining the security of the command center.

Codex ID: PS-20261019-MFA-VALIDATION-OPERATIONS

Done by Codex.

## Redraw required

### 14. Defense paper — Figure 4, Use Case Diagram

Page/s: Pending current live-PDF export and visual mapping.

#### Change metadata

Operation: redraw
Scope: figure
Changed target: the Operator/Administrator authentication relationships and MFA-related use cases
Preserve: incident, camera, report, role, and Help Center use cases not affected by MFA
Comment target: no standalone comment proposed

#### Current issue

The adjacent live narrative describes Log In as password validation followed by role selection; it does not describe the active second-factor or enrollment flow. The current diagram image could not be independently inspected because live PDF export returned 403.

#### Required redraw

Add the password challenge, TOTP verification, enrollment with TOTP confirmation, recovery-code entry leading to recovery enrollment, and Profile replacement/rotation actions. Make clear that a recovery code alone does not create a normal session and that development-only impersonation is not normal user authentication. Re-inspect the live image before approval; do not infer current figure contents from the supplied pre-MFA PDF.

### 15. Defense paper — Figure 8, Login Page

Page/s: Pending current live-PDF export and visual mapping; adjacent description begins at native index 193305.

#### Change metadata

Operation: redraw
Scope: figure
Changed target: login and authenticator setup/challenge UI
Preserve: ADAS identity, username/password entry, accessibility, and role-specific destinations
Comment target: no standalone comment proposed

#### Current issue

The current live description names only username, password, and Login controls. The image is not available for current visual inspection because PDF export returned 403.

#### Required redraw

Show the password stage followed by TOTP/recovery choice and the enrollment screen with local QR/manual setup and TOTP confirmation. If the one-time recovery-code screen is included, use masked disposable values and show its explicit acknowledgment. Never place a real setup key or recovery code in the paper figure.

## Changes (continued)

### 16. Defense paper — Figure 8 description, Login Page

Page/s: Pending current live-PDF mapping; main tab paragraph starting at native index 193305.

#### Change metadata

Operation: replace
Scope: logical paragraph
Changed target: Figure 8 description
Preserve: system title, username/password entry, and role-specific dashboard destination
Comment target: the exact updated description

#### OLD

> Figure 8 presents the centralized authentication form that serves as the primary entry point for all users. The interface displays the ADAS logo and full system title alongside a "Username" text field, a "Password" text field with a visibility toggle icon, and a "Login" button. The page enforces role-based access by requiring valid credentials before granting entry to the designated dashboard based on user role (directing administrators to the system administration console and operators to the active monitoring console).

#### NEW

Figure 8 presents the centralized authentication flow that serves as the primary entry point for all users. The flow begins with the ADAS login form and continues to a TOTP challenge or authenticator enrollment with local QR/manual setup and TOTP confirmation. Recovery-code entry begins recovery enrollment rather than granting a normal session. Any recovery-code example in the figure is masked and disposable.

#### Evidence

`frontend/src/pages/Login.tsx`, `frontend/src/pages/auth/MfaLoginFlow.tsx`, `MfaChallengePanel.tsx`, and `MfaEnrollmentPanel.tsx` implement the active flow. Recovery-code handling is in `RecoveryCodesPanel.tsx` and the sensitive-flow provider.

#### Proposed comment (same gate as replacement)

Comment scope: logical paragraph; replace the full Figure 8 description.

Previous: Figure 8 presents the centralized authentication form that serves as the primary entry point for all users. The interface displays the ADAS logo and full system title alongside a "Username" text field, a "Password" text field with a visibility toggle icon, and a "Login" button. The page enforces role-based access by requiring valid credentials before granting entry to the designated dashboard based on user role (directing administrators to the system administration console and operators to the active monitoring console).

Codex ID: PS-20261019-MFA-VALIDATION-OPERATIONS

Done by Codex.

### 17. Defense paper — Data model narrative, Security and Identity Management

Page/s: Pending current live-PDF mapping; main tab paragraph starting at native index 166761.

#### Change metadata

Operation: replace
Scope: span
Changed target: `staged MFA Foundation Storage`
Preserve: the entity count and all other domain names
Comment target: the exact changed span

#### OLD

> staged MFA Foundation Storage

#### NEW

MFA authentication and recovery storage

#### Evidence

P4 activates mandatory MFA on the main application and migrates/revokes legacy sessions. This is no longer staged storage unused by login.

#### Proposed comment (same gate as replacement)

Comment scope: span; OLD `staged MFA Foundation Storage`; NEW `MFA authentication and recovery storage`

Previous: staged MFA Foundation Storage

Codex ID: PS-20261019-MFA-VALIDATION-OPERATIONS

Done by Codex.

### 18. Defense paper — Data model narrative, `mfa_credential`

Page/s: Pending current live-PDF mapping; main tab paragraph starting at native index 168549.

#### Change metadata

Operation: replace
Scope: logical paragraph
Changed target: `mfa_credential` relationship description
Preserve: its strict one-to-one relationship and stored fields
Comment target: the exact updated relationship paragraph

#### OLD

> mfa_credential (Strict 1-to-1). Stores each user’s staged MFA state, credential version, encrypted active seed when enrolled, and recovery timestamps. This record is not used by the password-only login before cutover.

#### NEW

mfa_credential (Strict 1-to-1). Stores each user’s active MFA state, credential version, encrypted active TOTP seed when enrolled, replay step, and recovery timestamps. Normal user sessions require a valid TOTP proof bound to this credential version.

#### Evidence

`backend/app/models/mfa.py`, `backend/app/services/mfa.py`, and `backend/app/api/dependencies.py` define the active credential and version-bound session check. The current live Doc still says the record is staged and unused by password-only login.

#### Proposed comment (same gate as replacement)

Comment scope: logical paragraph; replace the full `mfa_credential` relationship paragraph.

Previous: mfa_credential (Strict 1-to-1). Stores each user’s staged MFA state, credential version, encrypted active seed when enrolled, and recovery timestamps. This record is not used by the password-only login before cutover.

Codex ID: PS-20261019-MFA-VALIDATION-OPERATIONS

Done by Codex.

### 19. Defense paper — Data model narrative, `mfa_challenge`

Page/s: Pending current live-PDF mapping; main tab paragraph starting at native index 168767.

#### Change metadata

Operation: replace
Scope: logical paragraph
Changed target: `mfa_challenge` relationship description
Preserve: one-challenge limit, token digest, purpose, credential snapshot, pending ciphertext, and UTC expiry
Comment target: the exact updated relationship paragraph

#### OLD

> mfa_challenge (Strict 1-to-1). Stores at most one staged MFA challenge per user, including its token digest, purpose, credential snapshot, optional encrypted pending seed, and UTC expiry. Challenges do not authenticate users before cutover.

#### NEW

mfa_challenge (Strict 1-to-1). Stores at most one active MFA challenge per user, including its token digest, purpose, credential snapshot, optional encrypted pending seed, and UTC expiry. A challenge is temporary and does not grant dashboard access without the required proof.

#### Evidence

`backend/app/services/mfa.py` validates challenge purpose/expiry and creates a normal session only after the required TOTP proof or confirmed enrollment. The current live paragraph still describes a staged pre-cutover challenge.

#### Proposed comment (same gate as replacement)

Comment scope: logical paragraph; replace the full `mfa_challenge` relationship paragraph.

Previous: mfa_challenge (Strict 1-to-1). Stores at most one staged MFA challenge per user, including its token digest, purpose, credential snapshot, optional encrypted pending seed, and UTC expiry. Challenges do not authenticate users before cutover.

Codex ID: PS-20261019-MFA-VALIDATION-OPERATIONS

Done by Codex.

### 20. Defense paper — Data model narrative, duplicate `mfa_recovery_code` paragraph

Page/s: Pending current live-PDF mapping; duplicate starts at native index 169160, immediately after the same paragraph at 169008.

#### Change metadata

Operation: delete
Scope: logical paragraph
Changed target: the second consecutive copy of the `mfa_recovery_code` relationship paragraph
Preserve: the first identical paragraph and all other ERD narrative
Comment target: the nearest surviving left character, the terminator of the first copy

#### OLD

> mfa_recovery_code (1-to-Many). Stores generation-scoped recovery-code digests and consumption timestamps for each user; plaintext codes are not stored.

#### NEW

DELETE ONLY — insert nothing.

#### Evidence

The current native text read has the exact same paragraph twice at consecutive native ranges 169008 and 169160. The first copy already has a P1 package comment; no second relationship is required.

#### Proposed comment (same gate as replacement)

Comment scope: span; deletion of the second identical paragraph, with the comment anchored to the first copy's terminating character.

Previous: mfa_recovery_code (1-to-Many). Stores generation-scoped recovery-code digests and consumption timestamps for each user; plaintext codes are not stored.

Codex ID: PS-20261019-MFA-VALIDATION-OPERATIONS

Done by Codex.

### 21. Defense paper — Table 15, Auth Session `auth_method` constraints

Page/s: Pending current live-PDF mapping; main tab constraint paragraph starting at native index 185173.

#### Change metadata

Operation: replace
Scope: span
Changed target: `auth_method` constraints cell
Preserve: the `auth_method` name, type, and surrounding Auth Session rows
Comment target: the exact updated constraints text

#### OLD

> Not Null, Default: password; values: password, totp, demo_impersonation

#### NEW

Not Null, no default after cutover; values: password (legacy history only and rejected as a full session), totp (bound to an enrolled credential version), demo_impersonation (flag-gated development session)

#### Evidence

P4 migration `8d4e7a2c9f10_mfa_mandatory_cutover.py` removes the server default and revokes all old sessions. `backend/app/models/user.py` has no model default; `create_session` requires an explicit method; dependencies reject `password` after cutover.

#### Proposed comment (same gate as replacement)

Comment scope: span; OLD `Not Null, Default: password; values: password, totp, demo_impersonation`; NEW `Not Null, no default after cutover; values: password (legacy history only and rejected as a full session), totp (bound to an enrolled credential version), demo_impersonation (flag-gated development session)`

Previous: Not Null, Default: password; values: password, totp, demo_impersonation

Codex ID: PS-20261019-MFA-VALIDATION-OPERATIONS

Done by Codex.

### 22. Defense paper — System Maintenance and Database Restoration Architecture

Page/s: Pending current live-PDF mapping; insert after the current Integrity Verification & Automated Rollback paragraph.

#### Change metadata

Operation: insert
Scope: logical paragraph
Changed target: MFA candidate preflight, session/challenge invalidation, key escrow, and snapshot semantics
Preserve: existing restore lease, emergency snapshot, service stop/restart, and rollback description
Comment target: the exact inserted paragraph

#### OLD

> N/A

#### NEW

Before replacement, restore accepts only a snapshot at the current MFA-enabled migration head and verifies that the stable deployment key decrypts every stored seed. It transforms a temporary candidate copy, invalidates all sessions and pending challenges with an audit event, then verifies the transformed candidate; emergency rollback applies the same invalidation policy. The selected backup remains unchanged. Restoring a snapshot can restore an older authenticator or unused recovery-code state, so users must authenticate again and operators must review restored factors before operational acceptance. The stable key is escrowed separately from ordinary backup artifacts.

#### Evidence

`backend/app/maintenance/restore.py::_verify_manifest_artifact`, `_validate_and_invalidate_mfa_candidate`, `perform_offline_restore`, and `perform_rollback`; `backend/app/maintenance/cli.py::_restore_mfa_config`; P5 `test_mfa_restore.py` and safe drill record `P5-1L-RESTORE-ESCROW-01`. This finding does not claim physical escrow or a replacement-host drill.

#### Proposed comment (same gate as replacement)

Comment scope: logical paragraph; highlight the inserted MFA restore paragraph.

Previous: N/A

Codex ID: PS-20261019-MFA-VALIDATION-OPERATIONS

Done by Codex.

### 23. Defense paper — Security Architecture, Authentication and Authorization

Page/s: Pending current live-PDF mapping; main tab paragraph starting at native index 210813.

#### Change metadata

Operation: replace
Scope: span
Changed target: the first two sentences describing human authentication
Preserve: the HttpOnly/SameSite cookie, eight-hour cap, session-row, role, Origin, and WebSocket statements after the changed span
Comment target: the exact changed authentication span

#### OLD

> Authentication and authorization. Human users sign in with a username and password. Passwords are stored as Argon2id hashes.

#### NEW

Authentication and authorization. Human users sign in with a username and password, then complete a registered TOTP proof before normal access; accounts without a factor must enroll and confirm a new TOTP first. Recovery-code use starts recovery rather than creating a normal session. Passwords are stored as Argon2id hashes.

#### Evidence

The active login/challenge/enrollment path is in `backend/app/api/routes/auth.py` and `backend/app/api/routes/mfa.py`; service state transitions are in `backend/app/services/mfa.py`. The current security paragraph still describes password-only authentication.

#### Proposed comment (same gate as replacement)

Comment scope: span; OLD `Human users sign in with a username and password. Passwords are stored as Argon2id hashes.`; NEW `Human users sign in with a username and password, then complete a registered TOTP proof before normal access; accounts without a factor must enroll and confirm a new TOTP first. Recovery-code use starts recovery rather than creating a normal session. Passwords are stored as Argon2id hashes.`

Previous: Human users sign in with a username and password. Passwords are stored as Argon2id hashes.

Codex ID: PS-20261019-MFA-VALIDATION-OPERATIONS

Done by Codex.

### 24. Defense paper — Frameworks and Libraries, Backend Layer

Page/s: Pending current live-PDF mapping; main tab paragraph starting at native index 223683.

#### Change metadata

Operation: replace
Scope: span
Changed target: the staged-MFA/password-only dependency sentence
Preserve: surrounding FastAPI/Uvicorn, password hashing, scheduler, maintenance, and telemetry claims
Comment target: the exact changed sentence

#### OLD

> The backend also declares PyOTP and cryptography for the staged MFA foundation’s TOTP primitives and Fernet seed encryption; the existing password-only login remains active until cutover.

#### NEW

The backend declares PyOTP for the active TOTP challenge, enrollment, recovery, replacement, and rotation flows, and cryptography for Fernet encryption of server-side TOTP seeds.

#### Evidence

`pyproject.toml`, `backend/app/services/mfa.py`, and `backend/app/core/mfa.py`; P4 activates the router and password adapter. The current live paragraph still says MFA is staged and password-only login remains active.

#### Proposed comment (same gate as replacement)

Comment scope: span; OLD `The backend also declares PyOTP and cryptography for the staged MFA foundation’s TOTP primitives and Fernet seed encryption; the existing password-only login remains active until cutover.`; NEW `The backend declares PyOTP for the active TOTP challenge, enrollment, recovery, replacement, and rotation flows, and cryptography for Fernet encryption of server-side TOTP seeds.`

Previous: The backend also declares PyOTP and cryptography for the staged MFA foundation’s TOTP primitives and Fernet seed encryption; the existing password-only login remains active until cutover.

Codex ID: PS-20261019-MFA-VALIDATION-OPERATIONS

Done by Codex.

### 25. Defense paper — Frameworks and Libraries, Frontend Layer

Page/s: Pending current live-PDF mapping; main tab paragraph starting at native index 226835.

#### Change metadata

Operation: insert
Scope: logical paragraph
Changed target: local MFA QR-rendering dependency
Preserve: existing React/Vite/React Router/Zustand/TanStack Query/Recharts/Tailwind/Remix Icon sentence
Comment target: the inserted sentence

#### OLD

> N/A

#### NEW

The frontend uses qrcode.react to render authenticator setup QR codes locally during enrollment; the provisioning URI is not sent to an external QR service.

#### Evidence

`frontend/package.json` declares `qrcode.react`; `frontend/src/pages/auth/MfaEnrollmentPanel.tsx` uses `QRCodeSVG`. The current live paragraph omits this dependency, and the older P3 proposal still describes the component as inactive.

#### Proposed comment (same gate as replacement)

Comment scope: span; highlight only the inserted qrcode.react sentence.

Previous: N/A

Codex ID: PS-20261019-MFA-VALIDATION-OPERATIONS

Done by Codex.

### 26. Defense paper — Reliability, Recovery, and Security Results

Page/s: Pending current live-PDF mapping; insert after the MFA-relevant security-results paragraph and before Table 29.

#### Change metadata

Operation: insert
Scope: logical paragraph
Changed target: separate repository-level MFA implementation validation and its limits
Preserve: the August 27–31 evaluation results and the existing 27/27 Security Testing count
Comment target: the inserted paragraph

#### OLD

> N/A

#### NEW

Separately, repository validation of the mandatory-MFA implementation used disposable accounts and databases on one Windows laptop. Automated tests and isolated restore/rollback exercises verified password-plus-TOTP enrollment/login behavior, recovery/replacement/rotation rules, demo gating, current-head restore invalidation, candidate rejection, key exclusion from backup artifacts, and emergency rollback. The local database restore function took 130.31 ms and rollback took 95.46 ms. After rollback, a fresh loopback backend process reached readiness in 4.279 seconds and rejected a pre-restore signed session cookie with 401 AUTH_REVOKED. A separate full-stack drill restored a disposable snapshot, restarted the backend, frontend, local MediaMTX simulator, and AI engine, then observed backend readiness in 0.032 seconds and a fresh AI heartbeat in 1.579 seconds. The offline CLI restore was explicitly finalized after that heartbeat; total time from the restore command to completed status was 13.193 seconds, within the existing 60-second readiness-and-heartbeat target for that one local run. This did not exercise the supervised Maintenance UI's coordinator finalization. Windows denied the default RTSP port 8554, so a temporary untracked MediaMTX config used loopback port 18554; the repository config was unchanged. No physical authenticator, authenticator cloud-sync setting, second-client LAN/TLS session, or independent offline key escrow was tested. These checks are separate from the August 27–31 security cases and do not establish physical-device, production, or deployment acceptance.

#### Evidence

P4 full gate on the exact merged code tree; P5 `pnpm full:check` passed on implementation commit `8d4ccfda5ba332f8ec6ec5e54752ebefd6e6c1ef` (backend 1,377 passed/5 skipped; frontend 395 across 62 files; build passed; Chromium E2E 6/6). P5 scoped help/restore selectors and safe records `P5-1L-RESTORE-ESCROW-01`, `P5-1L-POST-ROLLBACK-AUTH-01`, and `P5-1L-FULLSTACK-RESTORE-HEARTBEAT` (safe record `var/test-evidence/mfa-p5-full-stack-04432d05.json`). Physical phone, cloud-sync setting, second-client LAN/TLS, and independent offline escrow remain not run. The live current PDF page mapping remains pending.

#### Proposed comment (same gate as replacement)

Comment scope: logical paragraph; highlight the inserted supplemental MFA validation paragraph.

Previous: N/A

Codex ID: PS-20261019-MFA-VALIDATION-OPERATIONS

Done by Codex.

### 27. Tracker Sheet — 🚩 Action Stream!A89:H89 (candidate; unresolved local ordering)

#### Change metadata

Operation: insert
Scope: row
Changed target: first fully blank row in `🚩 Action Stream`; current range A89:H89
Preserve: all occupied rows and the `Reviewed by` column; do not overwrite the older P1/P3 proposed rows
Comment target: the exact new A:G text colored orange (`#E67E22`); no Sheet comment

#### OLD

> A89:H89 has no `userEnteredValue`. The live sheet has no MFA row; rows 89–99 are empty. Existing unapproved local P1/P3 findings separately proposed A89 and A90.

#### NEW

- A Change Type: Major
- B Section / Chapter: Authentication, Security Requirements, Data Dictionary, Frameworks, Deployment, and Testing & Validation
- C Page Number: Pending current live-PDF mapping
- D Required Revision: Align the paper with active mandatory MFA, audited factor/recovery flows, session invalidation, authenticator-device localization exception, stable-key restore, and the separately qualified validation results.
- E Notes: Keep physical authenticator/storage and cloud-sync observation, second-client LAN/TLS, and independent offline escrow as not run until observed. Record the one-laptop simulated restore/readiness result separately; it is not production evidence.
- F Status: Not started
- G Assigned to: Daniboy
- H Reviewed by: leave blank

#### Evidence

Read 2026-10-19 with `google_drive_get_spreadsheet_cells` on A89:H99, `userEnteredValue` only. Sheet metadata: 99 rows, 8 columns; all returned data for the requested tail was empty. A89:H89 is the live first blank row, but older local P1/P3 proposals reserve the same append order. Any eventual write must first reconcile the unapproved local proposals and re-read the first blank row.

#### Formatting fallback (same gate as replacement)

Color only the new text in A89:G89 orange (`#E67E22`); keep H89 blank and preserve existing cell formatting, validation, and manual fields. This candidate remains blocked pending the row-order reconciliation and current PDF page mapping.

## Carry-forward finding status

- P1's 11 textual comments are present on current inserted schema/dependency text; do not duplicate them. The old P1 Figure 7 redraw and tracker proposal remain unresolved and are not marked complete because the current image/PDF could not be checked.
- P3's `qrcode.react` text remains absent from the current frontend paragraph; the active dependency and flow are proposed in block 25.
- The duplicate `mfa_recovery_code` narrative is a newly verified live-doc defect and is proposed for deletion in block 20.
- No live Drive artifact or comment was changed. Every Doc block and the Sheet row remain pending under separate approval gates.

## Approval / sync ledger

Package ID: PS-20261019-MFA-VALIDATION-OPERATIONS
Approval source: The P5 instruction authorizes local proposals and explicitly prohibits Drive writes/comments; no Drive write is approved.

| Target              | Approved scope | Applied/read back | Skipped/pending | Blocked                                                                             |
| ------------------- | -------------- | ----------------- | --------------- | ----------------------------------------------------------------------------------- |
| Defense paper       | —              | —                 | blocks 1–26     | current rendered-page mapping unavailable                                           |
| Tracker Sheet       | —              | —                 | block 27        | A89 ordering conflicts with older local proposals; current page mapping unavailable |
| Standalone comments | Not proposed   | —                 | —               | —                                                                                   |
