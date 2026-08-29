---
slug: resolving-an-ongoing-incident
title: Resolving an Ongoing Incident
category: Operations
roles: [Admin, Operator]
summary: Closing out a confirmed accident once the scene has been cleared.
sort_order: 40
is_faq: false
---

![The incident detail view for an Ongoing incident, with Dismiss and Resolve
actions](/help/incident-detail-modal.png)

## When to use this

Resolve an alert once it is **Ongoing** and the situation has actually been dealt with —
the scene is cleared, emergency response has concluded, or the incident is otherwise
over. This is the normal, expected ending for a real accident: confirm it, deal with
it, then resolve it once it's actually finished. Don't resolve an incident early just to
clear it out of the tray — see [Reviewing Ongoing Incidents in the
Tray](reviewing-ongoing-incidents-in-the-tray) if the tray itself is what's bothering
you, not the incident.

## What happens after you resolve it

- The alert moves to **Resolved**, a final state. It cannot be reopened, edited, or
  moved back to Ongoing — see [Can I Undo a Confirmed or Resolved
  Incident?](faq-can-i-undo-a-confirmed-or-resolved-incident).
- You are recorded as the operator who closed it; the original verifier is unchanged,
  so the incident's history still shows both who confirmed it and who resolved it, even
  when that's two different people.
- The camera resumes AI detection immediately — there's no cooldown here, unlike a
  dismissed false positive, because a resolved incident was a real, already-confirmed
  event rather than something that might immediately misfire again.

Resolved and Dismissed alerts both stay visible in your incident history — resolving
doesn't delete anything, it just marks the incident as finished. You can still find it
later with a search or filter — see [Viewing and Filtering
Incidents](viewing-and-filtering-incidents) — and it still counts toward the dashboard's
**Total Resolved** figure and the AI performance metrics for that camera.

## If you resolve the wrong incident

Resolved is final, so double-check you're looking at the right accident number and
camera before closing it out, especially if more than one incident is open at once. If
you resolve an incident that actually needed correcting instead (it wasn't a real
accident after all), there's no way back from Resolved — that mistake can only be
noted, not undone, through the normal incident actions. An Administrator can see exactly
what happened afterward in the audit trail if it needs explaining — see [Reading the
Audit Trail](reading-the-audit-trail).
