# Package A — Seed Core Refactor & Enriched Profiles

> **Blocked by:** nothing. This is the first package on its branch.
> **Branch:** `feat/dev-seeding-and-tools` (create it off `main`).
> **Prerequisite reading:** [`00_OVERVIEW.md`](00_OVERVIEW.md) · `CLAUDE.md` · `backend/scripts/README.md`
> **Size:** L. Seven steps.
> **Scope:** `backend/` only. No HTTP routes, no frontend, no `ai_engine/`.

## Why this package exists

Two problems, one structural and one about coverage.

**Structural.** All the seed logic lives in `backend/scripts/seed_dev_data.py`, which is not
importable by the FastAPI app. `backend/scripts/` has no `__init__.py`; every script there calls
`bootstrap_backend()` from `_bootstrap.py` to inject `backend/` into `sys.path` before importing
`app.*`. That works for a CLI entrypoint and nothing else. Package B needs to call this logic from
inside a live request, and `backend/tests/perf/conftest.py` already resorts to its own `sys.path`
hack to re-import the module and reach `_build_perf_rows`, `_enforce_open_camera_limit`,
`ensure_default_operators` and `seed_sample_cameras`. That hack is the tell: the logic is in the
wrong place.

**Coverage.** A "profile" today is only a list of `SeedAlertSpec`s — `PROFILE_BUILDERS` maps three
names to three `build_*_alert_specs` functions, and `perf` isn't even in that dict (it's dispatched
by a duplicated `if profile == PERF_PROFILE` branch in both `seed_dev_data.main()` and
`reseed_dev.reseed_dev()`). Users and cameras are hard-coded and identical everywhere. The result:

- `sys_health_raw` / `sys_health_hourly` — never seeded. The System Health page has no history.
- `export_job` — never seeded. The Exports page is always empty.
- `audit_log` — `_seed_audit_log_rows` writes 10 rows using 3 of the 26 `AUDIT_ACTIONS`, all
  `success` except one. No `ALERT_*`, no `CAMERA_*`, no `REPORT_EXPORT`, no `BACKUP_TRIGGER`.
- Detection snooze columns (`snoozed_at`/`snoozed_until`/`snoozed_by_id`) — always NULL.
- Camera telemetry (`last_heartbeat_at`, `measured_fps`, `inference_latency_ms`, `last_error_code`,
  `last_error_message`, `applied_config_version`) — always NULL, so every seeded camera presents as
  `Reconnecting`.
- `AlarmSettings` — always the defaults (`default`/80/30), so per-user alarm config can't be shown.
- No `Unresponsive` camera, no soft-deleted (`is_active=False`) camera, no disabled user, no
  second Admin, no forced-password-change user.
- **No snapshot file is ever written**, for any profile, so `GET /api/alerts/{log_id}/snapshot`
  404s on every seeded row.

---

## Scope

### In

| #   | Change                                                                            |
| --- | --------------------------------------------------------------------------------- |
| 1   | Move seed logic from `backend/scripts/` into a new `backend/app/dev/` package     |
| 2   | `SeedProfile` dataclass + `PROFILES` registry replacing the tuple/dict/`if` triad |
| 3   | Unify the two disagreeing open-incident enforcers                                 |
| 4   | Enrich `demo`, `analytics` and `edge`; add `empty`                                |
| 5   | Write placeholder snapshot files so the snapshot endpoint resolves                |
| 6   | Thin CLI wrappers; `--count` passthrough on `reseed_dev.py`                       |
| 7   | Drop the `sys.path` hack in `backend/tests/perf/conftest.py`                      |

### Out — do not do these here

- **Any HTTP route.** No `routes/dev.py`, no settings flag. That is Package B.
- **Any Alembic migration.** Every column this package populates already exists. If you conclude
  you need a schema change, **stop and report it** — that is a planning error, not something to
  fix inline.
- **Changing `perf`'s 100 000-row behaviour or its statistical distribution.**
  `backend/tests/perf/` asserts against it and `be_plan/10_PKG_migration_evidence.md` is the
  evidence trail for NFR-08.
- **Touching `frontend/` or `ai_engine/`.**

---

## Step 1 — Create `backend/app/dev/` and move the seed logic

New package, three modules:

| File                          | Holds                                                                                                                 |
| ----------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| `backend/app/dev/__init__.py` | Re-exports the public surface (`PROFILES`, `SEED_PROFILES`, `DEFAULT_SEED_PROFILE`, `seed_profile`, `seed_perf_data`) |
| `backend/app/dev/profiles.py` | `SeedProfile`, the spec dataclasses, `PROFILES`, the `build_*_specs` functions                                        |
| `backend/app/dev/seed.py`     | The `ensure_*` writers and the orchestration                                                                          |

