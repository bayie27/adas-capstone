---
slug: understanding-ai-performance-metrics
title: Understanding AI Performance Metrics
category: Monitoring
roles: [Admin]
summary: What precision score and confidence mean on the AI Performance page.
sort_order: 30
is_faq: false
---

![The AI Performance page, with system-wide stat cards above a per-camera
breakdown table](/help/ai-performance.png)

## The headline numbers

At the top of the page:

- **Total Accidents**: how many alerts have been confirmed as real, for the current
  date range and camera filter.
- **Total Dismissed**: how many were dismissed as false positives over the same
  filter.
- **Avg Precision Score**: see below.
- **Avg Accident Confidence**: the AI's average certainty score on the alerts that
  turned out to be real.
- **Avg Dismissed Score**: the AI's average certainty score on the alerts that turned
  out to be false positives.

## Precision score

Precision measures how often a confirmed accident really was one:

```
precision = confirmed accidents / (confirmed accidents + dismissed alerts)
```

In other words, out of everything an operator actually made a call on, what share was a
real accident. Ongoing and Unverified alerts aren't in this calculation at all: only
alerts that have actually been confirmed or dismissed count, since precision is
measuring the model's accuracy against human judgment, not against alerts no one has
weighed in on yet.

If there's no data yet for the current filter (no confirmed accidents and no
dismissals), precision shows as unavailable rather than 0%, since 0% would incorrectly
suggest the system got everything wrong, when really it just hasn't seen anything yet.
A low precision score doesn't necessarily mean something is broken, either. See
[Dismissing a False Positive](dismissing-a-false-positive) for why a meaningful share of
false positives is expected by design.

## Confidence

Confidence is the AI's own certainty score for a detection, averaged separately for
confirmed accidents and for dismissed (false-positive) alerts. A healthy system usually
shows higher average confidence on confirmed accidents than on dismissed ones, a gap
that's a sign the model's certainty actually tracks with reality. If the two numbers
are close together, or reversed, that's worth flagging to whoever administers the AI
model, since it suggests the confidence score isn't a reliable signal for that
camera or time period.

Confidence is not the same thing as precision: confidence is what the AI thought about
a single detection, before anyone acted on it; precision is a historical accuracy rate
built from what operators decided afterward.

## Per-camera breakdown

Below the headline numbers, the same metrics (accidents, dismissed, precision score,
confidence score, and dismissed score) are broken down per camera, sorted by how
active each camera has been. Use this to spot a specific camera that's underperforming
rather than only seeing the system-wide average: a camera with a bad angle, poor
lighting, or a partially obstructed view will often show up here as a low-precision
outlier well before anyone notices a pattern by hand.

A camera with no acted-on alerts yet in the current filter shows N/A for its
precision, confidence, and dismissed scores rather than a misleading 0% or blank,
the same "no data yet" reasoning as the headline precision figure.

## Filtering the view

Like the incident list, this page respects a date range and camera filter, and its own
Export button downloads the current view. Narrow the range or the camera before
exporting if you want a report for just one location or period. See [Exporting Incident
History to CSV](exporting-incident-history-to-csv) for how exports work generally.
