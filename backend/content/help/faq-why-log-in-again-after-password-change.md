---
slug: faq-why-log-in-again-after-password-change
title: Why do I need to log in again after changing my password?
category: FAQ
roles: [Admin, Operator]
summary: Changing your password signs out every device, including the current one, for security.
sort_order: 50
is_faq: true
---

![The Change Password dialog: saving this signs out every device you're logged in
on](/help/change-password-modal.png)

Changing your password signs out every session on every device you're logged in on,
including the one you just used to change it. This is intentional: it makes sure a
password change actually invalidates anything relying on the old one, rather than
leaving an old, still-valid session running somewhere you've forgotten about. Just log
back in with your new password.

This applies the same way whether you changed it yourself from your Profile page (see
[Updating Your Profile and Password](updating-your-profile-and-password)) or an
Administrator reset it for you after a lockout (see [Resetting a User's
Password](resetting-a-users-password)). Either path ends the same way: a fresh password,
and a fresh login required everywhere.
