# 21 — Realtime WebSocket Alert Delivery

> **One-liner:** The backend commits incident state, then pushes a typed alert event to each authenticated dashboard; REST recovery restores the current pending state after a disconnect.
> **Panel risk:** High — alert delivery and recovery sit directly on the path from an AI detection to operator awareness.

## 1. What it is

An alert reaches a connected operator through a persistent WebSocket from the backend to the browser.
The AI engine does not send the alert to the browser directly.
It submits the detected incident to the backend over the authenticated internal HTTP API.

The backend stores the incident and its camera state first.
After that transaction commits, it puts a JSON event on each eligible dashboard connection.
The browser validates the event, updates its alert store, and renders the pending alert and its snapshot.

The socket is for live updates.
It is not the durable record of an incident.
The database holds the current incident state, and the dashboard reloads that state through REST after a page load or reconnection.

The paper describes this as a server pushing JSON alerts to client browsers over WebSocket.
The recovery requirement adds the important second half: if a client missed the live event, it must still retrieve current Unverified incidents later.

## 2. Where it lives

### In the paper

- Chapter 3, System Architecture and Design, Figure 2, Client-Server Architecture, p. 101.
  It shows the server sending JSON alerts to browser clients through WebSocket connections.

- Chapter 3, Data Flow Diagram, Figure 5, Context Level DFD, p. 112.
  It shows the operator receiving real-time accident alerts from ADAS.

- Chapter 3, Data Flow Diagram, Figure 6, Level 1 DFD, p. 113.
  It decomposes incident analysis and human response into separate logical processes.

- Chapter 1, Non-Functional Requirements Specification, Table 3, NFR-04 Alert Response Time, p. 70.
  The dashboard alert, captured image, and alarm are required within two seconds of the AI detecting a collision.

- Chapter 1, Non-Functional Requirements Specification, Table 6, NFR-17 Asynchronous Alert Recovery, p. 72.
  When the dashboard opens or reconnects after a network interruption, it must immediately retrieve and display all incidents still Unverified.

- Chapter 1, Non-Functional Requirements Specification, Table 7, NFR-19 Session Security, p. 73.
  This is the paper's session security requirement relevant to the cookie-authenticated channel.

### In the code

**Handshake, authentication, and connection limits**

- backend/app/main.py:442 — /ws/alerts handshake and event loop.
- backend/app/main.py:459 — Origin validation runs before cookie processing and database access.
- backend/app/main.py:464 — session cookie is read and checked.
- backend/app/main.py:469 — database session is opened only after the Origin check.
- backend/app/main.py:476 — per-user and overall connection limits are checked before accept.
- backend/app/api/dependencies.py:48 — the shared JWT and server-side session validation.
- backend/app/core/config.py:120 — WebSocket connection, queue, and send-timeout settings.

**Queues, event schemas, and commit order**

- backend/app/services/realtime.py:51 — active connection registry.
- backend/app/services/realtime.py:74 — per-connection queue and sender task are created.
- backend/app/services/realtime.py:132 — non-blocking broadcast enqueue and overflow handling.
- backend/app/services/realtime.py:177 — the sender for one socket drains its queue.
- backend/app/schemas/events.py:21 — event types, typed data models, and the envelope.
- backend/app/services/events.py:54 — typed alert event builders.
- backend/app/api/routes/internal.py:93 — AI alert ingestion and the new-alert broadcast sequence.
- backend/app/api/routes/alerts.py:572 — the explicit ordering rule for dismiss transitions.
- backend/app/api/routes/alerts.py:647 — clear commits before camera and alert events are broadcast.

**Browser connection, parsing, recovery, and display**

- frontend/src/hooks/useAdasWebSocket.ts:30 — socket setup, close handling, and reconnect behavior.
- frontend/src/components/RealtimeAlertsBridge.tsx:66 — event handling and recovery coordination.
- frontend/src/components/RealtimeAlertsBridge.tsx:235 — REST recovery after an accepted connection.
- frontend/src/api/events.ts:4 — TypeScript event and payload types.
- frontend/src/api/events.ts:151 — runtime envelope validation.
- frontend/src/store/useAlertStore.ts:154 — alert state, deduplication, and stale-update protection.
- frontend/src/components/GlobalAlerts.tsx:48 — the operator alert modal reads pending incidents from the store.

