---
slug: faq-what-happens-if-another-operator-already-acted
title: What happens if another operator already acted on the same alert?
category: FAQ
roles: [Admin, Operator]
summary: Your action is rejected with an error rather than silently applied on top.
sort_order: 30
is_faq: true
---

You'll get an error explaining the alert is no longer in the status your action expects,
and nothing changes on your end. Only the operator who acted first has their action
applied — a second confirm, dismiss, or resolve on the same alert never goes through
silently.
