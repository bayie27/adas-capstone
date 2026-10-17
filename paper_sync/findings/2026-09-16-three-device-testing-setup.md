---
section: Testing and Validation
page/s: "pp. 187–191 (live TOC; fresh PDF export unavailable)"
required_revision: Distinguish three-device technical/system network testing from single-laptop participant-facing UAT
notes: Technical/system testing used a Linux VMS simulator, Windows ADAS server, and separate browser-only operator laptop over HTTPS/WSS. Participant-facing UAT used a single-laptop evaluation environment. Cached rendered pages were inspected, but the current PDF export endpoint returned 403.
status: In progress
assigned_to: Daniboy
synced: false
---

## Changes

### 1. Defense paper — Testing Strategy Overview

Page/s: p. 187 (live TOC page hint; native range `t.y7ms6bhlk4qn:225457–226567`; cached rendered equivalent on p. 184)

#### Change metadata

Operation: replace
Scope: logical paragraph
Changed target: the complete Testing Strategy Overview paragraph beginning "The testing strategy employed..."
Preserve: the phased evaluation rationale, production-safety boundary, VMS-simulation purpose, and the section's narrative order
Comment target: the complete new logical paragraph; resolve native indexes after replacement

#### OLD

> The testing strategy employed a phased, hybrid evaluation approach to validate both standard web application stability and computationally intensive machine learning operations. To eliminate any risk of impacting the Lipa CDRRMO’s live production servers or disrupting active emergency dispatch processes, all testing was conducted exclusively within a controlled, isolated LAN staging environment. A key element of this strategy was the high-fidelity simulation of the command center’s enterprise VMS architecture. Instead of evaluating the computer vision model with static, local video files, an open-source RTSP media gateway (MediaMTX) was implemented to replicate the behavior of the CDRRMO’s VMS. By broadcasting benchmark traffic footage through this proxy, the AI edge server was required to ingest, decode, and process live network streams. This approach ensured that the system's network protocols, hardware limitations, and AI ingestion buffers were thoroughly validated under the precise physical constraints of the intended deployment environment, without jeopardizing the city's live operations.

#### NEW

The testing strategy employed a phased, hybrid evaluation approach to validate both standard web application stability and computationally intensive machine learning operations. To eliminate any risk of impacting the Lipa CDRRMO’s live production servers or disrupting active emergency dispatch processes, technical and system-level network testing used a controlled, isolated three-device LAN staging environment. The setup separated video-source simulation, ADAS processing, and operator access: a Linux VMS laptop ran MediaMTX and FFmpeg to publish prerecorded RTSP feeds; a Windows ADAS server ran the AI engine, FastAPI backend, SQLite database, and React frontend; and a browser-only operator laptop accessed the dashboard over HTTPS/WSS. Instead of evaluating the computer vision model with static, local video files, the Linux VMS laptop rebroadcast benchmark traffic footage through MediaMTX, requiring the Windows ADAS server to ingest, decode, and process live network streams while the operator laptop exercised the browser path. This approach ensured that the system’s network protocols, hardware limitations, and AI ingestion buffers were validated within the physical constraints of the intended deployment environment, without jeopardizing the city’s live operations. Participant-facing UAT was conducted separately in a single-laptop evaluation environment; offline and archival evaluation methods remain qualified separately in the applicable results.

#### Evidence

The live defense paper is `Group7_Capstone Project Defense Document - ITCAPROJ2`, read on 2026-09-16 at revision `ANLCKQnYZzduyxFf4ed_c5ymsMgs7EtwqcpUSxjGjPUN9HCc__l2Nkci1qpTtrFdVAk2mU2XYBD_JDHK0z8nIRQ0vp8hn3ugoc9MumU1mbM`. The current paper paragraph is in the main tab `t.y7ms6bhlk4qn` at native range `225457–226567`.

`docs/operations/VMS_SIMULATOR_SETUP.md:1-8, 26-45` establishes the three-device topology: a Linux VMS laptop runs MediaMTX and FFmpeg, the Windows ADAS server reads RTSP from Linux, and the operator browser reads HTTPS/WSS from Windows. The same runbook states that the operator laptop never connects to RTSP. `mediamtx-vms.yml:1-5` and `scripts/start-vms-sim.sh:1-24` establish the dedicated Linux-side simulator entry point. This is a documentation drift correction; it does not claim a live CDRRMO deployment.