Move these symbols out of `backend/scripts/seed_dev_data.py` verbatim except for the engine change
in Step 2 — this step is a move, not a rewrite:

- to `profiles.py`: `SeedAlertSpec`, `build_demo_alert_specs`, `build_analytics_alert_specs`,
  `build_edge_alert_specs`, `build_alert_specs`, `_OPEN_STATUSES`, `PERF_*` constants
- to `seed.py`: `_SEED_NAMESPACE`, `_seed_source_event_id`, `ensure_user`, `ensure_camera`,
  `ensure_alert`, `seeded_timestamp`, `seed_sample_cameras`, `ensure_default_operators`,
  `_seed_audit_log_rows`, `_enforce_one_open_incident_per_camera`, `_enforce_open_camera_limit`,
  `_perf_pick_status`, `_build_perf_rows`, `_PERF_SNAPSHOT_POOL`, `seed_dev_data`, `seed_perf_data`

Delete `seed_cameras_only()` — it has no CLI wiring and no caller.

Use absolute `app.*` imports (house rule). Note `backend/scripts/*.py` carries a ruff `E402`
per-file-ignore for the `bootstrap_backend()`-before-imports pattern; code under `backend/app/` does
**not**, so imports must be at the top.

## Step 2 — Take the engine as a parameter

`seed_dev_data.py` does `from app.core.db import engine` at module scope and uses that global
throughout. `app/core/db.py` builds it from the process-global `settings`, but `create_app()` binds
a _different_ engine per `Settings` instance to `app.state.engine`. Package B will call this code
from a request handler and must pass that engine, and the tests need to pass a throwaway one.

Change every public entry point to take an explicit engine:

```python
def seed_profile(engine: Engine, *, profile: str = DEFAULT_SEED_PROFILE, now: datetime | None = None) -> SeedResult
def seed_perf_data(engine: Engine, *, target_count: int = PERF_TARGET_INCIDENT_COUNT) -> SeedResult
```

`now` is injectable so tests get determinism instead of `datetime.now(UTC)` at import time.

`SeedResult` is a small dataclass of per-table row counts (`users`, `cameras`, `detections`,
`audit_rows`, `health_samples`, `export_jobs`, `snapshots`) — Package B returns it from the reseed
endpoint and the panel displays it. Return it instead of only printing; keep the existing printed
summary for the CLI path.

The `perf` dispatch currently duplicated in `seed_dev_data.main()` and `reseed_dev.reseed_dev()`
collapses into `seed_profile()` — see Step 3.

## Step 3 — `SeedProfile` registry

```python
@dataclass(frozen=True)
class SeedProfile:
    name: str
    description: str                                  # shown in the dev panel
    cameras: Callable[[], list[SeedCameraSpec]]
    users: Callable[[], list[SeedUserSpec]]
    alerts: Callable[[datetime], list[SeedAlertSpec]]
    audit: Callable[[datetime], list[SeedAuditSpec]]
    health_days: int = 0
    exports: bool = False
    snapshots: bool = True
    bulk: Callable[..., None] | None = None           # perf's bulk path; None for the spec path

PROFILES: dict[str, SeedProfile] = {...}
```

`SeedProfiles` gains two new spec dataclasses alongside `SeedAlertSpec` — `SeedCameraSpec` and
`SeedUserSpec` — carrying the fields the current hard-coded literals set, plus the telemetry and
lifecycle fields listed in Step 4.

Keep these as re-exports so nothing downstream breaks:

```python
SEED_PROFILES = tuple(PROFILES)          # was a literal tuple
DEFAULT_SEED_PROFILE = "demo"
PERF_PROFILE = "perf"
```

`build_alert_specs(profile, now)` currently raises `ValueError(f"Unknown seed profile '{profile}'...")`
on a `KeyError`. Preserve that behaviour on the registry lookup — Package B's route relies on a
clean error for an unknown profile name.

`seed_sample_cameras()` currently returns a fixed 6-tuple that `seed_dev_data` destructures into a
hard-coded `cameras` dict keyed `ayala/southbound/north_exit/inosluban/tambo/dagatan`. That
destructuring has to become a dict comprehension keyed off `SeedCameraSpec.key`, or profiles still
can't vary cameras. The alert specs reference cameras by that same key, so the keys stay stable for
the existing profiles.

## Step 4 — Unify the open-incident enforcers

