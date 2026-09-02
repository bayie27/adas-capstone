# College of Information Technology and Engineering

## Information Technology Department

### Capstone Test Execution and Validation Plan

---

## Project Information

|                     |                                                                                                                                          |
| ------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| **Project Title**   | ADAS: An Intelligent Real-Time Road Accident Detection & Alert System based on Deep Learning Analysis of CCTV Video Streams in Lipa City |
| **Organization**    | Lipa City Disaster Risk Reduction and Management Office (Lipa CDRRMO)                                                                    |
| **Student Members** | Enjey Kashlee M. Alonzo<br>Sebastian Angelo T. Meer<br>Daniel Luis P. Sahagun<br>Jhon Paulo H. Tenorio                                   |
| **Adviser**         | Donna M. Garcia                                                                                                                          |
| **Testing Period**  | August 17, 2026 to August 21, 2026                                                                                                       |

---

## Purpose

This document defines the planned testing and validation activities for ADAS before its
final evaluation, organizational acceptance, and any future production deployment. It
identifies the testing scope, environments, participants, schedule, evaluation methods,
success criteria, and documentary evidence required to determine whether the system
correctly implements its specified functional requirements; meets its defined
detection-accuracy, latency, and performance targets under simulated multi-camera load;
sustains reliable operation and recovers from fault and data-loss conditions; enforces its
access-control and audit requirements; and is judged usable and acceptable by Lipa CDRRMO
operators and administrators — within the constraints of a single-node demonstration
environment.

The closing qualifier is deliberate. Every capacity, latency, and throughput figure this
plan produces is measured on the demonstration hardware described in the Test Environment
section, not on the production-target edge server. The plan is designed so that each claim
it makes is traceable to evidence produced within that environment, and so that claims the
environment cannot support are stated as limitations rather than results.

---

## Testing Scope

Ten testing activities are included. Each has its own test case ID family, a named
executor, and a defined documentary output. Activities that are not applicable to this
project are listed after the table with the reason for their exclusion.

| #   | Testing Activity                | Test Case ID Family | Executed By                  | Included |
| --- | ------------------------------- | ------------------- | ---------------------------- | -------- |
| 1   | Unit Testing                    | `TC-UNIT-xxx`       | Researchers                  | Yes      |
| 2   | Integration Testing             | `TC-INT-xxx`        | Researchers                  | Yes      |
| 3   | System / End-to-End Testing     | `TC-SYS-xxx`        | Researchers                  | Yes      |
| 4   | AI Model Validation             | `TC-AI-xxx`         | Researchers                  | Yes      |
| 5   | Performance & Load Testing      | `TC-PERF-xxx`       | Researchers                  | Yes      |
| 6   | Reliability & Endurance Testing | `TC-REL-xxx`        | Researchers                  | Yes      |
| 7   | Backup & Recovery Testing       | `TC-BKP-xxx`        | Researchers                  | Yes      |
| 8   | Security Testing                | `TC-SEC-xxx`        | Researchers                  | Yes      |
| 9   | Usability Testing               | `TC-USE-xxx`        | Operators and Administrators | Yes      |
| 10  | User Acceptance Testing (UAT)   | `TC-UAT-xxx`        | Operators and Administrators | Yes      |

### Activities excluded, and why

| Activity                             | Reason for exclusion                                                                                                                                                                                                              |
| ------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Compatibility Testing                | The deployment environment specifies a single standardized browser on operator workstations. A browser or operating system matrix would test a variability the deployment does not have.                                          |
| Public / Citizen-Facing Testing      | The project scope states the platform is intended only for internal command centre personnel and does not include public-facing applications. There is no citizen-facing surface to test.                                         |
| Third-Party Penetration Testing      | Requires an external security provider and a lead time the capstone schedule cannot accommodate. Security testing is performed internally against a defined checklist instead, and this substitution is recorded as a limitation. |
| Automated Emergency Dispatch Routing | Explicitly outside the project scope. The system terminates at operator decision; dispatch itself remains a manual CDRRMO process.                                                                                                |

### What each activity covers

**1. Unit Testing.** Isolated verification of individual modules: backend services and
route handlers, AI engine components (detector, temporal accumulator, camera worker,
outbox, supervisor), and frontend utilities. Establishes that each unit behaves correctly
against its own contract before any component is composed with another.

**2. Integration Testing.** Verification of the three inter-component seams: AI engine to
backend over the authenticated HTTP webhook, backend to frontend over the WebSocket
channel, and backend to database including the atomic coupling of every audited state
change with its audit record. Also covers camera state reconciliation between the AI
engine's observed status and the backend's stored configuration.

**3. System / End-to-End Testing.** Verification of complete operator workflows against
the fully deployed system running across the two-node test network — from collision
occurring in a video stream through detection, alert delivery, snapshot rendering, operator
verification, and incident resolution. This is the first activity that exercises the real
network path, the real TLS configuration, and a real browser.

**4. AI Model Validation.** Measurement of detection accuracy. Reports the model's mean
average precision as the primary criterion, and event-level detection performance against
hand-labelled real Lipa CCTV footage as supporting field-realism evidence.

**5. Performance & Load Testing.** Measurement of the system's timing behaviour under the
full ten-stream simulated load: inference latency per frame, sustained frame rate, alert
delivery latency, dashboard query response against a fully populated database, and report
export speed.

**6. Reliability & Endurance Testing.** Verification that the system survives fault
conditions and sustained operation: camera stream loss and reconnection, isolation of a
single camera's failure from the rest of the system, the scheduled daily restart and
recovery, dashboard state recovery after network interruption, and resource behaviour
across a continuous multi-hour run.

**7. Backup & Recovery Testing.** Verification that the automated database backup completes
without interrupting active inference or locking the database, and that an administrative
restore returns the system to service within its defined recovery window.

**8. Security Testing.** Verification of session security, role-based access control,
audit trail integrity and non-repudiation, transport security, and data localization.
Executed against a defined security checklist with automated test evidence supporting each
item.

