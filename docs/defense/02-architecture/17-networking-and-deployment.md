# 17 — Networking and deployment

> **One-liner:** The paper describes a localized CDRRMO production design; the tested demonstration used a separate private LAN with simulated RTSP cameras.
> **Panel risk:** high — confusing the target design with the demonstration can turn a proof of concept into an unsupported live deployment claim.

## 1. What it is

Networking and deployment describes where the application components sit and which devices are allowed to talk to each other.

There are two different topologies to defend:

- **Target production:** an edge server would be installed inside the Lipa CDRRMO command center, connected to the agency network and the Dahua DSS Pro media gateway.
- **Demonstration actually used:** a Linux laptop publishes simulated RTSP streams, a Windows laptop runs the ADAS stack, and a third laptop opens the browser dashboard.

The first is the paper’s intended production design. The second is the test and demo network. The CDRRMO design has not been installed as a completed live rollout.

The safest opening sentence is: **“Our target is on-premises at CDRRMO; our evaluation ran on researcher-controlled hardware in a private LAN using simulated feeds.”**

That sentence keeps the deployment claim, test environment, and video source distinct.

### Keep the two registers separate

| Question                    | Intended CDRRMO production design                                  | Demonstration actually used                           |
| --------------------------- | ------------------------------------------------------------------ | ----------------------------------------------------- |
| Where does it run?          | A localized edge server inside the command center                  | A Windows ADAS laptop on a private Globe LAN          |
| Where does video come from? | The authorized main RTSP feed from the Dahua DSS Pro media gateway | MediaMTX and FFmpeg on a Linux VMS laptop             |
| Who uses the dashboard?     | Authorized command-center workstations                             | A browser-only operator laptop                        |
| What is proven?             | A deployment architecture and integration target                   | The tested networked application path and workflow    |
| What is not proven?         | A completed CDRRMO installation                                    | Production-scale operation or a live citywide rollout |

When a panel question switches from one column to the other, name the register before answering. “In the target design…” is the right opening for a VLAN or Dahua question; “In the demonstration…” is the right opening for a port, DHCP, or simulator question.

## 2. Where it lives

### In the paper

- **Chapter 1, Technical Scope:** the architecture is designed for local, on-premises edge deployment, while the proof of concept is evaluated on researcher-controlled hardware.
- **Chapter 1, Scope and Delimitations:** ADAS is an independent proof-of-concept layer; it does not integrate its user interface with, modify, or administer the CDRRMO’s Dahua DSS Video Management System.
- **Chapter 3, Deployment Architecture:** the paper separates the localized evaluation environment from the target CDRRMO production architecture.
- **Chapter 3, Figure 33, “Network Architecture Diagram” (p. 160):** the target command-center network and its four planned VLANs.
- **Chapter 3, Figure 34, “Deployment Architecture Diagram” (p. 161):** cameras and VMS feed the local edge server; operator and administrator workstations access the application as clients.
- **Chapter 3, Network Configuration and Main RTSP Feed Ingestion (pp. 162–165):** planned server placement, cross-VLAN client access, the authorized main feed from the Dahua DSS Pro media gateway, and the intended internet-independent local path.

### In the test plan and tracker

- **Capstone Test Execution and Validation Plan, Purpose:** testing ran on one Windows ADAS host within a private three-device LAN; the record does not establish production-scale capacity or a completed live CDRRMO deployment.
- **Test plan, Test Environment and Network Configuration:** the Linux VMS simulator publishes RTSP, Windows runs the ADAS application and AI, and the browser-only operator laptop uses HTTPS/WSS. It records DHCP-reserved venue addresses, TCP ports 8554, 8000, and 5173, and the operator’s lack of RTSP access.
- **Tracker, Security Testing, TC-SEC-025 / NFR-20 Data Localization:** marked Pass with a qualification. The observation was limited to loopback connections during a controlled backend health and operational-request simulation; full packet capture across every workflow and backup activity was outside that run.
- **Tracker, Summary:** records formal UAT acceptance. Read that as acceptance of the evaluated project scope, not as a production go-live.

