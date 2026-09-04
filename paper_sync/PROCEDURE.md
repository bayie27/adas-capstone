# Paper sync — does this change affect the paper?

> **Runtime-neutral.** Claude Code, Codex, and Antigravity all read this file. In Claude Code, `.claude/skills/adas-paper-sync/SKILL.md` wraps it — the procedure itself is here.

The defense document lags the code. Most of what the paper describes as planned or missing is already built, so the usual drift is not "the paper says something false" but **"the paper says we never built it."** That is the expensive kind: it understates the system to a panel.

This procedure answers one question — **the code changed; which paper claims did that break?** It always writes a proposed change, with evidence, to a local finding. A runtime with native Drive write tools may apply the approved change later, but analysis and reporting are always read-only and permission is never inferred.

---

## The three Drive artifacts

Everything live is in Google Drive. **Nothing in this repo is authoritative for paper state.**

| Artifact                                               | Type  | Role                                                                                   |
| ------------------------------------------------------ | ----- | -------------------------------------------------------------------------------------- |
| `Group7_Capstone Project Defense Document - ITCAPROJ1` | Doc   | **The paper.** Read during analysis; write only under the defense-paper approval gate. |
| `ADAS_Paper_Audit`                                     | Doc   | **The full explanation** of each proposed change.                                      |
| `ADAS_Paper_Audit_Tracker`                             | Sheet | **The assignable summary.** One row per change.                                        |

Read all three during the read-only analysis phase. Findings always go to `paper_sync/findings/`. Codex may apply approved updates to the relevant Doc and Sheet in a separate gated phase; Claude remains read-only and leaves the Drive write to a human.

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

Read the paper Doc through the runtime's configured Google Drive connector — Claude Code's native connector or Codex's Google Drive MCP. If neither is available, follow the manual export fallback below.

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

For every textual site that needs a change, produce a separate change block with its own artifact, location, page/s or Sheet range, OLD, NEW, and evidence. Do not defer actionable text to a propagation list or a "see above" reference. For figures and diagrams, produce a `REDRAW REQUIRED` block instead of inventing replacement prose.

### Current finding ownership

The current dated finding is the sole owner of every newly implicated site discovered in the current analysis, even when an older finding discussed the same surface. Repeat the relevant OLD, NEW, and Evidence in the current finding instead of handing the work back to an older Markdown file or making the current finding depend on it. Older findings remain untouched historical records by default; cite them only as provenance, not as the place where the current work lives.

### Change metadata

Every change block must also record a compact execution manifest, which may be generated automatically:

- `Operation`: `replace`, `insert`, `delete`, or `redraw`.
- `Scope`: `span`, `logical paragraph`, `cell`, `row`, or `figure`.
- `Changed target`: the exact text span, cell(s), row, or figure being changed.
- `Preserve`: nearby text, cells, validation, formatting, or manual fields that must not change.
- `Comment target`: the exact native range, or the exact changed Sheet text colored orange (`#E67E22`).

This metadata is an execution contract, not extra replacement prose. It lets the workflow validate that a comment does not cover preserved content and that a proposed operation matches the actual write.

### Comment scope

Choose the comment scope per textual site before writing and record it in the finding:

- **Span scope** — use this when the change is genuinely one small, contiguous word or phrase. The comment's `Previous:` line contains only the exact old span, and the native comment range highlights only the exact new span.
- **Logical-paragraph scope** — use this when most of the paragraph changes, when the required changes are scattered across multiple non-contiguous spans, or when one paragraph contains three or more distinct changes. Create one comment for the whole logical paragraph rather than flooding it with phrase comments. For this scope, the comment may use `Previous (marked, intentionally non-verbatim):` and wrap each changed old fragment in `[[...]]` so the changes are easy to see. The finding's OLD section must still contain the exact verbatim paragraph.

Do not use a paragraph-sized comment for a small, contiguous replacement. Do not use many span comments when a paragraph-level rewrite is the clearer audit trail. The required `Codex ID:` and final `Done by Codex.` lines remain in both comment shapes.