**9. Usability Testing.** Measurement of how effectively CDRRMO personnel can operate the
dashboard, using the System Usability Scale supplemented by task observation and timing.

**10. User Acceptance Testing.** Scenario-based validation by CDRRMO operators and
administrators that the system supports their actual operational workflow, concluding in a
formal acceptance decision. The end-to-end collision-visible-to-operator-decision timing target
is measured during this activity, from the collision’s first visible frame on the monitored camera
to the operator’s recorded Confirm or Dismiss decision.

---

## Test Environment

### Test Environment for the Team, UAT, and Other Tests

| Item                               | Description                                                                                                                                                                                                        |
| ---------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Inference and Application Host** | Lenovo IdeaPad Gaming 3i 15IAH7; Intel Core i5-12500H; NVIDIA GeForce RTX 3050 Ti with 4 GB VRAM; 16 GB RAM; 512 GB SSD; Windows 11                                                                                |
| **Client Device**                  | Acer Nitro 5 AN515-57; Intel Core i5-11400H; NVIDIA GeForce RTX 3050 with 4 GB VRAM; 16 GB RAM; 512 GB SSD; Windows 11                                                                                             |
| **Application Stack**              | React and TypeScript frontend; FastAPI backend; SQLite database configured with Write-Ahead Logging; Python AI engine using Ultralytics YOLO and OpenCV                                                            |
| **RTSP Simulation**                | MediaMTX will locally rebroadcast ten distinct prerecorded traffic and collision videos as ten simultaneous RTSP streams. All ten streams will run active AI inference simultaneously.                             |
| **Browser**                        | Latest stable desktop version of Google Chrome                                                                                                                                                                     |
| **Network**                        | Two-node wired Ethernet segment. See "Network Configuration" below.                                                                                                                                                |
| **AI Batch Size**                  | TensorRT engine exported with dynamic shapes at batch 15, supporting an operating range of 1–15 cameras. Tested operating point is 10 concurrent streams at 15 FPS. See "Model and Inference Configuration" below. |

### Network Configuration

The test network is a direct two-node wired segment. This is not a convenience
substitution: the production deployment places operator workstations on a wired Ethernet
connection to the edge server through an aggregation switch, so a direct cable reproduces
the production link with fewer hops rather than approximating a different one. No internet
path exists in the design, and none is used during testing — this is required by the data
localization requirement, which prohibits transmitting system data to external services.

| Item                    | Server (Inference and Application Host)                                                                             | Client (Operator Workstation)                       |
| ----------------------- | ------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------- |
| **Link**                | Single Cat5e/Cat6 cable, direct. No switch, no crossover cable required.                                            |                                                     |
| **IPv4 address**        | `192.168.50.1`                                                                                                      | `192.168.50.2`                                      |
| **Subnet mask**         | `255.255.255.0`                                                                                                     | `255.255.255.0`                                     |
| **Default gateway**     | _(deliberately blank)_                                                                                              | _(deliberately blank)_                              |
| **Hostname resolution** | Serves as `adas.local`                                                                                              | Static hosts-file entry: `192.168.50.1  adas.local` |
| **Network profile**     | Private (required; a gateway-less link is otherwise classified Public and inbound connections are dropped silently) | —                                                   |

**Addressing is static on both ends.** There is no DHCP server on a two-node cable, and
Windows link-local addresses change between boots, which would invalidate the certificate
and the hosts entry. Leaving the gateway blank is also deliberate: it prevents Windows from
attempting to route internet traffic over the test link, and allows both machines to retain
normal wireless connectivity for unrelated work during the testing period.

| Item                         | Value                                                                                                                                                                                                                          |
| ---------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Transport security**       | HTTPS for REST, WSS for the WebSocket channel                                                                                                                                                                                  |
| **Certificate**              | Self-signed, issued to the hostname `adas.local`, with subject alternative names covering `adas.local`, `localhost`, `192.168.50.1`, and `127.0.0.1`; installed into the client's Trusted Root Certification Authorities store |
| **Dashboard origin**         | `https://adas.local:5173`                                                                                                                                                                                                      |
| **API and WebSocket origin** | `https://adas.local:8000`                                                                                                                                                                                                      |
| **Ports crossing the link**  | TCP 8000 and TCP 5173 only                                                                                                                                                                                                     |
| **RTSP**                     | Port 8554, server-local only. MediaMTX, the video sources, the AI engine, and the backend all reside on the server, exactly as they all reside on the edge server in production. Camera traffic never crosses the client link. |

The certificate is issued to a hostname rather than an IP address by design. A certificate
pinned to an address fails the moment the address changes, and a certificate error on a
WebSocket handshake cannot be clicked past — it fails silently, producing a dashboard that
loads but never receives events. Binding to a hostname reduces a network change to a
one-line hosts-file edit.

### Model and Inference Configuration

| Item                               | Value                                                                                                                                                                                    |
| ---------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Architecture**                   | YOLO26n (Ultralytics)                                                                                                                                                                    |
| **Trained checkpoint**             | `epoch50.pt` — epoch 50, checkpoint dated 2026-08-09, trained at image size 640 with a training batch size of 64                                                                         |
| **Deployed build**                 | TensorRT engine exported from `epoch50.pt` — dynamic shapes, batch 15, FP16 (half) precision, workspace 2 GiB. Built on the inference host itself; engines are not portable across GPUs. |
| **Inference image size**           | 640                                                                                                                                                                                      |
| **Detection confidence threshold** | 0.15                                                                                                                                                                                     |
| **Detected class**                 | Accident (class 0). The second training class is a foil and is discarded at inference.                                                                                                   |
| **Temporal accumulation**          | Detections must accumulate corroborating evidence over time before an alert is raised; a single frame cannot trigger an alert.                                                           |
| **Operating point**                | 10 concurrent camera streams at 15 FPS                                                                                                                                                   |

**The distinction between training batch size and inference batch size matters here and is
easy to conflate.** The training batch size of 64 describes how the model was trained on
cloud hardware. The inference batch size describes how many camera frames the deployed
engine processes in a single tick, and is therefore bounded by the number of concurrent
streams and by the 4 GB VRAM ceiling of the inference host.