The plan also states that the application and AI components ran on one Windows ADAS host within a private three-device LAN, and that the record does not establish production-scale capacity or a completed live CDRRMO deployment. Its Network Configuration table gives the roles, port numbers, DHCP-reserved addressing, and isolation rule used for the remote-VMS run. Those are the references for the demonstration details below.

The paper’s Chapter 3 deployment section is the reference for the production intent. The test plan and tracker are the references for what was tested and how that evidence is qualified. The simulator runbook supplies the operational steps that make the three-device path repeatable.

### In the code

- **backend/app/core/config.py:76** defines the local development RTSP template. The remote VMS address is supplied through configuration for the LAN run.
- **backend/app/services/cameras.py:44** builds a camera’s RTSP address from the configured template and channel ID.
- **ai_engine/camera.py:157** owns the RTSP reader loop; failed opens and dropped reads move the stream into reconnect handling.
- **scripts/start-vms-sim.sh:1-24** starts the Linux-side MediaMTX process, while **mediamtx-vms.yml:5-17** selects TCP RTSP and disables unrelated public listeners for that simulator profile.
- **scripts/start-dev.ps1:442** starts the backend with TLS on port 8000 and a LAN-reachable bind address; **scripts/start-dev.ps1:456** starts the TLS frontend; **scripts/start-dev.ps1:474** points the AI engine back to the local backend.
- **frontend/vite.config.ts:19** enables the TLS frontend profile when the certificate directory is set.
- **frontend/src/utils/env.ts:22** builds the REST base URL from the browser hostname; **frontend/src/utils/env.ts:26** selects WSS when the page is HTTPS.
- **frontend/src/components/RealtimeAlertsBridge.tsx:235** starts dashboard recovery after WebSocket readiness; **backend/app/api/routes/alerts.py:254** documents the open-alert REST recovery query.

The operational wiring is documented in **docs/operations/VMS_SIMULATOR_SETUP.md**, especially sections 1, 2, 4.2, 5.4, 6.2, 6.3, 8.1, and 8.2. Those steps describe the demonstration LAN, not a deployed CDRRMO network.

## 3. How it works

### A. Target CDRRMO production topology

The paper positions the system on-premises: the edge server would sit inside the CDRRMO command center rather than sending camera video to a remote cloud service.

The target design is written for the agency’s 418-camera network, but that is a production design scale, not the scale demonstrated in the evaluation. The proof-of-concept evidence must stay attached to the tested LAN and stream profiles.

Figure 34 groups the application on that local edge server:

- The AI engine ingests the authorized camera feed and performs detection.
- The FastAPI application handles operator and administrator requests.
- SQLite stores the application records on the server.
- The web application is served to workstations on the internal LAN.

Figure 33 describes four planned network zones:

| Paper VLAN | Paper’s role                                                             |
| ---------- | ------------------------------------------------------------------------ |
| VLAN 50    | Core management and storage, including the planned edge inference server |
| VLAN 51    | Video processing and archival equipment such as NVRs and decoders        |
| VLAN 52    | The edge surveillance camera network                                     |
| VLAN 60    | Operations workstations used by command-center personnel                 |

The paper’s intended route keeps video processing local and uses planned cross-VLAN routing for authorized operator clients. The edge server is shown on the command-center core network; the paper describes Router-on-a-Stick routing for REST and WebSocket traffic from the server to operator terminals.

The paper’s production integration target is the **authorized main RTSP feed from the Dahua DSS Pro media gateway**. The edge server is designed as a headless VMS client: it requests the approved main stream from the gateway rather than polling each physical camera directly.

The exact production RTSP connection details and credentials would be confirmed during approved deployment configuration and validation. The paper does not give a live production URL for the main feed.

The localization argument is architectural: video ingestion, inference, database, API, and dashboard are planned to operate within the command center network. The paper says that a loss of the external ISP connection is designed not to stop local RTSP ingestion, AI inference, or intra-VLAN alert delivery.

#### Production data path, step by step

