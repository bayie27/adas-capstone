# 12 — Cross-Cutting Design Decisions

> **One-liner:** These decisions make alert delivery, camera control, and operator-visible state recoverable when messages repeat, processes restart, or actions race.
> **Panel risk:** high — without these boundaries the system can duplicate an incident, resume the wrong camera, or show an operator a state that never committed.

## 1. What it is

These are the choices that keep the AI engine, backend, database, and dashboard in agreement while each part can fail or restart independently.
They cover event identity, durable state, camera configuration, concurrent operator actions, live notification, and retry behavior.

The AI engine detects a collision and creates an event with a stable `source_event_id`.
The engine first writes that event to a disk-backed outbox; the backend accepts it into the incident database and broadcasts a live alert only after the database transaction commits.

The backend owns desired camera configuration in the database.
The AI engine reports what it currently observes, then receives a complete camera configuration snapshot on each heartbeat and reconciles its local stream workers to match.

The dashboard is a live view of committed backend state.
WebSocket messages are sent after the durable update, while database predicates decide which operator action wins when two requests race.

The design has a simple rule at its center: persisted state defines correctness; memory and network messages help each component notice and act on that state.
The engine outbox is the separate durable holding area for a detected event that the backend has not accepted yet.

## 2. Where it lives

### In the paper

- **Chapter 3, System Architecture and Design:** the AI Engine description and the “Idempotent Alert Ingestion” subsection explain the `source_event_id` webhook and duplicate response behavior.
- **Chapter 3, System Architecture and Design:** “State Reconciliation & Heartbeat” describes observed camera metrics traveling to the backend and the backend returning authoritative desired configuration, with restart recovery on the next heartbeat.
- **Chapter 3, System Architecture and Design:** “Durable Outbox” describes persisting the event and snapshot on disk before transmission, then retrying with exponential backoff when the backend returns.
- **Chapter 3, System Architecture and Design:** the Backend subsection describes database transactions, audited mutations, and WebSocket delivery.
- **Chapter 3, Data Dictionary, Table 10 (Camera):** the desired-state fields and observed runtime fields share a camera record, but represent different owners and facts.
- **Chapter 3, Data Dictionary, Table 11 (Detection Log):** `source_event_id` supports retry-safe ingestion; the table also documents active-incident uniqueness by camera.
- **Chapter 3, Figures 3 and 4:** the swimlane and operational use cases show the automated alert and human decision workflow these mechanisms protect.

### In the code

| Decision                                         | Implementation entry points                                                                                                                                                  |
| ------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Stable event identity and duplicate handling     | `ai_engine/events.py:10`; `ai_engine/accident.py:60`; `backend/app/models/detection.py:32`; `backend/app/services/incidents.py:124`; `backend/app/api/routes/internal.py:94` |
| Full heartbeat snapshot                          | `backend/app/api/routes/internal.py:140`; `backend/app/schemas/internal.py:49`; `ai_engine/supervisor.py:43`; `ai_engine/supervisor.py:216`                                  |
| Durable backend state and recoverable scheduling | `backend/app/models/camera.py:77`; `backend/app/services/snoozes.py:3`; `backend/app/main.py:139`; `backend/app/services/snoozes.py:177`                                     |
| Desired versus observed camera state             | `backend/app/models/camera.py:30`; `backend/app/services/cameras.py:264`; `backend/app/services/cameras.py:326`                                                              |
| Commit before broadcast                          | `backend/app/services/incidents.py:206`; `backend/app/api/routes/internal.py:130`; `backend/app/api/routes/alerts.py:502`; `backend/app/api/routes/alerts.py:506`            |
| Conditional incident transitions                 | `backend/app/services/incidents.py:229`; `backend/app/services/incidents.py:265`; `backend/app/services/incidents.py:273`                                                    |
| Durable event outbox and retry policy            | `ai_engine/accident.py:92`; `ai_engine/outbox.py:52`; `ai_engine/outbox.py:58`; `ai_engine/outbox.py:138`; `ai_engine/outbox.py:169`                                         |

The tracker has focused evidence for the behavior: `TC-INT-009` checks duplicate webhook retry, `TC-INT-014` checks heartbeat state and snapshot exchange, and `TC-INT-019` checks delivery after a backend outage.
`TC-INT-007` checks that an engine report cannot erase a camera pause required by an open incident, and `TC-SYS-008` checks that a second operator cannot record a conflicting decision.

