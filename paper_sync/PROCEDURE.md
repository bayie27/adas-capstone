# Paper sync — does this change affect the paper?

> **Runtime-neutral.** Claude Code, Codex, and Antigravity all read this file. In Claude Code, `.claude/skills/adas-paper-sync/SKILL.md` wraps it — the procedure itself is here.

The defense document lags the code. Most of what the paper describes as planned or missing is already built, so the usual drift is not "the paper says something false" but **"the paper says we never built it."** That is the expensive kind: it understates the system to a panel.

This procedure answers one question — **the code changed; which paper claims did that break?** When verified drift exists, it writes a proposed change with evidence to a local finding; otherwise report no drift within the examined scope without creating an empty finding. Analysis is read-only with respect to Drive. Local evidence collection, finding creation, and tracker regeneration proceed without additional confirmation within the requested scope. Drive writes require explicit approval under the gates below.

---

## The two Drive artifacts

Everything live is in Google Drive. **Nothing in this repo is authoritative for paper state.**

| Artifact                                               | Type  | Role                                                                                   |
| ------------------------------------------------------ | ----- | -------------------------------------------------------------------------------------- |
| `Group7_Capstone Project Defense Document - ITCAPROJ1` | Doc   | **The paper.** Read during analysis; write only under the defense-paper approval gate. |
| `ADAS_Paper_Audit_Tracker`                             | Sheet | **The assignable summary.** One row per change.                                        |

First perform the local claim-bearing triage in Step 2. If no relevant surface changed, report that result without fetching Drive artifacts. Otherwise read both during analysis. Findings always go to `paper_sync/findings/`. Codex may apply approved updates to the relevant Doc and Sheet in a separate gated phase; Claude remains read-only and leaves the Drive write to a human.

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

1. `ADAS_Paper_Audit_Tracker` — already a row?
2. `paper_sync/findings/` — already written locally, waiting to be moved up?

Re-raising something already cleared is the fastest way to lose the panel's trust, and these records help prevent it.

**Deduplicate each site individually, then continue reviewing the remaining input.** Check the live site and the existing finding's ledger:

- **OLD still there** — report the existing pending block without duplicating it. Resume it when application is already authorized.
- **OLD absent** — verify the intended replacement or deletion at the correct site and every outstanding ledger obligation, including comments and tracker changes, before describing the finding as fully synced. Absence of OLD alone proves neither application nor completion.

Report verified historical status corrections for the user to apply; do not automatically rewrite older findings. Newly implicated sites belong to the current finding under Step 5. Resuming an approved package is not a new analysis: retain its package ID and block numbers and maintain its execution ledger under Step 8.

---

## Step 4 — read the paper and classify

Read the paper Doc through the runtime's configured Google Drive connector — Claude Code's native connector or Codex's Google Drive MCP. If neither is available, follow the manual export fallback below.

**If an artifact is inaccessible, stop only conclusions and operations requiring its current state.** Test the configured connector before reporting access failure. Complete independent code inspection, evidence collection, and local draft preparation, and report the exact limitation. Do not guess or reconstruct current paper state from repo snapshots. Request the missing connection or export only when needed for the remaining work; resume when it becomes available.

For the manual route, name the path so everyone uses the same one: **File → Download → Plain Text** from the Doc, saved as `paper_sync/.local/paper.txt`. That directory is gitignored — a copy of the paper must never be committed. Treat it as session-scoped draft evidence only. A TXT export cannot establish rendered pages or the state of the other artifacts. Missing artifact verification and PDF mapping remain explicit blockers to approval-ready output and affected Drive writes; label draft gaps rather than inventing evidence.

Classify into one of four drift classes:

1. **Paper now wrong** — code changed under a claim the paper makes.
2. **Paper says unimplemented, now built** — the common case here, and the most expensive at a defense. You are understating your own system.
3. **Paper never described it** — a subsystem exists and the paper is silent. Seven are already known: durable outbox, audit-log subsystem, async export jobs, login rate limiting, backup/restore, health routers, FTS5 help search.
4. **Figure / diagram / data-dictionary drift** — needs a redraw, not a reworded sentence: ERD (Figure 7), Level-1 DFD, Tables 9–13. Say explicitly that it is a redraw; it lands on a different person than prose edits do.

