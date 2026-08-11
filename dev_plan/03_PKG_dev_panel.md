# Package C — Frontend Dev Panel

> **Blocked by:** Package B. It must be **committed** before this session starts — this package
> codes against the six `/api/dev/*` endpoints.
> **Branch:** `feat/dev-seeding-and-tools` (already exists; continue on it).
> **Prerequisite reading:** [`00_OVERVIEW.md`](00_OVERVIEW.md) · [`02_PKG_dev_api.md`](02_PKG_dev_api.md) §5
> for the exact request/response shapes · `CLAUDE.md` (TypeScript conventions, testing policy)
> **Size:** M. Six steps.
> **Scope:** `frontend/` only. Do not touch `backend/` or `ai_engine/` — if an endpoint is wrong,
> report it rather than patching the backend from this session.

## Why this package exists

Package B's endpoints exist but there's no way to reach them from the app. This adds a small
floating button that opens a side panel with the four capability groups, and — critically — handles
the client-side state that a reseed invalidates.

That last part is not optional plumbing. After a wipe:

- **Query keys are ad-hoc across 8 pages** (`["cameras"]`, `["alerts","active",offset]`,
  `["dashboard-analytics",filters]`, `["system-health-history",tab]`, …). There is no central
  `queryKeys` factory, so no scoped invalidation can cover them all.
- **`useAlertStore.handledIds` persists in `sessionStorage`** under `adas-handled-alert-ids` and
  holds stale `log_id`s. Freshly seeded alerts reusing those ids would be silently suppressed.
- **`useAuthStore` is hydrated from `localStorage`** under `adas-auth-session` and would keep
  showing the old username and role.

Get this wrong and the panel appears to work while showing stale data — the worst possible failure
mode for a demo tool.

---

## Scope

### In

| #   | Change                                                  |
| --- | ------------------------------------------------------- |
| 1   | Extract `Modal`'s overlay behaviour into a shared hook  |
| 2   | `ui/SidePanel.tsx` built on that hook                   |
| 3   | `services/dev.ts` + `hooks/useDevTools.ts`              |
| 4   | `components/dev/DevPanelTrigger.tsx` and `DevPanel.tsx` |
| 5   | Mount in `App.tsx`; post-reseed cache and store reset   |
| 6   | Tests                                                   |

### Out

- **shadcn/ui, Radix, `class-variance-authority`, a toast library, or any other new dependency.**
  See §Drawer below — this is a decision, not an omission.
- **A `queryKeys` factory refactor.** Tempting while you're here; out of scope and a large diff
  across 8 pages. `queryClient.clear()` is the correct tool for this specific job.
- **Any backend change.**

---

## Drawer — house style, not shadcn (DT-6)

This frontend is **not** shadcn. There is no `components.json`, no Radix, no
`class-variance-authority`, no `lucide-react`. It is hand-rolled components in
`frontend/src/components/ui/` plus Tailwind v4 (`@tailwindcss/vite`, `@import "tailwindcss"` in
`index.css`) and `@remixicon/react` for icons, with `utils/cn.ts` (clsx + tailwind-merge) as the
class merger. Adding shadcn/Radix for one drawer means importing a whole component convention
alongside the existing one, against CLAUDE.md's "reach for what's there before adding a dependency".

What's already there: `ui/Modal.tsx` (112 lines) solves the hard parts — focus-on-open, body scroll
lock, Escape-to-close with listener cleanup, backdrop click. It's just hardcoded to
`fixed inset-0 z-50 flex items-center justify-center p-4` with `w-full max-w-md`.

**Step 1** extracts that behaviour; **Step 2** builds the drawer on it.

## Step 1 — `useOverlayBehavior`

New `frontend/src/hooks/useOverlayBehavior.ts`. Move the body of `Modal`'s single `useEffect`
(lines 30–53) into it, returning the ref to attach:

```ts
export function useOverlayBehavior(
  isOpen: boolean,
  onClose: () => void,
): RefObject<HTMLDivElement | null>
```

Have `Modal` consume it. **`Modal`'s rendered output and props must not change** — it is used by
`ConfirmDeleteModal` and several pages. This step is a pure extraction; if it produces any visible
diff in behaviour, you've gone too far.

## Step 2 — `ui/SidePanel.tsx`

Same design tokens as `Modal` (`bg-[#111111]`, `border border-[#2A2A2A]`, `rounded-xl`,
`text-[#A1A1AA]` for secondary text, `RiCloseLine` for the close button), different positioning:
anchored right, full height, fixed width (~420px), `max-w-full` so it still works on a narrow
viewport, sliding in from the right.

**Z-index**: `z-[9000]`. `GlobalAlerts` sits at `z-9999` and `Modal` at `z-50`. The alarm modal must
stay above the dev panel — when a real alert fires mid-demo, that's the thing to see.

Keep `role="dialog"`, `aria-modal`, `aria-label` and `tabIndex={-1}` as `Modal` has them.

## Step 3 — Service and probe hook

`frontend/src/services/dev.ts` — thin axios wrappers over the six endpoints, matching the existing
pattern in `services/cameras.ts` (`const { data } = await api.get<T>(...); return data`). Use the
shared instance from `services/api.ts` so `withCredentials` and the 401 interceptor apply.

One caution: the 401 interceptor in `services/api.ts` calls `clearSession()` and
`window.location.replace("/login")`. The reseed response carries a fresh `Set-Cookie`, so the
_following_ request is authenticated — but if anything in the panel fires a request in the window
between the wipe and the new cookie landing, it will bounce the operator to the login screen. Await
the reseed response fully before doing anything else.

`frontend/src/hooks/useDevTools.ts` — a `useQuery` against `GET /api/dev/status` with
`retry: false` and `staleTime: Infinity`. A 404 (router not registered) means disabled. Returns
`{ enabled, profiles }`.

**Gate on this probe, not `import.meta.env.DEV`.** Per DT-3 the panel must work in a `pnpm build`
bundle for the LAN demo, and `import.meta.env.DEV` is false there. There are currently no
`import.meta.env.DEV` conditionals anywhere in the codebase; don't introduce the first one here.

Consequence: the panel code ships in the production bundle. Keep it small and `lazy()` it (Step 4)
so it lands in its own chunk and is never fetched unless the backend says the routes exist.

## Step 4 — Trigger and panel

`frontend/src/components/dev/DevPanelTrigger.tsx` — a small fixed button, bottom-right,
`z-[9000]`. Renders `null` when `useDevTools().enabled` is false. Owns the open/closed state and
`lazy()`-imports `DevPanel`. Bind `Ctrl+Shift+D` to toggle.

`frontend/src/components/dev/DevPanel.tsx` — the body, in three sections:

- **Data** — one button per profile from the probe response, each showing its `description`. On
  success render the `SeedResult` counts. `perf` is labelled slow (~33 s) and needs a second click
  to confirm.
- **Simulate** — inject a detection (camera select + confidence slider, both optional), camera state
  controls (connection/AI status, "make stale", "clear cooldown"), and generate health history.
- **Session** — login-as buttons for the seeded accounts.

Feedback uses the existing `ui/NoticeBanner.tsx` and its exported `NoticeState`
(`{ tone: "success" | "error"; message: string }`) held in local `useState`, rendered inside the
panel. That is how every page in this app already reports success and failure. Run errors through
`getApiErrorMessage` from `utils/api.ts`. **There is no toast system and this package does not add
one.**

## Step 5 — Mount and post-reseed reset