Each finding block must record `Comment scope:` immediately before its proposed comment. For span scope, include the exact changed OLD and NEW spans; for logical-paragraph scope, identify the single logical paragraph being highlighted.

For an insertion-only block, use `Previous: N/A` and highlight only the inserted NEW text. For a deletion-only block, make NEW explicitly say `DELETE ONLY — insert nothing.`, put the exact deleted text in `Previous:`, and anchor the native comment to the nearest surviving left character. Do not comment on preserved text merely because it is adjacent to the deletion.

For a new tracker row, resolve the target deterministically rather than assuming a convenient row. Read a bounded range with `userEnteredValue` immediately before proposing and again immediately before writing. Treat a row as occupied when any cell has a `userEnteredValue`; formatting, validation, banding, or a blank-looking rendered value does not make it occupied or available. Use the response's `startRow`/`startColumn` metadata when mapping returned arrays to A1 rows—blank trailing rows may be omitted. If the candidate is occupied, scan downward to the first fully blank row, preserve every occupied row, and update the finding's Sheet range, OLD, Evidence, proposed comment, tracker summary, and approval report to the actual range before writing. Write only the intended cells, normally A:G, and preserve manual cells such as `Reviewed by`, formatting, validation, and notes.

### Approval and sync manifest

Before any Drive write, translate the user's approval into an explicit manifest of exact block numbers and standalone comments. Do not infer that an omitted block is approved. Record the manifest in the finding and report it before writing. For partial approval, distinguish these states:

- **Approved** — the user authorized the exact block or standalone comment.
- **Applied/read back** — the authorized write and its verification succeeded.
- **Skipped/pending** — the user did not authorize it or explicitly excluded it; it remains pending.
- **Blocked** — the user authorized it, but a required capability or verification failed.

Use an `Approval / sync ledger` section in the finding so a later run can resume from exact block numbers without rereading the conversation. Keep `synced: false` while any block is skipped, pending, or blocked; set it to the date only when the finding has no outstanding scope and every approved write has passed read-back verification.

For every finding/package, assign one stable searchable package ID derived from its filename: use the finding date and normalized slug, for example `PS-20260820-CAMERA-RESTORE-UC4`. Every Codex-created comment in that package—including replacement comments and standalone figure comments—must use the same package ID. Keep it unchanged on retries and record it in every proposed comment.

For every textual NEW that Codex will apply, also draft the comment that will be attached to that new information after the replacement is verified. Use the recorded comment scope: a span comment preserves only the replaced old span; a logical-paragraph comment preserves the full previous paragraph. Both comment bodies include the package ID and end with the attribution line:

```text
Previous: <the exact OLD text or old cell value; use N/A for insertion-only>

Codex ID: PS-YYYYMMDD-FINDING-SLUG

Done by Codex.
```

For a logical-paragraph comment with three or more distinct changes, replace the `Previous:` label with `Previous (marked, intentionally non-verbatim):` and wrap each changed old fragment in `[[...]]`. The block's OLD section remains the exact audit quote.

For a standalone review comment, put the review text first, then the `Codex ID:` line, and keep `Done by Codex.` as the exact final line. This comment is an audit trail, not part of NEW. Do not add it to unchanged sites, preserved tracker cells, or redraw-only items unless a separate comment is useful.

The comment uses the same approval gate as its replacement: a defense-paper replacement and its `Previous` comment are approved together under **Defense paper**; an audit-Doc replacement and its comment are approved under **Audit + tracker**; a tracker Sheet replacement uses the exact orange text fallback in that same gate. Only a standalone review comment uses the separate Comments gate.

For Sheets, do not create comments. Color only the exact new or changed word/phrase text orange (`#E67E22`) using rich-text `textFormatRuns`; preserve unchanged characters and all other cell formatting. Never color the whole cell unless the entire cell value is new or changed.
Comment target: exact NEW span, or exact changed Sheet text colored orange (`#E67E22`)
Before creating comments, search the file's existing comments for the package ID. Multiple comments with the same package ID are expected; for each planned comment, match its recorded scope, exact content, quote, and anchor and do not duplicate an exact match. If the package ID is attached to an unrelated finding or the expected scope/anchor/quote conflicts, stop and report it. Existing comments created before this convention are historical and are not rewritten solely to add IDs without explicit approval.

