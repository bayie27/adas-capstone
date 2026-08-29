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

- **Connection status** — is the video feed reachable at all? Values: Connected,
  Disconnected, Reconnecting, Unresponsive.
- **AI status** — is detection actually running on that feed? Values: Active, Inactive,
  Paused, Unresponsive.

A camera can be connected but not actively detecting (for example, while it's paused
during an open incident), so don't assume one status tells you the other.

## What the numbers on the camera list mean

The camera list shows the total number of registered cameras, how many currently have a
connected feed, and how many currently have active detection running — three separate
counts, because a camera can be enabled without being connected, and connected without
actively detecting.

## What "Unresponsive" means

Unresponsive means that status is no longer being reported for that camera — treat it as
"we don't currently know," not as "definitely broken," and check the camera's connection
directly if you see it.
