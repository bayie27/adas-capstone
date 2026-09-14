---
slug: operator-vs-administrator-roles
title: "Operator vs. Administrator: What Each Role Can Do"
category: Getting Started
roles: [Admin, Operator]
summary: A side-by-side look at what each account type can see and do.
sort_order: 30
is_faq: false
---

## The short version

An Administrator can do everything an Operator can, plus a set of account- and
system-level tasks that Operators don't need for day-to-day monitoring. There is no
partial or custom role — every account is exactly one or the other, chosen when it's
created.

## What every account can do

- Confirm or dismiss an accident alert. See [Confirming an Accident Alert](confirming-an-accident-alert)
  and [Dismissing a False Positive](dismissing-a-false-positive).
- Clear an ongoing incident once it's resolved. See [Clearing an Ongoing
  Incident](clearing-an-ongoing-incident).
- Correct a mistaken confirmation. See [Correcting a Mistaken
  Confirmation](correcting-a-mistaken-confirmation).
- View and filter incident history, and export it to CSV. See [Viewing and Filtering
  Incidents](viewing-and-filtering-incidents) and [Exporting Incident History to
  CSV](exporting-incident-history-to-csv).
- View camera details and register or disable cameras. See [Viewing Camera
  Details](viewing-camera-details) and [Adding, Editing, and Disabling
  Cameras](managing-cameras).
- Check System Health and read the Dashboard KPIs.
- Update their own profile, password, and alarm sound.

## What only an Administrator can do

- Create user accounts and assign roles, or edit an existing account.
- Reset another user's password.
- Read the audit trail: a record of every recorded action in the system, by whom. See
  [Who Can See the Audit Trail?](faq-who-can-see-the-audit-trail).
- Review AI performance metrics: precision, accuracy, and per-camera trends.
- Back up or restore the system's database.

Each of these has its own Administrator-only Help Center guide. They're intentionally
not linked from here: an Operator account can't open them, so a link would just be a
dead end. Signing in as an Administrator surfaces those guides directly in the Help
Center's Administration category.

## Why the split exists

Most of what's Administrator-only is either irreversible (restoring a database),
identity-sensitive (creating accounts, resetting passwords), or accountability-related
(the audit trail). Keeping those separate from day-to-day monitoring means an
Operator's account can't be used, by mistake or otherwise, to quietly change who has
access to what. The system also refuses to leave itself with zero Administrators — one
specific protection built on top of this split, covered in the Administrator-only
guides.

## Changing someone's role

A role isn't permanent. An Administrator can change any account between Operator and
Administrator from the Users page at any time.
