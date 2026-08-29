---
slug: correcting-a-mistaken-confirmation
title: Correcting a Mistaken Confirmation
category: Operations
roles: [Admin, Operator]
summary: What to do when an Ongoing alert turns out not to have been a real accident.
sort_order: 30
is_faq: false
---

![The incident detail view for an Ongoing incident, with Dismiss and Resolve
actions](/help/incident-detail-modal.png)

## When to use this

Sometimes an alert is confirmed (moved to **Ongoing**) and it later becomes clear it
wasn't actually an accident — a closer look at the snapshot, a report from someone on
the scene, or simply a second opinion that changes the read. Dismiss it from **Ongoing**
to correct that, using the same **Dismiss Accident** action on the incident's detail
view.

This is different from the everyday false-positive path: that one dismisses an alert
that's still **Unverified**, before anyone confirmed it. This one dismisses an alert
that a person already vouched for. Both end at Dismissed, but they say different things
about what happened — see [Dismissing a False Positive](dismissing-a-false-positive) for
the other path.

## What happens after you correct it

- The alert moves to **Dismissed**, a final state. It cannot be reopened, edited, or
  restored, regardless of who dismisses it or why — see [Can I Undo a Confirmed or
  Resolved Incident?](faq-can-i-undo-a-confirmed-or-resolved-incident).
- The original operator who confirmed it stays on the record as the verifier; you are
  recorded as the operator who closed it. Both names remain visible on the incident
  afterward — correcting a confirmation doesn't erase who made the original call, since
  the point of the record is to reflect what actually happened, not to flatter anyone.
- Unlike dismissing a fresh **Unverified** alert, there is no cooldown here — the camera
  resumes AI detection immediately, since it was already known to be a false alarm and
  there's no risk of it re-triggering on the same non-event a moment later.

## Why this isn't the same as an undo

Correcting a confirmation doesn't put the alert back the way it was before anyone
touched it — it moves forward to a new, final state (Dismissed) rather than reversing
time to Unverified. That distinction matters for the audit trail: an Administrator
looking back later sees exactly what happened — confirmed, then corrected — rather than
a record that looks like nothing occurred. See [Reading the Audit
Trail](reading-the-audit-trail) if you need to explain a correction after the fact.

If the incident had already been resolved (scene cleared) rather than corrected while
still Ongoing, it's too late for this path — Resolved is also final. See [Resolving an
Ongoing Incident](resolving-an-ongoing-incident) for that state instead.
