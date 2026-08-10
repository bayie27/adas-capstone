# P5 — System Health and Hardware Telemetry

> **Blocked by:** P4 (needs heartbeat FPS/latency data).
> **Branch:** `feat/be-p5-system-health`
> **Prerequisite reading:** [`01_CONTRACTS.md`](01_CONTRACTS.md) §3.7, `be_decisions_review.md` D-009.
> **Size:** L. Six steps.

## Why this package exists

FR-16 and NFR-05 require uptime, CPU, GPU, RAM, disk, and inference-speed telemetry with a 48-hour
history and 30-day trends. Nothing exists: `backend/app/core/monitor.py` is 0 bytes,
`SysHealthRaw` / `SysHealthHourly` are created by `create_all` and stay empty forever, and `psutil`
and `gputil` are declared as runtime dependencies but imported nowhere in the repo.

> `CLAUDE.md` lists `monitor.py` as an intentional placeholder not to be "fixed". This package is the
> explicit instruction to implement it. P9 updates that note.

---

## Step 0 — Dependency swap

**Remove `gputil`. Add `nvidia-ml-py`.**

GPUtil's last release was 2018 and it works by parsing `nvidia-smi` **text output**, which breaks on
driver formatting changes and gives no reliable per-device memory figures. `nvidia-ml-py` is NVIDIA's
official NVML binding, and D-009's verification requirement ("unit and scheduler tests mock OS, time,
**NVML**, missing sensors") already assumes NVML. Run `uv lock`.

Import NVML lazily and tolerate its absence entirely — CI runners have no GPU, and the collector must
degrade to "no GPUs available", not crash.

---

## Step 1 — The provider layer

**File:** new `backend/app/services/hardware.py`

Isolate every OS/driver call behind small functions so the collector is testable without hardware:

```python
def read_cpu() -> CpuSample          # usage %, temperature (None on Windows)
def read_memory() -> MemorySample    # usage %
def read_disk(path: Path) -> DiskSample   # total, used, available, percent
def read_gpus() -> list[GpuSample]   # index, name, usage, temp, mem_used_mb, mem_total_mb, mem_pct
def read_uptime() -> UptimeSample    # host uptime, backend-process uptime
```

Each returns a value object with an explicit availability flag. **Every one of them must catch its own
exceptions and return "unavailable" rather than propagate** — D-009: "sensor/provider failure does not
make the complete endpoint fail when other metrics remain available."

**CPU temperature on Windows.** `psutil.sensors_temperatures()` does not exist on Windows at all
(the attribute is absent, not empty). Return `None` with `cpu_temp_available=False`. It renders as
"Unavailable", never as `0`. This is expected on the demo laptop and is not a bug to work around.