`paper_sync/findings/2026-09-16-chapter4-results-framing.md:318-320` records the user-confirmed single-laptop participant-facing UAT setup and distinguishes it from tri-device technical tests. This finding therefore limits the three-device claim to technical/system network testing rather than applying it to all evaluation activity.

#### Proposed comment (same gate as replacement)

Comment scope: logical paragraph; the complete revised Testing Strategy Overview paragraph

Previous (marked, intentionally non-verbatim): The testing strategy employed a phased, hybrid evaluation approach to validate both standard web application stability and computationally intensive machine learning operations. To eliminate any risk of impacting the Lipa CDRRMO’s live production servers or disrupting active emergency dispatch processes, all testing was conducted exclusively within a [[controlled, isolated LAN staging environment]]. A key element of this strategy was the high-fidelity simulation of the command center’s enterprise VMS architecture. Instead of evaluating the computer vision model with [[static, local video files]], an open-source RTSP media gateway (MediaMTX) was implemented to replicate the behavior of the CDRRMO’s VMS. By broadcasting benchmark traffic footage through this proxy, the [[AI edge server]] was required to ingest, decode, and process live network streams. This approach ensured that the system's network protocols, hardware limitations, and AI ingestion buffers were thoroughly validated under the precise physical constraints of the intended deployment environment, without jeopardizing the city's live operations.

Codex ID: PS-20260916-THREE-DEVICE-TESTING-SETUP

Done by Codex.

### 2. Defense paper — Table 23, Test Environment Summary, RTSP-simulation item label

Page/s: p. 189 (live TOC page hint; native range `t.y7ms6bhlk4qn:228046–228061`; cached rendered equivalent on p. 186)

#### Change metadata

Operation: replace
Scope: span
Changed target: the item label `RTSP Simulation`
Preserve: the table row placement and formatting; the description cell is updated in block 3
Comment target: the replacement item label

#### OLD

> RTSP Simulation

#### NEW

Linux VMS Laptop

#### Evidence

The live table label is `t.y7ms6bhlk4qn:228046–228061`. `docs/operations/VMS_SIMULATOR_SETUP.md:1-8, 154-260` establishes that MediaMTX and FFmpeg run on a separate Linux VMS laptop. The row label should identify that device directly; block 3 updates the paired description cell with its simulator role and network relationship.

#### Proposed comment (same gate as replacement)

Comment scope: span; OLD `RTSP Simulation`; NEW `Linux VMS Laptop`

Previous: RTSP Simulation

Codex ID: PS-20260916-THREE-DEVICE-TESTING-SETUP

Done by Codex.

### 3. Defense paper — Table 23, Test Environment Summary, Linux VMS description

Page/s: p. 189 (live TOC page hint; native range `t.y7ms6bhlk4qn:228063–228203`; cached rendered equivalent on p. 186)

#### Change metadata

Operation: replace
Scope: logical paragraph
Changed target: the `Linux VMS Laptop` description cell
Preserve: the RTSP-simulation purpose and the table's row formatting
Comment target: the complete revised cell text

#### OLD

> MediaMTX locally rebroadcasts fifteen distinct prerecorded videos as ten simultaneous RTSP streams, with active AI inference on all streams.

#### NEW

Runs MediaMTX and FFmpeg to rebroadcast prerecorded traffic videos as RTSP streams to the Windows ADAS server. The ADAS server performs active AI inference on the configured concurrent streams; the browser-only operator laptop does not access RTSP.

#### Evidence

The live table cell is `t.y7ms6bhlk4qn:228063–228203`. `docs/operations/VMS_SIMULATOR_SETUP.md:3-8, 26-45, 154-260` places MediaMTX and FFmpeg on the Linux VMS laptop, uses the Windows ADAS server as the RTSP client, and explicitly restricts port 8554 so the operator laptop cannot reach it. The revised row deliberately does not change the separate ten-stream performance profile stated later in the section; it identifies the Linux laptop as the VMS/simulation device and states which device exercises each path.

