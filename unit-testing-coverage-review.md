# Unit Testing Coverage Review

Reviewed on 2026-08-29 against the current implementation and the capstone
requirements. This is a requirements-level selection, not a copy of every
automated test. A selector is selected only when it directly proves a distinct
required success, denial, boundary, or recovery behavior in isolation.

The tracker rows are `TC-UNIT-001` through `TC-UNIT-050`. Performance-marked
tests, AI clip tests, Playwright specifications, and frozen transfer-reference
tests are intentionally excluded from this Unit Testing selection.

## Functional requirements

| Requirement                                 | Correct activity           | Direct isolated coverage / disposition                                                                                                                                       |
| ------------------------------------------- | -------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| FR-01 Authentication                        | Unit                       | `TC-UNIT-001` successful cookie session; `TC-UNIT-002` generic credential denial.                                                                                            |
| FR-02 Role-Based Access Control             | Unit                       | `TC-UNIT-003` denies an Operator user-management access; `TC-UNIT-004` denies audit-log access.                                                                              |
| FR-03 User Account Management               | Unit                       | `TC-UNIT-005` creates an Operator account; `TC-UNIT-006` protects the last Administrator.                                                                                    |
| FR-04 Video Stream Ingestion                | Unit                       | `TC-UNIT-007` does not start disabled cameras; `TC-UNIT-008` safely keeps only the newest frame. Real RTSP/VMS interoperability remains Integration/System.                  |
| FR-05 Automated Collision Detection         | Unit + AI Model Validation | `TC-UNIT-009` filters to the accident class; `TC-UNIT-010` requires sustained evidence; `TC-UNIT-011` rejects intermittent noise. Accuracy is AI Model Validation, not Unit. |
| FR-06 Alert Generation and Snapshot Capture | Unit                       | `TC-UNIT-012` creates a loadable JPEG snapshot; `TC-UNIT-013` creates an idempotent alert record from the AI event.                                                          |
| FR-07 Audible Alert Timeout / Escalation    | Unit                       | `TC-UNIT-014` uses the saved snooze duration; `TC-UNIT-015` clears expired snoozes and retains only pending alarms for re-scheduling. Live delivery is Integration/System.   |
| FR-08 Alarm Configuration                   | Unit                       | `TC-UNIT-016` persists a complete configuration; `TC-UNIT-017` exposes matching allowed sound and bound options.                                                             |
| FR-09 Human-in-the-Loop Verification        | Unit                       | `TC-UNIT-018` confirms an unverified alert; `TC-UNIT-019` blocks illegal state transitions.                                                                                  |
| FR-10 False Positive Handling               | Unit                       | `TC-UNIT-020` records immediate dismissal as verification; `TC-UNIT-021` starts the cooldown and scheduling side effect.                                                     |
| FR-11 True Positive Handling                | Unit                       | `TC-UNIT-022` resolves only an ongoing incident; `TC-UNIT-023` reactivates an enabled camera afterward.                                                                      |
| FR-12 Incident Logging                      | Unit                       | `TC-UNIT-013` persists a received AI alert; `TC-UNIT-024` checks the event source idempotency path.                                                                          |
| FR-13 Historic Logs Search and Filtering    | Unit                       | `TC-UNIT-025` intersects alert filters; `TC-UNIT-026` emits a safe CSV history export.                                                                                       |
| FR-14 Camera Configuration Management       | Unit                       | `TC-UNIT-027` creates an active desired-state camera; `TC-UNIT-028` disables and bumps configuration; `TC-UNIT-029`–`031` cover client validation.                           |
| FR-15 System Health and Hardware Telemetry  | Unit                       | `TC-UNIT-032` returns a fresh health sample; `TC-UNIT-033` presents stale heartbeats as unresponsive. Live hardware readings remain System/Performance evidence.             |
| FR-16 AI Performance Monitoring             | Unit + Performance         | `TC-UNIT-034` builds per-camera and global performance metrics. Required latency/FPS thresholds are Performance evidence.                                                    |
| FR-17 Accident Analytics and Visualisation  | Unit                       | `TC-UNIT-035` returns KPIs, accident frequency, and the complete hour series; `TC-UNIT-036` handles date-range deltas without fabricating zeroes.                            |
| FR-18 Report Generation and Data Export     | Unit                       | `TC-UNIT-037` completes and downloads a queued incident CSV job; `TC-UNIT-038` neutralizes formula injection in exports. Timing/scalability are Performance evidence.        |
| FR-19 Help Centre                           | Unit                       | `TC-UNIT-039` enforces article role visibility; `TC-UNIT-040` falls back safely when FTS5 is unavailable.                                                                    |
| FR-20 Activity Audit Trail                  | Unit                       | `TC-UNIT-041` records a user deletion with the target username; `TC-UNIT-049` records correct actions for every legal alert transition.                                      |

