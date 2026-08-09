---
slug: the-last-admin-guard
title: The Last-Admin Guard
category: Administration
roles: [Admin]
summary: Why the system won't let you remove the only remaining Administrator.
sort_order: 30
is_faq: false
---

## What it protects against

The system always keeps at least one active Administrator account. If an account is the
last active admin, it's blocked from being:

- Demoted to Operator.
- Deactivated.
- Deleted.

Separately, no admin can ever delete their **own** account through the user list, even
when other admins exist — deleting yourself always has to be done by someone else.

If you need to remove yourself as an admin, make sure at least one other active
Administrator exists, then have that admin remove your account.
