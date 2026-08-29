---
slug: creating-a-user-and-assigning-a-role
title: Creating a User and Assigning a Role
category: Administration
roles: [Admin]
summary: Adding a new account and choosing between Admin and Operator.
sort_order: 10
is_faq: false
---

![The Add User dialog with a Role choice, name fields, username, and
password entry](/help/create-user-modal.png)

## Creating an account

Open **Add User** from the Users page. A new account needs a unique username, a first
and last name, a role, and an initial password. Only Administrators can create
accounts.

As you type the first and last name, the username field suggests one automatically (for
example, "John Doe" suggests "jdoe") — you can accept it or type your own, as long as
it's unique among active accounts. The initial password needs to be at least 8
characters long and contain at least one number, the same requirement that applies
everywhere else a password is set in this system.

## Choosing a role

- **Operator** — day-to-day incident handling: confirming, dismissing, and resolving
  alerts, and managing cameras.
- **Admin** — everything an Operator can do, plus user management and the audit trail.

Administrators automatically get everything Operators can do — there's no need to grant
both, and there's no way to grant an Operator only _some_ of the Administrator
capabilities. Role is a single either/or choice at account creation, though it can be
changed later by editing the account (see below).

Think about what the person will actually be doing before defaulting to Administrator
"just in case" — the audit trail and user management aren't needed for most day-to-day
monitoring work, and giving out Administrator access more widely than necessary makes
the [last-admin guard](the-last-admin-guard) and the audit trail itself less useful as
a record of who's actually responsible for account-level changes.

## Editing an existing account

Once created, an account's name, username, and role can all still be changed from the
same Users page — creating an account isn't a one-time, unchangeable choice. Changing
someone's role between Operator and Administrator takes effect the next time their
permissions are checked; they don't need to log out and back in for a promotion or
demotion to apply, though a demoted Administrator does lose access to Administrator-only
pages immediately.

Resetting a user's password is a separate action from editing their name or role — see
[Resetting a User's Password](resetting-a-users-password).
