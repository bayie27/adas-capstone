---
section: Frameworks and Libraries
page/s: "137"
required_revision: Frontend stack sentence names two libraries the codebase does not use (shadcn/ui, Lucide icons) instead of the two it actually uses (hand-rolled Tailwind components, Remix Icon)
notes: Found incidentally while checking whether frontend/src/pages/snapshot zoom PR's new dependency (react-zoom-pan-pinch) belonged in this paragraph — it does not (see report), but this paragraph's existing claim was wrong regardless
status: Not started
assigned_to: Meerio
synced: false
---

## Changes

### 1. Defense paper — Frameworks and Libraries, Frontend Layer bullet

Page/s: 137 (live Doc TOC, observed 2026-09-04)

#### Change metadata

Operation: replace
Scope: logical paragraph
Changed target: the final sentence of the "Frontend Layer (React.js Ecosystem & Tailwind)" bullet
Preserve: the rest of the bullet (React, React Router, Zustand, TanStack Query, Recharts sentences — all verified correct) and all surrounding bullets
Comment target: the full changed sentence, per logical-paragraph scope

#### OLD

> Tailwind CSS, shadcn/ui, and Lucide icons were employed to ensure a responsive, accessible, and cohesive web interface.

#### NEW

Tailwind CSS, hand-rolled house-style components, and Remix Icon were employed to ensure a responsive, accessible, and cohesive web interface.

#### Evidence

- `frontend/package.json` has no `shadcn`, no `@radix-ui/*`, no `class-variance-authority`; `frontend/components.json` (the shadcn CLI's own config file) does not exist.
- `frontend/src/components/ui/SidePanel.tsx:16-20` — explicit code comment: "Deliberately not shadcn/Radix (DT-6): this frontend has no components.json, no Radix and no CVA, so adding one would import a whole second component convention alongside the existing one for a single drawer."
- Locked decision `DT-6` — `dev_plan/00_OVERVIEW.md:54` ("The drawer is a house-style `ui/SidePanel.tsx`, **not** shadcn — The frontend has no Radix/CVA/`components.json`") and `dev_plan/03_PKG_dev_panel.md:56`.
- `lucide-react` is a `package.json` dependency but is imported by zero files (`grep -rl 'from "lucide-react"' frontend/src` → 0 matches, checked 2026-09-04).
- `@remixicon/react` is imported by 46 files across `frontend/src` (checked 2026-09-04), including every icon used in the accident-modal surfaces (`RiCloseLine`, `RiZoomInLine`, `RiAddLine`, `RiSubtractLine`, etc.).
- Single site: `shadcn`, `Lucide`, and `Radix` each appear exactly once in the live paper Doc — this sentence is the only place any of the three is mentioned, so no propagation elsewhere is required.

#### Proposed comment (same gate as associated replacement)

Previous (marked, intentionally non-verbatim): Tailwind CSS, [[shadcn/ui]], and [[Lucide icons]] were employed to ensure a responsive, accessible, and cohesive web interface.

Codex ID: PS-20260904-FRONTEND-UI-STACK

Done by Codex.

## Approval / sync ledger

Package ID: `PS-20260904-FRONTEND-UI-STACK`

User initially declined block 1 on 2026-09-04 ("I do not approve"), then clarified the decline was based on a misunderstanding and approved it the same day ("Now go fix it"). This Claude Code session's Google Drive connector is read-only (per the skill's Claude-specific notes: "do not enter the optional Codex Drive-write phase") — it has no tool capable of editing live Doc content or inserting a comment. Block 1 is therefore approved but blocked on capability: it needs a Codex session (or a human, manually) to apply the OLD→NEW replacement and its `Previous` comment, then read both back before `synced` can be set.

| Target                        | Approved scope    | Applied/read back | Skipped/pending | Blocked                                                               |
| ----------------------------- | ----------------- | ----------------- | --------------- | --------------------------------------------------------------------- |
| Defense paper                 | block 1           | —                 | —               | block 1 — no Drive-write tool in this runtime; needs Codex or a human |
| ADAS_Paper_Audit plus tracker | —                 | —                 | not proposed    | —                                                                     |
| Standalone comments           | block 1's comment | —                 | —               | same as block 1                                                       |
