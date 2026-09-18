# Thread prompts — copy one per Luna Max thread

One guide per thread. Each block below is self-contained: paste it as the first message of
a new thread, nothing else needed.

**Wave 1 — run all 28 in parallel:** guides 01–27 and 31.
**Wave 2 — run after Wave 1 has landed:** guides 28, 29, 30. These read the Wave 1 output
files as their primary input, so they must not start early.

`00-START-HERE.md` and `PLAN.md` already exist — do not regenerate them.

---

## Shared preamble

Every prompt below already embeds this. Shown once here for reference:

> You are writing ONE study guide for the ADAS capstone final defense. The audience is the
> four-person project team, who must defend this system to an academic panel. The repo root
> is the ADAS project.
>
> **Read `docs/defense/PLAN.md` first.** It holds the source map, the source-of-truth
> precedence rule, the house rules, and the guide template. Follow the template exactly —
> all eight sections, in order.
>
> **Source precedence is critical.** The defense paper and the test tracker are
> authoritative. Where a repo engineering doc frames something differently, follow the
> paper/tracker and do not comment on the difference, do not flag it as a risk, and do not
> hedge the paper's claim. Repo docs are for mechanism and rationale only.
>
> **Questions (section 7):** the seeds given are a MINIMUM, not the full set. Add the
> questions your topic actually invites, at the volume and emphasis PLAN.md describes for
> this kind of topic, and drop a seed that does not fit once you have the material. Answers
> must be speakable in under 30 seconds.
>
> ~300–500 lines. Every number traces to the paper or the tracker; if you cannot source
> one, write `[UNSOURCED — verify]`. Cite the paper by chapter/table/figure and code as
> `path/file.py:123`. Documentation only — do not modify any code.

---

# Wave 1

## 01 — Objectives

```text
You are writing ONE study guide for the ADAS capstone final defense. The audience is the four-person project team, who must defend this system to an academic panel. The repo root is the ADAS project.

Read docs/defense/PLAN.md first — source map, source-of-truth precedence, house rules, and the guide template. Follow the template exactly, all eight sections in order.

Source precedence is critical: the defense paper and the test tracker are authoritative. Where a repo engineering doc frames something differently, follow the paper/tracker, do not comment on the difference, and do not hedge the paper's claim. Repo docs are for mechanism and rationale only.

Write: docs/defense/01-paper/01-objectives.md

Topic: All three objectives of the study. Present the old and new wording side by side and explain the justification for each change. Cover why Objective 1 moved from "a custom-trained YOLO model" to "a real-time collision detection pipeline", and why Objective 3 moved from a sub-15-second to a 25-second end-to-end collision-to-operator-decision target — including the component budget for the 25 seconds as the test plan records it. Explain what each objective commits the team to proving, and which guide holds that proof.

Seed questions (a minimum — add your own): "Did you weaken your objectives to make them easier to hit?" / "Who approved the change?" / "Which objective was hardest to meet?"

Questions must be speakable in under 30 seconds. ~300-500 lines. Every number traces to the paper or the tracker; if you cannot source one, write [UNSOURCED — verify]. Cite the paper by chapter/table/figure and code as path/file.py:123. Documentation only — do not modify any code.
```

## 02 — Chapter 1: Introduction

```text
You are writing ONE study guide for the ADAS capstone final defense. The audience is the four-person project team, who must defend this system to an academic panel. The repo root is the ADAS project.

Read docs/defense/PLAN.md first — source map, source-of-truth precedence, house rules, and the guide template. Follow the template exactly, all eight sections in order.

Source precedence is critical: the defense paper and the test tracker are authoritative. Where a repo engineering doc frames something differently, follow the paper/tracker, do not comment on the difference, and do not hedge the paper's claim. Repo docs are for mechanism and rationale only.

Write: docs/defense/01-paper/02-chapter1-introduction.md

Topic: Chapter 1 — background of the study, statement of the problem, significance, and scope and delimitations. Explain the CDRRMO operational problem being solved, the notification gap, why Lipa City, and who benefits. Be precise about what is explicitly delimited out of scope and the reasoning for each exclusion, since delimitations are a common line of questioning.

Seed questions (a minimum — add your own): "What exactly is the gap you are closing?" / "Why can't CDRRMO just watch the monitors?" / "What did you deliberately leave out, and why?"

Questions must be speakable in under 30 seconds. ~300-500 lines. Every number traces to the paper or the tracker; if you cannot source one, write [UNSOURCED — verify]. Cite the paper by chapter/table/figure and code as path/file.py:123. Documentation only — do not modify any code.
```

## 03 — Chapter 2: RRL ⭐

```text
You are writing ONE study guide for the ADAS capstone final defense. The audience is the four-person project team, who must defend this system to an academic panel. The repo root is the ADAS project.

Read docs/defense/PLAN.md first — source map, source-of-truth precedence, house rules, and the guide template. Follow the template exactly, all eight sections in order.

Source precedence is critical: the defense paper and the test tracker are authoritative. Where a repo engineering doc frames something differently, follow the paper/tracker, do not comment on the difference, and do not hedge the paper's claim. Repo docs are for mechanism and rationale only.

Write: docs/defense/01-paper/03-chapter2-rrl.md

Topic: HIGH PRIORITY. Chapter 2 — Review of Related Literature and Studies. Cover all six thematic subsections plus the synthesis. For each study: what it investigated, what it found, the numbers it reported, and which specific ADAS design decision it justifies. Pay particular attention to the studies that underpin the detection approach and the accuracy expectations, because the team relies on these to justify their own model's performance.

Build an explicit table mapping "our claim -> the reference that supports it". Also note where the literature is thin or where a study's conditions differ from Lipa City's, since the panel may push on transferability.

Seed questions (a minimum — add your own): "What accuracy do comparable systems report, and how does yours compare?" / "Which paper justifies your threshold?" / "Did any study contradict your approach?" / "Is any of your literature out of date?"

Questions must be speakable in under 30 seconds. ~300-500 lines. Every number traces to the paper or the tracker; if you cannot source one, write [UNSOURCED — verify]. Cite the paper by chapter/table/figure and code as path/file.py:123. Documentation only — do not modify any code.
```

## 04 — Chapter 3: Methodology

