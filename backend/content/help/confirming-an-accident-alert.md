---
slug: confirming-an-accident-alert
title: Confirming an Accident Alert
category: Operations
roles: [Admin, Operator]
summary: What confirming does, when you can do it, and what happens right after.
sort_order: 10
is_faq: false
---

## When you can confirm

An alert can be confirmed only while it is **Unverified** — the status it arrives in the
moment the AI detects a possible accident. If someone else has already acted on it, your
request is rejected and nothing changes.

## What to check first

Open the alert and look at the snapshot and confidence score before deciding. Confirming
tells the system this is a real accident that needs a response.

## What happens after you confirm

- The alert moves to **Ongoing**.
- You are recorded as the operator who verified it.
- The camera that reported it stays paused — it does not resume AI detection while the
  incident is open.

From **Ongoing**, the alert can later be resolved (scene cleared) or, if confirming it
turns out to have been a mistake, dismissed as a correction.
