# 22 — Reports and exports

> **One-liner:** ADAS turns filtered incident, audit, dashboard, and AI-performance data into downloadable CSV or PDF files, with a background-job path for larger exports.
> **Panel risk:** Medium — the feature is easy to describe technically, but the team must be precise about who needs the reports, what the performance result proves, and what the exports do and do not remove.

## 1. What it is

Reports and exports let an authorized ADAS user take a filtered view of system records and save it as a file.

The files support a practical CDRRMO workflow as well as later review of system activity and AI behaviour.

### Why these reports exist

The primary operational driver is shift handover.

In the CDRRMO workflow given for this guide, accidents from the 2–10 and 10–6 shifts are passed to PDRRMO.

An incident report gives the outgoing team a readable record to carry with that handover.

ADAS prepares the file; staff still pass it on.

It does not send a report directly to PDRRMO or dispatch a response.

Researchers and students who approach the office and request records are secondary users.

That is a real secondary use, but it is not the main reason to justify the feature.

The paper’s FR-18 describes sharing information with other agencies, official record-keeping, and supporting improvement of the AI model.

Say the narrower truth: the report supports handover, sharing, and later review.

Do not present the file as a legally prescribed form or claim that ADAS automates an agency submission.

### The four report types

#### Incident report

This is the case-level view: a filtered list of detected incidents and the human handling of each record.

It includes a record reference, detection time, camera name, status, confidence, and the names and times associated with verification and closure.

This is the most direct fit for shift handover because it carries the incident facts and the current human-reviewed state.

It can also be used to retrieve a filtered historical record when someone requests information.

#### Audit log report

This is the accountability view of important actions in the system.

It records the audit identifier, date and time, user and role, action, affected record, result, and details.

The audit export is available to Administrators, matching the role that reviews audit records in the paper’s use-case description.

It answers “who did what, to which record, and what was the result?” rather than “what happened at the camera?”

#### Dashboard report

This is the trend and summary view of past accident data.

The PDF presents summary measures, accident frequency by camera location, and peak accident times.

The CSV contains the confirmed-accident rows underlying the dashboard view, so a reader can inspect the records behind its totals.

The dashboard report summarizes patterns; the incident report is the better fit when a recipient needs event-by-event detail.

#### AI performance report

This is the model-monitoring view, available to Administrators.

It presents system-level and per-camera counts, precision, and confidence measures.

The purpose is to help identify cameras or conditions that deserve review and to inform model-improvement work.

It is an AI diagnostic report, not a replacement for the operator’s incident decision.

### Two output formats

CSV is a row-and-column file that can be opened in spreadsheet software or imported for further analysis.

PDF is the formatted report intended to be read or printed as a stable document.

The same report family can have different CSV and PDF presentations when that better fits the content.

For example, dashboard CSV gives the underlying confirmed-incident rows, while its PDF gives the summary view.

The data stays filtered to the user's selection so the export answers the same question as the on-screen view.

## 2. Where it lives

### In the paper

- Chapter 3, Functional Requirements Specification, Table 2, FR-18: incident records and summary figures can be exported in common formats such as CSV and PDF; Administrators can export AI-performance data.

- Chapter 3, Table 2, FR-16: the AI-performance view reports system and camera-level incident counts and confidence information.

- Chapter 3, Table 2, FR-17: the dashboard summarizes past accident counts and clearance status, with time and location patterns and filtering.

- Chapter 3, Table 2, FR-20: the audit trail records report generation and incident export, along with critical operational and administrative actions.

- Chapter 3, Figure 4 and its actor description: Operators export incident and dashboard reports; Administrators additionally review and export AI-performance and audit records.

- Chapter 3, Non-Functional Requirements Specification, Table 3, NFR-06: a standard 30-day report must begin downloading within 5 seconds; larger PDF and CSV requests use a background job, expose progress, retain the finished file for 72 hours, and resume if interrupted.

- Chapter 3, Table 17, Export Job: the job record tracks the lifecycle, requested parameters, progress, failure information, and artifact-retention details.

- Chapter 4, “Operator Scenarios (Analytics & Reporting)”: the UAT scenario uses historical records, date and location filters, and CSV/PDF incident reports for post-incident record-keeping.

- Chapter 4, “Data Utility and Reporting”: the assessment checks report accuracy and formatting for historical logs used in inter-agency coordination.

### In the code

#### Routes and permissions

