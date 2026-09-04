---
slug: clearing-an-ongoing-incident
title: Clearing an Ongoing Incident
category: Operations
roles: [Admin, Operator]
summary: Closing out a confirmed accident once the scene has been cleared.
sort_order: 40
is_faq: false
---

![The incident detail view for an Ongoing incident, with Dismiss and Cleared
actions](/help/incident-detail-modal.png)

## When to use this

Clear an alert once it is **Ongoing** and the situation has actually been dealt with:
the scene is cleared, emergency response has concluded, or the incident is otherwise
over. This is the normal, expected ending for a real accident: confirm it, deal with
it, then clear it once it's actually finished. Don't clear an incident early just to
clear it out of the tray. See [Reviewing Ongoing Incidents in the
Tray](reviewing-ongoing-incidents-in-the-tray) if the tray itself is what's bothering
you, not the incident.

## What happens after you clear it

- The alert moves to **Cleared**, a final state. It cannot be reopened, edited, or
  moved back to Ongoing. See [Can I Undo a Confirmed or Cleared
  Incident?](faq-can-i-undo-a-confirmed-or-cleared-incident).
- You are recorded as the operator who closed it; the original verifier is unchanged,
  so the incident's history still shows both who confirmed it and who cleared it, even
  when that's two different people.
- The camera resumes AI detection immediately. There's no cooldown here, unlike a
  dismissed false positive, because a cleared incident was a real, already-confirmed
  event rather than something that might immediately misfire again.

Cleared and Dismissed alerts both stay visible in your incident history. Clearing
doesn't delete anything; it just marks the incident as finished. You can still find it
later with a search or filter (see [Viewing and Filtering
Incidents](viewing-and-filtering-incidents)), and it still counts toward the dashboard's
**Total Cleared** figure and the AI performance metrics for that camera.

## If you clear the wrong incident

Cleared is final, so double-check you're looking at the right accident number and
camera before closing it out, especially if more than one incident is open at once. If
you clear an incident that actually needed correcting instead (it wasn't a real
accident after all), there's no way back from Cleared. That mistake can only be
noted, not undone, through the normal incident actions. An Administrator can see exactly
what happened afterward in the audit trail if it needs explaining. See [Reading the
Audit Trail](reading-the-audit-trail).
