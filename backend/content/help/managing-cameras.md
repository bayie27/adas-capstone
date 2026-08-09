---
slug: managing-cameras
title: Adding, Editing, and Disabling Cameras
category: Operations
roles: [Admin, Operator]
summary: Registering a new camera, renaming one, and taking a camera out of service.
sort_order: 70
is_faq: false
---

## Adding a camera

A new camera needs a name and a channel ID. Both must be unique among active cameras —
you can reuse a name or channel ID that used to belong to a camera that was removed.

## Editing a camera

You can rename a camera, change its channel ID, or enable/disable it. Disabling a camera
takes it out of AI monitoring without deleting its history.

## Removing a camera

Removing a camera is a soft delete: the camera disappears from the active list, but its
past incidents are kept and still show up in incident history and reports.
