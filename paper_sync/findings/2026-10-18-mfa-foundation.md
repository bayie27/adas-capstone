---
section: ERD, Data Dictionary, Auth Session, Frameworks and Libraries
page/s: "114–117, 128, 166, 291"
required_revision: Align the paper's schema and backend library description with staged MFA storage.
notes: P1 is additive; public login remains password-only until cutover.
status: Not started
assigned_to: Daniboy
synced: false
---

# P1 MFA foundation — schema and dependency drift

## Analysis

The live native document is **Group7_Capstone Project Defense Document - ITCAPROJ2** (`1MkTrdBPrrXpw8JGC4xrS475wbF7Yn-9YCaXIN-xd0aw`), revision `AHj4eMSnweWmZPSPT7laKA8Xy4phugSdIAMcywLUpDGAaYPx66S42zc6W8XM0IjPyPnLcOvWLMBu1P5rjy6eldRLJRRHt7AgWcUvmQD04gw`, read on 2026-10-18. Its native PDF export is 300 pages; pages 114–117, 128, 166, and 291 were rendered and visually checked.

The live tracker is **ADAS_Paper_Audit_Tracker** (`1iTt2K-t9Jyae-lqApCY0PX9N7HXCrKE850pvJLHzfoQ`), tab `🚩 Action Stream`. Existing row 32's earlier ten-table correction is marked Completed, row 29's stateful `auth_session` definition is also Completed, and there is no MFA, PyOTP, or cryptography row. Those historical corrections do not cover the three new P1 tables, the two new session columns, or the new direct dependencies. The first blank row is 89; `A89:H99` had no `userEnteredValue` on 2026-10-18.

P1 adds `mfa_credential`, `mfa_challenge`, and `mfa_recovery_code` in revision `5b87b6564753`; `auth_session` gains `auth_method` and `mfa_credential_version`. `pyotp` and `cryptography` are direct backend dependencies. P1 registers no MFA router and leaves the current password login unchanged. The proposed text labels the storage as staged and does not claim active MFA behavior.

## Changes

### 1. Defense paper — ERD narrative, ten-entity count

Page/s: 114 (rendered PDF export, 2026-10-18)

#### Change metadata

- Operation: replace
- Scope: logical paragraph
- Changed target: the sentence listing the ten persistent relational entities and four domains
- Preserve: the existing entity names and their groupings where unchanged
  Comment target: the complete replacement paragraph; resolve native indexes before writing

#### OLD

> The database’s operational workflow was structured around ten persistent relational entities clustered into four functional domains: Core Detection Operations (camera, detection_log), Security and Identity Management (user, auth_session, alarm_settings), System Governance and Async Jobs (audit_log, export_job), and Independent Documentation and Telemetry (help_article, sys_health_raw, sys_health_hourly).

#### NEW

The database’s operational workflow is structured around thirteen persistent relational entities clustered into five functional domains: Core Detection Operations (camera, detection_log), Security and Identity Management (user, auth_session, alarm_settings), staged MFA Foundation Storage (mfa_credential, mfa_challenge, mfa_recovery_code), System Governance and Async Jobs (audit_log, export_job), and Independent Documentation and Telemetry (help_article, sys_health_raw, sys_health_hourly).

#### Evidence

The live Doc's page 114 states ten entities and lists the four domains. The current SQLModel registry has the same ten prior application tables plus the three MFA tables; `backend/app/models/mfa.py` and migration `5b87b6564753_add_mfa_foundation_storage.py` establish the current schema. The disposable migration/schema-equivalence checks passed. The stage qualifier is supported by the P1 scope: `/api/auth/mfa` is not registered and the existing password login remains active.

#### Proposed comment (same gate as replacement)

Comment scope: logical paragraph; OLD and NEW are the complete ERD entity-count paragraph

Previous (marked, intentionally non-verbatim): The database’s operational workflow was structured around [[ten persistent relational entities clustered into four functional domains]]: Core Detection Operations (camera, detection_log), Security and Identity Management (user, auth_session, alarm_settings), System Governance and Async Jobs (audit_log, export_job), and Independent Documentation and Telemetry (help_article, sys_health_raw, sys_health_hourly).

