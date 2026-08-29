---
slug: monitoring-system-health
title: Monitoring System Health
category: Monitoring
roles: [Admin, Operator]
summary: The status banner, key numbers, and history charts on the System Health page.
sort_order: 15
is_faq: false
---

![The System Health page showing a warning banner, the four KPI cards, and
the history charts below](/help/system-health.png)

## The status banner

At the top of the page, one banner tells you the overall state of the system at a
glance:

- **Green ("All systems normal")** — everything is within expected ranges. Shows current
  processing speed and how many cameras are actively reporting.
- **Amber or red (a warning)** — something needs attention, such as disk space running
  low or a metric crossing a threshold. The most urgent issue is shown first, with a
  "+N more issues" link if there's more than one.
- **Amber ("data may be out of date")** — the page hasn't received a fresh sample
  recently. This isn't necessarily a problem by itself; it refreshes automatically.

## The four key numbers

- **Server Uptime** — how long the server machine itself has been powered on and running,
  with a smaller "Backend process" line underneath showing how long the ADAS backend
  software specifically has been running without a restart (which can be shorter than
  the machine's own uptime).
- **Inference Latency** — how long the AI takes, on average, to process a frame across
  every camera currently reporting.
- **Processing Speed** — average frames per second being processed right now.
- **Disk Storage Usage** — how much of the server's storage is used, with the exact
  free/total space underneath. Turns amber, then red, as it approaches capacity.

A small colored dot next to a number is a quick health indicator for that metric — green
is healthy, amber or red means it's worth a closer look. For Inference Latency and
Processing Speed specifically, the dot also reflects whether any cameras are currently
reporting data at all — if nothing is reporting, there's nothing to average, and the
dot turns red even though "N/A" isn't itself a bad number.

## What to do when you see a warning

A warning here is a prompt to check the specific thing it names, not necessarily an
emergency. Disk space running low, for instance, is worth acting on before it becomes a
problem (old backups and exports can usually be cleared — see [Backing Up and Restoring
the Database](backing-up-and-restoring-the-database)), but it rarely means anything is
failing right this moment. If a warning names a specific camera or component, check that
camera's own detail panel next — see [Viewing Camera Details](viewing-camera-details) —
since the system-wide banner here is meant to tell you _that_ something needs attention,
while the camera-level detail tells you _what_.

## History charts

Switch between "Last 48 Hours" and "30-Day Trend" to see six charts: CPU usage, GPU
usage, GPU temperature, RAM usage, CPU temperature, and GPU memory over time. CPU
temperature and GPU memory each plot two lines — a peak line (the worst moment in each
time period) and a lighter average line — so a brief spike is visible even if the
average looks fine. The other four charts (CPU usage, GPU usage, GPU temperature, RAM
usage) show a single line. Some readings — CPU temperature in particular — may show
"Unavailable — not reported on this host" if the server's hardware doesn't expose that
sensor; that's a hardware limitation, not an error.
