# 23 — System health and hardware telemetry

> **One-liner:** System health combines public process/readiness probes with an authenticated dashboard that samples edge-server resources, AI throughput, and historical trends.
> **Panel risk:** medium — the terms “healthy,” “ready,” and “warning” refer to different signals, and the team should be precise about what each one proves.

## 1. What it is

ADAS system health is the operator’s view of whether the edge server has usable capacity and whether the AI pipeline is processing camera feeds steadily.

It also gives host automation a small, unauthenticated way to ask whether the backend process is alive and whether the database is ready after startup.

These are related but separate surfaces.

- Liveness answers: “Is the backend process responding?”
- Readiness answers: “Has initialization finished, and can this process reach its database?”
- Telemetry answers: “What resource and AI measurements has the running system collected?”
- Camera status answers: “Is this individual feed still reporting its connection and AI state?”

Operators use the System Health page to see server uptime, AI processing time, processing speed, storage use, warnings, and historical hardware trends.

FR-15 makes this an operational feature: the system displays server use and AI processing steadiness over past periods.

NFR-05 sets the refresh and retention schedule for the live numbers and historical records.

The health page is a monitoring aid, not a substitute for an operator’s live CCTV view or a proof that every camera is producing useful video.

## 2. Where it lives

### In the paper

Chapter 3, “Requirements Analysis,” Table 2 contains FR-15, “System Health and Hardware Telemetry.”

FR-15 calls for server uptime, processing, graphics, memory, storage, video analysis speed, and historical views.

Chapter 3, “Requirements Analysis,” Table 3 contains NFR-03, the frame-rate requirement, and NFR-05, “Telemetry Refresh Rate.”

NFR-05 specifies live refresh every 5 seconds, detailed readings every 5 minutes, raw retention for 48 hours, and hourly summaries for 30 days.

The “Monitor System Health and Performance” use case describes the operator opening the health dashboard, reading historical CPU, GPU, RAM, and temperature charts, polling live figures, and switching to the 30-day view.

Chapter 3, “System Architecture and Design,” describes three health interfaces: unauthenticated host-watchdog probes, authenticated operator telemetry, and administrator-controlled maintenance operations.

Chapter 3, Figure 7 shows the database entity relationships, including the independent health telemetry tables.

Chapter 3, Data Dictionary, Table 12 describes System Health Raw; Table 13 describes System Health Hourly.

Chapter 3, Figure 25 is the System Health Page. Its four summary cards are Server Uptime, AI Processing Time, Processing Speed, and Disk Storage Usage.

Figure 25 also shows time-series views for CPU and GPU utilization, GPU and CPU temperature, RAM utilization, and GPU memory.

The paper’s hardware-monitoring description says psutil reads host CPU, memory, and disk metrics, while nvidia-ml-py provides GPU telemetry.

The paper’s Use Case alternative flow describes critical hardware warnings with temperature and RAM examples at 85°C and 95%.

The frame-rate warning floor is also stated in the performance requirements and the test plan: 15 FPS is the target and below 5 FPS is the warning floor.

### In the code

Unauthenticated liveness and readiness are in backend/app/api/routes/system.py:14 and backend/app/api/routes/system.py:20.

Authenticated live and historical telemetry endpoints are in backend/app/api/routes/system_health.py:29, backend/app/api/routes/system_health.py:208, and backend/app/api/routes/system_health.py:246.

The machine-readable warning schema is in backend/app/schemas/health.py:33.

Hardware sampling is in backend/app/services/hardware.py:69, backend/app/services/hardware.py:104, and backend/app/services/hardware.py:146.

The cached sample, raw persistence, UTC-hour rollup, and pruning logic are in backend/app/core/monitor.py:59, backend/app/core/monitor.py:153, backend/app/core/monitor.py:163, backend/app/core/monitor.py:231, and backend/app/core/monitor.py:284.

The background schedules are registered in backend/app/main.py:179; router registration is in backend/app/main.py:593.

Maintenance and restore behavior are in backend/app/api/routes/maintenance.py:73 and backend/app/maintenance/cli.py:475.

The operator page, including polling and status presentation, is in frontend/src/pages/SystemHealth.tsx:129, frontend/src/pages/SystemHealth.tsx:267, and frontend/src/pages/SystemHealth.tsx:526.

Warning copy is mapped for operators in frontend/src/utils/warningCopy.ts:26.

Per-camera connection and AI state are rendered in frontend/src/pages/Cameras.tsx:470; stale-heartbeat presentation is in backend/app/services/cameras.py:62.

The tracker covers this topic in Unit Testing rows TC-UNIT-046, TC-UNIT-047, TC-UNIT-058, and TC-UNIT-059; Integration Testing rows TC-INT-015 and TC-INT-018; and System E2E Testing row TC-SYS-015.

