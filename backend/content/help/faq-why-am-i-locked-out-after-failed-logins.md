---
slug: faq-why-am-i-locked-out-after-failed-logins
title: Why am I temporarily locked out after failed logins?
category: FAQ
roles: [Admin, Operator]
summary: Too many wrong password attempts triggers a short, timed lockout shown as a countdown.
sort_order: 90
is_faq: true
---

![The login page after too many failed attempts, showing a countdown before you can try
again](/help/login-lockout.png)

After several incorrect password or authenticator attempts, the system briefly blocks
further attempts and shows a countdown timer on the login page, along with a message
that reads "Too many login attempts. Please try again later." This is a security
measure against repeated guessing, not a sign your account has been disabled. Wait for
the countdown; changing the input or restarting sign-in does not clear an authenticator
limit. If you just used a valid code, wait for the next code before trying again.

Double-check your username and password (and Caps Lock) before trying again to avoid
triggering it a second time. If you've genuinely forgotten your password rather than
mistyped it, waiting out the countdown just to fail again won't help. Ask an
Administrator to reset the password; that does not reset an authenticator. See
[Resetting a User's Password](resetting-a-users-password) and [Setting Up Your
Authenticator and Recovery Codes](managing-your-authenticator-and-recovery) for the
separate MFA recovery rules.