## 3. How it works

### The end-to-end path

The path has two separate links:

1. The AI engine sends a detected incident to the backend through the internal alert endpoint.
   The alert contains a stable source event identifier so a retry can be recognized.

2. The backend checks the camera and event, creates the incident record, and updates the camera's desired AI state.
   On a new collision, the camera is paused as part of the same database transaction.

3. The service commits the transaction and refreshes the stored incident and camera rows.
   A duplicate delivery returns without creating another incident or broadcasting another new alert.

4. The route constructs a typed NEW_DETECTION envelope from the committed incident.
   It enqueues NEW_DETECTION first and CAMERA_STATUS_UPDATE second.

5. The realtime manager visits each eligible connection and places the serialized envelope into that connection's queue.
   It does not wait for one browser to finish a network send before serving another browser.

6. That connection's sender task takes events from its queue in order and writes them to the WebSocket.
   Each browser has an independent queue and sender.

7. The React bridge parses and validates the envelope, updates the alert store, and invalidates active-alert query data.
   The global alert component presents Unverified incidents and plays the configured alarm when an unsnoozed Unverified item enters the queue.

The image travels as an authorized snapshot URL in the incident payload.
The browser uses the normal authenticated API route to retrieve the image; the WebSocket does not expose a filesystem path.

### Handshake and access checks

The browser opens /ws/alerts after it has an authenticated user role.
It creates a normal WebSocket connection without adding an Authorization header.
The browser attaches the same HttpOnly session cookie used for REST requests.

The backend checks the request Origin first.
If an Origin header is present, it must exactly match an entry in CORS_ORIGINS.
An unapproved Origin is rejected before the cookie is read or a database session is opened.

A missing Origin is allowed for non-browser callers such as local test clients.
That does not authenticate the connection: a valid session cookie is still required.

After the Origin check, the backend reads the cookie and validates the signed session token.
It then checks the server-side session row and the current user record.
The session must be active, the user must be active, and the token's user identity must agree with the session row.
The role used for the connection comes from the current user record.

Only after authentication does the handshake check the connection limits.
The current code allows five sockets per user and fifty across the realtime manager [UNSOURCED — verify].
If either cap is reached, the new connection is refused before it is accepted.
An established operator dashboard is not displaced to make room.

After acceptance, the backend registers the connection under its connection, user, and session identifiers.
It creates one bounded queue and one sender task for that socket.
The server then queues CONNECTION_READY with a connection identifier, server time, user identifier, and role.

### What the limits protect

The per-user cap prevents one account with several tabs from consuming all available sockets.
The overall cap bounds the manager's in-memory connections and sender tasks.

The configured per-connection queue holds up to one hundred envelopes [UNSOURCED — verify].
The manager uses a non-blocking enqueue, so a slow browser cannot stall the alert-producing HTTP route or another operator's socket.

When a queue is full, the manager closes only that connection with a send-failure reason.
It does not silently discard one event and keep that socket appearing healthy.
The frontend treats an ordinary delivery failure as reconnectable, then runs REST recovery on the next accepted connection.

The sender also applies a configured send timeout.
If sending fails or times out, that sender closes its own connection and returns.
The manager removes the connection from its connection, user, and session indexes.

### The event envelope

Every server message uses the same envelope shape:

| Field       | Purpose                                                              |
| ----------- | -------------------------------------------------------------------- |
| version     | Identifies the envelope contract version.                            |
| event_id    | Identifies this event so the client can ignore a duplicate delivery. |
| type        | Names the event and selects the payload validator.                   |
| occurred_at | Records when the backend created the event.                          |
| data        | Holds the event-specific typed payload.                              |

The backend creates envelopes through one helper.
That helper fills the event identifier and UTC timestamp, while a Pydantic model validates each payload shape.
The frontend first checks the envelope, then validates the fields required for that event type.

The frontend consumes these event types:

| Type                 | What the browser does                                                                         |
| -------------------- | --------------------------------------------------------------------------------------------- |
| CONNECTION_READY     | Stores the connection identifier and server clock offset, then starts recovery.               |
| NEW_DETECTION        | Adds the incident to the active alert store and refreshes active-alert query data.            |
| ALERT_STATUS_UPDATE  | Updates the incident and identifies the operator who handled it for other viewers.            |
| CAMERA_STATUS_UPDATE | Reconciles the camera's enabled state, AI state, connection state, and configuration version. |
| SNOOZE_ACTIVATED     | Mirrors the saved snooze deadline and display name to connected dashboards.                   |
| RE_ALARM             | Clears the snooze state when the incident is due to sound again.                              |
| MAINTENANCE_NOTICE   | Shows a notice before a planned restore or maintenance action takes the backend offline.      |

The socket is server to browser only for business state.
The server ignores client messages; confirming, dismissing, clearing, or snoozing an incident still uses an authenticated REST request.

### Commit first, broadcast second

The ordering is deliberate.
The database transaction is the source of truth; a WebSocket event is a notification that the committed state is available.

For a new alert, the incident row and camera pause are committed together.
Only then does the route enqueue the alert event and the camera status event.
If the database transaction fails, no dashboard is told that an incident exists.

The backend refreshes rows after commit before constructing messages.
That means a broadcast reflects the values the database accepted, not an uncommitted in-memory edit.

This also matters for operator actions.
The state transition and its audit entry commit together before any status event is enqueued.
A rollback therefore cannot leave a dashboard showing a decision that never became durable.

### Broadcast order is part of the contract

The manager's per-connection queue is FIFO.
So the order in which a route calls broadcast is the order that one connected browser receives those events.
The route order is meaningful to the interface and is covered by tracker acceptance criteria.

| Change                       | Event order                                                 | Why the order matters                                                                     |
| ---------------------------- | ----------------------------------------------------------- | ----------------------------------------------------------------------------------------- |
| New incident                 | NEW_DETECTION, then CAMERA_STATUS_UPDATE                    | The operator first sees the incident; the second event shows the camera's incident pause. |
| Dismiss Unverified           | ALERT_STATUS_UPDATE, then CAMERA_STATUS_UPDATE when changed | The dismissal appears before the related cooldown state.                                  |
| Correct Ongoing to Dismissed | CAMERA_STATUS_UPDATE, then ALERT_STATUS_UPDATE              | The resumed camera state leads the correction result.                                     |
| Clear Ongoing incident       | CAMERA_STATUS_UPDATE, then ALERT_STATUS_UPDATE              | The camera's resumed state is shown before the incident becomes Cleared.                  |

The tracker records the new-incident order in Integration Testing, TC-INT-003.
It records the clear order in Integration Testing, TC-INT-008.
Both cases are marked Pass.

This is an ordering guarantee for each receiving queue.
It is not a claim that separate browser connections render at the exact same instant.

### Reconnection and state recovery

A WebSocket event stream is not the alert history.
If the browser was closed, or a network interruption happened before a frame arrived, the server does not replay old frames from a durable socket log.

Instead, every accepted connection begins with CONNECTION_READY.
The frontend treats that event as the signal to synchronize from persisted server state.
It does this both after the first connection and after each reconnect.

The recovery sequence is:

1. Mark recovery as in progress and record incident identifiers the client already has.
2. Request the active incident list from the authenticated alerts API.
   The query asks for Unverified and Ongoing incidents.
3. Add each returned incident into the alert store and rebuild active snooze state from persisted snooze deadlines.
4. Invalidate camera query data so the dashboard can load current camera status.
5. Process any WebSocket events that arrived while the REST request was running.

The recovery request in the current bridge asks for one page with a limit of one hundred and does not request another page [UNSOURCED — verify].
This is the current code path to verify against the intended all-alert contract at larger active incident counts.

Events arriving during the REST read are buffered instead of applied immediately.
After the snapshot is added, the buffered events are replayed.
Incident updates use updated_at as the merge key, and camera updates use config_version, so an older snapshot cannot overwrite a newer event.
Event identifiers are also checked to avoid applying the same live message twice.

The alert store keeps Unverified and Ongoing incidents.
The global alert dialog filters that store to Unverified items, so outstanding items return to the operator queue after a page reload or reconnection.
Ongoing incidents are restored for the in-progress incident tray, but do not sound the new-alert siren.

A closed browser receives no live frame at the moment the AI detects.
The backend still has the committed incident record.
When the operator reopens the authenticated dashboard, the connection is accepted, CONNECTION_READY starts the recovery request, and the currently pending record is brought back into view.