```text
You are writing ONE study guide for the ADAS capstone final defense. The audience is the four-person project team, who must defend this system to an academic panel. The repo root is the ADAS project.

Read docs/defense/PLAN.md first — source map, source-of-truth precedence, house rules, and the guide template. Follow the template exactly, all eight sections in order.

Source precedence is critical: the defense paper and the test tracker are authoritative. Where a repo engineering doc frames something differently, follow the paper/tracker, do not comment on the difference, and do not hedge the paper's claim. Repo docs are for mechanism and rationale only.

Write: docs/defense/01-paper/04-chapter3-methodology.md

Topic: Chapter 3 — methodology, research design, and the project development model. Cover both development tracks (the AI track and the application track), all five phases, what each phase produced, and how the two tracks were kept in sync. Explain why this development model was chosen over the alternatives and what the exit criteria for each phase were.

Seed questions (a minimum — add your own): "Why this development model?" / "How did you decide a phase was done?" / "How did the AI and application work stay aligned?"

Questions must be speakable in under 30 seconds. ~300-500 lines. Every number traces to the paper or the tracker; if you cannot source one, write [UNSOURCED — verify]. Cite the paper by chapter/table/figure and code as path/file.py:123. Documentation only — do not modify any code.
```

## 05 — Chapter 4: Results ⭐

```text
You are writing ONE study guide for the ADAS capstone final defense. The audience is the four-person project team, who must defend this system to an academic panel. The repo root is the ADAS project.

Read docs/defense/PLAN.md first — source map, source-of-truth precedence, house rules, and the guide template. Follow the template exactly, all eight sections in order.

Source precedence is critical: the defense paper and the test tracker are authoritative. Where a repo engineering doc frames something differently, follow the paper/tracker, do not comment on the difference, and do not hedge the paper's claim. Repo docs are for mechanism and rationale only.

Write: docs/defense/01-paper/05-chapter4-results.md

Topic: HIGH PRIORITY, and the largest guide in the pack. Chapter 4 Results and Discussion, using the test plan and the test tracker as the evidence base.

Walk all ten testing activities (unit, integration, system/E2E, AI model validation, performance and load, reliability and endurance, backup and recovery, security, usability, UAT). For each: its acceptance criterion, what was actually executed, and the recorded outcome. Cover the headline figures — technical test cases, participant-stage executions, the SUS mean, the readiness items, and the formal acceptance decision — each with its source.

Critically: explain how each qualified result is qualified (simulated, duration-accelerated, archival, or scope-limited) and why that framing is the correct and defensible one. The team must be able to state a qualification in the same breath as the number.

Seed questions (a minimum — add your own): "Which criteria did you not fully prove, and why is that acceptable?" / "A 100% pass rate — why should we believe that?" / "Four participants, is that enough?" / "What does 'qualified' mean here?"

Questions must be speakable in under 30 seconds. ~300-500 lines. Every number traces to the paper or the tracker; if you cannot source one, write [UNSOURCED — verify]. Cite the paper by chapter/table/figure and code as path/file.py:123. Documentation only — do not modify any code.
```

## 06 — Chapter 5: Conclusions

```text
You are writing ONE study guide for the ADAS capstone final defense. The audience is the four-person project team, who must defend this system to an academic panel. The repo root is the ADAS project.

Read docs/defense/PLAN.md first — source map, source-of-truth precedence, house rules, and the guide template. Follow the template exactly, all eight sections in order.

Source precedence is critical: the defense paper and the test tracker are authoritative. Where a repo engineering doc frames something differently, follow the paper/tracker, do not comment on the difference, and do not hedge the paper's claim. Repo docs are for mechanism and rationale only.

Write: docs/defense/01-paper/06-chapter5-conclusions.md

Topic: Chapter 5 — summary, conclusions, recommendations, and future work. Tie each conclusion explicitly back to the objective it answers, so the team can show the chain from objective to evidence to conclusion. Cover the recommendations and what would be required to act on each.

Seed questions (a minimum — add your own): "Which objective is least well supported by your conclusions?" / "What is the single most important next step?" / "If you had another semester, what would you do?"

Questions must be speakable in under 30 seconds. ~300-500 lines. Every number traces to the paper or the tracker; if you cannot source one, write [UNSOURCED — verify]. Cite the paper by chapter/table/figure and code as path/file.py:123. Documentation only — do not modify any code.
```

## 07 — Definition of Terms

```text
You are writing ONE study guide for the ADAS capstone final defense. The audience is the four-person project team, who must defend this system to an academic panel. The repo root is the ADAS project.

Read docs/defense/PLAN.md first — source map, source-of-truth precedence, house rules, and the guide template. Follow the template exactly, all eight sections in order.

Source precedence is critical: the defense paper and the test tracker are authoritative. Where a repo engineering doc frames something differently, follow the paper/tracker, do not comment on the difference, and do not hedge the paper's claim. Repo docs are for mechanism and rationale only.

Write: docs/defense/01-paper/07-definition-of-terms.md

Topic: Every term from the paper's Definition of Terms that is technical enough to be probed. For each: the paper's own definition, then a deeper "if they push" explanation the team can give, and why the term matters to this system specifically.

Cover at least: mAP, IoU, RTSP, WebSocket Secure, human-in-the-loop, temporal accumulation, inference latency, write-ahead logging, idempotency, false positives per minute, System Usability Scale. Add any other term in the paper's list that a panelist could reasonably ask the team to define on the spot.

Section 7's format may deviate here — per-term "define X and why it matters" prompts work better than a standard Q&A block. That is fine, but keep the section.

Questions must be speakable in under 30 seconds. ~300-500 lines. Every number traces to the paper or the tracker; if you cannot source one, write [UNSOURCED — verify]. Cite the paper by chapter/table/figure and code as path/file.py:123. Documentation only — do not modify any code.
```

## 08 — FRs and NFRs ⭐

```text
You are writing ONE study guide for the ADAS capstone final defense. The audience is the four-person project team, who must defend this system to an academic panel. The repo root is the ADAS project.

Read docs/defense/PLAN.md first — source map, source-of-truth precedence, house rules, and the guide template. Follow the template exactly, all eight sections in order.

Source precedence is critical: the defense paper and the test tracker are authoritative. Where a repo engineering doc frames something differently, follow the paper/tracker, do not comment on the difference, and do not hedge the paper's claim. Repo docs are for mechanism and rationale only.

Write: docs/defense/01-paper/08-requirements-fr-nfr.md

Topic: HIGH PRIORITY. All 20 functional requirements (FR-01 to FR-20) and all 22 non-functional requirements (NFR-01 to NFR-22).

For each requirement, give: the paper's requirement text, where it is implemented in the code (path/file.py:line), how it was verified, and the tracker's recorded result. Keep this scannable — a table per group, with prose only where a requirement needs explanation.

One documentation gap to note plainly: the tracker's UAT Traceability sheet carries no row for NFR-10 Workflow Efficiency, although the requirement exists in the paper. State this as a traceability gap and prepare the answer for how NFR-10 is nonetheless satisfied.

When searching the paper text extraction, beware that "FR-19" also matches "NFR-19" — anchor your searches.

Seed questions (a minimum — add your own): "Show me a requirement you only partly met." / "Which requirement was added late, and why?" / "How do you know FR-xx actually works?" / "Which requirement was hardest?"

Questions must be speakable in under 30 seconds. ~300-500 lines. Every number traces to the paper or the tracker; if you cannot source one, write [UNSOURCED — verify]. Cite the paper by chapter/table/figure and code as path/file.py:123. Documentation only — do not modify any code.
```

