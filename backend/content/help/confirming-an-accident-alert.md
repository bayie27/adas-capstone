---
slug: confirming-an-accident-alert
title: Confirming an Accident Alert
category: Operations
roles: [Admin, Operator]
summary: What confirming does, when you can do it, and what happens right after.
sort_order: 10
is_faq: false
---

![The full-screen accident alert with the snapshot, timestamp, camera name, and
confidence score, alongside Dismiss and Confirm buttons](/help/accident-alert-popup.png)

## When you can confirm

An alert can be confirmed only while it is **Unverified** — the status it arrives in the
moment the AI detects a possible accident. Unverified is the only status the Confirm
button appears on; once someone else has already acted on the same alert, your own
click is rejected and nothing on your screen changes except a short notice telling you
what happened and who acted first.

## What to check first

Open the alert and look at the snapshot and confidence score before deciding. A higher
confidence score is not automatically a real accident, and a lower one is not
automatically a false alarm — it's the AI's own certainty about what it saw, not a
verdict. Use it as one input alongside the snapshot itself:

- Does the snapshot actually show a collision, or something that could be mistaken for
  one — a stopped vehicle, a shadow, headlight glare, debris in the road?
- Does the camera name and timestamp match what you'd expect for that location and time
  of day?
- If you're genuinely unsure and want a moment before deciding, use the alarm's snooze
  button rather than guessing — see [The Accident Alert Popup and the
  Alarm](the-accident-alert-popup-and-the-alarm).

There's no penalty for taking an extra few seconds to look closely. There is a
consequence for confirming the wrong thing: a real accident sitting in Ongoing when it
should have been dismissed, or vice versa, is corrected differently depending on which
way the mistake went — see [Correcting a Mistaken
Confirmation](correcting-a-mistaken-confirmation) if you confirm something and later
realize it wasn't real.

## What happens after you confirm

- The alert moves to **Ongoing**.
- You are recorded as the operator who verified it, and that record doesn't change even
  if someone else later resolves or corrects the incident.
- The camera that reported it stays paused — it does not resume AI detection while the
  incident is open. This is intentional: the system doesn't want a second, overlapping
  alert from the same camera for the same event while it's already being handled. See
  [Getting Started with ADAS](getting-started-with-adas) for why cameras pause at all.
- The incident also appears in the floating **ONGOING** tray that follows you around the
  app, so you (and any other operator) can find it again later without hunting through
  the full incident history — see [Reviewing Ongoing Incidents in the
  Tray](reviewing-ongoing-incidents-in-the-tray).

From **Ongoing**, the alert can later be resolved (scene cleared — see [Resolving an
Ongoing Incident](resolving-an-ongoing-incident)) or, if confirming it turns out to have
been a mistake, dismissed as a correction (see [Correcting a Mistaken
Confirmation](correcting-a-mistaken-confirmation)).
