# 09 — System Architecture

> **One-liner:** A local edge system separates collision inference, authoritative operations, and the browser interface, joined by three explicit network seams.
> **Panel risk:** high — panelists may confuse components, processes, and machines, or treat the proposed camera scale as demonstrated capacity.

## 1. What it is

ADAS is a local client/server system for turning CCTV streams into reviewable operator alerts.

The software has three main components:

| Component       | Runs where          | Owns                                                                                                             |
| --------------- | ------------------- | ---------------------------------------------------------------------------------------------------------------- |
| AI engine       | Edge inference host | RTSP intake, frame selection, YOLO inference, event snapshots, delivery queue                                    |
| FastAPI backend | Edge inference host | User and camera records, authorization, incident workflow, database transactions, REST API, live event broadcast |
| React frontend  | Operator browser    | Dashboard display, user actions, local presentation state, chart and form interaction                            |

SQLite is the backend’s embedded store. It is a file and library used by the backend, not a fourth network service.

The IP camera and VMS network is the input source. It sits outside the software boundary, even though it feeds the AI engine continuously.

The system has three communication seams:

| Direction            | Seam                    | Main purpose                                                                     |
| -------------------- | ----------------------- | -------------------------------------------------------------------------------- |
| AI engine to backend | Authenticated HTTP POST | Submit collision events and report camera state through heartbeat reconciliation |
| Backend to frontend  | WebSocket push          | Deliver live alerts, camera changes, and other real-time events                  |
| Frontend to backend  | REST over HTTP          | Load records and submit operator or administrator actions                        |

The engine also receives the backend’s authoritative camera state in the HTTP heartbeat response. The browser opens the WebSocket handshake; the backend then pushes events across that open connection.

Figure 2 is the logical view. It places the AI engine, FastAPI backend, and SQLite database in the edge server area, with React in the browser client area.

Figure 34 is the deployment view. It groups the AI engine, web application, and SQLite database inside one edge inference server, while the operator workstations remain client devices.

Those views describe component ownership and physical deployment at different levels. A single host can run the server-side services; the operator still opens the dashboard in a browser.

The React build is served from the edge host in the paper’s target deployment, then runs in the browser. During development, Vite serves the frontend source from a separate development server.

The design keeps video processing and system data on the internal LAN. The system does not need remote cloud processing for its core detection and alert path.

## 2. Where it lives

### In the paper

The main architecture source is Chapter 3, “System Architecture and Design.”

- Figure 2, “Client-Server Architecture,” shows cameras and VMS feeding the edge server.
- Figure 2 places the AI Engine, Backend (FastAPI), and Database (SQLite) inside the edge server.
- Figure 2 shows the Frontend (React) in the client area beside the user.
- The text around Figure 2 says the core ingestion, inference, database, and API work stays on the internal LAN.
- The same section says the server pushes JSON alerts to browser clients through WebSocket connections.
- The AI-engine description gives the RTSP input, YOLO inference, event snapshot, and backend delivery path.
- It names the alert endpoint as POST /api/internal/alert.
- It names the state-reconciliation endpoint as POST /api/internal/heartbeat.
- It calls the pair a bidirectional, two-endpoint reconciliation protocol.
- It explains that the heartbeat response carries authoritative camera configuration and desired state.
- It describes a disk-backed outbox for event delivery when the backend is temporarily unavailable.
- The backend description assigns business logic, database transactions, RBAC, telemetry, and WebSocket broadcasting to FastAPI.
- The frontend description assigns the SPA to React, fast incoming-event state to Zustand, and REST caching to TanStack Query.

Citation: Defense paper, Chapter 3, “System Architecture and Design,” Figure 2 and accompanying text, pp. 101–102.

The deployment view is in Chapter 3, “Deployment Architecture.”

- Figure 33 is the target network architecture diagram.
- Figure 34 is the deployment architecture diagram.
- Figure 34 places an AI Engine, Web App (FastAPI & React), and Database (SQLite) inside the Edge Inference Server.
- Figure 34 places administrator and operator workstations under Client Devices.
- The text says the proof of concept was evaluated on localized, researcher-controlled hardware.
- It distinguishes that evaluated setup from a target production design for the Lipa CDRRMO.
- The production description says the edge server would host FastAPI, SQLite, YOLO worker processes, and the compiled React frontend.
- Client browsers connect to that server through the internal LAN.
- The paper says this arrangement removes the network transit to remote cloud services and a separate standalone web server.
- Figure 33 and Figure 34 describe a proposed topology; they are not evidence that the proposed full camera network is already deployed.