## 09 — System architecture

```text
You are writing ONE study guide for the ADAS capstone final defense. The audience is the four-person project team, who must defend this system to an academic panel. The repo root is the ADAS project.

Read docs/defense/PLAN.md first — source map, source-of-truth precedence, house rules, and the guide template. Follow the template exactly, all eight sections in order.

Source precedence is critical: the defense paper and the test tracker are authoritative. Where a repo engineering doc frames something differently, follow the paper/tracker, do not comment on the difference, and do not hedge the paper's claim. Repo docs are for mechanism and rationale only.

Write: docs/defense/02-architecture/09-system-architecture.md

Topic: The overall system architecture — three components and the three seams between them. The AI engine reaches the backend over an authenticated HTTP webhook; the backend reaches the frontend over a WebSocket; the frontend reaches the backend over REST for everything else. Cover the paper's client-server diagram, the deployment architecture section, and the frameworks and libraries the paper lists.

Explain why the system is split into three processes rather than one, what each component owns, and what happens when any one of them is unavailable.

Seed questions (a minimum — add your own): "Why three processes instead of one?" / "What happens if the AI engine dies?" / "Why FastAPI, React and SQLite specifically?" / "Could this run on one machine? Does it?"

Questions must be speakable in under 30 seconds. ~300-500 lines. Every number traces to the paper or the tracker; if you cannot source one, write [UNSOURCED — verify]. Cite the paper by chapter/table/figure and code as path/file.py:123. Documentation only — do not modify any code.
```

## 10 — Data model

```text
You are writing ONE study guide for the ADAS capstone final defense. The audience is the four-person project team, who must defend this system to an academic panel. The repo root is the ADAS project.

Read docs/defense/PLAN.md first — source map, source-of-truth precedence, house rules, and the guide template. Follow the template exactly, all eight sections in order.

Source precedence is critical: the defense paper and the test tracker are authoritative. Where a repo engineering doc frames something differently, follow the paper/tracker, do not comment on the difference, and do not hedge the paper's claim. Repo docs are for mechanism and rationale only.

Write: docs/defense/02-architecture/10-data-model.md

Topic: The complete data model — all ten tables plus the full-text search virtual table — mapped against the paper's data dictionary and ERD. For each table: what it stores, its key columns, and its constraints.

Cover in depth the patterns a panelist can probe: the custom UTC datetime type and why naive datetimes are rejected at the database boundary; storing enums as plain strings guarded by CHECK constraints rather than database enum types; and the partial unique indexes, explaining what each one makes impossible (at most one open incident per camera, and soft-delete-friendly uniqueness on camera name and channel).

Seed questions (a minimum — add your own): "Why enforce that in the database instead of in Python?" / "Why SQLite for a system that runs 24/7?" / "What stops two incidents opening on the same camera?" / "How do you handle time zones?"

Questions must be speakable in under 30 seconds. ~300-500 lines. Every number traces to the paper or the tracker; if you cannot source one, write [UNSOURCED — verify]. Cite the paper by chapter/table/figure and code as path/file.py:123. Documentation only — do not modify any code.
```

## 11 — From 5 tables to 10

```text
You are writing ONE study guide for the ADAS capstone final defense. The audience is the four-person project team, who must defend this system to an academic panel. The repo root is the ADAS project.

Read docs/defense/PLAN.md first — source map, source-of-truth precedence, house rules, and the guide template. Follow the template exactly, all eight sections in order.

Source precedence is critical: the defense paper and the test tracker are authoritative. Where a repo engineering doc frames something differently, follow the paper/tracker, do not comment on the difference, and do not hedge the paper's claim. Repo docs are for mechanism and rationale only.

Write: docs/defense/02-architecture/11-five-to-ten-tables.md

Topic: The schema grew from 5 tables at the 28 April 2026 defense to 10 today. Establish what the original five were, what the current ten are, and for each addition: what it stores, which functional or non-functional requirement forced it into existence, and what would break or become impossible without it.

Use `git log --since="2026-04-28" -- backend/app/models/` to build the timeline and identify when each table appeared and in what work.

The framing matters: this is requirement-driven growth, not a design error being corrected. Make that case with evidence rather than assertion.

Seed questions (a minimum — add your own): "Why did your schema double — was the original design wrong?" / "Which of these could you have avoided?" / "Did adding tables hurt performance?" / "Which one was the most important addition?"

Questions must be speakable in under 30 seconds. ~300-500 lines. Every number traces to the paper or the tracker; if you cannot source one, write [UNSOURCED — verify]. Cite the paper by chapter/table/figure and code as path/file.py:123. Documentation only — do not modify any code.
```

## 12 — Design decisions

```text
You are writing ONE study guide for the ADAS capstone final defense. The audience is the four-person project team, who must defend this system to an academic panel. The repo root is the ADAS project.

Read docs/defense/PLAN.md first — source map, source-of-truth precedence, house rules, and the guide template. Follow the template exactly, all eight sections in order.

Source precedence is critical: the defense paper and the test tracker are authoritative. Where a repo engineering doc frames something differently, follow the paper/tracker, do not comment on the difference, and do not hedge the paper's claim. Repo docs are for mechanism and rationale only.

Write: docs/defense/02-architecture/12-design-decisions.md

Topic: The cross-cutting engineering decisions that shape the whole system. Cover each with the problem it solves and what would break without it:

- Idempotency on the alert webhook via a source event ID, so a replayed alert returns success without creating a duplicate incident or re-broadcasting
- The fixed-cadence heartbeat that returns a complete authoritative snapshot of every active camera rather than a delta, making recovery deterministic after either side restarts
- The database as the single source of truth, with in-memory scheduling treated as an optimisation rather than the correctness mechanism
- The desired-versus-observed split on camera state, separating what the operator wants from what the engine reports
- Commit-then-broadcast ordering, and why the reverse would be unsafe
- Conditional UPDATE as the concurrency primitive for state transitions
- The durable outbox with exponential backoff between the AI engine and the backend

Seed questions (a minimum — add your own): "What if the same alert arrives twice?" / "Why not keep state in memory?" / "What happens if the backend is down when a collision is detected?" / "Why is the heartbeat a full snapshot?"

Questions must be speakable in under 30 seconds. ~300-500 lines. Every number traces to the paper or the tracker; if you cannot source one, write [UNSOURCED — verify]. Cite the paper by chapter/table/figure and code as path/file.py:123. Documentation only — do not modify any code.
```

## 13 — Security architecture ⭐

