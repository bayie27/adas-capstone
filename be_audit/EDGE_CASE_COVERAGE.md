# Edge Case Coverage Register

Built 2026-08-11 by the A5 audit pack (`be_audit/A5_edge_cases.md`, Part 2), closing F12: P9's
original "~28 partially- or un-covered rows out of ~150" sweep result was lost outside the repo, and
`14_EDGE_CASES.md` had no status column to prevent that from happening again. This document is that
status column, one row per case in `be_plan/14_EDGE_CASES.md`.

## How this was built

Every row below was checked by opening the actual matching test function and reading its body —
never marked `covered` on a plausible test name alone. For rows with several listed sub-parts (e.g.
"asserts X, Y, and Z"), the row is only `covered` if the test asserts all of them; if some but not
all are asserted, it's `partial`, with the gap named in Evidence.

## Status legend

- **covered** — the test(s) named in Evidence fully assert what the row describes.
- **partial** — some but not all of what the row describes is asserted; Evidence says what's missing.
- **uncovered** — no real test exercises this case.
- **accepted-gap** — falls under `14_EDGE_CASES.md`'s own pre-declared exclusions (see bottom).
- **inapplicable** — the row doesn't actually apply to this codebase; rationale given.

**Totals: 110 covered · 23 partial · 9 uncovered · 1 inapplicable · 0 accepted-gap · 143 rows/units.**

Nine rows turned out to be more than a missing test. Two are confirmed implementation bugs found
while verifying this register (not just untested — read directly in source): **3.5** (analytics
performance breakdown silently drops any camera with zero incidents) and **6.9** (no startup check
that `SNAPSHOT_ROOT` is writable). These and five more materially-risky gaps are now `F22`–`F28` in
`be_audit/00_FINDINGS.md` — see that register for the full writeup; this document only summarizes.

---

## 1. Concurrency and races

| Row | Case | Package | Status | Evidence |
|---|---|---|---|---|
| 1.1 | Two operators confirm the same incident simultaneously | P4 | covered | `test_alerts.py::TestConcurrency::test_two_confirms_race_exactly_one_wins` — sequential simulation (relies on the atomic conditional-UPDATE `transition()`, not real threads); asserts `{200,409}` and final status `Ongoing` |
| 1.2 | Two operators resolve the same `Ongoing` incident | P4 | covered | `test_alerts.py::TestConcurrency::test_two_resolves_race_exactly_one_wins` — sequential simulation, asserts `{200,409}` |
| 1.3 | Snooze racing a Confirm | P4 | covered | `test_alerts.py::TestConcurrency::test_snooze_loses_to_a_confirm_landing_mid_flight` — deterministic interleaving via `monkeypatch` on `Session.get`; asserts `ConflictState` with `current_status=Ongoing`, `handled_action=ALERT_CONFIRM` |
| 1.4 | Re-snooze racing the previous snooze's expiry job | P4 | covered | `test_snoozes.py::TestClearExpiredSnooze::test_re_snooze_racing_the_previous_deadline_finds_it_moved` — sequential/state simulation; asserts zero `RE_ALARM` |
| 1.5 | Two AI events for one camera arriving simultaneously | P4 | covered | `test_internal.py::TestReceiveAiAlertV2::test_v2_open_camera_conflict_is_409` — sequential simulation; second is `409 CONFLICT_STATE`. Race-safety rests on `ux_detection_open_camera`, unexercised by a genuinely parallel test |
| 1.6 | The same `source_event_id` posted twice concurrently | P4 | partial | `test_internal.py::TestReceiveAiAlertV2::test_v2_idempotent_retry_returns_200_same_row` proves idempotency only **sequentially**. The row explicitly requires genuinely parallel requests; the `ux_detection_source_event` `IntegrityError` backstop is never actually hit by any test. **F24** |
| 1.7 | AI event arriving while an operator disables that camera | P4 | covered | `test_internal.py::TestConcurrentDisableRace::test_ai_alert_racing_operator_disable_never_500s_and_stays_consistent` — genuinely parallel threaded test; found and fixed two real race bugs while writing it (**F21**) |
| 1.8 | Cooldown job firing while a new incident opens on that camera | P4 | covered | `test_camera_reconciliation.py::TestResumeCameraAfterCooldown::test_leaves_camera_paused_if_a_new_incident_opened` |
| 1.9 | Camera soft-deleted while its cooldown job is pending | P4 | covered | `test_camera_reconciliation.py::TestResumeCameraAfterCooldown::test_soft_deleted_camera_is_untouched` (job no-ops) + `test_cameras.py::TestDeleteCamera::test_succeeds_without_open_incident_sets_inactive` (the delete route itself sets `Inactive`) |
| 1.10 | Session revoked mid-request | P2 | covered | `test_auth.py::TestConcurrencyAndMultiSession::test_request_completes_cleanly_after_mid_flight_revocation` — sequential simulation; pre-revocation request `200`, next `401` |
| 1.11 | Same user logging in twice | P2 | covered | `test_auth.py::TestConcurrencyAndMultiSession::test_two_logins_create_independent_sessions` + `test_revoking_one_session_does_not_touch_the_other` |
| 1.12 | Restore requested while a backup is running | P7 | covered | `test_maintenance.py::TestCrossOperationLock::test_restore_returns_409_while_backup_holds_the_lock`, `test_backup_returns_409_while_restore_holds_the_lock` |
| 1.13 | Backup running during heavy incident ingestion | P7 | covered | `test_maintenance.py::TestBackupCore::test_online_backup_succeeds_during_concurrent_writes` — genuine `threading.Thread` hammering writes while backup runs |
| 1.14 | Export artifact cleanup firing while a download is streaming | P6 | covered | `test_exports.py::TestArtifactExpiry::test_cleanup_backs_off_when_artifact_is_open_for_reading` — genuine OS-level open file handle held during cleanup |
| 1.15 | Two export jobs for the same user at once | P6 | covered | `test_exports.py::TestConcurrentJobs::test_two_jobs_for_the_same_user_are_both_processed_independently` — sequential simulation |
| 1.16 | WebSocket broadcast during a client disconnect | P3 | covered | `test_realtime.py::test_broadcast_during_a_client_disconnect_does_not_raise` — deterministic single-threaded simulation |
| 1.17 | Hourly rollup running twice for the same hour | P5 | covered | `test_system_health.py::TestRollupHour::test_rerunning_is_idempotent` |
| 1.18 | Two heartbeats from different engine instances | P4 | partial | `test_internal.py::TestHeartbeat::test_second_engine_id_within_staleness_window_logs_warning` only proves the identity-conflict warning logs; no test sends two engines' heartbeats reporting the *same* camera with conflicting state to check "last write wins, no corruption." **F24** |

