# ADAS Backend — Frozen Contracts

> **This is not a work package.** It is the shared reference every package implements against.
> Read it in full before starting any package. Derived from `be_decisions_review.md` D-001…D-012.
>
> If you find a contradiction between this document and a locked decision, **stop and report it.**

---

## 1. Global conventions

### 1.1 Time

- Every stored timestamp is **UTC-aware**, written through the `UtcDateTime` SQLAlchemy
  `TypeDecorator` introduced in P1. SQLite does not preserve tzinfo from `DateTime(timezone=True)` —
  that is why a custom type is mandatory (D-005).
- Every API timestamp is **ISO 8601 UTC with an explicit offset**: `2026-07-12T10:30:05+00:00`.
- Query parameters accepting datetimes must accept an offset. A **naive** datetime in a query
  parameter is interpreted as UTC, and this is documented in the OpenAPI description.
- Clients localize for display. The backend never formats a local time except inside a generated PDF,
  where D-010 requires both the UTC timestamp and a configured local-display timestamp.
- `datetime.now()` is banned. Always `datetime.now(UTC)`.

### 1.2 Naming

- Python: snake_case. JSON: snake_case (matches what the frontend already consumes).
- Table names: singular snake_case — `user`, `camera`, `detection_log`, `auth_session`, `audit_log`,
  `alarm_settings`, `sys_health_raw`, `sys_health_hourly`, `export_job`, `help_article`.
  *(The current code produces SQLModel's default `detectionlog` / `systemhealthraw`. P1 sets explicit
  `__tablename__` values. The dev DB is disposable, so this is a free rename.)*
- Backend imports are absolute (`from app.services.incidents import …`), never relative.

### 1.3 Error envelope

Every non-2xx response uses this shape (already implemented in `backend/app/main.py`, keep it):

```json
{
  "detail": "Human readable message.",
  "code": "MACHINE_READABLE_CODE",
  "errors": [{ "loc": ["body", "volume"], "msg": "…", "type": "…" }]
}
```

`errors` is present only for `422` validation failures.

**Stable error codes.** Do not invent new ones without adding them here.

| Code | Status | Meaning |
|---|---|---|
| `VALIDATION_ERROR` | 422 | Pydantic request validation failed |
| `AUTH_REQUIRED` | 401 | No session cookie, or it failed validation |
| `AUTH_EXPIRED` | 401 | Session expired — client should return to login |
| `AUTH_REVOKED` | 401 | Session was revoked (logout, password change, role change, deactivation) |
| `AUTH_INVALID_CREDENTIALS` | 401 | Login failure. **Generic** — never distinguishes unknown user / wrong password / inactive account |
| `AUTH_RATE_LIMITED` | 429 | Login rate limit hit. Includes `Retry-After` |
| `FORBIDDEN` | 403 | Authenticated but not authorized for this action |
| `ORIGIN_REJECTED` | 403 | Cookie-authenticated unsafe method with a disallowed `Origin` |
| `NOT_FOUND` | 404 | Target does not exist, is soft-deleted, or is not visible to the caller |
| `CONFLICT_STATE` | 409 | Expected-state transition lost the race. Body carries current state — see §5.3 |
| `CONFLICT_DUPLICATE` | 409 | Unique constraint (camera name, channel id, username) |
| `CONFLICT_BUSY` | 409 | An exclusive operation is already running (backup, restore) |
| `PRECONDITION_FAILED` | 400 | Business rule rejected the request (last admin, self-delete, snooze on a non-`Unverified` incident) |
| `PAYLOAD_TOO_LARGE` | 413 | Synchronous export exceeded the configured row limit. Body names the job endpoint |
| `TEMPORARILY_UNAVAILABLE` | 503 | SQLite lock timeout, or a required subsystem is down |
| `INTERNAL_SERVER_ERROR` | 500 | Unhandled |

### 1.4 Pagination

List endpoints use `limit` (1–100) + `offset`, and return a total alongside the page:

```json
{ "total_filtered": 137, "items": [] }
```

The existing response models keep their current field names (`users`, `cameras`, `logs`) so the
frontend does not churn. New list endpoints use `items`.

### 1.5 Sorting

D-010 requires list and export routes to share sorting. `sort_by` accepts only allowlisted field
names per resource; `sort_order` accepts only `asc` / `desc`. Anything else is `422`. Clients never
supply raw SQL.

### 1.6 Secrets that must never leave the backend

Never log, audit, serialize, or include in any response, PDF, CSV, or error message:

- password hashes, plaintext passwords
- JWTs, cookie values, `INTERNAL_API_KEY`, `SECRET_KEY`
- **the resolved RTSP URL** and any `DSS_*` credential
- absolute filesystem paths (`SNAPSHOT_ROOT`, `BACKUP_DIR`, `EXPORT_DIR`)
- raw exception tracebacks

The resolved RTSP URL is transmitted **only** in the internal heartbeat response (§6.2), which is
`INTERNAL_API_KEY`-authenticated. It must be redacted in every log line.

---

## 2. Canonical enums

```python
class UserRole(StrEnum):
    ADMIN = "Admin"
    OPERATOR = "Operator"

class DetectionStatus(StrEnum):
    UNVERIFIED = "Unverified"
    ONGOING    = "Ongoing"
    DISMISSED  = "Dismissed"
    CLEARED    = "Cleared"

class ConnectionStatus(StrEnum):        # observed, AI-reported
    CONNECTED    = "Connected"
    DISCONNECTED = "Disconnected"
    RECONNECTING = "Reconnecting"
    UNRESPONSIVE = "Unresponsive"

class AIStatus(StrEnum):                # observed, AI-reported
    ACTIVE       = "Active"
    INACTIVE     = "Inactive"
    PAUSED       = "Paused"
    UNRESPONSIVE = "Unresponsive"

class DesiredAIState(StrEnum):          # desired, backend-owned  (D-003)
    ACTIVE   = "Active"
    PAUSED   = "Paused"
    INACTIVE = "Inactive"

class DesiredStateReason(StrEnum):
    INCIDENT = "incident"
    COOLDOWN = "cooldown"
    DISABLED = "disabled"

class AuditResult(StrEnum):
    SUCCESS = "success"
    DENIED  = "denied"
    FAILURE = "failure"
```