```text
You are writing ONE study guide for the ADAS capstone final defense. The audience is the four-person project team, who must defend this system to an academic panel. The repo root is the ADAS project.

Read docs/defense/PLAN.md first — source map, source-of-truth precedence, house rules, and the guide template. Follow the template exactly, all eight sections in order.

Source precedence is critical: the defense paper and the test tracker are authoritative. Where a repo engineering doc frames something differently, follow the paper/tracker, do not comment on the difference, and do not hedge the paper's claim. Repo docs are for mechanism and rationale only.

Write: docs/defense/02-architecture/13-security-architecture.md

Topic: HIGH PRIORITY. The security architecture was omitted from the main paper and has not been updated since the 28 April defense, so this guide has to build the current picture from the code and from the security testing record in the tracker.

Document what is implemented today: password hashing, the cookie-based session model and its cookie attributes, server-side revocable session records, the explicit algorithm/issuer/audience pinning on token decoding, role-based authorisation through dependency injection, the internal API key with constant-time comparison protecting the AI engine's webhook, login rate limiting, CORS together with origin pinning on state-changing requests, the WebSocket origin check performed before any database work, and HTTPS/WSS transport with the adas.local certificate.

Then give a clear before-and-after table against docs/old-security-archi.pdf, which described the pre-April design. Explain what the session model change alters in practice, and how cross-site request forgery is addressed under the current design. Present this as the system's evolution, not as a correction of an error.

Cross-check against the Security Testing sheet in the tracker so the guide's claims match the recorded evidence.

Seed questions (a minimum — add your own): "How is the session protected, and what happens if it leaks?" / "Why cookies instead of bearer tokens?" / "What stops a script on the same LAN from faking an accident alert?" / "A self-signed certificate — isn't that insecure?" / "How do you revoke access immediately?"

Questions must be speakable in under 30 seconds. ~300-500 lines. Every number traces to the paper or the tracker; if you cannot source one, write [UNSOURCED — verify]. Cite the paper by chapter/table/figure and code as path/file.py:123. Documentation only — do not modify any code.
```

## 14 — RBAC and roles

```text
You are writing ONE study guide for the ADAS capstone final defense. The audience is the four-person project team, who must defend this system to an academic panel. The repo root is the ADAS project.

Read docs/defense/PLAN.md first — source map, source-of-truth precedence, house rules, and the guide template. Follow the template exactly, all eight sections in order.

Source precedence is critical: the defense paper and the test tracker are authoritative. Where a repo engineering doc frames something differently, follow the paper/tracker, do not comment on the difference, and do not hedge the paper's claim. Repo docs are for mechanism and rationale only.

Write: docs/defense/02-architecture/14-rbac-and-roles.md

Topic: The complete role-based access control picture. Produce an endpoint-by-endpoint matrix of what an Operator can do versus what an Administrator can do, derived from the actual route definitions rather than from documentation.

Explain the enforcement mechanism: where the role is checked, why the role is re-read from the database rather than trusted from the token, where the 403 is produced, and the fact that a denial writes its own audit record. Tie this to the relevant FR and to the RBAC items in the Security Testing sheet.

Seed questions (a minimum — add your own): "Show me exactly what an Operator cannot do." / "Could an Operator escalate to Administrator?" / "What if someone's role changes mid-session?" / "Where is that enforced — the frontend or the backend?"

Questions must be speakable in under 30 seconds. ~300-500 lines. Every number traces to the paper or the tracker; if you cannot source one, write [UNSOURCED — verify]. Cite the paper by chapter/table/figure and code as path/file.py:123. Documentation only — do not modify any code.
```

## 15 — Audit trail

```text
You are writing ONE study guide for the ADAS capstone final defense. The audience is the four-person project team, who must defend this system to an academic panel. The repo root is the ADAS project.

Read docs/defense/PLAN.md first — source map, source-of-truth precedence, house rules, and the guide template. Follow the template exactly, all eight sections in order.

Source precedence is critical: the defense paper and the test tracker are authoritative. Where a repo engineering doc frames something differently, follow the paper/tracker, do not comment on the difference, and do not hedge the paper's claim. Repo docs are for mechanism and rationale only.

Write: docs/defense/02-architecture/15-audit-trail.md

Topic: The activity audit trail. Cover the action catalogue and how a single definition generates both the database CHECK constraint and the enum used for query validation; append-only enforcement by database triggers that reject updates and deletes outright; and detail redaction.

The central design point to explain carefully: every audited state change and its audit record commit in one transaction, so an audited action can never land without its evidence. Then explain the counterpart — how denied and failure records are written in a separate short transaction after the primary one has rolled back, and why losing an audit write must never turn a 403 into a 500.

Tie to the audit-related FR and NFR and to the audit items in the Security Testing sheet.

Seed questions (a minimum — add your own): "Can an administrator delete an audit entry?" / "What happens if the audit write fails?" / "Would this stand up as evidence?" / "What exactly gets recorded when an operator dismisses an alert?" / "Do you log failed logins?"

Questions must be speakable in under 30 seconds. ~300-500 lines. Every number traces to the paper or the tracker; if you cannot source one, write [UNSOURCED — verify]. Cite the paper by chapter/table/figure and code as path/file.py:123. Documentation only — do not modify any code.
```

## 16 — Backup and restore ⭐

```text
You are writing ONE study guide for the ADAS capstone final defense. The audience is the four-person project team, who must defend this system to an academic panel. The repo root is the ADAS project.

Read docs/defense/PLAN.md first — source map, source-of-truth precedence, house rules, and the guide template. Follow the template exactly, all eight sections in order.

Source precedence is critical: the defense paper and the test tracker are authoritative. Where a repo engineering doc frames something differently, follow the paper/tracker, do not comment on the difference, and do not hedge the paper's claim. Repo docs are for mechanism and rationale only.

Write: docs/defense/02-architecture/16-backup-and-restore.md

Topic: HIGH PRIORITY, and the most technically dense subject in the pack. The team has said they find this one genuinely hard to follow, so lead section 3 with a plain-language walkthrough — "what actually happens, in order, in ordinary words" — before any technical detail. Then go deep.

Backup: an online page-level database copy taken through the database's own backup API rather than a file copy, and why that matters while the system is running; the disk-space precheck; integrity and foreign-key verification; the checksum; atomic publication; the manifest; retention tiers; the protected-versus-degraded storage tiers; and the locking that prevents a scheduled job racing an API request.

Restore, and the key architectural point: the API never restores anything itself. It writes a durable request and a separately supervised coordinator performs the swap with services stopped. Explain why it has to work that way. Then the guards — administrator role, password re-verification, an exact confirmation phrase, identifier validation before any path is built, and a conflict response when the system is busy — followed by the emergency backup taken before the swap, verify-then-replace, rollback on failure, and the readiness gate on restart.

Cross-check every timing and outcome against the Backup & Recovery sheet in the tracker.

Seed questions (a minimum — add your own): "What if the power cuts in the middle of a restore?" / "Can you back up while the system is running and detecting?" / "Who can trigger a restore, and what stops a mistake?" / "How do you know a backup isn't corrupt?" / "How long is the system down during a restore?" / "What happens to alerts that arrive during a restore?"

Questions must be speakable in under 30 seconds. ~300-500 lines. Every number traces to the paper or the tracker; if you cannot source one, write [UNSOURCED — verify]. Cite the paper by chapter/table/figure and code as path/file.py:123. Documentation only — do not modify any code.
```