- `backend/app/api/routes/alerts.py:299` handles synchronous incident exports.

- `backend/app/api/routes/analytics.py:341` handles dashboard exports.

- `backend/app/api/routes/analytics.py:743` handles AI-performance exports and requires an Administrator.

- `backend/app/api/routes/audit.py:274` handles audit exports and requires an Administrator.

- `backend/app/api/routes/exports.py:55` creates asynchronous jobs and applies the Administrator-only boundary for audit and performance jobs.

#### Formatting and report construction

- `backend/app/services/reports/common.py:23` formats report timestamps in the configured local time zone.

- `backend/app/services/reports/common.py:60` formats confidence and precision values for reports.

- `backend/app/services/reports/common.py:137` maps internal report types and formats to reader-facing labels.

- `backend/app/services/reports/csv_writer.py:47` handles CSV cell values; `:65` writes CSV rows in chunks; `:101` returns a downloadable CSV response.

- `backend/app/services/reports/pdf_writer.py:61` defines the shared PDF layout.

- `backend/app/services/reports/pdf_writer.py:88` writes the PDF header, while `:152` writes the footer.

- `backend/app/services/reports/pdf_writer.py:287` builds the incident PDF; `:319` the dashboard PDF; `:377` the AI-performance PDF; and `:428` the audit PDF.

#### Job lifecycle

- `backend/app/models/export.py:9` defines the persistent export-job record.

- `backend/app/api/routes/exports.py:95` returns job status and progress fields; `:182` reads a job; `:193` downloads a completed artifact.

- `backend/app/services/reports/jobs.py:616` generates a job artifact and records its outcome.

- `backend/app/services/reports/jobs.py:744` recovers jobs that were queued or processing when the service stopped.

## 3. How it works

### A user chooses a report

The user signs in and selects the report family and output format.

Incident, dashboard, and audit exports accept filters such as date range, camera, status, user, or action, according to the report.

The selected filters define which rows or summary values are generated.

The incident and dashboard routes use the same underlying filter logic as their on-screen views.

The AI-performance export uses the same filters as the Administrator’s performance screen.

The audit export uses the filters available on the audit-log view.

### The access check happens on the server

Incident and dashboard export routes require a signed-in user.

The AI-performance and audit routes require an Administrator.

The asynchronous route applies the same role boundary, so an Operator cannot create an audit or AI-performance job and download it as its owner.

An Administrator can view another user’s jobs through the administrative list option; ordinary job listings are scoped to the requesting user.

### Small exports use the synchronous path

The synchronous endpoints count the filtered rows before generating the file.

That count is compared with the configured synchronous ceiling for the requested format.

The paper and code set the ceiling at 10,000 rows for PDF and 50,000 rows for CSV.

When the request is within the ceiling, the route records the export attempt and then builds the selected format.

An incident or audit export can stream CSV rows from the database query.

The PDF path builds a formatted document with a report title, filter summary, and table or summary sections.

Every export attempt is recorded in the audit trail, including a rejected synchronous request that exceeded its row ceiling.

### The export row is prepared for a reader

Incident and dashboard rows use the camera name rather than the camera’s database foreign key.

They use handler names instead of the handler foreign-key columns.

The event’s human-facing Log ID remains in the incident and dashboard export as a record reference.

The snapshot API path is not included in those reports.

Report timestamps are displayed in the configured local time zone rather than as raw database timestamps.

Confidence and precision values are presented as percentages instead of raw decimal fractions.

The audit report uses labels for action and result values and converts its detail payload into labelled text where it recognizes the fields.

Missing cell values are shown as `N/A` rather than an empty cell that could be mistaken for zero.

CSV cell values are also checked for spreadsheet formula prefixes before they are written.

That check prevents a value from being treated as a spreadsheet formula; it is separate from personal-data handling.

### The PDF carries the CDRRMO identity

The shared PDF header identifies Lipa CDRRMO and the Accident Detection & Alert System.

It places the selected report title and generation-time information in the header.

The logo is rendered when the configured image asset is available.

The footer repeats the system identity and supplies page numbering.

All four PDF report builders use the same shared base layout.

That makes the exports recognizable as ADAS-generated CDRRMO reports rather than unlabelled database dumps.

### A larger export becomes a separate job

For requests above the synchronous ceiling, the client submits the report type, format, and filters to the export-job endpoint.

The server creates a persistent queued job and places its identifier on the worker queue.