`Closed` is **not** a status. Where the paper says "Closed", it means a terminal `Cleared` or
`Dismissed` incident (D-002). The `closed_by_id` / `closed_at` column names stay.

---

## 3. Target database schema

All tables. P1 creates every one of them at once — do not add them piecemeal, because D-005's
"one clean initial migration" strategy in P9 depends on the schema being stable by then.

Notation: `UtcDateTime` = the custom type from P1. All FKs are `ON DELETE RESTRICT` because users and
cameras are **soft-deleted**, never physically removed (D-005), except `alarm_settings.user_id` which
is `ON DELETE CASCADE`.

### 3.1 `user`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `user_id` | INTEGER | PK | autoinc | |
| `username` | TEXT | no | | UNIQUE, indexed, 3–20, stripped |
| `first_name` | TEXT | no | | 1–20, stripped |
| `last_name` | TEXT | no | | 1–20, stripped |
| `role` | TEXT | no | | CHECK IN (`Admin`,`Operator`) |
| `password_hash` | TEXT | no | | Argon2id |
| `is_active` | BOOLEAN | no | `1` | soft delete |
| `created_at` | UtcDateTime | no | now | |
| `updated_at` | UtcDateTime | no | now, onupdate | |
| `password_changed_at` | UtcDateTime | yes | | |
| `last_login` | UtcDateTime | yes | | |

### 3.2 `auth_session` — NEW (D-006)

| Column | Type | Null | Notes |
|---|---|---|---|
| `session_id` | TEXT | PK | UUID4, becomes the JWT `sid` |
| `user_id` | INTEGER | no | FK `user`, indexed |
| `created_at` | UtcDateTime | no | |
| `expires_at` | UtcDateTime | no | indexed |
| `revoked_at` | UtcDateTime | yes | |
| `revocation_reason` | TEXT | yes | CHECK IN (`logout`,`password_change`,`password_reset`,`role_change`,`account_disabled`,`admin_revoke`,`expired_cleanup`) |
| `user_agent` | TEXT | yes | truncated to 256 chars |
| `source_ip` | TEXT | yes | normalized |

Index: `(user_id, revoked_at)` for the cascade-revocation query.

### 3.3 `camera` — desired/observed split (D-003)

**Backend-owned desired state.** Only routes write these.

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `camera_id` | INTEGER | PK | | |
| `camera_name` | TEXT | no | | 1–100, stripped |
| `channel_id` | INTEGER | no | | CHECK > 0 |
| `is_active` | BOOLEAN | no | `1` | soft delete |
| `is_enabled` | BOOLEAN | no | `1` | operator toggle |
| `desired_ai_state` | TEXT | no | `Inactive` | CHECK IN (`Active`,`Paused`,`Inactive`) |
| `desired_state_reason` | TEXT | yes | | CHECK IN (`incident`,`cooldown`,`disabled`) |
| `cooldown_until` | UtcDateTime | yes | | persisted 60s deadline |
| `config_version` | INTEGER | no | `1` | bumped on any AI-relevant change |
| `created_at` / `updated_at` | UtcDateTime | no | | |

**AI-owned observed state.** Only heartbeat processing writes these.

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `connection_status` | TEXT | no | `Disconnected` | CHECK IN the 4 values |
| `ai_status` | TEXT | no | `Inactive` | CHECK IN the 4 values |
| `applied_config_version` | INTEGER | yes | | last version the engine confirmed |
| `last_heartbeat_at` | UtcDateTime | yes | | staleness source |
| `measured_fps` | REAL | yes | | |
| `inference_latency_ms` | REAL | yes | | |
| `last_error_code` | TEXT | yes | | sanitized |
| `last_error_message` | TEXT | yes | | sanitized, ≤256 chars, never credential-bearing |

**Indexes**

```sql
CREATE UNIQUE INDEX ux_camera_name_active    ON camera(lower(camera_name)) WHERE is_active = 1;
CREATE UNIQUE INDEX ux_camera_channel_active ON camera(channel_id)         WHERE is_active = 1;
CREATE INDEX ix_camera_active_state ON camera(is_active, is_enabled, connection_status, ai_status);
```

The partial unique indexes are what D-005 means by "active-only uniqueness … enforced by SQLite, not
only Python validation". They also fix a live bug: today `camera_name` is DB-unique across *all* rows
while the route only pre-checks active rows, so reusing a soft-deleted camera's name raises an
unhandled `IntegrityError` → 500.

### 3.4 `detection_log`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `log_id` | INTEGER | PK | | human-facing accident number |
| `source_event_id` | TEXT | no | | **UNIQUE.** AI-generated UUID (v2) or backend-generated (v1 legacy) |
| `camera_id` | INTEGER | no | | FK `camera`, indexed |
| `detected_at` | UtcDateTime | no | | indexed |
| `snapshot_key` | TEXT | no | | relative key, see §7 |
| `confidence_score` | REAL | no | | CHECK 0.0–1.0 |
| `detection_status` | TEXT | no | `Unverified` | CHECK IN the 4 values |
| `verified_by_id` | INTEGER | yes | | FK `user` |
| `verified_at` | UtcDateTime | yes | | |
| `closed_by_id` | INTEGER | yes | | FK `user` |
| `closed_at` | UtcDateTime | yes | | |
| `snoozed_at` | UtcDateTime | yes | | |
| `snoozed_until` | UtcDateTime | yes | | |
| `snoozed_by_id` | INTEGER | yes | | FK `user` |
| `created_at` / `updated_at` | UtcDateTime | no | | server-managed (D-002) |

**Indexes**

```sql
CREATE UNIQUE INDEX ux_detection_source_event ON detection_log(source_event_id);
CREATE UNIQUE INDEX ux_detection_open_camera  ON detection_log(camera_id)
       WHERE detection_status IN ('Unverified','Ongoing');   -- at most one open incident per camera
CREATE INDEX ix_detection_status_time  ON detection_log(detection_status, detected_at);
CREATE INDEX ix_detection_camera_time  ON detection_log(camera_id, detected_at);
CREATE INDEX ix_detection_verified_by  ON detection_log(verified_by_id);
CREATE INDEX ix_detection_closed_by    ON detection_log(closed_by_id);
CREATE INDEX ix_detection_snooze_due   ON detection_log(snoozed_until) WHERE snoozed_until IS NOT NULL;
```

