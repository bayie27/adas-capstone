# Inventory mode — sweep the whole system against the paper

Not diff-driven. Where [`PROCEDURE.md`](PROCEDURE.md) asks _"this change broke which claim?"_, this asks the reverse for everything at once: **for each thing that exists, does the paper describe it, describe it wrongly, or not at all?**

Run this deliberately, not on every change. It exists because development ran ahead of the paper, so the backlog of undescribed work cannot be reached by watching new diffs — no future PR will ever surface a subsystem that shipped in July.

## How to run it

Steps 3–7 of `PROCEDURE.md` apply unchanged — same evidence rules, same OLD/NEW/Evidence shape, same dedupe against the live artifacts, same queue. Only the input differs: instead of a diff, you walk the requested areas below in batches. Step 8 remains available only for explicitly approved writes in a permitted runtime.

**Review one area at a time.** For a whole-system request, continue through all requested areas in successive batches within the task, recording coverage and reporting progress. For an unspecified inventory request, choose and state a starting area. Ask for clarification only when the requested scope cannot reasonably be determined. Batching is not a reason to stop before the requested scope is complete.

## Areas, and what to enumerate in each

| Area                | Enumerate                                                    | Compare against                                                                                                                                 |
| ------------------- | ------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| **Routes**          | Every router in `backend/app/api/routes/`                    | FR/NFR tables, use cases, the API narrative                                                                                                     |
| **Schema**          | Every model in `backend/app/models/`, every column and index | ERD (Figure 7), data dictionary (Tables 9–13)                                                                                                   |
| **Services**        | Every module in `backend/app/services/`                      | Chapter 3 architecture prose, DFDs, and the tables — a service's real guarantees often live in the data dictionary or an NFR row, not the prose |
| **AI engine**       | Every module in `ai_engine/` — pipeline, accumulator, outbox | Deep Learning Implementation, the detection narrative                                                                                           |
| **Scripts and ops** | `scripts/`, `backend/scripts/`, `backend/app/maintenance/`   | Deployment & Implementation, NFR-16 / NFR-18                                                                                                    |
| **Frontend**        | Routes and pages under `frontend/src/`                       | Wireframes (Figures 8–17), use-case steps                                                                                                       |
| **Dependencies**    | `pyproject.toml`, `frontend/package.json`                    | Frameworks and Libraries                                                                                                                        |

**These area boundaries are cleaner than the paper is.** A fact about one area routinely has to be checked against another area's tables. Treat the right-hand column as where to start, never as where to stop.

## The question to ask of each item

1. **Described correctly?** Record it as verified and move on — do not write a finding.
2. **Described wrongly?** Drift class 1. Normal finding.
3. **Described as absent, but it exists?** Drift class 2. The expensive one — the paper is understating the system to a panel.
4. **Not described at all?** Drift class 3. Judge whether it _should_ be: not every internal helper belongs in a defense document. A subsystem with its own failure modes, its own operational story, or its own requirement does. A utility function does not.

The already-known class-3 items are listed in [`PROCEDURE.md`](PROCEDURE.md) Step 4 — one list, one place, so it cannot drift. Check it, the live tracker Sheet, and local findings before re-raising any of them.

## Scoping honestly

The paper is a defense document, not an API reference. Adding every module to it makes it worse, not better. The bar for "the paper should describe this" is: **a panel member could reasonably ask about it, and the current text would leave you unable to point at anything.**

When you decide something is deliberately out of scope, say so in the report rather than staying silent — an unrecorded judgement call looks identical to an oversight.