## Non-functional requirements

| Requirement                                  | Correct activity              | Direct isolated coverage / disposition                                                                                                                                              |
| -------------------------------------------- | ----------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| NFR-01 Algorithmic Accuracy                  | AI Model Validation           | Not a Unit criterion. Validate mAP and labelled clips, not fake-detector tests.                                                                                                     |
| NFR-02 Inference Latency                     | Performance & Load Testing    | Requires timed inference on declared hardware.                                                                                                                                      |
| NFR-03 Frame-rate                            | Performance & Load Testing    | Requires sustained multi-stream measurement.                                                                                                                                        |
| NFR-04 Alert Response Time                   | Performance & Load Testing    | Requires end-to-end detection-to-dashboard timing.                                                                                                                                  |
| NFR-05 Telemetry Refresh Rate                | Performance & Load Testing    | Requires time-based measurement under running services.                                                                                                                             |
| NFR-06 Report Generation Speed / Scalability | Performance & Load Testing    | Requires the seeded large dataset and timings.                                                                                                                                      |
| NFR-07 Hardware Scalability                  | Performance & Load Testing    | Requires actual machine/load measurements.                                                                                                                                          |
| NFR-08 Database Performance                  | Performance & Load Testing    | Requires timed database queries on the target dataset.                                                                                                                              |
| NFR-09 Operational Efficiency                | User Acceptance Testing       | Requires observed operators and dispatch-decision timings.                                                                                                                          |
| NFR-10 Workflow Efficiency                   | User Acceptance Testing       | Requires real click-path observation.                                                                                                                                               |
| NFR-11 Alert Distinctiveness                 | Unit + Usability              | `TC-UNIT-042` verifies the configured distinct sound mapping. Human recognisability is Usability evidence.                                                                          |
| NFR-12 Learnability                          | Usability Testing             | Requires a new participant's unaided task performance.                                                                                                                              |
| NFR-13 Availability                          | Reliability & Endurance       | Requires readiness sampling through a soak window.                                                                                                                                  |
| NFR-14 Network Fault Tolerance               | Reliability & Endurance       | Requires real stream/network fault injection.                                                                                                                                       |
| NFR-15 Process Isolation                     | Reliability & Endurance       | `test_pipeline.py::test_isolated_failure_is_not_recorded_as_a_completion` is supporting code coverage, but a process failure claim needs the live fault drill.                      |
| NFR-16 Daily Restart / Restart Recovery      | Reliability & Endurance       | Requires a real restart and recovered ingestion measurement.                                                                                                                        |
| NFR-17 Asynchronous Alert Recovery           | Unit + System / E2E           | `TC-UNIT-043` drains durable events after restart; a dashboard re-synchronisation workflow remains System/E2E.                                                                      |
| NFR-18 Data Redundancy and Recovery          | Unit + Backup & Recovery      | `TC-UNIT-045` validates online backup with concurrent writes; `TC-UNIT-046` prevents backup paths escaping their directory. Operational restore time is Backup & Recovery evidence. |
| NFR-19 Session Security                      | Unit + Security Testing       | `TC-UNIT-047` rejects an invalid signing key; `TC-UNIT-048` rejects hostile snapshot paths. Transport and deployment controls are Security Testing.                                 |
| NFR-20 Data Localisation                     | Security Testing / Operations | No isolated application test proves deployment location or access boundary; inspect the deployed local network and storage configuration.                                           |
| NFR-21 Audit-Trail Integrity                 | Unit + Security Testing       | `TC-UNIT-049` asserts legal transitions write the correct audited action. Broader non-repudiation review remains Security Testing.                                                  |
| NFR-22 Modular AI Upgrades                   | Unit                          | `TC-UNIT-050` fails closed for a missing configured model rather than silently falling back.                                                                                        |

## Confirmed Unit gap and repair

`TC-UNIT-029` exposed that the shared camera form parsed `12abc` as channel
`12`. The backend already rejects non-integer input, so this was a client-side
validation mismatch rather than a changed requirement. The form now accepts
only digit-only positive safe integers; the original failing case and its
retest are recorded in the frontend execution report and tracker retest note.