#### Proposed comment (same gate as replacement)

Comment scope: logical paragraph; the complete revised `Linux VMS Laptop` description cell

Previous: MediaMTX locally rebroadcasts fifteen distinct prerecorded videos as ten simultaneous RTSP streams, with active AI inference on all streams.

Codex ID: PS-20260916-THREE-DEVICE-TESTING-SETUP

Done by Codex.

### 4. Defense paper — Table 23, Test Environment Summary, network description

Page/s: p. 189 (live TOC page hint; native range `t.y7ms6bhlk4qn:228215–228409`; cached rendered equivalent on p. 186)

#### Change metadata

Operation: replace
Scope: logical paragraph
Changed target: the `Network` description cell
Preserve: data-localization intent, transport-security claim, and the table's row formatting
Comment target: the complete revised cell text

#### OLD

> Two-node wired Ethernet segment (192.168.50.1 / 192.168.50.2) via direct Cat5e cable, enforcing data localization. Transport security via HTTPS/WSS with a self-signed certificate for adas.local.

#### NEW

Three-device private LAN through the same Globe router, connecting the Linux VMS simulator, the Windows ADAS server, and the browser-only operator laptop. RTSP traffic on port 8554 runs between the Windows ADAS server and the Linux VMS simulator; the operator laptop reaches the dashboard over HTTPS/WSS on ports 8000 and 5173. Transport security uses a self-signed certificate for adas.local, and no service is exposed to the internet.

#### Evidence

The live table cell is `t.y7ms6bhlk4qn:228215–228409`. `docs/operations/VMS_SIMULATOR_SETUP.md:26-45` defines the three-device flow and ports; `:51-64` records the current Globe deployment addresses; `:71-80` requires all three devices on the same private LAN; and `:432-452` validates the router, VMS, server, and operator layers in order. The replacement omits hard-coded addresses because the runbook treats them as venue-specific DHCP reservations while preserving the paper's data-localization and HTTPS/WSS claims.

#### Proposed comment (same gate as replacement)

Comment scope: logical paragraph; the complete revised `Network` cell

Previous: Two-node wired Ethernet segment (192.168.50.1 / 192.168.50.2) via direct Cat5e cable, enforcing data localization. Transport security via HTTPS/WSS with a self-signed certificate for adas.local.

Codex ID: PS-20260916-THREE-DEVICE-TESTING-SETUP

Done by Codex.

### 5. Defense paper — Types of Testing Conducted, System / End-to-End Testing

Page/s: p. 190 (live TOC page hint; native range `t.y7ms6bhlk4qn:229769–230182`; cached rendered equivalent on p. 187)

#### Change metadata

Operation: replace
Scope: logical paragraph
Changed target: the complete `System / End-to-End Testing` paragraph
Preserve: the workflow sequence, real-network qualification, TLS qualification, and browser qualification
Comment target: the complete revised logical paragraph

#### OLD

> System / End-to-End Testing. This phase verified complete operator workflows against the fully deployed system running across the two-node test network—from a collision occurring in a video stream through detection, alert delivery, snapshot rendering, operator verification, and incident resolution. This was the first activity that exercised the real network path, the real TLS configuration, and a real browser.

#### NEW

System / End-to-End Testing. This phase verified complete operator workflows against the fully deployed system running across the three-device test network—from a collision occurring in a video stream on the Linux VMS simulator through RTSP ingestion and AI detection on the Windows ADAS server to alert delivery, snapshot rendering, operator verification, and incident resolution in the browser client. This was the first activity that exercised the real network path between the simulator and ADAS server, the real TLS configuration, and a real browser on a separate device.

#### Evidence

The live paragraph is `t.y7ms6bhlk4qn:229769–230182`. `docs/operations/VMS_SIMULATOR_SETUP.md:34-45` defines the directional RTSP and HTTPS/WSS paths, and `:432-452` defines the end-to-end validation sequence from Linux VMS through Windows ADAS to the operator browser. The replacement keeps the existing workflow claims and changes only the topology that the test actually exercises.

#### Proposed comment (same gate as replacement)

Comment scope: logical paragraph; the complete revised `System / End-to-End Testing` paragraph