**Why the TensorRT export is a prerequisite rather than an optimization.** The plain
PyTorch checkpoint was benchmarked across batch sizes 1 through 16, giving 73.5 ms at batch
10 and 106 ms at batch 15 against a 66.7 ms tick budget at 15 FPS — a measured capacity of
8 cameras at 15 FPS, or 13 at 10 FPS. **These figures were measured on a GTX 1650
development laptop, not on the RTX 3050 Ti inference host**, and are therefore a
conservative floor rather than a description of the test machine: the RTX 3050 Ti is an
Ampere part with tensor cores, where the GTX 1650 is Turing and has none. Re-measurement on
the inference host is the first item of the Day 0 gate, and every capacity figure reported
in the results comes from that re-measurement, not from the development-laptop profile.

**Why dynamic shapes.** Dynamic shapes are mandatory here, not preferred. The inference
pipeline assembles each tick's batch from only those cameras that are currently live and
un-paused, and the self-blindfold rule pauses a camera on every confirmed detection, so the
batch size varies continuously between 1 and the camera count. The engine's optimization
profile sets the batch dimension to minimum 1, so this range is covered. A fixed-batch
engine accepts exactly one batch size and would fail on the first detection.

**Why batch 15.** In this exporter the `batch` argument sets the optimization target and
the hard ceiling simultaneously — the profile is minimum 1, optimum `batch`, maximum
`batch` — so a single number serves as both. It is set to 15 to cover an operating range of
1 to 15 cameras without rebuilding the engine. Running below the optimum is well-supported:
inputs are not padded, so compute scales with the actual batch, and the only penalty is
that kernel tactics were selected at the optimum rather than at the running batch. That
penalty is proportionally small and falls on the small-batch ticks, which have the most
slack in the budget. The genuine cost of the higher ceiling is activation memory
provisioned for batch 15 on a 4 GB card, which is monitored during the endurance run.

**Why FP16 and workspace 2.** The speed gain comes principally from half-precision
execution on the host GPU's tensor cores rather than from the export format alone; an FP32
engine is not assumed sufficient. The exporter silently downgrades to FP32 if the platform
does not report fast FP16 support, so the builder log line stating whether an FP16 or FP32
engine was built is checked and recorded rather than assumed. Workspace is set to 2 GiB
because the exporter overloads this argument: besides capping the builder's tactic-selection
memory pool, it also scales the maximum input resolution by `max(2, workspace)`. A value of
2 therefore yields the smallest possible maximum resolution while leaving a reasonable
tactic budget; larger values would only inflate the input dimensions the engine must be
built to accommodate, on a card with no memory to spare.

**The export is not complete until it is verified.** Half precision changes numerical
results slightly, and the detection confidence threshold is deliberately low at 0.15 —
chosen because in this model false positives score higher than genuine detections, so a
higher threshold would remove real collisions before it removed false alarms. At a
threshold that low, small numeric shifts can change whether a borderline detection fires.
The Day 0 gate therefore requires three steps in order: export the engine, re-run the
per-clip regression and diff the result against the frozen reference baseline clip by clip,
and re-measure capacity against the exported engine. Drift found at step two is recorded
rather than treated as automatic grounds for rejection, but it must be known before any
accuracy or capacity figure in this plan is quoted.

### Software Version Manifest

| Component                  | Version                                | Note                                                                       |
| -------------------------- | -------------------------------------- | -------------------------------------------------------------------------- |
| Python                     | 3.12.13                                |                                                                            |
| SQLite                     | 3.50.4                                 | Write-Ahead Logging mode                                                   |
| PyTorch                    | 2.11.0+cu130                           | CUDA 13.0 build                                                            |
| Ultralytics — **training** | 8.4.116                                | Version that produced `epoch50.pt` (cloud environment)                     |
| Ultralytics — **runtime**  | 8.4.41                                 | Version installed on the inference host and used for export and inference  |
| TensorRT                   | 10.x, pinned below 11                  | Installed as the CUDA-13-matched wheel, not the PyPI stub. See note below. |
| ONNX toolchain             | `onnx`, `onnxslim`                     | Required by the `.pt` → ONNX → `.engine` export chain                      |
| MediaMTX                   | v1.18.0                                |                                                                            |
| Backend framework          | FastAPI                                |                                                                            |
| Frontend                   | React with TypeScript, built with Vite |                                                                            |
| Browser                    | Google Chrome, latest stable desktop   |                                                                            |

**On the two Ultralytics versions.** The checkpoint was trained in a cloud environment on a
newer release than the one installed on the inference host. Both are recorded because they
are genuinely different environments and the difference is a plausible source of behavioural
variance; the Day 0 parity gate is what confirms the runtime version reproduces the recorded
baseline.

**On the TensorRT version pin.** The installed Ultralytics release contains no handling for
TensorRT 11 and sets the FP16 builder flag directly. That flag was removed in TensorRT 11,
which is strongly-typed and requires reduced precision to be baked into the ONNX graph
beforehand. Installing TensorRT 11 would therefore break the FP16 export. The pin is below
11 for that reason, and the CUDA-13-matched wheel is installed directly rather than through
the general PyPI package, whose build step downloads several gigabytes inside a build hook
with no timeout and has hung indefinitely on this project's hardware before.

The exact commit of the application under test is tagged and recorded on Day 1. No feature
changes are accepted into the build after that tag; defect fixes during the window are
applied as tracked patches and re-tested.

### Deviations from the Production Target

The production deployment target is a rack-mounted edge server with eight datacentre GPUs,
running Linux, ingesting from the agency's video management system across a segmented VLAN
network. The test environment is a single laptop. Every difference is listed here so that
no result in this plan is read as a production-scale claim.