### 3.5 `alarm_settings` — NEW (D-004)

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `alarm_settings_id` | INTEGER | PK | | |
| `user_id` | INTEGER | no | | **UNIQUE**, FK `user` ON DELETE CASCADE |
| `alarm_sound` | TEXT | no | `default` | must be in `ALARM_SOUND_KEYS` |
| `volume` | INTEGER | no | `80` | CHECK 0–100 |
| `snooze_duration` | INTEGER | no | `30` | CHECK 15–60 seconds |
| `created_at` / `updated_at` | UtcDateTime | no | | |

Created with every new account; backfilled for existing accounts.

### 3.6 `audit_log` — NEW (D-007)

| Column | Type | Null | Notes |
|---|---|---|---|
| `audit_id` | INTEGER | PK | |
| `actor_type` | TEXT | no | CHECK IN (`user`,`system`) |
| `user_id` | INTEGER | yes | FK `user` — null for failed logins and system actions |
| `username` | TEXT | yes | actor snapshot, survives later renames |
| `role` | TEXT | yes | actor snapshot |
| `action` | TEXT | no | CHECK IN the §8 catalog |
| `target_type` | TEXT | yes | e.g. `incident`, `camera`, `user`, `backup`, `session` |
| `target_ref` | TEXT | yes | **TEXT**, so it holds numeric ids, filenames, and session UUIDs alike |
| `result` | TEXT | no | CHECK IN (`success`,`denied`,`failure`) |
| `detail` | TEXT | yes | sanitized JSON object |
| `request_id` | TEXT | yes | correlates with operational logs |
| `source_ip` | TEXT | yes | |
| `created_at` | UtcDateTime | no | indexed |

**Immutability triggers — required by D-007 and NFR-21:**

```sql
CREATE TRIGGER trg_audit_log_no_update BEFORE UPDATE ON audit_log
BEGIN SELECT RAISE(ABORT, 'audit_log is append-only'); END;

CREATE TRIGGER trg_audit_log_no_delete BEFORE DELETE ON audit_log
BEGIN SELECT RAISE(ABORT, 'audit_log is append-only'); END;
```

Indexes: `(created_at)`, `(action, created_at)`, `(user_id, created_at)`, `(target_type, target_ref)`.
No pruning, ever.

### 3.7 `sys_health_raw` / `sys_health_hourly` — reshaped (D-009)

`sys_health_raw` — one row every 5 minutes, retained 48 hours:

| Column | Type | Null | Notes |
|---|---|---|---|
| `sys_health_id` | INTEGER | PK | |
| `created_at` | UtcDateTime | no | indexed |
| `cpu_usage` | REAL | no | 0–100 |
| `ram_usage` | REAL | no | 0–100 |
| `gpu_usage_avg` | REAL | yes | mean of available GPUs |
| `gpu_temp_max` | REAL | yes | max device temp |
| `cpu_temp` | REAL | yes | **null on Windows** |
| `gpu_mem_pct_max` | REAL | yes | worst-device VRAM % |

`sys_health_hourly` — one row per UTC hour, retained 30 days:

| Column | Type | Null | Notes |
|---|---|---|---|
| `hourly_id` | INTEGER | PK | |
| `hour_start` | UtcDateTime | no | **UNIQUE**, indexed — the idempotency key |
| `avg_cpu_usage`, `avg_ram_usage` | REAL | no | |
| `avg_gpu_usage` | REAL | yes | |
| `avg_cpu_temp`, `peak_cpu_temp` | REAL | yes | |
| `peak_gpu_temp` | REAL | yes | |
| `avg_gpu_mem_pct`, `peak_gpu_mem_pct` | REAL | yes | |
| `sample_count` | INTEGER | no | makes incomplete hours visible |

Disk, uptime, FPS, and inference latency are **live-only** — never persisted.

### 3.8 `export_job` — NEW (D-010)

| Column | Type | Null | Notes |
|---|---|---|---|
| `job_id` | TEXT | PK | UUID4 |
| `requested_by_id` | INTEGER | no | FK `user` |
| `report_type` | TEXT | no | CHECK IN (`incidents`,`dashboard`,`performance`,`audit`,`retraining`) |
| `format` | TEXT | no | CHECK IN (`csv`,`pdf`,`zip`) |
| `filters_json` | TEXT | yes | sanitized |
| `sort_json` | TEXT | yes | |
| `status` | TEXT | no | CHECK IN (`queued`,`processing`,`completed`,`failed`,`expired`) |
| `progress_current` | INTEGER | no | default 0 |
| `progress_total` | INTEGER | yes | |
| `artifact_path` | TEXT | yes | under `EXPORT_DIR`, never returned to a client |
| `artifact_bytes` | INTEGER | yes | |
| `failure_category` | TEXT | yes | safe category, never a traceback |
| `created_at`, `started_at`, `completed_at`, `expires_at` | UtcDateTime | | |

### 3.9 `help_article` — NEW (FR-20)

| Column | Type | Null | Notes |
|---|---|---|---|
| `article_id` | INTEGER | PK | |
| `slug` | TEXT | no | UNIQUE |
| `title` | TEXT | no | |
| `category` | TEXT | no | |
| `roles` | TEXT | no | JSON array, e.g. `["Admin","Operator"]` |
| `summary` | TEXT | yes | |
| `body_markdown` | TEXT | no | |
| `sort_order` | INTEGER | no | default 0 |
| `is_faq` | BOOLEAN | no | default 0 — drives the "Top FAQs" empty state |
| `content_hash` | TEXT | no | idempotent reseeding |
| `created_at` / `updated_at` | UtcDateTime | no | |

Plus an FTS5 external-content virtual table `help_article_fts` over `title`, `summary`,
`body_markdown`, kept in sync by insert/update/delete triggers.

### 3.10 Restore state is **not** a table

A restore replaces `adas.db`, so anything recorded in the database about the restore is destroyed by
the restore itself. Restore progress and outcome live in a JSON file beside the backups
(`BACKUP_DIR/restore_state.json`). See P7.