`ux_detection_open_camera` is a partial unique index (`WHERE detection_status IN
('Unverified','Ongoing')`) enforcing at most one open incident per camera at the database level.
Two enforcers exist and **they disagree on which row survives**:

| Function                                            | Path               | Keeps                                   |
| --------------------------------------------------- | ------------------ | --------------------------------------- |
| `_enforce_one_open_incident_per_camera` (~line 646) | hand-written specs | the **first** open spec in list order   |
| `_enforce_open_camera_limit` (~line 1058)           | `perf` bulk dicts  | the **most recently detected** open row |

They also synthesize different closure metadata (`verified_after_minutes or 5` + `closed = verified

- 15`vs`detected_at + 4min`+`closed = verified + 20min`).

Collapse to one **most-recent-wins** function. Most-recent is the correct semantic: the open
incident a camera actually has is its latest one, and it is what the `perf` path — the one with
test coverage in `backend/tests/perf/` — already does. Demoted rows become `Resolved` with
synthesized verifier/closer.

Expose it in a shape both callers can use (specs and bulk dicts differ in type), e.g. a single
generic keyed on accessor callables, or one core function with two thin adapters. Either is fine;
one source of truth for the _rule_ is the requirement.

**Check whether this changes the existing `demo`/`analytics`/`edge` output.** If a profile's spec
list has two open incidents on one camera in an order where first ≠ most-recent, the surviving row
changes. That is acceptable — but say so in the commit message rather than letting it look
accidental.

## Step 5 — Enrich the profiles

### `demo` (default)

Keep the existing 18 alerts and 6 cameras. Add:

- **Cameras**: a 7th that is `Unresponsive`, and an 8th that is soft-deleted (`is_active=False`).
  Populate telemetry on the connected ones — `last_heartbeat_at` recent, `measured_fps`,
  `inference_latency_ms`, and on one camera `last_error_code`/`last_error_message`. Leave one with
  `applied_config_version` lagging `config_version`.
- **Users**: a second Admin, a disabled user (`is_active=False`), and one with
  `password_changed_at=None` (forced change on first login). Vary `AlarmSettings` per user across
  the `ALARM_SOUND_KEYS` range, non-default `volume` and `snooze_duration`.
- **Detections**: one snoozed row — `snoozed_at`, `snoozed_until` in the future, `snoozed_by_id`.
- **`export_job`**: one row in each of `queued`, `processing`, `completed`, `failed`, `expired`,
  spanning several `report_type`/`format` combinations. `completed` needs a plausible
  `artifact_path` and `artifact_bytes`; `failed` needs a `failure_category`; `expired` needs
  `expires_at` in the past. Do **not** write real artifact files.
- **`audit_log`**: extend `_seed_audit_log_rows` to cover **all 26** `AUDIT_ACTIONS` with a mix of
  `success`, `denied` and `failure` results, and both `actor_type` values. Keep its existing
  "bail entirely if any audit row already exists" idempotency guard.
- **Health**: `health_days = 7`.

### `analytics`