## 17 — Networking and deployment

```text
You are writing ONE study guide for the ADAS capstone final defense. The audience is the four-person project team, who must defend this system to an academic panel. The repo root is the ADAS project.

Read docs/defense/PLAN.md first — source map, source-of-truth precedence, house rules, and the guide template. Follow the template exactly, all eight sections in order.

Source precedence is critical: the defense paper and the test tracker are authoritative. Where a repo engineering doc frames something differently, follow the paper/tracker, do not comment on the difference, and do not hedge the paper's claim. Repo docs are for mechanism and rationale only.

Write: docs/defense/02-architecture/17-networking-and-deployment.md

Topic: Two distinct things — keep them clearly separated, because conflating them is the single easiest way to over-claim in front of the panel.

(a) The intended production deployment: the CDRRMO topology as the paper describes it, on-premises positioning, data localization, and the main RTSP feed target. Keep the scope exactly as honest as the tracker records it — this is a proof of concept, not a completed live rollout.

(b) The demonstration topology actually used, from docs/operations/VMS_SIMULATOR_SETUP.md: a three-device private LAN with a Linux VMS laptop publishing RTSP, the Windows ADAS server running backend, frontend and AI engine, and a browser-only operator laptop. Cover the ports and their directions, the DHCP reservations, the firewall rule restricting RTSP to the server alone, the Windows inbound rules, the hostname mapping, and certificate trust on the operator machine. Explain why the operator laptop is deliberately denied RTSP access.

Seed questions (a minimum — add your own): "Is this deployed at CDRRMO right now?" / "Why simulate the cameras instead of using real ones?" / "What changes when you move to real CCTV?" / "Why is the operator laptop blocked from the camera streams?" / "What happens if the network drops mid-incident?"

Questions must be speakable in under 30 seconds. ~300-500 lines. Every number traces to the paper or the tracker; if you cannot source one, write [UNSOURCED — verify]. Cite the paper by chapter/table/figure and code as path/file.py:123. Documentation only — do not modify any code.
```

## 18 — Diagrams: swimlane, DFD, ERD

```text
You are writing ONE study guide for the ADAS capstone final defense. The audience is the four-person project team, who must defend this system to an academic panel. The repo root is the ADAS project.

Read docs/defense/PLAN.md first — source map, source-of-truth precedence, house rules, and the guide template. Follow the template exactly, all eight sections in order.

Source precedence is critical: the defense paper and the test tracker are authoritative. Where a repo engineering doc frames something differently, follow the paper/tracker, do not comment on the difference, and do not hedge the paper's claim. Repo docs are for mechanism and rationale only.

Write: docs/defense/02-architecture/18-diagrams-swimlane-dfd-erd.md

Topic: Every diagram in the paper, walked through so the team can narrate any of them on demand: the swimlane diagram, the data flow diagrams (context and levelled), the use case diagram, the entity relationship diagram, and the client-server diagram.

The diagrams are images, so read them from the rendered page PNGs under paper_sync/.local/defense-pages-20260916-final/ rather than the text extraction. For each diagram: identify every actor, process, data store and flow; say what each one means; and map it to the real code so the team can connect a box on a slide to a file in the repo.

Note that the DFD was overhauled during development — describe the current one as it stands in the paper.

Seed questions (a minimum — add your own): "Walk me through your data flow diagram." / "Where does the operator appear in the swimlane?" / "Why is that a data store and not a process?" / "Which use case covers the false-positive path?" / "Your ERD shows that relationship as one-to-many — why?"

Questions must be speakable in under 30 seconds. ~300-500 lines. Every number traces to the paper or the tracker; if you cannot source one, write [UNSOURCED — verify]. Cite the paper by chapter/table/figure and code as path/file.py:123. Documentation only — do not modify any code.
```

## 19 — HITL state machine ⭐

```text
You are writing ONE study guide for the ADAS capstone final defense. The audience is the four-person project team, who must defend this system to an academic panel. The repo root is the ADAS project.

Read docs/defense/PLAN.md first — source map, source-of-truth precedence, house rules, and the guide template. Follow the template exactly, all eight sections in order.

Source precedence is critical: the defense paper and the test tracker are authoritative. Where a repo engineering doc frames something differently, follow the paper/tracker, do not comment on the difference, and do not hedge the paper's claim. Repo docs are for mechanism and rationale only.

Write: docs/defense/03-behaviour/19-hitl-state-machine.md

Topic: The human-in-the-loop verification workflow — the conceptual heart of the system.

Cover the legal transitions (Unverified to Ongoing to Cleared for a true positive; Unverified to Dismissed for a false positive; Ongoing to Dismissed as a human correction) and why no others are permitted. Note the paper's terminology: incidents are Cleared, never "Resolved".

Explain how a transition is performed as a single conditional update so two operators acting simultaneously cannot both succeed, and what the losing operator is told.

Then the self-blindfold pattern: on detection the AI engine immediately pauses its own ingestion for that camera, and the backend mirrors this by marking the camera paused and broadcasting before any operator acts. Explain why that ordering is mandatory and what would go wrong if it were reversed.

Finally the dismissal cooldown: why a false-positive dismissal holds the camera for a cooldown period, why that state is durable in the database rather than held in memory, and why a human correction from Ongoing to Dismissed resumes immediately instead.

Seed questions (a minimum — add your own): "What if two operators click at once?" / "Why blind your own camera at exactly the moment of the accident?" / "Can an operator undo a mistake?" / "What if the operator never responds?" / "Why a cooldown after a dismissal?" / "What happens to the state machine if the server restarts mid-incident?"

Questions must be speakable in under 30 seconds. ~300-500 lines. Every number traces to the paper or the tracker; if you cannot source one, write [UNSOURCED — verify]. Cite the paper by chapter/table/figure and code as path/file.py:123. Documentation only — do not modify any code.
```

## 20 — Alarm snooze