### Detecting a connection loss

CONNECTION_READY proves that the handshake was accepted and gives the frontend a connection identifier that can be matched to backend logs.
The browser also observes WebSocket open, close, error, and message events.
The server's receive loop observes client disconnects; the dedicated sender observes failed or timed-out writes.

The frontend reconnects after recoverable closes using capped exponential backoff with jitter.
Authentication and origin failures are treated as terminal until the session or configuration changes.
A connection-limit close backs off more aggressively to avoid immediately trying the same rejected connection again.

There is no application-level alert heartbeat message in this event catalog.
A silent network partition may not be surfaced at the exact instant it occurs.
The system detects it when the socket layer reports closure or a send fails; the recovery query restores current alert state after a new connection is accepted.

## 4. Why it was built this way

A persistent WebSocket lets the backend enqueue an alert as soon as the committed record exists.
The browser does not need to wait for its next periodic request to discover a new event.
That design fits the paper's NFR-04 target for displaying the alert, image, and alarm within two seconds of AI detection.

REST still has a separate job.
It returns the authoritative current alert list on first load and reconnect, when a live event might have been missed.
Using a current database snapshot for recovery avoids treating the transient socket queue as permanent history.

A bounded queue and a separate sender task isolate slow or disconnected workstations.
A network send can wait for one browser without making every other broadcast wait behind it.
If that socket cannot recover before its queue fills, closing it is safer than dropping an arbitrary status change and pretending the connection is current.

Cookie authentication keeps the browser handshake on the same session model as REST.
Checking Origin before database access rejects an untrusted browser source before session lookups.
The cookie is not read by JavaScript, and the dashboard does not put the session credential in a URL or an event payload.

Commit-before-broadcast preserves the relationship between stored state and visible state.
The explicit event order preserves what each dashboard should observe when one action changes both an incident and a camera.

The paper and tracker do not present a side-by-side WebSocket-versus-polling benchmark.
The defensible reason to give the panel is the system's real-time alert requirement and immediate push design, not an experimental claim that polling was measured and failed.

## 5. What changed since the 28 April defense

The paper's high-level description is still the same system seam: the backend sends alerts to browser dashboards through WebSocket.
The current implementation fills in the operational contract behind that diagram.

Since the prior defense, the channel has been made explicit in code as a cookie-authenticated endpoint with an early Origin check, connection caps, per-socket sender queues, typed envelopes, session revocation, and reconnect backoff.
The frontend now requests persisted active state after each accepted connection and merges that snapshot with live events received during the request.

The channel also carries camera state, incident status, snooze, re-alarm, and maintenance notices.
The alert route's event order is explicitly represented in integration acceptance criteria rather than being an incidental series of sends.

## 6. Limits and honest caveats

The paper's NFR-17 states the requirement for all current Unverified incidents.
The tracker acceptance criterion for state recovery asks for all currently Unverified alerts to be displayed on reload or reconnection.

The recorded recovery test is Reliability & Endurance, TC-REL-014.
It generated two Unverified alerts, closed and reopened the dashboard lifecycle, and marked the result Pass.
The recorded qualification is browser-lifecycle simulation; the tracker says to repeat with a force-closed real browser tab for deployment evidence.

The test result supports recovery of the exercised alerts.
Do not describe that tracker result as a production browser trial or as a test of an unbounded number of open alerts.

The current recovery call has a one-page request bound and no pagination loop.
Its page size of one hundred is a code value not stated in the paper or tracker [UNSOURCED — verify].
If the panel asks whether the implementation recovers more than one page of active incidents, answer that this path needs a larger-count verification before claiming it.

The WebSocket queue size and connection caps are current configuration values.
The code sets one hundred queued envelopes per socket, five sockets per user, and fifty sockets overall [UNSOURCED — verify].
The paper and tracker do not state those exact operational values.

The socket channel is not a durable event log.
A closed browser does not receive a push frame at the time of detection.
Recovery returns current Unverified and Ongoing state; it does not replay every intermediate frame or reconstruct a notification that is already terminal.

If the one REST recovery request fails, the current bridge finishes the recovery attempt and replays buffered WebSocket events.
It does not retry that failed snapshot request while the same socket stays open.
A later reload or reconnection starts recovery again.