---

## Step 5 — find every site

One correction usually has several homes. Past entries have run to four and ten sites. **Applying only the first leaves the rest contradicting it**, which reads worse than not fixing it at all.

Before finalizing a proposal for approval, sweep the claim's propagation sites: Definition of Terms · the FR/NFR tables · the data dictionary (Tables 9–13) · use-case steps · figure narratives · the chapter prose. Local drafts may be saved while this sweep is in progress; record incomplete coverage explicitly.

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

Each Doc block with a proposed comment must record `Comment scope:` immediately before it. For span scope, include the exact changed OLD and NEW spans; for logical-paragraph scope, identify the single logical paragraph being highlighted. A standalone figure comment highlights exactly the figure-caption range. Sheet blocks record the formatting fallback instead of a comment.

For an insertion-only block, use `Previous: N/A` and highlight only the inserted NEW text. For a deletion-only block, make NEW explicitly say `DELETE ONLY — insert nothing.`, put the exact deleted text in `Previous:`, and anchor the native comment to the nearest surviving left character. Anchoring a deletion comment to that single surviving character is the explicit exception to avoiding preserved-text anchors; do not highlight additional preserved text. If no surviving left character exists, leave the comment blocked pending a reviewed anchor choice.

For a new tracker row, the proposed manifest must specify the semantic append target as "the first fully blank row in this named tab" and record the current A1 range. If approval specifies only a fixed row, relocation requires revised approval. Resolve the target deterministically rather than assuming a convenient row. Read a bounded range with `userEnteredValue` immediately before proposing and again immediately before writing. Treat a row as occupied when any cell has a `userEnteredValue`; formatting, validation, banding, or a blank-looking rendered value does not make it occupied or available. Use the response's `startRow`/`startColumn` metadata when mapping returned arrays to A1 rows—blank trailing rows may be omitted. If the candidate is occupied, scan downward to the first fully blank row, preserve every occupied row, and update the finding's Sheet range, OLD, Evidence, formatting fallback, tracker summary, and approval report to the actual range before writing. Write only the intended cells, normally A:G, and preserve manual cells such as `Reviewed by`, formatting, validation, and notes.

### Approval and sync manifest

Before any Drive write, translate the user's approval into an explicit manifest of exact block numbers and standalone comments. Do not infer that an omitted block is approved. Record the manifest in the finding and report it before writing. Existing explicit approval remains valid for unchanged blocks and bundled comments across retries and resumptions; it does not authorize new or materially changed scope. Preserve the approval source in the ledger so a later run can verify it. If the source is unavailable or ambiguous, clarify only the affected scope. For partial approval, distinguish these states:

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

The comment uses the same approval gate as its replacement: a defense-paper replacement and its `Previous` comment are approved together under **Defense paper**; a tracker Sheet replacement and its exact orange text fallback are approved together under **Tracker Sheet**. Only a standalone review comment uses the separate Comments gate.

For Sheets, do not create comments. Color only the exact new or changed word/phrase text orange (`#E67E22`) using rich-text `textFormatRuns`; preserve unchanged characters and all other cell formatting. Never color the whole cell unless the entire cell value is new or changed.

Before creating comments, search the file's existing comments for the package ID. Multiple comments with the same package ID are expected; for each planned comment, match its recorded scope, exact content, quote, and anchor and do not duplicate an exact match. If the package ID is attached to an unrelated finding or the expected scope/anchor/quote conflicts, stop the affected comment operation and report it. Continue independent approved work only where its prerequisites remain satisfied. Existing comments created before this convention are historical and are not rewritten solely to add IDs without explicit approval.

## Step 6 — write the finding

Every finding stays in `paper_sync/findings/<YYYY-MM-DD>-<slug>.md` and contains one explicit block per changeable site. `NEW` is paste-ready and contains no reasoning, file path, audit reference, or implementation detail.

Use this template once per finding. Repeat the complete textual block for each Doc site; use the Sheet and redraw variants only when applicable. Replace illustrative values with verified evidence.

