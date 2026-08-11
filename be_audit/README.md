# ADAS Backend — Audit Pass

Opened 2026-08-10, after PRs #55–#70 merged P1–P10 plus the frontend migration — roughly
**24,000 lines across 152 backend files in two days**. `be_plan/` declared the backend finished and
production-ready. This directory is the pass that checks whether that is true.

`be_plan/` is the **planning record and stays immutable** except where a pack explicitly appends to
it. `be_audit/` is the verification record.

## Scope and posture

- **Deployment reality first, paper evidence second.** Both in scope; reliability leads.
- The realistic ceiling is **this laptop as the server, a second laptop as the client over the
  LAN** — not the paper's 8×L4 edge server. Every claim is labelled accordingly.
- Scope is **backend + its two contract seams** (AI engine, frontend). Not AI or frontend internals.
- The recent work is genuinely strong — 561 test functions / ~655 collected cases with real race,
  boundary, hostile-input and failure-injection coverage. This pass looks for what would fail *in
  the room*, not for things to rewrite.

## Files

| File | What it is |
|---|---|
| `00_FINDINGS.md` | **The register.** Single source of truth for audit state. Every pack updates the rows it owns. Also lists what was checked and cleared, so nothing gets re-raised. |
| `DEMO_TOPOLOGY.md` | **Read this before A1.** Why the demo is a wired two-node LAN (because that is what CDRRMO runs), how it maps to production, the demo-day runbook with per-step checks, kit list, hazards, fallback ladder, and answers to likely panel questions. |
| `A1_lan_tls_drill.md` | LAN + self-signed TLS end-to-end drill. **Run first.** Implements what `DEMO_TOPOLOGY.md` describes. |
| `A2_critical_fixes.md` | F1 test pragmas · F2 RTSP template fail-fast · F5 CORS · F7 export workers |
| `A3_ai_seam.md` | Delete the two clientless v1 routes · harden the heartbeat schema · live seam drill |
| `A4_realtime_hardening.md` | WS keepalive (verify, don't build) · request-id on 500s · binary frames |
| `A5_edge_cases.md` | Close edge cases 1.7 / 1.12 / 1.14 · rebuild the lost coverage register |
| `A6_manual_evidence.md` | Run the nine manual procedures · re-scope NFR-06 · refresh EVIDENCE.md |
| `A7_paper_reconciliation.md` | ~26 paper↔code divergences (the existing list has 5) · doc hygiene |
| `A8_housekeeping.md` | Layering fix · stray files · `/api/events/schema` auth posture |

## Running order

```
A1 (first — its results feed F5 and F8)
 ├─ A2  ┐
 ├─ A3  ├─ independent branches, any order
 └─ A4  ┘
A5  (after A2, so it walks the register against fixed code)
A6  (after A1–A4 land — the numbers must describe the demoed system)
A7  (any time; A6 feeds it one amendment)
A8  (last, or drop if time runs short)
```

One branch per pack, branched from `main`. Conventional Commits — commitlint enforces it on
`commit-msg`, and `pnpm check` runs on `pre-push`.

## Decisions already made by the owner

Do not re-open these; they were settled during audit planning.

1. **Delete both v1 internal camera routes** (`GET /api/internal/cameras`,
   `PATCH /api/internal/cameras/{id}/status`). Keep the v1 `/alert` payload branch —
   `backend/scripts/seed_alerts_via_api.py` still uses it.
2. **Real self-signed TLS for the LAN demo**, not an http profile. This fixes the Secure-cookie
   failure *and* makes the paper's HTTPS claim true.
3. **NFR-06 / TC-R-203 is re-scoped** to the real operating envelope — ~10 incidents/day, so ~300
   rows for a 30-day export. The paper's literal 10,000-row framing is disregarded. The 10,000-row
   measurement is **retained as a documented ceiling**, not deleted.
4. **Deployment target is a proof of concept.** A Linux edge server is what production *would* be;
   it will not happen. Linux artifacts stay implemented and labelled production-target so the
   capability is demonstrable, and are not presented as verified.

## Ground rules

- Run everything from the repo root with `uv run` — bare `python` on PATH is 3.14, the project is
  pinned to 3.12.13.
- `uv run pytest` then `pnpm check` before every push. **A2 is the exception**: enabling foreign-key
  enforcement in tests is *expected* to surface failures, and each one gets triaged as a real bug
  or a fixture bug. Neither gets muted by reverting the pragma.
- A procedure or assertion that fails is a **finding**, recorded in `00_FINDINGS.md` — not a reason
  to soften the procedure.
- Do not mark a finding resolved without either a fix or a written accepted-gap rationale.

---

## Kickoff prompts

Copy one into a fresh session. Each pack is self-contained — the session needs nothing from the
conversation that produced these files.

**A1**
> Read `be_audit/README.md`, `be_audit/00_FINDINGS.md`, `be_audit/DEMO_TOPOLOGY.md`, then
> `be_audit/A1_lan_tls_drill.md`, and execute that pack. The target topology is two laptops on a
> direct Ethernet cable with static IPs — that is what Lipa CDRRMO actually runs, not a fallback.
> You have full permission to run the backend, frontend, `ai_engine`, `mediamtx` and `ffmpeg` on
> this machine. Report what actually happened at each drill step, including anything that failed,
> and fold the commands you actually ran back into `DEMO_TOPOLOGY.md`.

**A2**
> Read `be_audit/README.md`, `be_audit/00_FINDINGS.md`, then `be_audit/A2_critical_fixes.md`, and
> execute that pack. Expect the F1 pragma change to break tests — triage each failure as a real bug
> or a fixture bug and say which, rather than reverting the pragma.

**A3**
> Read `be_audit/README.md`, `be_audit/00_FINDINGS.md`, `be_plan/01_CONTRACTS.md` §6, then
> `be_audit/A3_ai_seam.md`, and execute that pack. The live seam drill at the end needs the real
> stack running; you have permission to start it.

**A4**
> Read `be_audit/README.md`, `be_audit/00_FINDINGS.md`, then `be_audit/A4_realtime_hardening.md`,
> and execute that pack. Note that F6 is a verify-and-document job, not a build job — read it
> before writing code, and skip F8 entirely if A1 marked it `void`.

**A5**
> Read `be_audit/README.md`, `be_audit/00_FINDINGS.md`, `be_plan/14_EDGE_CASES.md`, then
> `be_audit/A5_edge_cases.md`, and execute that pack. Part 2 is the larger half — do not mark a row
> `covered` on the strength of a plausible test name; open the test.

**A6**
> Read `be_audit/README.md`, `be_audit/00_FINDINGS.md`, `be_plan/MANUAL_TESTS.md`,
> `be_plan/EVIDENCE.md`, then `be_audit/A6_manual_evidence.md`, and execute that pack. This is
> mostly execution and recording, not coding. Record what you observe, including failures.

**A7**
> Read `be_audit/README.md`, `be_audit/00_FINDINGS.md`, `final_paper_text.txt`,
> `be_plan/TRACEABILITY.md`, then `be_audit/A7_paper_reconciliation.md`, and execute that pack.
> Documentation only — no code changes.

**A8**
> Read `be_audit/README.md`, `be_audit/00_FINDINGS.md`, then `be_audit/A8_housekeeping.md`, and
> execute that pack. `test_reports.py::TestScreenExportParity` passing unchanged is the acceptance
> criterion for the refactor.