---

## 4. Configuration inventory

Every setting, with its default. P1 gives everything a safe default so a missing `.env` key no longer
prevents the app from importing.

| Setting | Type | Default | Used by |
|---|---|---|---|
| `ENVIRONMENT` | `development`\|`production` | `development` | cookie flags, docs exposure |
| `LOG_LEVEL` | str | `INFO` | logging |
| `SQL_ECHO` | bool | `false` | replaces the hardcoded `echo=True` |
| `SECRET_KEY` | SecretStr | *required* | JWT |
| `ALGORITHM` | str | `HS256` | JWT |
| `JWT_ISSUER` | str | `adas-backend` | D-006 required claim |
| `JWT_AUDIENCE` | str | `adas-dashboard` | D-006 required claim |
| `SESSION_LIFETIME_MINUTES` | int | `480` | 8h absolute (NFR-19, TC-S-203) |
| `SESSION_COOKIE_NAME` | str | `adas_session` | |
| `SESSION_COOKIE_SECURE` | bool | `true` in production | false only for localhost dev |
| `CORS_ORIGINS` | list[str] | `["http://localhost:5173","http://127.0.0.1:5173"]` | replaces the hardcode in `main.py` |
| `LOGIN_RATE_LIMIT_ATTEMPTS` | int | `10` | per window |
| `LOGIN_RATE_LIMIT_WINDOW_SECONDS` | int | `300` | |
| `DEFAULT_ADMIN_PASSWORD` | **SecretStr** | *required* | bootstrap admin |
| `INTERNAL_API_KEY` | SecretStr | *required* | AI engine |
| `DATABASE_URL` | str | `sqlite:///./adas.db` | anchored to repo root by the existing validator |
| `SQLITE_BUSY_TIMEOUT_MS` | int | `5000` | D-005 |
| `SNAPSHOT_ROOT` | Path | `<repo>/ai_engine/snapshots` | evidence store |
| `LEGACY_SNAPSHOT_DIR` | Path | `<repo>/ai_engine/snapshots` | flat legacy filenames |
| `BACKUP_DIR` | Path | `<repo>/var/backups` | D-011 |
| `EXPORT_DIR` | Path | `<repo>/var/exports` | D-010, outside any static mount |
| `ARCHIVE_DIR` | Path | `<repo>/var/archive` | weekly air-gapped archive staging |
| `RTSP_URL_TEMPLATE` | str | `rtsp://localhost:8554/channel{channel_id}` | see §7.2 |
| `DSS_IP` / `DSS_PORT` / `DSS_USERNAME` / `DSS_PASS` | optional | `None` | consumed only by `RTSP_URL_TEMPLATE` |
| `ALARM_SOUND_KEYS` | list[str] | `["default"]` | D-004 validation allowlist |
| `SNOOZE_MIN_SECONDS` / `SNOOZE_MAX_SECONDS` | int | `15` / `60` | |
| `DISMISS_COOLDOWN_SECONDS` | int | `60` | FR-11 |
| `HEARTBEAT_STALE_SECONDS` | int | `10` | D-003, D-009 |
| `HEALTH_SAMPLE_SECONDS` | int | `5` | live collector |
| `HEALTH_PERSIST_SECONDS` | int | `300` | raw rows |
| `HEALTH_RAW_RETENTION_HOURS` | int | `48` | |
| `HEALTH_HOURLY_RETENTION_DAYS` | int | `30` | |
| `GPU_TEMP_CRITICAL_C` | float | `85` | D-009 |
| `RAM_CRITICAL_PCT` | float | `95` | |
| `DISK_WARNING_PCT` / `DISK_CRITICAL_PCT` | float | `80` / `90` | |
| `EXPORT_PDF_MAX_ROWS` | int | `10000` | D-010 |
| `EXPORT_CSV_MAX_ROWS` | int | `50000` | |
| `EXPORT_ARTIFACT_TTL_HOURS` | int | `72` | |
| `WS_MAX_CONNECTIONS_TOTAL` | int | `50` | D-008, config-driven |
| `WS_MAX_CONNECTIONS_PER_USER` | int | `5` | |
| `WS_QUEUE_MAXSIZE` | int | `100` | bounded per-connection queue |
| `WS_SEND_TIMEOUT_SECONDS` | float | `5` | |
| `BACKUP_DAILY_RETENTION` | int | `30` | D-011 |
| `BACKUP_MANUAL_RETENTION` | int | `10` | |
| `MAINTENANCE_HOUR_LOCAL` | int | `3` | 3 AM restart window (NFR-16) |

---

## 5. REST API inventory

`Auth` column: **S** = valid session cookie; **A** = session + `Admin` role; **K** = `x-api-key`;
**—** = public.

### 5.1 Authentication — `/api/auth`

| M | Path | Auth | Pkg | Notes |
|---|---|---|---|---|
| POST | `/api/auth/login` | — | P2 | `OAuth2PasswordRequestForm`. **CHANGED:** no longer returns a token. Sets the `HttpOnly` session cookie and returns `{"user": UserRead}`. `Cache-Control: no-store`. Rate limited. |
| POST | `/api/auth/logout` | S | P2 | **NEW.** Revokes the session, closes its WebSockets, clears the cookie. `204`. |

`GET /api/users/me` remains the authenticated profile endpoint.

### 5.2 Users — `/api/users`

Paths and semantics unchanged; every mutation now writes an audit row and, where D-006 requires,
cascades session revocation.

| M | Path | Auth | Revokes sessions? |
|---|---|---|---|
| GET | `/api/users/me` | S | |
| PATCH | `/api/users/me` | S | no — identity is `user_id` |
| PATCH | `/api/users/me/password` | S | **yes**, all sessions for that user |
| GET | `/api/users/` | A | |
| POST | `/api/users/` | A | also creates `alarm_settings` |
| PATCH | `/api/users/{user_id}` | A | **yes** on role change or deactivation |
| POST | `/api/users/{user_id}/reset-password` | A | **yes** |
| DELETE | `/api/users/{user_id}` | A | **yes** |

Existing guards stay: cannot demote, deactivate, or delete the last active admin; cannot delete self.

