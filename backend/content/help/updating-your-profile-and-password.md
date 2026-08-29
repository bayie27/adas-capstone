---
slug: updating-your-profile-and-password
title: Updating Your Profile and Password
category: Operations
roles: [Admin, Operator]
summary: Changing your own name, username, or password.
sort_order: 80
is_faq: false
---

![The Edit Personal Information dialog, with fields for first name, last name, and
username](/help/edit-profile-modal.png)

## Your profile

Your Profile page shows your name, username, role, account status, when your account
was created, and when you last logged in. Most of that is read-only — your role and
account status are set by an Administrator, not by you — but you can update your own
username, first name, or last name at any time by opening **Edit** next to Personal
Information.

Changing your username changes what you type to log in from now on, but it doesn't
retroactively change your name on past incidents or audit rows — those keep showing
whatever name was current at the time the action happened.

## Changing your password

![The Change Password dialog, asking for your current password and a new one
twice](/help/change-password-modal.png)

Open **Change Password** from the same page. You'll need to enter your current
password along with the new one, typed twice to confirm it. The new password needs to
be at least 8 characters long and contain at least one number — the same requirement
that applies when an account is first created or reset.

You can't change your password to something you can't confirm, since a typo in either
new-password field is caught before it's saved — much better than discovering a typo
only after you're locked out.

## What happens after you change it

Once it's changed, every device you're logged in on is signed out, including the one
you just used — you'll need to log back in with the new password. This is intentional,
not a bug: see [Why Do I Need to Log In Again After Changing My
Password?](faq-why-log-in-again-after-password-change) for why a password change always
does this, whether you initiated it yourself here or an Administrator reset it for you.

## If you've forgotten your current password

This self-service flow needs your current password, so it doesn't help if you've
actually forgotten it — there's no "forgot password" link on this page. In that case,
an Administrator needs to reset your password for you instead; see [Resetting a User's
Password](resetting-a-users-password). Talk to an Administrator directly, since the
system has no way to email or otherwise contact you automatically.