## 3. How it works

### The two public probes

The probes live outside the authenticated telemetry router so host scripts can call them without a browser session.

GET /healthz/live returns a small status response when the process can handle the request.

It does not query the database, read hardware sensors, or depend on telemetry.

That keeps liveness narrow: a database outage does not make the process itself look dead.

GET /healthz/ready first checks that application startup has completed its database initialization.

It then opens a database session and executes SELECT 1.

If initialization has not finished or the database cannot be reached, the route returns HTTP 503.

When both checks pass, readiness returns a ready status and names the checks that passed.

This is a real dependency check, not a constant response.

The maintenance restart and restore orchestration polls /healthz/ready after services restart.

If readiness returned success without reaching SQLite, the orchestrator could accept a backend whose database was not usable.

A successful readiness probe proves initialization and basic database reachability; it does not prove every table is intact, that AI inference is running, or that cameras are healthy.

The restore workflow has additional checks for its own recovery outcome and camera heartbeat conditions.

### The authenticated live sample

The System Health page is for signed-in system users; the paper assigns system health monitoring to Operators and Administrators.

The API router applies authentication to its telemetry routes.

The frontend polls the live endpoint every 5 seconds, matching NFR-05.

The backend does not run a new hardware-driver read for every browser request.

A background collector builds one LiveHealthSample and places it in a process-local HealthStore.

The sample is overwritten by the next collector run; dashboard requests read the latest retained sample.

This keeps multiple operator dashboards from independently querying operating-system and GPU-driver sensors.

The collector reads CPU usage, memory usage, disk usage on the configured data volume, host uptime, and backend-process uptime.

It queries available NVIDIA devices for GPU utilization, temperature, and memory.

The hardware provider treats sensor availability separately from the measurement value.

An unavailable GPU or temperature sensor is represented as unavailable, not as a fabricated zero.

CPU and RAM are required for a raw database row; if either required value is unavailable, the persistence job skips that raw row.

The AI engine reports per-camera measured FPS, inference latency, and connection state through its heartbeat.

The backend calculates the live FPS and inference-latency figures across cameras with fresh heartbeats.

The camera count shown with those averages provides the denominator, so “processing at this rate” is not mistaken for a per-camera measurement.

GPU utilization is aggregated as an average of available devices.

GPU temperature and memory pressure use the highest available device reading, so one heavily loaded GPU is not hidden by a lower average.

### Warning payload and state

The live response has a warnings list; each warning is data, not a prewritten sentence or color.

Each warning carries a code, a severity, a measurement, and a threshold.

The frontend maps codes to operator-facing wording and colors.

This keeps the backend response stable if the dashboard wording changes.

The backend currently emits codes for critical GPU temperature, critical RAM usage, disk warning or critical usage, and stale AI heartbeats.

The paper’s example thresholds are temperature above 85°C and RAM above 95%.

The implementation uses the configured 85°C GPU-temperature threshold and 95% RAM threshold.

Disk warning and critical cutoffs are configurable in code; the paper and tracker do not state their exact values: [UNSOURCED — verify].

The stale-heartbeat freshness interval is configurable in code; its exact value is not stated in the paper or tracker: [UNSOURCED — verify].

A warning-severity item makes the overall health state Degraded.

A critical-severity item makes the overall state Critical.

With no warning items, the overall state is Healthy.

Critical describes a serious threshold condition; it does not mean that the backend process has stopped.

A failed readiness check is a separate condition and is reported through HTTP 503 rather than as a telemetry warning.

### How operators see it

The System Health page presents the status banner and summary cards described in Figure 25.

The banner can report stale or not-yet-collected data, show the highest-severity active warning first, or show an all-clear state.

Additional warnings can be expanded below the headline.

The page provides Last 48 Hours and 30-Day Trend chart views.

The live cards refresh without a full-page reload.

If polling fails, the page retains its last values, shows an offline indication, and retries on the next polling interval.

The frame-rate tile is a distinct warning signal: a rate below 5 FPS is shown with an amber warning dot.

A rate in the paper’s accepted 5–15 FPS band is shown as green on the Processing Speed card.

No reporting cameras are shown as idle or unavailable rather than as a zero-FPS measurement.

If cameras are reporting but FPS is missing, the Processing Speed card signals a stream error.

A camera that stops sending fresh heartbeats is shown as Unresponsive in the camera-status surface.

A merely slow but still-reporting camera remains distinct from a camera that has stopped reporting.

The live FPS on System Health is averaged across fresh reporters, so operators should read the reporting-camera count with it.

### Raw samples and historical rollups

The collector refreshes its in-memory sample on the live telemetry cadence.

A separate persistence job writes the latest fresh sample to sys_health_raw on the detailed-reading cadence in NFR-05.

