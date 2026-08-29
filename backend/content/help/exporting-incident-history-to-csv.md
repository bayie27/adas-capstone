---
slug: exporting-incident-history-to-csv
title: Exporting Incident History to CSV
category: Operations
roles: [Admin, Operator]
summary: Downloading the incident list as a spreadsheet for reporting.
sort_order: 60
is_faq: false
---

![The Export button's dropdown on the Detections page, offering CSV and PDF
formats](/help/export-dropdown.png)

## Where to find it

The **Export** button sits above the incident list on the Detections page. Clicking it
opens a small menu with two formats, **Export as CSV** and **Export as PDF**, rather
than downloading immediately, so you don't trigger the wrong format by accident.

## What gets exported

Either export downloads a file of the incident history using the same date, status,
camera, operator, and search filters you currently have applied to the list. Whatever
you can see on screen is what ends up in the file. If you want a report for just one
camera's incidents last week, filter the list down to that first, then export; the
export never includes rows you've filtered out, and it never silently expands to
include more than what's showing.

## What's in the file

Each row covers one incident: its number, when it was detected, which camera reported
it, its status and confidence score, a link to its snapshot, and who verified and closed
it (with timestamps). Nothing about the underlying alert changes because you exported
it. Exporting is read-only, and you can run it as many times as you like against the
same filters without affecting the data.

## Choosing CSV vs. PDF

- **CSV** is the better choice if you're going to open the file in a spreadsheet
  program to sort, filter, or chart the data further, or feed it into another system.
- **PDF** is the better choice if you just need something to hand to someone else to
  read or print as-is: a fixed, formatted report rather than raw rows.

## Tracking your exports

Every export you run is recorded as an export job, and a small **Export jobs** indicator
elsewhere in the app shows how many you've triggered: that's a queue of your own past
downloads, not a separate feature you need to configure. If Administrators need to
confirm who exported what and when, that's also visible in the audit trail. See
[Reading the Audit Trail](reading-the-audit-trail).