| Production target                   | Test environment                             | Verdict                                                                                                                                 |
| ----------------------------------- | -------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| Rack edge server, Ubuntu Server LTS | Laptop, Windows 11                           | Different scale and operating system; **identical application code**                                                                    |
| 8 datacentre-class GPUs             | 1 laptop GPU, 4 GB VRAM                      | Different capacity; same inference path. Capacity figures are demo-validated only.                                                      |
| Dahua DSS Pro, RTSP substreams      | MediaMTX rebroadcasting prerecorded clips    | **Same protocol and URL shape**, different source                                                                                       |
| Operator PC on a routed VLAN, wired | Second laptop, wired, direct                 | Same reachability, fewer hops                                                                                                           |
| HTTPS and WSS with agency PKI       | HTTPS and WSS with a self-signed certificate | **Same protocols**; demonstration-grade trust anchor                                                                                    |
| No internet egress                  | No internet egress                           | **Identical**                                                                                                                           |
| Full citywide camera network        | 10 simulated streams                         | Different scale; the citywide figure is a VRAM calculation, not something this hardware demonstrates and not something this plan claims |

---

## Test Data & Datasets

| Dataset                       | Source and how produced                                                                                    | Size                                                                                                | Used by                                                   |
| ----------------------------- | ---------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------- | --------------------------------------------------------- |
| **Labelled evaluation clips** | Lipa CDRRMO archival CCTV footage, with crash onset times hand-labelled by the project owner from playback | 17 clips — 16 containing a labelled collision, 1 declared accident-free for false-alarm measurement | AI Model Validation                                       |
| **RTSP simulation videos**    | Prerecorded traffic and collision footage, rebroadcast by MediaMTX as live RTSP streams                    | 10 distinct streams                                                                                 | System / E2E, Performance & Load, Reliability & Endurance |
| **Performance seed dataset**  | Generated on demand by the repository's seeding script under its performance profile                       | 100,000 incident records across 6 cameras and 4 operators, spread over approximately 18 months      | Performance & Load, Backup & Recovery                     |
| **Test user accounts**        | Generated by the repository's development seeding script                                                   | 6 operator accounts, 2 administrator accounts                                                       | Security, Usability, UAT                                  |

### Handling of CCTV footage

The evaluation clips are real surveillance footage supplied by the partner agency. They
carry no public licence and show identifiable people, vehicles, and locations. They are
therefore treated as test-only material permanently: they are not published, not included
in any appendix or presentation as raw footage, and not used as training data. Where visual
evidence of a detection is required in the results, a single annotated frame is used with
identifying detail obscured. This restriction is a standing project rule and not a decision
made for this testing period.

### Independence of evaluation data — a stated limitation

The model was trained on a hybrid dataset combining public repositories with archival
CDRRMO footage. Full independence between the evaluation clip set and the training data
**has not been established.** Five of the seventeen clips carry location captions matching
cameras that also appear in an earlier footage set, and at least two clips share a single
camera viewpoint, so there are at most sixteen distinct viewpoints rather than seventeen.
This is recorded here rather than in a footnote because it bounds what the event-level
results can claim: they demonstrate performance on real Lipa CCTV conditions, but they are
not a fully held-out independent test set, and this plan does not describe them as one.

---

## Test Participants

Participant groups differ by activity. The operator and administrator counts are derived
from the partner agency's actual staffing: three shifts with two designated operators each,
giving six operators, plus two administrators who require system knowledge. This is the
complete population of intended users, not a sample drawn from a larger one.

| Testing Activity                | Group                                                    | Participants |
| ------------------------------- | -------------------------------------------------------- | ------------ |
| Unit Testing                    | Researchers                                              | 4            |
| Integration Testing             | Researchers                                              | 4            |
| System / End-to-End Testing     | Researchers                                              | 4            |
| AI Model Validation             | Researchers                                              | 1–2          |
| Performance & Load Testing      | Researchers                                              | 2            |
| Reliability & Endurance Testing | Researchers                                              | 2            |
| Backup & Recovery Testing       | Researchers                                              | 1–2          |
| Security Testing                | Researchers                                              | 2            |
| **Usability Testing**           | Operators<br>Administrators<br>Researchers (observers)   | 6<br>2<br>2  |
| **User Acceptance Testing**     | Operators<br>Administrators<br>Researchers (facilitator) | 6<br>2<br>1  |

**On sample size.** Eight participants is the entire intended user population, which makes
this a census of the target users rather than a sample. It nonetheless remains a small
number for statistical inference, and usability results are reported with that constraint
stated explicitly alongside them.

**On the absence of a citizen participant group.** The project scope states the platform is
intended only for internal command centre personnel and does not include public-facing
applications. There is no interface a citizen participant would exercise, so no citizen
group is defined.

---

## Roles, Responsibilities & Entry/Exit Criteria

### Roles

| Role              | Responsibility                                                                                                   | Assigned to        |
| ----------------- | ---------------------------------------------------------------------------------------------------------------- | ------------------ |
| Test Coordinator  | Owns the schedule, the defect log, and the consolidated Test Summary Report; facilitates the participant session | _(to be assigned)_ |
| AI Engine Lead    | TensorRT export and verification; AI Model Validation; AI-side unit tests; inference performance measurement     | _(to be assigned)_ |
| Backend Lead      | Backend unit and integration testing; security testing; backup and recovery drills; database performance         | _(to be assigned)_ |
| Frontend Lead     | Frontend unit testing; system and end-to-end testing; usability session setup and observation                    | _(to be assigned)_ |
| Environment Owner | Network, certificate, and deployment setup; environment health across the window                                 | _(to be assigned)_ |

One researcher may hold more than one role. Assignments are recorded before Day 1 so that
each result carries a named executor.

### Entry criteria — conditions required before an activity may begin

