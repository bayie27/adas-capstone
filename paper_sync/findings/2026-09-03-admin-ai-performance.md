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

### 1. Defense paper — Scope and Delimitations, study scope paragraph

Page/s: unconfirmed; native paragraph index 16341–17755

#### OLD

> This study covers the development and evaluation of a proof-of-concept, edge-based real-time road-collision detection and alert system intended to support internal CDRRMO operations in Lipa City, Batangas. Conducted over three semesters spanning the 2025–2026 and 2026–2027 academic years, the project implements a custom-trained YOLO-based model using publicly available annotated datasets and evaluates its event-level performance separately using held-out Lipa CDRRMO CCTV footage. The system processes configured RTSP CCTV feeds, with MediaMTX used only to simulate VMS streams during development and testing. It integrates a Python AI engine, FastAPI backend, local SQLite database, and React dashboard on researcher-controlled edge/test hardware. Operators and Administrators can review AI-generated alerts through a Human-in-the-Loop workflow, manage camera configurations, monitor analytics, system health, and AI-performance telemetry, and review historical detections. Role-Based Access Control is enforced: Administrators inherit operational privileges and additionally manage user accounts, review audit logs, and administer backup and restoration functions. The evaluation focuses on model detection performance, system timing behaviour, and operator workflow efficiency within the documented demonstration environment; it does not claim production-scale deployment or unmeasured operational outcomes.

#### NEW

This study covers the development and evaluation of a proof-of-concept, edge-based real-time road-collision detection and alert system intended to support internal CDRRMO operations in Lipa City, Batangas. Conducted over three semesters spanning the 2025–2026 and 2026–2027 academic years, the project implements a custom-trained YOLO-based model using publicly available annotated datasets and evaluates its event-level performance separately using held-out Lipa CDRRMO CCTV footage. The system processes configured RTSP CCTV feeds, with MediaMTX used only to simulate VMS streams during development and testing. It integrates a Python AI engine, FastAPI backend, local SQLite database, and React dashboard on researcher-controlled edge/test hardware. Operators and Administrators can review AI-generated alerts through a Human-in-the-Loop workflow, manage camera configurations, monitor dashboard analytics and system health, and review historical detections. Administrators can additionally review AI-performance metrics and reports. Role-Based Access Control is enforced: Administrators inherit operational privileges and additionally manage user accounts, review audit logs, administer backup and restoration functions, and review and export AI-performance reports. The evaluation focuses on model detection performance, system timing behaviour, and operator workflow efficiency within the documented demonstration environment; it does not claim production-scale deployment or unmeasured operational outcomes.

#### Evidence

Live paper paragraph index 143 says Operators and Administrators monitor AI-performance telemetry without distinguishing the Administrator-only module. The implemented boundary is enforced by `backend/app/api/routes/analytics.py:680-759`, where both performance routes depend on `get_current_admin`, and by `backend/app/api/routes/exports.py:72-168`, which gates performance job creation, listing, polling, and download.

#### Proposed comment (same gate as associated replacement)

Comment scope: Logical-paragraph scope — highlight the full revised Scope and Delimitations paragraph.

Previous: This study covers the development and evaluation of a proof-of-concept, edge-based real-time road-collision detection and alert system intended to support internal CDRRMO operations in Lipa City, Batangas. Conducted over three semesters spanning the 2025–2026 and 2026–2027 academic years, the project implements a custom-trained YOLO-based model using publicly available annotated datasets and evaluates its event-level performance separately using held-out Lipa CDRRMO CCTV footage. The system processes configured RTSP CCTV feeds, with MediaMTX used only to simulate VMS streams during development and testing. It integrates a Python AI engine, FastAPI backend, local SQLite database, and React dashboard on researcher-controlled edge/test hardware. Operators and Administrators can review AI-generated alerts through a Human-in-the-Loop workflow, manage camera configurations, monitor analytics, system health, and AI-performance telemetry, and review historical detections. Role-Based Access Control is enforced: Administrators inherit operational privileges and additionally manage user accounts, review audit logs, and administer backup and restoration functions. The evaluation focuses on model detection performance, system timing behaviour, and operator workflow efficiency within the documented demonstration environment; it does not claim production-scale deployment or unmeasured operational outcomes.

Codex ID: PS-20260903-ADMIN-AI-PERFORMANCE