## 3. How it works

### Alert identity makes retries safe

The AI engine creates a UUID when a real detection event fires and includes it as `source_event_id` in the payload.
The same payload, including the same ID, remains in the outbox until delivery is acknowledged (`ai_engine/events.py:10`; `ai_engine/accident.py:60`; `ai_engine/outbox.py:58`).

The backend looks up the ID before creating an incident.
If it already exists, the handler returns that row with HTTP 200 and exits before sending a WebSocket event; a newly created incident returns HTTP 201 (`backend/app/services/incidents.py:153`; `backend/app/api/routes/internal.py:126`; `backend/app/api/routes/internal.py:135`).

The database unique index is the backstop if two identical requests arrive together and both pass the initial lookup.
After an integrity conflict, the service rolls back, checks the same source ID again, and returns the row created by the winning request (`backend/app/models/detection.py:32`; `backend/app/services/incidents.py:206`; `backend/app/services/incidents.py:210`).

This protects the effect of a repeated request, not the number of HTTP attempts.
The intended result is one persisted incident and one new-alert broadcast for that event, even if delivery has to be retried.

### Heartbeat is a state reconciliation exchange

The engine sends a heartbeat containing each local camera worker’s observed status and measurements.
The backend writes those observed fields, commits them, then queries its active camera records and builds the response snapshot from the database (`backend/app/api/routes/internal.py:140`; `backend/app/api/routes/internal.py:181`; `backend/app/api/routes/internal.py:185`).

The response carries camera identity, channel, resolved stream address, enabled flag, desired AI state, state reason, cooldown deadline, and configuration version (`backend/app/schemas/internal.py:49`; `backend/app/schemas/internal.py:65`).
It is a complete list of active camera configuration, rather than a list of changes since the previous heartbeat.

The engine compares the returned snapshot with its local workers.
It starts a worker for a camera that should run, stops a missing or inactive worker, updates changed configuration, and applies pause or resume decisions (`ai_engine/supervisor.py:43`; `ai_engine/supervisor.py:172`).

After a backend restart, the backend can rebuild desired state from database records and open incidents.
After an engine restart, its local worker map starts empty, so the next successful snapshot tells it what to start and which state to apply (`ai_engine/main.py:62`; `ai_engine/supervisor.py:216`).
The paper describes the first-heartbeat reconciliation as the recovery point for either process restarting (Chapter 3, System Architecture and Design).

The engine also checks for locally queued events before applying a backend resume.
If a collision has been detected but the backend has not received it yet, the pending outbox event keeps that camera paused rather than letting a stale `Active` snapshot resume analysis (`ai_engine/outbox.py:97`; `ai_engine/supervisor.py:108`).

### Persisted state is authoritative; scheduling is a convenience

The backend stores incident status, camera desired state, cooldown deadlines, and snooze deadlines in SQLite.
The in-process scheduler holds jobs that wake the application near an expiry time, but a scheduled job is not the only record that an expiry exists (`backend/app/models/camera.py:77`; `backend/app/models/detection.py:67`; `backend/app/services/snoozes.py:3`).

At startup, the backend recomputes camera desired state and reconciles stored snoozes before it schedules pending work (`backend/app/main.py:139`; `backend/app/main.py:145`; `backend/app/main.py:161`).
A periodic database sweep finds due snoozes if a scheduled wake-up was lost; the same expiry function is safe to call from either path (`backend/app/services/snoozes.py:110`; `backend/app/services/snoozes.py:157`; `backend/app/services/snoozes.py:177`).

The expiry path runs a conditional update against the stored incident status and deadline.
Only the process that actually clears the due snooze commits and broadcasts the re-alarm; a duplicate or stale job updates no row and stays silent (`backend/app/services/snoozes.py:84`; `backend/app/services/snoozes.py:110`).

The camera cooldown follows the same principle.
Its deadline is stored on the camera, desired state is recalculated on startup, and expiry work is rebuilt from the database (`backend/app/services/cameras.py:326`; `backend/app/services/cameras.py:368`; `backend/app/services/cameras.py:422`).

This is the meaning of “database as the single source of truth” for backend domain state.
The engine’s local outbox is a durable transport queue for an event that has not yet become a backend incident; it is not an alternative copy of a committed incident record.

### Desired and observed camera state have different owners

