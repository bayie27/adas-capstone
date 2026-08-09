---
slug: correcting-a-mistaken-confirmation
title: Correcting a Mistaken Confirmation
category: Operations
roles: [Admin, Operator]
summary: What to do when an Ongoing alert turns out not to have been a real accident.
sort_order: 30
is_faq: false
---

## When to use this

Sometimes an alert is confirmed (moved to **Ongoing**) and it later becomes clear it
wasn't actually an accident. Dismiss it from **Ongoing** to correct that.

## What happens after you correct it

- The alert moves to **Dismissed**, a final state. It cannot be reopened.
- The original operator who confirmed it stays on the record as the verifier; you are
  recorded as the operator who closed it.
- Unlike dismissing a fresh **Unverified** alert, there is no cooldown here — the camera
  resumes AI detection immediately, since it was already known to be a false alarm.