Codex ID: PS-20261018-MFA-FOUNDATION

Done by Codex.

### 2. Defense paper — ERD child-table count

Page/s: 115 (rendered PDF export, 2026-10-18)

#### Change metadata

- Operation: replace
- Scope: span
- Changed target: `four specialized child tables`
- Preserve: the surrounding sentence and the existing child-table descriptions
  Comment target: `seven specialized child tables`; resolve native indexes before writing

#### OLD

> four specialized child tables

#### NEW

seven specialized child tables

#### Evidence

The live Doc's page 115 says the user entity is linked to four child tables and then describes `auth_session`, `alarm_settings`, `audit_log`, and `export_job`. P1 adds three user-keyed MFA tables with the foreign-key and cardinality constraints described in `backend/app/models/mfa.py`.

#### Proposed comment (same gate as replacement)

Comment scope: span; OLD `four specialized child tables`; NEW `seven specialized child tables`

Previous: four specialized child tables

Codex ID: PS-20261018-MFA-FOUNDATION

Done by Codex.

### 3. Defense paper — ERD narrative, MFA credential relationship

Page/s: 115 (rendered PDF export, 2026-10-18)

#### Change metadata

- Operation: insert
- Scope: logical paragraph
- Changed target: insert after the existing `auth_session` relationship description
- Preserve: all existing child-table descriptions and their order
  Comment target: only the inserted paragraph; resolve the insertion range before writing

#### OLD

> N/A

#### NEW

mfa_credential (Strict 1-to-1). Stores each user’s staged MFA state, credential version, encrypted active seed when enrolled, and recovery timestamps. This record is not used by the password-only login before cutover.

#### Evidence

`MfaCredential.user_id` is both its primary key and a cascading foreign key to `user.user_id`. The model permits `unenrolled`, `enrolled`, and `recovery_pending` states and stores ciphertext, version, replay step, recovery generation, and UTC timestamps.

#### Proposed comment (same gate as replacement)

Comment scope: logical paragraph; highlight only the inserted `mfa_credential` relationship paragraph

Previous: N/A

Codex ID: PS-20261018-MFA-FOUNDATION

Done by Codex.

### 4. Defense paper — ERD narrative, MFA challenge relationship

Page/s: 115 (rendered PDF export, 2026-10-18)

#### Change metadata

- Operation: insert
- Scope: logical paragraph
- Changed target: insert after the new `mfa_credential` relationship description
- Preserve: all existing child-table descriptions and their order
  Comment target: only the inserted paragraph; resolve the insertion range before writing

#### OLD

> N/A

#### NEW

mfa_challenge (Strict 1-to-1). Stores at most one staged MFA challenge per user, including its token digest, purpose, credential snapshot, optional encrypted pending seed, and UTC expiry. Challenges do not authenticate users before cutover.

#### Evidence

`MfaChallenge.user_id` is its primary key and a cascading foreign key to `user.user_id`; `token_hash` is unique. The purpose and pending-seed constraints are defined in `backend/app/models/mfa.py` and the P1 Alembic revision.

#### Proposed comment (same gate as replacement)

Comment scope: logical paragraph; highlight only the inserted `mfa_challenge` relationship paragraph

Previous: N/A

Codex ID: PS-20261018-MFA-FOUNDATION

Done by Codex.

### 5. Defense paper — ERD narrative, recovery-code relationship

Page/s: 115 (rendered PDF export, 2026-10-18)

#### Change metadata

- Operation: insert
- Scope: logical paragraph
- Changed target: insert after the new `mfa_challenge` relationship description
- Preserve: all existing child-table descriptions and their order
  Comment target: only the inserted paragraph; resolve the insertion range before writing

#### OLD

> N/A

#### NEW

mfa_recovery_code (1-to-Many). Stores generation-scoped recovery-code digests and consumption timestamps for each user; plaintext codes are not stored.

#### Evidence

`MfaRecoveryCode.user_id` references `user.user_id` with cascading deletion. The model constrains generations and digest length, enforces uniqueness by user, generation, and hash, and indexes unconsumed codes by user and generation.