1. The authorized VMS gateway exposes the main stream for the edge server to request.
2. The edge server receives the RTSP stream and runs the AI engine locally.
3. The AI engine sends detection events to the co-located FastAPI backend.
4. The backend stores incidents and snapshots locally in SQLite and serves the compiled dashboard.
5. Authorized operator workstations receive REST responses and WebSocket alerts through the planned internal routes.

The production design therefore has a local video path and a local alert path. It does not describe a cloud relay, a public camera URL, or a browser pulling raw RTSP directly from each camera. The paper’s deployment assumptions still require CDRRMO network authorization, a static address, credentials, and deployment validation before this path can be activated.

The edge server is a headless VMS client. “Headless” means it requests the authorized media gateway stream without replacing the VMS interface or administering the physical camera estate. Camera maintenance, repair, and bandwidth management remain agency responsibilities in the paper’s target design.

### B. Three-device demonstration topology actually used

The test plan and VMS simulator setup describe this private LAN:

| Device              | Role in the demonstration                                                                                               |
| ------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| Linux VMS laptop    | MediaMTX and FFmpeg publish selected prerecorded traffic clips as RTSP feeds.                                           |
| Windows ADAS server | Runs the backend, frontend, and AI engine; reads the Linux RTSP feeds.                                                  |
| Operator laptop     | Browser-only client; opens the ADAS dashboard and does not run the repository, MediaMTX, FFmpeg, model, or RTSP reader. |

All three devices use the same private Globe LAN. The router supplies DHCP reservations; the runbook binds each device’s MAC address to its venue address so the endpoint stays predictable between sessions.

No actual venue IP values are needed to understand the design. The setup uses the reserved VMS and ADAS addresses in the RTSP template and firewall allow rule, and maps the reserved ADAS address to the stable hostname adas.local on the operator laptop.

The runbook’s current deployment record lists one reservation for each device and records the corresponding MAC address. The important defense point is the binding, not memorizing a session-specific address: the VMS address must stay stable for the RTSP template, the ADAS address must stay stable as the firewall source and hostname target, and the operator address must remain a known LAN client. If the router changes the lease, the source allow rule or the hosts-file mapping can point at the wrong device.

#### Node responsibilities

- **Linux VMS laptop:** starts MediaMTX and FFmpeg, publishes the selected prerecorded clips, listens on the RTSP port, and accepts that port only from the reserved ADAS source.
- **Windows ADAS server:** reads RTSP, runs the AI engine, hosts FastAPI and SQLite, serves the TLS dashboard, and accepts browser traffic on the two application ports.
- **Operator laptop:** runs a supported browser, resolves `adas.local`, trusts the public certificate, and uses the dashboard. It has no repository checkout, model, MediaMTX process, FFmpeg publisher, or RTSP reader.

This division lets the team isolate failures. A failed VMS check is a source or RTSP problem; a failed localhost health check is an ADAS host problem; a failed operator check is a browser, certificate, hostname, or Windows inbound-rule problem.

#### Port direction and payload

| Link             | TCP connection is initiated by | Destination listener          | Payload and use                                                                       |
| ---------------- | ------------------------------ | ----------------------------- | ------------------------------------------------------------------------------------- |
| RTSP camera path | Windows ADAS server            | Linux VMS, TCP 8554           | The Linux VMS supplies video to the ADAS reader over the established RTSP connection. |
| API and alerts   | Operator browser               | Windows ADAS server, TCP 8000 | HTTPS REST calls and the secure WebSocket alert channel.                              |
| Dashboard        | Operator browser               | Windows ADAS server, TCP 5173 | The HTTPS dashboard frontend.                                                         |

The RTSP direction is easy to say imprecisely. **The VMS publishes the stream, but the ADAS server initiates the TCP connection to the VMS listener.** The video content then travels from Linux to Windows over that connection.

For the operator, the direction is simpler: the browser makes HTTPS/WSS connections to the Windows server on the dashboard and API ports. The browser does not request an RTSP stream.

The end-to-end sequence is therefore:

1. FFmpeg publishes a clip into MediaMTX on Linux.
2. The AI engine on Windows opens the configured RTSP URL to the Linux listener.
3. Frames travel over the established RTSP/TCP session to the Windows reader.
4. Detection and alert state stay on the ADAS host until the backend sends application data to the browser.
5. The browser receives dashboard data over HTTPS and alert events over WSS; it never receives the camera stream.