Done by Codex.

### 2. Defense paper — Table 2, FR-02 Role-Based Access Control

Page/s: unconfirmed; native paragraph index 92713–93049

#### OLD

> The system shall enforce two distinct access levels. Operators shall have operational access to the analytics dashboard, active camera status lists and configurations, detection logs, and system health and AI performance metrics. Administrators shall inherit all Operator privileges and have exclusive access to User Account Management.

#### NEW

The system shall enforce two distinct access levels. Operators shall have operational access to the analytics dashboard, active camera status lists and configurations, detection logs, and system health metrics. Administrators shall inherit all Operator privileges and have exclusive access to AI performance monitoring, AI performance exports, and User Account Management.

#### Evidence

Live paper paragraph index 412 assigns AI performance metrics to Operators. `GET /api/analytics/performance` and `GET /api/analytics/export/performance` require `get_current_admin`; the frontend renders the page only under `/admin/ai` and removes it from the Operator route/sidebar (`frontend/src/App.tsx:80-113`, `frontend/src/components/layouts/Sidebar.tsx:88-107`).

#### Proposed comment (same gate as associated replacement)

Comment scope: Logical-paragraph scope — highlight the full revised FR-02 role-based-access paragraph.

Previous: The system shall enforce two distinct access levels. Operators shall have operational access to the analytics dashboard, active camera status lists and configurations, detection logs, and system health and AI performance metrics. Administrators shall inherit all Operator privileges and have exclusive access to User Account Management.

Codex ID: PS-20260903-ADMIN-AI-PERFORMANCE

Done by Codex.

### 3. Defense paper — Table 2, FR-18 Report Generation and Data Export

Page/s: unconfirmed; native paragraph index 98049–98288

#### OLD

> The system shall allow users to export incident records, summary figures, and AI performance data as files in common formats such as CSV and PDF, for sharing with other agencies, for official record-keeping, and for improving the AI model.

#### NEW

The system shall allow users to export incident records and summary figures, and shall allow Administrators to export AI performance data as files in common formats such as CSV and PDF, for sharing with other agencies, for official record-keeping, and for improving the AI model.

#### Evidence

The live paper’s FR-18 row uses “users” for all three export families. Operator dashboard and incident exports remain available through `backend/app/api/routes/analytics.py:341-497` and the existing incident export route; only performance exports are Admin-only. The async route applies the same boundary to `report_type="performance"`.

#### Proposed comment (same gate as associated replacement)

Comment scope: Logical-paragraph scope — highlight the full revised FR-18 export paragraph.

Previous: The system shall allow users to export incident records, summary figures, and AI performance data as files in common formats such as CSV and PDF, for sharing with other agencies, for official record-keeping, and for improving the AI model.

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

### 7. Defense paper — Use Case Diagram, actor narrative

Page/s: unconfirmed; native paragraph index 142983–143755

#### OLD

> The system has three primary actors. The Operator, also referred to as the Dispatcher, is responsible for day-to-day command center operations, including monitoring and verifying collision alerts, managing cameras, configuring alarm settings, monitoring system health, analyzing accident trends, reviewing detection logs, tracking AI performance, exporting reports, and accessing the Help Center. The Administrator inherits the capabilities of the Operator and additionally performs administrative functions such as managing user accounts, triggering database backups, restoring the system from backups, and reviewing and exporting audit records. The CCTV/VMS acts as the external system responsible for continuously providing camera feeds to ADAS for collision detection.

#### NEW

The system has three primary actors. The Operator, also referred to as the Dispatcher, is responsible for day-to-day command center operations, including monitoring and verifying collision alerts, managing cameras, configuring alarm settings, monitoring system health, analyzing accident trends, reviewing detection logs, exporting incident and dashboard reports, and accessing the Help Center. The Administrator inherits the capabilities of the Operator and additionally performs administrative functions such as reviewing AI performance, exporting AI performance reports, managing user accounts, triggering database backups, restoring the system from backups, and reviewing and exporting audit records. The CCTV/VMS acts as the external system responsible for continuously providing camera feeds to ADAS for collision detection.

#### Evidence

The current actor paragraph explicitly gives the Operator “tracking AI performance” and unrestricted “exporting reports.” The Admin route/sidebar boundary is implemented in `frontend/src/App.tsx:80-113` and `frontend/src/components/layouts/Sidebar.tsx:88-107`; backend authorization is enforced by the Admin dependency and export-job filters.