#### Proposed comment (same gate as replacement)

Comment scope: logical paragraph; highlight only the inserted `mfa_recovery_code` relationship paragraph

Previous: N/A

Codex ID: PS-20261018-MFA-FOUNDATION

Done by Codex.

## Redraw required

### 6. Defense paper — Figure 7, Entity-Relationship Diagram of the Database Architecture

Page/s: 117 (rendered PDF export, 2026-10-18)

#### Change metadata

- Operation: redraw
- Scope: figure
- Changed target: Figure 7's entity boxes, fields, and relationship lines
- Preserve: the existing non-MFA entities, their fields, relationships, and surrounding caption
  Comment target: no standalone comment proposed

#### Current issue

Figure 7 shows the ten prior application tables. It does not show `mfa_credential`, `mfa_challenge`, or `mfa_recovery_code`, and its `auth_session` box lacks `auth_method` and `mfa_credential_version`.

#### Required redraw

Add the three staged MFA entities and their keys, checks, and relationships: `user` to `mfa_credential` (1-to-1), `user` to `mfa_challenge` (1-to-1), and `user` to `mfa_recovery_code` (1-to-Many). Add `auth_method` and `mfa_credential_version` to `auth_session`. Label the MFA storage as staged and keep the existing password-login flow unchanged until cutover.

#### Evidence

The live PDF's page 117 image was visually inspected. `backend/app/models/mfa.py`, `backend/app/models/user.py`, and migration `5b87b6564753_add_mfa_foundation_storage.py` define the missing entities and session columns. P1 does not register an MFA router or alter the password login.

### 7. Defense paper — Table 15, Auth Session revocation reason

Page/s: 128 (rendered PDF export, 2026-10-18)

#### Change metadata

- Operation: replace
- Scope: cell
- Changed target: the description cell for `revocation_reason`
- Preserve: the field name, data type, nullable constraint, and all other table rows
  Comment target: the complete replacement description cell; resolve native indexes before writing

#### OLD

> Reason for revocation (logout, password_change, admin_revoke, etc.).

#### NEW

Reason for revocation (logout, password_change, password_reset, role_change, account_disabled, admin_revoke, expired_cleanup, mfa_rollout, mfa_recovery, mfa_replacement, mfa_enrollment, mfa_restore).

#### Evidence

The live PDF's page 128 shows the `revocation_reason` row with the old examples. `AuthSession.__table_args__` and the P1 migration now allow the five `mfa_*` reasons alongside all prior reasons; existing values are preserved.

#### Proposed comment (same gate as replacement)

Comment scope: span; OLD `Reason for revocation (logout, password_change, admin_revoke, etc.).`; NEW is the complete replacement cell text

Previous: Reason for revocation (logout, password_change, admin_revoke, etc.).

Codex ID: PS-20261018-MFA-FOUNDATION

Done by Codex.

### 8. Defense paper — Table 15, Auth Session authentication method

Page/s: 128 (rendered PDF export, 2026-10-18)

#### Change metadata

- Operation: insert
- Scope: row
- Changed target: insert the `auth_method` row after `revocation_reason`
- Preserve: all existing rows and the table's four-column structure
  Comment target: only the inserted row text; resolve the row range before writing

#### OLD

> N/A

#### NEW

auth_method | String | Method used to authenticate this session. | Not Null, Default: password; values: password, totp, demo_impersonation

#### Evidence

`AuthSession.auth_method` is non-null, server-defaulted to `password`, and constrained to `password`, `totp`, or `demo_impersonation`. Existing sessions remain password sessions under P1.

#### Proposed comment (same gate as replacement)

Comment scope: span; Previous: N/A; highlight only the inserted `auth_method` row

Previous: N/A

Codex ID: PS-20261018-MFA-FOUNDATION

Done by Codex.

### 9. Defense paper — Table 15, MFA credential version

Page/s: 128 (rendered PDF export, 2026-10-18)

#### Change metadata