The word “publishes” describes the VMS-side media action. The word “initiates” describes the TCP connection owner. Keeping those terms separate avoids claiming that the Linux publisher actively pushes an unsolicited stream to the operator or that the browser is a camera client.

#### DHCP reservations and firewalls

The router’s DHCP reservation table pins a lease to each device’s wired MAC address. This gives the VMS a stable address for the Windows RTSP template, the ADAS server a stable source address for the VMS firewall, and the operator a stable destination for the adas.local mapping.

On Linux, UFW denies incoming traffic by default and allows TCP 8554 only from the reserved Windows ADAS server address. This permits the intended RTSP reader and rejects RTSP attempts from the operator device.

On Windows, the runbook adds inbound TCP rules for ports 8000 and 5173 on the Private network profile. Those rules let the operator reach the API/WebSocket service and dashboard; port 8554 is not an operator-facing Windows service.

The runbook keeps the router in private-LAN mode and does not use port forwarding or a DMZ. The demo services are not exposed to the public internet.

The firewall policy is least privilege at the topology level:

| Policy                     | Allowed path                              | Deliberately denied path                                          |
| -------------------------- | ----------------------------------------- | ----------------------------------------------------------------- |
| RTSP source                | Windows ADAS → Linux VMS listener         | Operator → Linux VMS RTSP listener                                |
| Application API and alerts | Operator browser → Windows ADAS port 8000 | Public-internet clients through the router (no forwarding or DMZ) |
| Dashboard                  | Operator browser → Windows ADAS port 5173 | Direct browser access to the VMS service                          |

The Windows rules are inbound rules for the server’s Private profile. They are not an identity-aware allowlist for one operator; the demo relies on the private LAN and the browser-only role, while the Linux UFW rule provides the explicit RTSP source restriction. The Windows rules do not make the camera stream public, and both sides matter: Windows must be reachable for the application, while Linux must reject an unauthorized RTSP client.

#### Hostname and certificate trust

The operator laptop maps **adas.local** to the current reserved address of the Windows ADAS server. The browser uses the hostname rather than the router-assigned numeric address so it matches the certificate name.

The Windows server presents a self-signed certificate for adas.local. The operator receives only the public certificate and installs it in the trusted root store; the private key stays on the Windows server.

The operator opens the dashboard at **https://adas.local:5173**. The browser then uses HTTPS for the API and WSS for alert delivery through **adas.local:8000**. Trusting the certificate is part of the connection setup; clicking through a browser warning is not the intended procedure.

The trust sequence is: map `adas.local` to the reserved Windows address, install only `adas-cert.pem` in the operator’s trusted root store, restart the browser if required, then open `https://adas.local:5173`. The frontend derives its API host from the browser hostname and chooses `wss:` when the page protocol is HTTPS (`frontend/src/utils/env.ts:21-27`). A click-through exception is not equivalent to installing trust and can leave secure cookies or the alert channel unreliable.

#### Why RTSP is denied to the operator laptop

Only the Windows ADAS host needs raw video so the AI engine can ingest and analyze the selected feeds. The operator’s role is to review alerts, snapshots, and incident details in the browser.

The firewall expresses that division directly: one authorized consumer reads the simulated RTSP feeds; the browser reaches only the application. This avoids turning the operator laptop into a second VMS client and keeps the evaluation path focused on the ADAS server’s stream ingest.

In the paper’s intended operation, the ADAS dashboard is separate from the existing Dahua VMS interface. Operators can use the agency’s live CCTV view as context; ADAS does not replace or administer that VMS.

#### If a network link drops

An external internet or ISP loss is different from a break inside the private LAN. The production paper’s design expects local VMS, AI, and intra-VLAN alert traffic to continue during external ISP loss.

If the VMS-to-ADAS link drops, that camera has no new frames to analyze while disconnected. The AI stream reader retries the connection and reports a reconnecting or unresponsive status; it cannot reconstruct frames that were not received.

