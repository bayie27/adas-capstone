---
slug: the-accident-alert-popup-and-the-alarm
title: The Accident Alert Popup and the Alarm
category: Operations
roles: [Admin, Operator]
summary: What the full-screen alert looks like, why you can't dismiss it by closing the window, and what the snooze button actually does.
sort_order: 5
is_faq: false
---

![The full-screen accident alert panel showing the snapshot, timestamp,
camera name, and confidence score, with Dismiss and Confirm buttons and an
"Alert 1 of 3" queue indicator](/help/accident-alert-popup.png)

## What happens when the AI detects a possible accident

A red "ACCIDENT DETECTED" panel takes over the screen, showing the camera's name, the
timestamp, the snapshot, and the AI's confidence score. An alarm sound plays and keeps
looping until the alert is handled. The snapshot is the actual frame the AI flagged —
look at it closely before deciding, since it's the main evidence you have for the call
you're about to make.

This popup is deliberately hard to get rid of:

- There is no X button, and clicking outside the panel does nothing.
- Pressing Escape does nothing.

The only ways to make it go away are to **Confirm Accident** or **Dismiss Accident** —
see [Confirming an Accident Alert](confirming-an-accident-alert) and [Dismissing a False
Positive](dismissing-a-false-positive) for what each one does. This is by design: a real
accident should never be closed out of view by an accidental click.

## The snooze button

The bell icon in the top-right of the panel snoozes the **alarm sound only** — it does
not confirm or dismiss anything. Use it if you need a moment of quiet to look at the
snapshot before deciding. Once you snooze, the button becomes disabled and shows a
"snoozed" icon until the snooze period runs out on its own; there's no way to cancel a
snooze early. How long a snooze lasts is set on your own Profile page — see [Choosing
Your Alarm Sound and Volume](choosing-your-alarm-sound-and-volume).

Snoozing is per alert and per browser tab. If the same alert is still Unverified after
the snooze period ends, the alarm resumes.

## When more than one alert is queued

If multiple cameras raise alerts at the same time, the panel shows "Alert 1 of 3" (for
example) with left/right arrows — or your keyboard's ←/→ keys — to browse between them.
Browsing between queued alerts does not silence the alarm and does not count as
snoozing; only the snooze button does that. Confirming or dismissing the alert you're
currently viewing removes it from the queue and moves you to the next one.

## If someone else already handled it

If a colleague confirms or dismisses the same alert a moment before you do, your action
is rejected and a short notice tells you who acted and what they did — see [What Happens
if Another Operator Already Acted?](faq-what-happens-if-another-operator-already-acted).

## If you don't respond right away

The popup and its alarm don't time out — see [What Happens if I Don't Respond to an
Alert?](faq-what-happens-if-i-dont-respond-to-an-alert). Nothing auto-resolves in your
absence, which is exactly why the alarm keeps looping rather than playing once and going
quiet.
