---
slug: viewing-camera-details
title: Viewing Camera Details
category: Monitoring
roles: [Admin, Operator]
summary: What you see when you click into a single camera, and what each field means.
sort_order: 22
is_faq: false
---

## Opening the detail panel

Clicking a camera in the Cameras list opens a side panel with more detail than the list
shows, refreshed the moment you open it so it's never stale.

## Identity

Shows the camera's name and channel number, plus its stream address in a masked form
like `rtsp://***:***@host:port/path` — the real address and any credentials are never
sent to the browser. Operators see a badge reading "Admin only" here instead; only
Administrators can view (and, with a click, reveal) the masked address, and even then
there's nothing usable to connect with — it's for identifying which physical feed a
camera points at, not for retrieving a working connection string.

## State

- **Connection** and **AI detection** — the same two independent statuses described in
  [Camera Connection Status vs. AI Status](camera-connection-vs-ai-status).
- **Cooldown** — if the camera is in the short pause after a dismissed false positive,
  this counts down the seconds remaining before detection resumes automatically.

## Convergence

Two version numbers: the configuration the backend currently wants this camera to run
("Desired") and the configuration the camera last confirmed it's actually running
("Applied"). These normally match within a few seconds of any change. If they disagree
for longer than that, it's a sign the camera hasn't picked up a recent change yet —
useful evidence if you need to report that a toggle doesn't seem to be taking effect.

## Engine telemetry

- **Last heartbeat** — the last time this camera's AI engine checked in. Flagged "Stale"
  if it's overdue.
- **Measured FPS** — how many frames per second the engine is actually processing,
  shown in green when it's within the expected range and amber when it's outside it.
- **Inference latency** — how long the AI model takes to process each frame.
- **Last error code** — the most recent problem the engine reported for this camera, if
  any, with a plain-language message underneath.

Together, these tell apart a camera with a real problem (an error code, but a recent
heartbeat) from one whose AI engine has stopped responding entirely (a stale heartbeat,
no error code).