The test plan’s network-fault criterion is an attempted reconnection within 10 seconds of camera-stream disconnection. That criterion measures the recovery attempt; it does not claim that the missing interval is replayed or that an operator decision can be completed while the internal path is down.

If the operator-to-ADAS link drops, the browser temporarily loses live dashboard and WebSocket updates. The WebSocket reconnect path then asks the backend for current Unverified and Ongoing alerts to rebuild the open-alert state.

The defensible answer is segment-specific: the design tolerates loss of the external ISP, while a broken internal RTSP or operator link interrupts that path until connectivity returns.

| Failure                                 | What stops                             | What the system can do next                                      |
| --------------------------------------- | -------------------------------------- | ---------------------------------------------------------------- |
| External ISP loss, internal LAN healthy | Remote internet access                 | Continue the localized production path described in the paper    |
| Linux VMS → Windows RTSP path loss      | New frames for the affected camera     | Reader retries; no missing frames can be reconstructed           |
| Windows server process failure          | Inference, API, and dashboard together | Requires host/service recovery before alerts resume              |
| Windows → operator path loss            | Browser view and live WSS updates      | Browser reconnects and reloads open `Unverified`/`Ongoing` state |

That last recovery is application-state recovery, not video recovery. The frontend fetches current open alerts after a WebSocket reconnect, as documented in `frontend/src/components/RealtimeAlertsBridge.tsx:235-255` and `backend/app/api/routes/alerts.py:254-259`. It cannot show a frame that the server never received during an RTSP outage.

## 4. Why it was built this way

### Keep compute and data inside the command center

The CDRRMO production design is an edge design. Keeping video ingestion, inference, the database, and operator alert traffic inside the agency network supports local handling and avoids depending on a remote cloud round trip for the main detection path.

That placement also supports the paper’s stated internet-independence goal: external ISP loss should not prevent local processing when the internal CCTV and operations network remains available.

### Request from the VMS gateway

The production edge server is designed to request an authorized main stream from Dahua DSS Pro. That gives CDRRMO a controlled integration point through its VMS rather than having ADAS query physical cameras one by one.

It also keeps authorization and camera infrastructure management with the agency. ADAS consumes a configured feed; it does not manage the city’s cameras or replace the VMS.

### Simulate feeds without interrupting dispatch

The paper says testing was isolated from live production servers and active emergency dispatch. MediaMTX and prerecorded clips still create network RTSP traffic, so the team can exercise feed ingest, decoding, buffering, and the alert workflow without consuming the live operational camera path.

Using the remote Linux VMS also makes the roles visible: a publisher, an inference/application host, and a separate browser client. This is a realistic network path for the demo while remaining a controlled proof-of-concept environment.

### Give each device only the access it needs

The AI host needs RTSP; the operator browser needs the web application. The Linux source firewall and Windows inbound rules enforce that split instead of relying on the operator to avoid the camera stream.

The private LAN and absence of router port forwarding keep the demonstration endpoints local to the test network. DHCP reservations make the firewall source address and browser hostname mapping repeatable.

### Use a hostname that matches the TLS certificate

The certificate is issued for adas.local, so the browser connects with that name. A stable DHCP reservation plus the operator’s hostname mapping makes the certificate identity usable even though the LAN’s addresses come from the router.

Trusting the server certificate on the operator laptop allows the browser to use HTTPS and WSS without a certificate warning. The runbook keeps the private key on the ADAS server.

### Make the demonstration repeatable without changing the production claim

DHCP reservations, a named certificate, and an explicit source firewall rule turn a temporary LAN into a repeatable test fixture. They make endpoint identity stable between sessions while preserving the boundary that the demo is researcher-controlled. They do not grant the team authority to connect to CDRRMO’s CCTV VLAN, and they do not stand in for the agency’s production credentials or route approval.

### Why not let every browser view RTSP?

That would add a second class of video client, duplicate ingest responsibility, and make the panel’s “what did the AI actually analyze?” answer less clear. The chosen path has one raw-video consumer—the ADAS server—and one application consumer—the browser. Operators still use the dashboard for alerts and can cross-check the separate agency VMS view in the intended production workflow.

