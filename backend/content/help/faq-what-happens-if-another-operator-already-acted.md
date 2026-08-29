---
slug: faq-what-happens-if-another-operator-already-acted
title: What happens if another operator already acted on the same alert?
category: FAQ
roles: [Admin, Operator]
summary: Your action is rejected with an error rather than silently applied on top.
sort_order: 30
is_faq: true
---

![An incident's detail view — only the operator who acts first has their action
applied](/help/incident-detail-modal.png)

You'll get an error explaining the alert is no longer in the status your action
expects, and nothing changes on your end. Only the operator who acted first has their
action applied — a second confirm, dismiss, or resolve on the same alert never goes
through silently on top of the first one.

This matters most when several operators are watching the same alert queue on a busy
shift: two people can both open the same alert, but only the first click actually does
anything. See [The Accident Alert Popup and the Alarm](the-accident-alert-popup-and-the-alarm)
for how this plays out specifically when it's the full-screen alert popup rather than an
incident already sitting in Ongoing.