The client can poll the job-status endpoint for status and progress fields.

When the job is complete, the requesting user can download its artifact.

The completed artifact remains available for 72 hours, then the cleanup routine removes the file and marks the job expired.

The synchronous endpoint does not silently convert an oversized request into a job.

It rejects that request with a row-limit response and directs the client to use the asynchronous endpoint.

This explicit split prevents a long, large report build from keeping an ordinary export request open.

The test tracker records a 600,006-row CSV job that returned 202 Accepted, reported progress, completed, and produced a file with the matching data-row count.

The same tracker records that the large job was recovered after a deliberate restart.

On service restart, queued or processing jobs are put back on the queue from their saved report parameters.

Recovery regenerates the artifact from the beginning; it does not trust a partial file from the interrupted run.

### Exporting the audit log does not include its own new row

Creating an audit export itself writes an audit record.

Before writing that row, the route captures the newest existing audit identifier.

The exported query includes only rows up to that captured watermark.

The new “audit export” action is therefore outside the dataset being exported.

This keeps the export from recursively containing its own action and gives a stable cutoff for that file.

## 4. Why it was built this way

The design starts with the actual handover use: a staff member can carry a filtered incident record when accidents from the 2–10 and 10–6 shifts are passed to PDRRMO.

This is a narrower and more defensible reason than claiming that ADAS satisfies a broad external reporting mandate.

The paper connects the export function to agency sharing and official record-keeping; the team’s operational explanation should begin with shift handover.

Researchers and students who request records are additional users of the same history, not the primary operational driver.

The incident and dashboard reports answer different questions.

The incident report is for individual events and their human-reviewed state.

The dashboard report is for aggregate time and location patterns.

The AI-performance report is for reviewing model behaviour by camera.

The audit report is for administrator accountability about system actions.

Keeping them distinct avoids forcing a recipient to infer case facts, trend summaries, model diagnostics, and administrative history from one mixed export.

CSV supports table-based analysis; PDF preserves a page layout with titles, filters, and readable sections.

The PDF’s CDRRMO identity gives a recipient context for where the file came from.

The reader-facing time and percentage formats lower the work needed to interpret stored system values.

Replacing internal foreign keys with names makes incident rows intelligible to people who do not query the database.

Keeping the Log ID preserves a concise reference back to the incident record.

Audit exports keep their Audit ID and affected-record reference because those are the audit trail’s traceability fields.

The background path separates larger report generation from normal request handling, while the synchronous ceiling defines which requests are considered routine.

NFR-06 supplies both the operational response target and the larger-file job behaviour rather than treating every export as one kind of request.

The 72-hour artifact window lets a user return to a completed job without keeping generated files indefinitely.

## 5. What changed since the 28 April defense

The current export feature is a substantial addition since the previous defense baseline.

Git history after 28 April shows the CSV writer, PDF writer, report endpoints, and asynchronous export-job lifecycle landing after that baseline.

The incident, dashboard, AI-performance, and audit report routes now share CSV/PDF construction instead of leaving report output as a planned feature.

The large-file job path stores a job record, runs work in a background worker, exposes job status, and retains a downloadable artifact.

The PDF reports now carry Lipa CDRRMO identity and consistent report layouts.

The output formatting now uses reader-facing timestamps, confidence percentages, and audit labels.

Incident and dashboard output omit internal foreign-key columns and the snapshot API path while retaining the Log ID reference.

AI-performance exports are Administrator-only, as are audit exports.

These changes are reflected in the current paper’s FR-18, NFR-06, Figure 4 actor description, and Export Job table.

Relevant history includes `0a67ea9` for CSV/PDF export routes, `5cee396` for background export jobs, `7d438f9` for Lipa CDRRMO PDF branding, `c349fb3` for human-readable value formatting, `1b8b873` for dropping internal ID columns and the snapshot path, and `432311b` for restricting AI-performance access.

## 6. Limits and honest caveats

- The standard-window performance result comes from a test dataset, not a month of live CDRRMO production traffic.

- TC-PERF-005 used 300 records to represent the approximately 10-incidents-per-day operating-envelope assumption over 30 days.

- The tracker measured total request/download time: CSV took 0.190 seconds and PDF took 2.104 seconds, both below NFR-06’s 5-second target.

- Those elapsed totals do not isolate the exact time to first byte; do not relabel them as a separate time-to-first-byte measurement.

