# Visual checklist

Two mechanisms verify this refactor, and they answer different questions.

The Playwright screenshot diff (`pnpm test:visual`) proves a page **changed**.
It cannot prove the page is now **right** — a wrong token on a status colour
produces a clean, confident diff and a `Disconnected` camera that reads as
healthy.

This checklist is the other half. Walk it route by route against the Figma
frame, comparing the specific properties listed. It documents the target state,
which is why it lands with the token layer rather than after it.

**Design source:** [ADAM-UI](https://www.figma.com/design/PEf6KSUiVgTbSS6dEDLiX5/ADAM-UI),
page `Web Design`. Token definitions and every resolved Figma inconsistency are
in `FE_Implementation.md` §2.

## How to use it

1. `pwsh -File scripts/start-dev.ps1`, then sign in.
2. Open the Figma frame for the route beside the running app at a 1440px viewport.
3. Compare each listed property. Tick the row, or file what differs.

A row that cannot be ticked is either a bug in this phase or a gap in the design
file — say which. Rows that depend on a screen phase (6–11) rather than on the
token layer are marked _(phase N)_ and are expected to differ until then.

## Routes

| Route                         | Figma node                         | Check                                                                                                                                                                                                                                                                                                                                                                      |
| ----------------------------- | ---------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `/login`                      | `206:10216`                        | Card width / radius (`--radius-xl`) / shadow (`--shadow-overlay`); logo scale; wordmark is Inter 700 `tracking-[0.25em]`, **not** League Spartan; label and input treatment; button fill `--color-primary` with `--color-fg-on-primary` text; error text `--color-danger`.                                                                                                 |
| `/admin`                      | `2:2`                              | Sidebar width **272px** _(phase 5 — still 240px)_; nav group eyebrows in `--color-fg-muted`; active-item fill `--color-surface-2` plus the accent bar; chart stroke `--color-chart-line`, gradient `--color-chart-fill-from` → `-to`, grid `--color-chart-grid`; KPI column — elevated first card, delta badges on the other two; toolbar control height 40px _(phase 8)_. |
| `/admin/cameras`              | `37:74`                            | Three-across KPI row, elevated first card; search field width; two dropdowns; primary `Add Camera` fill; table header `--color-fg-muted`; **status colours — `Connected` `--color-success`, `Paused` `--color-warning`, `Inactive`/`Disconnected` `--color-danger`**; toggle on/off states; pagination footer.                                                             |
| `/admin/detections` (Ongoing) | `37:76`                            | Tab chip selected/unselected; **no toolbar on this tab**; table columns; `Ongoing` in `--color-warning`.                                                                                                                                                                                                                                                                   |
| `/admin/detections` (Logs)    | `112:8438`                         | Full toolbar — search, date range, three dropdowns, `Export`; `Cleared` in `--color-success`, `Dismissed` in `--color-fg-muted`.                                                                                                                                                                                                                                           |
| `/admin/health`               | `37:78`                            | Four-across KPI row; range tabs as `--radius-full` pills; 2×2 chart grid; chart card padding and title treatment. GPU Temperature keeps `--color-danger` as its series colour — see the deviation note below.                                                                                                                                                              |
| `/admin/ai`                   | `38:82`                            | Five-across KPI row _(phase 9)_; table numeric alignment; precision / confidence / dismissed score colours.                                                                                                                                                                                                                                                                |
| `/admin/users`                | `38:81`                            | Search + `Add User` alignment; four columns + actions; three action icons.                                                                                                                                                                                                                                                                                                 |
| `/admin/profile`              | _(none — mismatch M10)_            | Tokens only. **No frame to compare against**; flag anything that looks wrong rather than assuming it is right.                                                                                                                                                                                                                                                             |
| Alert modals                  | `118:8948`, `129:9234`, `124:9186` | Banner colour per status — `--color-danger` unverified, `--color-warning` ongoing, neutral cleared; badge fill; metadata label treatment (`caption` + uppercase + `tracking-[0.08em]`); button pairing; **no actions on the cleared variant**.                                                                                                                             |

## Cross-cutting

Check these once, on any route:

- **No raw colour anywhere.** `pnpm lint:frontend` fails the build on an
  arbitrary hex, a Tailwind palette colour, or a bare colour literal. It is the
  mechanical half of this checklist and needs no manual pass.
- **Surfaces read as three, not ten.** Canvas behind everything, `surface-1`
  for cards and inputs, `surface-2` only where something is elevated or active.
- **Muted text is one grey.** If something looks dimmer than `--color-fg-muted`,
  it should be `opacity-60` on that token, never a new value.
- **Focus is visible.** `focus-visible` only, `--color-stroke-strong`, offset 2px.
- **Disabled is `opacity-60`,** with no colour change.

## Deviations from §2, and why

Recorded here rather than applied silently.

- **GPU Temperature series stays `--color-danger`.** §2.2 says Figma renders
  every chart series in white, which would drop the red that distinguishes a
  temperature chart from the three utilisation charts beside it. The value now
  comes from a token instead of a raw `#ef4444`, so the lint rule still holds.
- **`text-white` / `bg-white` / `text-black` were tokenised** even though §1's
  count covers only hex literals and palette classes. §2 defines `--color-fg`,
  `--color-primary` and `--color-fg-on-primary` for exactly those jobs; leaving
  them would have left every page title and primary button off the palette.
- **`Cleared` is now `--color-primary`, not green.** §2.2 lists it
  under the primary action alongside `Confirm Accident`. Worth a second look on
  the alert modal: it removes a green/red colour distinction between the two
  buttons, leaving position and label to carry it.