#### Proposed comment (same gate as associated replacement)

Comment scope: Logical-paragraph scope — highlight the full revised Use Case Diagram actor narrative.

Previous: The system has three primary actors. The Operator, also referred to as the Dispatcher, is responsible for day-to-day command center operations, including monitoring and verifying collision alerts, managing cameras, configuring alarm settings, monitoring system health, analyzing accident trends, reviewing detection logs, tracking AI performance, exporting reports, and accessing the Help Center. The Administrator inherits the capabilities of the Operator and additionally performs administrative functions such as managing user accounts, triggering database backups, restoring the system from backups, and reviewing and exporting audit records. The CCTV/VMS acts as the external system responsible for continuously providing camera feeds to ADAS for collision detection.

Codex ID: PS-20260903-ADMIN-AI-PERFORMANCE

Done by Codex.

### 8. Defense paper — Use Case Diagram, System Monitoring and Analytics narrative

Page/s: unconfirmed; native paragraph index 146213–146898

#### OLD

> System Monitoring and Analytics. The Operator can Monitor System Health to observe the operational condition of the system and its connected resources. The Analyze Accident Trends, Track AI Performance, and Review Detection Logs functions provide analytical and historical information that supports operational assessment and system improvement. Relevant information can be consolidated through Export Reports, while large report requests may be handled through Queue Async Export to prevent lengthy export operations from disrupting normal system activities. These functions allow the command center to evaluate incident patterns, detection performance, and system behavior over time.

#### NEW

System Monitoring and Analytics. The Operator can Monitor System Health to observe the operational condition of the system and its connected resources. The Analyze Accident Trends and Review Detection Logs functions provide analytical and historical information that supports operational assessment and system improvement. Incident and dashboard information can be consolidated through Export Reports, while Administrators can use Track AI Performance and export its reports. Large report requests may be handled through Queue Async Export to prevent lengthy export operations from disrupting normal system activities. These functions allow the command center to evaluate incident patterns, detection performance, and system behavior over time.

#### Evidence

The live narrative assigns `Track AI Performance` and `Export Reports` to the Operator. Dashboard and incident exports remain Operator-accessible; performance analytics and performance export routes are Admin-only, and Operators cannot list, poll, or download performance jobs.

#### Proposed comment (same gate as associated replacement)

Comment scope: Logical-paragraph scope — highlight the full revised System Monitoring and Analytics narrative.

Previous: System Monitoring and Analytics. The Operator can Monitor System Health to observe the operational condition of the system and its connected resources. The Analyze Accident Trends, Track AI Performance, and Review Detection Logs functions provide analytical and historical information that supports operational assessment and system improvement. Relevant information can be consolidated through Export Reports, while large report requests may be handled through Queue Async Export to prevent lengthy export operations from disrupting normal system activities. These functions allow the command center to evaluate incident patterns, detection performance, and system behavior over time.

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

The live UAT paragraph makes Dispatchers interact with AI Performance. The Test Execution Tracker’s UAT rows currently do the same in `OP-J01`, `OP-J03`, and `OP-J09`; the write-free manifest below moves the performance checks to the Administrator journey and keeps Operator dashboard/incident exports.

#### Proposed comment (same gate as associated replacement)

Comment scope: Logical-paragraph scope — highlight the full revised role-based UAT scenario paragraph.

Previous: Operator Scenarios (System Health & AI Diagnostics): Dispatchers evaluated infrastructure dashboards. For system health, evaluators reviewed the live metric tiles for server uptime, inference latency, processing speed, and disk storage utilization, alongside the historical trend charts for CPU utilization, GPU utilization, GPU temperature, and RAM utilization, to validate hardware monitoring capabilities. For AI performance, evaluators interacted with the AI Performance module, reviewing the global KPIs (Total Accidents, Total Dismissed, Avg Precision Score, Avg Accident Confidence, and Avg Dismissed Score) alongside the per-camera breakdown to trace false positive concentrations to specific camera nodes.

Codex ID: PS-20260903-ADMIN-AI-PERFORMANCE

Done by Codex.

### 12. ADAS_Paper_Audit — new P29 finding entry

Page/s: unconfirmed; live audit Doc `08.13 pass 1` tab, re-read 2026-09-04

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

