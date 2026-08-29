---
slug: viewing-and-filtering-incidents
title: Viewing and Filtering Incidents
category: Operations
roles: [Admin, Operator]
summary: Finding a specific incident in the history list with filters and search.
sort_order: 50
is_faq: false
---

![The Detections list with the search box and date, status, camera, and
operator filters above a table of incidents](/help/detections-filters.png)

## What the list shows

Every accident alert the system has ever raised, one row per incident: its number, when
it was detected, which camera reported it, the AI's confidence score, its current
status, who last handled it, and when it was last updated. Clicking the view icon on
any row opens its full detail, including who verified it and who closed it. See
[Confirming an Accident Alert](confirming-an-accident-alert) and the related articles
for what those actions actually do.

## Filtering the incident list

The incident history list can be narrowed down by:

- **Date range**: a start and end date.
- **Status**: Unverified, Ongoing, Dismissed, Resolved (you can select more than one
  at once, so you can view, for example, both Dismissed and Resolved together while
  excluding anything still open).
- **Camera**: one or more cameras.
- **Operator**: incidents an operator verified or closed. This finds incidents by who
  acted on them, not by who happens to be logged in right now, so an Administrator can
  filter to a specific Operator's history just as easily as their own.
- **Search**: matches either an incident number or a camera name.

Filters combine with each other rather than replace one another. Narrowing by camera and
then adding a status filter looks for incidents matching both, not either.

## Tips

Searching with just a number looks for that exact incident number as well as camera
names containing that number, so a partial camera name is usually the faster path if
you're not sure of the incident number. If you only remember roughly when something
happened, start with the date range rather than guessing at a search term. Narrowing
the window first often gets you to the right incident faster than searching blind.

Whatever combination of filters you have applied when you export is exactly what ends
up in the file. See [Exporting Incident History to CSV](exporting-incident-history-to-csv)
for how filtering here is also how you scope a report before downloading it.

## Undoing a mistaken action

Once you're looking at an incident's detail, be aware that most actions taken from
there are final. See [Can I Undo a Confirmed or Resolved
Incident?](faq-can-i-undo-a-confirmed-or-resolved-incident) before clicking Confirm,
Dismiss, or Resolve if you're not certain.
