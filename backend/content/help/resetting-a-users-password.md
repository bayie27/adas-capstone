---
slug: resetting-a-users-password
title: Resetting a User's Password
category: Administration
roles: [Admin]
summary: Force-resetting another account's password when they've been locked out.
sort_order: 20
is_faq: false
---

## When to use this

Use a password reset when a user can't sign in and needs a new password set for them,
rather than changing it themselves from their own profile.

## What happens

- The account's password is replaced with the one you set.
- Every session that account currently has open is signed out — they'll need to log in
  again with the new password on every device.