### 5.3 Alerts / incidents — `/api/alerts`

| M | Path | Auth | Pkg | Notes |
|---|---|---|---|---|
| GET | `/api/alerts/` | S | P6 | Filters: `start_date`, `end_date`, `status[]`, `camera_id[]`, `user_id[]`, `search`, `sort_by`, `sort_order`, `limit`, `offset` |
| GET | `/api/alerts/export` | S | P6 | `?format=csv\|pdf`, defaults `csv`. Same filters, streamed |
| GET | `/api/alerts/{log_id}` | S | P4 | **CHANGED:** missing log is now `404`, not `400` |
| GET | `/api/alerts/{log_id}/snapshot` | S | P4 | **NEW.** Replaces the public `/snapshots` static mount |
| POST | `/api/alerts/{log_id}/confirm` | S | P4 | `Unverified → Ongoing` |
| POST | `/api/alerts/{log_id}/dismiss` | S | P4 | `Unverified → Dismissed` or `Ongoing → Dismissed` |
| POST | `/api/alerts/{log_id}/clear` | S | P4 | `Ongoing → Cleared` |
| POST | `/api/alerts/{log_id}/snooze` | S | P4 | **NEW.** Only on `Unverified`. Duration comes from the actor's saved settings — never from the request body |

**The `409 CONFLICT_STATE` body** — this exact shape drives the frontend's "already handled" modal
(D-002), so it is a contract, not an implementation detail:

```json
{
  "detail": "This incident was already handled by another operator.",
  "code": "CONFLICT_STATE",
  "current_status": "Ongoing",
  "handled_action": "ALERT_CONFIRM",
  "handled_by": "D. Sahagun",
  "handled_at": "2026-07-12T10:30:05+00:00"
}
```

### 5.4 Cameras — `/api/cameras`

| M | Path | Auth | Pkg | Notes |
|---|---|---|---|---|
| GET | `/api/cameras/` | S | P4 | **CHANGED response shape** — see §5.9 |
| POST | `/api/cameras/` | S | P4 | Bumps `config_version`. `IntegrityError` → `CONFLICT_DUPLICATE`, never a 500 |
| PATCH | `/api/cameras/{camera_id}` | S | P4 | Bumps `config_version` when an AI-relevant field changes. Enable/disable emits its own audit action |
| DELETE | `/api/cameras/{camera_id}` | S | P4 | Soft delete; sets `desired_ai_state=Inactive` |

Operators may perform all four — FR-02 grants Operators "camera status/config". This is a deliberate
decision, recorded in P2, not an oversight.

### 5.5 Analytics — `/api/analytics`

| M | Path | Auth | Pkg |
|---|---|---|---|
| GET | `/api/analytics/dashboard` | S | P6 — gains a `response_model` |
| GET | `/api/analytics/performance` | S | P6 — gains a `response_model` |
| GET | `/api/analytics/export/dashboard` | S | P6 — `?format=csv\|pdf` |
| GET | `/api/analytics/export/performance` | S | P6 — `?format=csv\|pdf` |

Domain rules (unchanged, keep them): accidents = `Ongoing` + `Cleared`; false positives =
`Dismissed`; `Unverified` excluded entirely; `precision = confirmed / (confirmed + dismissed)`,
returning **`null`** (never `0`) on zero division; global confidence averages are count-weighted.

### 5.6 Settings — `/api/settings`

| M | Path | Auth | Pkg |
|---|---|---|---|
| GET | `/api/settings/alarm` | S | P4 — side-effect free |
| PUT | `/api/settings/alarm` | S | P4 — full replacement, idempotent |

### 5.7 Audit — `/api/audit-logs`

| M | Path | Auth | Pkg |
|---|---|---|---|
| GET | `/api/audit-logs` | **A** | P2 — newest-first, filters: `action[]`, `user_id[]`, `result[]`, `target_type`, `target_ref`, `start_date`, `end_date`, `search` |
| GET | `/api/audit-logs/export` | **A** | P6 — `?format=csv\|pdf`, identical filters |

Operators have no audit access at all. Viewing is not audited; exporting is.

### 5.8 System — `/api/system` and `/healthz`

**Three separate router files**, one owner each, so P5 and P7 can run in parallel without editing the
same file. Do not consolidate them.

| M | Path | Auth | Router file | Pkg |
|---|---|---|---|---|
| GET | `/healthz/live` | — | `routes/system.py` | P1 — process responds |
| GET | `/healthz/ready` | — | `routes/system.py` | P1 — DB reachable + initialization complete |
| GET | `/api/system/health/live` | S | `routes/system_health.py` | P5 |
| GET | `/api/system/health/history?range=48h\|30d` | S | `routes/system_health.py` | P5 |
| GET | `/api/system/backups` | **A** | `routes/maintenance.py` | P7 |
| POST | `/api/system/backups` | **A** | `routes/maintenance.py` | P7 |
| POST | `/api/system/restores` | **A** | `routes/maintenance.py` | P7 — requires current admin password + backup id confirmation. `202` |
| GET | `/api/system/restores/latest` | **A** | `routes/maintenance.py` | P7 |

The URL prefixes stay as shown — `/api/system/...` for both health and maintenance. Only the Python
module boundary differs, and it exists purely to keep the packages independent.

Probes expose no telemetry and no configuration.

### 5.9 Camera list response — CHANGED shape (D-009)

```json
{
  "kpis":       { "total": 10, "enabled": 8, "network_connected": 7, "active_detection": 6 },
  "breakdowns": {
    "connection": { "connected": 7, "disconnected": 2, "reconnecting": 1, "unresponsive": 0 },
    "ai":         { "active": 6, "paused": 1, "inactive": 3, "unresponsive": 0 }
  },
  "total_filtered": 4,
  "cameras": []
}
```

Population invariants — all counts exclude soft-deleted rows and share one population:

```
Total = all cameras WHERE is_active = 1
Enabled + Disabled                                            = Total
Connected + Disconnected + Reconnecting + Unresponsive        = Total
Active + Paused + Inactive + Unresponsive                     = Total
```

`Disabled` is derived (`total - enabled`) and is not returned separately. Configuration, connection,
and AI state are **independent dimensions** — a disabled camera usually settles to
`Disconnected`/`Inactive`, but those statuses must never be used to infer whether a camera is disabled.