```markdown
---
section: Frameworks and Libraries
page/s: "<exact rendered pages; pending PDF mapping in drafts only>"
required_revision: One-line summary
notes: Short qualifier
status: Not started
assigned_to: Daniboy
synced: false
---

## Changes

### 1. Defense paper — visible heading/table label

Page/s: <rendered pages and observation date>

#### Change metadata

Operation: replace
Scope: span
Changed target: <exact OLD span within its identified site>
Preserve: <surrounding text and formatting>
Comment target: <exact NEW span; resolve native indexes before writing>

#### OLD

> <verbatim live text>

#### NEW

<paste-ready replacement>

#### Evidence

<file:line or measured evidence; live artifact identity and location>

#### Proposed comment (same gate as replacement)

Comment scope: span; OLD <exact changed span>; NEW <exact changed span>

Previous: <exact changed OLD span>

Codex ID: PS-YYYYMMDD-FINDING-SLUG

Done by Codex.

### 2. Tracker Sheet — <tab and current A1 range>

#### Change metadata

Operation: insert
Scope: row
Changed target: <first fully blank row in named tab; current A1 range>
Preserve: <manual columns, occupied rows, formatting, validation, notes>
Comment target: <exact new text colored orange; no Sheet comment>

#### OLD

> <verified empty row, or exact existing values for an update>

#### NEW

<exact values keyed by intended cell/column>

#### Evidence

<live userEnteredValue read, startRow/startColumn mapping, observation time>

#### Formatting fallback (same gate as replacement)

<exact changed text runs colored #E67E22; preserve other formatting>

## Redraw required

### 3. Defense paper — <figure and caption>

Page/s: <rendered pages and observation date>

#### Change metadata

Operation: redraw
Scope: figure
Changed target: <identified figure>
Preserve: <unaffected figure content and surrounding text>
Comment target: <exact figure-caption range, if a standalone comment is proposed>

#### Current issue

<what the live figure shows, with evidence>

#### Required redraw

<exact visual change; no invented replacement prose>

#### Proposed standalone comment (separate gate; omit if unnecessary)

Comment scope: figure caption; <exact caption text>

<review text>

Codex ID: PS-YYYYMMDD-FINDING-SLUG

Done by Codex.

## Approval / sync ledger

Package ID: PS-YYYYMMDD-FINDING-SLUG
Approval source: <user approval reference, or not yet approved>

| Target              | Approved scope | Applied/read back | Skipped/pending        | Blocked |
| ------------------- | -------------- | ----------------- | ---------------------- | ------- |
| Defense paper       | —              | —                 | blocks 1 and 3         | —       |
| Tracker Sheet       | —              | —                 | block 2                | —       |
| Standalone comments | —              | —                 | comment 3, if proposed | —       |
```

For paragraph, insertion, and deletion variants, retain every field and use the operation and comment-scope rules in Step 5. Record redraw execution separately from its optional comment; a verified comment does not mean the figure has been redrawn.

### Replacement-text rules

- Keep NEW close to OLD in sentence count, grammar, table-row shape, and approximate length.
- Add only the minimum wording needed to make the paper accurate.
- Put implementation detail, key lists, counts, file paths, and reasoning in Evidence, never in NEW.
- Repeat OLD/NEW for every site; never replace those blocks with a site list or cross-reference.
- For every textual NEW, include either a proposed comment body using the site's recorded scope or, for Sheet content, a documented orange text-format fallback covering the exact changed text. Comment bodies use exact changed OLD/NEW spans for span scope or the full OLD/NEW logical paragraph for paragraph scope; replacement bodies start with the applicable `Previous:` or `Previous (marked, intentionally non-verbatim):` label, while standalone bodies start with review text. Every comment includes the finding's package-level `Codex ID:` line, and ends with `Done by Codex.` on its own final line. Standalone comments also include the same package ID.
- The proposed comment or formatting fallback is not part of NEW and is applied only after the associated replacement has been read back successfully and its same approval gate has been granted.
- Use `REDRAW REQUIRED` for non-text artifacts.

### Standing evidence rules