## 2. Boundary values

| Row | Case | Package | Status | Evidence |
|---|---|---|---|---|
| 2.1 | `limit`: 0→422, 1→ok, 100→ok, 101→422 | P4, P6 | uncovered | No test asserts the `ge=1, le=100` boundary anywhere; valid values appear only incidentally in unrelated tests. **F27** |
| 2.2 | `offset`: −1→422, 0→ok, beyond total→empty page with correct `total_filtered` | P4, P6 | uncovered | No test asserts `ge=0` rejection or the beyond-total empty-page behavior. **F27** |
| 2.3 | `confidence_score`: 0.0/1.0 ok, −0.001/1.001 rejected by CHECK | P1 | covered | `test_schema.py::TestCheckConstraints::test_confidence_score_out_of_range_rejected` + `test_confidence_score_at_boundary_accepted` |
| 2.4 | `snooze_duration`: 14→422, 15→ok, 60→ok, 61→422 | P4 | covered | `test_settings.py::TestUpdateAlarmSettings::test_snooze_duration_boundaries` — all four values |
| 2.5 | `volume`: −1→422, 0→ok, 100→ok, 101→422 | P4 | covered | `test_settings.py::TestUpdateAlarmSettings::test_volume_boundaries` — all four values |
| 2.6 | `channel_id`: 0/negative rejected, 1 ok | P1 | covered | `test_schema.py::TestCheckConstraints::test_non_positive_channel_id_rejected` (parametrized); positive case implicit throughout suite |
| 2.7 | `username`: 2→422, 3→ok, 20→ok, 21→422 | P2 | covered | `test_auth.py::TestBoundaryValues::test_username_length_boundary` |
| 2.8 | `first_name`/`last_name`: 0→422, 1→ok, 20→ok, 21→422 | P2 | covered | `test_auth.py::TestBoundaryValues::test_first_name_length_boundary` + `test_last_name_length_boundary` |
| 2.9 | `password`: 7→422, 8→ok, 128→ok, 129→422; exactly-one-digit passes | P2 | covered | `test_auth.py::TestBoundaryValues::test_password_length_boundary` + `test_password_with_exactly_one_digit_passes` |
| 2.10 | `camera_name`: 0→422, 1→ok, 100→ok, 101→422 | P4 | partial | Upper bound only: `test_schema.py::TestUnicodeLength::test_max_length_counts_codepoints_not_bytes` (100 ok) + `test_one_over_max_length_in_codepoints_rejected` (101→422). No test for empty string (0→422) or an explicit length-1-ok case |
| 2.11 | Date range: `start==end` valid, `start>end`→422 | P4, P6 | partial | `start>end→422` well covered (`test_alerts.py::TestGetAlerts::test_invalid_date_range_returns_422`, `test_analytics.py::test_analytics_endpoints_reject_inverted_date_ranges`). No test sets `start==end` and asserts it returns that instant's rows |
| 2.12 | `cooldown_until==now` → treated as expired | P4 | covered | `test_camera_reconciliation.py::TestRecomputeDesiredState::test_cooldown_exactly_now_is_treated_as_expired` |
| 2.13 | `snoozed_until==now` → due, fires once | P4 | covered | `test_snoozes.py::TestClearExpiredSnooze::test_deadline_exactly_now_is_due` |
| 2.14 | Raw retention: exactly 48h→pruned, 47h59m→kept | P5 | covered | `test_system_health.py::TestPruneRaw::test_boundary_is_inclusive` |
| 2.15 | Hourly retention: exactly 30d→pruned, 29d23h→kept | P5 | covered | `test_system_health.py::TestPruneHourly::test_boundary_is_inclusive` |
| 2.16 | Session expiry: `expires_at==now` → rejected | P2 | covered | `test_auth.py::TestSessionAuthority::test_session_expiry_exact_boundary_is_rejected` |
| 2.17 | Export row limits: 10,000 PDF ok/10,001→413; 50,000 CSV ok/50,001→413 | P6 | covered | `test_reports.py::TestRowLimitBoundary::test_csv_at_exact_limit_succeeds_one_over_is_413` + `test_pdf_at_exact_limit_succeeds_one_over_is_413` (mechanism verified with monkeypatched limits; prod defaults 10000/50000 confirmed in `config.py`) |
| 2.18 | Heartbeat staleness: exactly 10s→`Unresponsive`, 9.9s→fresh | P4, P5 | covered | `test_cameras.py::TestGetAllCameras::test_heartbeat_staleness_boundary` + `test_system_health.py::TestCollectAiMetrics::test_heartbeat_staleness_boundary` |

