---
slug: viewing-camera-details
title: Viewing Camera Details
category: Monitoring
roles: [Admin, Operator]
summary: What you see when you click into a single camera, and what each field means.
sort_order: 22
is_faq: false
---

![The camera detail panel showing Identity, State, Convergence, and Engine
Telemetry sections](/help/camera-detail-panel.png)

## Opening the detail panel

Clicking a camera in the Cameras list opens a side panel with more detail than the list
shows, refreshed the moment you open it so it's never stale. Close it and reopen the
same camera later to see how its state has changed since. Nothing here is cached from
the moment you first looked.

## Identity

Shows the camera's name and channel number, plus its stream address in a masked form
like `rtsp://***:***@host:port/path`. The real address and any credentials are never
sent to the browser. Operators see a badge reading "Admin only" here instead; only
Administrators can view (and, with a click, reveal) the masked address, and even then
there's nothing usable to connect with: it's for identifying which physical feed a
camera points at, not for retrieving a working connection string. A copy icon next to
the field copies the masked form, useful for pasting into a support ticket without
exposing anything sensitive.

## State

- **Connection** and **AI detection**: the same two independent statuses described in
  [Camera Connection Status vs. AI Status](camera-connection-vs-ai-status).
- **Desired state**: what the system currently wants this camera's AI detection to be
  (usually Active), independent of what it's actually managed to become. This is the
  "target" side of the convergence pair described below.
- **Desired state reason**: a short note explaining _why_ the desired state is what it
  is, when it isn't simply "run normally," for example that it's deliberately held
  paused for an open incident, or turned off because someone disabled the camera.
- **Cooldown**: if the camera is in the short pause after a dismissed false positive,
  this counts down the seconds remaining before detection resumes automatically. Shows
  a dash when there's no active cooldown.

## Convergence

Two version numbers: the configuration the backend currently wants this camera to run
("Desired config version") and the configuration the camera last confirmed it's
actually running ("Applied config version"). These normally match within a few seconds
of any change: enabling a camera, disabling it, or any other toggle bumps the desired
version, and the applied version catches up once the engine's next heartbeat confirms
it picked the change up.

If they disagree for longer than that, it's a sign the camera hasn't picked up a recent
change yet, useful evidence if you need to report that a toggle doesn't seem to be
taking effect. A large, static gap between desired and applied (rather than one that
closes within moments) usually pairs with a stale heartbeat below, pointing at the same
underlying problem: the camera's AI engine isn't actually receiving updates.

## Engine telemetry

- **Last heartbeat**: the last time this camera's AI engine checked in. Flagged "Stale"
  if it's overdue. This is what ultimately drives the Unresponsive status shown
  elsewhere.
- **Measured FPS**: how many frames per second the engine is actually processing,
  shown in green when it's within the expected range and amber when it's outside it.
  A camera running well below its expected FPS may be struggling with hardware load
  or a degraded feed even while it's still technically Connected.
- **Inference latency**: how long the AI model takes to process each frame. Rising
  latency over time on a camera that used to be fast is worth investigating even before
  it becomes an outright failure.
- **Last error code**: the most recent problem the engine reported for this camera, if
  any, with a plain-language message underneath (for example, "Could not open RTSP
  stream").

Together, these tell apart a camera with a real problem (an error code, but a recent
heartbeat, meaning the engine is alive and reporting trouble) from one whose AI engine
has stopped responding entirely (a stale heartbeat with no error code, meaning there's
no one left to report anything).