Citation: Defense paper, Chapter 3, “Deployment Architecture,” Figures 33 and 34, pp. 160–162.

The framework and database choices are in the later Chapter 3 sections.

- “Frameworks and Libraries” covers the backend, frontend, and AI engine stack.
- The backend section names FastAPI and Uvicorn for asynchronous API and WebSocket serving.
- It also names PyJWT, argon2-cffi, APScheduler, psutil, and nvidia-ml-py.
- The frontend section names React, Vite, React Router, Zustand, TanStack Query, Recharts, Tailwind CSS, and Remix icons.
- The AI section names Ultralytics, YOLO, and OpenCV.
- It also describes an optional NVDEC and CUDA path on supported NVIDIA hardware.
- “Database Technologies” compares PostgreSQL, MySQL, MongoDB, and SQLite in Table 19.
- The paper selects SQLite as an embedded, serverless database and describes Write-Ahead Logging (WAL) for concurrent reads and writes.
- The paper identifies SQLModel as the ORM used to validate and structure database interactions.

Citation: Defense paper, Chapter 3, “Frameworks and Libraries,” pp. 167–169; “Database Technologies,” Table 19 and accompanying text, pp. 170–171.

The project scope is qualified in the paper’s abstract and deployment section.

- The study is a proof of concept evaluated on researcher-controlled test hardware.
- The paper says it does not claim production-scale deployment or unmeasured operational outcomes.
- The 418-camera figure belongs to the proposed production specification, not to the demonstrated test capacity.

Citation: Defense paper, Abstract; Chapter 3, “Deployment Architecture,” pp. 159–162.

### In the code

AI engine ownership and startup:

- ai_engine/main.py:33 starts inference setup and model loading.
- ai_engine/main.py:61–85 connects the engine’s event handler to the inference pipeline.
- ai_engine/accident.py:46–92 captures the annotated snapshot and queues the event.
- ai_engine/backend_client.py:17 adds the x-api-key header to backend requests.
- ai_engine/backend_client.py:40–70 sends heartbeat reports and handles backend responses.
- ai_engine/backend_client.py:73–95 posts alert payloads and classifies delivery outcomes.
- ai_engine/supervisor.py:216–243 keeps camera reconciliation running and preserves existing camera runtimes during a backend outage.
- ai_engine/outbox.py:58–74 writes pending events atomically to disk.
- ai_engine/outbox.py:196–219 drains pending events and retries delivery through a worker.

Backend ownership and HTTP seam:

- backend/app/api/dependencies.py:24–31 checks the internal API key using a constant-time comparison.
- backend/app/api/routes/internal.py:30–34 protects the internal router with that key check.
- backend/app/api/routes/internal.py:93–136 handles alert ingestion and broadcasts after event persistence.
- backend/app/api/routes/internal.py:139–213 processes heartbeat reports and returns desired camera state.
- backend/app/services/incidents.py owns incident-domain rules invoked by the internal alert route.
- backend/app/core/db.py:26–35 applies SQLite connection settings, including WAL mode.
- backend/app/main.py:108–110 initializes the database as the backend starts.
- backend/app/main.py:587–600 registers the HTTP routers.

WebSocket seam and frontend recovery:

- backend/app/main.py:442–529 authenticates and manages the /ws/alerts connection.
- backend/app/main.py:615 registers the WebSocket route.
- backend/app/services/realtime.py:46–124 manages WebSocket connections and broadcasts.
- frontend/src/hooks/useAdasWebSocket.ts:52–101 opens the socket and retries after recoverable disconnects.
- frontend/src/components/RealtimeAlertsBridge.tsx:235–264 fetches active alerts during recovery.
- backend/app/api/routes/alerts.py:254–259 documents the REST recovery query after a WebSocket connection or reconnection.
- frontend/src/api/client.ts:8–20 configures the REST client to send the browser’s session cookie.
- frontend/src/api/alerts.ts:171–207 implements REST incident reads and actions.

