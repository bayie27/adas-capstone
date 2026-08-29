---
slug: backing-up-and-restoring-the-database
title: Backing Up and Restoring the Database
category: Administration
roles: [Admin]
summary: Creating a manual backup, understanding validation, and the safeguards around restoring one.
sort_order: 50
is_faq: false
---

![The Maintenance page's backup list, showing each backup's date, origin,
size, and Valid status](/help/maintenance-backup.png)

## The automatic restore service banner

Near the top of the page, a banner labeled **Automatic restore service** shows whether
restoring is currently possible at all:

- **Ready**: you can select a valid backup and restore it right now.
- **Busy**: a restore is already in progress; wait for it to finish before starting
  another.
- **Unavailable**: the background service that actually performs a restore isn't
  running, so the Restore action on every backup row is disabled until it comes back.
  This isn't something you can fix from this page. It means the maintenance service
  itself needs attention, which is a job for whoever administers the server, not a
  setting you can toggle here.

## Automatic and manual backups

The system takes scheduled backups on its own, and keeps up to 30 daily backups and 10
manual ones, and older backups beyond those limits are deleted automatically, so you don't
need to manage storage yourself. Press **Create Backup** at any time to take one
immediately; it runs in the background and the page tells you once it's finished.

## Reading the backup list

Every backup shows when it was taken, its origin (manual, scheduled, or automatically
taken right before a restore), its file size, and whether it's **Valid**. Expanding a
row shows the individual checks that produced that verdict: things like file integrity,
database structure, and whether internal data links are intact. Only a backup marked
Valid can be restored.

## Restoring a backup: read this before you start

Restoring replaces the entire current database with the selected historical point.
Before you confirm, the system asks you to:

1. Re-enter your current password.
2. Type a confirmation phrase shown on screen, to guard against clicking through by
   habit.

Once you confirm:

- **Every signed-in user, on every device, is immediately signed out.**
- Monitoring may be briefly unavailable while the system restarts.
- The system restarts on its own; you don't need to do anything further.
- A fresh backup of the current (pre-restore) database is taken automatically first, so
  restoring is itself recoverable.

If the restored database fails a readiness check afterward, the system **automatically
rolls back** to the database that was running before you started, and you'll see this
reflected as a "Rolled back" status rather than being left on a broken restore.

Only one backup or restore can run at a time; if one is already in progress, the other
action is unavailable until it finishes.
