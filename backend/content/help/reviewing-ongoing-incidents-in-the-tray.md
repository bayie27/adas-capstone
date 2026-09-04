---
slug: reviewing-ongoing-incidents-in-the-tray
title: Reviewing Ongoing Incidents in the Tray
category: Operations
roles: [Admin, Operator]
summary: The "ONGOING" button that follows you around the app, and what's behind it.
sort_order: 35
is_faq: false
---

![The Ongoing Incidents side panel, listing each open incident's camera,
detection time, and confidence, with a Review Incident
button](/help/ongoing-incidents-tray.png)

## The ONGOING button

Whenever at least one incident is confirmed and still open, a small "ONGOING" button
with a pulsing dot and a count appears, floating over whichever page you're on. It's
there so you never lose track of a confirmed accident, even while you're working
somewhere else in the app.

Clicking it opens a side panel listing every ongoing incident: its camera, how long ago
it was detected, the AI confidence score, who verified it (or "Confirmed active" if it
hasn't been picked up yet), and a snapshot thumbnail. On a desktop or laptop, hovering
over a thumbnail shows a larger preview next to the panel.

## Reviewing one

Selecting **Review Incident** on a card opens the full incident detail view, where you
can:

- **Clear** it once the scene has been cleared. See [Clearing an Ongoing
  Incident](clearing-an-ongoing-incident).
- **Dismiss** it if confirming it turns out to have been a mistake. See [Correcting a
  Mistaken Confirmation](correcting-a-mistaken-confirmation).

If another operator clears or dismisses the same incident while you have it open, a
notice tells you what happened and the incident disappears from the tray. See [What
Happens if Another Operator Already
Acted?](faq-what-happens-if-another-operator-already-acted).

## Why this exists alongside the dashboard

The dashboard also shows an **Ongoing** count (see [Reading the Dashboard
KPIs](reading-the-dashboard-kpis)), but that's a number on one specific page. The tray
is the same information made available everywhere, so you don't have to navigate back
to the dashboard just to check whether anything confirmed is still waiting on you. Both
always agree with each other, since they're reading the same underlying set of Ongoing
incidents.