| Activity                | Entry criteria                                                                                                                   |
| ----------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| All activities          | Build tagged and frozen; environment smoke test passed; test cases for the activity authored and reviewed                        |
| Unit, Integration       | Deployment complete; dependencies installed on the inference host                                                                |
| System / E2E            | Unit and Integration exited; two-node network reachable; certificate trusted on the client; all 10 streams live and ingesting    |
| AI Model Validation     | TensorRT engine exported and parity-verified against the recorded per-clip baseline; evaluation clips present                    |
| Performance & Load      | System / E2E exited; 10 streams sustained; performance seed dataset loaded                                                       |
| Reliability & Endurance | Performance baseline captured (so degradation is measurable against it); both machines on mains power with sleep disabled        |
| Backup & Recovery       | Performance seed dataset loaded (so the backup operates on a realistically sized database)                                       |
| Security                | System deployed over HTTPS/WSS with the production-shaped configuration                                                          |
| Usability, UAT          | All researcher-executed activities exited; no open Critical defect; participants briefed; instruments and consent forms prepared |

### Exit criteria — conditions required to declare an activity complete

An activity is complete when all four hold:

1. Every planned test case for the activity has been executed, or has a recorded reason for
   not being executed.
2. Results are recorded against each case with pass/fail status and observed values.
3. Every Critical and Major defect found is either resolved and re-tested, or formally
   accepted with a documented justification.
4. The activity's documentary output listed in the Deliverables section has been produced.

---

## Testing Schedule

Testing runs across one week, August 17–21, 2026. Researcher-executed activities are
front-loaded so that CDRRMO participants — who are available for a single dedicated day —
encounter a system that has already passed functional, performance, and security testing.
Friday is reserved for defect re-test and analysis rather than new execution.

| Day       | Date        | Activity                                                                                                                                                                  | Status |
| --------- | ----------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------ |
| **Day 0** | Sun, Aug 16 | **Prerequisite gate — see the ordered checklist below.** All of it executes on the RTX 3050 Ti inference host.                                                            |        |
| **Day 1** | Mon, Aug 17 | Final deployment and build freeze; environment bring-up and smoke test; **Unit Testing**; **Integration Testing**                                                         |        |
| **Day 2** | Tue, Aug 18 | **System / End-to-End Testing** (two-node walkthrough in a real browser); **AI Model Validation**. Endurance soak run begins at end of day.                               |        |
| **Day 3** | Wed, Aug 19 | **Performance & Load Testing**; **Security Testing**; **Backup & Recovery Testing**. Soak run continues.                                                                  |        |
| **Day 4** | Thu, Aug 20 | Soak run ends; **Reliability & Endurance** results captured. **Participant session — full day: Usability Testing (SUS) and User Acceptance Testing**, all 8 participants. |        |
| **Day 5** | Fri, Aug 21 | Defect re-test; data analysis and scoring; evidence consolidation; Test Summary Report                                                                                    |        |

### Day 0 prerequisite checklist

Every step below runs on the RTX 3050 Ti inference host, because a TensorRT engine is tied
to the GPU architecture, TensorRT version, and driver it was built against — an engine built
on any other machine will not load. Steps are ordered by dependency; a failure at any step
stops the sequence and triggers the corresponding entry in the Risks table.

| #   | Step                                                                                                                                                                | Success check                                                                                   |
| --- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| 0.1 | Baseline capacity measurement on the host using the plain PyTorch weights                                                                                           | Camera capacity recorded at both ends of the FPS band, replacing the development-laptop figures |
| 0.2 | Install the export toolchain: CUDA-13-matched TensorRT wheel pinned below 11, plus `onnx` and `onnxslim`                                                            | All three import successfully; TensorRT reports a 10.x version                                  |
| 0.3 | Extend the capacity tool to accept a weights or engine path _(see note)_                                                                                            | The tool runs against an explicitly supplied model file                                         |
| 0.4 | Export the engine — dynamic shapes, batch 15, FP16, workspace 2                                                                                                     | Builder log reads "building **FP16** engine", not FP32                                          |
| 0.5 | Per-clip regression against the frozen reference baseline                                                                                                           | Per-clip results diffed individually; any drift recorded before results are quoted              |
| 0.6 | Capacity re-measurement against the exported engine                                                                                                                 | Confirms whether the 10-stream, 15 FPS operating point is met                                   |
| 0.7 | Two-node network setup: static addressing, Private network profile, firewall rules for ports 8000 and 5173, certificate generation, client trust-store installation | Client reaches both ports; browser shows no certificate warning                                 |

**Note on step 0.3.** The capacity tool currently reads the model path from configuration
and exposes no argument for overriding it, so it cannot benchmark a built engine as written.
This is a small change — the detector class already accepts a path, and the model loader
accepts an engine file natively — but until it is made, step 0.6 cannot be executed and the
exported engine's capacity cannot be measured. It is listed as a prerequisite for exactly
that reason: there is no value in building an engine that cannot be benchmarked.

**Two scheduling decisions worth noting.**

The endurance soak deliberately spans Tuesday evening through Thursday morning —
approximately 36 continuous hours. This crosses **two scheduled 3:00 AM restart windows**,
so the automated daily restart and recovery requirement is exercised twice under real
conditions rather than being simulated in a separate manual drill. It also means resource
behaviour is observed across a period long enough for gradual degradation to appear.

The participant session is the fixed anchor of the week. Every other activity is scheduled
around it, because it is the one resource the team does not control. If it moves, the
researcher-executed activities compress; they do not move with it.

---

## Evaluation Methods

