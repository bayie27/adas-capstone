---
section: "FR-02, UC-7, actor/DFD narrative, and UAT"
page/s: "unconfirmed"
required_revision: "Make AI Performance analytics and exports Administrator-only"
notes: "Live paper, audit Doc, audit tracker, and Test Execution Tracker re-read on 2026-09-04. P28's merged terminology changes are preserved; DFD changes coordinate with the pending logical-DFD finding rather than duplicating its redraw."
status: "Not started"
assigned_to: "Daniboy"
synced: false
---

## Changes

### 1a. Defense paper — Scope and Delimitations, Operator analytics/telemetry span

Page/s: unconfirmed; native span `17222–17284` within paragraph `16341–17755`

#### OLD

> monitor analytics, system health, and AI-performance telemetry

#### NEW

monitor dashboard analytics and system health

#### Evidence

This contiguous span is the Operator/Administrator scope sentence in the live Scope and Delimitations paragraph. The implementation keeps Dashboard analytics and System Health available to Operators while the performance endpoints require `get_current_admin` (`backend/app/api/routes/analytics.py:680-759`).

#### Proposed comment (same gate as associated replacement)

Comment scope: Span scope — replace the exact contiguous span `monitor analytics, system health, and AI-performance telemetry` with `monitor dashboard analytics and system health`.

Previous: monitor analytics, system health, and AI-performance telemetry

Codex ID: PS-20260903-ADMIN-AI-PERFORMANCE

Done by Codex.

### 1b. Defense paper — Scope and Delimitations, Administrator metrics sentence insertion

Page/s: unconfirmed; native span `17320–17345` within paragraph `16341–17755`

#### OLD

> Role-Based Access Control

#### NEW

Administrators can additionally review AI-performance metrics and reports. Role-Based Access Control

#### Evidence

Insert the Administrator-only AI Performance sentence immediately before the existing `Role-Based Access Control` sentence in the live scope paragraph. The page is rendered only at `/admin/ai` and the performance APIs use the Admin dependency (`frontend/src/App.tsx:80-113`; `backend/app/api/routes/analytics.py:680-759`).

#### Proposed comment (same gate as associated replacement)

Comment scope: Span scope — insert the exact sentence `Administrators can additionally review AI-performance metrics and reports.` immediately before `Role-Based Access Control`; highlight only the inserted sentence.

Previous: N/A

Codex ID: PS-20260903-ADMIN-AI-PERFORMANCE

Done by Codex.

### 1c. Defense paper — Scope and Delimitations, Administrator export span

Page/s: unconfirmed; native span `17489–17511` within paragraph `16341–17755`

#### OLD

> restoration functions.

#### NEW

restoration functions, and review and export AI-performance reports.

#### Evidence

This contiguous ending of the Administrator privilege list adds the implemented performance-report export capability. The asynchronous performance job boundary is enforced in `backend/app/api/routes/exports.py:72-168`.

#### Proposed comment (same gate as associated replacement)

Comment scope: Span scope — replace the exact contiguous span `restoration functions.` with `restoration functions, and review and export AI-performance reports.`.

Previous: restoration functions.

Codex ID: PS-20260903-ADMIN-AI-PERFORMANCE

Done by Codex.

### 2a. Defense paper — Table 2, FR-02 Operator AI-performance deletion

Page/s: unconfirmed; native span `92914–92933` within paragraph `92713–93049`

#### OLD

> and AI performance

#### NEW

`DELETE ONLY — insert nothing.`

#### Evidence

Deleting this exact span from `system health and AI performance metrics` leaves the live FR-02 Operator capability as `system health metrics`. The immediately preceding left character is `h`, the final character of `health`.

#### Proposed comment (same gate as associated replacement)

Comment scope: Deletion-only span — delete the exact span ` and AI performance`; after deletion, highlight/comment the nearest left character `h` in `health`.

Previous: and AI performance

Codex ID: PS-20260903-ADMIN-AI-PERFORMANCE

Done by Codex.

### 2b. Defense paper — Table 2, FR-02 Administrator AI-performance access insertion

Page/s: unconfirmed; native span `93025–93048` within paragraph `92713–93049`

#### OLD

> User Account Management

#### NEW

AI performance monitoring, AI performance exports, and User Account Management

#### Evidence

The Administrator sentence gains the two restricted AI Performance capabilities immediately before its existing `User Account Management` capability. The frontend Admin navigation and backend route dependencies enforce the same boundary (`frontend/src/App.tsx:80-113`; `frontend/src/components/layouts/Sidebar.tsx:88-107`; `backend/app/api/routes/analytics.py:680-759`).

#### Proposed comment (same gate as associated replacement)

Comment scope: Span scope — replace the exact span `User Account Management` with `AI performance monitoring, AI performance exports, and User Account Management`; highlight the full new span.

Previous: User Account Management

Codex ID: PS-20260903-ADMIN-AI-PERFORMANCE

Done by Codex.

### 3. Defense paper — Table 2, FR-18 Report Generation and Data Export

Page/s: unconfirmed; native span `98123–98146` within paragraph `98049–98288`

#### OLD

> and AI performance data

#### NEW

and shall allow Administrators to export AI performance data

#### Evidence

This exact span is in the live FR-18 sentence. Replace only `and AI performance data` with `and shall allow Administrators to export AI performance data`; incident and summary exports remain available to users, while performance exports are Admin-only. The async route applies the same boundary to `report_type="performance"`.

#### Proposed comment (same gate as associated replacement)

