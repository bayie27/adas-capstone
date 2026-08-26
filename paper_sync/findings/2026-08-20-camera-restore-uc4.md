---
section: "Use Cases — Use Case 4 (Manage Cameras)"
page/s: "pp. 76–77; p. 97; p. 100; pp. 131–132; audit Doc pp. 23–24"
required_revision: Add the removed-camera restore path and align the camera-management figures and prose with the live UI
notes: The live implementation supports soft deletion, filtered listing, restoration, and duplicate-conflict handling. Figure 4 and Figure 12 also need redraws.
status: In progress
assigned_to: Daniboy
synced: false
---

## Where

The live defense Doc still contains the stale Use Case 4 action list, database-removal wording,
and camera-management narratives. The current code and tests expose a removed-camera listing,
restore action, soft-delete retention, and duplicate Name/Channel ID protection.

Page mapping was made against the live native Doc's internal PDF export: Use Case 4 is on
pp. 76–77, Figure 4 is on p. 97 with its narrative on p. 100, and Figure 12 is on p. 131 with
its narrative on pp. 131–132. The related audit explanation is on audit Doc pp. 23–24.

## Changes

### 1. Defense paper — Use Case 4, Main Flow step 2

Page/s: p. 76

#### OLD

> The user selects a specific management action: Add New Camera, Edit Camera Configuration, Disable/Enable Feed, or Remove Camera.

#### NEW

The user selects a specific management action: Add New Camera, Edit Camera Configuration, Disable/Enable Feed, Remove Camera, or Restore a previously removed Camera.

#### Evidence

`backend/app/api/routes/cameras.py:162-198` supports active-only, removed-only, and both-camera listing. `frontend/src/pages/Cameras.tsx:99,140-150,394-398` exposes the camera-state filter.

#### Proposed comment (Defense paper gate)

Previous: The user selects a specific management action: Add New Camera, Edit Camera Configuration, Disable/Enable Feed, or Remove Camera.

Done by Codex.

### 2. Defense paper — Use Case 4, Main Flow step 6 database clause

Page/s: p. 76

#### OLD

> and updates or deletes the database record.

#### NEW

and, for a removal, deactivates rather than erases the database record so it can be restored later.

#### Evidence

`backend/app/api/routes/cameras.py:445-478` sets `is_active` false in the delete path, while the restore-capable PATCH path uses `_get_camera_or_404` at lines 305-316. `backend/tests/test_cameras.py:1109-1127` verifies that restored cameras retain linked detection records.

#### Proposed comment (Defense paper gate)

Previous: and updates or deletes the database record.

Done by Codex.

### 3. Defense paper — Use Case 4, Alternative Flows after 5a

Page/s: p. 77

#### OLD

> No restore alternative flow is present after 5a.

#### NEW

6a. Restore Removed Camera: If the user selects a removed camera and chooses "Restore," the system reactivates the record unless its Camera Name or Channel ID conflicts with an active camera; otherwise it displays the duplicate-configuration error.

#### Evidence

`backend/app/api/routes/cameras.py:316-346,414-435` accepts a removed row for PATCH restoration, rejects duplicate active Name/Channel ID values with `CONFLICT_DUPLICATE`, and records `CAMERA_RESTORE`. The corresponding UI action is `frontend/src/pages/Cameras.tsx:545-562`; collision coverage is in `backend/tests/test_cameras.py:1010-1054`.

#### Proposed comment (Defense paper gate)

Previous: No restore alternative flow is present after 5a.

Done by Codex.

### 4. Defense paper — Use Case 4, Postconditions

Page/s: p. 77

#### OLD

> The camera database is updated to reflect the new configurations or deletions.

#### NEW

The camera database reflects new configurations, activations, or deactivations; removed records are preserved for restoration.

#### Evidence

`backend/app/models/camera.py:53-74` defines partial uniqueness for active cameras while retaining the row, and `backend/tests/test_cameras.py:974-1008,1109-1127` verifies the restore round trip and linked detection history.

#### Proposed comment (Defense paper gate)

Previous: The camera database is updated to reflect the new configurations or deletions.

Done by Codex.

### 5. Defense paper — Use Case Diagram narrative, Camera Configuration Management

Page/s: p. 100

#### OLD

> dispatchers can perform administrative tasks such as Add New Camera, Edit Camera Configuration, View Camera Status, or Delete Camera Feed.

#### NEW

dispatchers can perform administrative tasks such as Add New Camera, Edit Camera Configuration, View Camera Status, Delete Camera Feed, or Restore a previously removed Camera Feed.

#### Evidence

`frontend/src/pages/Cameras.tsx:394-398,502-562` shows the camera-state filter and the Restore action for removed rows. `frontend/src/api/cameras.ts:63-73,116-153` carries the three-state filter and restore request.

#### Proposed comment (Defense paper gate)

Previous: dispatchers can perform administrative tasks such as Add New Camera, Edit Camera Configuration, View Camera Status, or Delete Camera Feed.

Done by Codex.

### 6. Defense paper — Figure 12 narrative, camera filters

Page/s: p. 132

