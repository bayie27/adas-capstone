# End-to-end tests

Playwright specs that drive a real backend and a real frontend together. They live
at the repository root rather than in `frontend/` because they span both.

Configuration is [`playwright.config.ts`](../playwright.config.ts), which carries
long comments explaining the screenshot thresholds. Read those before changing any
comparison setting.

## Two projects, on purpose

| Project    | Specs                                          | Run by                                 | In CI |
| ---------- | ---------------------------------------------- | -------------------------------------- | ----- |
| `chromium` | `login.spec.ts`, `mfa.spec.ts`, `totp.spec.ts` | `pnpm test:e2e`, and `pnpm full:check` | Yes   |
| `visual`   | `visual.spec.ts`                               | `pnpm test:visual`                     | No    |

`chromium` is the functional project. It ignores the visual spec and is part of the
pre-PR gate.

The isolated runner creates a UUID-scoped database and storage root, a fresh
Fernet key, a disposable admin, and a separate random-password account for each
MFA browser scenario. Alembic provisions the schema; setup inserts only those
accounts before the server starts. The browser then enrolls and authenticates
through the real UI and API. It never uses `/api/dev/login-as` as normal-login
evidence. The default E2E job does not reset or touch the repository's root DB.
Playwright traces, automatic screenshots, and video are disabled so secret-entry
and one-time-code screens are not captured in artifacts. Automatic failure page
snapshots are disabled too; assertions on setup and recovery-code screens use
locator waits so failures do not attach those screen contents.

`visual` is a screenshot diff across nine routes. It is deliberately kept out of
both `full:check` and CI: a legitimate design change would fail the gate with a
picture, which is noise rather than a defect. Run it when you change the token
layer or the layout, and review the diff yourself.

The visual project authenticates through the normal password-plus-authenticator
flow on isolated data. It may use a dev-only reseed afterward to prepare the visual
dataset; that returned impersonation session is not login evidence. It runs serially
with one worker and zero retries at 1440x1024 with `deviceScaleFactor: 1`. Each of
those matters. The tests share one signed-in page, so they cannot run in parallel.
A retry would re-run the whole serial block and pass a route whose baseline the
failed attempt had just written, which hides both a missing baseline and a real
flake.

A screenshot diff proves a page changed. It cannot prove the page is now correct —
a wrong token on a status colour produces a clean, confident diff. The
[visual checklist](../frontend/VISUAL_CHECKLIST.md) is the other half of that.

## Running them

```powershell
pnpm test:e2e
pnpm test:visual
```

Nothing needs to be running first — Playwright starts a backend and a frontend
itself, and stops them afterwards. If you already have the dev stack up locally it
reuses those instead and leaves them running. If Playwright says the browser is
missing:

```powershell
pnpm exec playwright install --with-deps chromium
```

To point the tests at an already-deployed stack instead, set `E2E_LIVE_DEPLOYMENT=1`.
That switch is what turns the behaviour on, and the config refuses to start without
`E2E_BASE_URL` alongside it. In that mode it starts no servers of its own:

```powershell
$env:E2E_LIVE_DEPLOYMENT = "1"
$env:E2E_BASE_URL = "https://<host>:5173"
```

Enrollment, recovery, replacement, rotation, and wrong-code specs are skipped in
live mode. A live deployment is never enrolled or modified by the default browser
suite, and a live-mode run is not evidence for isolated MFA cutover.

## Baselines are Linux-only

The nine committed baselines in `visual.spec.ts-snapshots/` all end in `-linux.png`.
That suffix is not decorative: Playwright appends `process.platform` to every
screenshot filename, so a Windows run looks for `-win32.png`, finds nothing, and
reports `A snapshot doesn't exist ..., writing actual` — failing that run and
writing a fresh Windows baseline. **Run it again and it passes, comparing Windows
against Windows and proving nothing about the committed baselines.**

So run the visual project on Linux or WSL. If a `-win32.png` file appears in the
snapshots directory, it was created by accident; delete it rather than committing
it.

To update the Linux baselines after an intended design change, on Linux or WSL:

```bash
pnpm exec playwright test --project=visual --update-snapshots
```

Then look at what changed before committing. A baseline refreshed without reviewing
its diff is worse than no baseline.
