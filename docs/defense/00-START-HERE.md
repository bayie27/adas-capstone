# ADAS Final Defense — Study Pack

Everything you need to defend this system, split into 31 guides. Read this page first.

The last defense was **28 April 2026**. A great deal has changed since, so several guides
carry a _"What changed since the 28 April defense"_ section — those are the parts the
panel is most likely to probe, because they will remember the old version.

---

## How to use this pack

Every guide has the same eight sections:

1. **What it is** — plain language, no code
2. **Where it lives** — in the paper, and in the code
3. **How it works** — the real mechanism
4. **Why it was built this way** — the reasoning and the rejected alternatives
5. **What changed since the 28 April defense**
6. **Limits and honest caveats**
7. **Likely panel questions** — with answers you can actually say out loud
8. **Cram summary** — the five-minute version

**If you are short on time, read section 8 first, then section 7.** Those two sections
alone will get you through most questions. Sections 3 and 4 are what you need when a
panelist keeps pushing.

---

## Reading orders

### If you have 2 hours

Read the cram summaries and panel questions only, in this order:

1. [`28-numbers-cheat-sheet`](05-defense-craft/28-numbers-cheat-sheet.md) — every figure you might be asked for
2. [`01-objectives`](01-paper/01-objectives.md) — what you promised, and why the wording changed
3. [`26-ai-accuracy-and-evaluation`](04-ai/26-ai-accuracy-and-evaluation.md) — the accuracy answer
4. [`05-chapter4-results`](01-paper/05-chapter4-results.md) — what the testing proved
5. [`29-weak-points-and-limitations`](05-defense-craft/29-weak-points-and-limitations.md) — the soft spots, with answers ready
6. [`30-anticipated-qa`](05-defense-craft/30-anticipated-qa.md) — rehearse out loud

### If you have 1 day

The 2-hour list in full (all sections), plus the six high-priority guides:

- [`03-chapter2-rrl`](01-paper/03-chapter2-rrl.md) — your references justify most of your decisions
- [`08-requirements-fr-nfr`](01-paper/08-requirements-fr-nfr.md) — all 20 FRs and 22 NFRs
- [`13-security-architecture`](02-architecture/13-security-architecture.md) — never updated in the paper, so expect questions
- [`16-backup-and-restore`](02-architecture/16-backup-and-restore.md) — heavily revised last defense
- [`19-hitl-state-machine`](03-behaviour/19-hitl-state-machine.md) — the conceptual core of the system
- [`24-ai-pipeline`](04-ai/24-ai-pipeline.md) — how detection actually works

### If you have 1 week

All 31 guides, folder by folder, in numeric order.

---

## The guides

### [`01-paper/`](01-paper/) — The paper spine

What the document says, chapter by chapter.

| #   | Guide                                                            | Covers                                                          |
| --- | ---------------------------------------------------------------- | --------------------------------------------------------------- |
| 01  | [Objectives](01-paper/01-objectives.md)                          | All three objectives, old vs. new wording, and why each changed |
| 02  | [Chapter 1 — Introduction](01-paper/02-chapter1-introduction.md) | Background, problem, significance, scope                        |
| 03  | [Chapter 2 — RRL](01-paper/03-chapter2-rrl.md) ⭐                | Every reference and the decision it justifies                   |
| 04  | [Chapter 3 — Methodology](01-paper/04-chapter3-methodology.md)   | Research design and the development model                       |
| 05  | [Chapter 4 — Results](01-paper/05-chapter4-results.md) ⭐        | All ten testing activities and what they proved                 |
| 06  | [Chapter 5 — Conclusions](01-paper/06-chapter5-conclusions.md)   | Conclusions and recommendations                                 |
| 07  | [Definition of Terms](01-paper/07-definition-of-terms.md)        | Every technical term, defined twice — simply and deeply         |
| 08  | [FRs and NFRs](01-paper/08-requirements-fr-nfr.md) ⭐            | All 20 FRs and 22 NFRs, with evidence                           |

### [`02-architecture/`](02-architecture/) — Architecture and design

How the system is put together, and why.