Comment scope: Span scope — replace the exact contiguous span `and AI performance data` with `and shall allow Administrators to export AI performance data`; highlight only the new span.

Previous: and AI performance data

Codex ID: PS-20260903-ADMIN-AI-PERFORMANCE

Done by Codex.

### 4. Defense paper — Use Case 7, Actor

Page/s: unconfirmed; native paragraph index 118648–118679

#### OLD

> Actor: Operator, Administrator

#### NEW

Actor: Administrator

#### Evidence

The live paper’s Use Case 7 is the AI Performance module. The administrator-only route and the Admin-only help articles establish that this use case no longer has an Operator actor.

#### Proposed comment (same gate as associated replacement)

Comment scope: Span scope — replace the exact contiguous span `Operator, Administrator` with `Administrator`.

Previous: Operator, Administrator

Codex ID: PS-20260903-ADMIN-AI-PERFORMANCE

Done by Codex.

### 5. Defense paper — Use Case 7, Main Flow step 1

Page/s: unconfirmed; native paragraph index 118883–118933

#### OLD

> The user navigates to the "AI Performance" module.

#### NEW

The Administrator navigates to the "AI Performance" module.

#### Evidence

`frontend/src/App.tsx:96` keeps the page at `/admin/ai`; the stale `/user/ai` path redirects to `/user`, and the Operator sidebar has no AI Performance entry.

#### Proposed comment (same gate as associated replacement)

Comment scope: Span scope — replace the exact contiguous span `The user` with `The Administrator`.

Previous: The user

Codex ID: PS-20260903-ADMIN-AI-PERFORMANCE

Done by Codex.

### 6. Defense paper — Use Case 7, Main Flow step 5

Page/s: unconfirmed; native paragraph index 119568–119701

#### OLD

> The user selects "Export" to extract the displayed AI performance summary and its per-camera breakdown in a standardized file format.

#### NEW

The Administrator selects "Export" to extract the displayed AI performance summary and its per-camera breakdown in a standardized file format.

#### Evidence

The synchronous performance export depends on `get_current_admin` (`backend/app/api/routes/analytics.py:750-758`), and the async performance export is likewise rejected for Operators (`backend/app/api/routes/exports.py:72-77`).

#### Proposed comment (same gate as associated replacement)

Comment scope: Span scope — replace the exact contiguous span `The user` with `The Administrator`.

Previous: The user

Codex ID: PS-20260903-ADMIN-AI-PERFORMANCE

Done by Codex.

### 7a. Defense paper — Use Case Diagram, Operator AI-performance deletion

Page/s: unconfirmed; native span `143303–143328` within paragraph `142983–143755`

#### OLD

> , tracking AI performance

#### NEW

`DELETE ONLY — insert nothing.`

#### Evidence

Deleting this exact span removes the Operator’s AI Performance action while preserving the surrounding `detection logs, exporting reports` list. The immediately preceding left character is `s`, the final character of `logs`.

#### Proposed comment (same gate as associated replacement)

Comment scope: Deletion-only span — delete the exact span `, tracking AI performance`; after deletion, highlight/comment the nearest left character `s` in `logs`.

Previous: , tracking AI performance

Codex ID: PS-20260903-ADMIN-AI-PERFORMANCE

Done by Codex.

### 7b. Defense paper — Use Case Diagram, Operator report-export span

Page/s: unconfirmed; native span `143330–143347` within paragraph `142983–143755`

#### OLD

> exporting reports

#### NEW

exporting incident and dashboard reports

#### Evidence

This contiguous Operator capability is narrowed to the incident and dashboard export surfaces that remain available to Operators.

#### Proposed comment (same gate as associated replacement)

Comment scope: Span scope — replace the exact contiguous span `exporting reports` with `exporting incident and dashboard reports`.

Previous: exporting reports

Codex ID: PS-20260903-ADMIN-AI-PERFORMANCE

Done by Codex.

### 7c. Defense paper — Use Case Diagram, Administrator AI-performance insertion

Page/s: unconfirmed; native span `143491–143521` within paragraph `142983–143755`

#### OLD

> such as managing user accounts

#### NEW

such as reviewing AI performance, exporting AI performance reports, managing user accounts

#### Evidence

This contiguous Administrator capability list gains AI Performance review and report export before the existing user-account-management capability. The Admin route/sidebar boundary is implemented in `frontend/src/App.tsx:80-113` and `frontend/src/components/layouts/Sidebar.tsx:88-107`; backend authorization is enforced by the Admin dependency and export-job filters.

#### Proposed comment (same gate as associated replacement)

Comment scope: Span scope — replace the exact contiguous span `such as managing user accounts` with `such as reviewing AI performance, exporting AI performance reports, managing user accounts`; highlight the full new span.

Previous: such as managing user accounts

Codex ID: PS-20260903-ADMIN-AI-PERFORMANCE

Done by Codex.

### 8a. Defense paper — Use Case Diagram, Operator AI-performance deletion

Page/s: unconfirmed; native span `146392–146415` within paragraph `146213–146898`

#### OLD

> , Track AI Performance,

#### NEW

`DELETE ONLY — insert nothing.`

#### Evidence

Deleting this exact span removes `Track AI Performance` and its surrounding list punctuation while preserving the `Analyze Accident Trends and Review Detection Logs` wording. The immediately preceding left character is `s`, the final character of `Trends`.

#### Proposed comment (same gate as associated replacement)

Comment scope: Deletion-only span — delete the exact span `, Track AI Performance,`; after deletion, highlight/comment the nearest left character `s` in `Trends`.

Previous: , Track AI Performance,

