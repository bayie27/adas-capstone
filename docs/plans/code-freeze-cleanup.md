# ADAS code-freeze cleanup and organization handoff

## 1. Objective, decisions and execution setup

Perform a comprehensive, behavior-preserving cleanup of the ADAS repository before code freeze. Remove confirmed dead code, obsolete tests, unnecessary comments, disposable artifacts and organizational clutter. Improve documentation discoverability and create a polished main README without losing useful information.

**Executor:** Sonnet 5, High reasoning, in a new session.

**Intended handoff file:** `docs/plans/code-freeze-cleanup.md`.

This approved handoff is now saved to disk. Save it before starting implementation.

### Approved decisions

- Archive historical documentation inside the repository.
- Keep component documentation alongside its code; organize shared documentation under `docs/`.
- Preserve runtime behavior. No architectural redesign, feature implementation or dependency upgrades.
- Remove the dormant delivery-backlog frontend feature; preserve the working AI outbox.
- Delete the batch-32 engine artifact.
- Audit local artifacts individually rather than treating every ignored file as disposable.
- Remove only clean, fully merged, confirmed inactive worktrees.
- Do **not** create `OPEN_ITEMS.md`.
- Preserve useful README information by moving it to explicit destinations and maintaining navigation.
- Give the main README a polished technical presentation.
- Use one lead editor and two read-only subagents.

### Starting state and planning evidence

Planning was performed against `main` at `041c863`.

- Inventory: 658 tracked files, 620 readable tracked text files and 148 Markdown documents.
- No tracked modifications were present during the final planning status check.
- No ordinary untracked files were reported, but ignored artifacts exist.
- `.codex-pytest-tmp/` could not be inspected because access was denied.
- Frontend typecheck passed.
- Ruff passed accessible files with an access warning.
- Full test suites were not run.
- Searches covered the tracked text corpus; selected implementation and test bodies were inspected. This is not a claim that every function has already received semantic review.

Revalidate these facts before execution. Preserve changes made after this baseline.

### Branch and authorization

Read `AGENTS.md` and `CLAUDE.md`. Work from the repository root on `chore/code-freeze-cleanup`, created from the current checkout after recording its state.

Do not push, create a PR, deploy, reseed the current database, or modify live Google artifacts. Do not discard existing changes.

## 2. Agent responsibilities and completeness ledger

The lead agent must explicitly spawn these **subagents within its session**, not separate user-facing tasks:

| Agent                  | Responsibility                                                                            | Restrictions                                            |
| ---------------------- | ----------------------------------------------------------------------------------------- | ------------------------------------------------------- |
| Code/tests auditor     | Review runtime code, test relevance, references, dependencies and deletion candidates     | Read-only; no edits, package installs or test processes |
| Docs/artifacts auditor | Review documentation, links, historical evidence, assets, ignored artifacts and worktrees | Read-only; do not expose secrets or modify local state  |
| Lead agent             | Reconcile findings, ask necessary questions, perform all edits and run verification       | Sole mutation owner                                     |

Give auditors concrete paths and deliverables. Require each finding to state the file/symbol, evidence, proposed action, preservation requirements and uncertainty.

Auditors may continue independently while the lead inventories configuration and prepares the move manifest. Do not delete an item while its relevant audit remains unresolved.

After implementation, send both auditors the baseline and final diff for another review. Resolve their findings before declaring completion. If subagents are unavailable, execute these same passes sequentially and report the fallback.

Maintain one `docs/plans/code-freeze-cleanup-audit.md` with:

- Baseline HEAD and working-tree status.
- Every tracked file's disposition: retain, edit, move or delete.
- Exact source/destination paths for moves.
- Deletion evidence and test-coverage implications.
- Local-artifact inventory and individual dispositions.
- Verification results and deferred decisions.

Group unchanged files compactly, but account for every tracked path. This ledger is an execution record, not a new product backlog.

### Required audit coverage

Inspect all of the following:

