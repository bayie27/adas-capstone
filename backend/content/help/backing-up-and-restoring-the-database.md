---
slug: backing-up-and-restoring-the-database
title: Backing Up and Restoring the Database
category: Administration
roles: [Admin]
summary: Creating a manual backup, understanding validation, and the safeguards around restoring one.
sort_order: 50
is_faq: false
---

## Automatic and manual backups

The system takes scheduled backups on its own, and keeps up to 30 daily backups and 10
manual ones — older backups beyond those limits are deleted automatically, so you don't
need to manage storage yourself. Press **Create Backup** at any time to take one
immediately; it runs in the background and the page tells you once it's finished.

## Reading the backup list

Every backup shows when it was taken, its origin (manual, scheduled, or automatically
taken right before a restore), its file size, and whether it's **Valid**. Expanding a
row shows the individual checks that produced that verdict — things like file integrity,
database structure, and whether internal data links are intact. Only a backup marked
Valid can be restored.

## Restoring a backup — read this before you start

Restoring replaces the entire current database with the selected historical point.
Before you confirm, the system asks you to:

1. Re-enter your current password.
2. Type a confirmation phrase shown on screen, to guard against clicking through by
   habit.

Once you confirm:

- **Every signed-in user, on every device, is immediately signed out.**
- Monitoring may be briefly unavailable while the system restarts.
- The system restarts on its own — you don't need to do anything further.
- A fresh backup of the current (pre-restore) database is taken automatically first, so
  restoring is itself recoverable.

If the restored database fails a readiness check afterward, the system **automatically
rolls back** to the database that was running before you started — you'll see this
reflected as a "Rolled back" status rather than being left on a broken restore.

Only one backup or restore can run at a time; if one is already in progress, the other
action is unavailable until it finishes.