## Step 6 — write the finding

Every finding stays in `paper_sync/findings/<YYYY-MM-DD>-<slug>.md` and contains one explicit block per changeable site. `NEW` is paste-ready and contains no reasoning, file path, audit reference, or implementation detail.

```markdown
---
section: Frameworks and Libraries
page/s: "<exact rendered page(s)>"
required_revision: One-line summary of the change
notes: Any qualifier a reader needs
status: Not started
assigned_to: Daniboy
synced: false
---

## Changes

### 1. Defense paper — Table 7, NFR-21

Page/s: 66

#### Change metadata

Operation: replace
Scope: span
Changed target: exact OLD span
Preserve: surrounding text and formatting
Comment target: exact NEW span, or exact changed Sheet text colored orange (`#E67E22`)

#### OLD

> verbatim quote from the live Doc

#### NEW

paste-ready replacement, kept close to OLD in length and shape

#### Evidence

file:line or measured evidence

#### Proposed comment (same gate as associated replacement)

Previous: verbatim OLD text

Codex ID: PS-YYYYMMDD-FINDING-SLUG

Done by Codex.

### 2. Defense paper — Table 14, Audit Log, `detail`

Page/s: 137

#### OLD

> verbatim quote from the live Doc

#### NEW

paste-ready replacement

#### Evidence

file:line or measured evidence

### 3. ADAS_Paper_Audit — §2.6

Page/s: p. NN (exact rendered page required)

#### OLD

> verbatim quote from the live audit Doc

#### NEW

paste-ready replacement

#### Evidence

file:line or measured evidence

### 4. Tracker Sheet — `🚩 Action Stream`!A65:H65

#### OLD

> existing row values, or `No existing row` when the change is new

#### NEW

the exact row values to update or append

#### Evidence

live Sheet readback location

## Redraw required

### Figure 11

Page/s: 112

#### Current issue

What the live figure or caption currently shows.

#### Required redraw

The exact visual change required.

#### Proposed comment

Comment text to attach only if a valid native highlight anchor is available.
```

### Replacement-text rules

- Keep NEW close to OLD in sentence count, grammar, table-row shape, and approximate length.
- Add only the minimum wording needed to make the paper accurate.
- Put implementation detail, key lists, counts, file paths, and reasoning in Evidence, never in NEW.
- Repeat OLD/NEW for every site; never replace those blocks with a site list or cross-reference.
- For every textual NEW, include either a proposed comment body using the site's recorded scope or, for Sheet content, a documented orange text-format fallback covering the exact changed text. Comment bodies use exact changed OLD/NEW spans for span scope or the full OLD/NEW logical paragraph for paragraph scope; every body starts with `Previous:`, includes the finding's package-level `Codex ID:` line, and ends with `Done by Codex.` on its own final line. Standalone comments also include the same package ID.
- The proposed comment or formatting fallback is not part of NEW and is applied only after the associated replacement has been read back successfully and its same approval gate has been granted.
- Use `REDRAW REQUIRED` for non-text artifacts.

### Standing evidence rules

- **Cite, never recall.** Open the file. The paper claimed `bcrypt` and `gputil` for months — neither has ever been in this repo — because nobody opened `pyproject.toml`.
- **Never invent a number to fill a gap.** If the evidence does not exist, say so and name the run that would produce it. A previous audit pass substituted the _previous_ model's true-positive confidences for the adopted model's false-positive peaks and published a figure that described neither model. That is the failure this rule exists to prevent.
- **Anchor on heading plus verbatim quote, then verify page/s.** Page numbers have drifted twice already. Record the rendered page you observed and the date you observed it; treat any inherited page number as a hint until the live PDF is checked.
- **Report the paper-visible table label.** A connector's raw table number can be offset by title tables or other structural elements; reconcile it with the visible caption and rendered PDF before naming the site.

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

## Changes

### 1. Artifact — heading or cell/range

Page/s: p. NN, or `Sheet tab!A1:H1` for a tracker change

#### OLD

> verbatim quote or existing row values

#### NEW

replacement text or exact row values, paste-ready, nothing else

#### Evidence

file:line or measured evidence

#### Proposed comment (same gate as associated replacement)

Previous: exact OLD text or old cell value

Codex ID: PS-YYYYMMDD-FINDING-SLUG

Done by Codex.

### 2. Another textual site

Page/s: p. NN

#### OLD

> verbatim quote

#### NEW

replacement text, paste-ready, nothing else

#### Evidence

file:line or measured evidence

## Redraw required

Use this section for figures and diagrams. Give each item its own page/s, current issue, required redraw, and optional proposed comment.
```