| #   | Objective                                                       | Evaluation Method                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                | Evidence Produced                                                                                                                  |
| --- | --------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| 1   | Module-level correctness                                        | Execution of the automated unit test suites across backend, AI engine, and frontend                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              | Test execution report with per-suite pass counts                                                                                   |
| 2   | Inter-component correctness                                     | Execution of integration tests across the three component seams, including webhook authentication, WebSocket broadcast payload shape, and atomic audit coupling                                                                                                                                                                                                                                                                                                                                                                                                                                                                  | Integration test execution report                                                                                                  |
| 3   | Functional correctness of complete workflows                    | Execution of system test cases over the two-node network in a real browser, combining automated end-to-end scripts with a structured manual walkthrough                                                                                                                                                                                                                                                                                                                                                                                                                                                                          | System test case results, automated run report, annotated walkthrough log                                                          |
| 4   | AI detection accuracy                                           | **Primary:** mean average precision at IoU 0.50 on the **validation split**, from the metrics recorded in the trained checkpoint at epoch 50. The dataset defines only training and validation splits; no held-out test split exists, so a test-split measurement was not available.<br>**Supporting:** event-level scoring of the deployed engine against the 17 hand-labelled clips — a detection counts as correct only if it falls inside the labelled crash window — reporting recall separately for standard-difficulty and pre-registered hard-difficulty clips, plus false alarms per minute of ordinary traffic footage | Model validation report containing both measures, a per-clip results table, and a comparison against the frozen reference baseline |
| 5   | Inference and delivery latency                                  | Timed measurement under the full 10-stream load: per-frame inference time, sustained frame rate per stream, and elapsed time from detection to alert rendered on the client dashboard                                                                                                                                                                                                                                                                                                                                                                                                                                            | Performance measurement log with hardware conditions recorded alongside each figure                                                |
| 6   | Query and export performance                                    | Timed dashboard queries and report exports executed against the 100,000-record seeded database                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   | Performance measurement log                                                                                                        |
| 7   | Fault tolerance and endurance                                   | Fault injection (stream disconnection, single-camera process failure, network interruption, service restart) plus a continuous multi-hour run with resource and availability sampling at fixed intervals                                                                                                                                                                                                                                                                                                                                                                                                                         | Endurance run log covering memory, VRAM, thermals, and availability probe results; fault injection results table                   |
| 8   | Backup and recovery                                             | Timed execution of an automated backup against a live system with active inference and concurrent database writes, followed by a timed administrative restore and service resumption                                                                                                                                                                                                                                                                                                                                                                                                                                             | Backup and restore drill record with phase-separated timings                                                                       |
| 9   | Security posture                                                | Structured security checklist covering authentication, session handling, authorization, audit integrity, transport security, and data localization; each item evidenced by an automated test, a manual verification, or an inspected artifact                                                                                                                                                                                                                                                                                                                                                                                    | Completed security checklist with audit log extracts and header inspections                                                        |
| 10  | Ease of use                                                     | System Usability Scale (10-item standard instrument) administered to all 8 participants after task completion, supplemented by task observation and click-path counting                                                                                                                                                                                                                                                                                                                                                                                                                                                          | SUS response sheets, computed per-participant and mean scores, observation notes                                                   |
| 11  | Learnability                                                    | Timed observation of a participant with no prior exposure processing an alert unaided following a short structured briefing                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      | Learnability observation record with timings                                                                                       |
| 12  | Operational efficiency (collision-visible to operator decision) | Timed observation during UAT: elapsed time from the collision’s first visible frame on the monitored camera to the operator’s recorded Confirm or Dismiss decision, repeated across all operators and multiple incidents                                                                                                                                                                                                                                                                                                                                                                                                         | Timing table with per-operator means, overall mean, and worst case                                                                 |
| 13  | Organizational acceptance                                       | Scenario-based UAT covering the operational workflows the agency actually performs, concluding in a formal acceptance decision by an authorized CDRRMO representative                                                                                                                                                                                                                                                                                                                                                                                                                                                            | UAT scenario results, defect list, signed acceptance form                                                                          |

---

## Acceptance Criteria

| Item                                 | Success Criterion                                                                                                                                                                                                                                              |
| ------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Unit Testing**                     | 100% of executed unit tests pass. Anything less is treated as a build defect blocking further activity, not as a test result.                                                                                                                                  |
| **Integration Testing**              | 100% of executed integration tests pass.                                                                                                                                                                                                                       |
| **System / End-to-End Testing**      | ≥95% of system test cases pass, with zero open Critical or Major defects.                                                                                                                                                                                      |
| **AI Model Validation — primary**    | mean average precision at IoU 0.50 ≥ 0.85, measured on the validation split.                                                                                                                                                                                   |
| **AI Model Validation — supporting** | Event-level recall on standard-difficulty clips and false alarms per minute reported against the frozen reference baseline, with no regression from that baseline. Hard-difficulty recall reported separately and never blended into a single headline figure. |
| **Inference latency**                | ≤ 100 ms per frame.                                                                                                                                                                                                                                            |
| **Frame rate**                       | Sustained 10–15 FPS on every one of the 10 concurrent streams.                                                                                                                                                                                                 |
| **Alert delivery**                   | Alert, including snapshot, rendered on the client dashboard within 2 seconds of detection.                                                                                                                                                                     |
| **Dashboard query response**         | ≤ 3 seconds against the 100,000-record database.                                                                                                                                                                                                               |
| **Report export**                    | Export initiates within 5 seconds for the operational 30-day dataset. The larger-scale measurement is reported separately as a documented ceiling, not as the operational criterion.                                                                           |
| **Network fault tolerance**          | Reconnection to a lost camera stream attempted within 10 seconds of disconnection.                                                                                                                                                                             |
| **Process isolation**                | Failure of a single camera's detection process does not crash the server, the dashboard, or any other camera's processing.                                                                                                                                     |
| **Restart recovery**                 | Memory flush and return to service completed in under 10 seconds; camera ingestion confirmed resumed afterward.                                                                                                                                                |
| **State recovery**                   | Dashboard automatically re-synchronizes and displays all currently unverified alerts on reload or reconnection.                                                                                                                                                |
| **Availability**                     | ≥ 99.9% of readiness probes successful across the continuous soak window, with no unplanned service interruption. _(See note below.)_                                                                                                                          |
| **Backup**                           | Automated backup completes with no interruption to active inference and no database lock errors.                                                                                                                                                               |
| **Recovery**                         | Restore completes and automated alerting resumes within a 60-second operational window.                                                                                                                                                                        |
| **Security**                         | 100% of security checklist items pass, with zero Critical findings. Role-based denials and failed authentication attempts verified present in the audit trail.                                                                                                 |
| **Usability**                        | SUS mean score ≥ 68.                                                                                                                                                                                                                                           |
| **Workflow efficiency**              | Operator completes verification in 3 clicks or fewer.                                                                                                                                                                                                          |
| **Learnability**                     | A new operator processes and verifies an alert unaided within 15 minutes of briefing.                                                                                                                                                                          |
| **Operational efficiency**           | Collision-visible-to-operator-decision mean ≤ 25 seconds across operators, measured from the collision’s first visible frame on the monitored camera to the operator’s recorded Confirm or Dismiss decision; worst case reported alongside the mean.           |
| **User Acceptance Testing**          | ≥ 95% of UAT scenarios accepted, zero open Critical or Major defects, and formal sign-off obtained from an authorized CDRRMO representative.                                                                                                                   |