Previous (marked, intentionally non-verbatim): System / End-to-End Testing. This phase verified complete operator workflows against the fully deployed system running across the [[two-node test network]]—from a collision occurring in a [[video stream]] through detection, alert delivery, snapshot rendering, operator verification, and incident resolution. This was the first activity that exercised the [[real network path]], the real TLS configuration, and a real browser.

Codex ID: PS-20260916-THREE-DEVICE-TESTING-SETUP

Done by Codex.

### 6. Defense paper — User Acceptance Testing, staging-environment paragraph

Page/s: p. 191 (live TOC page hint; native range `t.y7ms6bhlk4qn:233104–233332`; cached rendered equivalent on p. 189)

#### Change metadata

Operation: replace
Scope: logical paragraph
Changed target: the complete UAT staging-environment paragraph
Preserve: the prohibition on testing live CDRRMO production servers and the Dahua DSS Pro simulation boundary
Comment target: the complete revised logical paragraph

#### OLD

> To maintain safety protocols, UAT was not conducted on the CDRRMO’s live production servers. Testing was performed within an isolated LAN staging environment, simulating the command center’s Dahua DSS Pro server’s media gateway.

#### NEW

To maintain safety protocols, UAT was not conducted on the CDRRMO’s live production servers. Participant-facing UAT used a single-laptop evaluation environment, with separate browser profiles for participant and administrator sessions. This usability evaluation was distinct from technical system testing, which used an isolated three-device LAN staging environment: a Linux laptop running MediaMTX and FFmpeg simulated the command center’s Dahua DSS Pro media gateway, the Windows ADAS server ran the application and AI components, and a separate browser-only operator laptop exercised the dashboard.

#### Evidence

The live paragraph is `t.y7ms6bhlk4qn:233104–233332`. `paper_sync/findings/2026-09-16-chapter4-results-framing.md:318-320` records the user-confirmed single-laptop UAT setup, including the distinction from tri-device technical tests. `docs/operations/VMS_SIMULATOR_SETUP.md:1-8, 154-260, 262-367, 368-430` establishes the separate three-device technical network procedure. The CDRRMO production-system exclusion remains unchanged.

#### Proposed comment (same gate as replacement)

Comment scope: logical paragraph; the complete revised UAT staging-environment paragraph

Previous: To maintain safety protocols, UAT was not conducted on the CDRRMO’s live production servers. Testing was performed within an isolated LAN staging environment, simulating the command center’s Dahua DSS Pro server’s media gateway.

Codex ID: PS-20260916-THREE-DEVICE-TESTING-SETUP

Done by Codex.

### 7. Tracker Sheet — `ADAS_Paper_Audit_Tracker`, `🚩 Action Stream!A87:H87`

#### Change metadata

Operation: insert
Scope: row
Changed target: the first fully blank row in the named `🚩 Action Stream` tab; current A1 range `A87:H87`
Preserve: occupied rows 1–86, existing formatting, validation, notes, and the manual `Reviewed by` cell H87
Comment target: exact newly inserted text colored orange (`#E67E22`); no Sheet comment

#### OLD

> The live bounded `userEnteredValue` read returned occupied rows through row 86; row 87 is the first fully blank append candidate. The current grid extends through row 99.

#### NEW

A87: Major  
B87: Testing and Validation  
C87: 187–191  
D87: Distinguish three-device technical/system network testing from single-laptop participant-facing UAT
E87: Linux VMS simulator feeds the Windows ADAS server; a separate browser-only operator laptop exercises HTTPS/WSS.  
F87: Not started  
G87: Daniboy  
H87: preserve blank

#### Evidence

Live tracker identity: `ADAS_Paper_Audit_Tracker`, spreadsheet `1iTt2K-t9Jyae-lqApCY0PX9N7HXCrKE850pvJLHzfoQ`. Metadata reports the canonical `🚩 Action Stream` tab as sheet ID `1620600289`, with 99 rows and 8 columns. The bounded `userEnteredValue` read of `🚩 Action Stream!A1:H99` returned occupied content through row 86; row 87 has no entered value. The candidate was re-read on 2026-09-16. The `Reviewed by` cell must remain blank.

#### Formatting fallback (same gate as replacement)

