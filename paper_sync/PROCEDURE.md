# Paper sync — does this change affect the paper?

> **Runtime-neutral.** Claude Code, Codex, and Antigravity all read this file. In Claude Code, `.claude/skills/adas-paper-sync/SKILL.md` wraps it — the procedure itself is here.

The defense document lags the code. Most of what the paper describes as planned or missing is already built, so the usual drift is not "the paper says something false" but **"the paper says we never built it."** That is the expensive kind: it understates the system to a panel.

This procedure answers one question — **the code changed; which paper claims did that break?** It does not edit the paper. It writes a proposed change, with evidence, to a file that a human applies.

---

## The three Drive artifacts

Everything live is in Google Drive. **Nothing in this repo is authoritative for paper state.**

| Artifact                                               | Type  | Role                                              |
| ------------------------------------------------------ | ----- | ------------------------------------------------- |
| `Group7_Capstone Project Defense Document - ITCAPROJ1` | Doc   | **The paper.** Read only, always.                 |
| `ADAS_Paper_Audit`                                     | Doc   | **The full explanation** of each proposed change. |
| `ADAS_Paper_Audit_Tracker`                             | Sheet | **The assignable summary.** One row per change.   |

Read all three. **Write to none of them.** Findings go to `paper_sync/findings/`; a human moves them up to the Doc and the Sheet, the same way a human applies the edit to the paper.

`paper-audit.md` and `ADAS_Paper_Revisions_Tracker.pdf` in this repo are **superseded snapshots**. Useful history, never current state. Do not read them to decide what the paper says today.

---

## Step 1 — take the input

Four modes, one pipeline.

| Mode                 | Input                                                                 |
| -------------------- | --------------------------------------------------------------------- |
| **Branch** (default) | `git diff main...HEAD` and `git log main..HEAD --oneline`             |
| **PR**               | `gh pr diff <n>` and `gh pr view <n> --json title,body,files`         |
| **Sweep**            | `git log --oneline <since>..HEAD` and `git diff <since>..HEAD --stat` |
| **Described**        | Prose from the user, for work not in a diff yet                       |

---

## Step 2 — reduce the change to claim-bearing surfaces

Most diffs do not touch the paper. Say so and stop rather than manufacturing a finding.

**Claim-bearing:** new or changed routes · model columns and constraints · constants the paper quotes by value · dependencies in `pyproject.toml` · new services, scripts, or subsystems · AI-engine pipeline behaviour · anything that changes the deployment story.

**Usually not:** pure refactors · formatting · test-only changes · comment and docstring edits · frontend styling that changes no described behaviour.

For each claim-bearing surface, find its ground truth using [`CLAIM_SOURCES.md`](CLAIM_SOURCES.md).

---

## Step 3 — check what is already known

Before reading the paper, read what has already been decided:

1. `ADAS_Paper_Audit` — already an entry, or a recorded verified-correct note?
2. `ADAS_Paper_Audit_Tracker` — already a row?
3. `paper_sync/findings/` — already written locally, waiting to be moved up?

`ADAS_Paper_Audit` holds proposed text that has not reached the paper yet, so it is worth checking rather than trusting: a wrong number there becomes a wrong number in the paper the moment someone applies it.

Re-raising something already cleared is the fastest way to lose the panel's trust, and all three exist partly to prevent it.

**Before stopping on "already known", confirm the finding is still pending.** A queued finding says `synced: false` because nobody has updated the file, not because nobody has applied the edit — the two come apart the moment a human edits the Doc and forgets. So check the live Doc for that finding's OLD text:

- **OLD still there** — genuinely pending. Say so, name the file, and stop.
- **OLD gone** — the edit already landed. Say that instead, and tell the user to set `synced` to today's date so the finding stops being re-reported forever.

This is the one check that keeps the queue from silently accumulating work that was finished weeks ago.

---

## Step 4 — read the paper and classify

Read the paper Doc through whatever read access the runtime has. In Claude Code that is the native Google Drive connector.

**No Drive access? Stop.** Do not guess, and do not reconstruct the paper from anything in this repo — a finding built on a stale copy is worse than no finding, because it arrives with the same confidence as a real one. Tell the user to either connect a Drive integration, or export the Doc themselves and re-run. Say which of the two you need.

For the manual route, name the path so everyone uses the same one: **File → Download → Plain Text** from the Doc, saved as `paper_sync/.local/paper.txt`. That directory is gitignored — a copy of the paper must never be committed. Treat it as good only for the session that produced it: it is a snapshot, and the whole reason this procedure distrusts snapshots is that the Doc moves.

