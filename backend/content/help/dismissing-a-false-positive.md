---
slug: dismissing-a-false-positive
title: Dismissing a False Positive
category: Operations
roles: [Admin, Operator]
summary: Dismissing an alert that never confirmed as a real accident, and the cooldown that follows.
sort_order: 20
is_faq: false
---

## When to use this

Dismiss an alert while it is still **Unverified** when you can see it was not actually an
accident — a false trigger, an empty road, a shadow the model misread.

## What happens after you dismiss

- The alert moves to **Dismissed**, a final state. It cannot be reopened.
- You are recorded as the operator who closed it.
- The camera stays paused for a short cooldown period (about 60 seconds) before AI
  detection resumes automatically on that camera. You don't need to do anything to
  resume it — it comes back on its own once the cooldown ends.

If you need to dismiss an alert that was already confirmed by mistake, that's a
correction rather than a false-positive dismissal — see
[Correcting a Mistaken Confirmation](correcting-a-mistaken-confirmation).
