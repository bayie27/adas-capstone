---
slug: reading-the-audit-trail
title: Reading the Audit Trail
category: Administration
roles: [Admin]
summary: What's recorded in the audit log and how to search it.
sort_order: 40
is_faq: false
---

![The Audit Log listing each recorded action with its actor, action type,
target, and result](/help/audit-log.png)

## Who can see it

The audit trail is visible to Administrators only. Operators don't have access to it,
even though many of the rows in it are their own actions. See [Who Can See the Audit
Trail?](faq-who-can-see-the-audit-trail).

## What's recorded

Actions that change something: logins and logouts (including failed login attempts),
incident confirm/dismiss/clear, camera create/update/enable/disable/delete, and user
create/update/role-change/password-reset/enable/disable. Backup and restore actions are
recorded too, attributed to the system itself rather than a person when they run on a
schedule rather than by someone clicking a button.

Each row records who did it (or "system" for an automated action), what they did, what
it was done to, whether it succeeded or was denied, and when. A failed login is
recorded even though the attempted username may not correspond to any real account.
That's deliberate, so a string of failed attempts against a nonexistent or mistyped
username is still visible as a pattern.

Routine viewing, like opening the audit trail itself or looking at a camera's detail
panel, is not recorded, since that would just add noise about people looking at
things rather than changing them.

## Reading the Result column

Every row shows one of three outcomes:

- **Success**: the action went through exactly as requested.
- **Denied**: the action was blocked by a permission or business rule (for example,
  the [last-admin guard](the-last-admin-guard) rejecting a demotion, or an Operator's
  session attempting something restricted to Administrators).
- **Failure**: the action was attempted and allowed, but didn't complete successfully
  for some other reason (for example, an export job or a restore that didn't finish
  cleanly).

Denied and Failure look similar at a glance but mean different things: Denied is the
system correctly refusing something it shouldn't do; Failure is something going wrong
partway through an action it should have been able to do.

## Filtering

You can filter by action, by which user performed it, by whether it succeeded or was
denied, by date range, and by a free-text search. Combine filters to answer a specific
question quickly. For example, filtering to one user and "Denied" results shows every
time that account tried something it wasn't allowed to do, which is often exactly what
you need when investigating a support question or a suspicious pattern.
