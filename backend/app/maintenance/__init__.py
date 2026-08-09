"""D-011 backup, restore, restart, and archival — pure Python, no FastAPI
import (08_PKG_backup_ops.md Step 1). Every orchestrator (the maintenance
API route, PowerShell, systemd, a Windows Scheduled Task) calls into this
package; nothing reimplements file handling.

Runnable as `python -m app.maintenance <command>` via cli.py.
"""
