---
slug: faq-what-does-precision-score-mean
title: What does precision score mean?
category: FAQ
roles: [Admin]
summary: The share of confirmed alerts that were real accidents rather than false positives.
sort_order: 60
is_faq: true
---

![The AI Performance page's Avg Precision Score, alongside confidence and
per-camera figures](/help/ai-performance.png)

Precision is confirmed accidents divided by (confirmed accidents + dismissed alerts):
in other words, out of everything an operator made a call on, how much of it was a real
accident. It shows as unavailable rather than 0% when there's no data yet for the
current filter, since that's different from the system having gotten everything wrong.

Precision isn't the same as the AI's confidence score for any single detection.
Confidence is what the AI thought at the moment it flagged something; precision is a
historical accuracy rate built from what operators actually decided afterward. See
[Understanding AI Performance Metrics](understanding-ai-performance-metrics) for both
numbers in full, including the per-camera breakdown.
