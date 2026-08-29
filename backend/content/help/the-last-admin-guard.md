---
slug: the-last-admin-guard
title: The Last-Admin Guard
category: Administration
roles: [Admin]
summary: Why the system won't let you remove the only remaining Administrator.
sort_order: 30
is_faq: false
---

![The User Management list, showing more than one active Administrator
account](/help/users-list.png)

## What it protects against

The system always keeps at least one active Administrator account. Losing every admin
would mean no one left could create accounts, reset a locked-out user's password, read
the audit trail, or restore a backup. The system would still run, but no one could
manage it. The last-admin guard exists to make that state impossible to reach by
accident.

If an account is the last active admin, it's blocked from being:

- **Demoted to Operator**: the role change is rejected outright.
- **Deactivated**: the account can't be disabled while it's the only one left.
- **Deleted**: the account can't be removed while it's the only one left.

Try any of these on the last admin and you'll get an error explaining why, rather than
the action silently failing or partially applying.

## The guard only cares about the count, not who's asking

The guard checks how many active Administrator accounts exist, full stop. It doesn't
matter which admin is attempting the demote/deactivate/delete, or whether they're
acting on their own account or someone else's. As soon as a second active admin exists,
none of these actions are blocked by this particular rule anymore for either account.

## Separately: no admin can delete their own account

This is a different rule from the last-admin guard, and it applies even when other
admins exist: no admin can ever delete their **own** account through the user list.
Deleting yourself always has to be done by someone else. Two admins can each freely
delete the _other's_ account (assuming neither is the last one standing), but neither
can delete their own.

## If you need to step down as an Administrator

If you need to remove yourself as an admin, make sure at least one other active
Administrator exists first, then have that admin either demote or remove your account.
You can't do either of those to yourself. If you're the only admin and need to hand
off the role, create a new Administrator account (or promote an existing Operator)
before doing anything to your own.