```text
You are writing ONE study guide for the ADAS capstone final defense. The audience is the four-person project team, who must defend this system to an academic panel. The repo root is the ADAS project.

Read docs/defense/PLAN.md first — source map, source-of-truth precedence, house rules, and the guide template. Follow the template exactly, all eight sections in order.

Source precedence is critical: the defense paper and the test tracker are authoritative. Where a repo engineering doc frames something differently, follow the paper/tracker, do not comment on the difference, and do not hedge the paper's claim. Repo docs are for mechanism and rationale only.

Write: docs/defense/03-behaviour/20-alarm-snooze.md

Topic: Everything about alarm snooze. The critical thing is to separate two things that are easy to conflate:

1. The per-user alarm preference — sound, volume, and a snooze duration within a bounded range, autosaved rather than saved by a button.
2. The incident snooze itself — which is global, not per-user. Only an unverified incident can be snoozed; the duration comes from the acting user's preference, but the resulting mute applies to every dashboard. A duration supplied by the client is rejected.

Explain the expiry mechanism: an atomic conditional update means only the process that actually clears the snooze broadcasts the re-alarm, so duplicate or late jobs stay silent. Cover the scheduler job and its stable identifier, the periodic sweep, startup reconciliation after a restart, and why a terminal transition clears the snooze fields in the same update — making the in-memory job an optimisation rather than the correctness mechanism.

Tie to the relevant FRs for audible alert timeout/escalation and the alarm configuration module.

Seed questions (a minimum — add your own): "If one operator snoozes, does everyone go quiet? Is that safe?" / "What stops an alert being silenced indefinitely?" / "What happens if the server restarts mid-snooze?" / "Why is the snooze global rather than per-operator?" / "Can an operator snooze an incident someone else is already handling?"

Questions must be speakable in under 30 seconds. ~300-500 lines. Every number traces to the paper or the tracker; if you cannot source one, write [UNSOURCED — verify]. Cite the paper by chapter/table/figure and code as path/file.py:123. Documentation only — do not modify any code.
```

## 21 — Real-time delivery

```text
You are writing ONE study guide for the ADAS capstone final defense. The audience is the four-person project team, who must defend this system to an academic panel. The repo root is the ADAS project.

Read docs/defense/PLAN.md first — source map, source-of-truth precedence, house rules, and the guide template. Follow the template exactly, all eight sections in order.

Source precedence is critical: the defense paper and the test tracker are authoritative. Where a repo engineering doc frames something differently, follow the paper/tracker, do not comment on the difference, and do not hedge the paper's claim. Repo docs are for mechanism and rationale only.

Write: docs/defense/03-behaviour/21-realtime-websocket.md

Topic: How an alert actually reaches the operator's screen. Cover the alert WebSocket channel: the cookie-authenticated handshake, the origin check performed before any database work, connection limits per user and overall, per-connection bounded queues and what happens when a client cannot keep up, and the typed event envelopes the frontend consumes.

Explain the commit-then-broadcast rule and the fact that broadcast ordering is itself a contract, not an accident.

Then asynchronous alert recovery: how a dashboard re-synchronises and displays every currently unverified alert on reload or reconnection, so an operator who was disconnected loses nothing. Tie this to the relevant NFR and its acceptance criterion.

Seed questions (a minimum — add your own): "What if the operator's browser was closed when the alert fired?" / "How do you know the dashboard is still connected?" / "What if the WebSocket drops mid-incident?" / "What if a slow client can't keep up with the alerts?" / "Why WebSocket rather than polling?"

Questions must be speakable in under 30 seconds. ~300-500 lines. Every number traces to the paper or the tracker; if you cannot source one, write [UNSOURCED — verify]. Cite the paper by chapter/table/figure and code as path/file.py:123. Documentation only — do not modify any code.
```

## 22 — Reports and exports

```text
You are writing ONE study guide for the ADAS capstone final defense. The audience is the four-person project team, who must defend this system to an academic panel. The repo root is the ADAS project.

Read docs/defense/PLAN.md first — source map, source-of-truth precedence, house rules, and the guide template. Follow the template exactly, all eight sections in order.

Source precedence is critical: the defense paper and the test tracker are authoritative. Where a repo engineering doc frames something differently, follow the paper/tracker, do not comment on the difference, and do not hedge the paper's claim. Repo docs are for mechanism and rationale only.

Write: docs/defense/03-behaviour/22-reports-and-exports.md

Topic: Report generation and data export. Cover the report types (incident, audit, dashboard, AI performance), both output formats, the distinction between synchronous exports over an operational window and asynchronous export jobs for larger ranges, the CDRRMO branding, the human-readable value formatting, and why internal identifiers are stripped from exported output.

Include the purpose question explicitly, because it is a known soft spot. The real CDRRMO workflow is that accidents from the 2-10 and 10-6 shifts are passed to PDRRMO, and records are also requested by researchers and students who approach the office. Frame shift handover as the primary driver and the secondary uses honestly as secondary. Do not invent institutional requirements that were never stated — an honest, narrower justification is stronger than an inflated one.

Tie to the relevant FR and to the report generation and export scalability NFR with its recorded performance results.

Seed questions (a minimum — add your own): "Who actually reads these reports?" / "Why four different report types?" / "What stops an export leaking personal data?" / "Why is the large export asynchronous?" / "Could an Operator export the audit log?"

Questions must be speakable in under 30 seconds. ~300-500 lines. Every number traces to the paper or the tracker; if you cannot source one, write [UNSOURCED — verify]. Cite the paper by chapter/table/figure and code as path/file.py:123. Documentation only — do not modify any code.
```

## 23 — System health and telemetry

```text
You are writing ONE study guide for the ADAS capstone final defense. The audience is the four-person project team, who must defend this system to an academic panel. The repo root is the ADAS project.

Read docs/defense/PLAN.md first — source map, source-of-truth precedence, house rules, and the guide template. Follow the template exactly, all eight sections in order.

Source precedence is critical: the defense paper and the test tracker are authoritative. Where a repo engineering doc frames something differently, follow the paper/tracker, do not comment on the difference, and do not hedge the paper's claim. Repo docs are for mechanism and rationale only.

Write: docs/defense/03-behaviour/23-system-health-telemetry.md

Topic: System health and hardware telemetry. Cover the two unauthenticated probes — liveness and readiness — and explain why readiness genuinely checks the database rather than returning a constant, since the restart after a restore gates on it. Then the authenticated telemetry surface: CPU, memory and GPU sampling, the raw sample retention window, the hourly rollup with its own retention and its idempotency key, and the machine-readable warnings carrying code, severity, measurement and threshold.

Cover the frame-rate warning floor and how a degraded camera surfaces to the operator. Explain why the health, telemetry and maintenance routers are three separate modules by design rather than one.

Tie to the system health FR and the telemetry refresh rate NFR.

Seed questions (a minimum — add your own): "How would an operator know the system is unhealthy?" / "Why is one health endpoint unauthenticated?" / "What does the dashboard show if a camera is running slowly?" / "How long do you keep telemetry?" / "What counts as a warning versus a failure?"

Questions must be speakable in under 30 seconds. ~300-500 lines. Every number traces to the paper or the tracker; if you cannot source one, write [UNSOURCED — verify]. Cite the paper by chapter/table/figure and code as path/file.py:123. Documentation only — do not modify any code.
```

