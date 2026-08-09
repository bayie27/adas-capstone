---
slug: faq-what-does-precision-score-mean
title: What does precision score mean?
category: FAQ
roles: [Admin, Operator]
summary: The share of confirmed alerts that were real accidents rather than false positives.
sort_order: 60
is_faq: true
---

Precision is confirmed accidents divided by (confirmed accidents + dismissed alerts) —
in other words, out of everything an operator made a call on, how much of it was a real
accident. It shows as unavailable rather than 0% when there's no data yet for the
current filter, since that's different from the system having gotten everything wrong.
