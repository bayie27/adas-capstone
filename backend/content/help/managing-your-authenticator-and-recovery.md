---
slug: managing-your-authenticator-and-recovery
title: Setting Up Your Authenticator and Recovery Codes
category: Security
roles: [Admin, Operator]
summary: How to enroll, replace or recover an authenticator and keep one-time recovery codes.
sort_order: 25
is_faq: false
---

## Set up your authenticator

After you enter your username and password, follow the setup screen to scan its QR code
with an authenticator app or enter the displayed setup key manually. Enter the current
six-digit code from the app to confirm setup. If the code has just changed or was
already used, wait for the next code before trying again.

Choose an authenticator and storage setting that meet your organization's policy. If
the app offers cloud sync for this entry, turn it off where supported. ADAS cannot
inspect or enforce how an authenticator app stores or syncs its own copy of the setup
key.

## Save your recovery codes

After enrollment, ADAS shows a new batch of one-time recovery codes once. Copy or
download them yourself and keep them in a secure place separate from your phone. The
acknowledgment button confirms that you accept responsibility for saving them; ADAS
does not verify that a copy exists. The batch cannot be displayed again after you leave
or reload the screen.

If you still have access to your account but no longer have the codes, open **Profile**
and rotate the batch with your password and a fresh authenticator code. Rotation
invalidates every code from the previous batch and keeps your current sessions active.

## Replace an authenticator you can still use

From **Profile**, start authenticator replacement with your password and a fresh code
from the current authenticator. Your current authenticator remains active while you set
up the new one. Canceling or letting setup expire leaves the current authenticator in
place. Confirming the replacement switches to the new authenticator, issues a new
recovery-code batch, and signs you out on every device. Save the new codes before
continuing.

## Recover when the authenticator is unavailable

At sign-in, choose a recovery code and enter one unused code. Using it disables the old
authenticator and signs out every session immediately. You must then set up a new
authenticator and confirm one of its codes before you receive a new recovery batch and
regain a normal session.

If recovery setup is interrupted, start again with your password and another unused
recovery code. A code that was already used cannot be used again. If you use your final
recovery code and then lose or let the setup challenge expire before confirming the
new authenticator, no unused code remains to restart recovery.

## If you lose both the authenticator and all recovery codes

ADAS has no in-app or Administrator MFA reset. An Administrator password reset changes
only the password; it does not replace the authenticator or recovery codes. Follow
your organization's separately approved escalation process, if one exists. Do not
share setup keys or recovery codes in messages, screenshots, or support requests.