Deployment and dependency evidence:

- scripts/start-dev.ps1:29–33 starts FastAPI and Vite as separate development processes.
- frontend/package.json:8–17 shows Vite’s development and production-build commands.
- pyproject.toml:11 declares FastAPI with its standard extras.
- pyproject.toml:21 declares SQLModel.
- pyproject.toml:26 and pyproject.toml:29 declare OpenCV and Ultralytics.
- frontend/package.json:21–34 declares the React ecosystem libraries used by the current dashboard.
- The development process layout is not the paper’s target production topology.

## 3. How it works

### One event from a camera to an operator

1. The IP camera or VMS supplies an RTSP feed over the local network.
2. The AI engine selects frames and sends them through the YOLO detection pipeline.
3. When temporal evidence is sufficient, the engine pauses that camera’s ingestion and writes an annotated snapshot.
4. It records the event payload in its disk-backed outbox before relying on network delivery.
5. The engine sends the alert to the backend’s internal HTTP endpoint with the shared API key.
6. The backend validates the payload and stores the incident in SQLite.
7. After persistence, the backend broadcasts a typed JSON event through the WebSocket manager.
8. The React client receives the push and updates its alert state.
9. For other page loads, filters, and operator actions, the client uses REST requests to the backend.
10. The backend owns the durable incident state; the browser keeps presentation state.

The picture to remember is:

- Camera or VMS to AI engine: RTSP video.
- AI engine to backend: authenticated HTTP alert and heartbeat requests.
- Backend to SQLite: local database operations.
- Backend to frontend: WebSocket event push.
- Frontend to backend: REST reads and actions.

### The engine-to-backend seam

The engine does not own camera configuration. It reports what it observes and asks the backend for the current desired state.

The alert path is an HTTP POST to /api/internal/alert.

Each event carries a stable source event identifier so the backend can recognize a retry.

A new accepted event returns HTTP 201 in the paper’s description.

A duplicate retry returns HTTP 200 without creating a second incident.

The heartbeat path is an HTTP POST to /api/internal/heartbeat.

The engine reports connection state, measured processing status, and diagnostic information.

The backend returns the complete authoritative camera snapshot, including desired state and resolved stream configuration.

That lets the backend remain the owner of the operational configuration.

The current code adds the x-api-key request header from the engine.

The backend checks that header before either internal route runs.

This seam is request and response traffic, even though the alert direction is usually from the engine to the backend.

### The backend-to-frontend seam

The frontend opens a WebSocket at /ws/alerts after the user has an authenticated browser session.

The browser sends its session cookie during the handshake.

The backend accepts the connection only after origin and session checks pass.

The backend sends live incident and system events to connected clients.

The WebSocket is for prompt notification and synchronization events.

The client does not send incident decisions over that socket.

The server persists a new incident before it broadcasts the corresponding event.

That ordering means a disconnected browser can miss the push without erasing the incident.

### The frontend-to-backend seam

The React app uses REST for logins, page data, filters, incident actions, camera management, reports, and settings.

The request and response shape is suitable for ordinary reads and commands.

The frontend’s API client sends the session cookie automatically.

TanStack Query caches REST results so pages can manage their server state.

Zustand stores incoming real-time alert state used by the dashboard.

These libraries divide the browser work by responsibility: API cache, live state, and rendered views.

### What happens when a component is unavailable

If the AI engine is stopped:

- No new RTSP frames are analyzed, so no new AI detections can be produced.
- The backend and browser interface can remain available.
- The backend stops receiving fresh engine heartbeats.
- When camera status is requested, the backend can derive an Unresponsive state from stale heartbeat data.
- If an event was already written to the outbox, it remains available for delivery after the engine restarts.
- The engine gets camera state back from the backend on a later successful heartbeat.

If the backend is temporarily unavailable:

- The engine keeps its existing camera runtimes and retries the heartbeat.
- Newly detected events are saved in the disk-backed outbox and retried.
- The dashboard cannot load new REST data or receive WebSocket events during the outage.
- The engine cannot obtain new camera configuration until the backend returns.
- On recovery, heartbeat reconciliation refreshes the engine’s desired camera state.
- The outbox sends events that were pending before the outage or engine restart.