#### OLD

> A dedicated query toolbar is positioned directly beneath these KPIs, integrating a dynamic search input and dropdown filters for "Network Connection" and "AI Detection Status" to enable rapid identification of specific camera feeds. The primary call-to-action, the "Add Camera" button, is strategically anchored at the top right and distinguished by a contrasting background and clear icon.

#### NEW

A dedicated query toolbar is positioned directly beneath these KPIs, integrating a dynamic search input and dropdown filters for "Network Connection," "AI Detection Status," camera enablement, and camera state (Active only, Deleted only, or All) to enable rapid identification of specific camera feeds. The primary call-to-action, the "Add Camera" button, is strategically anchored at the top right and distinguished by a contrasting background and clear icon.

#### Evidence

`frontend/src/pages/Cameras.tsx:344-408` renders connection, AI-status, enablement, and Active only/Deleted only/All filters. The current audit Doc records the stale two-filter description at §3.2, p. 23.

#### Proposed comment (Defense paper gate)

Previous: A dedicated query toolbar is positioned directly beneath these KPIs, integrating a dynamic search input and dropdown filters for "Network Connection" and "AI Detection Status" to enable rapid identification of specific camera feeds. The primary call-to-action, the "Add Camera" button, is strategically anchored at the top right and distinguished by a contrasting background and clear icon.

Done by Codex.

### 7. Defense paper — Figure 12 narrative, Actions column

Page/s: p. 132

#### OLD

> The central component is a structured data table listing individual camera configurations and their real-time operational states. The interactive 'Actions' column is organized by usage frequency and operational risk: routine controls, such as the active state toggle and edit functions, precede the delete action, which is isolated at the far right to reduce the risk of accidental data loss.

#### NEW

The central component is a structured data table listing individual camera configurations and their real-time operational states. The interactive 'Actions' column retains the active-state toggle, edit, and delete controls for active rows; a removed-camera row instead provides a Restore action.

#### Evidence

`frontend/src/pages/Cameras.tsx:502-562` renders toggle, edit, and delete controls for active rows and Restore for removed rows. The current audit Doc records the stale action description at §3.2, p. 23.

#### Proposed comment (Defense paper gate)

Previous: The central component is a structured data table listing individual camera configurations and their real-time operational states. The interactive 'Actions' column is organized by usage frequency and operational risk: routine controls, such as the active state toggle and edit functions, precede the delete action, which is isolated at the far right to reduce the risk of accidental data loss.

Done by Codex.

### 8. ADAS_Paper_Audit — §3.2 Wireframe mismatches, Figure 12 filter description

Page/s: p. 23

#### OLD

> filters for "Network Connection" and "AI Detection Status"

#### NEW

filters for "Network Connection," "AI Detection Status," camera enablement, and camera state (Active only, Deleted only, or All)

#### Evidence

Live audit Doc range `t.0:46858-46916`; corresponding defense-paper narrative is p. 132. The four filters are rendered in `frontend/src/pages/Cameras.tsx:344-408`.

#### Proposed comment (Audit + tracker gate)

Previous: filters for "Network Connection" and "AI Detection Status"

Done by Codex.

### 9. ADAS_Paper_Audit — §3.2 Wireframe mismatches, Figure 12 actual filter count

Page/s: p. 23

#### OLD

> three dropdowns; the third filters by enablement (Cameras.tsx:153-207)

#### NEW

four dropdowns; the third filters by enablement and the fourth filters by camera state (Active only, Deleted only, or All).

#### Evidence

Live audit Doc range `t.0:46918-46988`. `frontend/src/pages/Cameras.tsx:344-408` renders the four current dropdowns; the file-path citation stays in Evidence rather than in NEW.

#### Proposed comment (Audit + tracker gate)

Previous: three dropdowns; the third filters by enablement (Cameras.tsx:153-207)

Done by Codex.

### 10. ADAS_Paper_Audit — §3.2 Wireframe mismatches, Figure 12 paper action description

Page/s: p. 23

#### OLD

> Actions column includes "the active state toggle"

#### NEW

Actions column includes the active-state toggle, edit, and delete controls for active rows, plus Restore for removed rows.

#### Evidence

Live audit Doc range `t.0:47003-47052`; corresponding defense-paper narrative is p. 132. `frontend/src/pages/Cameras.tsx:502-562` is the current action rendering.

#### Proposed comment (Audit + tracker gate)

Previous: Actions column includes "the active state toggle"

Done by Codex.

### 11. ADAS_Paper_Audit — §3.2 Wireframe mismatches, Figure 12 actual action behavior

Page/s: p. 23

#### OLD

> the Switch is rendered disabled — a read-only indicator (Cameras.tsx:253)

#### NEW

the Switch is enabled for active rows and is disabled only while its update is pending; removed rows show Restore.

#### Evidence

Live audit Doc range `t.0:47054-47127`. `frontend/src/pages/Cameras.tsx:502-562` shows the active-row mutation and the removed-row Restore branch.

#### Proposed comment (Audit + tracker gate)

Previous: the Switch is rendered disabled — a read-only indicator (Cameras.tsx:253)