Codex ID: PS-20260903-ADMIN-AI-PERFORMANCE

Done by Codex.

### 8b. Defense paper — Use Case Diagram, incident/dashboard information span

Page/s: unconfirmed; native span `146559–146579` within paragraph `146213–146898`

#### OLD

> Relevant information

#### NEW

Incident and dashboard information

#### Evidence

This contiguous span makes the existing Operator-facing `Export Reports` narrative specific to incident and dashboard information, not Administrator-only AI Performance reports.

#### Proposed comment (same gate as associated replacement)

Comment scope: Span scope — replace the exact contiguous span `Relevant information` with `Incident and dashboard information`.

Previous: Relevant information

Codex ID: PS-20260903-ADMIN-AI-PERFORMANCE

Done by Codex.

### 8c. Defense paper — Use Case Diagram, Administrator AI-performance insertion

Page/s: unconfirmed; native span `146622–146651` within paragraph `146213–146898`

#### OLD

> , while large report requests

#### NEW

, while Administrators can use Track AI Performance and export its reports. Large report requests

#### Evidence

This contiguous insertion assigns Track AI Performance and its reports to Administrators while preserving the existing Queue Async Export explanation.

#### Proposed comment (same gate as associated replacement)

Comment scope: Span scope — replace the exact contiguous span `, while large report requests` with `, while Administrators can use Track AI Performance and export its reports. Large report requests`; highlight the full new span.

Previous: , while large report requests

Codex ID: PS-20260903-ADMIN-AI-PERFORMANCE

Done by Codex.

### 9. Defense paper — User Acceptance Testing, Operator participant scope

Page/s: unconfirmed; native paragraph index 240338–240588

#### OLD

> Operators: Personnel responsible for monitoring the command center’s video wall. This group tested real-time HITL alert handling, camera stream configuration, and historical data export functions, as operators are the primary users of these features.

#### NEW

Operators: Personnel responsible for monitoring the command center’s video wall. This group tested real-time HITL alert handling, camera stream configuration, and historical incident and dashboard export functions, as operators are the primary users of these features.

#### Evidence

The live UAT scope now says “HITL alert handling” after P28’s terminology update and still uses a broad “historical data export” description. The implemented Operator export surface includes incident and dashboard reports; AI Performance reports are now Administrator-only.

#### Proposed comment (same gate as associated replacement)

Comment scope: Span scope — replace the exact contiguous span `historical data export` with `historical incident and dashboard export`.

Previous: historical data export

Codex ID: PS-20260903-ADMIN-AI-PERFORMANCE

Done by Codex.

### 10. Defense paper — User Acceptance Testing, Administrator participant scope

Page/s: unconfirmed; native paragraph index 240589–240871

#### OLD

> Administrators: Senior division members responsible for system security and system governance. This group exclusively evaluated restricted modules, including user account management and permission oversight, database backup and restoration, and review and export of the audit trail.

#### NEW

Administrators: Senior division members responsible for system security and system governance. This group exclusively evaluated restricted modules, including AI Performance review and export, user account management and permission oversight, database backup and restoration, and review and export of the audit trail.

#### Evidence

The Admin-only analytics and export routes are the restricted AI Performance surface. `backend/tests/test_analytics.py` covers Admin success and Operator denial; `backend/tests/test_exports.py` covers Admin access and legacy Operator-owned performance-job denial.

#### Proposed comment (same gate as associated replacement)

Comment scope: Span scope — replace the exact contiguous span `including user account management` with `including AI Performance review and export, user account management`.

Previous: including user account management

Codex ID: PS-20260903-ADMIN-AI-PERFORMANCE

Done by Codex.

### 11. Defense paper — User Acceptance Testing, role-based scenario description

Page/s: unconfirmed; native paragraph index 241997–242711

#### OLD

> Operator Scenarios (System Health & AI Diagnostics): Dispatchers evaluated infrastructure dashboards. For system health, evaluators reviewed the live metric tiles for server uptime, inference latency, processing speed, and disk storage utilization, alongside the historical trend charts for CPU utilization, GPU utilization, GPU temperature, and RAM utilization, to validate hardware monitoring capabilities. For AI performance, evaluators interacted with the AI Performance module, reviewing the global KPIs (Total Accidents, Total Dismissed, Avg Precision Score, Avg Accident Confidence, and Avg Dismissed Score) alongside the per-camera breakdown to trace false positive concentrations to specific camera nodes.

#### NEW

Operator Scenarios (System Health): Dispatchers evaluated infrastructure dashboards. Evaluators reviewed the live metric tiles for server uptime, inference latency, processing speed, and disk storage utilization, alongside the historical trend charts for CPU utilization, GPU utilization, GPU temperature, and RAM utilization, to validate hardware monitoring capabilities. Administrator Scenarios (AI Performance & Model Diagnostics): Administrators interacted with the AI Performance module, reviewing the global KPIs (Total Accidents, Total Dismissed, Avg Precision Score, Avg Accident Confidence, and Avg Dismissed Score) alongside the per-camera breakdown to trace false positive concentrations to specific camera nodes.

#### Evidence

The live UAT paragraph makes Dispatchers interact with AI Performance. The Test Execution Tracker’s UAT rows currently do the same in `OP-J01`, `OP-J03`, and `OP-J09`; the approved manifest below moves the performance checks to the Administrator journey and keeps Operator dashboard/incident exports.

#### Proposed comment (same gate as associated replacement)

Comment scope: Logical-paragraph scope — highlight the full revised role-based UAT scenario paragraph.