**Front-matter values are cells, not prose.** Each one is pasted into a spreadsheet cell, so keep it short — a summary, not an explanation. Anything that needs reasoning goes in the body. This is the same rule as NEW, one field over.

**Page/s are rendered-document evidence.** Native Docs indexes are not page numbers. Export the live native Doc internally as PDF, match the exact OLD text against the rendered PDF, and record every matching page or page range before approval. Exact page mapping is a hard requirement because those pages must flow into the paper-audit tracker; an unresolved mapping blocks approval and the tracker write. For the tracker Sheet, record the tab name and A1 cell/range instead of a page.

The front matter is the tracker row. Its keys are the Sheet's columns, in order:

`Section / Chapter` · `Page Number` · `Required Revision` · `Notes` · `Status` · `Assigned to`

Status in use: `Not started`. Assignees in use: `Daniboy`, `Enjey`, `Meerio`, `Paulo`.

`synced: false` means the finding has not completed its approved Drive write/readback cycle or still has skipped, pending, or blocked scope. If the user declines a gate, a write fails, or readback does not match, leave it false and report the partial state. Set it to the current date only after every finding block is either successfully applied and verified or explicitly closed as out of scope, with no blocked item remaining.

Partial approval is valid: apply only the approved block numbers, maintain the `Approval / sync ledger` with exact approved, applied/read-back, skipped/pending, and blocked items, and keep `synced: false` until no finding scope remains pending or blocked and all approved writes are verified.

### Approval / sync ledger template

Add this section to findings that may be applied in subsets:

```markdown
## Approval / sync ledger

Package ID: `PS-YYYYMMDD-FINDING-SLUG`

| Target                        | Approved scope | Applied/read back | Skipped/pending | Blocked |
| ----------------------------- | -------------- | ----------------- | --------------- | ------- |
| Defense paper                 | blocks …       | blocks …          | blocks …        | —       |
| ADAS_Paper_Audit plus tracker | blocks …       | blocks …          | blocks …        | …       |
| Standalone comments           | comments …     | comments …        | comments …      | …       |
```

**One current finding per analysis, never one shared file for one analysis.** The current dated file owns all newly implicated sites, including sites previously discussed elsewhere. Older finding files remain untouched historical records by default; do not split current work across the current file and an older file.

Then regenerate the summary — it is generated, never hand-edited:

```bash
uv run python paper_sync/build_tracker.py
```

---

## Step 7 — report and request permission

After writing the local finding and regenerating `paper_sync/TRACKER.md`, report every change block with its OLD, NEW, Evidence, page/s or Sheet range, and intended Drive target. Do not call any Drive write tool before approval.

Before the three gates, include the exact approval manifest: list the approved block numbers and standalone comment IDs, and list every omitted block as skipped/pending. Natural-language approval such as “only 1–4” must exclude block 5 and any other unlisted target. Use the same manifest in the finding's `Approval / sync ledger` and update it after each verified write.

Include the finding/package's stable `Codex ID:` in the report so the user can search the Docs comment list once and reconcile all of its live threads.

End with three separate approval gates:

1. **Defense paper** — permission for only the listed defense-paper replacements.
2. **ADAS_Paper_Audit plus tracker Sheet** — one combined permission for the listed audit-Doc and Sheet updates.
3. **Standalone comments** — a separate permission only for comments that are not attached to a replacement, such as a figure/redraw review comment.

The Defense paper gate includes each paper replacement's `Previous` comment. The combined Audit + tracker gate includes each audit-Doc replacement's `Previous` comment or tracker replacement's exact text-format fallback. For native Google Docs, use the Docs `insertComment` request through `google_drive_batch_update_document`, with the exact NEW range, only after its associated replacement has been read back. Do not synthesize Drive `kix.*` anchors or use the Drive comments bulk endpoint for Doc highlighting. If a native highlight cannot be created and verified, leave the proposed comment in the report and do not create an unanchored comment.

## Step 8 — apply approved writes and verify

For each approved gate:

- Re-read the target and obtain a fresh revision ID immediately before writing.
- Apply exact Doc replacements with `google_drive_batch_update_document` and a required revision guard.
- For a Docs insertion after an existing paragraph, resolve the anchor paragraph and the next paragraph from the live Doc immediately before writing. Use their returned `startIndex`, `endIndex`, and `tabId` to determine the paragraph boundary; when the matched text ends before its terminator and the next paragraph begins at `endIndex + 1`, insert `\n<NEW>` at the current paragraph's `endIndex`. Otherwise use the boundary shown by the live ranges. Re-find the exact NEW text before creating its comment. For multiple direct range edits in one batch, apply them from highest index to lowest; never reuse indexes after an earlier mutation has shifted them.
- Update only the intended tracker row/cells with `google_drive_batch_update_spreadsheet`; read the full resolved target row immediately before writing and preserve unrelated values, formatting, validation, blank owner/status cells, and other manual columns. For an append, verify the target is fully blank by `userEnteredValue`; if not, resolve the next fully blank row, update the finding/ledger/report, and only then write.
- After each approved Doc replacement succeeds, find the exact NEW text again, obtain a fresh revision, and create its approved comment with a raw Docs `insertComment` request containing `content` and `range` (`startIndex`, `endIndex`, `tabId`). Apply the recorded scope: highlight only the new changed span for span scope, or one full new logical paragraph for paragraph scope. Do not combine the replacement and comment into one batch because the replacement changes the range being anchored. Before inserting, check comments with the package ID and match the expected scope, content, and quote/anchor to avoid duplicates.
- If an incorrect, duplicate, or provisional comment was created, delete it with the provider's comment-deletion operation and verify deletion. Do not resolve it as a substitute; if deletion is unavailable, stop and report the limitation.
- Read back the changed Doc paragraphs, Sheet cells, comment state, and any Sheet text-format fallback. For a native Doc comment, verify the returned `commentThread`, non-empty anchor, exact `plainTextQuote`/quoted text (HTML-decode entities before comparison), the expected `Codex ID:`, and that the content ends with `Done by Codex.`.
- Update the local finding's approval/sync ledger after each verified artifact. Update `synced` only when no block remains skipped, pending, or blocked and every approved write has passed read-back.

After all approved writes and read-backs, run a fresh read-only sweep of the live artifacts for claim-bearing drift. If the sweep finds a new textual site that was not in the approved manifest, stop completion, record the site with its OLD/NEW text and evidence in the finding, leave it pending, and request approval before writing it. Do not silently expand the manifest or mark the finding synced. Generic technical or ordinary-language matches may be classified as out of scope only with an explicit justification.

If a revision guard fails, a resolved tracker row changes, or readback differs, stop that artifact's writes and report the conflict without retrying blindly. Rebuild the approval/sync ledger from the fresh read before resuming.

**An aside still gets a finding file.** If you notice something real while looking at something else — a duplicated table number, a figure that contradicts its caption — file it. Scope limits where you look, not what you are allowed to report. Give it its own change or redraw block and say in the report that it came up incidentally.

**If nothing drifted, say that plainly.** A clean result is a real result. A procedure that always finds something is one nobody trusts.