- Backend routes, services, models, schemas, core infrastructure, maintenance and development tooling.
- Alembic history, backend scripts, unit/integration tests and performance tests.
- Frontend routes, APIs, components, hooks, stores, utilities, styles, tests and public assets.
- AI runtime, configuration, tests, evaluation harnesses, diagnostics, prototypes and evidence.
- Playwright configuration, tests and visual baselines.
- PowerShell/shell launchers, MediaMTX profiles and systemd deployment files.
- Package manifests, lockfiles, CI, hooks, formatting and ignore configuration.
- Root/component READMEs, historical plans, handoffs, validation documents and paper-sync references.
- Ignored local files, generated directories and registered worktrees.

File age, size, an unfamiliar name or lack of a simple import reference is not sufficient deletion evidence.

## 3. Documentation organization and README redesign

### Target layout

| Location              | Purpose                                                                  |
| --------------------- | ------------------------------------------------------------------------ |
| Root                  | Project README, contributor/agent entrypoints and required configuration |
| Component directories | Component READMEs and technical references used beside code              |
| `docs/README.md`      | Documentation navigation and authority guide                             |
| `docs/operations/`    | Shared setup and operational instructions                                |
| `docs/architecture/`  | Verified current architecture and contracts                              |
| `docs/validation/`    | Testing guidance and traceability references                             |
| `docs/archive/`       | Historical plans, audits, decisions and execution reports                |
| `docs/plans/`         | This handoff and execution ledger                                        |
| `paper_sync/`         | Existing paper-sync workflow and records                                 |

### Required moves

- Move `LAN_SETUP.md` to `docs/operations/LAN_SETUP.md`.
- Move `be_plan/`, `be_audit/` and `dev_plan/` into matching directories under `docs/archive/`.
- Move `be_decisions_review.md` and `paper-audit.md` into `docs/archive/`.
- Move these files into `docs/archive/validation/`, keeping their filenames:
  - `LAN_DEMO_HANDOFF.md`
  - `NFR04_LAN_MEASUREMENT_HANDOFF.md`
  - `UAT_READINESS_DRY_RUN_HANDOFF.md`
  - `UAT_READINESS_DRY_RUN_RERUN_LOG.md`
- Move `test-execution-validation-plan.md` and `unit-testing-coverage-review.md` into `docs/validation/`.
- Keep `frontend/VISUAL_CHECKLIST.md` alongside frontend code.
- Keep AI documentation, diagnostics and prototypes in their existing component locations.
- Keep `paper_sync/` and both runtime skill wrappers in place.

Before moving backend plans and decisions, extract still-applicable architecture, contracts and rationale into `docs/architecture/README.md`. Verify against current implementation and `CLAUDE.md`; retain decision identifiers and source links. Report contradictions rather than inventing replacements.

Label archived material as historical and non-executable. Preserve its measurements, verdicts and outstanding findings without implying they are resolved. Do not create `OPEN_ITEMS.md`.

Label local validation documents as dated references where applicable. Do not imply they supersede live Google documents or trackers.

### Preserve information before shortening READMEs

For each substantial section removed from a README, record its destination in the move manifest.

- Installation and shared operational detail → `docs/operations/`.
- Architecture and cross-component contracts → `docs/architecture/`.
- Component-specific configuration and diagnostics → component README or existing component docs.
- Test execution and validation detail → `docs/validation/`.
- Historical experiments and execution narratives → archive or existing AI historical references.

Delete prose only when it is demonstrably redundant, obsolete or incorrect. Consolidating duplicates must retain unique constraints, caveats and troubleshooting information.

### Main README presentation

Use a polished technical style suited to both a public repository and the defense:

1. Existing ADAS logo and a concise project description.
2. A small set of accurate badges: CI and verified stack information.
3. One representative dashboard screenshot using an existing suitable asset or a sanitized new capture.
4. Concise implemented capabilities.
5. A small Mermaid architecture diagram grounded in the actual RTSP → AI engine → backend → dashboard flow.
6. Prerequisites and a short working quick start.
7. Links to component guides, operations, architecture, testing and contribution instructions.
8. Accurate academic attribution.

Avoid invented coverage, deployment, licensing, adoption or performance claims. Do not add decorative badges that imply unsupported status. Do not expose private footage, credentials or live incident data in screenshots.

Replace the frontend's Vite template README with actual project setup, structure, commands and testing guidance. Reconcile backend and AI READMEs with current code.

### Link and authority audit

Update all affected links and paths, including references inside:

- Active and archived Markdown.
- Agent instructions and skill references.
- Source/test comments.
- CI, scripts and tooling exclusions.
- Paper-sync claim-source references.