- Operation: insert
- Scope: row
- Changed target: insert the `mfa_credential_version` row immediately after `auth_method`
- Preserve: all existing rows and the table's four-column structure
  Comment target: only the inserted row text; resolve the row range before writing

#### OLD

> N/A

#### NEW

mfa_credential_version | Integer | Credential version bound to a TOTP-authenticated session. | Nullable, non-negative; required when auth_method is totp

#### Evidence

`AuthSession.mfa_credential_version` is nullable and non-negative; a database CHECK requires it for `auth_method='totp'`. Password and demo-impersonation sessions may leave it null.

#### Proposed comment (same gate as replacement)

Comment scope: span; Previous: N/A; highlight only the inserted `mfa_credential_version` row

Previous: N/A

Codex ID: PS-20261018-MFA-FOUNDATION

Done by Codex.

### 10. Defense paper — supplemental staged MFA data dictionary

Page/s: 291 (insertion point after the final existing Table 35; rendered PDF export, 2026-10-18)

#### Change metadata

- Operation: insert
- Scope: row
- Changed target: append Tables 36–38 as a staged MFA data-dictionary supplement after Table 35 and before UAT
- Preserve: existing Table labels 1–35, the Table 35 rows, and all following UAT text
  Comment target: only the inserted supplement; resolve the insertion range before writing

#### OLD

> N/A

#### NEW

Supplemental MFA Data Dictionary (P1 foundation; staged until cutover)

Table 36 — MFA Credential

Field Name | Data Type | Description | Constraints
user_id | Integer | User who owns this MFA credential. | Primary Key; Foreign Key (user.user_id), ON DELETE CASCADE
state | String | Current MFA state. | Not Null; CHECK: unenrolled, enrolled, recovery_pending
active_secret_ciphertext | String | Encrypted active TOTP seed. | Nullable
credential_version | Integer | Version of the user's MFA credential. | Not Null; CHECK >= 0
last_accepted_step | Integer | Last accepted TOTP time step. | Nullable; CHECK >= 0 when present
enrolled_at | Datetime | UTC time the factor was enrolled. | Nullable
recovery_started_at | Datetime | UTC time recovery-pending state began. | Nullable
recovery_generation | Integer | Recovery-code batch generation. | Not Null; CHECK >= 0
created_at | Datetime | UTC row creation time. | Not Null
updated_at | Datetime | UTC most recent row update time. | Not Null; auto-updates

Table 37 — MFA Challenge

Field Name | Data Type | Description | Constraints
user_id | Integer | User who owns this MFA challenge. | Primary Key; Foreign Key (user.user_id), ON DELETE CASCADE; one per user
token_hash | String(64) | SHA-256 digest of the opaque challenge token. | Not Null; Unique; length 64
purpose | String | Purpose of the MFA flow. | Not Null; CHECK: login, enroll, recovery_verify, recovery_enroll, replace
credential_version | Integer | Credential version snapshot. | Not Null; CHECK >= 0
password_changed_at | Datetime | UTC password-change snapshot. | Nullable
pending_secret_ciphertext | String | Encrypted pending TOTP seed. | Nullable; allowed only for enroll, recovery_enroll, replace
created_at | Datetime | UTC challenge creation time. | Not Null
expires_at | Datetime | UTC challenge expiration time. | Not Null

Table 38 — MFA Recovery Code

Field Name | Data Type | Description | Constraints
recovery_code_id | Integer | Unique recovery-code row identifier. | Primary Key; Auto-increment
user_id | Integer | User who owns this recovery code. | Foreign Key (user.user_id), ON DELETE CASCADE
generation | Integer | Recovery-code batch generation. | Not Null; CHECK >= 1
code_hash | String(64) | SHA-256 digest of a canonical recovery code. | Not Null; length 64; unique by user and generation
created_at | Datetime | UTC recovery-code creation time. | Not Null
consumed_at | Datetime | UTC time the recovery code was consumed. | Nullable

#### Evidence

The live PDF's page 291 ends Table 35, followed by the UAT section on page 292. Appending Tables 36–38 at this boundary preserves existing table numbering 1–35. The model fields and constraints are in `backend/app/models/mfa.py` and migration `5b87b6564753_add_mfa_foundation_storage.py`. This supplement documents schema only; it does not claim that MFA login, enrollment, recovery, or management flows are active.