## 3. Empty, null, and degenerate states

| Row | Case | Package | Status | Evidence |
|---|---|---|---|---|
| 3.1 | Analytics with zero incidents: KPIs 0, `precision_score` null, 24 zeroed buckets | P6 | partial | Only exercised indirectly via "only Unverified" tests (one Unverified log, not a literal zero-row DB) |
| 3.2 | Analytics with only `Unverified` incidents excluded from every number | P6 | covered | `test_analytics.py::test_dashboard_ignores_unverified_logs_and_returns_empty_state` + `test_performance_ignores_unverified_logs_and_returns_empty_state` |
| 3.3 | Precision when confirmed=0, dismissed=0 → `null` | P6 | covered | `test_analytics.py::test_performance_ignores_unverified_logs_and_returns_empty_state` — asserts `precision_score: None` |
| 3.4 | Precision when confirmed=0, dismissed>0 → `0.0` | P6 | covered | `test_analytics.py::TestPerformanceAnalytics::test_performance_returns_global_and_per_camera_metrics` |
| 3.5 | Camera with zero incidents appears in performance breakdown with null averages, not omitted | P6 | uncovered | **Confirmed implementation bug, not just untested** — `_compute_performance_data` builds `all_camera_ids` only from `confirmed_map.keys() \| dismissed_map.keys()`, structurally excluding any quiet camera. **F22** |
| 3.6 | Zero cameras registered: KPI invariants hold, heartbeat empty snapshot | P4, P5 | covered | `test_cameras.py::TestGetAllCameras::test_zero_cameras_kpis_all_zero` + `test_system_health.py::TestCollectAiMetrics::test_zero_cameras_is_a_clean_zero_state` |
| 3.7 | Export with zero matching rows: header-only CSV, empty-state PDF correct page count | P6 | covered | `test_reports.py::TestHostileAndDegenerateInput::test_sql_injection_string_in_search_is_inert` (CSV) + `TestPdfContent::test_empty_dataset_pdf_has_empty_state_and_correct_page_count` |
| 3.8 | Help search matching nothing: empty `items`, populated `top_faqs` | P8 | covered | `test_help.py::TestEmptyState::test_no_results_returns_empty_items_and_populated_top_faqs` |
| 3.9 | Help search with an empty string: returns all role-visible articles | P8 | covered | `test_help.py::TestEmptyState::test_empty_search_string_returns_all_visible_articles` |
| 3.10 | System health with no GPU: empty per-GPU list, null aggregates, still 200 | P5 | covered | `test_system_health.py::TestHealthLiveEndpoint::test_no_gpu_present_yields_empty_list_and_null_aggregates` |
| 3.11 | System health before first sample: explicit "no sample yet" | P5 | covered | `test_system_health.py::TestHealthLiveEndpoint::test_no_sample_yet_is_explicit_not_fabricated` |
| 3.12 | History range containing a collection gap: missing points, never zeros | P5 | covered | `test_system_health.py::TestHealthHistoryEndpoint::test_gap_in_data_is_a_missing_point_not_a_zero` |
| 3.13 | Hourly rollup for an hour with zero raw rows: no row created | P5 | covered | `test_system_health.py::TestRollupHour::test_no_rows_produces_no_row` |
| 3.14 | Audit viewer on a fresh database: empty page, correct `total_filtered`, no crash | P2 | covered | `test_audit.py::TestAuditViewer::test_fresh_database_returns_empty_page` |
| 3.15 | Incident whose snapshot file was deleted: detail ok, `/snapshot`→404, manifest marks unavailable | P4, P6 | partial | `/snapshot`→404 covered (`test_alerts.py::TestAlertSnapshotRoute::test_snapshot_404_when_file_missing`); manifest-unavailable covered (`test_maintenance.py::TestArchiveBuilder::test_archive_reports_missing_referenced_snapshot`). No test asserts the detail endpoint still 200s with the file missing |
| 3.16 | Backup list with zero backups: empty list; restore of nonexistent id→404 | P7 | covered | `test_maintenance.py::TestBackupRoutes::test_list_empty_when_no_backups` + `TestRestoreRoutes::test_restore_of_nonexistent_id_is_404` |

