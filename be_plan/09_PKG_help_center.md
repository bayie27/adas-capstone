# P8 — Help Center

> **Blocked by:** P2 only. Parallel-safe with P5, P6, P7.
> **Branch:** `feat/be-p8-help-center`
> **Prerequisite reading:** [`01_CONTRACTS.md`](01_CONTRACTS.md) §§3.9, 5.11.
> **Size:** S. Four steps. This is a good filler package between larger ones.

## Why this package exists

FR-20 requires a "centralized, searchable, role-tailored" Help Center with SOPs, navigation guides,
and FAQs, and UC-10 specifies the behavior. **It appears in none of D-001…D-012** — it is a genuine
gap in the decision record, resolved in this planning session in favor of a small backend module so
FR-20 has real backend test evidence rather than being quietly reclassified as frontend styling.

Scope is deliberately small: articles are authored as markdown files in the repo, seeded into the
database, searched with SQLite FTS5, and filtered by the caller's role. No CMS, no admin authoring UI,
no versioning.

---

## Step 1 — Content directory

**Location:** `backend/content/help/`

One markdown file per article, with YAML frontmatter:

```markdown
---
slug: confirming-an-accident-alert
title: Confirming an Accident Alert
category: Operations
roles: [Admin, Operator]
summary: What to check before confirming, and what happens after you do.
sort_order: 10
is_faq: false
---

## Before you confirm
…
```

`roles` controls visibility. An Admin-only article omits `Operator`. Note FR-02: Administrators
inherit all Operator privileges, so an article visible to Operators is **also** visible to Admins —
encode that in the filter, not by duplicating articles.

Write a starter set covering what UC-10 names, drawn from the paper's own workflows:

| Category | Articles |
|---|---|
| Operations | confirming an alert, dismissing a false positive, the 60-second cooldown, resolving an ongoing incident, correcting a mistaken confirmation, snoozing an alarm |
| Monitoring | reading the dashboard KPIs, camera connection vs AI status, what "Unresponsive" means, reading system health |
| Administration *(Admin only)* | creating users and assigning roles, resetting a password, the last-admin guard, reading the audit trail, taking a backup, restoring from a backup |
| FAQ (`is_faq: true`) | six to eight short entries — these are what UC-10 surfaces when a search returns nothing |

Keep them short and accurate to the implemented behavior. An article describing a workflow the
backend does not have is worse than no article.

---

## Step 2 — Seeding

**File:** new `backend/app/services/help.py` + a hook in `init_db()`

- Parse frontmatter (`python-frontmatter`, or a small parser — this is simple enough not to warrant a
  dependency; decide and note it).
- Upsert by `slug`. Store a `content_hash` and skip unchanged files, so startup seeding is cheap and
  idempotent.
- Delete rows whose slug no longer has a file, so removing an article actually removes it.
- Validate every `roles` entry against `UserRole` and fail loudly on a typo — a misspelled role
  silently hides an article from everyone.
- Run at startup **and** expose it through `reseed_dev.py`.

---

## Step 3 — FTS5 search

Create an external-content FTS5 virtual table over `title`, `summary`, and `body_markdown`, kept in
sync by insert/update/delete triggers on `help_article`.

```sql
CREATE VIRTUAL TABLE help_article_fts USING fts5(
    title, summary, body_markdown,
    content='help_article', content_rowid='article_id',
    tokenize='porter unicode61'
);
```

- FTS5 is compiled into the standard CPython SQLite build. **Verify it at startup** and fall back to
  `LIKE`-based search with a logged warning if the module is unavailable — do not let a missing
  compile option take down the whole app.
- Sanitize user input before passing it to `MATCH`. Raw FTS5 query syntax (`"`, `*`, `NEAR`, `OR`) in
  a search box produces confusing errors; quote the terms and treat the input as a phrase/prefix
  search.
- Rank with `bm25()`, tie-broken by `sort_order` then `title`.

---

## Step 4 — Endpoints

```
GET /api/help/articles?search=&category=
GET /api/help/articles/{slug}
```

Both require a session. Both filter by the **caller's** role — an Operator requesting an Admin-only
slug gets `404`, not `403`, so the endpoint does not confirm the article exists.

List response:

```json
{
  "items": [ { "slug": "...", "title": "...", "category": "...", "summary": "...", "is_faq": false } ],
  "top_faqs": []
}
```

`top_faqs` is populated **only when a search returned no results** — UC-10 requires the empty state to
show Top FAQs rather than a dead end. The paper also pins the empty-state string
*"No articles found for your search."*; return a machine-readable empty result and let the frontend
render that copy.

Detail response returns `body_markdown` raw. The frontend renders it — **do not render HTML on the
backend**, and note in the docstring that the frontend must sanitize before rendering.

Help Center access is not audited (it is a read-only reference, and D-007 excludes routine reads).

---

## Verification

```bash
uv run pytest backend/tests/test_help.py
```

Manually:

1. Log in as an Operator → `GET /api/help/articles` lists Operations and Monitoring articles and
   **no** Administration articles.
2. Log in as an Admin → the same call lists everything, including the shared Operator articles.
3. `GET /api/help/articles?search=cooldown` → the cooldown article ranks first.
4. `GET /api/help/articles?search=zzzznotathing` → empty `items`, populated `top_faqs`.
5. As an Operator, `GET /api/help/articles/reading-the-audit-trail` → `404`.
6. Edit an article's markdown, restart → the change appears. Restart again with no edit → no writes.
7. Search for `"` and for `NEAR(a b)` → a clean empty result, not a 500.
8. `pnpm check`.

---

## Tests to write

| Area | Assertions |
|---|---|
| Frontmatter | valid file parses; a bad `roles` value fails loudly at seed time |
| Idempotent seeding | re-seeding unchanged content writes nothing; a changed file updates; a deleted file removes the row |
| Role filter | Operator cannot list or fetch Admin-only articles; Admin sees Operator articles too |
| Search | term matching, ranking order, case insensitivity |
| Search sanitization | FTS5 metacharacters do not raise |
| Empty state | no results → empty `items` + non-empty `top_faqs` |
| Auth | both endpoints require a session |
| FTS fallback | with FTS5 unavailable, `LIKE` search still returns sensible results |

## Paper test cases covered

FR-20 and UC-10 (role-filtered article list, search, markdown SOPs, Top FAQs on a null result).

## Deliberately not in this package

Admin authoring UI, article versioning, rich media, and multi-language content. None are in the paper.