If a browser or its network connection is unavailable:

- The engine and backend can continue their server-side work.
- The backend keeps committed incidents in SQLite.
- That browser receives no live WebSocket push while disconnected.
- The client reconnects its WebSocket when connectivity returns.
- The frontend then requests active incidents through REST and rebuilds its alert state.
- A reload therefore does not depend on having received every earlier WebSocket message.

If the edge host itself is unavailable:

- AI inference, the backend API, and the local SQLite database are all on that host in the paper’s target design.
- Operator browsers cannot reach new server data or live events.
- This is a single-host availability boundary, not a multi-server failover design.
- The paper describes local operation over the LAN; it does not claim automatic server failover.

## 4. Why it was built this way

### Separate the work by responsibility

AI inference is compute intensive and handles continuous video streams.

The backend owns records, permissions, business rules, transactions, and integration points.

The browser concentrates on the operator’s view and actions.

This division keeps the inference pipeline away from the operator workstation.

It also gives the backend a single place to apply rules before updating the incident database or broadcasting an event.

### Keep the response path local

The paper chooses a localized edge architecture for security, latency, and data privacy.

Video, inference, database operations, and API routing remain inside the internal LAN.

That avoids sending sensitive video to remote cloud processing.

It also avoids adding a remote network hop between detection and the command dashboard.

### Use each communication style for its job

The engine sends discrete records and periodic reports, so HTTP request and response traffic fits that seam.

The backend must notify browsers as events happen, so a persistent WebSocket carries pushes without polling.

REST remains the ordinary path for page data and operator actions.

A single transport would make every interaction follow the same pattern, while the design has both server-initiated notification and client-initiated requests.

### Why FastAPI and Uvicorn

The paper selects FastAPI for asynchronous routing and integrated WebSocket support.

Uvicorn supplies the ASGI network runtime.

The paper contrasts ASGI with synchronous WSGI: a waiting WebSocket should not occupy a blocking worker for its full lifetime.

ASGI lets the event loop suspend idle connections while it handles other HTTP requests, heartbeats, or broadcasts.

That lets one Uvicorn worker process serve the three communication channels described in the paper.

### Why React

The paper describes a component-based React single page application.

React Router provides client-side navigation while the app keeps its real-time connection.

Zustand manages rapid updates from WebSocket payloads.

TanStack Query handles REST requests and caches page data.

Recharts, Tailwind CSS, and Remix icons support analytics and interface presentation.

### Why SQLite

The application runs close to its data on the edge server.

SQLite stores relational records in an embedded file and avoids a separate database daemon.

The paper’s Table 19 compares SQLite with PostgreSQL, MySQL, and MongoDB.

PostgreSQL and MySQL add separate server processes and resource use.

MongoDB’s document model does not match the system’s relational records as directly.

SQLite with WAL supports simultaneous dashboard reads and engine writes.

SQLModel provides the application’s typed database interaction layer.

### Why not collapse every role into one monolithic loop

The engine, backend, and browser do different kinds of work and have different failure behavior.

A single monolithic process would couple video inference, data rules, and interface availability.

The current seams let event persistence, live notification, and operator actions be handled by the component that owns each responsibility.

The deployment can still place the server-side components on one physical edge machine.

## 5. What changed since the 28 April defense

The three-part system shape remains the right explanation: inference, API and data ownership, and browser experience.

The current implementation makes the seams and recovery behavior more explicit.

- The internal HTTP contract now has distinct alert-ingestion and heartbeat endpoints.
- The alert route accepts an idempotent event contract, so a network retry does not create duplicate incident rows.
- The engine writes snapshots and event payloads before relying on the backend response.
- The backend persists incidents before broadcasting their events to WebSocket clients.
- WebSocket connections now use authenticated browser sessions.
- The frontend reconnects after recoverable socket failures and fetches active incidents over REST.
- The engine receives authoritative camera settings through heartbeat reconciliation rather than owning a separate copy.

These are post-defense implementation details visible in the repository history and current code.