| #   | Guide                                                                        | Covers                                                       |
| --- | ---------------------------------------------------------------------------- | ------------------------------------------------------------ |
| 09  | [System architecture](02-architecture/09-system-architecture.md)             | Three components, three seams                                |
| 10  | [Data model](02-architecture/10-data-model.md)                               | All ten tables and the data dictionary                       |
| 11  | [From 5 tables to 10](02-architecture/11-five-to-ten-tables.md)              | What was added since April, and what forced it               |
| 12  | [Design decisions](02-architecture/12-design-decisions.md)                   | Idempotency, heartbeat, database as single source of truth   |
| 13  | [Security architecture](02-architecture/13-security-architecture.md) ⭐      | The current picture, and how it differs from the old chapter |
| 14  | [RBAC and roles](02-architecture/14-rbac-and-roles.md)                       | Exactly what each role can and cannot do                     |
| 15  | [Audit trail](02-architecture/15-audit-trail.md)                             | Append-only logging and the one-transaction rule             |
| 16  | [Backup and restore](02-architecture/16-backup-and-restore.md) ⭐            | The most technical topic, explained plainly first            |
| 17  | [Networking and deployment](02-architecture/17-networking-and-deployment.md) | The production plan, and the three-laptop demo               |
| 18  | [Diagrams](02-architecture/18-diagrams-swimlane-dfd-erd.md)                  | Swimlane, DFD, use case, ERD — walked through                |

### [`03-behaviour/`](03-behaviour/) — How the system behaves

| #   | Guide                                                          | Covers                                             |
| --- | -------------------------------------------------------------- | -------------------------------------------------- |
| 19  | [HITL state machine](03-behaviour/19-hitl-state-machine.md) ⭐ | The four transitions and the self-blindfold        |
| 20  | [Alarm snooze](03-behaviour/20-alarm-snooze.md)                | Per-user preference vs. the shared incident snooze |
| 21  | [Real-time delivery](03-behaviour/21-realtime-websocket.md)    | WebSocket alerts and recovery after a disconnect   |
| 22  | [Reports and exports](03-behaviour/22-reports-and-exports.md)  | What the reports are for, and who reads them       |
| 23  | [System health](03-behaviour/23-system-health-telemetry.md)    | Telemetry, warnings, and the health endpoints      |

### [`04-ai/`](04-ai/) — The AI engine

| #   | Guide                                                                | Covers                                            |
| --- | -------------------------------------------------------------------- | ------------------------------------------------- |
| 24  | [AI pipeline](04-ai/24-ai-pipeline.md) ⭐                            | Stream to alert, including temporal accumulation  |
| 25  | [Training and dataset](04-ai/25-ai-training-and-dataset.md)          | How the model was trained and why this checkpoint |
| 26  | [Accuracy and evaluation](04-ai/26-ai-accuracy-and-evaluation.md) ⭐ | The accuracy answer, with all its qualifications  |
| 27  | [Performance](04-ai/27-ai-performance-fps-latency.md)                | Frame rate, latency, and camera capacity          |

### [`05-defense-craft/`](05-defense-craft/) — Defense preparation

| #   | Guide                                                             | Covers                                                |
| --- | ----------------------------------------------------------------- | ----------------------------------------------------- |
| 28  | [Numbers cheat sheet](05-defense-craft/28-numbers-cheat-sheet.md) | Every quotable figure, with its source                |
| 29  | [Weak points](05-defense-craft/29-weak-points-and-limitations.md) | The soft spots, each with a prepared answer           |
| 30  | [Anticipated Q&A](05-defense-craft/30-anticipated-qa.md)          | 60–80 questions, rehearsable                          |
| 31  | [Demo-day runbook](05-defense-craft/31-demo-day-runbook.md)       | Bring-up, validation, and recovery if the demo breaks |

⭐ = high priority. Read these properly, not just the cram summary.

---

## Ground rules these guides follow

So you know what you are reading and can trust it:

- **The paper and the test tracker are authoritative.** Where an internal engineering
  document words something differently, these guides follow the paper and the tracker.
- **No invented numbers.** Every figure traces back to the paper or the tracker. Anything
  marked `[UNSOURCED — verify]` still needs checking before you quote it.
- **Qualified results stay qualified.** Where the tracker records a result as simulated,
  accelerated, archival, or limited in scope, the guide says so — and so should you. State
  the qualification in the same breath as the number; it is far stronger than being caught
  omitting it.
- **Incidents are Cleared, not "Resolved."** The paper's terminology throughout.

---

## Source documents

If you need to go past the guides to the originals:

| Source                  | Where                                                           |
| ----------------------- | --------------------------------------------------------------- |
| Defense paper (246 pp.) | `docs/Group7_Capstone Project Defense Document - ITCAPROJ2.pdf` |
| Test plan               | `docs/Capstone Test Execution and Validation Plan.md`           |
| Test tracker            | `docs/ADAS Test Execution.xlsx`                                 |
| Demo topology           | `docs/operations/VMS_SIMULATOR_SETUP.md`                        |
| Old security chapter    | `docs/old-security-archi.pdf`                                   |
| How this pack was built | [`PLAN.md`](PLAN.md)                                            |
