# Contributing

This is the "what to run before committing" doc. See [README.md](README.md) for how to run the system itself.

## First-time setup

```bash
uv sync --extra ai
pnpm install
cp .env.example .env
```

- `uv sync --extra ai` — installs the backend plus the AI engine's heavy ML deps (torch, tensorrt, ultralytics, opencv). Use plain `uv sync` if you're only touching the backend/frontend and don't need to run the AI engine.
- `pnpm install` — **run this at the repo root**, not inside `frontend/`. This is a pnpm workspace, and running install at the root is what triggers husky's `prepare` script and activates the git hooks below. Running it only inside `frontend/` will leave your hooks inert.
- `cp .env.example .env` — then fill in real values. The backend hard-fails on startup if any of the 10 keys are missing.

Also run this once, locally (it's a personal git config, not something that can be committed):

```bash
git config blame.ignoreRevsFile .git-blame-ignore-revs
```

Without it, `git blame` will stop at the repo's one bulk formatting commit (`style: apply ruff and prettier formatting`) instead of the commit that actually introduced a line.

## The one command

Run `pnpm check` before pushing. Run `pnpm full:check` before opening a PR — it's everything `pnpm check` does, plus a production build and the E2E suite.

| Script                | Runs                                                                    |
| --------------------- | ----------------------------------------------------------------------- |
| `pnpm format`         | `prettier --write .` + `uv run ruff format .`                           |
| `pnpm format:check`   | Same, in check mode (no writes)                                         |
| `pnpm lint`           | `pnpm --filter frontend lint` + `uv run ruff check .`                   |
| `pnpm lint:fix`       | Same, with `--fix`                                                      |
| `pnpm typecheck`      | `pnpm --filter frontend typecheck` (`tsc --noEmit`)                     |
| `pnpm test:be`        | `uv run pytest`                                                         |
| `pnpm test:fe`        | `pnpm --filter frontend test:run` (Vitest)                              |
| `pnpm test`           | `test:be` then `test:fe`                                                |
| `pnpm test:e2e`       | `playwright test` — boots both servers, CI-only, not in `check`         |
| `pnpm build`          | `pnpm --filter frontend build`                                          |
| **`pnpm check`**      | `format:check` → `lint` → `typecheck` → `test` — **what pre-push runs** |
| **`pnpm full:check`** | `check` → `build` → `test:e2e` — the pre-PR command                     |

## What the hooks do, and when

Hooks live in `.husky/` and only activate after `pnpm install` has run at the repo root (see above).

- **pre-commit** — runs `lint-staged`: Prettier/ESLint/Ruff against only the files you staged. Fast (~1-3s), auto-fixes in place.
- **commit-msg** — runs `commitlint` against your commit message. Rejects anything that isn't [Conventional Commits](https://www.conventionalcommits.org/).
- **pre-push** — runs `pnpm check` (format check, lint, typecheck, both test suites) against the whole repo. Slower; this is the real gate.

## Commit conventions

Conventional Commits, matching the existing history. No fixed scope list — use whatever scope fits (`fix(auth):`, `refactor(modals):`, or no scope at all).

| Type       | Example                                               |
| ---------- | ----------------------------------------------------- |
| `feat`     | `feat: add camera pause/resume endpoint`              |
| `fix`      | `fix(auth): harden session expiry validation`         |
| `refactor` | `refactor(modals): extract form components`           |
| `chore`    | `chore: bump vite to v8`                              |
| `docs`     | `docs: fix broken installation fence in README`       |
| `test`     | `test: add coverage for alert dismissal side effects` |
| `ci`       | `ci: add GitHub Actions workflow`                     |
| `style`    | `style: apply ruff and prettier formatting`           |

## Escape hatch

`git commit --no-verify` / `git push --no-verify` skip the hooks. They exist for genuine WIP commits on your own branch — CI runs the same checks (`pnpm check`-equivalent jobs) on every PR, so skipping locally just defers the failure, it doesn't avoid it. Don't push straight to `main` with `--no-verify` expecting it to slide through unnoticed.

## Branch protection

CI (`.github/workflows/ci.yml`) runs on every PR and push to `main`, but **requiring those checks to pass before merge is a manual GitHub repo setting** (Settings → Branches → branch protection rules) — it can't be committed as a file. `gh` CLI is available if you'd rather script it than click through the UI.

## Troubleshooting

- **Hooks aren't firing.** You probably ran `pnpm install` inside `frontend/` instead of the repo root. Run it at the root.
- **`ruff` / `uv run ruff ...` says command not found.** Run `uv sync` (or `uv sync --extra ai`) at the repo root first.
- **Playwright says browsers are missing.** Run `pnpm exec playwright install --with-deps chromium`.
- **`pnpm check` fails on files you didn't touch.** `lint`/`format:check` run against the whole repo, not just your change — if `main` already had lint debt when you branched, you'll see it too. Not a bug in your change; fix it or coordinate before landing more on top of it.