As today (demo's 18 plus the 14-day loop), with `health_days = 30`.

### `edge`

As today (10 specs with odd verifier/closer combinations), plus: `confidence_score` at exactly
`0.0` and exactly `1.0` (the column's `ge=0.0, le=1.0` bounds), a detection sitting right at the
`DISMISS_COOLDOWN_SECONDS` boundary, and a camera with a non-null `cooldown_until`.

### `empty` — new

Schema plus the default admin only. Zero cameras, zero detections, zero audit rows beyond what
`init_db()` produces. For demoing first-run and empty states, which currently cannot be shown at
all without hand-deleting rows.

### `perf`

Unchanged. `snapshots=False`.

### Health history generation

New writer in `seed.py` producing `sys_health_raw` (one row per 5 minutes over `health_days`) and
`sys_health_hourly` (one row per hour, `hour_start` being the unique idempotency key, with
`sample_count` and the `avg_*`/`peak_*` columns consistent with the raw rows they summarize).

Use a seeded `random.Random` so it's deterministic, and shape the curve so it's legible on a chart —
a daily cycle with a visible spike, not uniform noise. Respect `HEALTH_RAW_RETENTION_HOURS` (48h)
conceptually: writing raw rows older than that is fine for a seed, but the hourly table is what a
30-day view reads from.

## Step 6 — Snapshot placeholders

`services/snapshots.resolve()` looks for `snapshot_root / snapshot_key` and requires the resolved
path to stay inside `SNAPSHOT_ROOT` or `LEGACY_SNAPSHOT_DIR`. The seeder already builds keys shaped
`YYYY/MM/DD/camera_{id}/{source_event_id}.jpg`. Write a file at each.

New `backend/app/dev/assets.py`:

```python
def write_snapshot(snapshot_key: str, *, snapshot_root: Path) -> bool
```

Creates parent dirs and writes the image. Source, in order of preference:

1. a real `.jpg` from `backend/app/dev/assets/snapshots/` if any exist — round-robin across them
2. otherwise an embedded base64 JPEG constant in the module

**No new dependency.** Pillow is only a transitive of the `ai` extra, so there is no image
generation available in a plain `uv sync`. The embedded constant is a small solid-colour JPEG; keep
it under ~2 KB. Add `backend/app/dev/assets/snapshots/` to `.gitignore` and document in
`backend/scripts/README.md` that dropping real frames there gives a better-looking demo.

Skip entirely when `profile.snapshots is False` — 100 000 files is not a demo asset, and `perf`
already reuses 5 fake keys from `_PERF_SNAPSHOT_POOL`.

## Step 7 — CLI wrappers and the perf conftest

`backend/scripts/seed_dev_data.py` and `backend/scripts/reseed_dev.py` become thin argparse
wrappers: `bootstrap_backend()`, import from `app.dev`, pass `app.core.db.engine`, print the
summary. **Keep their existing CLI surface** — `--profile` (now including `empty`) and
`--count` — because `CLAUDE.md`, `README.md` and `backend/scripts/README.md` all document it.

Add the missing `--count` passthrough to `reseed_dev.py`. Today it drops the argument, so
`reseed_dev.py --profile perf` always seeds the full 100 000 rows (~33 s) with no way to ask for
less.

Replace the `sys.path` hack in `backend/tests/perf/conftest.py` with plain
`from app.dev.seed import ...`. Its two extra incident-free cameras ("Perf Latency Cam" ch.201,
"Perf Isolation Cam" ch.202) exist because the enforcer leaves every seeded camera with exactly one
open incident, so a latency test POSTing a new incident would hit a 409 — keep them.

**That hack has two consumers now, not one.** PR #78 (A6's NFR-06 re-scope) added a second
session-scoped fixture, `envelope_seeded`, alongside `perf_seeded`; both call
`perf_seed.ensure_default_operators`, `seed_sample_cameras`, `_build_perf_rows` and
`_enforce_open_camera_limit`, so there are four call sites to repoint. `_build_perf_rows` also
gained a `spread_days` parameter in that PR (defaulting to `PERF_SPREAD_DAYS`, so the `perf`
profile's distribution is unchanged) — carry the parameter through the move verbatim, since
`envelope_seeded` passes a 30-day window to build its ~10-incidents/day dataset.

Update `backend/scripts/README.md`: the new `empty` profile, the `--count` passthrough, the
optional real-snapshot directory, and a note that the logic now lives in `backend/app/dev/`.

---

## Verification

```bash
uv run pytest backend/tests/test_dev_seed.py
```

New file. Assert:

1. **Every profile satisfies `ux_detection_open_camera`** — after seeding, no camera has more than
   one detection in `('Unverified','Ongoing')`. Parametrize over `PROFILES` so a future profile
   can't skip this.
2. **`empty`** produces zero cameras and zero detections but keeps the `help_article` rows
   `init_db()` seeded.
3. **`demo`** writes at least one row to `sys_health_raw`, `sys_health_hourly` and `export_job`;
   covers all 26 `AUDIT_ACTIONS`; produces at least one snoozed detection, one `Unresponsive`
   camera, one soft-deleted camera and one disabled user.
4. **Snapshots resolve** — for a seeded detection, `services.snapshots.resolve(key, ...)` returns an
   existing file.
5. **Re-seeding without a reset is idempotent** — running `demo` twice doesn't violate
   `ux_detection_source_event` (the `uuid5`-based `_seed_source_event_id` and `ensure_alert`'s
   existing-row short-circuit are what make this work; don't break them).
6. **Determinism** — same `now`, same seed, same row counts.

Then confirm the CLI path still works end to end:

```bash
uv run python backend/scripts/reseed_dev.py --profile empty
```

...and repeat for `demo`, `analytics`, `edge`. Skip `perf` in routine runs (~33 s); run it once
before the PR, plus its own suite:

```bash
uv run pytest backend/tests/perf -m slow
```

This package touches `backend/tests/perf/conftest.py`, so run the full suite before opening the PR:

```bash
uv run pytest -n auto
```

---

## Report back

- Whether Step 4's unification changed which open incident survives in any existing profile.
- Any column you found you could not populate without a migration (there should be none).
- The final `SeedResult` field list — Package C renders it.