Useful implementation references include ai_engine/outbox.py:58, backend/app/api/routes/internal.py:93, backend/app/main.py:442, and frontend/src/components/RealtimeAlertsBridge.tsx:235.

The paper’s current deployment section also separates the evaluated proof of concept from the proposed target production design.

## 6. Limits and honest caveats

The paper’s evaluation used researcher-controlled test hardware.

The target Lipa CDRRMO deployment is a proposed design; the paper does not claim it is already a production installation.

The target figure for 418 cameras is a design scope. Do not present it as a measured camera capacity result.

The architecture puts the AI engine, backend, and SQLite file on one edge host in the target deployment.

That is a compact local design, and it also means the host is a shared availability boundary.

A backend outage does not immediately erase events already queued by a live engine.

An engine outage does stop new video inference until the engine is running again.

A browser outage does not prevent the backend from persisting a committed incident.

WebSocket delivery is not the durable record; SQLite and REST recovery supply that record.

The development stack runs Vite separately from FastAPI. That is a development convenience and should not be described as a separate production web server.

The system is local to the command-center LAN. The paper’s core path does not depend on remote cloud processing.

## 7. Likely panel questions

### “Why did you split it into three processes instead of building one app?”

The work falls into three responsibilities: continuous video inference, authoritative data and workflow, and the operator interface. The split keeps heavy video processing away from the browser and lets the backend control state changes. The production design can still put server-side services on one edge host.

### “What happens if the AI engine dies?”

No new frames are analyzed, so no new AI alerts are created. The backend and browser can stay up, and the backend can show camera health as unresponsive when the heartbeat becomes stale. Events already stored in the engine’s outbox can be delivered when it returns.

### “What happens if the backend goes down?”

The engine keeps its existing camera runtimes and retries its heartbeat. Events already detected are written to the disk-backed outbox and sent after the backend returns; the browser cannot receive new server events or perform REST actions during the outage.

### “What if the operator’s browser disconnects during an alert?”

The backend commits the incident before broadcasting, so losing the socket does not remove the incident. On reconnection, the frontend fetches active incidents through REST and rebuilds the alert state before continuing with live WebSocket events.

### “Why FastAPI instead of a simpler synchronous framework?”

The backend has ordinary HTTP requests, engine heartbeats, and long-lived browser WebSockets at the same time. FastAPI with Uvicorn uses ASGI so idle socket connections do not block a worker while other requests arrive. The paper selected it for that asynchronous and WebSocket support.

### “Why React and SQLite specifically?”

React gives the browser a component-based dashboard, with Zustand for live updates and TanStack Query for REST data. SQLite is embedded on the edge host, avoids a separate database server, and uses WAL so the engine can write while the dashboard reads. The paper’s Table 19 explains the database comparison.

### “Could this run on one machine? Does it?”

Yes: Figure 34 places the AI engine, FastAPI/React web app, and SQLite on one on-premises edge server, with browser workstations on the LAN. The proof of concept was evaluated on researcher-controlled test hardware; the paper does not claim a production deployment at CDRRMO.

### “You mention 418 cameras. Have you actually tested that scale?”

No. That number belongs to the proposed full production specification. The paper distinguishes that design target from the researcher-controlled proof-of-concept evaluation, so describe it as a planned deployment capacity target rather than a measured result.

## 8. Cram summary

- The three components are AI engine, FastAPI backend, and React browser client.
- The IP camera/VMS network is the input source, not another software component.
- The engine sends authenticated HTTP alert and heartbeat requests to the backend.
- The backend pushes events and status changes to browsers over WebSocket.
- The browser uses REST for ordinary reads and actions.
- SQLite is embedded storage owned by the backend, with WAL for concurrent reads and writes.
- The target deployment puts server-side services on one local edge host; browsers remain LAN clients.
- FastAPI and Uvicorn support asynchronous HTTP and persistent WebSocket connections.
- React, Zustand, and TanStack Query split rendered UI, live state, and REST cache work.
- The engine’s durable outbox protects detected events during a backend outage.
- REST recovery fills the browser’s active incident state after a socket disconnect.
- The 418-camera figure is a proposed target, not a proven production result.