Previous: Operator Scenarios (System Health & AI Diagnostics): Dispatchers evaluated infrastructure dashboards. For system health, evaluators reviewed the live metric tiles for server uptime, inference latency, processing speed, and disk storage utilization, alongside the historical trend charts for CPU utilization, GPU utilization, GPU temperature, and RAM utilization, to validate hardware monitoring capabilities. For AI performance, evaluators interacted with the AI Performance module, reviewing the global KPIs (Total Accidents, Total Dismissed, Avg Precision Score, Avg Accident Confidence, and Avg Dismissed Score) alongside the per-camera breakdown to trace false positive concentrations to specific camera nodes.

Codex ID: PS-20260903-ADMIN-AI-PERFORMANCE

Done by Codex.

### 12. ADAS_Paper_Audit — new P29 finding entry

Page/s: unconfirmed; audit Doc tab `t.0`; inserted after native paragraph `52332–52741` (before the new paragraph at `52742–53367`), re-read 2026-09-04

#### OLD

No existing audit entry covers the P29 Administrator-only AI Performance boundary. Existing audit items 3.4 and 4.3 discuss the broader Use Case/UI and export architecture, while the `handoff` tab contains the pending logical-DFD replacement.

#### NEW

P29 — AI Performance access boundary. The built system makes AI Performance Administrator-only at the synchronous analytics, synchronous performance export, asynchronous job creation, job listing, status polling, and artifact download surfaces. Update FR-02 and FR-18, Use Case 7, the Use Case Diagram actor and analytics narratives, and the UAT role descriptions so Operators retain Dashboard, Detections, System Health, and incident/dashboard exports while Administrators review and export AI Performance. Coordinate the Context/Level-1 DFD amendment with the pending logical-DFD finding rather than adding a second redraw.

#### Evidence

`backend/app/api/routes/analytics.py:680-759` uses `get_current_admin` for both performance endpoints. `backend/app/api/routes/exports.py:72-168` rejects Operator performance-job creation, excludes performance jobs from Operator lists, and rejects Operator detail/download access even for legacy rows. `frontend/src/App.tsx:80-113` and `frontend/src/components/layouts/Sidebar.tsx:88-107` keep the page at `/admin/ai`; the help frontmatter changes in this branch make both dedicated AI Performance articles Admin-only.

#### Proposed comment (same gate as associated replacement)

Comment scope: Logical-paragraph scope — highlight the full new P29 audit-entry paragraph.

Previous: No existing audit entry covers the P29 Administrator-only AI Performance boundary. Existing audit items 3.4 and 4.3 discuss the broader Use Case/UI and export architecture, while the `handoff` tab contains the pending logical-DFD replacement.

Codex ID: PS-20260903-ADMIN-AI-PERFORMANCE

Done by Codex.

### 13. ADAS_Paper_Audit_Tracker — `🚩 Action Stream`!A82:H82

Page/s: `🚩 Action Stream`!A82:H82

#### OLD

No existing row. Live `userEnteredValue` re-read on 2026-09-04 found rows 1–81 occupied and row 82 fully blank; row 82 retains the native assignee validation in column H.

#### NEW

| Change Type | Section / Chapter                         | Page Number | Required Revision                                            | Notes                                                                                                                                                     | Status      | Assigned to | Reviewed by |
| ----------- | ----------------------------------------- | ----------- | ------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------- | ----------- | ----------- |
| Major       | FR-02, FR-18, UC-7, Use Case Diagram, UAT | unconfirmed | Make AI Performance analytics and exports Administrator-only | Operators retain Dashboard, Detections, System Health, and incident/dashboard exports; coordinate the DFD amendment with the pending logical-DFD finding. | Not started | Daniboy     |             |

#### Evidence

The live audit tracker’s first fully blank row is A82:H82. The approved A82:G82 write was applied and read back; the row’s native Poppins/wrap structure, H-column assignee validation, blank Reviewed by cell, and neighboring rows were preserved. Preflight found no provider-valid native anchor for the approved Sheet comment, so it was not attempted and remains blocked.

#### Proposed comment (same gate as associated replacement)

Comment scope: Logical-paragraph scope — highlight the full proposed A82:H82 tracker-row content.

Previous: No existing row. Live `userEnteredValue` re-read on 2026-09-04 found rows 1–81 occupied and row 82 fully blank; row 82 retains the native assignee validation in column H.

Codex ID: PS-20260903-ADMIN-AI-PERFORMANCE

Done by Codex.

## Coordination with pending logical-DFD finding

The live paper’s Context DFD paragraph currently says the Operator receives AI performance metrics. The pending local finding [`2026-08-23-logical-dfd-overhaul.md`](2026-08-23-logical-dfd-overhaul.md) already owns the Context/Level-1 DFD replacement and redraw. Do not create a second DFD replacement block or redraw here. When that finding is applied, amend its Administrator exchange to include AI-performance queries/reports alongside the unique user-management, audit, and maintenance exchanges, and ensure the Operator exchange does not list AI Performance. The same amendment should be reflected in the live audit Doc `handoff` tab.

## 2026-09-04 sweep notes

The fresh live-paper sweep found three other role-adjacent AI-performance matches that are not additional P29 replacement sites. The Definition of Terms precision paragraph (`31238–31514`) describes operator-confirmed and dismissed labels as metric inputs, not module access. The system-boundary paragraph (`79972–80490`) says the application is available only to authenticated, authorized users; it does not assign AI Performance to Operators and remains accurate. The Context DFD paragraph (`148750–149552`) does assign AI-performance metrics to the Operator, but it is explicitly owned by the pending logical-DFD finding above. Headings, metric definitions, the generic Use Case 7 login/postcondition wording, and the FR-16 content are either role-neutral or covered by blocks 4–6, 7a–8c, and 9–11; no new P29 replacement block is needed.