**Pass rate** is computed as executed cases passed divided by executed cases, expressed as a
percentage. Cases not executed are reported separately with reasons and are never counted
as passes.

### Note on the availability criterion

The system requirement specifies 99.9% uptime. A figure of that form describes annual
availability and cannot be evidenced by a one-week testing period; no measurement performed
here can establish it. What this plan measures instead is a defined proxy: the proportion of
readiness probes that succeed across the continuous soak window, sampled at a fixed
interval, together with a record of any unplanned interruption. The result is reported
precisely as that — availability observed across the soak window — and is not presented as
proof of the annual figure. This substitution is stated in the results rather than left
implicit.

### Note on the two AI accuracy measures

Mean average precision and event-level recall answer different questions, and the plan
reports both because neither alone is sufficient.

Mean average precision is computed on the **validation** split during training. It measures
per-frame bounding box quality across that split, and it is the measure the system
requirement is written against. It is reported here as the primary criterion, with three
qualifications stated plainly rather than buried:

1. The dataset defines only training and validation splits. **There is no held-out test
   split**, so no test-split measurement was possible and none is claimed.
2. The validation split shares a data distribution with the training data.
3. The validation split **informed checkpoint selection** — epoch 50 was retained because
   it achieved the best validation fitness of the run. A metric that selected the
   checkpoint is optimistically biased as a measure of that same checkpoint.

None of this makes the figure meaningless; it makes it a specific thing. It is reported as
what it is — a validation-split result on the training distribution — and the event-level
measurements below are what carry the claim about behaviour on real deployment footage.

Event-level recall measures something the requirement does not capture: whether the
deployed engine, running its full temporal accumulation logic, raises an alert inside the
window where a real crash actually occurred in real Lipa CCTV footage — and how often it
raises one when nothing happened. It is reported as supporting evidence because it is
closer to the operational question the agency cares about. Reporting hard-difficulty clips
separately, using difficulty judgements recorded before any model was run against the
footage, is what keeps that breakdown an honest stratification rather than a post-hoc
selection of favourable results.

---

## Defect Management & Severity Levels

Every defect found during any activity is logged with an identifier, the test case that
found it, the activity, a severity, reproduction steps, and a resolution status.

| Severity     | Definition                                                                                                                                          | Blocks acceptance? |
| ------------ | --------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------ |
| **Critical** | Prevents accident detection, alert delivery, or incident resolution; causes data loss or corruption; allows authentication or authorization bypass. | **Yes**            |
| **Major**    | A specified functional or non-functional requirement is not met and no workaround exists.                                                           | **Yes**            |
| **Minor**    | The requirement is met but behaviour is degraded, or a workaround exists.                                                                           | No                 |
| **Cosmetic** | Presentation, wording, or layout only; no functional impact.                                                                                        | No                 |

**Triage.** Defects are triaged daily during the testing window. Critical defects halt the
affected activity until resolved. Major defects are scheduled for fix and re-test within
the window where feasible; where not feasible, they are formally accepted with a documented
justification and carried into the results as known limitations.

**Re-test.** Any defect marked resolved is re-tested by executing the original failing test
case. A defect is closed only after its originating case passes. Re-test is why Day 5
carries no new execution.

---

## Risks, Assumptions & Constraints

### Risks