NFR-04 performance evidence is also qualified.
TC-PERF-003 is marked Pass with controlled browser simulation: thirty dev-injected detections rendered with mean 668.2 ms, p95 887 ms, maximum 1,395 ms, all below the paper's two-second requirement.
The tracker notes the browser run used an isolated instance and audio was checked with component-level instrumentation.

TC-PERF-004 measured broadcast to two independent dashboard clients.
The second socket received an ALERT_STATUS_UPDATE 24 ms after the first operator's confirm commit.
The tracker marks Pass, and notes that only two clients were exercised, below the documented command-centre workstation count.

## 7. Likely panel questions

**What if the operator's browser was closed when the alert fired?**

The backend commits the incident before broadcasting, so the record survives without a browser connection.
When the operator reopens the authenticated dashboard, CONNECTION_READY triggers a REST recovery read and the still-Unverified alert returns to the queue.
The tracker passed the exercised two-alert browser-lifecycle simulation, with real force-closed-browser evidence still to repeat for deployment.

**How do you know the dashboard is still connected?**

The accepted handshake is confirmed by CONNECTION_READY, which includes a connection identifier that can be matched to server logs.
The browser and server observe socket open, close, error, and send-failure events.
A silent network break may take time to surface; the dashboard reconciles current alert state after it reconnects.

**What if the WebSocket drops mid-incident?**

The incident state is already in the database, so dropping the socket does not roll back the alert.
The browser reconnects with backoff, then retrieves the current Unverified and Ongoing records before applying events received during that read.
This is the recovery required by NFR-17.

**What if a slow client cannot keep up with alerts?**

Each connection has its own bounded queue and sender.
A full queue or failed send closes only that connection, rather than blocking other operators or silently losing an event.
That browser reconnects and reconstructs current alert state through the alerts API.

**Why WebSocket rather than polling?**

A persistent socket lets the backend push a committed event immediately, instead of waiting for a later client request.
The paper's NFR-04 sets a two-second display target for the alert, image, and alarm.
The paper and tracker do not claim a head-to-head polling benchmark.

**How does the handshake stop a different site from opening a socket with the operator's cookie?**

If the request has an Origin header, the backend checks it against the allowed origin list before any session lookup.
A valid cookie is still required, and a missing cookie or revoked session is refused before any event is sent.
The tracker records that behavior as Pass in Security Testing, TC-SEC-007.

**Why commit before broadcasting?**

A broadcast tells the operator that a particular state change exists.
If the database transaction later rolled back, sending first would show a change that never became durable.
The backend commits and refreshes the row, then builds and enqueues the event from that stored result.

**Why does event order matter if both updates are eventually sent?**

The receiving queue is FIFO, so route order is user-visible order.
For a new incident, the alert comes before the camera-pause event; for clearing, the camera-resume event comes before the Cleared alert update.
The tracker checks those orders in TC-INT-003 and TC-INT-008.

**How do you stop a recovery snapshot from undoing a newer live change?**

Events that arrive during recovery are buffered until the REST snapshot has been applied.
The client then replays them, rejecting incident rows with an older updated_at and camera rows with an older config_version.
Event identifiers also prevent the same envelope from being applied twice.

**Can the dashboard confirm or dismiss an alert through the WebSocket?**

No.
The WebSocket is for server-to-browser updates; the server ignores messages from the client.
Operator decisions remain authenticated REST requests, which commit the incident and audit entry before broadcasting the result.

## 8. Cram summary

- The AI engine submits alerts to the backend over HTTP; the backend sends live JSON events over the authenticated WebSocket.
- The Origin check runs before cookie validation and database work; session authentication still requires the valid HttpOnly cookie.
- The backend commits incident and camera state before broadcast.
- Each connection has its own bounded queue and sender; a slow client is closed without blocking other dashboards.
- Event envelopes are typed and parsed on both server and browser.
- Per-connection FIFO makes route broadcast order part of the UI contract.
- CONNECTION_READY triggers REST recovery on initial load and reconnect; live events arriving during that request are buffered and replayed after the snapshot.
- NFR-17 is in Chapter 1, Table 6, p. 72. TC-REL-014 passed a two-alert browser-lifecycle simulation; the tracker requests a real force-closed-tab repeat for deployment evidence.
- The current recovery call requests one page only; do not claim beyond its current code path without verification.
