# AGENTS.md

Entry point for coding agents. Read by Claude Code, Codex, and Antigravity alike.

This file is a pointer, not a rulebook. It stays short on purpose: the conventions live in one place so they cannot drift, and Antigravity caps rules files at 12,000 characters.

## Conventions, commands, and gotchas

**Read [`CLAUDE.md`](CLAUDE.md).** Despite the name it is runtime-neutral — commands, the services-layer rule, the migration policy, the UTC timestamp type, the AI-engine constraints, and the testing and verification policies. It applies to every agent working in this repo, not just Claude.

Three that catch everyone, repeated here because they cost the most time:

- **Run everything from the repo root**, and always `uv run python`, never bare `python` — PATH `python` is 3.14 and the project is pinned to 3.12.13.
- **When a push is already authorized, pre-push runs `pnpm check`.** Don't run it manually beforehand. This rule does not authorize a push; use narrow relevant checks for local work.
- **Branch names use the work type and scope**, such as `feat/`, `fix/`, `docs/`, `test/`, `refactor/`, or `chore/`. Do not add agent or runtime prefixes such as `codex/` or `claude/`.

## Keeping the defense document honest

The code has run ahead of the paper. When a change touches something the paper describes — routes, model columns, constants quoted by value, dependencies, deployment, AI-engine behaviour — check it with [`paper_sync/PROCEDURE.md`](paper_sync/PROCEDURE.md).

When verified drift exists, that procedure produces a local proposed edit with evidence. Otherwise report no drift within the examined scope; do not create an empty finding. Codex can read the whole native Docs through Google Drive MCP, map passages to rendered PDF pages, and apply explicitly approved updates to the defense paper, audit Doc, and tracker Sheet with read-back verification; a TXT export is only a fallback. Claude Code remains read-only and requires a human to apply them.

It is also packaged as an invocable skill, `adas-paper-sync`, in both directories this repo carries:

| Runtime            | Skill directory                   |
| ------------------ | --------------------------------- |
| Codex, Antigravity | `.agents/skills/adas-paper-sync/` |
| Claude Code        | `.claude/skills/adas-paper-sync/` |

Sharing the Codex wrapper does not grant Antigravity Codex write capability or permission; follow its explicitly configured runtime policy.

Both wrappers point at the same `paper_sync/PROCEDURE.md`; they differ in Drive mechanics and write capability. If your runtime does not pick up a project-level skill, point it at the procedure directly.
