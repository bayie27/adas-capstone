# AGENTS.md

Entry point for coding agents. Read by Claude Code, Codex, and Antigravity alike.

This file is a pointer, not a rulebook. It stays short on purpose: the conventions live in one place so they cannot drift, and Antigravity caps rules files at 12,000 characters.

## Conventions, commands, and gotchas

**Read [`CLAUDE.md`](CLAUDE.md).** Despite the name it is runtime-neutral — commands, the services-layer rule, the migration policy, the UTC timestamp type, the AI-engine constraints, and the testing and verification policies. It applies to every agent working in this repo, not just Claude.

Two that catch everyone, repeated here because they cost the most time:

- **Run everything from the repo root**, and always `uv run python`, never bare `python` — PATH `python` is 3.14 and the project is pinned to 3.12.13.
- **`pnpm check` runs on pre-push already.** Don't run it manually first; just push.

## Keeping the defense document honest

The code has run ahead of the paper. When a change touches something the paper describes — routes, model columns, constants quoted by value, dependencies, deployment, AI-engine behaviour — check it with [`paper_sync/PROCEDURE.md`](paper_sync/PROCEDURE.md).

That procedure produces a proposed edit with evidence. It never edits the paper itself; a human applies it.

It is also packaged as an invocable skill, `adas-paper-sync`, in both directories this repo carries:

| Runtime            | Skill directory                   |
| ------------------ | --------------------------------- |
| Codex, Antigravity | `.agents/skills/adas-paper-sync/` |
| Claude Code        | `.claude/skills/adas-paper-sync/` |

Both wrappers point at the same `paper_sync/PROCEDURE.md`; they differ only in the tool mechanics for reading the Doc. If your runtime does not pick up a project-level skill, point it at the procedure directly — nothing in it depends on the skill loading.
