---
slug: getting-started-with-adas
title: Getting Started with ADAS
category: Getting Started
roles: [Admin, Operator]
summary: What this system does, the two account types, and where to find things.
sort_order: 10
is_faq: false
---

## What this system does

ADAS watches your road-camera feeds and uses an AI model to spot possible vehicle
accidents automatically. When it thinks it has found one, it doesn't act on its own —
it raises an alert and waits for a person to look at the snapshot and decide. That
person-in-the-loop step is on purpose: the AI flags candidates, but only a logged-in
user ever confirms that something is a real accident.

The moment a camera reports a possible accident, that camera pauses its own detection
until the alert is resolved. This keeps the system from raising a flood of duplicate
alerts for the same event while someone is already looking at it.

## The two account types

- **Operator** — the day-to-day monitoring role. Confirms or dismisses alerts, resolves
  ongoing incidents, manages cameras, and checks system health and AI performance.
- **Administrator** — everything an Operator can do, plus managing user accounts,
  reading the audit trail, and backing up or restoring the system's database.

Your account type is assigned when it's created and shown in the sidebar under your
name. If something in this Help Center is missing from your view, it's most likely
restricted to Administrators — see [Who Can See the Audit
Trail?](faq-who-can-see-the-audit-trail) for an example.

## Where things live

- **Dashboard** — the daily overview: key numbers and recent activity. See [Reading the
  Dashboard KPIs](reading-the-dashboard-kpis).
- **Cameras** — the list of registered cameras and their live status. See [Camera
  Connection Status vs. AI Status](camera-connection-vs-ai-status).
- **Detections** — the full history of every alert the system has ever raised, with
  search and filters. See [Viewing and Filtering Incidents](viewing-and-filtering-incidents).
- **System Health** — server and hardware diagnostics. See [Monitoring System
  Health](monitoring-system-health).
- **AI Performance** — how accurate the detection model has been. See [Understanding AI
  Performance Metrics](understanding-ai-performance-metrics).
- **Profile** — your own name, username, password, and alarm sound preferences. See
  [Updating Your Profile and Password](updating-your-profile-and-password).
- **Users, Audit Log, Maintenance** — Administrator-only areas for managing accounts,
  reviewing every recorded action, and backing up or restoring the database.

## What happens when an alert comes in

A full-screen alert appears with a siren, no matter which page you're on, and it stays
on screen until you make a decision. See [The Accident Alert Popup and the
Alarm](the-accident-alert-popup-and-the-alarm) for exactly how that works and what your
options are.
