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

The audit trail is visible to Administrators only.

## What's recorded

Actions that change something: logins and logouts, incident confirm/dismiss/resolve,
camera create/update/enable/disable/delete, and user create/update/role-change/
password-reset/enable/disable. Each row records who did it, what they did, what it was
done to, whether it succeeded or was denied, and when.

Routine viewing — like opening the audit trail itself — is not recorded, since that
would just add noise about people looking at logs.

## Filtering

You can filter by action, by which user performed it, by whether it succeeded or was
denied, by date range, and by a free-text search.
