---
section: "Use Cases — Use Case 2 (Manage User Accounts), Figure 4, FR-20"
page/s: "pp. 64, 72–74; p. 97; p. 100; audit Doc p. 24"
required_revision: "Add the deactivated-user restore path and align the administrator account-management narrative and audit actions with the live UI"
notes: "FR-03 and the UC-2 postcondition already mention that retained user accounts may be restored. The existing wireframe-coverage finding owns the missing User Management screens; Figure 4 also needs the user-restore branch added when it is redrawn."
status: Not started
assigned_to: Daniboy
synced: false
---

## Changes

### 1. Defense paper — Use Case 2, Main Flow step 2

Page/s: p. 72

#### OLD

> The Administrator selects an action: Add New User, Edit User Details, Change User Password, or Delete User.

#### NEW

The Administrator selects an action: Add New User, Edit User Details, Change User Password, Delete User, or Restore a previously deleted (deactivated) User account.

#### Evidence

The live native defense Doc contains the OLD text at Docs range `t.y7ms6bhlk4qn:108197–108304`. The current User Management page exposes the deactivated-user path through the state filter and a row-level Restore action at `frontend/src/pages/Users.tsx:148-160, 205-300`.

The API wrapper sends the reactivation request through `frontend/src/api/users.ts:94-112`; the backend accepts a retained deactivated row for the update path at `backend/app/api/routes/users.py:303-317`.

#### Proposed comment (Defense paper gate)

Previous: The Administrator selects an action: Add New User, Edit User Details, Change User Password, or Delete User.

Codex ID: PS-20260825-USER-RESTORE-UC2

Done by Codex.

### 2. Defense paper — Use Case 2, Main Flow step 3

Page/s: p. 73

#### OLD

> The Administrator enters the required information into the corresponding form (e.g., new account details, updated roles, or new passwords) or confirms the deletion prompt.

#### NEW

The Administrator enters the required information into the corresponding form (e.g., new account details, updated roles, or new passwords), confirms a deletion prompt, or filters the directory to “Deactivated only” or “All” before selecting Restore for the target previously deleted (deactivated) account.

#### Evidence

The live native defense Doc contains the OLD text at Docs range `t.y7ms6bhlk4qn:108305–108476`. Restore is a direct row action in `frontend/src/pages/Users.tsx:280-300`; it does not open an edit form or deletion-confirmation modal.

#### Proposed comment (Defense paper gate)

Previous: The Administrator enters the required information into the corresponding form (e.g., new account details, updated roles, or new passwords) or confirms the deletion prompt.

Codex ID: PS-20260825-USER-RESTORE-UC2

Done by Codex.

### 3. Defense paper — Use Case 2, Alternative Flows after 5a

Page/s: p. 74

#### OLD

> No restore alternative flow is present after 5a.

#### NEW

6a. Restore Deleted User: If the Administrator filters the directory to “Deactivated only” or “All,” selects a previously deleted (deactivated) user account, and chooses “Restore,” the system reactivates the retained user record and refreshes the user directory while preserving its historical actions.

#### Evidence

The live native defense Doc has no restore alternative after the current UC-2 `5a` paragraph at Docs range `t.y7ms6bhlk4qn:109202–109684`. The frontend renders the exact `Deactivated only` and `All` options at `frontend/src/pages/Users.tsx:148-160` and the Restore mutation at `frontend/src/pages/Users.tsx:111-123, 280-300`.

The backend’s `?is_active=false` and `?is_active=null` filters surface deactivated or both account states at `backend/app/api/routes/users.py:205-246`; `backend/tests/test_users.py:633-667` verifies the deactivate → list inactive → reactivate → list active round trip and its audit rows.

#### Proposed comment (Defense paper gate)

Previous: No restore alternative flow is present after 5a.

Codex ID: PS-20260825-USER-RESTORE-UC2

Done by Codex.

### 4. Defense paper — FR-20 Activity Audit Trail

Page/s: p. 64

#### OLD

> For Administrators, the system shall record user account creation, account editing, account disabling, role changes, and password updates.

#### NEW

For Administrators, the system shall record user account creation, account editing, account disabling or restoration, role changes, and password updates.

#### Evidence

The live native defense Doc contains the OLD text at Docs range `t.y7ms6bhlk4qn:98947–99705`. The backend records a successful `USER_ENABLE` row when a deactivated account becomes active again at `backend/app/api/routes/users.py:374-377, 431-439`; the round-trip test asserts one `USER_ENABLE` action at `backend/tests/test_users.py:659-667`.

#### Proposed comment (Defense paper gate)

Previous: For Administrators, the system shall record user account creation, account editing, account disabling, role changes, and password updates.

Codex ID: PS-20260825-USER-RESTORE-UC2

Done by Codex.

### 5. Defense paper — Use Case Diagram narrative, User Account Administration

Page/s: p. 100

#### OLD

> User Account Administration. The Manage User Accounts workflow is exclusively reserved for Administrators. When accessing this secured directory, Administrators are provided with a comprehensive suite of access-control tools necessary to maintain the dispatch team's security, including the ability to Add User Account, Edit User Account, Delete User Account, and forcefully Change User Password.

#### NEW

User Account Administration. The Manage User Accounts workflow is exclusively reserved for Administrators. When accessing this secured directory, Administrators are provided with a comprehensive suite of access-control tools necessary to maintain the dispatch team's security, including the ability to Add User Account, Edit User Account, Delete User Account, Restore Deactivated User Accounts, and forcefully Change User Password.

#### Evidence

The live native defense Doc contains the OLD text at Docs range `t.y7ms6bhlk4qn:148580–148976`. The current UI shows Restore only for deactivated rows and keeps edit, password-reset, and delete actions on active rows at `frontend/src/pages/Users.tsx:241-300`.

