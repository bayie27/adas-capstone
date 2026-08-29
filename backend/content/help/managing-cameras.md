---
slug: managing-cameras
title: Adding, Editing, and Disabling Cameras
category: Operations
roles: [Admin, Operator]
summary: Registering a new camera, renaming one, and taking a camera out of service.
sort_order: 70
is_faq: false
---

![The Add Camera dialog, asking for a camera name and channel
number](/help/add-camera-modal.png)

## Adding a camera

Open **Add Camera** from the Cameras page. A new camera needs a name and a channel ID.
Both must be unique among active cameras — you can reuse a name or channel ID that used
to belong to a camera that was removed, since a removed camera is soft-deleted rather
than permanently freeing its identity for reuse in a confusing way. Pick a name that
identifies the physical location clearly (the seeded examples in this system — "Ayala
Highway Cam", "Southbound Entry Cam" — name the road or approach, not just a number),
since that's what shows up throughout the app: on alerts, in incident history, and in
the audit trail.

A newly added camera starts enabled, but whether it actually shows Connected and Active
depends on the physical feed and the AI engine actually reaching it — adding it here
registers it in the system, it doesn't make the hardware connection happen. See [Camera
Connection Status vs. AI Status](camera-connection-vs-ai-status) for what the resulting
statuses mean.

## Editing a camera

You can rename a camera, change its channel ID, or enable/disable it from the same
place you added it. Renaming a camera doesn't affect its history — every past incident
still shows the name it had when the incident happened, updated to the new name, so past
records stay attached to the same physical camera rather than becoming orphaned.

Disabling a camera takes it out of AI monitoring without deleting its history. A
disabled camera:

- Stops being monitored for new accidents.
- Keeps every past incident it ever reported, visible in incident history exactly as
  before.
- Shows as **Inactive** in its AI status, with a note that detection has been turned
  off for that camera specifically (as opposed to Inactive from some other cause — see
  [Camera Connection Status vs. AI Status](camera-connection-vs-ai-status)).

Disable a camera rather than removing it if you expect to bring it back later — for
maintenance, a temporary outage you already know about, or a location that's
seasonal. Re-enabling it is a single toggle; re-adding a removed camera means starting
over with a new registration.

## Removing a camera

Removing a camera is a soft delete: the camera disappears from the active list, but its
past incidents are kept and still show up in incident history and reports. This is
different from disabling — a removed camera is gone from the day-to-day camera list
entirely (you won't see it while managing cameras unless you specifically look for
inactive ones), whereas a disabled camera stays visible, just paused.

Removing a camera is the right call when the physical camera is genuinely gone —
decommissioned, relocated, or replaced by a new install that gets its own channel and
its own entry in this list.

## Who can do this

Both Operators and Administrators can add, edit, enable/disable, and remove cameras —
camera management is a day-to-day operational task, not something reserved for
Administrators. See [Can Operators Manage Cameras?](faq-can-operators-manage-cameras).