- **Cite, never recall.** Open the file. The paper claimed `bcrypt` and `gputil` for months — neither has ever been in this repo — because nobody opened `pyproject.toml`.
- **Never invent a number to fill a gap.** If the evidence does not exist, say so and name the run that would produce it. A previous audit pass substituted the _previous_ model's true-positive confidences for the adopted model's false-positive peaks and published a figure that described neither model. That is the failure this rule exists to prevent.
- **Anchor on heading plus verbatim quote, then verify page/s.** Page numbers have drifted twice already. Record the rendered page you observed and the date you observed it; treat any inherited page number as a hint until the live PDF is checked.
- **Report the paper-visible table label.** A connector's raw table number can be offset by title tables or other structural elements; reconcile it with the visible caption and rendered PDF before naming the site.

### Where it goes

Use the single Step 6 template above at `paper_sync/findings/<YYYY-MM-DD>-<slug>.md`.

**Front-matter values are cells, not prose.** Each one is pasted into a spreadsheet cell, so keep it short — a summary, not an explanation. Anything that needs reasoning goes in the body. This is the same rule as NEW, one field over.

**Page/s are rendered-document evidence.** Native Docs indexes are not page numbers. Export the live native Doc internally as PDF, match the exact OLD text against the rendered PDF, and record every matching page or page range before approval. Exact page mapping is a hard requirement because those pages must flow into the paper-audit tracker; an unresolved mapping blocks approval and the tracker write. For the tracker Sheet, record the tab name and A1 cell/range instead of a page.

The front matter is the tracker row. Its keys are the Sheet's columns, in order:

`Section / Chapter` · `Page Number` · `Required Revision` · `Notes` · `Status` · `Assigned to`

Status in use: `Not started`. Assignees in use: `Daniboy`, `Enjey`, `Meerio`, `Paulo`.

`synced: false` means the finding has not completed its approved Drive write/readback cycle or still has skipped, pending, or blocked scope. If the user declines a gate, a write fails, or readback does not match, leave it false and report the partial state. Set it to the current date only after every finding block is either successfully applied and verified or explicitly closed as out of scope, with no blocked item remaining.

Partial approval is valid: apply only the approved block numbers, maintain the `Approval / sync ledger` with exact approved, applied/read-back, skipped/pending, and blocked items, and keep `synced: false` until no finding scope remains pending or blocked and all approved writes are verified.

**One current finding per analysis.** The current dated file owns all newly implicated sites, including sites previously discussed elsewhere. Older findings remain historical records by default; resuming an approved package follows Step 3 rather than creating duplicate work. Use the ledger in the Step 6 template and maintain it after verified writes.

Then regenerate the summary — it is generated, never hand-edited:

```bash
uv run python paper_sync/build_tracker.py
```

---

## Step 7 — report and request permission

After writing the local finding and regenerating `paper_sync/TRACKER.md`, report every change block with its OLD, NEW, Evidence, page/s or Sheet range, and intended Drive target. Do not call any Drive write tool before approval.

Before approval, report a proposed manifest; do not label proposed blocks approved. After the user responds, record the exact approved subset and list every omitted block as skipped/pending. Natural-language approval such as “only 1–4” must exclude block 5 and any other unlisted target. Use the same manifest in the finding's `Approval / sync ledger` and update it after each verified write.

Include the finding/package's stable `Codex ID:` in the report so the user can search the Docs comment list once and reconcile all of its live threads.

Keep these three permission categories separate. Request approval only for applicable, unapproved scope; mark empty gates "Not applicable" and already-approved gates "Approved" without asking again:

1. **Defense paper** — permission for only the listed defense-paper replacements.
2. **Tracker Sheet** — permission for only the listed tracker updates and their formatting fallbacks.
3. **Standalone comments** — a separate permission only for comments that are not attached to a replacement, such as a figure/redraw review comment.

The Defense paper gate includes each paper replacement's `Previous` comment. The Tracker Sheet gate includes each tracker replacement's exact text-format fallback. For native Google Docs, use the Docs `insertComment` request through `google_drive_batch_update_document`, with the exact NEW range, only after its associated replacement has been read back. Do not synthesize Drive `kix.*` anchors or use the Drive comments bulk endpoint for Doc highlighting. If a native highlight cannot be created and verified, leave the proposed comment in the report and do not create an unanchored comment.

Claude ends with the local report and human-application instructions; do not solicit permission for Drive writes this workflow forbids it to perform. Sharing a wrapper does not grant another runtime Codex write capability or permission; follow its explicitly configured runtime policy.

## Step 8 — apply approved writes and verify

For each approved gate:

- Re-read the target and obtain a fresh revision ID immediately before writing.
- Apply exact Doc replacements with `google_drive_batch_update_document` and a required revision guard.
- For a Docs insertion after an existing paragraph, resolve the anchor paragraph and the next paragraph from the live Doc immediately before writing. Use their returned `startIndex`, `endIndex`, and `tabId` to determine the paragraph boundary; when the matched text ends before its terminator and the next paragraph begins at `endIndex + 1`, insert `\n<NEW>` at the current paragraph's `endIndex`. Otherwise use the boundary shown by the live ranges. Re-find the exact NEW text before creating its comment. For multiple direct range edits in one batch, apply them from highest index to lowest; never reuse indexes after an earlier mutation has shifted them.
- Update only the intended tracker row/cells with `google_drive_batch_update_spreadsheet`; read the full resolved target row immediately before writing and preserve unrelated values, formatting, validation, blank owner/status cells, and other manual columns. For an append, verify the target is fully blank by `userEnteredValue`; if not, resolve the next fully blank row under the approved semantic append target, update the finding/ledger/report, and only then write. A fixed-row approval does not authorize relocation.
- After each approved Doc replacement succeeds, find the exact NEW text again, obtain a fresh revision, and create its approved comment with a raw Docs `insertComment` request containing `content` and `range` (`startIndex`, `endIndex`, `tabId`). Apply the recorded scope: highlight only the new changed span for span scope, or one full new logical paragraph for paragraph scope. Do not combine the replacement and comment into one batch because the replacement changes the range being anchored. Before inserting, check comments with the package ID and match the expected scope, content, and quote/anchor to avoid duplicates.
- Automatic cleanup applies only to incorrect, duplicate, or provisional comments created by this execution for an approved block, identified by returned comment IDs. Delete those comments with the provider's comment-deletion operation and verify deletion; do not resolve them as a substitute. Deleting other comments requires explicit approval. If deletion is unavailable, leave the affected operation blocked, report the limitation, and continue independent approved work where safe.
- Read back the changed Doc paragraphs, Sheet cells, comment state, and any Sheet text-format fallback. For a native Doc comment, verify the returned `commentThread`, non-empty anchor, exact `plainTextQuote`/quoted text (HTML-decode entities before comparison), the expected `Codex ID:`, and that the content ends with `Done by Codex.`.
- Update the local finding's approval/sync ledger after each verified artifact. Update `synced` only when no block remains skipped, pending, or blocked and every approved write has passed read-back.

After all approved writes and read-backs, run a fresh read-only sweep of the live artifacts for the corrected claims and their propagation sites. Record any new site outside the manifest with OLD/NEW text and evidence in the finding and leave it pending. Request approval before writing new scope; do not silently expand the manifest or mark the whole finding synced. Report verified completion of the authorized subset even when new sites remain pending. Generic technical or ordinary-language matches may be classified as out of scope only with an explicit justification.

If a revision guard fails, a tracker row changes, or readback differs, pause that artifact's writes and re-read and reconcile before retrying. Resume under existing approval only when the exact approved content, semantic target, preservation requirements, and comment scope remain unchanged; refresh indexes and revision guards and rebuild the ledger from the fresh read. Never reapply a verified replacement just to retry its comment. If the approved contract changed, leave the affected block blocked and request revised approval. Continue independent approved work only where its prerequisites remain satisfied; do not retry blindly or loop on a recurring unresolved conflict.

### Task completion versus finding sync

An analysis request is complete when the requested scope has been examined and findings, evidence, and limitations are reported. If access prevents full examination, report the completed portion and exact remaining blocker without claiming the full analysis complete. An application request is complete for its authorized subset when its writes, required comments or formatting, and verification succeed. Finding-level `synced` remains false while any scope is outstanding. A pending new site does not invalidate verified completion of the authorized subset, and an analysis-only task does not require Drive application to finish.

**An aside still gets a finding file.** If you notice something real while looking at something else — a duplicated table number, a figure that contradicts its caption — file it. Scope limits where you look, not what you are allowed to report. Give it its own change or redraw block and say in the report that it came up incidentally.

**If nothing drifted, say that plainly.** A clean result is a real result. A procedure that always finds something is one nobody trusts.