## 24 — AI pipeline ⭐

```text
You are writing ONE study guide for the ADAS capstone final defense. The audience is the four-person project team, who must defend this system to an academic panel. The repo root is the ADAS project.

Read docs/defense/PLAN.md first — source map, source-of-truth precedence, house rules, and the guide template. Follow the template exactly, all eight sections in order.

Source precedence is critical: the defense paper and the test tracker are authoritative. Where a repo engineering doc frames something differently, follow the paper/tracker, do not comment on the difference, and do not hedge the paper's claim. Repo docs are for mechanism and rationale only.

Write: docs/defense/04-ai/24-ai-pipeline.md

Topic: The AI engine end to end — from camera stream to alert on the operator's screen. Trace every stage: RTSP ingestion and decoding with bounded timeouts and a pinned transport, the fixed-cadence scheduler that slips rather than accumulating a backlog, the dropping of stale frames, preprocessing, batched inference, class filtering, temporal accumulation, event selection, the camera pause, the annotated snapshot, and the durable outbox delivering to the backend webhook.

Give temporal accumulation the depth it deserves — it is what makes the low detection confidence threshold safe, and a panelist will ask about that threshold. Explain that it is a leaky integrator rather than a consecutive-frame counter: detections link to an existing region by overlap, evidence accumulates as confidence multiplied by elapsed time, unmatched regions decay, boxes are smoothed, and an event fires only once accumulated evidence crosses a threshold. The consequence to state plainly: a single frame can never raise an alert.

Then cover the four accumulator reset seams — reconnect, resume, restart, and a long gap between processed frames — and explain why the fourth exists and what removing it would allow.

Seed questions (a minimum — add your own): "Why such a low confidence threshold — isn't that reckless?" / "How do you avoid alerting on every near-miss?" / "What if the stream stutters or freezes?" / "How long after a collision does the alert appear?" / "What happens if a camera disconnects mid-accident?"

Questions must be speakable in under 30 seconds. ~300-500 lines. Every number traces to the paper or the tracker; if you cannot source one, write [UNSOURCED — verify]. Cite the paper by chapter/table/figure and code as path/file.py:123. Documentation only — do not modify any code.
```

## 25 — Training and dataset

```text
You are writing ONE study guide for the ADAS capstone final defense. The audience is the four-person project team, who must defend this system to an academic panel. The repo root is the ADAS project.

Read docs/defense/PLAN.md first — source map, source-of-truth precedence, house rules, and the guide template. Follow the template exactly, all eight sections in order.

Source precedence is critical: the defense paper and the test tracker are authoritative. Where a repo engineering doc frames something differently, follow the paper/tracker, do not comment on the difference, and do not hedge the paper's claim. Repo docs are for mechanism and rationale only.

Write: docs/defense/04-ai/25-ai-training-and-dataset.md

Topic: How the model was trained. Follow the paper's Deep Learning Implementation and Training Protocol section for framing and terminology.

Cover: the architecture and its pretraining; the two-class design and why the second class exists as a discriminative foil that is discarded at inference; dataset composition with per-source counts and splits; the geometry filter that removed images whose accident regions filled too much of the frame, and why that mattered given the framing of real CCTV footage; grayscale as a preprocessing step rather than an augmentation; the hyperparameters; the training hardware; the run history across model versions; and why the adopted checkpoint was selected by event-level evaluation on labelled clips rather than by taking the best validation checkpoint.

Seed questions (a minimum — add your own): "Why not just use the best checkpoint?" / "Where did your accident images come from?" / "Is your training data representative of Lipa City?" / "Why grayscale?" / "How much data is enough?" / "Did you use any synthetic or generated images?"

Questions must be speakable in under 30 seconds. ~300-500 lines. Every number traces to the paper or the tracker; if you cannot source one, write [UNSOURCED — verify]. Cite the paper by chapter/table/figure and code as path/file.py:123. Documentation only — do not modify any code.
```

## 26 — Accuracy and evaluation ⭐

```text
You are writing ONE study guide for the ADAS capstone final defense. The audience is the four-person project team, who must defend this system to an academic panel. The repo root is the ADAS project.

Read docs/defense/PLAN.md first — source map, source-of-truth precedence, house rules, and the guide template. Follow the template exactly, all eight sections in order.

Source precedence is critical: the defense paper and the test tracker are authoritative. Where a repo engineering doc frames something differently, follow the paper/tracker, do not comment on the difference, and do not hedge the paper's claim. Repo docs are for mechanism and rationale only. This rule matters more here than anywhere else in the pack — use the tracker's own framing for the accuracy result and do not import alternative framings from engineering notes.

Write: docs/defense/04-ai/26-ai-accuracy-and-evaluation.md

Topic: HIGH PRIORITY. The accuracy story, told the way the team will have to tell it.

Start from the paper's Objective 3 threshold and the tracker's recorded result for it, using the tracker's own wording: a qualified validation-split result whose limitations are disclosed in the record, and which is explicitly not presented as independent operational detection accuracy. Explain what that qualification means in plain terms so the team can say it confidently rather than sounding evasive.

Then the operational evidence, which is the stronger ground: work through all nine AI model validation cases in the tracker — event-level recall on the labelled clip corpus, standard versus hard difficulty reported separately with their denominators, false alarms per minute over the clean observation window, the negative clip, the night-condition analysis, checkpoint selection, deployed-artifact equivalence, and sensitivity across cadence and source-resolution profiles. Give each its acceptance criterion and its recorded outcome.

Connect back to the comparison table in guide 03 so the team can place their numbers against the literature.

Seed questions (a minimum — add your own): "Did you meet your 85% accuracy target?" — the answer must be crisp and unhesitating / "What does a qualified validation-split result actually mean?" / "Why is hard-case recall what it is?" / "How often does it false-alarm in a shift?" / "Would you trust this at 2am?" / "Why report recall by difficulty instead of one number?" / "How does this compare to the systems in your literature review?"

Questions must be speakable in under 30 seconds. ~300-500 lines. Every number traces to the paper or the tracker; if you cannot source one, write [UNSOURCED — verify]. Cite the paper by chapter/table/figure and code as path/file.py:123. Documentation only — do not modify any code.
```

## 27 — Performance: FPS and latency