## 5. What changed since the 28 April defense

The repository history shows a repeatable remote Linux VMS simulator workflow added after the April defense: commit 38e5d54 adds the remote MediaMTX setup, followed by b379d43 to make simulation configuration selectable.

The current runbook now makes the three-device demonstration path explicit, including RTSP direction, DHCP reservations, the RTSP source allow rule, the Windows dashboard rules, and operator certificate trust.

This is a demonstration and reproducibility improvement. It does not mean that the proposed CDRRMO production topology has been installed.

The meaningful change since April is the documented remote-VMS path: the simulator can live on Linux, while the Windows host remains the application and inference host and the third machine remains browser-only. The runbook records the bring-up order and the checks that distinguish a broken source, a broken server, and a broken client. The target production architecture remains a plan requiring CDRRMO authorization and post-capstone implementation.

## 6. Limits and honest caveats

- **No live CDRRMO rollout is claimed.** The paper calls the project a proof of concept; the test plan says the record does not establish production-scale capacity or a completed live deployment.
- **The CDRRMO network drawing is a target design.** VLAN placement, VMS authorization, static addressing, credentials, and final route rules depend on agency approval and deployment validation.
- **The demo feed is simulated.** Linux MediaMTX and FFmpeg replay selected prerecorded clips; the demo is not a live pull from the city’s production Dahua DSS Pro gateway.
- **The demo network is not the production network.** A private venue LAN with DHCP reservations demonstrates the application path, not the agency’s actual CCTV VLAN or its operational network policies.
- **Formal UAT acceptance is not a go-live record.** The tracker records acceptance of the completed evaluation; that does not convert the proof of concept into a completed production deployment.
- **Localization evidence is qualified.** Tracker case TC-SEC-025 is marked Pass for the controlled health and operational-request simulation, where only loopback connections were observed. Full packet capture across every workflow and backup activity was outside that run.
- **Camera capacity remains qualified.** The test plan reports simulated 8-, 9-, and 10-stream profiles and says fifteen-camera qualification is deferred; these results do not demonstrate the paper’s target citywide camera network.
- **The browser is not the live video client.** The operator laptop is intentionally denied RTSP. The current ADAS dashboard supports alert review; production use assumes a separate CDRRMO live CCTV view for visual cross-checking.
- **Internal network loss still matters.** The paper’s ISP-independence statement applies when the internal network remains functional. A broken VMS-to-server link stops new frames for that camera; a broken operator link interrupts live browser updates until reconnection.

### Phrases to use precisely

| Supported wording                                                                  | Wording to avoid                                              |
| ---------------------------------------------------------------------------------- | ------------------------------------------------------------- |
| “The target is an on-premises CDRRMO edge deployment.”                             | “ADAS is already deployed at CDRRMO.”                         |
| “The evaluation used a private three-device LAN with simulated RTSP.”              | “The city’s live cameras were tested end to end.”             |
| “The main production feed is the authorized Dahua DSS Pro RTSP feed.”              | “The prototype directly controls the city cameras.”           |
| “The tracker records a qualified localization result.”                             | “The tracker proved that no data can ever leave the network.” |
| “The ISP-loss design assumes the internal command-center network remains healthy.” | “The system survives any network outage.”                     |

The qualification is part of the answer, not an afterthought. The tracker’s TC-SEC-025 result supports local handling for the controlled health and operational-request simulation; it did not include full packet capture across every workflow and backup activity.

Do not say “the whole system is proven to stay operational during any network outage.” The supported statement is narrower: local production traffic is designed to survive loss of the external ISP, while internal links remain dependencies.

## 7. Likely panel questions

### “Is this deployed at CDRRMO right now?”

No. The paper describes the CDRRMO installation as the target production design; the completed evaluation ran on researcher-controlled hardware in a private LAN with simulated feeds. We do not claim a completed live CDRRMO rollout.

### “Why simulate the cameras instead of using real ones?”

The team needed a real RTSP network path but could not risk disrupting live command-center monitoring or dispatch. MediaMTX replayed prerecorded clips so the server still had to ingest and decode network streams in a repeatable test.

