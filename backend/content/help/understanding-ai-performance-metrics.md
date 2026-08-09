---
slug: understanding-ai-performance-metrics
title: Understanding AI Performance Metrics
category: Monitoring
roles: [Admin, Operator]
summary: What precision score and confidence mean on the AI Performance page.
sort_order: 30
is_faq: false
---

## Precision score

Precision measures how often a confirmed accident really was one:

```
precision = confirmed accidents / (confirmed accidents + dismissed alerts)
```

If there's no data yet for the current filter (no confirmed accidents and no dismissals),
precision shows as unavailable rather than 0% — 0% would incorrectly suggest the system
got everything wrong, when really it just hasn't seen anything yet.

## Confidence

Confidence is the AI's own certainty score for a detection, averaged separately for
confirmed accidents and for dismissed (false-positive) alerts. A healthy system usually
shows higher average confidence on confirmed accidents than on dismissed ones.

## Per-camera breakdown

The same metrics are also broken down per camera, sorted by how active each camera has
been, so you can spot a specific camera that's underperforming rather than only seeing
the system-wide average.