```text
You are writing ONE study guide for the ADAS capstone final defense. The audience is the four-person project team, who must defend this system to an academic panel. The repo root is the ADAS project.

Read docs/defense/PLAN.md first — source map, source-of-truth precedence, house rules, and the guide template. Follow the template exactly, all eight sections in order.

Source precedence is critical: the defense paper and the test tracker are authoritative. Where a repo engineering doc frames something differently, follow the paper/tracker, do not comment on the difference, and do not hedge the paper's claim. Repo docs are for mechanism and rationale only.

Write: docs/defense/04-ai/27-ai-performance-fps-latency.md

Topic: Performance and capacity. Cover the accepted frame-rate operating band with its target and its warning floor, and what each end of that band means operationally; per-frame inference latency against its target and the artifact and hardware conditions each measurement was taken under; the batch profile and why fifteen-camera qualification is deferred; alert delivery latency against its budget; and the end-to-end collision-visible-to-operator-decision figure broken into its component allowances.

Follow the test plan's insistence that a capacity diagnostic is supporting evidence and not a production scheduler result, and that each figure carries its stream count, artifact, hardware and duration.

Seed questions (a minimum — add your own): "How many cameras can this really handle?" / "Why is fifteen cameras deferred?" / "What is the bottleneck — the model or the hardware?" / "What happens if you exceed capacity?" / "Why is the frame rate a band rather than a fixed number?" / "How does performance change at night or in rain?"

Questions must be speakable in under 30 seconds. ~300-500 lines. Every number traces to the paper or the tracker; if you cannot source one, write [UNSOURCED — verify]. Cite the paper by chapter/table/figure and code as path/file.py:123. Documentation only — do not modify any code.
```

## 31 — Demo-day runbook

```text
You are writing ONE operational runbook for the ADAS capstone final defense. The audience is the four-person project team, who may need to bring the system up live in front of a panel and recover it if something breaks. The repo root is the ADAS project.

Read docs/defense/PLAN.md first for the source map and house rules. This guide is practical rather than academic, so the standard eight-section template does not apply — use whatever structure serves someone standing at a laptop under pressure. Keep the house rules on sourcing and accuracy.

Write: docs/defense/05-defense-craft/31-demo-day-runbook.md

Topic: How to bring up the three-device LAN demonstration and recover from failure. Base it on docs/operations/VMS_SIMULATOR_SETUP.md and docs/operations/LAN_SETUP.md, condensed into something usable live rather than reproduced in full.

Cover: the pre-session checklist; bring-up order across the three machines; the layer-by-layer validation table where each passing layer narrows the next possible failure; and a troubleshooting section for the known failure modes — no carrier on the wired adapter, wrong subnet, an address that changed after a restart, the RTSP port test failing, cameras stuck reconnecting, the operator unable to reach the dashboard ports, certificate warnings, login succeeding then every request failing, and the dashboard loading but no alerts arriving.

Add a short "if it breaks in front of the panel" section: what to say while recovering, what can be demonstrated without the live stream, and the fastest path back to a working state. Keep commands copy-pasteable and state which machine each one runs on.

Documentation only — do not modify any code or configuration.
```

---

# Wave 2 — run only after Wave 1 has landed

## 28 — Numbers cheat sheet

```text
You are writing ONE study guide for the ADAS capstone final defense. The audience is the four-person project team, who must defend this system to an academic panel. The repo root is the ADAS project.

Read docs/defense/PLAN.md first — source map, source-of-truth precedence, and house rules.

Write: docs/defense/05-defense-craft/28-numbers-cheat-sheet.md

Topic: Every quotable figure in the project, on one page. This is the highest-value file in the pack for a time-constrained reviewer, so prioritise density and scannability over prose.

Your primary inputs are the completed guides in docs/defense/01-paper/, 02-architecture/, 03-behaviour/ and 04-ai/, plus the test tracker and test plan as the authoritative source for any number.

Group the figures: detection and accuracy; performance, latency and capacity; testing and coverage; usability and acceptance; scale and configuration. For each figure give the number, what it means in one line, its source, and any qualification the tracker attaches to it. A number without its qualification is a liability — carry the qualification into the same row.

Where two guides state the same figure differently, resolve it against the tracker and note which guide needs correcting at the end of the file under a short "discrepancies found" heading.

The standard eight-section template does not apply — use tables. Keep it under 300 lines if you can; brevity is the point.

Documentation only — do not modify any code.
```

## 29 — Weak points and limitations

```text
You are writing ONE study guide for the ADAS capstone final defense. The audience is the four-person project team, who must defend this system to an academic panel. The repo root is the ADAS project.

Read docs/defense/PLAN.md first — source map, source-of-truth precedence, house rules, and the guide template.

Write: docs/defense/05-defense-craft/29-weak-points-and-limitations.md

Topic: The honest list of limitations, each paired with a prepared answer. Your primary inputs are the completed guides in docs/defense/, especially their "Limits and honest caveats" sections, plus the qualifications recorded in the tracker.

Cover at least: proof-of-concept and simulation scope rather than a live CDRRMO deployment; a single-host architecture not built for multi-GPU or multi-server operation; hard-difficulty detection recall; night and proximity false positives; the deferred fifteen-camera qualification; the endurance window's duration; and the small participant count in usability and acceptance testing.

Framing discipline matters more than content here. Each entry should be: what the limitation is, why it exists (a scope or resource decision, not an oversight), what the team did to bound its impact, and what the next step would be. Never write it as a confession, and never write it as a denial. A limitation stated confidently with a mitigation and a next step reads as engineering maturity; the same limitation extracted by a panelist reads as a gap.

Section 7 here should be the hostile versions of each question, since that is how these will actually arrive.

Documentation only — do not modify any code.
```

## 30 — Anticipated Q&A

```text
You are writing ONE study guide for the ADAS capstone final defense. The audience is the four-person project team, who must defend this system to an academic panel. The repo root is the ADAS project.

Read docs/defense/PLAN.md first — source map, source-of-truth precedence, and house rules.

Write: docs/defense/05-defense-craft/30-anticipated-qa.md

Topic: A consolidated question bank of 60-80 anticipated panel questions with rehearsable answers. Your primary inputs are the section 7 blocks of every completed guide in docs/defense/, deduplicated, sharpened, and reorganised by theme rather than by guide.

Group by theme: objectives and scope; the literature and justification; the AI model and its accuracy; performance and capacity; system design and architecture; security and access; data, audit and recovery; operations and the operator experience; testing and evidence; and deployment and future work.

Tag each question with the guide that holds the underlying detail, so the team can go deeper when a follow-up lands.

Include the blunt and hostile framings explicitly, because these are the ones that go wrong when unrehearsed: "so it doesn't really work at night?" / "why should CDRRMO trust an AI that misses the hard cases?" / "is this actually deployed, or just a demo?" / "who is accountable when it misses an accident?" / "what did you personally build?" / "what would you do differently?"

Every answer must be speakable in under 30 seconds — 2 to 4 sentences. If an answer needs a qualification, the qualification goes in the spoken answer, not a footnote. The standard template does not apply; structure this as themed question-and-answer sections.

Documentation only — do not modify any code.
```