Disk is measured on the volume containing the **data root** (database + snapshots), not `C:\`.

---

## Step 2 — The live collector

**File:** `backend/app/core/monitor.py` (currently 0 bytes)

A scheduler job every `HEALTH_SAMPLE_SECONDS` (5s) that builds one sample and **overwrites** it in
memory on `app.state`. Live samples are never individually persisted — that is the whole point of the
two-layer design (D-009): every workstation polling the API must not cause an independent OS/driver
query, and a 5-second sample rate must not become 17,000 database rows a day.

The sample also carries AI figures pulled from fresh heartbeats (P4):

- `avg_inference_latency_ms` and `avg_fps`, averaged across cameras whose `last_heartbeat_at` is
  within `HEARTBEAT_STALE_SECONDS`
- `sample_camera_count` — how many cameras contributed. D-009 is explicit that this is **contextual
  text beside FPS/latency, not another camera KPI card**; System Health must not duplicate the Camera
  Management KPIs.

A retained sample older than one interval is marked `stale: true` and keeps its **original**
collection timestamp. Never present a stale sample as fresh.

---

## Step 3 — Historical persistence and rollup

Four scheduler jobs, all with the P1 policy (UTC, `max_instances=1`, coalescing, own short session):

| Job | Cadence | Behavior |
|---|---|---|
| `health_persist_raw` | every 5 min | writes the raw subset (`01_CONTRACTS.md` §3.7) from the latest **valid** sample; skips entirely if there is no fresh sample — never fabricates |
| `health_rollup_hourly` | at each UTC hour boundary | aggregates the previous hour's raw rows into one `sys_health_hourly` row |
| `health_prune_raw` | hourly | deletes raw rows older than 48 h |
| `health_prune_hourly` | daily | deletes hourly rows older than 30 days |

Rollup rules:

- `hour_start` is `UNIQUE` and is the **idempotency key** — use an upsert so a re-run or a missed-then-
  coalesced firing cannot duplicate or double-count.
- Averages ignore `NULL`s rather than treating them as zero. An hour with no GPU present yields
  `avg_gpu_usage = NULL`, not `0`.
- `sample_count` records how many raw rows fed the row, so an incomplete hour after a restart is
  visible instead of silently understated.
- Missed periods produce **no** row. Gaps are gaps.

---

## Step 4 — Endpoints

**File:** new `backend/app/api/routes/system_health.py`

> **Do not add these to `routes/system.py`.** That module holds the P1 probes only, and P7 is adding
> `routes/maintenance.py` in parallel off the P2 branch. Sharing one file is what would make these
> two packages conflict. The URL prefix is still `/api/system/...`; only the module differs.

```
GET /api/system/health/live
GET /api/system/health/history?range=48h|30d
```

Both roles may read them. History returns oldest-to-newest using **one consistent point shape** for
raw and hourly ranges, so the frontend chart component does not branch on range.

The live response carries everything in D-009's list: host and backend-process uptime; CPU usage and
nullable CPU temperature; RAM usage; disk total/used/available/percent; per-GPU index, name, usage,
temperature, memory used/total and percent; aggregate GPU utilization, max GPU temperature, and
highest per-GPU memory percentage; average inference latency and FPS; `sample_camera_count`;
collection timestamp; freshness and availability flags; warnings; and an overall
`healthy` / `degraded` / `critical` state.

**Multi-GPU aggregation** — get these right, they differ deliberately:

| Aggregate | Rule |
|---|---|
| GPU utilization | **mean** of available devices |
| GPU temperature | **max** device temperature |
| GPU memory pressure | **max** device percentage — *not* a mean, which would hide one nearly exhausted GPU |

Warnings return a machine-readable code, severity, the measurement, and the threshold. The backend
never returns presentation strings or colors; the frontend decides how to display them. Defaults:
GPU temp critical 85 °C, RAM critical 95%, disk warning 80% / critical 90%, AI heartbeat stale > 10s.

---

## Step 5 — Camera KPI verification

P4 reshaped the camera list response. Add the invariant tests here, where the KPI semantics live:

```
Total = cameras WHERE is_active = 1
Enabled + Disabled                                       = Total
Connected + Disconnected + Reconnecting + Unresponsive   = Total
Active + Paused + Inactive + Unresponsive                = Total
```

Seed a fixture with cameras in every combination — including a **disabled camera that is still
reporting `Connected`** — and assert all four invariants hold. Configuration, connection, and AI state
are independent dimensions; nothing may infer "disabled" from a connection or AI status (D-009).

The KPI modals are number-only: no camera records, no pagination. The API returns counts only; the
existing page filters remain the way to find individual cameras.

---

## Verification

```bash
uv run pytest backend/tests/test_system_health.py
```

Manually:

1. Start the backend, wait ~30s, `GET /api/system/health/live` → real CPU/RAM/disk figures, and
   `cpu_temp: null` with `cpu_temp_available: false` on Windows.
2. On a machine with the RTX 3050 Ti, confirm the per-GPU list has one entry with a sensible VRAM
   total (~4096 MB). On a GPU-less machine, confirm an **empty list and null aggregates**, not zeros,
   and that the endpoint still returns 200.
3. Run for ~15 minutes → at least two `sys_health_raw` rows, five minutes apart.
4. Force a rollup with `time-machine` in a test, then run the job twice and confirm exactly one
   `sys_health_hourly` row and unchanged values.
5. Insert a raw row dated 49 hours ago, run the prune job, confirm it is gone and a 47-hour-old row
   survives.
6. `GET /api/system/health/history?range=48h` with a gap in the data → the gap appears as missing
   points, not as zeros.
7. Kill the AI engine → within 10s the live endpoint reports `sample_camera_count: 0`, null FPS and
   latency, and a heartbeat-stale warning; cameras present as `Unresponsive`.
8. `pnpm check`.

---

## Tests to write

| Area | Assertions |
|---|---|
| Providers | each returns "unavailable" instead of raising when its underlying call fails |
| Windows CPU temp | absent `sensors_temperatures` → `None` + flag `False`, never `0` |
| No GPU | empty per-GPU list, null aggregates, endpoint still 200 |
| Multi-GPU | mocked 4-GPU NVML: utilization is the mean, temperature is the max, **memory is the max** |
| Staleness | a sample older than one interval is flagged stale and keeps its original timestamp |
| Rollup | twelve 5-minute rows → one hourly row with correct means, peaks, and `sample_count = 12` |
| Rollup idempotency | running twice produces one row with identical values |
| Rollup with nulls | an hour with no GPU data yields `NULL`, not `0` |
| Pruning | 48h and 30d boundaries, inclusive/exclusive checked explicitly |
| No fabrication | a missed period creates no row |
| AI metrics | only cameras with fresh heartbeats contribute; `sample_camera_count` matches |
| Warnings | each threshold emits code, severity, measurement, and threshold |
| Camera KPIs | all four invariants, including a disabled-but-connected camera |
| Auth | both endpoints require a session; probes do not |

## Paper test cases covered

FR-16, FR-17 (per-camera AI metrics — the analytics side is P6), NFR-05 (10–15s live push from
in-memory data; 5-minute persistence; 48h pruning; hourly aggregates on a rolling 30 days).

TC-I-204 (OS utilities → FastAPI health payload), TC-U-404 (48-hour pruning), TC-U-405 (hourly mean
from twelve 5-minute points).

TC-R-401 / TC-R-402 (24-hour endurance: flat RAM, stable GPU thermals, locked VRAM) become
**measurable** with this package — the actual endurance run is a manual procedure recorded in P9.

## Deliberately not in this package

Analytics endpoints (P6 owns `/api/analytics/*`), backup and restart (P7). Do not add WebSocket
telemetry pushes — D-009 explicitly satisfies NFR-05 with a 10–15 second frontend **poll** of
`/health/live`, deliberately keeping high-frequency telemetry off the alert channel.