Raw rows are retained for 48 hours, then old rows are pruned.

The System Health history endpoint returns raw readings for the 48-hour view.

At the start of each UTC hour, a rollup job summarizes the preceding hour’s raw rows into sys_health_hourly.

The hourly record stores averages and peak values for the metrics supported by the rollup, plus a sample count.

The unique hour_start value is the idempotency key for a rollup row.

If the same completed hour is rolled up again, the existing row is updated instead of creating a duplicate.

If an hour has no raw samples, the system leaves a gap; it does not invent a zero-valued hour.

Hourly summaries are retained for 30 days, then pruned.

The history endpoint serves hourly summaries for the 30-day trend.

This two-resolution history gives the operator recent detail and longer trends without keeping every detailed reading indefinitely.

## 4. Why it was built this way

Liveness and readiness answer different operational questions.

Liveness is intentionally cheap and independent of SQLite, so a database fault does not falsely say the process has died.

Readiness includes SQLite because a process that cannot use its database is not ready to serve the restored application.

The restart and restore controller can call readiness without an operator logging in.

Telemetry stays authenticated because it exposes detailed host and AI measurements for the operator dashboard.

The sampler is a background service with a shared in-memory snapshot, while the endpoint only serializes that snapshot.

That avoids making browser polling frequency multiply the number of OS and GPU sensor reads.

The live snapshot and historical storage are separate on purpose.

The live snapshot is cheap to read and is replaced as new sensor data arrives.

The raw table preserves detail for short-term diagnosis.

The hourly table gives long-term trend charts a precomputed point for each populated hour.

Precomputing averages and peaks reduces repeated aggregation work on the edge server when an administrator opens historical charts.

The unique hour_start key makes a retry safe and prevents duplicate hourly points.

A missing sample remains a gap instead of looking like a real zero reading.

That distinction matters: zero CPU use and “sensor data unavailable” are not the same observation.

Warnings carry structured fields so the frontend owns human wording, severity styling, and future localization.

Critical hardware readings are visually urgent, while lower-severity conditions remain visible without pretending the service has failed.

The three routers are split along both audience and permission boundaries.

system.py contains host-facing liveness and readiness probes with no user session requirement.

system_health.py contains the signed-in dashboard telemetry surface.

maintenance.py contains administrator-only backup and restore operations.

The paper describes these as three dedicated interfaces; the code keeps their authentication rules and responsibilities in separate modules.

## 5. What changed since the 28 April defense

Since the 28 April defense baseline, the repository added an end-to-end health telemetry backend: hardware providers, the shared live collector, historical persistence, hourly rollups, and authenticated live/history routes.

The live collector and persistence work landed in commits 773ebd0 and 876a3b8; the authenticated health endpoints landed in b4d968c.

The current operator page now shows live hardware and AI metrics, historical charts, stale/offline states, and machine-warning explanations.

The page refresh interval was corrected to the paper’s 5-second NFR-05 cadence in commit 742c470.

The Processing Speed card gained its amber low-FPS state in commit 8ed17df, and the warning floor was aligned with the engine in commit 3cff53d.

The readiness probe now checks database initialization and connectivity, which lets the restart and restore workflow wait on the actual database-backed condition.

## 6. Limits and honest caveats

Liveness says only that the backend can answer a request; it can still return successfully while the database is down.

Readiness checks application initialization and a basic database query; it is not a database-integrity audit or an AI-engine health check.

The restore orchestration can perform additional recovery checks, but readiness itself does not certify that cameras are processing frames.

The live health sample is the latest completed sample, not an instantaneous hardware reading at the moment a browser request arrives.

At startup, before the first sample completes, values are unavailable; the endpoint does not pretend they are zero.

Individual sensors can be unavailable while other telemetry remains usable.

The average FPS is computed over fresh-heartbeat cameras, not reported as an individual FPS for every camera on the System Health page.

A low frame rate appears on the Processing Speed card; it is not one of the backend’s structured warning codes.

Therefore the banner may show no active hardware warning while the Processing Speed card still carries an amber low-FPS dot.

A single slow stream can also be hidden by the system-wide FPS average if other reporting feeds are faster.

The camera-status screen helps distinguish stale reporting from slow-but-reporting operation: a stale enabled camera is shown as Unresponsive.

The paper describes below 5 FPS as the performance-warning floor; this is not the same as a backend process failure or a readiness failure.

The exact disk warning cutoffs and stale-heartbeat interval are not stated in the paper or tracker: [UNSOURCED — verify].

The tracker’s TC-INT-015 integration run shortened raw persistence to 10 seconds so the write path could be exercised promptly.

That run passed the telemetry collection and endpoint checks, but it is an accelerated test interval, not evidence that a 10-second interval is the production requirement.