### 5.10 Exports — `/api/exports` (P6)

| M | Path | Auth |
|---|---|---|
| POST | `/api/exports/jobs` | S |
| GET | `/api/exports/jobs/{job_id}` | S — owner or Admin |
| GET | `/api/exports/jobs/{job_id}/download` | S — owner or Admin |
| POST | `/api/exports/retraining` | **A** |

### 5.11 Help Center — `/api/help` (P8)

| M | Path | Auth |
|---|---|---|
| GET | `/api/help/articles?search=&category=` | S — role-filtered by the caller's role |
| GET | `/api/help/articles/{slug}` | S — `404` if the caller's role is not in `roles` |

Empty search results return `{"items": [], "top_faqs": [...]}` (UC-10).

---

## 6. Internal AI contract

**Two versions run side by side.** v1 is the contract `ai_engine/` uses today and must keep working
after every package. v2 is what the AI owner migrates to. Both authenticate with the `x-api-key`
header compared using `secrets.compare_digest`.

> **2026-08-10:** superseded — see the §6.1 note. `ai_engine/` finished migrating to v2 in P10, and
> the A3 audit pack removed v1's remaining unused routes. Only v2 (§6.2, §6.3) is live.

> A **missing** `x-api-key` header currently returns `422`, not `401`. Fix this in P1 by giving the
> header parameter a default of `None` and raising `401 AUTH_REQUIRED` explicitly.

### 6.1 v1 — legacy, frozen (must not break)

> **2026-08-10 (be_audit/A3_ai_seam.md, F3):** `GET /api/internal/cameras` and
> `PATCH /api/internal/cameras/{id}/status` were **removed**. PR #67 had already removed their only
> caller (`ai_engine/sync.py`); the PATCH route was also a second, unguarded writer of AI-owned
> observed state, contradicting D-003's single-writer rule (`apply_observed()` is the only writer).
> The table below is left as-is for the historical record; both rows are dead. `POST
> /api/internal/alert`'s v1 payload branch (bare `snapshot_path`, backend-generated
> `source_event_id`) was removed in the same pack — the route now only accepts the v2 shape in
> §6.3. `backend/scripts/seed_alerts_via_api.py`, the only other v1 caller, was deleted.

| M | Path | Behavior |
|---|---|---|
| GET | `/api/internal/cameras` | Returns `is_active AND is_enabled` cameras as a flat list. **Compatibility rule:** the `ai_status` field in this response now reports the camera's `desired_ai_state`, not observed state — the engine uses it to reconcile pause/resume, which is desired-state semantics |
| POST | `/api/internal/alert` | Accepts `{camera_id, detected_at, snapshot_path, confidence_score}`. `snapshot_path` is a bare filename resolved against `LEGACY_SNAPSHOT_DIR`. Backend generates a `source_event_id`. No idempotency — unchanged from today |
| PATCH | `/api/internal/cameras/{id}/status` | Accepts `{connection_status?, ai_status?}`. Writes **observed** state only. Keeps the existing `409` guard rejecting `ai_status=Active` while an open incident exists |

### 6.2 v2 — heartbeat (P4, new)

```
POST /api/internal/heartbeat
```

Request:

```json
{
  "engine_id": "adas-ai-1",
  "sent_at": "2026-07-12T10:30:05.120+00:00",
  "cameras": [
    {
      "camera_id": 5,
      "connection_status": "Connected",
      "ai_status": "Active",
      "applied_config_version": 7,
      "measured_fps": 11.8,
      "inference_latency_ms": 42.5,
      "error_code": null,
      "error_message": null
    }
  ]
}
```

Response — a **complete authoritative snapshot**, not a change list, so either side can restart and
recover deterministically (D-003):

```json
{
  "server_time": "2026-07-12T10:30:05.180+00:00",
  "heartbeat_interval_seconds": 3,
  "cameras": [
    {
      "camera_id": 5,
      "channel_id": 3,
      "camera_name": "Ayala Highway",
      "rtsp_url": "rtsp://localhost:8554/channel3",
      "is_enabled": true,
      "desired_ai_state": "Paused",
      "desired_state_reason": "incident",
      "cooldown_until": null,
      "config_version": 7
    }
  ]
}
```

Only `is_active` cameras appear. A camera absent from the snapshot must have its runtime stopped and
its resources released. `rtsp_url` is credential-bearing and must be redacted in every log line.

### 6.3 v2 — idempotent incident ingestion (P4)

`POST /api/internal/alert` additionally accepts `source_event_id` and `snapshot_key`:

```json
{
  "source_event_id": "5f1c…-uuid",
  "camera_id": 5,
  "detected_at": "2026-07-12T10:30:00+00:00",
  "snapshot_key": "2026/07/12/camera_5/5f1c…-uuid.jpg",
  "confidence_score": 0.87
}
```

Response semantics — these are a hard contract because the AI outbox branches on them (D-012):

| Status | Meaning | AI engine action |
|---|---|---|
| `201 Created` | New incident committed | Acknowledge and remove from outbox |
| `200 OK` | Idempotent retry — returns the incident already created for that `source_event_id` | Acknowledge and remove from outbox |
| `409 CONFLICT_STATE` | Another open incident owns this camera | Keep paused, stop retrying **this** event |
| `404 NOT_FOUND` | Camera removed, inactive, or disabled | Stop that camera's runtime |
| `401` / `403` | Configuration or security fault | Stop rapid retry, raise a critical operational error |
| `422 VALIDATION_ERROR` | Non-retryable payload defect | Quarantine for diagnosis |
| `5xx` / network error | Transient | Retry from the persistent outbox with backoff |

The current v1 route returns `200` on creation. v2 returns `201`. Both are accepted by the existing
engine, which treats `200` and `201` identically — so this is safe to change.

---

## 7. Snapshots

### 7.1 Storage

- One configured absolute root, `SNAPSHOT_ROOT`. **It is never sent to a client and never stored in
  an incident record.**