Color the newly inserted text in A87:G87 orange (`#E67E22`) using rich-text `textFormatRuns`; preserve H87 blank, existing row formatting, validation, and notes.

## Scope notes

- The separate live Test Execution and Validation Plan still contains its older two-node wording. It was not included in this user-scoped defense-paper update; updating that plan is a separate local/Drive target if requested.
- The existing Acer `Client Device` row is left unchanged; the third device is represented by the renamed `Linux VMS Laptop` row.
- The paper's separate ten-stream performance wording is preserved. This finding changes the physical placement and network path of the RTSP simulator, not the declared stream-count or inference configuration.
- No production CDRRMO installation, CCTV-VLAN integration, or citywide capacity claim is added.
- The cached 2026-09-14 PDF was rendered and visually inspected for the affected section. The live native paper was re-read on 2026-09-16, but the current PDF export endpoint returned HTTP 403 and the fallback signed file reference was expired before local download. The live TOC supplies the current page hints above; exact fresh rendered-page verification remains pending.

## Post-write verification — 2026-09-16

The approved six paper replacements were applied with a required revision guard and read back from the live native paper. The final document revision is `ANLCKQkFwDDu3ifwX6GdyBU1utM169OCp-ybWPkN6b8pfTmcr-UdGM8FuKv-9O32bPZZ6JBreJrFafx4ABn74EBONuxSnvvuMUdK1KZ_djQ`. The existing `Client Device` row remains unchanged. The six new passages occur exactly once in the main tab, and a fresh sweep found no remaining `two-node`, `RTSP Simulation`, `MediaMTX locally rebroadcasts`, `192.168.50.1`, `192.168.50.2`, or obsolete UAT-staging phrase in the paper.

The six attached replacement comments were created and read back as open, non-deleted comments with non-empty native anchors and the expected package ID. Provider IDs and anchors are: block 1 `AAACAmWsXjc` / `kix.ls9kb4l4cbf7`; block 2 `AAACAmWsXjg` / `kix.s4nspeg531e8`; block 3 `AAACAmWsXjk` / `kix.brkh20rjtfn7`; block 4 `AAACAmWsXjo` / `kix.itw7hl1o0rug`; block 5 `AAACAmWsXjs` / `kix.n7868oai0kvt`; block 6 `AAACAmWsXjw` / `kix.y7f0yflcuumw`. Each comment content ends with `Done by Codex.` and its provider quote matches the corresponding new passage (the connector truncates the long block-1 quote in its read response, while the anchored replacement range and exact text search were verified).

The approved tracker append was applied and read back at `🚩 Action Stream!A87:G87`. All seven new cell values are orange `#E67E22`; `H87` remains blank and its existing validation is present. No Sheet comment was created. A fresh PDF export still returns HTTP 403, so the cached-render page observations and live-TOC page hints remain the available page evidence; final fresh rendered-page QA is still pending.

## Approval / sync ledger

Package ID: PS-20260916-THREE-DEVICE-TESTING-SETUP
Approval source: User message on 2026-09-16, “alright approved for writing,” following the revised proposal that kept the Acer `Client Device` row unchanged and renamed the RTSP row to `Linux VMS Laptop`. Approval covered paper blocks 1–6, their attached comments, and tracker block 7.

| Target                   | Approved scope                                                         | Applied/read back                                                                                                                  | Skipped/pending | Blocked                                                  |
| ------------------------ | ---------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------- | --------------- | -------------------------------------------------------- |
| Defense paper            | blocks 1–6, including attached replacement comments                    | blocks 1–6 and comments `AAACAmWsXjc`, `AAACAmWsXjg`, `AAACAmWsXjk`, `AAACAmWsXjo`, `AAACAmWsXjs`, `AAACAmWsXjw` applied/read back | —               | fresh PDF page mapping and final rendered QA unavailable |
| ADAS_Paper_Audit_Tracker | block 7, row `🚩 Action Stream!A87:G87` and orange formatting fallback | row A87:G87 applied/read back; all new text orange `#E67E22`; H87 blank with validation preserved                                  | —               | —                                                        |
| Standalone comments      | Not applicable; comments are bundled with the six replacements         | —                                                                                                                                  | —               | —                                                        |