The production detail interval remains the 5 minutes stated by NFR-05.

TC-INT-018 exercised the real hourly rollup using seeded raw rows, then reran the same hours to check that the unique hour key prevented duplicate summaries.

That is functional verification of aggregation and idempotency, not a real-time observation made by waiting through those full hours.

TC-SYS-015 passed the focused System Health page checks for KPI refresh, trend rendering, offline indication, and automatic polling recovery.

TC-UNIT-046 and TC-UNIT-047 passed the fresh-sample and Unresponsive-camera checks.

TC-UNIT-058 and TC-UNIT-059 passed the average/peak rollup and retention-boundary checks.

Do not claim an uptime percentage, an automatic hardware restart, per-camera FPS visibility on this page, or a live citywide deployment from this feature alone.

## 7. Likely panel questions

**How would an operator know the system is unhealthy?**

The System Health page shows the live resource and AI-processing cards, a status banner, warning explanations, and the historical trends.

A stale sample or failed poll is visible as outdated or offline data; a camera that stops reporting is shown as Unresponsive.

The host probes separately let the restart controller check whether the backend and database are ready.

**Why are the health probes unauthenticated?**

Both /healthz/live and /healthz/ready are machine-facing probes for host watchdog and restart automation.

They return a narrow process or readiness status, so automation can call them without an operator’s browser session.

The detailed CPU, memory, GPU, disk, and AI telemetry remains behind authentication.

**What does the dashboard show if a camera is running slowly?**

The Processing Speed card shows the live average across cameras with fresh heartbeats and turns amber when that average falls below 5 FPS.

The page also shows how many cameras contribute to the average.

If one camera stops heartbeating, its camera status changes to Unresponsive; that is a different signal from a slow frame rate.

**How long do you keep telemetry?**

Detailed readings are written every 5 minutes and retained for 48 hours.

Hourly summaries are kept for 30 days, so operators can inspect longer trends without retaining every detailed row.

Those are the NFR-05 windows.

**What counts as a warning versus a failure?**

A warning is a machine-readable threshold condition that the dashboard explains to the operator.

A critical reading changes the health state to Critical, but it does not by itself mean the backend has failed.

A readiness failure is different: startup or database access is incomplete, so the probe returns HTTP 503.

**Why does readiness query the database instead of just returning OK?**

The maintenance workflow uses readiness after a restart to decide whether the restored backend can proceed.

The route checks completed initialization and executes a database query.

If it returned a constant success while SQLite was unreachable, the restart controller could accept a process that could not use its application data.

**Does a ready response prove that the AI engine and cameras are running?**

No. Readiness proves that backend initialization completed and that its database can answer a query.

AI heartbeats and camera status are separate signals, and the restore workflow can check those separately.

**Why keep raw readings and hourly summaries in different tables?**

Raw readings preserve detail for recent diagnosis; hourly summaries support longer trend analysis.

Precomputing each hour’s average and peak reduces the work needed to render a long-range chart.

The unique hour key makes a repeated rollup update the existing point safely.

**What happens when a GPU sensor is missing?**

The sampler treats a missing provider or sensor reading as unavailable instead of inventing a zero.

The live response can still return other available readings, and the dashboard shows missing data as unavailable.

**Why are health, telemetry, and maintenance separate routers?**

They serve different callers and permissions.

The probes are for host automation, telemetry is for signed-in Operators and Administrators, and backup or restore is restricted to Administrators.

Separate router modules keep those responsibilities and access rules independently understandable.

## 8. Cram summary

- FR-15 is the System Health and Hardware Telemetry feature; NFR-05 sets its refresh and retention windows.
- /healthz/live asks whether the backend process responds and does not touch SQLite.
- /healthz/ready checks completed database initialization and a real database query.
- The restore/restart workflow waits for readiness because that check gates whether the restarted backend can use its database.
- Operators view authenticated live telemetry and historical trends on the System Health page.
- The collector samples CPU, RAM, disk, GPU, uptime, and AI heartbeat metrics into one shared live snapshot.
- The frontend refreshes live health every 5 seconds.
- Detailed rows are stored every 5 minutes and retained for 48 hours.
- Hourly summaries are retained for 30 days; hour_start is the unique idempotency key.
- The FPS target is 15 FPS; below 5 FPS is the warning floor, and the Processing Speed card turns amber.
- A stale enabled camera is shown as Unresponsive; a slow average and a stale heartbeat are different conditions.
- Warnings carry code, severity, measurement, and threshold; the UI supplies the operator wording.
- Liveness, readiness, authenticated telemetry, and administrator maintenance are separate router surfaces because their callers and permissions differ.
- The tracker passes live-sample, stale-camera, rollup, pruning, and System Health page checks; accelerated test intervals must not be stated as production cadence.