- TC-PERF-006 exercised a large CSV job with 600,006 data rows; the result is not evidence that every PDF, every report family, or every larger dataset has the same runtime.

- The 10,000-row PDF and 50,000-row CSV values are synchronous ceilings, not a promise that a file at either ceiling will meet the 5-second standard-window target.

- TC-UNIT-060 verifies which side of the synchronous ceiling a request takes; it is a boundary test, not a large-file timing result.

- The asynchronous test demonstrates a large CSV job’s acceptance, progress, completion, row count, and retention behaviour; the paper does not set the same 5-second download target for that job path.

- The report output is not anonymized: incident rows can name the handler, and audit rows identify the user and role.

- Foreign-key omission is data shaping for a reader, not a guarantee that the file contains no personal or identifying information.

- The Log ID, Audit ID, and affected-record reference remain in the relevant reports for traceability.

- The ADAS report feature creates downloadable files; the team must not claim an automatic PDRRMO transfer or automatic dispatch integration.

- The defense paper scopes the system as a proof of concept evaluated in the documented test environment, not a live command-centre deployment.

- An export is a record or analysis aid; it does not decide whether an alert is true and does not replace the operator’s review.

## 7. Likely panel questions

### “Who actually reads these reports?”

The primary reader is the staff member preparing a shift handover: accidents from the 2–10 and 10–6 shifts are passed to PDRRMO, and the incident report carries the filtered record for that handover.

Researchers and students who approach the office for records are secondary users.

### “Why four different report types?”

They answer four different questions: what happened in an incident, what actions users took, what patterns appear in the dashboard, and how the AI performs by camera.

Splitting those views keeps the data relevant to the reader and the role allowed to export it.

### “What stops an export leaking personal data?”

Server-side role checks restrict audit and AI-performance exports to Administrators, and the incident exports leave out internal join keys and snapshot paths.

The reports are not anonymized: handler names and audit user names remain where they support accountability, so we do not claim that exports contain no identifying information.

### “Why is the large export asynchronous?”

An explicit background job lets the user return to the dashboard while the server builds a large file, then poll status and download the finished artifact.

The tracker exercised a 600,006-row CSV job that returned 202 Accepted and completed with the matching row count.

### “Could an Operator export the audit log?”

No. Both the synchronous audit route and the asynchronous audit-job path require an Administrator, so hiding the button in the interface is not the only control.

### “Why offer CSV and PDF?”

CSV gives a table that can be filtered or analyzed in spreadsheet tools.

PDF gives a formatted, branded report with a title and filter context for reading or printing.

### “What happens if someone requests more rows than the synchronous ceiling?”

The synchronous route rejects the request and records the failed export attempt.

The user submits the same report parameters through the separate export-job endpoint to have it built in the background.

### “Are all internal identifiers removed?”

No. The incident and dashboard reports keep the human-facing Log ID, and the audit report keeps its Audit ID and affected-record reference.

The internal camera and handler foreign keys are omitted because their names are shown instead.

### “Does ADAS send the handover report directly to PDRRMO?”

No. ADAS generates a downloadable file; staff carry out the handover.

The report feature does not claim an automatic agency transfer or dispatch step.

### “What did you prove for NFR-06?”

In the 300-row, 30-day test envelope, the tracker records CSV at 0.190 seconds and PDF at 2.104 seconds against the 5-second target.

Separately, a 600,006-row CSV job returned 202, completed with the matching rows, and had the required artifact-retention behaviour; that is a different test from the standard-window timing result.

## 8. Cram summary

- Start with purpose: the primary use is shift handover when accidents from the 2–10 and 10–6 shifts are passed to PDRRMO.

- Researchers and students who request records are secondary users.

- The four types are incident, audit, dashboard, and AI performance.

- The two formats are CSV for table-based work and PDF for a formatted, CDRRMO-branded report.

- Operators can export incident and dashboard data; Administrators also export audit and AI-performance data.

- Internal foreign keys and snapshot paths are omitted, while human-facing record references and necessary names remain.

- NFR-06 is 5 seconds for the standard 30-day report, with background jobs above 10,000 PDF rows or 50,000 CSV rows and 72-hour artifact retention.

- The tracker’s standard-window run used 300 records: CSV 0.190 seconds, PDF 2.104 seconds.

- A separate 600,006-row CSV job returned 202, completed, and produced a matching row count; do not treat that as a PDF performance result.

- ADAS creates the file. People still perform the PDRRMO handover.