Desired state records what the backend wants the engine to do.
It reflects operator configuration, whether the camera is enabled, an open incident pause, or a cooldown (`backend/app/models/camera.py:77`; `backend/app/services/cameras.py:326`).

Observed state records what the engine reports it is doing and seeing: connection state, AI activity, applied configuration version, measured frame rate, inference latency, and diagnostics (`backend/app/models/camera.py:83`; `backend/app/services/cameras.py:264`).

The heartbeat updates the observed side and returns the desired side.
That allows the backend to show an operator both the requested behavior and the engine’s last known runtime state without letting an old engine report overwrite an operator decision.

The tracker’s `TC-INT-007` exercises this boundary: a self-reported `Active` AI status is recorded as observed, while the returned desired state remains `Paused` during an open incident.

### Commit first, then broadcast

For an incoming detection, the backend inserts the incident and updates the camera’s desired state within the database transaction.
The ingest service commits before it returns; the route broadcasts the new alert and camera status only for a newly created record (`backend/app/services/incidents.py:206`; `backend/app/api/routes/internal.py:130`).

For an operator transition, the route records the action and audit entry, commits them together, refreshes the saved row, and then broadcasts the resulting status (`backend/app/api/routes/alerts.py:502`; `backend/app/api/routes/alerts.py:506`).
This makes the WebSocket payload a notice of committed state rather than a promise that the database might later roll back.

If the order were reversed, a client could receive “incident created” or “incident confirmed” while the transaction later fails.
The database would then say the action never happened, but the dashboard and operator could already have acted on the broadcast.

The paper describes atomic audited mutations in Chapter 3, System Architecture and Design; the code supplies the more precise commit-before-broadcast ordering.

### Conditional UPDATE arbitrates state transitions

Every legal incident transition uses an update whose predicate includes both the incident identifier and the expected current status (`backend/app/services/incidents.py:229`; `backend/app/services/incidents.py:265`).
The database checks the expected status at the same point it writes the new status, verification or closure fields, and snooze cleanup.

If the update affects no row, the service reloads the current record and raises a state conflict (`backend/app/services/incidents.py:273`; `backend/app/services/incidents.py:277`).
The route translates that conflict to HTTP 409, so the second operator sees the current status instead of silently replacing the first decision.

A pre-read can help explain the page to the user, but it is not the concurrency guarantee.
The conditional write is the guarantee because it checks the live database value as part of the update.

The tracker’s `TC-SYS-008` records two independent operator sessions receiving the same incident; after one confirmation, the other session’s conflicting confirmation is refused with HTTP 409.

### The outbox holds detections through backend downtime

When the accumulator fires, the engine has already paused that camera.
The accident handler writes the annotated snapshot and event payload to disk before the background delivery worker attempts the webhook (`ai_engine/accident.py:5`; `ai_engine/accident.py:92`).

The outbox writes a temporary file and atomically replaces it with the final event record.
That record carries the payload and its retry metadata, so a process restart can pick up pending delivery (`ai_engine/outbox.py:52`; `ai_engine/outbox.py:58`; `ai_engine/outbox.py:169`).

Connection failures and server errors are treated as transient and scheduled for exponential backoff with jitter (`ai_engine/outbox.py:138`; `ai_engine/outbox.py:169`; `ai_engine/backend_client.py:74`).
Schema-invalid payloads are quarantined; accepted responses remove the pending record; a duplicate `HTTP 200` is accepted the same way as a new `HTTP 201` (`ai_engine/outbox.py:169`; `ai_engine/backend_client.py:24`; `ai_engine/backend_client.py:74`).

While the event is pending, the supervisor uses the outbox’s camera IDs to prevent an authoritative-but-stale backend snapshot from resuming the local worker.
When the backend comes back, the worker retries, the backend commits and broadcasts a new event if needed, and the engine removes the queue entry after acknowledgement (`ai_engine/outbox.py:97`; `ai_engine/supervisor.py:108`; `ai_engine/outbox.py:177`).

The tracker’s `TC-INT-019` reports that, in its controlled backend-outage run, events were persisted on disk, retry timing grew rather than tight-looping, and both events were delivered after the backend returned.
`TC-UNIT-063` separately checks that an event left pending before a process crash is delivered after restart.

## 4. Why it was built this way

### Stable event identity instead of guessing whether two payloads are alike

