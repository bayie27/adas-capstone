# ADAS frontend

React dashboard for incident review, camera management, analytics and system
operations. See the [project overview](../README.md) and
[operations guide](../docs/operations/README.md) for the complete stack.

## Development

Run from the repository root:

```powershell
pnpm install
pnpm --filter frontend dev
```

The backend must be running with matching origin/session settings. The default
frontend address is `http://localhost:5173`. Use the
[LAN/TLS guide](../docs/operations/LAN_SETUP.md) for certificate and cross-machine
setup.

The root pnpm workspace and lockfile own dependency installation. Install at the
root, not in here — installing inside `frontend/` also skips the Git hooks.

## Configuration

| Variable            | Default                                         |
| ------------------- | ----------------------------------------------- |
| `VITE_API_BASE_URL` | `<protocol>//<current hostname>:8000/api`       |
| `VITE_WS_BASE_URL`  | `ws://` or `wss://` + `<current hostname>:8000` |

Both are optional. When unset, `src/utils/env.ts` builds them from
`window.location`, which is why the same build works on `localhost` and on a LAN
address without rebuilding, and why the WebSocket automatically switches to `wss://`
on an HTTPS page.

Two more things live in `vite.config.ts`:

- `@` is an alias for `./src`. Prefer `@/utils/cn` over a long relative path.
- The dev server serves HTTPS **only** when `ADAS_TLS_CERT_DIR` is set, reading
  `adas-key.pem` and `adas-cert.pem` from that directory. Plain `pnpm dev`, the
  production build and the Playwright servers are untouched by it. That variable is
  the LAN demo profile.

## Structure

| Location          | Responsibility                                              |
| ----------------- | ----------------------------------------------------------- |
| `src/App.tsx`     | Lazy routes, role gates and persistent application overlays |
| `src/api/`        | REST client and resource requests                           |
| `src/pages/`      | Dashboard and domain pages                                  |
| `src/components/` | Shared UI, layout and workflow components                   |
| `src/hooks/`      | Reusable interaction, query and real-time hooks             |
| `src/store/`      | Client-side Zustand state                                   |
| `src/utils/`      | Formatting and shared utilities                             |
| `src/test/`       | Vitest setup and the provider render wrapper                |
| `public/help/`    | Help Center screenshots                                     |

TanStack Query owns server state; Zustand owns client state. Authentication uses
HttpOnly cookies. The runtime-gated development panel is lazy-loaded. Do not remove
pages or the panel merely because their imports are dynamic.

`public/help/` pairs with [`backend/content/help/`](../backend/content/README.md):
the articles there reference these images as `/help/<name>.png`, so the two
directories are edited together.

## Design tokens

Every colour in this app comes from a token. This is enforced by lint, so it is
worth understanding before you write a component.

**Where they live.** The `@theme` block at the top of `src/index.css`, transcribed
from the Figma variable collections. Tailwind v4 turns each entry into both a real
CSS custom property and a set of utilities: `--color-surface-1` gives you
`var(--color-surface-1)` and `bg-surface-1` / `text-surface-1` / `border-surface-1`.

**Which form to use.** The utility class, normally. The `var(...)` form is for
places a class cannot reach — Recharts props like `stroke` and `fill` take
`var(--color-chart-line)` and friends.

**What lint rejects.** `eslint.config.js` has three rules, because raw colour
arrives three different ways:

| Rejected                | Example            | Use instead                        |
| ----------------------- | ------------------ | ---------------------------------- |
| Arbitrary colour value  | `bg-[#111]`        | `bg-surface-1`                     |
| Tailwind palette colour | `text-emerald-500` | `text-success`                     |
| Bare colour literal     | `stroke="#ffffff"` | `stroke="var(--color-chart-line)"` |

`pnpm --filter frontend lint` fails on all three, and it feeds `pnpm check`, which
the pre-push hook and CI both run.

**What is still allowed.**

- Arbitrary values for geometry that is off the spacing scale — `w-[272px]` is
  fine. The rules only match colour.
- A computed colour built in a template literal, such as the `hsl()` ramp behind
  Accident Frequency by Location. The rules deliberately match plain string
  literals only, so a ramp calculated at runtime is not a hardcoded colour and is
  not flagged.

**Semantic names, not descriptive ones.** Use `text-danger`, not "the red one".
Surfaces read as three levels: canvas behind everything, `surface-1` for cards and
inputs, `surface-2` only for something elevated or active. Muted text is one grey —
if something needs to look dimmer, use `opacity-60` on that token rather than
inventing a value.

The [visual checklist](VISUAL_CHECKLIST.md) is the manual half of this: it walks
each route against the design source and records the few places where the
implementation deliberately departs from the token spec, and why.

## Conventions

- Prettier with `semi: false`, double quotes, `printWidth: 100`. It runs on staged
  files at commit time, so mostly you can ignore it.
- Unit tests sit next to the file they cover as `*.test.ts` or `*.test.tsx`. There
  is no separate `__tests__` tree.
- Absolute imports through `@/` for anything outside the current folder. `src/`
  currently has 572 of them and not a single `../`; keep it that way.

## Checks

```powershell
pnpm --filter frontend test:run
pnpm --filter frontend lint
pnpm --filter frontend typecheck
pnpm --filter frontend build
```

Vitest uses JSDOM and `src/test/setup.ts`. End-to-end and screenshot tests are
Playwright and live at the repository root, because they drive the backend too —
see [`e2e/README.md`](../e2e/README.md). Contribution gates are in
[CONTRIBUTING.md](../CONTRIBUTING.md).
