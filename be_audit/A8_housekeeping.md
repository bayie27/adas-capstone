# A8 — Housekeeping

Lowest priority. Do it last, or drop it if time runs out — nothing here fails a demo. It is here
so the codebase does not accumulate quiet inconsistencies that the next reader has to re-derive.

> **Read before starting:** `CLAUDE.md` (the services-layer convention), `be_audit/00_FINDINGS.md`.

---

## F10 — `services/` imports from `routes/` (Med)

`backend/app/services/reports/jobs.py` imports row-shaping helpers **from the route modules**
(`app/api/routes/alerts.py`, `analytics.py`, `audit.py`) at call time, inside the generator
functions, to guarantee the async export path emits bytes identical to the synchronous one.

The goal is right and the mechanism is wrong. `CLAUDE.md` states the layering plainly: "Routes
parse/authorize/call a service/serialize; the service owns the transaction and the domain rules."
A service reaching back into a route inverts that, and the deferred import is a workaround for a
circular dependency rather than a solution to it.

**Fix:** extract the shared row-shaping helpers into a module both sides import — e.g.
`app/services/reports/rows.py`. Routes import it; `jobs.py` imports it; the deferred imports go
away and byte-identical output is preserved *structurally* rather than by convention.

**Do not change any output.** The parity tests are the safety net —
`test_reports.py::TestScreenExportParity` runs 15 `PARITY_QUERIES` plus camera, user and combined
filter cases. If any of them move, the refactor is wrong. That suite passing unchanged is the
acceptance criterion.

---

## F16 — Repository and surface hygiene (Low)

### Stray files

- `backend/adas.db` — 0 bytes, created 9 Aug, an artifact from before `DATABASE_URL` was anchored
  to `REPO_ROOT`. The real database is the repo-root `adas.db`. Delete it and confirm `.gitignore`
  covers it so it cannot come back.
- `backend/app/__pycache__/models.cpython-312.pyc` and `ws_manager.cpython-312.pyc` — orphaned
  bytecode for `app/models.py` and `app/ws_manager.py`, both deleted in P1/P3 (replaced by the
  `models/` package and `services/realtime.py`). Harmless, but stale bytecode for a module that no
  longer exists is exactly the sort of thing that produces a confusing import error later.
  Delete and confirm `__pycache__` is gitignored.
- `backend/app/services/__init__.py` is 0 bytes while every other `__init__.py` in the tree carries
  at least a one-line marker comment. Trivial; make it consistent.

### `GET /api/events/schema` is unauthenticated

`backend/app/api/routes/events.py` registers no router-level dependency and no per-route
dependency, so the endpoint is fully public. It returns `model_json_schema()` for the WebSocket
envelope and all six payload models — the complete internal event contract, including field names
for incident and camera state.

This is almost certainly deliberate (it is a developer-facing schema doc, and the frontend owner
needs it), but nothing records that decision, and every *other* route in the application is
authenticated or explicitly documents why it is not (`/`, `/healthz/live`, `/healthz/ready`,
`/api/auth/login`).

**Make it a decision rather than an accident:** either add `Depends(get_current_user)` — the
frontend is authenticated anyway, so nothing breaks — or add a comment stating that it is
intentionally public and why. Record the choice in `01_CONTRACTS.md` §5's auth column.

Recommendation: gate it. It costs nothing and the contract's §1.6 "never leave the backend" list
is otherwise strict.

---

## Acceptance criteria

- `services/reports/jobs.py` has no imports from `app/api/routes/*`;
  `test_reports.py::TestScreenExportParity` passes **unchanged**.
- Stray files gone and gitignored; `uv run pytest` still green afterwards (the 0-byte
  `backend/adas.db` should be referenced by nothing — confirm before deleting).
- `/api/events/schema`'s auth posture is deliberate and documented in `01_CONTRACTS.md`.
- `pnpm check` green.

## Commits

`refactor(reports):` for the layering fix · `chore(repo):` for the stray files ·
`fix(events):` or `docs(planning):` for the schema endpoint, depending on which way you go.
