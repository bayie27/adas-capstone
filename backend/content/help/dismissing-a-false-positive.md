---
slug: dismissing-a-false-positive
title: Dismissing a False Positive
category: Operations
roles: [Admin, Operator]
summary: Dismissing an alert that never confirmed as a real accident, and the cooldown that follows.
sort_order: 20
is_faq: false
---

![The full-screen accident alert with Dismiss and Confirm buttons — Dismiss is what
closes out a false trigger](/help/accident-alert-popup.png)

## When to use this

Dismiss an alert while it is still **Unverified** when you can see it was not actually an
accident — a false trigger, an empty road, a shadow the model misread, glare, or a
vehicle that merely slowed down rather than collided. This is the everyday, expected
outcome for a share of alerts: the AI is deliberately tuned to flag anything that might
be an accident rather than only the ones it's certain about, so seeing false positives
in your queue is normal, not a sign something is broken. See [Understanding AI
Performance Metrics](understanding-ai-performance-metrics) for how that trade-off is
measured.

## What happens after you dismiss

- The alert moves to **Dismissed**, a final state. It cannot be reopened, edited, or
  restored — see [Can I Undo a Confirmed or Resolved
  Incident?](faq-can-i-undo-a-confirmed-or-resolved-incident).
- You are recorded as the operator who closed it.
- The camera stays paused for a short cooldown period (about 60 seconds) before AI
  detection resumes automatically on that camera. You don't need to do anything to
  resume it — it comes back on its own once the cooldown ends. If you open that
  camera's detail panel during the cooldown, you'll see a countdown of the seconds
  remaining — see [Viewing Camera Details](viewing-camera-details).

## Why there's a cooldown at all

The cooldown exists so a single misread frame doesn't turn into a rapid string of
repeat alerts for the same non-event before the camera's view has actually changed.
It's short on purpose — long enough to let a momentary glitch pass, not so long that a
real accident happening moments later on the same camera goes unnoticed.

## If you dismiss the wrong one

If you dismiss an alert that turns out, on reflection, to have actually been a real
accident, there's no way to undo the dismissal — Dismissed is final. The alert would
need to be caught again by a future detection, or handled manually outside the system.
This is a reason to actually look at the snapshot before dismissing rather than
clearing the popup on reflex, especially when several alerts are queued at once — see
[The Accident Alert Popup and the Alarm](the-accident-alert-popup-and-the-alarm) for how
the queue behaves.

If you need to dismiss an alert that was already **confirmed** by mistake, that's a
correction rather than a false-positive dismissal — see [Correcting a Mistaken
Confirmation](correcting-a-mistaken-confirmation).