`source_event_id` names the detection event itself, so a retry reuses the same identity even if its arrival time differs from the original request.
The backend can then distinguish “same event resent” from “a different event happened to use the same camera.”

Without that identity, a lost HTTP response could leave the engine unsure whether the backend saved the event.
Retrying could add another incident and alert; refusing to retry could lose an event that never arrived.

### A full snapshot instead of incremental changes

A delta is meaningful only when both sides agree on the last change they processed.
A process restart or missed message can break that agreement, leaving the engine with no reliable way to infer the current camera set or desired state from the next delta alone.

A complete snapshot lets the backend restate current desired configuration and lets the engine reconcile from whatever local condition remains.
If the backend returns a full authoritative view after each successful heartbeat, recovery does not depend on replaying every earlier configuration change.

### Database state instead of process memory as the authority

The database survives an application restart and can be checked when a scheduled job is late, duplicated, or missing.
The scheduler and local workers exist to perform work promptly, while persisted incident state and deadlines say what must ultimately be true.

If an in-memory job were the only record of a cooldown or snooze expiry, a backend restart could discard the deadline.
If an in-memory worker state were treated as the authority, the next engine restart could forget an operator pause.

### Separate desired state from observed state

An operator command and an engine report answer different questions: “What should happen?” and “What is happening now?”
The database stores them separately and each component owns its own side, so an engine heartbeat can report a stale active worker without cancelling an incident pause.

With one overloaded field, the backend would have to guess whether `Active` represented requested state or measured state.
That makes the pause decision and the health display ambiguous at exactly the time an operator needs to know whether the engine followed the command.

### Commit before sending a live event

The database is the durable decision point; a WebSocket frame cannot make a failed transaction real.
Sending the frame after commit means clients receive a notice only after the stored state and its audit entry exist.

If the event were sent first, a later rollback could leave the dashboard ahead of the database.
Operators might respond to a phantom alert or believe an action was saved when it was not.

### Conditional UPDATE instead of read-then-write

Two operators can load the same `Unverified` incident before either submits a decision.
A normal read followed by a later write allows both requests to act on the stale value they saw.

The conditional update combines the expected-state check and state change into one database operation.
The first valid change makes the predicate false for the competing request, which receives a conflict and must use the current status.

### Durable outbox and backoff instead of fire-and-forget retries

An in-memory network task disappears if the engine process exits while the backend is unreachable.
An on-disk event can be retried after reconnection or restart, while exponential backoff spaces attempts out during a sustained outage.

The outbox and idempotent receiver solve separate halves of delivery: the outbox retains work until acknowledgement, and the receiver makes a repeated submission safe.
Without the outbox, the event can be lost; without the idempotency key, an acknowledgement lost on the return trip can create duplicate effects.

## 5. What changed since the 28 April defense

The current implementation has explicit reliability boundaries that the earlier defense snapshot did not yet contain in this form.
The later code history records a versioned heartbeat reconciliation endpoint, source-event idempotency, a disk-backed outbox, and a service-level conditional transition path as additions after the April defense.

The current paper describes the heartbeat, idempotent ingestion, outbox, and desired/observed schema in Chapter 3, System Architecture and Design, and Tables 10–11.
For this defense, present those as current system behavior; do not describe them as features already demonstrated in April.

The practical change is recovery: a repeated request can reuse event identity, a pending alert can survive an engine restart, and the engine can rebuild camera configuration from the backend’s current snapshot.
The tracker now includes focused checks for duplicate retry, outage buffering, snapshot reconciliation, and conflicting operator decisions (`TC-INT-009`, `TC-INT-014`, `TC-INT-019`, `TC-SYS-008`).

## 6. Limits and honest caveats

The backend database is authoritative for committed application state.
The disk outbox is a distinct durable queue for events not yet accepted by the backend; it should not be described as a second incident database.

The heartbeat snapshot is complete for active camera configuration.
It does not carry an incident history or replace the separate outbox path for a collision that the backend has not accepted yet.

Idempotency depends on reusing the original `source_event_id` for retries.
If a producer creates a fresh ID for every attempt, the backend correctly sees separate event identities and cannot infer that the messages are duplicates by comparing camera, time, or confidence.

The outbox may submit the same payload more than once because the network can fail after a commit but before the acknowledgement reaches the engine.
The design makes the incident and broadcast effect idempotent; it does not claim that only one HTTP request or one network delivery attempt occurs.