The live audit tracker’s first fully blank row is A82:H82. Preserve the row’s native Poppins/wrap structure, the H-column assignee validation, the blank Reviewed by cell, and all neighboring rows. No live Sheet write was made.

#### Proposed comment (same gate as associated replacement)

Comment scope: Logical-paragraph scope — highlight the full proposed A82:H82 tracker-row content.

Previous: No existing row. Live `userEnteredValue` re-read on 2026-09-04 found rows 1–81 occupied and row 82 fully blank; row 82 retains the native assignee validation in column H.

Codex ID: PS-20260903-ADMIN-AI-PERFORMANCE

Done by Codex.

## Coordination with pending logical-DFD finding

The live paper’s Context DFD paragraph currently says the Operator receives AI performance metrics. The pending local finding [`2026-08-23-logical-dfd-overhaul.md`](2026-08-23-logical-dfd-overhaul.md) already owns the Context/Level-1 DFD replacement and redraw. Do not create a second DFD replacement block or redraw here. When that finding is applied, amend its Administrator exchange to include AI-performance queries/reports alongside the unique user-management, audit, and maintenance exchanges, and ensure the Operator exchange does not list AI Performance. The same amendment should be reflected in the live audit Doc `handoff` tab.

## 2026-09-04 sweep notes

The fresh live-paper sweep found three other role-adjacent AI-performance matches that are not additional P29 replacement sites. The Definition of Terms precision paragraph (`31238–31514`) describes operator-confirmed and dismissed labels as metric inputs, not module access. The system-boundary paragraph (`79972–80490`) says the application is available only to authenticated, authorized users; it does not assign AI Performance to Operators and remains accurate. The Context DFD paragraph (`148750–149552`) does assign AI-performance metrics to the Operator, but it is explicitly owned by the pending logical-DFD finding above. Headings, metric definitions, the generic Use Case 7 login/postcondition wording, and the FR-16 content are either role-neutral or covered by blocks 4–11; no new P29 replacement block is needed.

## Test Execution Tracker manifest (prepared; no live write)

The live `ADAS Test Execution Tracker` was re-read on 2026-09-04. The manifest below is exact and intentionally write-free. Each target must be re-read by `userEnteredValue` immediately before any future write; only listed content cells should be changed. Copy native row structure and validation, preserve manual/evidence columns not listed, and apply `#D9EAD3` only to changed cells.

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

Changed cells from live row 10: `D10 = Facilitator\n1. Provide a seeded date range, status, camera/location question, and Help Center topic.\n2. Assign export coverage: OP-01 Detections CSV; OP-02 Detections PDF; OP-03 Dashboard CSV; OP-04 Dashboard PDF; OP-05 AI Performance CSV; OP-06 AI Performance PDF.\n3. Direct the participant to use the visible active filters for the export.\n\nSystem Handler\n1. Ensure matching detection and analytics records exist.\n2. Keep the OP-J08 incident Ongoing for handover.\n3. Verify the downloaded artifact: uv run python backend/scripts/verify_uat_export.py \"<downloaded-file>\"\n4. Stop/reset publishers only after evidence is retained.\n\nLogger\n1. Verify the export against the visible filtered view.`; `F10 = 1. Filter the assigned Detections or analytics view using the given criteria. 2. Identify the requested operational pattern. 3. Export from the assigned surface and format. 4. Verify that the export matches the active filters. 5. Find the relevant SOP/FAQ in Help Center. 6. Give a concise verbal handover covering the active OP-J08 incident, cleared and dismissed records, and follow-up responsibilities.`; `G10 = 1. The correct records and operational pattern are found. 2. The assigned CSV/PDF export opens and matches the active filtered view. 3. Across the six Operators, Detections, Dashboard, and AI Performance are each covered in both CSV and PDF. 4. The role-appropriate Help Center guidance is found. 5. The handover accurately identifies the active Ongoing incident, terminal records, and manual responsibilities. 6. Evidence references are ready for the Execution Log.`; `H10 = FR-13; FR-17; FR-18; FR-19`.

#### NEW

