# Backend content

Content the application serves, kept as files rather than in code so it can be
edited without a code change.

Today that is one directory: `help/`, the Help Center articles.

## `help/` — Help Center articles

The 33 Markdown files in `help/` are the source of truth for the Help Center inside
the app. Editing one changes what operators read.

`backend/app/services/help.py` loads them into the `help_article` table on startup.
It matches on `slug`, skips files whose content has not changed, and **deletes the
row for any file you remove**. Re-seeding unchanged content writes nothing. The
FTS5 search index updates itself from database triggers.

> **Only article files belong in `help/`.** The loader parses every `*.md` in that
> directory and stops with an error on the first one it cannot read as an article —
> which fails startup. That is why this README sits here rather than inside `help/`.

### Frontmatter

Every article opens with a `---` block. It is a small fixed format, not full YAML —
plain `key: value` lines only.

```markdown
---
slug: managing-cameras
title: Adding, Editing, and Disabling Cameras
category: Operations
roles: [Admin, Operator]
summary: Registering a new camera, renaming one, and taking a camera out of service.
sort_order: 70
is_faq: false
---
```

| Field        | Required | Notes                                                          |
| ------------ | -------- | -------------------------------------------------------------- |
| `slug`       | Yes      | The article's address. Other articles link to it by this name. |
| `title`      | Yes      | Shown as the heading and in search results.                    |
| `category`   | Yes      | Groups the article under a tab.                                |
| `roles`      | Yes      | Who can see it. `Admin`, `Operator`, or both.                  |
| `summary`    | No       | One line under the title.                                      |
| `sort_order` | No       | Lower numbers appear first.                                    |
| `is_faq`     | No       | `true` puts it in the FAQ group.                               |

An unknown role stops the load with an error rather than quietly hiding the
article. That is deliberate — a typo in `roles` should be loud, not invisible. An
article body cannot be empty either.

A restricted article returns 404 rather than 403, so the response cannot confirm
that an article the reader is not allowed to see exists at all.

### Links in articles are not file paths

This is the thing that trips people up. Both kinds of link below are resolved by
the running app, not by the filesystem:

```markdown
See [Managing cameras](managing-cameras) for the full walkthrough.

![The Add Camera dialog](/help/add-camera-modal.png)
```

- A link with no `http://` or `https://` in front of it is treated as an **article
  slug** and navigates inside the Help Center.
- An image path starting with `/help/` is served by the frontend from
  `frontend/public/help/`.

Neither points at a file on disk next to the article, so your editor — and any link
checker run over the repository — will report every one of them as broken. They are
not. **Do not convert them to relative paths**; that breaks the app.

### Adding a screenshot

Put the PNG in `frontend/public/help/`, then reference it as `/help/<name>.png`.
The two directories move together; a screenshot added on one side and not the other
shows up as a missing image in the app.

### Writing style

Article bodies render through `react-markdown` with `rehype-sanitize`, which strips
anything outside its allowlist. Headings, lists, tables, bold, links and images all
work. Raw HTML does not — write Markdown.

Keep the wording plain. The audience is an operator on shift, not a developer.