Mount `<DevPanelTrigger />` in `frontend/src/App.tsx` as a sibling of `<GlobalAlerts />` — inside
`<Router>` (so it can use `useNavigate`) and inside `QueryClientProvider` (so it can use
`useQueryClient`), but **outside** `<ErrorBoundary>` and `<Suspense>` so it survives a page crash
and lazy-route loading. That is exactly the pattern `GlobalAlerts` and `RealtimeAlertsBridge`
already use, and mounting there rather than in `AdminLayout`/`UserLayout` also covers `/login`.

After a successful reseed, in this order:

```ts
queryClient.clear()                        // ad-hoc keys across 8 pages; scoped invalidation cannot cover them
useAlertStore.getState().clearAlerts()     // clears sessionStorage handledIds + stops the siren
useAuthStore.getState().setSession(...)    // from the response body: { username, role, user_id }
```

Then `navigate()` if the role changed — `/admin` and `/user` are separate route trees behind
`ProtectedRoute`, so an admin→operator switch that stays on `/admin/users` will bounce.

`clearAlerts()` is the one people forget. It also stops a playing siren, which matters if you reseed
while an alarm is up.

Same sequence after `login-as`, minus `queryClient.clear()` — the data hasn't changed, only who's
looking at it. (Use `invalidateQueries()` there instead, since role-scoped responses can differ.)

`RealtimeAlertsBridge` will also receive the `MAINTENANCE_NOTICE` broadcast Package B sends. You do
**not** need to handle it for the reseeding client — that client already did the reset above. Leave
the event unhandled unless you want other connected browsers to self-refresh; if you do add
handling, keep it to a cache invalidation, not a forced reload.

## Step 6 — Tests

`pnpm --filter frontend test:run`

Frontend coverage here is deliberately minimal (CLAUDE.md testing policy) — smoke tests on pure
utils and simple presentational components, not exhaustive integration coverage. Write:

- `components/dev/DevPanel.test.tsx` — renders nothing when the probe 404s; renders one button per
  profile when enabled.
- `components/ui/SidePanel.test.tsx` — opens, closes on Escape, closes on backdrop click.

No test infrastructure exists for components that use hooks: there is no MSW, no test
`QueryClientProvider` wrapper, no router wrapper. You'll need a small local wrapper
(`QueryClientProvider` + `MemoryRouter`) and `vi.mock("@/services/dev")`. Put the wrapper somewhere
reusable — `src/test/` already exists with `setup.ts`.

Follow the existing convention from `components/ui/StatCard.test.tsx`: co-located `*.test.tsx`,
explicit `import { describe, expect, it } from "vitest"` despite `globals: true`, `render`/`screen`
from `@testing-library/react`. `@testing-library/user-event` is installed but currently unused —
fine to be the first to use it.

Since `Modal` is being modified in Step 1 and has no test today, add a smoke test for it too. That's
the one place a regression would be invisible and would break real pages.

---

## Verification

```bash
pnpm --filter frontend test:run
```

Then manual, with the backend running and `DEV_TOOLS_ENABLED` on:

1. Log in as `admin` — the button appears bottom-right.
2. `Ctrl+Shift+D` toggles the panel.
3. Reseed → `analytics`: the page repaints, you stay logged in, System Health shows 30 days of
   curves.
4. Inject a detection: siren fires, alarm modal opens **above** the dev panel, camera flips to
   `Paused` — with the AI engine not running.
5. Open a seeded detection: the snapshot renders instead of 404ing.
6. Login-as `dsahagun`: the operator view loads and the route changes.
7. Reseed → `empty`: empty states render everywhere, no console errors.
8. Set `DEV_TOOLS_ENABLED=false`, restart the backend, reload: the button is gone.
9. `pnpm build && pnpm --filter frontend preview` with the flag on: **the panel still appears in a
   production bundle.** This is the DT-3 acceptance check — if it fails, the gate is wrong.

Don't run `pnpm check` manually — `.husky/pre-push` runs it on every push.

---

## Report back

- Whether the `Modal` extraction caused any visible change (it shouldn't).
- The production bundle size delta from `pnpm build`, so the DT-3 trade-off is on record.
