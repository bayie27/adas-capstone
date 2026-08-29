---
slug: resetting-a-users-password
title: Resetting a User's Password
category: Administration
roles: [Admin]
summary: Force-resetting another account's password when they've been locked out.
sort_order: 20
is_faq: false
---

![The Change User Password dialog, with a warning that resetting signs the user out of
every active session](/help/reset-password-modal.png)

## When to use this

Use a password reset when a user can't sign in and needs a new password set for them,
rather than changing it themselves from their own profile: a forgotten password, a
locked-out account after too many failed attempts (see [Why Am I Locked Out After
Failed Logins?](faq-why-am-i-locked-out-after-failed-logins)), or an account you're
handing back to someone after it was temporarily deactivated.

This is a different action from what a person does for themselves on their own Profile
page. See [Updating Your Profile and Password](updating-your-profile-and-password) for
that self-service flow, which requires knowing the _current_ password. A reset here
doesn't need the user's old password at all, since the whole point is that they can't
provide it.

## How to do it

From the Users page, open the reset-password action on the account that needs it,
enter the new password twice to confirm it, and save. The new password needs to meet
the same minimum requirements as any account password: at least 8 characters and at
least one number.

## What happens

- The account's password is replaced with the one you set. There's no way to view or
  recover the password afterward. If you don't tell the user what you set, they'll
  need another reset.
- Every session that account currently has open is signed out immediately. They'll
  need to log in again with the new password on every device, not just the one causing
  trouble. This is the same behavior as when a user changes their own password (see
  [Why Do I Need to Log In Again After Changing My Password?](faq-why-log-in-again-after-password-change));
  a reset is just an Administrator triggering that same guarantee on someone else's
  behalf.
- The reset itself is recorded in the audit trail, including which Administrator
  performed it and when. See [Reading the Audit Trail](reading-the-audit-trail).

## After resetting

Tell the user their new password through some channel outside this system. It isn't
emailed or displayed to them automatically. They can change it to something only they
know the moment they log back in, from their own Profile page.
