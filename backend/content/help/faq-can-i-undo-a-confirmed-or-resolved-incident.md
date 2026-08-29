---
slug: faq-can-i-undo-a-confirmed-or-resolved-incident
title: Can I undo a confirmed or resolved incident?
category: FAQ
roles: [Admin, Operator]
summary: No — Dismissed and Resolved are final. Ongoing can still be dismissed as a correction.
sort_order: 20
is_faq: true
---

![The incident list showing Dismissed and Resolved rows — both are end
states](/help/detections-filters.png)

No. **Dismissed** and **Resolved** are both final states — there's no reopen, edit, or
undo action for either one, no matter who's asking or how soon after the mistake you
notice it. If an alert is still **Ongoing**, you can dismiss it as a correction (see
[Correcting a Mistaken Confirmation](correcting-a-mistaken-confirmation)), but once it
reaches Dismissed or Resolved, that record is permanent and stays exactly as it is in
your incident history from then on.

This is deliberate: the incident history and audit trail are meant to reflect what
actually happened and what decisions were actually made, not a version that's been
cleaned up afterward. If a final decision turns out to have been wrong, that's a fact
worth knowing, not something to quietly erase.