Handle special cases correctly:

- Help Center links use article slugs; do not convert valid slugs into filesystem links.
- Imported training documents contain references to another repository. Use verified source links when available; otherwise explicitly identify unavailable source-repository paths.
- Do not rewrite frozen `ai_engine/adas_transfer/` to repair its historical links.
- Historical instructions such as “No Alembic until P9” must not appear as current guidance.

## 4. Code, comments, tests and tooling

### Confirmed cleanup

**Delete the eight tracked one-off scripts under `scratch/`:**

`patch_adduser.py`, `patch_ai.py`, `patch_audit.py`, `patch_audit2.py`, `patch_changepass.py`, `patch_confirmdelete.py`, `patch_edituser.py` and `patch_users.py`.

These rewrite frontend source files and are not runtime utilities. Do not execute them.

**Remove the dormant delivery-backlog frontend feature:**

- `useDeliveryBacklog` hook, associated type and dedicated test.
- `DeliveryBacklogNotice` component and dedicated tests.
- Related imports, invocation, rendering and comments in `App.tsx`.
- Related mocks in `App.test.tsx`.

The hook currently always returns `null`; the banner cannot appear. Preserve all real AI outbox storage, retry, quarantine and delivery behavior. Record the removed frontend feature's historical intent in the audit ledger.

**Remove the nested frontend lockfile** after rechecking root workspace ownership. Preserve the root lockfile, package versions and workspace setup.

Replace placeholder project metadata with an accurate description.

### Remaining code and test audit

For each additional deletion candidate, inspect:

- Direct and dynamic imports.
- Framework registration and public interfaces.
- CLI entrypoints and subprocess calls.
- Configuration-based selection.
- Test fixtures and helpers.
- Documentation commands and optional tooling.

Keep lazy-loaded frontend pages and the runtime-gated development panel.

Remove stale comments, obsolete implementation-phase narration, commented-out experiments and comments that merely repeat syntax. Preserve concise explanations of security, races, compatibility, platform limitations and numerical behavior.

For tests:

- Compare actual assertions and setup before declaring duplication.
- Preserve distinct authorization, failure, boundary, recovery, race and hostile-input cases.
- Preserve parity tests and frozen-reference comparisons.
- Retain legitimate GPU, clip, performance and platform skips.
- Retain documented expected failures unless their condition is verified obsolete.
- Documentation-only permanently skipped placeholders may move into validation guidance when they exercise no behavior; preserve traceability.
- Update documented selectors when tests move or disappear.

Do not split large modules or test files solely because of size. Do not weaken assertions to make cleanup pass.

### Tooling

Simplify duplicate and irrelevant ignore-file boilerplate while preserving protections and intentional asset exceptions.

Update formatter exclusions for moved archives so historical relocation does not trigger broad unrelated formatting changes. Preserve Ruff's Markdown exclusion and frozen-reference exclusions.

Do not remove dependencies, fonts, icons or public assets based solely on import searches. Account for CSS, URL references, optional execution paths and generated content.

### Protected behavior and evidence

No changes to routes, payloads, database schema, environment-variable contracts or visible working features.

Preserve:

- Alembic history and UTC timestamp handling.
- Services-layer ownership and atomic audited transactions.
- Authentication, authorization and incident/camera state transitions.
- Backup, restore and protected-storage behavior.
- Model selection and explicit failure behavior.
- TensorRT constraints and package declarations.
- Detection confidence, fixed cadence and accumulator reset seams.
- GPU arithmetic and cited prototype provenance.
- Evaluation labels/results, clips, licenses and visual baselines.

New functional defects discovered during cleanup are reported separately rather than silently expanding the task.

## 5. Local artifacts and worktrees

### Batch-32 engine

Delete only `ai_engine/epoch50-32.engine` after rechecking configuration and active usage.

Planning found `AI_MODEL_PATH=ai_engine/epoch50.engine`.

Preserve the active `epoch50.engine`, tracked `epoch50.pt` and, by default, `epoch50.onnx`. Preserve historical batch comparison measurements; identify the old binary as removed without rewriting the experiment's results.

### Local cleanup

Inventory caches, temporary files, logs, build output and reports individually. Delete only exact targets established as disposable and inactive.