### “What changes when you move to real CCTV?”

The authorized RTSP source changes from the simulator to the approved Dahua DSS Pro main feed, and CDRRMO must provide the approved network access, credentials, address, and validation conditions. The server then needs deployment testing on that network for stream compatibility, stability, security, and capacity.

### “Why is the operator laptop blocked from RTSP?”

The Windows ADAS host is the only device that needs raw RTSP for inference. The operator uses the secure dashboard and its alerts; the Linux firewall allows the RTSP port only from the reserved ADAS server address.

### “What happens if the network drops mid-incident?”

If only the external ISP fails, the paper’s localized production design expects internal camera ingest and alert delivery to continue. If an internal link fails, the affected path is interrupted: the camera reader retries a lost RTSP feed, and the browser rebuilds open alert state after its WebSocket reconnects.

### “If the tracker says accepted, why isn’t it deployed?”

Acceptance records the UAT result for the tested scope. The test plan explicitly says those results do not establish production-scale capacity or a completed live CDRRMO deployment.

### “Why put it on-premises instead of in the cloud?”

The paper places the AI engine, database, API, and web application on a physical edge server inside the command center. That keeps the main video and alert path local and supports operation without the external ISP when the internal network is healthy.

### “Does the localization test prove no data can ever leave the network?”

No. TC-SEC-025 passed for a controlled backend health and operational-request simulation that observed only loopback connections. The tracker says full packet capture across every workflow and backup activity was outside that run.

### “Does the demo prove the server can read the full city camera network?”

No. The paper shows a target production architecture; the test plan records simulated 8-, 9-, and 10-stream profiles and defers fifteen-camera qualification. Do not present those results as validation of the full CDRRMO network.

### “Why does the test plan say the VMS publishes to ADAS, while the connection table points ADAS to the VMS?”

Those describe different directions. MediaMTX publishes the video, but the ADAS server opens the TCP connection to the VMS RTSP listener; the video then flows back to the ADAS reader over that connection.

### “Which address does the operator use, and why not the numeric server address?”

The operator uses `https://adas.local:5173`, with `adas.local` mapped to the DHCP-reserved Windows address. The certificate is issued for that hostname, so using the name keeps hostname resolution and certificate identity aligned.

### “What has to be approved before this can go live?”

CDRRMO must authorize the edge server’s connection to the core switches and CCTV network, provide the approved VMS credentials and feed details, and validate route, stream, security, and capacity conditions. The paper treats pilot activation, scaling, handover, training, retraining, and hardware maintenance as post-capstone implementation work.

### “What exactly does the tracker’s localization Pass prove?”

It supports local handling for the controlled backend health and operational-request simulation, where only loopback process connections were observed. It does not prove a full packet-capture result for every detection, dashboard, export, and backup workflow.

## 8. Cram summary

- Keep two topologies separate: proposed CDRRMO production and the tested three-device private LAN.
- Production means a local edge server in the Lipa CDRRMO command center, with the application and data on-premises.
- The intended production video source is the authorized main RTSP feed from the Dahua DSS Pro media gateway.
- Figure 33 shows VLAN 50, 51, 52, and 60 roles; Figure 34 shows the local edge server and browser clients.
- The demo uses Linux MediaMTX/FFmpeg, a Windows ADAS host, and a browser-only operator laptop.
- TCP 8554 is RTSP: Windows initiates the connection to Linux; the video comes from Linux.
- TCP 8000 carries HTTPS API and WSS alerts; TCP 5173 serves the HTTPS dashboard.
- DHCP reservations stabilize the three demo devices; UFW limits RTSP to the Windows host; Windows firewall rules open the dashboard/API ports.
- The operator maps adas.local to the server, trusts the server’s public certificate, and never gets RTSP access.
- Tracker acceptance and a qualified localization Pass do not establish a live CDRRMO rollout or citywide camera capacity.
- If asked whether it is deployed live, answer: **No. It is a proof of concept evaluated in a private LAN; CDRRMO deployment remains the target design.**