#### Proposed comment (same gate as replacement)

Comment scope: logical paragraph; Previous: N/A; highlight only the inserted MFA data-dictionary supplement

Previous: N/A

Codex ID: PS-20261018-MFA-FOUNDATION

Done by Codex.

### 11. Defense paper — Frameworks and Libraries, staged MFA dependencies

Page/s: 166 (rendered PDF export, 2026-10-18)

#### Change metadata

- Operation: insert
- Scope: span
- Changed target: insert after the sentence naming `argon2-cffi` for password hashing
- Preserve: all existing backend, frontend, AI-engine, and operations library descriptions
  Comment target: only the inserted sentence; resolve native indexes before writing

#### OLD

> N/A

#### NEW

The backend also declares PyOTP and cryptography for the staged MFA foundation’s TOTP primitives and Fernet seed encryption; the existing password-only login remains active until cutover.

#### Evidence

The live PDF's page 166 lists `pyjwt` and `argon2-cffi` but not `pyotp` or `cryptography`. `pyproject.toml` now declares `pyotp>=2.10.0` and `cryptography>=50.0.2`; `uv.lock` resolves them to PyOTP 2.10.0 and cryptography 50.0.2. The default isolated browser login passed and no MFA router is registered.

#### Proposed comment (same gate as replacement)

Comment scope: span; Previous: N/A; highlight only the inserted dependency sentence

Previous: N/A

Codex ID: PS-20261018-MFA-FOUNDATION

Done by Codex.

### 12. Tracker Sheet — 🚩 Action Stream!A89:H89

#### Change metadata

- Operation: insert
- Scope: row
- Changed target: first verified blank row, A89:H89
- Preserve: rows 1–88, existing formatting and validation, and leave Reviewed by blank
  Comment target: exact new text colored orange (#E67E22); no Sheet comment

#### OLD

> N/A — `🚩 Action Stream!A89:H99` had no `userEnteredValue` on 2026-10-18.

#### NEW

- A: Major
- B: ERD, Data Dictionary, Auth Session, Frameworks and Libraries
- C: 114–117, 128, 166, 291
- D: Document staged MFA storage and dependencies without implying MFA is active
- E: P1 adds three MFA tables, two session columns, and two direct dependencies. Password-only login remains active until cutover. Add a Figure 7 redraw and staged schema documentation.
- F: Not started
- G: Daniboy
  H: (blank)

#### Evidence

Live native spreadsheet `ADAS_Paper_Audit_Tracker` (`1iTt2K-t9Jyae-lqApCY0PX9N7HXCrKE850pvJLHzfoQ`), tab `🚩 Action Stream`. Metadata shows 99 rows and 8 columns. A cell-level read of A89:H99 returned no `userEnteredValue`; the current last occupied record is row 88. Existing row 32 (the earlier ten-table correction) and row 29 (stateful session definition) remain Completed; neither describes P1 MFA storage or its dependencies.

#### Formatting fallback (same gate as replacement)

Color only the newly inserted text in A89:G89 orange (#E67E22); leave H89 blank and preserve the row's existing formatting, validation, and manual fields.

## Approval / sync ledger

- Package ID: PS-20261018-MFA-FOUNDATION
  Approval source: Not approved; no Drive write was requested in the P1 implementation task.

| Target              | Approved scope | Applied/read back | Skipped/pending | Blocked |
| ------------------- | -------------- | ----------------- | --------------- | ------- |
| Defense paper       | —              | —                 | blocks 1–11     | —       |
| Tracker Sheet       | —              | —                 | block 12        | —       |
| Standalone comments | Not proposed   | —                 | —               | —       |

The current paper describes ten application entities and the old `auth_session` shape. The P1 proposal covers the schema-count narrative, ERD relationships, Figure 7, Table 15, the staged backend dependencies, and supplemental Tables 36–38. All changes remain proposals; no native Doc, Sheet, or comment was written.
