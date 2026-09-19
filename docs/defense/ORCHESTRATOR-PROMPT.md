# Orchestrator prompt

Paste the block below as the **first message of a single Luna Max session**. That session
does not write any guides itself — it spawns one sub-thread per guide, hands each the
verbatim prompt from [`THREAD-PROMPTS.md`](THREAD-PROMPTS.md), and verifies the results.

````text
You are the ORCHESTRATOR for building the ADAS capstone defense study pack. You will not
write any study guides yourself. Your job is to dispatch sub-agents, one per guide, and
then verify what they produced.

Repo root is the ADAS project. Read these two files before doing anything else:

  docs/defense/THREAD-PROMPTS.md   <- 31 ready-made prompts, one per guide
  docs/defense/PLAN.md             <- source map, precedence rule, house rules, template

THREAD-PROMPTS.md contains 31 sections, each headed "## NN — <title>" and each containing
exactly one fenced ```text block. That fenced block IS the prompt for that guide.

== HOW TO DISPATCH ==

For each guide, spawn a SEPARATE sub-agent and pass it the contents of that guide's fenced
block VERBATIM as its prompt. Do not summarise it, do not reword it, do not merge two
guides into one agent, and do not add your own instructions on top of it. Each block is
already self-contained and was written to be used exactly as-is.

Give each sub-agent a short description naming its guide, e.g. "Write guide 13 — security
architecture", so progress is readable.

== WAVES — THIS ORDERING IS MANDATORY ==

WAVE 1 — 28 guides: numbers 01 through 27, plus 31.
  Launch these in parallel. If you can only run a limited number of agents concurrently,
  run them in batches of 6-8 and start the next batch as the previous one finishes. Do not
  run them one at a time; the whole point of this structure is concurrency.

WAVE 2 — 3 guides: numbers 28, 29 and 30.
  These read the Wave 1 output files as their primary input, so they MUST NOT start until
  every Wave 1 guide has been written to disk. Launch them in parallel with each other
  once Wave 1 is complete.

Guides 28, 29 and 30 are marked "Wave 2" in THREAD-PROMPTS.md. Everything else is Wave 1.

== AFTER EACH WAVE ==

Confirm each expected output file actually exists at the path its prompt specified. If a
sub-agent failed, produced nothing, or wrote to the wrong path, re-dispatch that single
guide with the same verbatim prompt. Do not write the guide yourself to patch a gap.

Report a short status after each wave: which guides landed, which failed, which were
retried.

== FINAL VERIFICATION ==

Once all 31 guides exist, run the verification checklist in the "Verification" section of
docs/defense/PLAN.md. In particular:

  1. All 31 guide files exist in the right folders. Each of guides 01-27 has all eight
     template sections. (Guides 28, 29, 30 and 31 deliberately deviate from the template —
     their own prompts say so. Do not force the template onto them.)
  2. Numeric consistency: cross-check figures in 28-numbers-cheat-sheet.md against the
     tracker and the test plan, and against the guide each figure came from. Any figure
     appearing in two guides must match. This is the highest-value check — do it properly.
  3. Grep the pack for "Resolved" (the paper's term is "Cleared") and for any leftover
     "[UNSOURCED" markers. Report both lists.
  4. Grep for hedging that contradicts the paper or re-litigates the tracker's framing, and
     rewrite those passages to the authoritative framing.
  5. Spot-check about 20 "path/file.py:123" code citations across guides; line numbers
     drift. Report any that no longer point at the right thing.
  6. Confirm every FR-01 through FR-20 and NFR-01 through NFR-22 appears in guide 08.
  7. Pick three Q&A answers at random and check each can be spoken in under 30 seconds.

Fix what you find, or report it clearly if a fix needs a human decision.

Finally run: pnpm exec prettier --write "docs/defense/**/*.md"

== RULES ==

- Do not modify any code. This is a documentation-only task.
- Do not edit docs/defense/PLAN.md, 00-START-HERE.md, THREAD-PROMPTS.md or this
  orchestrator file. They are inputs, not outputs.
- The defense paper and the test tracker are authoritative over repo engineering docs.
  If a sub-agent reports a "contradiction" between them, that is expected and is not a
  problem to escalate — the paper/tracker framing wins.
- Do not commit anything. Leave the working tree for a human to review.

Start by reading the two files, then confirm back to me the list of 31 guides you found
and your Wave 1 batching plan. Then begin.
````

## Notes

- The orchestrator is told to **confirm its plan before dispatching**, so you get one
  checkpoint to catch a misread before 28 agents spend tokens.
- If your Luna Max session has no sub-agent capability, use
  [`THREAD-PROMPTS.md`](THREAD-PROMPTS.md) directly and open the threads by hand — the
  blocks are identical either way.
- Wave 2 genuinely depends on Wave 1. If you run them early, guides 28–30 will have
  nothing to read and will quietly invent their content.