#### Proposed comment (Defense paper gate)

Previous: User Account Administration. The Manage User Accounts workflow is exclusively reserved for Administrators. When accessing this secured directory, Administrators are provided with a comprehensive suite of access-control tools necessary to maintain the dispatch team's security, including the ability to Add User Account, Edit User Account, Delete User Account, and forcefully Change User Password.

Codex ID: PS-20260825-USER-RESTORE-UC2

Done by Codex.

### 6. ADAS_Paper_Audit — §3.4 Use-case ↔ UI mismatches

Page/s: p. 24

#### OLD

> No existing audit note covers UC-2 restoration of a deactivated user.

#### NEW

UC-2 also needs a restore flow: Administrators can filter the directory to deactivated accounts, select a previously deleted (deactivated) account, and choose Restore to reactivate the retained user record; the account’s historical audit records remain associated with it.

#### Evidence

This is a new insertion after the current UC-2 `5a` note in the live `ADAS_Paper_Audit` Doc (`t.0:49125–49619`). `frontend/src/pages/Users.tsx:148-160, 280-300` implements the filter and Restore action; `backend/app/api/routes/users.py:303-317, 374-377, 431-439` reactivates the retained row and records `USER_ENABLE`. `backend/tests/test_users.py:633-667` verifies the round trip and audit trail.

#### Proposed comment (Audit + tracker gate)

Previous: No existing audit note covers UC-2 restoration of a deactivated user.

Codex ID: PS-20260825-USER-RESTORE-UC2

Done by Codex.

### 7. Tracker Sheet — `🚩 Action Stream`!A70:H70

Sheet tab/range: `🚩 Action Stream`!A70:H70

#### OLD

> No existing user-specific row at A70:H70. Existing entries at A67:H69 are preserved unchanged.

#### NEW

| Change Type | Section / Chapter                                  | Page Number        | Required Revision                                                                                                                  | Notes                                                                                                                                                                                                                  | Status      | Assigned to | Reviewed by |
| ----------- | -------------------------------------------------- | ------------------ | ---------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------- | ----------- | ----------- |
| Minor       | Use Case 2 (Manage User Accounts), Figure 4, FR-20 | 64, 72–74, 97, 100 | Add the deactivated-user restore path and align the administrator account-management narrative and audit actions with the live UI. | Deactivated accounts can be filtered and restored; restoration is audited as USER_ENABLE. Existing FR-03 and the UC-2 postcondition already mention restore. Audit Doc §3.4, p. 24, also needs the corresponding note. | Not started | Daniboy     |             |

#### Evidence

The live `ADAS_Paper_Audit_Tracker` Sheet was read through Google Drive MCP on 2026-08-25. `🚩 Action Stream`!A70:H70 has no `userEnteredValue`; existing entries at A67:H69 are preserved. The proposed row uses the first fully blank row after those entries and leaves the manual `Reviewed by` cell blank.

#### Proposed comment (Audit + tracker gate)

Previous: No existing user-specific row at A70:H70.

Codex ID: PS-20260825-USER-RESTORE-UC2

Done by Codex.

## Redraw required

### Figure 4 — Use Case Diagram

Page/s: p. 97

#### Current issue

The current user-management branch does not document the implemented Restore User action; its accompanying narrative lists Add, Edit, Delete, and Change User Password only. The existing camera-restore finding already tracks the corresponding Restore Camera addition to this same figure.

#### Required redraw

Add a `Restore User` use-case node under the Administrator’s user-account-management branch, alongside Add User, Edit User, Delete User, and Change User Password. Keep the action Administrator-only and show it as the path for a deactivated retained account.

#### Proposed comment (Standalone comments gate)

Review: Figure 4 should include a Restore User action under the Administrator’s user-management branch, alongside the already tracked camera restore action.

Codex ID: PS-20260825-USER-RESTORE-UC2

Done by Codex.

## Preserved on purpose

- The live FR-03 requirement already says Administrators can create, edit, delete, and restore user accounts; no FR-03 replacement is proposed.
- The live UC-2 postcondition already says a deleted account is soft-deactivated, retained, and restorable; the finding adds the missing executable flow rather than repeating that accurate sentence.
- The existing ADAS_Paper_Audit §3.3 / tracker row 40 owns the missing User Management, Add User, Edit User, Reset Password, and Delete User wireframes. When those screens are redrawn, the deactivated-state filter and Restore action should be shown, but this finding does not duplicate that coverage issue.
- The existing camera-restore finding owns the camera-specific Figure 4 and camera-management updates; this finding adds only the user branch.

## Approval / sync ledger

Package ID: `PS-20260825-USER-RESTORE-UC2`

| Target              | Approved scope                   | Applied/read back                          | Skipped/pending                      | Blocked                           |
| ------------------- | -------------------------------- | ------------------------------------------ | ------------------------------------ | --------------------------------- |
| Defense paper       | blocks 1–4 and attached comments | blocks 1–4 and comments                    | block 5 (Use Case Diagram narrative) | —                                 |
| ADAS_Paper_Audit    | block 6 and attached comment     | block 6 and comment                        | —                                    | —                                 |
| Tracker Sheet       | block 7 row and attached comment | `🚩 Action Stream`!A70:G70; H70 blank      | —                                    | tracker comment: no native anchor |
| Standalone comments | Figure 4 review comment          | exact `Figure 4` caption range and comment | —                                    | —                                 |

The temporary unanchored tracker comment was resolved and remains only in this local finding. `synced` remains `false` because block 5 is pending and the tracker comment is blocked.