Do not use blanket `git clean`, recursive wildcard deletion or directory-name assumptions.

Protect pending specific review:

- `.env`, certificates and agent configuration.
- `.venv`, `node_modules` and working dependency installations.
- Databases and SQLite sidecars.
- Incident snapshots, evaluation clips and outbox contents.
- Backups, restore state, UAT runs, safety backups and evidence.
- Inaccessible directories.

Do not delete `var/` or `tmp/` wholesale. They contain mixed-purpose material.

Before recursive Windows moves or deletions, verify each resolved absolute target is inside the specifically authorized directory. Use literal-path PowerShell operations. Do not change permissions to force access to blocked artifacts.

### Worktrees

Planning found seven additional worktrees:

- Three were clean.
- Four contained local changes or untracked files.
- All committed histories were reachable from `main`.

Recheck each before acting.

Remove a worktree only when it is clean, fully merged and confirmed unused by an active task or process. Use Git worktree commands and preserve its branch.

Keep dirty worktrees, including the one containing untracked `19_PKG_fe_backend_gaps.md` and `20_FRONTEND_HANDOFF.md`. Do not relocate or discard those files without a separate decision.

If activity cannot be established, defer removal. Respect permission boundaries for worktrees outside this repository.

## 6. Execution order, verification and completion

### Ordered batches

1. Record baseline; spawn auditors; build the disposition ledger and move manifest.
2. Perform documentation moves and update references.
3. Consolidate current documentation and redesign READMEs.
4. Remove confirmed dormant code, obsolete tests and scratch scripts.
5. Perform additional evidence-backed comment/code/tooling cleanup.
6. Run relevant verification.
7. Remove approved disposable local artifacts and eligible worktrees.
8. Obtain both subagents' final reviews; resolve findings and complete the ledger.

Keep batches distinguishable in the diff. Do not mix functional refactoring into organizational changes.

### Verification

- Compare final tracked paths with the baseline manifest; account for every move and deletion.
- Check Markdown targets, anchors, old-path references and archive navigation.
- Validate Help Center links using article-slug semantics.
- Check that useful README content survived at its intended destination.
- Run frontend App tests, frontend lint, typecheck and build for dormant UI removal.
- Run targeted Python tests for Python changes; use the full default suite for cross-cutting changes.
- Verify documented test selectors through existing test collection.
- Check formatting of edited material without reformatting frozen or historical artifacts unnecessarily.
- Confirm root workspace lockfile ownership and unchanged dependency versions.
- Verify protected binary/reference files remain unchanged.
- Follow `paper_sync/PROCEDURE.md` local claim-bearing triage. Produce findings only for verified drift; do not claim live paper synchronization.
- Use disposable databases for checks. Never reset current application data to make tests pass.

Follow repository lifecycle gates: if a PR is later requested, run `pnpm full:check`; if pushing is later authorized, let pre-push run `pnpm check`. Do not add redundant confirmation runs for already passing suites.

### Final audit and report

The lead and auditors must check for:

- Lost information or historical evidence.
- Broken references and inconsistent documentation authority.
- Changed runtime contracts.
- Accidental data deletion.
- Lost test coverage.
- Unsupported README claims.
- Unaccounted files or unfinished moves.

Report:

- What was removed, relocated and preserved.
- Verification passed, failed or unavailable.
- Exact deferred items and reasons.
- Any baseline issues discovered.
- Confirmation that no live Google artifacts, current data or runtime contracts were changed.

Cleanup is complete when the manifest is reconciled, relevant checks pass, final audit findings are resolved or explicitly deferred, and the repository is easier to navigate without losing behavior or evidence. Cleanup completion does not establish UAT readiness.

### New-session execution prompt

> Read AGENTS.md, CLAUDE.md and docs/plans/code-freeze-cleanup.md. Execute the approved cleanup using Sonnet 5 with High reasoning. Spawn the two read-only audit subagents specified in the handoff; remain the sole editor and test runner. Revalidate the baseline, maintain the disposition ledger, preserve README information through explicit moves, and complete the final independent audits. Do not create OPEN_ITEMS.md. Ask only about concrete unresolved retention, ownership or placement decisions while continuing independent work. Do not push, create a PR, alter current application data or modify live Google artifacts.