## Test Execution Tracker manifest (prepared; no live write)

The live `ADAS Test Execution Tracker` was re-read on 2026-09-04 immediately before the approved writes. The manifest below records the exact targets and values; only listed content cells were changed. Native row structure and validation were preserved, manual/evidence columns not listed were retained, and `#D9EAD3` was applied only to changed cells.

### 14. `Unit Testing`!A35:J35 — refresh with Administrator evidence

#### OLD

`[TC-UNIT-034, FR-16 AI Performance Monitoring, Performance analytics provides global and per-camera metrics., uv run pytest backend/tests/test_analytics.py::TestPerformanceAnalytics::test_performance_returns_global_and_per_camera_metrics, The metrics response contains correctly aggregated global and per-camera data., 2026-08-29, Pass, Pass — full backend fast suite: 939 passed, 2 skipped, 12 deselected., https://docs.google.com/document/d/1J2DsvyJLgxEw4B3EK6seyZO4AACk0p_FQkCxFmNOfnY/edit, No defect.]`

#### NEW

`[TC-UNIT-034, FR-16 AI Performance Monitoring (Administrator-only), Administrator performance analytics provides global and per-camera metrics., uv run pytest backend/tests/test_analytics.py::TestPerformanceAnalytics::test_performance_returns_global_and_per_camera_metrics, The Admin metrics response contains correctly aggregated global and per-camera data., 2026-09-03, Pass, Pass — P29 targeted backend suite: 227 passed; Admin performance success and Operator denial included., https://docs.google.com/document/d/1J2DsvyJLgxEw4B3EK6seyZO4AACk0p_FQkCxFmNOfnY/edit, Existing evidence refreshed for the Administrator-only boundary.]`

#### Evidence

Native row readback shows G35 has the existing `ONE_OF_LIST` validation (`Not Executed`, `Pass`, `Fail`, `Blocked`, `Retest Required`) and all cells use the Unit Testing row structure. Preserve I35’s evidence link and write only changed cells.

#### Proposed comment (same gate as associated replacement)

Comment scope: Logical-paragraph scope — highlight the full changed Unit Testing row A35:J35.

