# Backend tests

Which commands to run, and when, is in
[CLAUDE.md's verification policy](../../CLAUDE.md#verification-policy) and
[CONTRIBUTING.md](../../CONTRIBUTING.md#verification-commands). This file covers
what the suite gives you to build a test with.

Run from the repository root:

```powershell
uv run pytest backend/tests/test_alerts.py
```

## Layout

Roughly one file per route or core module — `test_alerts.py`, `test_auth.py`,
`test_cameras.py`, `test_migrations.py`, and so on. Start from the file named after
the thing you changed.

`perf/` is separate and works differently. See [below](#perf).

## What `conftest.py` gives you

It gives you two different things, and they are used in two different ways.

### Fixtures — ask for them as test arguments

- `session` — a fresh in-memory database per test. Use it when you are testing a
  service directly.
- `client` — a `TestClient` wired to that same session, for testing through a
  route. It also uses one migrated throwaway database, created once per test run,
  so app startup behaves like the real thing.
- `cheap_password_hashing` — automatic, nothing to request. It runs Argon2id at
  throwaway cost parameters, because the production settings are far too slow to
  run thousands of times. The real parameters are captured before this takes
  effect, so `test_security_params.py` can still assert against them.

### Helpers — import them

These are plain functions, not fixtures. `backend/tests/__init__.py` exists so
they can be imported relatively:

```python
from .conftest import auth_headers, make_admin, make_camera, make_operator
```

- `make_admin`, `make_operator`, `make_camera`, `make_detection` — build the rows a
  test needs without repeating field-by-field setup.
- `login(client, username, password)` — logs in and returns the user body.
- `auth_headers(client, username, password)` — logs in and returns a `Cookie`
  header, for requests that need to carry the session explicitly.
- `internal_headers()` — the `INTERNAL_API_KEY` header the AI engine uses.

One gotcha worth knowing before you write your own settings fixture: session
validation reads the process-global settings object in `app.core.config`, not
whatever `Settings` instance a test passes around. A test that builds its own must
patch that global. `internal_headers()` is the worked example.

## Perf

`perf/` measures the performance claims — alert delivery, export speed, 100,000-row
query performance, and slow-client isolation. It runs against a real file-backed
database seeded with 100,000 rows, not the in-memory fixtures above, because
numbers taken against a toy database would not mean anything.

Seeding alone takes about 30 seconds, so it is marked `slow` and excluded from the
default run:

```powershell
uv run pytest -m slow backend/tests/perf/ -s
```

`-s` matters — the tests print their measured numbers, which is the entire point.
In CI this is the manual `perf` job. See
[CONTRIBUTING.md](../../CONTRIBUTING.md#performance-evidence-suite).
