---
slug: camera-connection-vs-ai-status
title: Camera Connection Status vs. AI Status
category: Monitoring
roles: [Admin, Operator]
summary: The two independent status fields shown on every camera, and what each one means.
sort_order: 20
is_faq: false
---

![The camera list showing Connection Status and AI Detection Status as
separate columns, with explanatory notes like "Held for an open incident" and
"Detection turned off for this camera"](/help/camera-list-status.png)

## Two separate things

Every camera shows two statuses, and they answer different questions:

- **Connection status**: is the video feed reachable at all? Values: Connected,
  Disconnected, Reconnecting, Unresponsive.
- **AI status**: is detection actually running on that feed? Values: Active, Inactive,
  Paused, Unresponsive.

A camera can be connected but not actively detecting (for example, while it's paused
during an open incident), so don't assume one status tells you the other. It's also
possible, though less common, for a camera to show odd combinations for a moment during
a state change (a brief reconnect while an incident is still technically open, for
example) before things settle into a stable pairing again.

## Reading the small notes under AI status

The AI status column sometimes shows a short explanation underneath the status word
itself, and these are worth reading rather than skipping past:

- **"Held for an open incident"**, meaning it resumes when an operator closes it: the
  camera is Paused because it's the source of a currently Ongoing or Unverified alert.
  Nothing is wrong; detection will resume the moment that alert is
  confirmed-and-cleared, corrected, or dismissed. See [What Happens After I Confirm an
  Alert?](faq-what-happens-after-i-confirm-an-alert).
- **"Dismissal cooldown"**, shown with a live countdown of seconds remaining: the
  camera just had a false positive dismissed and is in its short automatic cooldown.
  See [Dismissing a False Positive](dismissing-a-false-positive).
- **"Detection turned off for this camera"**: someone deliberately disabled this
  camera; it won't resume on its own. See [Adding, Editing, and Disabling
  Cameras](managing-cameras).

## What the numbers on the camera list mean

The camera list shows the total number of registered cameras, how many currently have a
connected feed, and how many currently have active detection running: three separate
counts, because a camera can be enabled without being connected, and connected without
actively detecting. A healthy, fully-idle system (nothing paused, nothing
disconnected) shows all three numbers matching; any gap between them is where to look
first if something seems off.

## What "Unresponsive" means

Unresponsive means that status is no longer being reported for that camera. Treat it as
"we don't currently know," not as "definitely broken," and check the camera's connection
directly if you see it. A camera becomes Unresponsive when its last check-in (heartbeat)
is older than the system expects, which can mean the camera engine crashed, the network
path to it dropped, or simply that nothing has been actively watching that feed (for
example, in a dev or demo environment with no real camera hardware attached).

For more detail on a specific camera's Unresponsive state, including exactly how long
ago it last checked in, open its detail panel; see [Viewing Camera
Details](viewing-camera-details).