| Risk                                                                                                                                                                                     | Impact                                                                                         | Mitigation                                                                                                                                                                                                                                                                                            |
| ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **The inference host's real capacity is not yet measured.** All existing capacity figures come from a slower development laptop with a different GPU generation.                         | The operating point rests on an inaccurate number in either direction                          | Day 0 step 0.1 re-measures on the host before anything else. Every capacity figure in the results comes from that measurement.                                                                                                                                                                        |
| **TensorRT installation hangs.** The general PyPI package downloads several gigabytes inside a build hook with no timeout; this has hung indefinitely on this project's hardware before. | Day 0 stalls with no error to diagnose                                                         | Install the CUDA-13-matched wheel directly rather than the general package, bypassing the build hook. Do the install deliberately and early — the model library auto-installs missing export dependencies at runtime, which would otherwise trigger the same hang inside the export itself.           |
| **TensorRT 11 installed instead of 10.x**                                                                                                                                                | Export fails on a builder flag the installed model library still uses and TensorRT 11 removed  | Version pinned below 11; TensorRT version verified at Day 0 step 0.2 before the export is attempted.                                                                                                                                                                                                  |
| **FP16 silently downgrades to FP32.** The exporter forces half precision off if the platform does not report fast FP16 support, without raising an error.                                | An FP32 engine misses the tick budget, presenting as an unexplained performance failure        | The builder log line naming the precision is read and recorded at step 0.4. Precision is confirmed, never assumed.                                                                                                                                                                                    |
| **The capacity tool cannot benchmark a built engine** as currently written                                                                                                               | The exported engine's real capacity cannot be measured, leaving the operating point unverified | Day 0 step 0.3 extends the tool before the export. Listed as a prerequisite rather than a follow-up.                                                                                                                                                                                                  |
| TensorRT export does not complete before Day 1                                                                                                                                           | The 10-stream, 15 FPS operating point is not achievable                                        | Fall back to the PyTorch build and set the operating point from the host's measured PyTorch capacity at step 0.1 — reducing stream count, or dropping to the 10 FPS floor of the frame rate band, or both. Any such revision is recorded in the results, not concealed.                               |
| Half-precision export shifts detections near the 0.15 confidence threshold                                                                                                               | Detection behaviour differs from the recorded baseline; accuracy results become non-comparable | Day 0 gate step 2 diffs the exported engine against the frozen per-clip baseline before any accuracy claim is made. Drift is recorded and reported alongside results rather than silently absorbed. If drift is severe, the PyTorch fallback applies with its corresponding operating-point revision. |
| A stale or mismatched engine file is loaded instead of the intended build                                                                                                                | The system silently runs the wrong model — a failure mode this project has encountered before  | The engine is rebuilt from `epoch50.pt` on Day 0 and verified by the parity gate. No automatic fallback from engine to checkpoint is configured; a missing or invalid engine fails loudly rather than degrading silently.                                                                             |
| Participants unavailable on Aug 20                                                                                                                                                       | Usability and UAT produce no results                                                           | The session is the schedule's fixed anchor; fallback is per-shift staggered sessions on Aug 21, accepting reduced observation quality. Confirm attendance before Day 1.                                                                                                                               |
| 4 GB VRAM ceiling on the inference host                                                                                                                                                  | Ten simultaneous streams exhaust VRAM under load                                               | Capacity re-measured at the exported build on Day 0 before any performance claim is made; VRAM sampled continuously during the soak run.                                                                                                                                                              |
| Thermal throttling                                                                                                                                                                       | Latency and frame rate figures become unrepresentative                                         | Both machines on mains power on a hard surface throughout; battery operation prohibited during any timed measurement.                                                                                                                                                                                 |
| Cloud file synchronization running over the live database                                                                                                                                | File locking errors, conflicted database copies, partially written snapshots                   | Synchronization paused on the inference host for the entire testing window. This is a known documented hazard, not a hypothetical one.                                                                                                                                                                |
| Silent network profile misclassification                                                                                                                                                 | Client cannot reach the server; failure presents as an unexplained hang                        | Ethernet profile explicitly set to Private and inbound rules created for ports 8000 and 5173 during Day 0 setup, with reachability verified before Day 1.                                                                                                                                             |
| Frontend still under active development                                                                                                                                                  | Some functional requirements may be incompletely implemented at test time                      | Incomplete functionality is logged as a defect against its requirement rather than removed from the test case set. Coverage gaps are visible in the results instead of being hidden by scope reduction.                                                                                               |
| Simulated RTSP source differs from the agency's video management system                                                                                                                  | Behaviour under real camera conditions is not directly observed                                | The simulation uses the same protocol and URL structure as the production source; the difference is recorded in the deviations table and stated as a limitation.                                                                                                                                      |
| Looping short clips re-trigger detections rapidly                                                                                                                                        | Apparent duplicate alerts during demonstration                                                 | Understood as an artifact of clip length rather than a system defect; clips trimmed or the behaviour narrated during the session.                                                                                                                                                                     |

### Assumptions

- The application build is frozen at the Day 1 tag. Only defect fixes enter the build during
  the window, applied as tracked patches and re-tested.
- Participants have prior CCTV monitoring experience and basic computer literacy, consistent
  with their actual roles at the agency.
- The evaluation clips represent conditions comparable to those the deployed system will
  encounter, notwithstanding the independence limitation stated in the Test Data section.
- An authorized CDRRMO representative is available to render an acceptance decision.

### Constraints

- **One week.** Testing runs August 17–21. No activity may be extended beyond the window.
- **One participant day.** All participant-executed testing occurs in a single session.
- **Eight participants.** This is the complete population of intended users; it is not
  expandable, and usability results carry the corresponding statistical limitation.
- **Single-node environment.** No result in this plan constitutes evidence of behaviour at
  production scale on the target edge server. Every capacity figure is labelled as
  demonstration-hardware-validated.
- **Self-signed certificate.** Transport security is genuine; the trust anchor is
  demonstration-grade and differs from the agency's production public key infrastructure.

---

## Deliverables

Each activity produces a named artifact. All artifacts are attached as appendices and
supporting evidence in the final paper.

| Activity                        | Output                                                                                                                                                                |
| ------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Unit Testing                    | Unit test execution report — per-suite pass counts, execution time, failures with analysis                                                                            |
| Integration Testing             | Integration test execution report — per-seam results across the three component boundaries                                                                            |
| System / End-to-End Testing     | System test case results table; automated end-to-end run report; annotated two-node walkthrough log with screenshots                                                  |
| AI Model Validation             | Model validation report — mean average precision figures, per-clip event-level results table, false alarm rate, comparison against the frozen reference baseline      |
| Performance & Load Testing      | Performance measurement log — inference latency, per-stream frame rate, alert delivery latency, query response, export timing, each recorded with hardware conditions |
| Reliability & Endurance Testing | Endurance run log — memory, VRAM, thermal, and availability sampling across the soak window; fault injection results table; restart drill records                     |
| Backup & Recovery Testing       | Backup and restore drill record — phase-separated timings, database integrity verification, service resumption confirmation                                           |
| Security Testing                | Completed security checklist with per-item evidence; audit trail extracts; transport and header inspection records                                                    |
| Usability Testing               | SUS response sheets; computed per-participant and mean scores; task observation notes; click-path counts; learnability timing records                                 |
| User Acceptance Testing         | UAT scenario results; collision-visible-to-operator-decision timing table; defect list; **signed acceptance form**                                                    |
| **Cross-cutting**               | **Requirements Traceability Matrix** — every functional and non-functional requirement mapped to its test cases, evidence artifact, and status                        |
| **Cross-cutting**               | **Defect Log** — all defects with severity, status, and resolution                                                                                                    |
| **Cross-cutting**               | **Test Summary Report** — consolidated results, pass rates per activity, acceptance criteria outcomes, and stated limitations                                         |

---

## Document Control

|               |                                                         |
| ------------- | ------------------------------------------------------- |
| Version       | 1.0                                                     |
| Date prepared | August 16, 2026                                         |
| Prepared by   | Group 7 — ADAS Capstone Team                            |
| Status        | For adviser review prior to the August 17 testing start |