The tracker’s `TC-REL-002` labels its ambiguous-response and concurrent-redelivery proof as simulation and calls for a real response-path interruption before treating it as deployment evidence.
Keep that qualification if asked whether exactly-once delivery was proven operationally.

The backend-outage result in `TC-INT-019` is a controlled test run of the recorded environment and event setup.
It supports the outbox behavior under that tested outage; it is not evidence about every possible disk failure or production network condition.

Commit-then-broadcast protects against announcing an uncommitted update.
It does not turn WebSocket delivery into a durable queue for disconnected browsers, and the full heartbeat snapshot is for backend-to-engine camera reconciliation rather than dashboard event replay.

The heartbeat loop sleeps for the interval returned by the backend, making reconciliation periodic at a fixed cadence (`ai_engine/supervisor.py:216`; `backend/app/api/routes/internal.py:211`).
When asked for the exact interval, use a value only if it is sourced in the authoritative paper or tracker; otherwise describe the exchange as periodic.

## 7. Likely panel questions

### “What if the same alert arrives twice?”

The engine reuses the event’s `source_event_id`, so the backend recognizes the retry as the same collision.
The original request creates the incident with HTTP 201; a replay returns the same row with HTTP 200 and exits before broadcasting again.
The tracker’s `TC-INT-009` records that duplicate-retry behavior.

### “Why not keep state in memory and save the database?”

Memory disappears when a process restarts, while the database keeps incident state and camera deadlines available for reconciliation.
The scheduler is an early wake-up mechanism; startup reconciliation and database checks still find due work if an in-memory job is gone.
Without persisted state, a restart could forget a pause or an expiry.

### “What happens if the backend is down when a collision is detected?”

The engine has already paused that camera and writes the annotated snapshot and payload to its local outbox before attempting delivery.
It keeps the camera paused while the event is pending, then retries with backoff and removes the entry after acknowledgement.
`TC-INT-019` records a controlled outage run in which buffered events were delivered after the backend returned.

### “Why is the heartbeat a full snapshot?”

A delta cannot repair state if a process restarted or missed the change that the delta depends on.
The backend sends its current desired configuration for every active camera, so the engine can reconcile from its present local state on the next successful heartbeat.
The paper describes this as the restart recovery point in Chapter 3, System Architecture and Design.

### “Why broadcast only after the database commit?”

A live event should describe a state the backend has actually saved.
Broadcasting first could tell an operator that an incident or decision exists, then a failed transaction could remove it from the database.
The route commits and refreshes the state before it sends the WebSocket event.

### “What if two operators confirm the same incident?”

The transition update includes the expected current status in its database predicate.
After one action changes the row, the competing update no longer matches and returns a state conflict, surfaced as HTTP 409.
The tracker’s `TC-SYS-008` records that the second operator could not replace the first decision.

### “Is this really exactly-once delivery?”

The network can retry, so the same webhook may be sent more than once.
The guarantee is duplicate-safe processing: the same event ID produces one incident and only the creation path broadcasts a new alert.
Our ambiguous-response result is qualified as simulation in `TC-REL-002`, so I would not claim production-grade exactly-once network delivery.

### “Why use exponential backoff instead of retrying constantly?”

Repeated tight retries would add load while the backend is already unavailable.
The outbox records when an event is eligible for its next attempt and increases the wait between transient failures, then resumes delivery after recovery.
The tracker’s `TC-INT-019` observed the retry schedule growing during its controlled outage run.

## 8. Cram summary

- `source_event_id` gives one detection a stable identity; duplicate webhook retries return the existing incident and do not re-broadcast.
- The engine heartbeats at a fixed cadence and receives the backend’s full active-camera configuration snapshot, so either process can reconcile after restart.
- SQLite stores committed backend state; in-memory workers and scheduler jobs act on it, while startup reconciliation and database sweeps recover missed jobs.
- Desired camera state records backend intent; observed fields record what the engine reports.
- State changes and audit entries commit before their WebSocket updates are broadcast.
- A conditional `UPDATE` checks the expected incident status at write time; a stale competing action gets a conflict.
- The engine writes each pending detection to a durable outbox, uses exponential backoff for transient failures, and keeps the camera paused until the backend decides otherwise.
- Say “duplicate-safe processing” rather than “exactly-once networking,” and preserve the tracker’s simulation qualification for ambiguous-response evidence.