- `snapshot_key` is a normalized relative key: `2026/07/12/camera_5/<source_event_id>.jpg`.
- Legacy v1 payloads send a bare filename (`cam10_20260428_144448.jpg`). Resolution order:
  `SNAPSHOT_ROOT / key` first, then `LEGACY_SNAPSHOT_DIR / key` when the key has no path separator.
- Reject absolute paths, `..` traversal segments, and any key whose `Path.resolve()` escapes the
  configured roots. This check is mandatory and must be unit-tested with hostile inputs.
- The public `/snapshots` static mount in `backend/app/main.py` is **removed** in P4.

### 7.2 RTSP URL construction (backend-owned)

`RTSP_URL_TEMPLATE` is formatted with `channel_id`, `camera_id`, and the `DSS_*` values:

```
# demo (MediaMTX)
RTSP_URL_TEMPLATE=rtsp://localhost:8554/channel{channel_id}

# production (Dahua DSS Pro media gateway, 720p substream)
RTSP_URL_TEMPLATE=rtsp://{dss_username}:{dss_password}@{dss_ip}:{dss_port}/cam/realmonitor?channel={channel_id}&subtype=1
```

Switching stream sources is a `.env` change with zero AI engine code change. This matches wireframes
7.6/7.7, where the Add Camera form collects only Camera Name and Channel ID.

---

## 8. Audit action catalog (D-007)

The complete `CHECK` constraint set. One row per **semantic** action — renaming and disabling a camera
in one request produces both `CAMERA_UPDATE` and `CAMERA_DISABLE`.

```
LOGIN_SUCCESS   LOGIN_FAILURE   LOGOUT

ALERT_CONFIRM   ALERT_DISMISS   ALERT_CLEAR    ALERT_CORRECTION   ALERT_SNOOZE

CAMERA_CREATE   CAMERA_UPDATE   CAMERA_ENABLE   CAMERA_DISABLE   CAMERA_DELETE

REPORT_EXPORT   AUDIT_EXPORT

USER_CREATE     USER_UPDATE     USER_ENABLE     USER_DISABLE
USER_ROLE_CHANGE   USER_PASSWORD_RESET   USER_PROFILE_UPDATE   USER_PASSWORD_CHANGE

ALARM_SETTINGS_UPDATE   BACKUP_TRIGGER   RESTORE_TRIGGER
```

Incident-transition mapping:

| Transition | Action |
|---|---|
| `Unverified → Ongoing` | `ALERT_CONFIRM` |
| `Unverified → Dismissed` | `ALERT_DISMISS` |
| `Ongoing → Cleared` | `ALERT_CLEAR` |
| `Ongoing → Dismissed` | `ALERT_CORRECTION` |

**Excluded from the audit trail:** AI detections, heartbeats, FPS/latency samples, routine camera
telemetry, and audit-page views. Incident records and structured operational logs cover those.

**Transaction semantics:**

- `success` — the primary action and its audit row(s) commit in **one** transaction. If the audit
  insert fails, the primary action rolls back.
- `denied` / `failure` — written in a **separate short transaction** after the primary transaction
  has rolled back. If that write also fails, the action stays denied/failed and a critical structured
  log line is emitted.

---

## 9. WebSocket contract (D-008)

Endpoint: `GET /ws/alerts` (upgrade). Authenticated by the same session cookie as REST — the browser
sends it automatically on the handshake. The handshake also validates `Origin`.

### 9.1 Envelope

Every server message:

```json
{
  "version": 1,
  "event_id": "8c2a…-uuid",
  "type": "ALERT_STATUS_UPDATE",
  "occurred_at": "2026-07-12T10:30:05+00:00",
  "data": { }
}
```

`event_id` exists so clients can suppress duplicates across a reconnect race. Delivery is
**at-most-once, best-effort while connected**. There is no replay, no acknowledgement protocol, and
no durable event log — REST is the recovery path.

### 9.2 Event catalog

| Type | Emitted when | `data` |
|---|---|---|
| `CONNECTION_READY` | immediately after an accepted handshake | `{connection_id, server_time, user_id, role}` |
| `NEW_DETECTION` | an incident is committed | the full incident record (§9.3) |
| `ALERT_STATUS_UPDATE` | any committed lifecycle transition | incident record + `action`, `handled_by`, `handled_at` |
| `CAMERA_STATUS_UPDATE` | committed change to a camera's desired **or** observed state | `{camera_id, camera_name, is_enabled, desired_ai_state, desired_state_reason, connection_status, ai_status, cooldown_until, config_version}` |
| `SNOOZE_ACTIVATED` | a snooze transaction commits | `{log_id, camera_id, snoozed_by, snoozed_until}` |
| `RE_ALARM` | a persisted snooze deadline expires while still `Unverified` | `{log_id, camera_id}` |

Clients **never** mutate state over the WebSocket. All domain changes go through audited REST routes.

### 9.3 Incident payload

TC-U-205 pins the minimum field set. This is a superset and stays backward compatible:

```json
{
  "log_id": 42,
  "source_event_id": "5f1c…-uuid",
  "camera_id": 5,
  "camera_name": "Ayala Highway",
  "detected_at": "2026-07-12T10:30:00+00:00",
  "confidence_score": 0.87,
  "detection_status": "Unverified",
  "snapshot_url": "/api/alerts/42/snapshot",
  "verified_by_id": null, "verified_by_name": null, "verified_at": null,
  "closed_by_id": null,   "closed_by_name": null,   "closed_at": null,
  "snoozed_until": null,  "snoozed_by_id": null,
  "created_at": "…", "updated_at": "…"
}
```

`snapshot_url` is an **authorized API path**, never an operating-system path.

### 9.4 Delivery rules

- Enqueue **only after** the database transaction commits. Never inside one.
- Each connection owns a bounded `asyncio.Queue` and one sender task. Broadcast means "put into each
  eligible queue", not "await each send in a loop".
- A full queue or a repeatedly failing sender closes **that connection only**, with a documented
  policy close code. One frozen workstation must never delay another operator's alert.
- FIFO within a connection. No global ordering guarantee across connections.

### 9.5 Recovery sequence

After every accepted connection or reconnection:

1. Server sends `CONNECTION_READY`.
2. Client fetches all `Unverified` and `Ongoing` incidents (`GET /api/alerts/?status=…`) — this is
   NFR-17 / TC-R-304.
