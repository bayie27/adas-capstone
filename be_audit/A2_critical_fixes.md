# A2 — Critical fixes

Four independent fixes. F1 is the one with real fallout — budget most of the session for it.

> **Read before starting:** `CLAUDE.md`, `be_audit/00_FINDINGS.md`.
> Branch from `main`. One commit per finding.

---

## F1 — Test engine runs without SQLite pragmas (High)

`backend/tests/conftest.py`'s `session_fixture` builds its engine with a bare
`create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)` and
**never calls `install_sqlite_pragmas`**. Production installs four pragmas on every connect
(`app/core/db.py`). The consequence is that `foreign_keys` is **OFF** for the ~500 tests that go
through the `session` / `client` fixtures, while it is **ON** in production.

That is why `test_schema.py` and `test_db_pragmas.py` build their *own* engines — the constraint
tests could not work otherwise. Everything else has been running against weaker guarantees than
the deployed system.

**Fix:** call `install_sqlite_pragmas(engine, ...)` immediately after `create_engine` and
**before `SQLModel.metadata.create_all(engine)`**. Match the signature in `app/core/db.py`.

Ordering matters: the pragmas are installed as a `connect` event listener, and `StaticPool` holds
a single connection. Register the listener before anything opens that connection or it will not
apply.

Notes:
- `journal_mode=WAL` is inert on `:memory:` (it reports `memory`) and does **not** error.
  `foreign_keys` and `busy_timeout` both apply normally.
- **Expect failures.** That is the point of the change. Triage each one honestly:
  - a test inserting a `DetectionLog` with a `verified_by_id` that has no `user` row is a
    **test-fixture bug** → fix the fixture;
  - production code that relied on FK enforcement being off is a **real bug** → record it as a new
    `F17+` row in `00_FINDINGS.md` and fix it.
  - Neither gets papered over by reverting the pragma.
- If a specific test genuinely needs FKs off, disable it locally in that test with a comment
  explaining why — never globally.

---

## F2 — `RTSP_URL_TEMPLATE` fails at runtime instead of at boot (High)

`backend/app/api/routes/internal.py:59`:

```python
return settings.RTSP_URL_TEMPLATE.format(channel_id=..., dss_ip=..., dss_port=..., dss_username=..., dss_password=...)
```

`RTSP_URL_TEMPLATE` is an operator-editable `.env` value. A typo'd placeholder (`{channelid}`,
`{host}`) raises `KeyError`; a stray brace raises `ValueError`. Either one produces a 500 on
**every heartbeat, every 3 seconds, for every camera** — the AI engine loses its entire control
channel and the dashboard shows the whole estate as Unresponsive. Nothing validates the template
at startup, so a one-character `.env` mistake is discovered only in production.

**Fix:** add a `Settings` validator in `backend/app/core/config.py` that performs a trial
`.format()` with sentinel values for all five supported placeholders and raises a clear error
naming the offending key. The app then refuses to boot on a bad template instead of degrading
silently.

**Tests** (`backend/tests/` — new or in an existing config test):
- a template with an unknown placeholder raises at `Settings()` construction, and the message
  names the bad placeholder;
- a template with an unbalanced brace raises;
- the default template and a realistic DSS template both construct fine;
- `_build_rtsp_url` still produces the expected URL for a known-good template.

---

## F3 (routed to A3), F4 (routed to A1)

Not in this pack. See `A3_ai_seam.md` and `A1_lan_tls_drill.md`.

---

## F5 — CORS does not expose `Content-Disposition` (Med-High)

**Do this only after A1 has reproduced it in a browser.** The mechanism is not in doubt, but the
fix should land against an observed failure, not a predicted one.

`backend/app/main.py:475` configures `CORSMiddleware` without `expose_headers`. Per the CORS spec
only seven simple response headers are readable from JS cross-origin, and
`frontend/src/utils/download.ts:24` reads `response.headers["content-disposition"]` to name every
CSV and PDF download. Cross-origin (`:5173` → `:8000`) that read returns `undefined` and every
export silently saves under the fallback filename.

Neither test layer can see this: `TestClient` is not a browser and does not enforce CORS, and the
frontend unit tests stub the response.

**Fix:** `expose_headers=["Content-Disposition", "X-Request-ID"]`.

`X-Request-ID` is included deliberately — it is set on every response by `request_id_middleware`
and is useless for support unless the browser can read it.

**Verification:** browser-level, in A1's drill. A backend unit test can assert the middleware is
configured with the header list, which guards against regression even though it cannot prove the
browser behaviour.

---

## F7 — Async exports silently disabled when the scheduler is off (Med)

`backend/app/main.py:200-202` starts the export worker pool and runs `recover_interrupted_jobs`
**inside** `if app_settings.SCHEDULER_ENABLED:`. With the scheduler off, `POST /api/exports/jobs`
still returns `202 Accepted` and the job sits `queued` forever with no error anywhere.

**Fix:** gate the export queue on its own condition — `EXPORT_JOB_WORKERS > 0` — rather than on
the scheduler flag, so the two subsystems are independent.

Then set `EXPORT_JOB_WORKERS=0` in `_build_test_settings` (`backend/tests/conftest.py`). This
preserves current test behaviour exactly: `test_exports.py` drives jobs by calling
`process_export_job(session.get_bind(), job_id)` directly (see `test_exports.py:84` and ~10 other
call sites) and must not race a live worker pool.

**Tests:**
- with `EXPORT_JOB_WORKERS=0`, `POST /api/exports/jobs` behaves as it does today (tests unchanged);
- with workers enabled and the scheduler disabled, a queued job is actually processed — the
  regression this fix exists to prevent.

---

## Acceptance criteria

- `uv run pytest` green, with every F1-induced failure triaged and explained rather than muted.
- `pnpm check` green.
- `00_FINDINGS.md` updated: F1, F2, F7 → `fixed`; F5 → `fixed` once A1 has confirmed it.
- Any real bug uncovered by enabling FK enforcement is added as a new `F17+` row.

## Commits

`test(backend):` for the conftest pragma fix · `fix(config):` for the template validator
`fix(cors):` for expose_headers · `fix(exports):` for the worker gating.
