# Test Validation Handoff Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebase the validation work onto the latest main branch, consolidate the executable testing handoff into one AI-readable guide, verify the changed behavior and Playwright workflow, and deliver the result through a reviewed pull request.

**Architecture:** Keep runtime fixes in their existing backend and frontend modules. Keep tracker-bound tests and reusable runner scripts beside the component they exercise. Add one canonical guide at `docs/validation/ADAS_TESTING_GUIDE.md` that maps every test family, command, environment, evidence rule, and known limitation without fabricating results.

**Tech Stack:** Python 3.12.13 through `uv`, FastAPI, SQLModel, React, Vitest, Playwright, PowerShell, GitHub CLI.

**Spec:** User request in the active task, `AGENTS.md`, `CLAUDE.md`, and `paper_sync/PROCEDURE.md`.

## Global Constraints

- Run commands from the repository root.
- Use `uv run python`, never bare `python`.
- Preserve the 2K main-stream-only scope and the 5 to 15 FPS target.
- Do not modify `FPS_BAND_MIN`, snooze timing, tab names, row order, or workbook structure.
- Do not claim an environmental or human prerequisite passed when it was only simulated.
- Do not commit credentials, local databases, generated browser state, or private design notes.
- Do not write to Google Drive from this repository task.

---

### Task 1: Rebase and classify the existing work

**Files:**

- Modify: existing tracked runtime and test files already changed in the working tree
- Inspect: `git status`, `git diff`, `git log`, `origin/main`

- [ ] Preserve tracked edits in a stash.
- [ ] Rebase the feature branch onto fetched `origin/main`.
- [ ] Reapply the tracked edits and classify untracked files into commit candidates, local-only files, or unrelated user work.

### Task 2: Consolidate the testing handoff

**Files:**

- Create: `docs/validation/ADAS_TESTING_GUIDE.md`
- Modify: tracker-bound test module docstrings when they still describe resolved defects as open
- Inspect: `docs/validation/test-execution-validation-plan.md`, `e2e/README.md`, `backend/tests/README.md`, `ai_engine/tests/README.md`, `CLAUDE.md`, and the tracker-bound runner scripts

- [ ] Document setup, ports, profiles, credentials by reference only, test data isolation, and cleanup.
- [ ] Map Unit, Integration, System E2E, Performance, Reliability, Security, and Backup and Recovery families to exact commands and case IDs.
- [ ] Describe the browser workflow and the Playwright YAML workflow.
- [ ] Record the 2K main-stream-only resolution, 5 to 15 FPS target, 25 second UAT operator timing, and 15 second snooze boundary.
- [ ] Record skipped AI validation and backup execution, plus all known evidence limitations.
- [ ] Make the guide self-contained enough for another agent to execute it without relying on conversation history.

### Task 3: Verify behavior and repository hygiene

**Files:**

- Test: targeted backend selectors, focused frontend selectors, Playwright YAML tests, and relevant lint and format checks

- [ ] Run targeted tests for the runtime fixes.
- [ ] Run the repository's Playwright YAML checks from the latest branch.
- [ ] Run relevant formatting, lint, type, and build checks.
- [ ] Confirm generated artifacts and unrelated untracked files are excluded from the commit.
- [ ] Run the paper-sync local triage for claim-bearing runtime changes and record whether a finding is needed.

### Task 4: Commit and review

**Files:**

- Commit: only the organized validation handoff, runtime fixes, tracker-bound tests, and reusable scripts that belong to this change

- [ ] Create conventional commits with focused scopes.
- [ ] Push the feature branch.
- [ ] Open a detailed pull request targeting `main` with verification results and known limitations.
- [ ] Wait for required checks and inspect failures independently.
- [ ] Merge only after the required checks pass and the working tree is clean.