3. Client fetches current camera state (`GET /api/cameras/`).
4. Client reconstructs alarm/snooze state from the persisted `snoozed_until` values.
5. Client merges concurrently arriving events using incident `updated_at` and camera `config_version`
   so an older snapshot cannot overwrite newer event state.

---

## 10. Incident state machine (D-002)

```
AI detection  ->  Unverified
Unverified    ->  Ongoing     (Confirm)
Unverified    ->  Dismissed   (Immediate false positive)
Ongoing       ->  Cleared     (Emergency cleared)
Ongoing       ->  Dismissed   (Correction of a mistaken confirmation)
```

Every other transition is rejected. `Dismissed` and `Cleared` are terminal — there is no reopen path
and no general-purpose incident edit or delete API.

### 10.1 Actor and timestamp semantics

| Transition | `verified_by` / `verified_at` | `closed_by` / `closed_at` |
|---|---|---|
| Confirm (`Unverified→Ongoing`) | set to the actor | unchanged (null) |
| Immediate dismiss (`Unverified→Dismissed`) | **set to the actor** | remains empty |
| Clear (`Ongoing→Cleared`) | retained | set to the actor |
| Correction (`Ongoing→Dismissed`) | retained (original verifier) | set to the correcting actor |

> The current code sets *closure* fields on an immediate dismiss. That is wrong under D-002 and P4
> changes it. Existing tests assert the old behavior and must be updated.

### 10.2 Camera consequences

| Event | Desired state | Reason | Cooldown |
|---|---|---|---|
| Incident created | `Paused` | `incident` | — |
| Confirm | `Paused` (unchanged) | `incident` | — |
| Immediate dismiss | `Paused` | `cooldown` | `cooldown_until = now + 60s` |
| Cooldown expiry | `Active` | cleared | cleared |
| Clear | `Active` immediately | cleared | — |
| Correction | `Active` immediately | cleared | — |
| Camera disabled | `Inactive` | `disabled` | — |

Resume to `Active` only happens when the camera is `is_active AND is_enabled`. Any transition to a
terminal status clears the incident's snooze fields **in the same transaction**.

### 10.3 Atomicity

A transition is a **conditional UPDATE**, never a read-then-write:

```sql
UPDATE detection_log
   SET detection_status = :new, verified_by_id = :actor, verified_at = :now, updated_at = :now
 WHERE log_id = :log_id
   AND detection_status = :expected;
```

`rowcount == 0` means the race was lost → re-read the row → return `409 CONFLICT_STATE` with the §5.3
body. The incident transition, the camera desired-state change, and the audit row all commit in one
transaction; broadcasts are enqueued only after that commit succeeds.

---

## 11. Snooze semantics (D-004)

- Only an `Unverified` incident may be snoozed. Anything else → `400 PRECONDITION_FAILED`.
- Duration comes from the **actor's** `alarm_settings.snooze_duration`. A client-supplied duration is
  ignored, and a body containing one is a `422`.
- Snooze is **shared incident state**, not per-user: every dashboard mutes that incident until the
  shared deadline. Sound and volume remain per-user.
- Unlimited re-snoozes. The latest one overwrites `snoozed_at` / `snoozed_until` / `snoozed_by_id`.
- The scheduled job uses the stable identity `snooze:{log_id}` and is replaced on re-snooze.
- **`snoozed_until` in SQLite is authoritative** — the in-memory job is an optimization, not the
  correctness mechanism. Any job that wakes re-reads the incident and does nothing unless the current
  deadline is due, the incident is still `Unverified`, and the snooze has not been cleared.
- Expiry is an atomic conditional UPDATE. **Only the process that actually clears the row broadcasts
  `RE_ALARM`** — a duplicate or obsolete job updates zero rows and stays silent.
- On startup: reschedule unexpired snoozes for their remaining duration; atomically clear expired ones
  so those incidents become alarm-active again. A periodic safety sweep catches lost jobs.

---

## 12. Test-case traceability

D-001 requires acceptance evidence for all 82 paper test cases and forbids silently omitting one that
belongs to another owner. Every package doc names the test cases it satisfies. P9 assembles the full
matrix, where each case maps to exactly one of:

- an automated backend test (named file + test function),
- a documented manual procedure with recorded measured results,
- an explicitly external owner (AI model accuracy, physical VLAN/NAS, frontend UI) **with** the
  interface, prerequisite, and acceptance evidence named.

---

## 13. P28-P30 locked follow-up contracts

### 13.1 Incident terminal terminology (P28)

The only true-positive terminal state is `Cleared`. The legal transition is
`Ongoing -> Cleared`, performed by `POST /api/alerts/{log_id}/clear`, audited and broadcast as
`ALERT_CLEAR`. The visible action button is also `Cleared` and remains immediate; no confirmation
step is introduced. `Cleared` means the accident is no longer visible in that camera and detection
may resume. `Resolved`, `/resolve`, `ALERT_RESOLVE`, and `total_resolved*` are not compatibility
aliases for the active `Cleared` contract. Existing detection and audit rows are rewritten by the
reviewed migration. Closure actor/
timestamp field names remain generic because an Ongoing-to-Dismissed correction uses them too.

### 13.2 AI Performance authorization (P29)

AI Performance is Administrator-only at the API, async-job, route, navigation, help, and UAT layers.
Its sidebar location is the final Administration item after Maintenance. Operators retain Dashboard,
Detections, System Health, incident/dashboard exports, Profile, and role-appropriate Help. Existing
Operator-owned performance jobs are no longer listable, readable, or downloadable by that Operator.

### 13.3 Protected and degraded backup storage (P30)

`BACKUP_DIR` remains local fallback plus maintenance-control state. `PROTECTED_BACKUP_DIR` and
`PROTECTED_ARCHIVE_DIR` are explicit optional absolute targets. `protected` requires a provably
different physical device from the live database; a different drive letter alone is insufficient.
Backup/archive creation prefers protected storage and falls back locally as `degraded`. Listing and
restore use `(storage_tier, backup_id)` identity. Restore state and a verified pre-restore emergency
reserve stay local so loss of external media cannot erase rollback state. Paths and physical ids are
never returned or audited.