Classify into one of four drift classes:

1. **Paper now wrong** — code changed under a claim the paper makes.
2. **Paper says unimplemented, now built** — the common case here, and the most expensive at a defense. You are understating your own system.
3. **Paper never described it** — a subsystem exists and the paper is silent. Seven are already known: durable outbox, audit-log subsystem, async export jobs, login rate limiting, backup/restore, health routers, FTS5 help search.
4. **Figure / diagram / data-dictionary drift** — needs a redraw, not a reworded sentence: ERD (Figure 7), Level-1 DFD, Tables 9–13. Say explicitly that it is a redraw; it lands on a different person than prose edits do.

---

## Step 5 — find every site

One correction usually has several homes. Past entries have run to four and ten sites. **Applying only the first leaves the rest contradicting it**, which reads worse than not fixing it at all.

Before writing anything, sweep: Definition of Terms · the FR/NFR tables · the data dictionary (Tables 9–13) · use-case steps · figure narratives · the chapter prose.

Produce a propagation list naming every site.

---

## Step 6 — write the finding

Every finding has exactly three parts:

```text
OLD             Verbatim quote of what the paper says today.
NEW             The exact replacement text. Paste-ready. Nothing else.
JUSTIFICATION   Why — a file:line, or a measured number and the file that recorded it.
```

> **The justification is never part of NEW.** NEW gets pasted into the paper as-is, so it must read as paper prose: no reasoning, no `file:line`, no reference to this audit, no "changed because". This is the easiest rule here to violate and the only one that silently corrupts the paper.

### Standing evidence rules

- **Cite, never recall.** Open the file. The paper claimed `bcrypt` and `gputil` for months — neither has ever been in this repo — because nobody opened `pyproject.toml`.
- **Never invent a number to fill a gap.** If the evidence does not exist, say so and name the run that would produce it. A previous audit pass substituted the _previous_ model's true-positive confidences for the adopted model's false-positive peaks and published a figure that described neither model. That is the failure this rule exists to prevent.
- **Anchor on heading plus verbatim quote, never page number.** Page numbers have drifted twice already. Record the page you observed and the date you observed it; treat any inherited page number as a hint.

### Where it goes

Write each finding to `paper_sync/findings/<YYYY-MM-DD>-<slug>.md`:

```markdown
---
section: Frameworks and Libraries
page/s: "137"
required_revision: One-line summary of the change
notes: Any qualifier a reader needs
status: Not started
assigned_to: Daniboy
synced: false
---

## Where

Doc heading, observed p. NN on YYYY-MM-DD.

## OLD

> verbatim quote

## NEW

replacement text, paste-ready, nothing else

## Justification

file:line or measured evidence

## Propagation

- every other site saying the same thing
```

**Front-matter values are cells, not prose.** Each one is pasted into a spreadsheet cell, so keep it short — a summary, not an explanation. Anything that needs reasoning goes in the body. This is the same rule as NEW, one field over.

**`page/s` is best-effort.** The Doc's plain-text export carries no page breaks, so the read path this procedure prescribes usually cannot produce a page number. That is fine: Step 6's evidence rules already say to anchor on heading plus verbatim quote, because page numbers have drifted twice. Write the pages when you genuinely have them (a PDF export of the Doc will give them, if a finding is worth that round trip), and otherwise write exactly `unconfirmed` — one token, so the column stays sortable and every finding says it the same way.

The front matter is the tracker row. Its keys are the Sheet's columns, in order:

`Section / Chapter` · `Page Number` · `Required Revision` · `Notes` · `Status` · `Assigned to`

Status in use: `Not started`. Assignees in use: `Daniboy`, `Enjey`, `Meerio`, `Paulo`.

`synced: false` means nobody has copied it into Drive yet. Whoever does sets it to that date.

**One file per finding, never one shared file.** Four people work on separate branches; everyone appending to a single file conflicts on every merge, separate files never do.

Then regenerate the summary — it is generated, never hand-edited:

```bash
uv run python paper_sync/build_tracker.py
```

---

## Step 7 — report

Give the user OLD / NEW / JUSTIFICATION per finding, the propagation list, and the paths of the files you wrote.

**An aside still gets a finding file.** If you notice something real while looking at something else — a duplicated table number, a figure that contradicts its caption — file it. Scope limits where you look, not what you are allowed to report. Say in the report that it came up incidentally.

**If nothing drifted, say that plainly.** A clean result is a real result. A procedure that always finds something is one nobody trusts.
