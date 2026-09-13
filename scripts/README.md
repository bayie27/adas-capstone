# Scripts

Launcher and maintenance scripts for the whole stack. Run every one of them from
the repository root, never from inside `scripts/`.

Backend-only helpers (seeding, database resets, verification) live in
[`backend/scripts/`](../backend/scripts/README.md) instead.

## Running the stack

| Script          | What it does                                                                                                                                          |
| --------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| `start-dev.ps1` | Starts the dev stack, each component in its own window, in demo bring-up order: MediaMTX, backend, frontend, AI engine. This is what `pnpm dev` runs. |
| `stop-dev.ps1`  | Stops what `start-dev.ps1` started.                                                                                                                   |
| `start-sim.ps1` | Starts the camera simulation on its own (MediaMTX plus one ffmpeg per channel), after checking ffmpeg, mediamtx and the clips are present.            |
| `dev.sh`        | The macOS, Linux and WSL equivalent of `start-dev.ps1`. Supports `--logs`, `--verbose` and `--clean`.                                                 |

With no switches, `start-dev.ps1` starts the everyday pair — backend and frontend:

```powershell
pwsh -File scripts/start-dev.ps1
```

`-All` adds the simulation and the AI engine. `-Lan` swaps every launch command for
its TLS equivalent so a second machine can reach the dashboard; the operating-system
side of that (static IPs, firewall rules, certificate trust) stays manual and is
written up in [LAN setup](../docs/operations/LAN_SETUP.md).

Full switch reference and the seed-profile options are in the
[operations guide](../docs/operations/README.md#the-fast-path-scriptsstart-devps1).

## Maintenance

| Script                          | What it does                                                                                                                                                                             |
| ------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `adas-maintenance.ps1`          | Runs backup, restore and the daily restart on Windows. It stops and starts the backend and AI engine around the real work, which is always `uv run python -m app.maintenance <command>`. |
| `register-maintenance-task.ps1` | Registers, verifies or removes the Windows Scheduled Task `\ADAS\DailyRestart`. Reads the trigger hour from `MAINTENANCE_HOUR_LOCAL` in `.env`.                                          |

These two are the Windows counterpart to the units in
[`deploy/systemd/`](../deploy/systemd/README.md). Windows has no systemd, so the
scheduling lives in Task Scheduler and the orchestration lives in a script. Both
sides call the same Python maintenance core — neither re-implements backup or
restore logic.

`-Verify` on the registration script is the first thing to check when the daily
restart did not fire; see the
[troubleshooting notes](../CONTRIBUTING.md#troubleshooting).

## UAT clip publishing

`publish-uat-positive-then-silent.ps1` and its `.sh` twin are called by MediaMTX
through `runOnInit`, not by hand. They publish one positive clip once, then loop the
silent feed, so a UAT profile fires exactly one accident instead of a new one every
time the clip repeats. The two files are the same contract for Windows and POSIX.

## `lib/`

`adas-lifecycle.psm1` holds the PowerShell helpers the other `.ps1` files share:
atomic file writes, reading values out of `.env`, resolving the configured backup
and log directories, and starting, identifying and stopping managed processes. It
is imported, never run directly.

## Detailed help

Every `.ps1` here carries full comment-based help, which is more current than any
summary above:

```powershell
Get-Help scripts/start-dev.ps1 -Full
```
