---
slug: reading-the-dashboard-kpis
title: Reading the Dashboard KPIs
category: Monitoring
roles: [Admin, Operator]
summary: What the dashboard's key numbers and charts mean.
sort_order: 10
is_faq: false
---

![The dashboard's three headline numbers alongside the peak-hours and
per-camera charts](/help/dashboard-kpis.png)

## The three headline numbers

- **Ongoing**: accidents currently confirmed and not yet cleared. This is the same
  count shown on the floating ONGOING tray, and it's the number to watch if you want to
  know how much is currently uncleared right now. See [Reviewing Ongoing Incidents in
  the Tray](reviewing-ongoing-incidents-in-the-tray).
- **Total Accidents**: every incident that was confirmed, whether it's since been
  cleared or is still ongoing. This is a running total for the filter you have applied,
  not a lifetime count of the whole system unless your filter covers all cameras and
  all time.
- **Total Cleared**: confirmed accidents that have been closed out. Total Accidents
  minus Total Cleared always equals Ongoing, for the same filter. If those numbers
  don't line up, you're probably looking at two different filters without realizing it.

Dismissed (false-positive) incidents are not counted in any of these three numbers.
They never represent a real accident, so including them here would overstate how many
accidents actually happened. Dismissed alerts do still show up in the full incident
list. Administrators can also review them in AI Performance metrics and the audit trail.

## Accident frequency by location

A ranked list of cameras by how many confirmed accidents each has recorded, highest
first. Useful for spotting which locations need attention: a camera that consistently
tops this list over time might need a physical intervention (signage, a speed bump, a
signal change) that's outside what the software itself can fix, but the software is
what surfaces the pattern in the first place.

This list only includes cameras with at least one confirmed accident in the current
filter. A camera with zero doesn't appear as a zero-length bar; it simply isn't
listed.

## Peak accident times

A 24-hour breakdown showing which hours of the day confirmed accidents happen most.
This chart always shows all 24 hours, even ones with zero accidents, so you can see the
full daily pattern at a glance. A flat stretch in the middle of the night is real
information (nothing happened then), not a rendering gap.

Use this alongside staffing decisions: if accidents cluster heavily around a particular
hour, that's the window where having an operator actively watching (rather than relying
solely on the alarm to catch attention) pays off most.

## Filtering the dashboard

All three numbers and both charts respect whatever date range or camera filter you have
applied to the dashboard. Narrowing to a single camera or a specific week updates
everything on the page at once, consistently. There's no way for one tile to be
filtered and another not; if you change the filter, the whole page reflects it.