Previous: [TC-UNIT-034, FR-16 AI Performance Monitoring, Performance analytics provides global and per-camera metrics., uv run pytest backend/tests/test_analytics.py::TestPerformanceAnalytics::test_performance_returns_global_and_per_camera_metrics, The metrics response contains correctly aggregated global and per-camera data., 2026-08-29, Pass, Pass — full backend fast suite: 939 passed, 2 skipped, 12 deselected., https://docs.google.com/document/d/1J2DsvyJLgxEw4B3EK6seyZO4AACk0p_FQkCxFmNOfnY/edit, No defect.]

Codex ID: PS-20260903-ADMIN-AI-PERFORMANCE

Done by Codex.

### 15. `Unit Testing`!A52:J52 — add `TC-UNIT-051`

#### OLD

No existing row. `userEnteredValue` re-read on 2026-09-04 found A52:F52 and H52:J52 blank; G52 already has the native result validation.

#### NEW

`[TC-UNIT-051, FR-02 Role-Based Access Control (RBAC), Synchronous AI Performance analytics and export are available to Administrators and denied to Operators., uv run pytest backend/tests/test_analytics.py::test_operator_cannot_access_admin_only_performance_endpoints, Admin success and Operator requests both receive the role-appropriate result before performance work runs., 2026-09-03, Pass, Pass — P29 targeted backend suite: both synchronous performance endpoints passed Admin/Operator coverage; 227 tests passed overall., https://docs.google.com/document/d/1J2DsvyJLgxEw4B3EK6seyZO4AACk0p_FQkCxFmNOfnY/edit, No defect.]`

#### Evidence

Rows 51 and earlier are occupied; A52:J52 is the first fully blank Unit Testing row verified by `userEnteredValue`. Keep the existing G52 result validation and copy the native row structure if the row is materialized.

#### Proposed comment (same gate as associated replacement)

Comment scope: Logical-paragraph scope — highlight the full proposed Unit Testing row A52:J52.

Previous: No existing row.

Codex ID: PS-20260903-ADMIN-AI-PERFORMANCE

Done by Codex.

### 16. `Unit Testing`!A53:J53 — add `TC-UNIT-052`

#### OLD

No existing row. `userEnteredValue` re-read on 2026-09-04 found A53:F53 and H53:J53 blank; G53 already has the native result validation.

#### NEW

`[TC-UNIT-052, FR-19 Help Center, Dedicated AI Performance guidance is Admin-only and shared Operator guidance contains no restricted dead link., uv run pytest backend/tests/test_help.py::TestRoleFilter::test_real_ai_performance_guidance_is_admin_only_and_shared_articles_have_no_dead_links, Operator list/detail/search hide the restricted articles while Administrator search retains them and shared articles remain readable., 2026-09-03, Pass, Pass — P29 targeted backend suite: help role/list/search/detail coverage included., https://docs.google.com/document/d/1J2DsvyJLgxEw4B3EK6seyZO4AACk0p_FQkCxFmNOfnY/edit, No defect.]`

#### Evidence

Rows 52 and earlier are occupied or reserved by this manifest; A53:J53 was the next fully blank Unit Testing row at read time. Keep G53’s existing result validation and copy native row structure.

#### Proposed comment (same gate as associated replacement)

Comment scope: Logical-paragraph scope — highlight the full proposed Unit Testing row A53:J53.

Previous: No existing row.

Codex ID: PS-20260903-ADMIN-AI-PERFORMANCE

Done by Codex.

### 17. `Integration Testing`!A13:J13 — add `TC-INT-012`

#### OLD

No existing row. `userEnteredValue` re-read on 2026-09-04 found rows 1–12 occupied and A13:J13 blank; G13 already has the native result validation.

#### NEW

`[TC-INT-012, FR-02; FR-16; FR-18 Role-Based Access Control, The Administrator-only AI Performance boundary holds across synchronous analytics and asynchronous create/list/detail/download APIs., uv run pytest backend/tests/test_analytics.py::test_operator_cannot_access_admin_only_performance_endpoints backend/tests/test_exports.py::TestPerformanceReportJobIsAdminOnly, Administrators can use the performance surfaces and legacy Operator-owned performance jobs are unavailable to Operators; Dashboard and incident export authorization remains unchanged., 2026-09-03, Pass, Pass — P29 targeted backend suite: 227 passed, including sync and legacy async boundary coverage., https://docs.google.com/document/d/1J2DsvyJLgxEw4B3EK6seyZO4AACk0p_FQkCxFmNOfnY/edit, No defect.]`

#### Evidence

Rows 1–12 are occupied and A13:J13 is the first fully blank Integration Testing row. Preserve the native row structure and G13 result validation; do not overwrite neighboring rows.

#### Proposed comment (same gate as associated replacement)

Comment scope: Logical-paragraph scope — highlight the full proposed Integration Testing row A13:J13.

Previous: No existing row.

Codex ID: PS-20260903-ADMIN-AI-PERFORMANCE

Done by Codex.

### 18. `UAT Journeys`!A2:I2 — update OP-J01

#### OLD

Changed cells from live row 2: `G2 = 1. Secure access opens /user. 2. Cameras, Detections, System Health, AI Performance, Profile, and Help are available. 3. Users, Audit Log, and Maintenance are unavailable. 4. No new Unverified alert appears from the silent baseline. 5. The pre-seeded Ongoing incident is visible through the bottom-right tray without blocking monitoring.`

#### NEW

Changed cells: `G2 = 1. Secure access opens /user. 2. Cameras, Detections, System Health, Profile, and Help are available; AI Performance is Administrator-only. 3. Users, Audit Log, Maintenance, and AI Performance are unavailable. 4. No new Unverified alert appears from the silent baseline. 5. The pre-seeded Ongoing incident is visible through the bottom-right tray without blocking monitoring.`

#### Evidence

The Operator journey currently promises AI Performance availability. Preserve A2:F2, H2:I2, row formatting, and any validation; change only G2.

#### Proposed comment (same gate as associated replacement)

Comment scope: Logical-paragraph scope — highlight the full changed UAT Journeys G2 acceptance cell.

Previous: 1. Secure access opens /user. 2. Cameras, Detections, System Health, AI Performance, Profile, and Help are available. 3. Users, Audit Log, and Maintenance are unavailable. 4. No new Unverified alert appears from the silent baseline. 5. The pre-seeded Ongoing incident is visible through the bottom-right tray without blocking monitoring.

Codex ID: PS-20260903-ADMIN-AI-PERFORMANCE

Done by Codex.

### 19. `UAT Journeys`!A4:I4 — update OP-J03

#### OLD

Changed cells from live row 4: `F4 = 1. Review Cameras, System Health, and AI Performance. 2. Identify the Disabled test camera and explain the visible condition. 3. State whether monitoring may continue or needs escalation. 4. Use the camera enable control to restore only the assigned test camera. 5. Recheck the affected and unaffected cameras.`; `G4 = 1. The participant identifies the deliberately Disabled camera from system information. 2. The proceed/escalate judgment is operationally reasonable. 3. Only the assigned camera is enabled. 4. Unrelated cameras retain their states. 5. The assigned camera returns to the expected enabled/ready presentation without facilitator navigation.`; `H4 = FR-14; FR-15; FR-16`.

#### NEW

Changed cells: `F4 = 1. Review Cameras and System Health. 2. Identify the Disabled test camera and explain the visible condition. 3. State whether monitoring may continue or needs escalation. 4. Use the camera enable control to restore only the assigned test camera. 5. Recheck the affected and unaffected cameras.`; `G4 = 1. The participant identifies the deliberately Disabled camera from system information. 2. The proceed/escalate judgment is operationally reasonable. 3. Only the assigned camera is enabled. 4. Unrelated cameras retain their states. 5. The assigned camera returns to the expected enabled/ready presentation without facilitator navigation.`; `H4 = FR-14; FR-15`.

#### Evidence

OP-J03 is a system-readiness journey and should not require an Operator to inspect AI Performance. Preserve A4:E4, I4, row formatting, and any validation; change only F4:H4.

#### Proposed comment (same gate as associated replacement)

Comment scope: Logical-paragraph scope — highlight the full changed UAT Journeys F4:H4 field content.

Previous: F4 = 1. Review Cameras, System Health, and AI Performance. 2. Identify the Disabled test camera and explain the visible condition. 3. State whether monitoring may continue or needs escalation. 4. Use the camera enable control to restore only the assigned test camera. 5. Recheck the affected and unaffected cameras.; G4 = 1. The participant identifies the deliberately Disabled camera from system information. 2. The proceed/escalate judgment is operationally reasonable. 3. Only the assigned camera is enabled. 4. Unrelated cameras retain their states. 5. The assigned camera returns to the expected enabled/ready presentation without facilitator navigation.; H4 = FR-14; FR-15; FR-16

Codex ID: PS-20260903-ADMIN-AI-PERFORMANCE

Done by Codex.

### 20. `UAT Journeys`!A10:I10 — update OP-J09 while preserving P28’s merged terminology

#### OLD

Changed cells from live row 10: `D10 = Facilitator\n1. Provide a seeded date range, status, camera/location question, and Help Center topic.\n2. Assign export coverage: OP-01 Detections CSV; OP-02 Detections PDF; OP-03 Dashboard CSV; OP-04 Dashboard PDF; OP-05 AI Performance CSV; OP-06 AI Performance PDF.\n3. Direct the participant to use the visible active filters for the export.\n\nSystem Handler\n1. Ensure matching detection and analytics records exist.\n2. Keep the OP-J08 incident Ongoing for handover.\n3. Verify the downloaded artifact: uv run python backend/scripts/verify_uat_export.py \"<downloaded-file>\"\n4. Stop/reset publishers only after evidence is retained.\n\nLogger\n1. Verify the export against the visible filtered view.`; `G10 = 1. The correct records and operational pattern are found. 2. The assigned CSV/PDF export opens and matches the active filtered view. 3. Across the six Operators, Detections, Dashboard, and AI Performance are each covered in both CSV and PDF. 4. The role-appropriate Help Center guidance is found. 5. The handover accurately identifies the active Ongoing incident, terminal records, and manual responsibilities. 6. Evidence references are ready for the Execution Log.`. F10 and H10 are preserved from the existing tracker row.

#### NEW

Changed cells: `D10 = Facilitator\n1. Provide a seeded date range, status, camera/location question, and Help Center topic.\n2. Assign Operator export coverage: OP-01 Detections CSV; OP-02 Detections PDF; OP-03 Dashboard CSV; OP-04 Dashboard PDF. Assign Administrator export coverage separately: AD-J02 AI Performance CSV and AI Performance PDF.\n3. Direct the participant to use the visible active filters for the assigned export.\n\nSystem Handler\n1. Ensure matching detection and analytics records exist.\n2. Keep the OP-J08 incident Ongoing for handover.\n3. Verify each downloaded artifact: uv run python backend/scripts/verify_uat_export.py \"<downloaded-file>\"\n4. Stop/reset publishers only after evidence is retained.\n\nLogger\n1. Verify each export against the visible filtered view and record the role used.`; `G10 = 1. The correct records and operational pattern are found. 2. The assigned Operator CSV/PDF export opens and matches the active filtered view. 3. Across the Operator participants, Detections and Dashboard are each covered in both CSV and PDF; Administrator participants cover AI Performance in both CSV and PDF in AD-J02. 4. The role-appropriate Help Center guidance is found. 5. The handover accurately identifies the active Ongoing incident, terminal records, and manual responsibilities. 6. Evidence references are ready for the Execution Log.`. F10 and H10 are preserved from the existing tracker row.

#### Evidence

This is the shared P28/P29 row. P28’s merged `Cleared` terminology is already present in live F10; preserve it while applying the P29 role-boundary changes. Preserve A10:C10, F10, H10, and I10, row formatting, and any validation; write only D10 and G10.

#### Proposed comment (same gate as associated replacement)

Comment scope: Cell scope — comment only on the changed UAT Journeys D10 field; F10 and H10 are preserved and must not be commented.

The P29 write changes D10 and G10 only. The second comment below targets G10 separately so the preserved F10 and H10 cells are not included.

Previous (D10 only): D10 = Facilitator\n1. Provide a seeded date range, status, camera/location question, and Help Center topic.\n2. Assign export coverage: OP-01 Detections CSV; OP-02 Detections PDF; OP-03 Dashboard CSV; OP-04 Dashboard PDF; OP-05 AI Performance CSV; OP-06 AI Performance PDF.\n3. Direct the participant to use the visible active filters for the export.\n\nSystem Handler\n1. Ensure matching detection and analytics records exist.\n2. Keep the OP-J08 incident Ongoing for handover.\n3. Verify the downloaded artifact: uv run python backend/scripts/verify_uat_export.py \"<downloaded-file>\"\n4. Stop/reset publishers only after evidence is retained.\n\nLogger\n1. Verify the export against the visible filtered view.

Codex ID: PS-20260903-ADMIN-AI-PERFORMANCE

Done by Codex.

#### Proposed comment (same gate as associated replacement)

Comment scope: Cell scope — comment only on the changed UAT Journeys G10 field; F10 and H10 are preserved and must not be commented.

Previous: G10 = 1. The correct records and operational pattern are found. 2. The assigned CSV/PDF export opens and matches the active filtered view. 3. Across the six Operators, Detections, Dashboard, and AI Performance are each covered in both CSV and PDF. 4. The role-appropriate Help Center guidance is found. 5. The handover accurately identifies the active Ongoing incident, terminal records, and manual responsibilities. 6. Evidence references are ready for the Execution Log.

Codex ID: PS-20260903-ADMIN-AI-PERFORMANCE

Done by Codex.

### 21. `UAT Journeys`!A12:I12 — update AD-J02

#### OLD

Changed cells from live row 12: `E12 = Assess system readiness before maintenance`; `F12 = 1. Review Cameras, System Health, and AI Performance. 2. Identify the camera, hardware, or AI condition. 3. Explain its operational impact. 4. State whether maintenance may proceed or must be escalated. 5. After the facilitator reset, verify that the healthy baseline is restored before continuing.`; `G12 = 1. The intended condition is correctly identified. 2. The explanation matches the visible evidence. 3. The proceed/escalate decision is reasonable. 4. No unintended participant configuration change occurs. 5. The healthy baseline is explicitly restored and verified before account management and recovery work.`; `H12 = FR-14; FR-15; FR-16`.

#### NEW

Changed cells: `E12 = Assess system readiness and Administrator-only AI Performance before maintenance`; `F12 = 1. Review Cameras and System Health. 2. Confirm that AI Performance is located in Administration after Maintenance, then open it. 3. Review the AI Performance global and per-camera metrics and identify the camera, hardware, or AI condition. 4. Export the AI Performance report as CSV and PDF using the active filters. 5. Explain the operational impact and state whether maintenance may proceed or must be escalated. 6. After the facilitator reset, verify that the healthy baseline is restored before continuing.`; `G12 = 1. The intended condition is correctly identified. 2. AI Performance appears after Maintenance in the Administrator navigation and its global/per-camera metrics are understandable. 3. Both CSV and PDF performance exports open and match the active filters. 4. The explanation matches the visible evidence. 5. The proceed/escalate decision is reasonable. 6. No unintended participant configuration change occurs and the healthy baseline is explicitly restored before account management and recovery work.`; `H12 = FR-14; FR-15; FR-16; FR-18`.

#### Evidence

AD-J02 is the first Administrator readiness stage and the requested final location for AI Performance UAT evidence. Preserve A12:D12 and I12, row formatting, and any validation; write only E12:H12.

#### Proposed comment (same gate as associated replacement)

Comment scope: Logical-paragraph scope — highlight the full changed UAT Journeys E12:H12 field content.

Previous: E12 = Assess system readiness before maintenance; F12 = 1. Review Cameras, System Health, and AI Performance. 2. Identify the camera, hardware, or AI condition. 3. Explain its operational impact. 4. State whether maintenance may proceed or must be escalated. 5. After the facilitator reset, verify that the healthy baseline is restored before continuing.; G12 = 1. The intended condition is correctly identified. 2. The explanation matches the visible evidence. 3. The proceed/escalate decision is reasonable. 4. No unintended participant configuration change occurs. 5. The healthy baseline is explicitly restored and verified before account management and recovery work.; H12 = FR-14; FR-15; FR-16

Codex ID: PS-20260903-ADMIN-AI-PERFORMANCE

Done by Codex.

### 22. `UAT Traceability`!A17:G17 — map FR-16 only to AD-J02

#### OLD

`[Functional Requirement, FR-16, AI Performance, OP-J03; AD-J02, Execution Log; linked evidence, Mapped, All user-facing FRs have a role-appropriate journey stage.]`

#### NEW

`[Functional Requirement, FR-16, AI Performance, AD-J02, Execution Log; linked evidence, Mapped, AI Performance is Administrator-only; AD-J02 covers navigation order, metrics, and CSV/PDF exports.]`

#### Evidence

Live `UAT Traceability` row 17 currently maps FR-16 to both OP-J03 and AD-J02. The Operator row loses the AI Performance claim; Administrator AD-J02 becomes the sole role-appropriate journey. Preserve native row formatting and write only changed cells.

#### Proposed comment (same gate as associated replacement)

Comment scope: Logical-paragraph scope — highlight the full changed UAT Traceability row A17:G17.

Previous: [Functional Requirement, FR-16, AI Performance, OP-J03; AD-J02, Execution Log; linked evidence, Mapped, All user-facing FRs have a role-appropriate journey stage.]

Codex ID: PS-20260903-ADMIN-AI-PERFORMANCE

Done by Codex.

## Approval / sync ledger

Package ID: `PS-20260903-ADMIN-AI-PERFORMANCE`

| Target                        | Approved scope                               | Applied/read back                                                                   | Skipped/pending                                                         | Blocked                                                                                                                               |
| ----------------------------- | -------------------------------------------- | ----------------------------------------------------------------------------------- | ----------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| Defense paper                 | blocks 1a–1c, 2a–2b, 3–6, 7a–7c, 8a–8c, 9–11 | paper text and 18 native comments applied/read back                                 | DFD coordination note pending with `2026-08-23-logical-dfd-overhaul.md` | —                                                                                                                                     |
| ADAS_Paper_Audit plus tracker | blocks 12–13                                 | audit paragraph/comment and A82:G82 row applied/read back; H82 validation preserved | —                                                                       | preflight found no provider-valid native anchor for the approved A82:H82 Sheet comment; not attempted and retained locally as blocked |
| ADAS Test Execution Tracker   | blocks 14–22                                 | row/cell writes applied/read back                                                   | —                                                                       | approved Sheet comments returned no provider-valid native anchors; unanchored attempts were resolved and retained locally as blocked  |
| Standalone comments           | none; no P29 figure-comment block exists     | —                                                                                   | —                                                                       | —                                                                                                                                     |

Approved Drive writes were applied and read back for the paper, audit Doc, audit tracker row, and Test Execution Tracker rows. The 18 paper comments and one audit-Doc comment have provider-valid native anchors. The audit-tracker Sheet comment was not attempted because preflight found no native anchor; Test Execution Tracker comment attempts returned anchor: null, so they were resolved rather than left unanchored. The proposed Sheet comments remain in this finding as blocked. Rendered-paper page mapping remains `unconfirmed` because the connected export returned a user-scoped file reference that was not available to the local PDF renderer in this session.