Done by Codex.

### 12. ADAS_Paper_Audit — §3.4 Use-case ↔ UI mismatches, UC-4 restore coverage

Page/s: p. 24

#### OLD

> No existing audit note covers UC-4 restoration of a soft-deleted camera.

#### NEW

UC-4 also needs a restore flow: removed cameras can be listed, restored when their name and Channel ID are not in use by an active camera, and kept linked to their historical detection records.

#### Evidence

This is an insertion after the existing UC-4 notes at live audit Doc §3.4. `backend/app/api/routes/cameras.py:162-198,316-346,414-435` implements filtered listing, one-directional restoration, and duplicate-conflict handling. `backend/tests/test_cameras.py:974-1008,1010-1054,1109-1127` verifies the behavior.

#### Proposed comment (Audit + tracker gate)

Previous: No existing audit note covers UC-4 restoration of a soft-deleted camera.

Done by Codex.

### 13. Tracker Sheet — `🚩 Action Stream`!A68:H68

Page/s: `🚩 Action Stream`!A68:H68

#### OLD

> No existing camera-specific row at A68:H68. Related row 62, `FR-03 User Account Management & UCs 2-4 — Add restore user/camera`, is preserved unchanged.

#### NEW

| Change Type | Section / Chapter                           | Page Number             | Required Revision                                                                                           | Notes                                                                                            | Status      | Assigned to | Reviewed by |
| ----------- | ------------------------------------------- | ----------------------- | ----------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------ | ----------- | ----------- | ----------- |
| Minor       | Use Case 4 (Manage Cameras), Figures 4 & 12 | 75–77, 97, 100, 131–132 | Add the removed-camera restore path and align the camera-management figures and narrative with the live UI. | Soft-deleted cameras can be listed and restored; duplicate Name/Channel ID conflicts return 409. | Not started | Daniboy     |             |

#### Evidence

Live Sheet metadata identifies the `🚩 Action Stream` tab as sheet ID `1620600289`. The related generic row at row 62 is preserved. Row 67 was not overwritten because `D67` contains the unrelated manual note `revise 2 laptop netw setup; use vlan or at least accurate to the assumed setup`; `A68:H68` was the first fully blank row. The new row keeps the existing row 62's user-account scope intact.

#### Proposed comment (Audit + tracker gate)

Previous: No existing camera-specific row at A68:H68.

Done by Codex.

## Redraw required

### Figure 4 — Use Case Diagram

Page/s: p. 97

#### Current issue

The drawn diagram has no Restore Camera use-case node even though the live camera-management flow can list and restore removed cameras.

#### Required redraw

Add a `Restore Camera` use-case node under the Operator/Administrator camera-management actions, alongside the existing Add, Edit, Enable/Disable, and Remove actions. Keep the actor permissions consistent with the existing camera-management branch.

#### Proposed comment (Standalone comments gate)

Review: Figure 4 should include the implemented Restore Camera action in the camera-management branch.

Done by Codex.

### Figure 12 — Camera Management Page

Page/s: p. 131

#### Current issue

The screenshot does not show the current enablement and camera-state filters or the Restore action shown for a removed-camera row.

#### Required redraw

Replace the screenshot with the current Camera Management page: show the Network Connection, AI Detection Status, enablement, and Active only/Deleted only/All filters, plus a removed-camera row whose Actions column shows Restore.

#### Proposed comment (Standalone comments gate)

Review: Figure 12 should show the current four-filter toolbar and the Restore action for a removed-camera row.

Done by Codex.

## Preserved on purpose

- Table 10's `is_active` definition already describes soft deletion, preserved forensic history, and detection-log associations; it does not need another replacement.
- The existing UC-4 step 5/6 worker-process and heartbeat mismatch remains separately tracked in `ADAS_Paper_Audit` §2.4. This finding changes only the removal/restore wording and does not merge the two issues.
- Tracker row 62, `FR-03 User Account Management & UCs 2-4`, remains unchanged because this finding supplies the separate camera-specific row.

## Approval routing

1. **Defense paper** — blocks 1–7 and their attached `Previous:` comments. Figures 4 and 12 are redraw requests, not direct figure edits.
2. **ADAS_Paper_Audit plus tracker Sheet** — blocks 8–13 and their attached `Previous:` comments. A Sheet comment will be created only if the connector can verify a native cell anchor.
3. **Standalone comments** — the proposed Figure 4 and Figure 12 review comments only.

## Sync status

- 2026-08-25: Defense paper blocks 1–4 were applied and read back successfully. Their four native highlighted comments were created and verified as open.
- 2026-08-25: After approval, ADAS_Paper_Audit blocks 8–12 and tracker row `🚩 Action Stream`!A68:H68 were applied and read back successfully. Occupied row 67 was preserved. Audit replacement comments and standalone Figure 4/Figure 12 comments were created and verified as open; the proposed tracker comment remains in this finding because no provider-valid native Sheet-cell comment writer is available.
- Defense paper blocks 5–7 remain pending approval, so `synced` stays `false` because this finding is only partially applied.