## 4. Hostile and malformed input

| Row | Case | Package | Status | Evidence |
|---|---|---|---|---|
| 4.1 | Camera named `=cmd\|'/c calc'!A1` neutralized in CSV | P6 | covered | `test_alerts.py::TestExportAlerts::test_export_alerts_neutralizes_formula_injection` |
| 4.2 | Same formula-injection name rendered into a PDF | P6 | partial | No test uses the literal formula string in a PDF; adjacent hostile-name-in-PDF tests only assert `startswith(b"%PDF")`, no text-extraction check |
| 4.3 | Camera name with newline/embedded `"`: correctly quoted in CSV, wrapped in PDF | P6 | partial | `test_reports.py::TestHostileAndDegenerateInput::test_newline_and_quote_in_camera_name_survive_csv_and_pdf` — CSV verified exactly; PDF only checked for `%PDF` header |
| 4.4 | Unicode names (emoji, RTL, combining, ZWJ) stored/returned/exported/PDF-rendered without mojibake or crash | P4, P6 | partial | `test_reports.py::TestHostileAndDegenerateInput::test_unicode_camera_name_round_trips_without_crash` — CSV exact-match verified; PDF only checked for `%PDF` header, never extracts rendered text |
| 4.5 | Max length counted in characters, not bytes | P1 | covered | `test_schema.py::TestUnicodeLength::test_max_length_counts_codepoints_not_bytes` + `test_one_over_max_length_in_codepoints_rejected` |
| 4.6 | Null byte in a string field rejected, not stored | P1 | covered | `test_schema.py::TestNullByteRejection` (camera/user); `test_internal.py::TestHeartbeat::test_null_byte_in_engine_id_is_422`; `test_snapshots.py::test_null_byte_rejected` |
| 4.7 | Leading/trailing (incl. Unicode) whitespace stripped from `username`; padding can't create a 2nd account | P2 | partial | `test_auth.py::TestUsernameNormalization` + `test_users.py::TestUpdateMyProfile::test_username_strip_whitespace` — all ASCII-space only, no Unicode whitespace (U+00A0, U+2003) test |
| 4.8 | SQL injection strings in `search` params inert | P4, P6 | covered | `test_reports.py::TestHostileAndDegenerateInput::test_sql_injection_string_in_search_is_inert` (login-form SQLi covered separately per row's own note) |
| 4.9 | `snapshot_key` traversal — all variants rejected | P4 | covered | `test_snapshots.py::test_hostile_snapshot_keys_all_rejected` (all 5 variants) + `test_symlink_escaping_root_rejected` |
| 4.10 | `backup_id` traversal rejected before filesystem access, same variants | P7 | covered | `test_maintenance.py::TestManifest::test_validate_backup_id_rejects_hostile_input` (8 variants) + `TestRestoreRoutes::test_path_traversal_backup_id_rejected_before_filesystem_access` — strict uuid4-hex allowlist structurally blocks every hostile shape |
| 4.11 | ZIP entry paths in retraining package relative only, no absolute/`..`/symlinks | P6 | covered | `test_exports.py::TestRetraining::test_retraining_package_labels_and_missing_snapshot` |
| 4.12 | FTS5 metacharacters in help search never 500, return empty | P8 | covered | `test_help.py::TestSearch::test_metacharacters_never_crash_and_return_empty` + `test_or_as_a_literal_term_never_crashes` |
| 4.13 | Extremely long (10 KB) `search` string rejected, no timeout | P4, P6, P8 | partial | Covered for P6 and P8; no equivalent test for P4's `/api/alerts/` list endpoint `search` param |
| 4.14 | Malformed JSON body, wrong content type, missing required field → `422 VALIDATION_ERROR`, never 500 | all | partial | Missing-required-field and the envelope both covered elsewhere; no test sends syntactically-broken JSON bytes or a wrong `Content-Type` header anywhere in the suite |
| 4.15 | Extra unexpected fields in a request body ignored or rejected consistently | all | covered | `test_alerts.py::TestSnooze::test_snooze_rejects_a_client_supplied_duration` + `test_internal.py::TestReceiveAiAlertV2::test_malformed_dual_shape_payload_is_422` — both reject (`extra="forbid"`) |
| 4.16 | Heartbeat reporting an unknown `camera_id` ignored, not an error | P4 | covered | `test_internal.py::TestHeartbeat::test_unknown_camera_id_ignored_not_an_error` |
| 4.17 | Heartbeat `measured_fps` negative or absurd (1e9) rejected/clamped | P4 | covered | `test_internal.py::TestHeartbeat::test_rejects_absurd_or_negative_fps` — both → 422 |
| 4.18 | AI error message with credential-bearing URL redacted before storage | P4 | covered | `test_internal.py::TestHeartbeat::test_error_message_is_redacted_before_storage` + `test_rtsp_url_covered_by_generic_credential_redaction` |

## 5. Time, clocks, and timezones

| Row | Case | Package | Status | Evidence |
|---|---|---|---|---|
| 5.1 | Query param with `+08:00` offset converted to UTC | P1 | covered | `test_types.py::TestParseUtcQueryDatetime::test_offset_is_converted_to_utc` |
| 5.2 | Query param with no offset interpreted as UTC | P1 | covered | `test_types.py::TestParseUtcQueryDatetime::test_naive_value_is_assumed_utc` |
| 5.3 | Query param with `Z` suffix same as `+00:00` | P1 | covered | `test_types.py::TestParseUtcQueryDatetime::test_z_suffix_behaves_like_plus_zero_offset` |
| 5.4 | Naive datetime reaching the DB layer raises | P1 | covered | `test_types.py::TestUtcDateTime::test_naive_datetime_raises_on_write` |
| 5.5 | `detected_at` in the future accepted | P4 | covered | `test_internal.py::TestReceiveAiAlertV2::test_v2_future_detected_at_is_accepted` — verified, matches claimed "accept, don't reject/clamp" decision |
| 5.6 | `detected_at` far in the past accepted (outbox replay) | P4 | covered | `test_internal.py::TestReceiveAiAlertV2::test_v2_far_past_detected_at_is_accepted` |
| 5.7 | Incident exactly at a UTC hour boundary lands in exactly one bucket | P5, P6 | partial | P5 covered (`test_system_health.py::TestRollupHour::test_boundary_rows_land_in_exactly_one_hour`); P6 analytics hour-of-day bucketing has no equivalent boundary test |
| 5.8 | Rollup at midnight UTC gets correct date attribution | P5 | uncovered | No test exercises rollup across a day boundary; existing test only covers a mid-afternoon truncation |
| 5.9 | Peak-hours bucket at 00:00 and 23:00 both present; all 24 buckets always returned | P6 | partial | "24 buckets always returned" well covered; no test seeds an incident specifically at hour 00 or 23 |
| 5.10 | `MAINTENANCE_HOUR_LOCAL` across a DST transition has defined behavior | P7 | inapplicable | Config default only — no Python code reads it; the actual restart trigger is an OS-level Scheduled Task/systemd, outside the app. Documented in `test_maintenance.py::TestSchedulingEdgeCases::test_documented_as_os_scheduler_responsibility` (skipped, with rationale) |
| 5.11 | Scheduler misfire after suspend/resume coalesces into one catch-up run | P4, P5, P7 | partial | Policy-level only: `test_scheduler.py::TestAddJob::test_applies_the_d009_policy_to_every_job` confirms `coalesce=True`/`max_instances=1`/`misfire_grace_time=300` on every job; no test simulates an actual backlog. P7 is OS-scheduler-level, out of Python's control |
| 5.12 | Server clock stepping backwards: snooze deadline in the future stays pending | P4 | uncovered | No test simulates a backward clock jump; the underlying `now() <= snoozed_until` comparison is safe by construction but untested for this scenario |

## 6. Failure injection and resource exhaustion

| Row | Case | Package | Status | Evidence |
|---|---|---|---|---|
| 6.1 | SQLite lock timeout → 503 | P1 | covered | `test_app_factory.py::TestConcurrentWriteLockHandling::test_real_lock_contention_returns_503_end_to_end` — real busy-timeout contention |
| 6.2 | Unhandled exception inside a scheduler job keeps it scheduled | P1 | covered | `test_scheduler.py::TestSchedulerJobErrorHandling::test_unhandled_exception_in_a_job_keeps_it_scheduled` |
| 6.3 | Scheduler job overrunning its interval; `max_instances=1` | P5 | covered | `test_scheduler.py::TestAddJob::test_applies_the_d009_policy_to_every_job` |
| 6.4 | Disk full during a snapshot write | P4 | partial | Read-side covered (missing/truncated file → 404, never 500); the ingestion path is largely a black box since the backend never writes the snapshot itself (the AI engine does) |
| 6.5 | Disk full during an export | P6 | covered | `test_exports.py::TestDiskFullDuringExport::test_artifact_write_failure_marks_job_failed_and_removes_partial_file` |
| 6.6 | Disk full during a backup | P7 | covered | `test_maintenance.py::TestBackupCore::test_insufficient_disk_space_aborts_before_starting` |
| 6.7 | NVML unavailable or raising mid-run | P5 | covered | `test_system_health.py::TestReadGpus::test_no_nvml_bindings_returns_empty_list`, `test_nvml_init_failure_returns_empty_list` |
| 6.8 | `psutil` raising on a single reading | P5 | covered | `test_system_health.py::TestHealthLiveEndpoint::test_single_sensor_unavailable_does_not_fail_the_endpoint` |
| 6.9 | Snapshot root unwritable at startup | P1 | uncovered | **Confirmed unimplemented, not just untested** — no startup writability check exists anywhere in the codebase. **F23** |
| 6.10 | Rate-limiter key dictionary growth pruned | P2 | covered | `test_rate_limit.py::TestSlidingWindowLimiter::test_expired_keys_are_pruned_not_retained` |
| 6.11 | WebSocket queue overflow closes only that connection | P3 | covered | `test_realtime.py::test_full_queue_closes_only_the_slow_connection` |
| 6.12 | Many simultaneous WebSocket connections; limit enforced | P3 | covered | `test_realtime.py::test_per_user_connection_limit_rejects_extra_but_keeps_established`, `test_total_connection_limit_rejects_extra_from_any_user` |
| 6.13 | Client disconnecting mid-CSV-stream | P6 | uncovered | No test simulates a client disconnect during `StreamingResponse`; no assertion of generator closure or session release. **F26** |
| 6.14 | Backend restart with export jobs `processing` | P6 | covered | `test_exports.py::TestJobRestart::test_interrupted_jobs_are_reset_to_queued_and_returned`, `test_a_recovered_job_can_still_be_processed_to_completion` |
| 6.15 | Backend restart mid-cooldown | P4 | covered | `test_camera_reconciliation.py::TestReconcileCameraDesiredStates::test_recomputes_across_all_active_cameras` + `TestSchedulePendingCooldowns::test_registers_one_date_triggered_job_per_camera` |
| 6.16 | Backend restart with active snoozes | P4 | covered | `test_snoozes.py::TestReconcileSnoozes::test_clears_expired_and_returns_pending` |
| 6.17 | FTS5 unavailable in the SQLite build; falls back to `LIKE`, logged | P8 | covered | `test_help.py::TestFtsFallback::test_like_search_used_when_fts5_table_is_unavailable` |
| 6.18 | Restore failing at the readiness gate; automatic rollback | P7 | covered | `test_maintenance.py::TestRestoreCore::test_readiness_failure_triggers_rollback_flow` |
| 6.19 | AI engine down for an extended period | P4, P5 | partial | Cameras present `Unresponsive` and `sample_camera_count: 0` both covered via 200 responses; no test asserts bounded/non-runaway logging under sustained silence |

## 7. State machine exhaustiveness

Not individually numbered in `14_EDGE_CASES.md` (a 4×4 transition table plus prose requirements);
split here into checkable units.

| Row | Case | Package | Status | Evidence |
|---|---|---|---|---|
| 7.illegal-transitions | All 12 illegal ordered pairs (incl. self-transitions) rejected | P4 | covered | `test_alerts.py::TestStateMachineExhaustiveness::test_illegal_transition_rejected` (8 route-reachable pairs, 409) + `test_no_route_can_reopen_a_terminal_incident_to_unverified` (remaining 4, no route exists) |
| 7.legal-actor-timestamp-stamping | Correct `verified_by`/`closed_by` per §10.1 for all 4 legal transitions | P4 | covered | `test_alerts.py::TestAlertTransitions` — one test per transition |
| 7.legal-audit-action | Audit action correct for all 4 legal transitions | P4 | partial | Never asserted by directly querying `audit_log`; action asserted only via WS broadcast payload, and only for RESOLVE/CORRECTION. CONFIRM and immediate DISMISS action values never asserted. **F28** |
| 7.legal-timestamps-immutable | `detected_at`/`created_at` never modified by a transition | P4 | uncovered | No test captures these before a transition and re-asserts unchanged after. Safe by construction (`transition()` never touches them). **F28** |
| 7.legal-snooze-cleared | Snooze fields cleared on any legal transition | P4 | uncovered | No test combines an active snooze with a transition call. Safe by construction. **F28** |
| 7.legal-camera-desired-state | Camera desired state matches §10.2 table for all 4 legal transitions | P4 | covered | `test_alerts.py::TestAlertCameraStatusSideEffects` — confirm/dismiss/correction/resolve all covered |
| 7.terminal-no-reopen-no-edit-delete | Terminal states have no reopen/edit/delete API | P4 | partial | The no-reopen check walks `openapi.json` but only inspects POST subroutes, `continue`ing past any other method — wouldn't catch a future PUT/PATCH/DELETE route; today's absence confirmed only by source inspection |

## 8. Authentication attacks

| Row | Case | Package | Status | Evidence |
|---|---|---|---|---|
| 8.1 | JWT with `alg: none` | P2 | covered | `test_auth.py::TestJWTVerification::test_alg_none_rejected` |
| 8.2 | JWT signed with a different key | P2 | covered | `test_auth.py::TestJWTVerification::test_wrong_signing_key_rejected` |
| 8.3 | JWT with wrong `iss` or `aud` | P2 | covered | `test_auth.py::TestJWTVerification::test_wrong_issuer_rejected`, `test_wrong_audience_rejected` |
| 8.4 | JWT missing the `sid` claim | P2 | covered | `test_auth.py::TestJWTVerification::test_missing_sid_claim_rejected` |
| 8.5 | JWT whose `sid` belongs to a different `sub` | P2 | covered | `test_auth.py::TestJWTVerification::test_sid_belonging_to_different_sub_rejected` |
| 8.6 | Valid JWT, session row deleted/revoked/expired | P2 | covered | `test_auth.py::TestSessionAuthority::test_deleted_session_row_rejected`, `test_revoked_session_row_rejected`, `test_expired_row_with_unexpired_jwt_rejected` |
| 8.7 | Empty or malformed cookie value | P2 | covered | `test_auth.py::TestJWTVerification::test_empty_cookie_value_returns_401_not_500`, `test_malformed_cookie_value_returns_401_not_500` |
| 8.8 | Login timing for unknown vs known username | P2 | covered | `test_auth.py::TestLogin::test_unknown_username_still_runs_a_real_password_verification` |
| 8.9 | Response body identical for unknown user / wrong password / inactive account | P2 | covered | `test_auth.py::TestLogin::test_inactive_account_returns_identical_body_to_wrong_password` |
| 8.10 | Role escalation via `PATCH /api/users/me` | P2 | covered | `test_auth.py::TestRBAC::test_role_escalation_via_update_my_profile_ignored` |
| 8.11 | Operator hitting every admin route → 403 before payload processing | P2 | partial | Broad but scattered per-route coverage across several files; no exhaustive/parametrized "every admin route" test, and no test proves 403 fires before payload processing. **F25** |
| 8.12 | Cookie-auth unsafe method with a foreign `Origin` | P2 | covered | `test_auth.py::TestOriginValidation::test_foreign_origin_on_unsafe_method_rejected` |
| 8.13 | Missing `x-api-key` on `/api/internal/*` | P1 | covered | `test_internal.py::TestInternalAuth::test_internal_routes_reject_missing_api_key` — 401, not 422 |
| 8.14 | Wrong `x-api-key`, constant-time comparison | P1 | partial | 401 rejection confirmed; `secrets.compare_digest` is genuinely used but no test pins that mechanism down. **F25** |
| 8.15 | Password reset does not leak the old hash or the new password into audit `detail` | P2 | covered | `test_audit.py::TestAuditRedaction::test_password_reset_does_not_leak_new_password` + `test_password_token_apikey_url_and_paths_never_survive` |
| 8.16 | Last-admin guards: demote, deactivate, delete, self-delete — refused and audited denied | P2 | partial | Refusal covered for all 4; "audited denied" verified for only 2 of 4 (demote, self-delete). **F25** |

## 9. Soft delete and referential edges

| Row | Case | Package | Status | Evidence |
|---|---|---|---|---|
| 9.1 | Incident verified by a since-deactivated user | P4, P6 | covered | `test_reports.py::TestHostileAndDegenerateInput::test_export_renders_deactivated_users_name_from_the_fk` — export path; alert-detail endpoint uses the same FK mechanism |
| 9.2 | Audit row for a since-renamed user | P2 | covered | `test_audit.py::TestSinceRenamedUserSnapshot::test_audit_row_keeps_the_username_at_time_of_action` |
| 9.3 | Creating a camera reusing a soft-deleted camera's name | P1, P4 | covered | `test_cameras.py::TestCreateCamera::test_reuses_soft_deleted_camera_name` + `test_schema.py::TestPartialUniqueIndexes::test_reusing_a_soft_deleted_cameras_name_succeeds` |
| 9.4 | Creating a camera reusing a soft-deleted camera's `channel_id` | P1, P4 | covered | `test_cameras.py::TestCreateCamera::test_reuses_soft_deleted_camera_channel_id` + `test_schema.py::TestPartialUniqueIndexes::test_reusing_a_soft_deleted_cameras_channel_id_succeeds` |
| 9.5 | Two soft-deleted cameras with the same name | P1 | covered | `test_schema.py::TestPartialUniqueIndexes::test_two_soft_deleted_cameras_can_share_a_name` |
| 9.6 | Soft-deleting a camera with an open incident | P4 | covered | `test_cameras.py::TestDeleteCamera::test_refuses_with_open_incident` — `400 PRECONDITION_FAILED` |
| 9.7 | Soft-deleted camera still appearing in historical analytics | P6 | partial | Export path covered (`test_reports.py::TestHostileAndDegenerateInput::test_soft_deleted_camera_still_appears_in_export_history`); the analytics dashboard/performance endpoints have no equivalent test |
| 9.8 | Soft-deleted camera excluded from KPI counts | P5 | covered | `test_cameras.py::TestGetAllCameras::test_soft_deleted_camera_excluded_from_kpis` |
| 9.9 | Hard-deleting a referenced user | P1 | covered | `test_schema.py::TestForeignKeyEnforcement::test_hard_deleting_a_referenced_user_is_blocked` — raw DELETE bypassing ORM, `ON DELETE RESTRICT` |
| 9.10 | Deleting a user cascades their `alarm_settings` | P1 | covered | `test_schema.py::TestCascadeDeletes::test_deleting_a_user_cascades_their_alarm_settings` |

## 10. Idempotency and replay

| Row | Case | Package | Status | Evidence |
|---|---|---|---|---|
| 10.1 | Same `source_event_id` twice, sequentially | P4 | covered | `test_internal.py::TestReceiveAiAlertV2::test_v2_idempotent_retry_returns_200_same_row` |
| 10.2 | Same `source_event_id` after the incident was resolved | P4 | covered | `test_internal.py::TestReceiveAiAlertV2::test_v2_retry_after_resolved_returns_resolved_unchanged` |
| 10.3 | Same `source_event_id` from a different `camera_id` | P4 | covered | `test_internal.py::TestReceiveAiAlertV2::test_v2_second_source_event_from_different_camera_is_409` — actually a distinct id targeting a camera with an open incident (cross-camera conflict), matching the row's "most likely 409" resolution |
| 10.4 | `PUT /api/settings/alarm` twice with identical values | P4 | covered | `test_settings.py::TestUpdateAlarmSettings::test_no_op_save_writes_no_redundant_audit_row` + `test_full_replacement_roundtrip` |
| 10.5 | Logout twice | P2 | covered | `test_auth.py::TestLogout::test_logout_twice_both_return_204` |
| 10.6 | Re-seeding help content with no file changes | P8 | covered | `test_help.py::TestIdempotentSeeding::test_reseed_unchanged_writes_nothing` |
| 10.7 | Re-running the hourly rollup | P5 | covered | `test_system_health.py::TestRollupHour::test_rerunning_is_idempotent` |
| 10.8 | Duplicate `RE_ALARM` attempt from two processes | P4 | covered | `test_snoozes.py::TestClearExpiredSnooze::test_duplicate_call_after_clearing_is_a_no_op` — sequential simulation of two processes via separate sessions against the same engine |
| 10.9 | Client receiving a duplicate `event_id` after reconnect | P3 | covered | `test_realtime.py::test_event_ids_are_unique_across_broadcasts` — proves per-emission uniqueness, not an actual reconnect scenario |

---

## Coverage gaps that are acceptable

Per `14_EDGE_CASES.md`'s own pre-declared list — none of the rows above needed this status, since
none of them individually *are* one of these categories (they're blanket exclusions, not rows):

- **Multi-worker behavior.** D-005 locks a single Uvicorn worker; out of scope.
- **Multi-instance / broker fan-out.** D-008 rejects Redis/Kafka/cross-instance delivery for this deployment.
- **Non-SQLite databases.** The backend is deliberately SQLite-bound.
- **Model accuracy.** AI-owner evidence per D-012.
- **Browser and UI behavior.** Frontend-owned.
- **Real 8×L4 hardware capacity.** Unvalidatable on the demo laptop; stays `Needs Evidence` (D-009).

## New findings surfaced by this register

All recorded in `be_audit/00_FINDINGS.md`, left `open` (this pack is register-building, not a fix
pass — see `A5_edge_cases.md`'s own scope):

- **F22** (Med) — 3.5: analytics performance breakdown drops cameras with zero incidents. Confirmed bug.
- **F23** (Med) — 6.9: no startup writability check for `SNAPSHOT_ROOT`. Confirmed unimplemented.
- **F24** (Med) — 1.6, 1.18: AI-ingestion race claims proven only sequentially, not with genuine parallelism.
- **F25** (Low-Med) — 8.11, 8.14, 8.16: auth/authz claims correct today but regression-prone, untested.
- **F26** (Low-Med) — 6.13: CSV stream-disconnect cleanup unverified.
- **F27** (Low-Med) — 2.1, 2.2: pagination boundaries enforced only by undeflected `Query()` declarations.
- **F28** (Low-Med) — 7: three incident-transition side-effects (audit action, timestamp immutability, snooze clearing) unverified for some/all legal transitions.