Changed cells: `D10 = Facilitator\n1. Provide a seeded date range, status, camera/location question, and Help Center topic.\n2. Assign Operator export coverage: OP-01 Detections CSV; OP-02 Detections PDF; OP-03 Dashboard CSV; OP-04 Dashboard PDF. Assign Administrator export coverage separately: AD-J02 AI Performance CSV and AI Performance PDF.\n3. Direct the participant to use the visible active filters for the assigned export.\n\nSystem Handler\n1. Ensure matching detection and analytics records exist.\n2. Keep the OP-J08 incident Ongoing for handover.\n3. Verify each downloaded artifact: uv run python backend/scripts/verify_uat_export.py \"<downloaded-file>\"\n4. Stop/reset publishers only after evidence is retained.\n\nLogger\n1. Verify each export against the visible filtered view and record the role used.`; `F10 = 1. Filter the assigned Detections or Dashboard view using the given criteria. 2. Identify the requested operational pattern. 3. Export from the assigned surface and format. 4. Verify that the export matches the active filters. 5. Find the relevant SOP/FAQ in Help Center. 6. Give a concise verbal handover covering the active OP-J08 incident, cleared and dismissed records, and follow-up responsibilities.`; `G10 = 1. The correct records and operational pattern are found. 2. The assigned Operator CSV/PDF export opens and matches the active filtered view. 3. Across the Operator participants, Detections and Dashboard are each covered in both CSV and PDF; Administrator participants cover AI Performance in both CSV and PDF in AD-J02. 4. The role-appropriate Help Center guidance is found. 5. The handover accurately identifies the active Ongoing incident, terminal records, and manual responsibilities. 6. Evidence references are ready for the Execution Log.`; `H10 = FR-13; FR-17; FR-18; FR-19`.

#### Evidence

This is the shared P28/P29 row. P28’s merged `Cleared` terminology is already present in live F10; preserve it while applying the P29 role-boundary changes. Preserve A10:C10 and I10, row formatting, and any validation; write only D10, F10, and G10.

#### Proposed comment (same gate as associated replacement)

Comment scope: Logical-paragraph scope — highlight the full changed UAT Journeys D10, F10, and G10 field content.

Previous: D10 = Facilitator\n1. Provide a seeded date range, status, camera/location question, and Help Center topic.\n2. Assign export coverage: OP-01 Detections CSV; OP-02 Detections PDF; OP-03 Dashboard CSV; OP-04 Dashboard PDF; OP-05 AI Performance CSV; OP-06 AI Performance PDF.\n3. Direct the participant to use the visible active filters for the export.\n\nSystem Handler\n1. Ensure matching detection and analytics records exist.\n2. Keep the OP-J08 incident Ongoing for handover.\n3. Verify the downloaded artifact: uv run python backend/scripts/verify_uat_export.py \"<downloaded-file>\"\n4. Stop/reset publishers only after evidence is retained.\n\nLogger\n1. Verify the export against the visible filtered view.; F10 = 1. Filter the assigned Detections or analytics view using the given criteria. 2. Identify the requested operational pattern. 3. Export from the assigned surface and format. 4. Verify that the export matches the active filters. 5. Find the relevant SOP/FAQ in Help Center. 6. Give a concise verbal handover covering the active OP-J08 incident, cleared and dismissed records, and follow-up responsibilities.; G10 = 1. The correct records and operational pattern are found. 2. The assigned CSV/PDF export opens and matches the active filtered view. 3. Across the six Operators, Detections, Dashboard, and AI Performance are each covered in both CSV and PDF. 4. The role-appropriate Help Center guidance is found. 5. The handover accurately identifies the active Ongoing incident, terminal records, and manual responsibilities. 6. Evidence references are ready for the Execution Log.

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

| Target                        | Approved scope | Applied/read back | Skipped/pending                                                                      | Blocked |
| ----------------------------- | -------------- | ----------------- | ------------------------------------------------------------------------------------ | ------- |
| Defense paper                 | —              | —                 | blocks 1–11; DFD coordination note pending with `2026-08-23-logical-dfd-overhaul.md` | —       |
| ADAS_Paper_Audit plus tracker | —              | —                 | blocks 12–13                                                                         | —       |
| ADAS Test Execution Tracker   | —              | —                 | blocks 14–22                                                                         | —       |
| Standalone comments           | —              | —                 | none proposed outside replacement comments                                           | —       |

No Drive writes were made in this implementation. The rendered-paper page mapping remains `unconfirmed` because the connected export returned a user-scoped file reference that was not available to the local PDF renderer in this session.
