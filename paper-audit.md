# Full-codebase audit → Defence Document edit list (v2)

**Date:** 2026-08-13, augmented 2026-08-14
**Applies to:** the live Google Doc, _Group7_Capstone Project Defense Document - ITCAPROJ1_
([open](https://docs.google.com/document/d/1MkTrdBPrrXpw8JGC4xrS475wbF7Yn-9YCaXIN-xd0aw/edit)),
163 pp., Chapters 1–3 + References, as of its 2026-08-13 revision.
**Supersedes:** the previous version of this file (2026-08-12), which audited
`ai_engine/docs/Final-Paper.pdf` (109 pp.). Every item from it is carried, corrected,
or explicitly retired below — see [Corrections to the superseded audit](#corrections-to-the-superseded-audit).
**2026-08-14 addition:** `ai_engine/adas_transfer/training-configuration.md` landed as a
verified-reference file sourced directly from the training notebook. It resolves §0.6 (the
augmentation list was previously unverifiable from this repository) and surfaces a new finding,
§1.13 (the annotation-methodology claim). Both were checked directly against the live Doc's
current text via Drive access, quoted above.

---

## Why this is a new audit, not a refresh

Three things changed.

**The paper is a different artifact.** The live Doc is 163 pp. where the PDF was 109, and it
has restructured: new Project Scope and Boundaries, Swimlane, Context/Level-1 DFD, and
Deployment & Implementation sections. **Every cross-reference in the old audit is now wrong** —
the ERD is **Figure 7** (old audit said "Figure 6.0"), the data dictionary is **Tables 9–13**
(old audit said "Table 4.0–8.0"), and page numbers are off by roughly 50.

**None of the old audit's fixes were applied.** The paper still reads `bcrypt`, `gputil`,
"150 epochs", TensorRT `.engine`, and 85% mAP.

**The old audit checked one axis.** It compared paper↔code. This pass adds three more:
paper↔measured evidence, **paper↔paper**, and **paper↔reality-of-deployment**. The last two
account for most of the new findings, and the deployment axis (§1.0) is the largest single
cluster in the document.

### How to use this document

Items are grouped by priority and each gives location, current text, replacement text, and
why. Every claim carries either a `file:line` reference or a Doc heading link. Where one
correction has several sites in the paper, a **propagation list** names all of them — applying
only the first leaves the others contradicting it.

Doc links are of the form
`https://docs.google.com/document/d/1MkTrdBPrrXpw8JGC4xrS475wbF7Yn-9YCaXIN-xd0aw/edit#heading=h.xxxx`;
the anchor for each section is listed in the [reference map](#appendix--reference-map) at the end.

**Out of scope this pass:** the 81-case test-case chapter (Tables 15–35). The old audit's seven
parked items are preserved and corrected in [Deferred](#deferred--test-case-chapter). The
_narrative_ testing sections (Testing Strategy Overview, Types of Testing Conducted, UAT) **are**
in scope and appear below.

---

## Priority 0 — The paper contradicts itself

These need no code knowledge, cost minutes to fix, and are the easiest class of error for a
panel member to find by reading alone.

### 0.1 Evaluation Scope cites two wrong NFRs in one sentence

**Where:** Project Scope and Boundaries → Evaluation Scope.

**Currently:** _"alert latency, defined as the time elapsed from AI detection to dashboard alert
delivery, with a target ceiling of 2 seconds as specified in **NFR-03**; … and operational
effectiveness, specifically the reduction in the notification gap as measured against the
15-second detection-to-dispatch target in **NFR-06**."_

**Change to:** NFR-03 → **NFR-04** (Alert Response Time). NFR-06 → **NFR-09** (Operational
Efficiency). As written, NFR-03 is Frame Rate Maintenance and NFR-06 is Report Generation Speed
— neither is the requirement being cited.

### 0.2 FR-10 does not exist

**Where:** Table 2, Functional Requirements. The list runs FR-01 … FR-09, then **FR-11**.

**Why it matters beyond the gap:** UC-2's postcondition still refers to _"FRS-10 auditing
purposes"_ — a dangling pointer to the deleted requirement. The audit-trail requirement is now
**FR-21**. Either renumber FR-11…FR-21 to close the gap, or keep the numbering and fix the UC-2
reference; do not leave both.

### 0.3 UC-5 sets a status the paper's own data dictionary does not define

**Where:** Use Case 5, steps 9–10.

**Currently:** step 9 has the operator update the log to _"Resolved"_; step 10 says _"The system
updates the database record with the status changed to **'Closed'**, the user's name as 'Closed
by,' and the exact 'Time Closed' timestamp."_

**Change to:** status **`Resolved`** throughout. Table 11 enumerates exactly four statuses —
`Unverified, Ongoing, Dismissed, Resolved` — and the database CHECK constraint agrees
(`backend/app/models/detection.py:24-31`). The _column_ names `closed_by_id` / `closed_at` are
correct and should stay; it is only the _status value_ that is wrong.

### 0.4 Three different alert-latency figures

| Site        | Says                                                                                     |
| ----------- | ---------------------------------------------------------------------------------------- |
| Objective 3 | "a sub-15-second alert propagation latency"                                              |
| NFR-04      | "within 2 seconds of collision detection"                                                |
| Phase 4     | "trigger sub-15-second WebSocket alerts on the React dashboard"                          |
| NFR-09      | 15 s, but for _detection-to-dispatch_ — a different quantity that includes operator time |

**Change to:** one consistent framing. Recommended: **2 s** is the backend→WebSocket→UI budget
(NFR-04); **15 s** is the end-to-end collision→operator-decision budget (NFR-09); Objective 3
and Phase 4 should cite the 15 s end-to-end figure explicitly as end-to-end, not as
"alert propagation".

### 0.5 The Administrator's role is described three incompatible ways

| Site                                                                  | Says                                                                                            |
| --------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| Ch. 1 Scope and Delimitations                                         | "Administrators limited to user account **and security** management"                            |
| Ch. 3 Research Design                                                 | "Administrators limited to user account management"                                             |
| Project Scope → User Scope, FR-02, and the Use Case Diagram narrative | "Administrators, who **inherit all Operator privileges** and additionally manage user accounts" |

**Change to:** the third. It is what the code does — `/admin/*` renders every Operator page plus
Users (`frontend/src/App.tsx:48-63`), and only the Users routes carry
`get_current_admin` / `require_admin` (`backend/app/api/routes/users.py:163-433`). Delete
"limited to" from both Scope paragraphs.

### 0.6 Two different augmentation lists — now resolved against the actual training call

**Where:** Phase 2 says _"the application of image augmentation techniques such as **brightness
adjustment, rotation, and cropping**"_; Deep Learning Implementation and Training Protocol says
_"targeted augmentations were applied. This included **mosaic** augmentation … as well as
randomized **brightness and contrast** adjustments"_.

**Change to** the verified list, sourced from the literal `model.train()` call
(`ai_engine/adas_transfer/training-configuration.md:55-80`, reused unchanged between the v2 and
v3 runs):

> Mosaic compositing (disabled for the final 10 epochs), horizontal flip (50% of images),
> brightness jitter (±40%), small-angle rotation (±5°), translation and scale jitter, and random
> erasing (40% probability). Saturation jitter and vertical flip are explicitly disabled — the
> former because it is a no-op on grayscale input, the latter because CCTV footage has a fixed
> up/down orientation that a vertical flip would violate.

**Neither "cropping" nor "contrast" survives.** `scale=0.9` is the closest thing to cropping that
actually runs, but it is continuous scale jitter, not a discrete crop step. "Contrast" is not a
native Ultralytics parameter in this call at all — the only path by which it could enter training
is Ultralytics' _optional_ albumentations integration, which the training notebook's own comment
(directly above the training call) flags as unverified for any given run and warns not to claim
without checking that run's environment-probe output. "Mosaic," "brightness," and "rotation" are
the three terms both paper sites already agree on — keep those, drop the other two everywhere
they appear, including Table 1's "Synthetic Data Augmentation" milestone entry, which should not
be read as implying cropping or contrast either.

### 0.7 Temporal scope disagrees with itself

Ch. 1 Scope: _"over a three-semester period (**2025–2026**)"_. Project Scope → Temporal Scope:
_"3 academic semesters spanning the **2025-2026 and 2026-2027** school years"_. Pick one.

### 0.8 Table 1 (Timelines and Milestones) is malformed

The Phase 4 and Phase 5 rows place SDLC and integration work — "Perform UAT with CDRRMO
dispatchers", "Install physical edge server", "Conduct formal Operator & Administrator
training" — in the **Track 1 (MLDLC)** column, and leave the **Track 2 (SDLC) column empty**.
Redistribute, or merge the two columns for the converged phases and say so.

### 0.9 "MLDC" vs "MLDLC"

Phases 1 and 3 write "Track 1 (MLDC)"; the section heading and Phase 2 write "MLDLC". The
Definition of Terms defines **MLDLC**. Normalise.

### 0.10 Figure 11's button list contradicts FR-07 and UC-5

**Where:** the Accident Alert Modal wireframe narrative.

**Currently:** _"two essential action buttons ('Confirm' and 'Dismiss')"_.

But FR-07 requires _"a 'Mute/Snooze' button"_ on the alert, and UC-5 step 4 begins _"The user
clicks 'Snooze.'"_ The paper's own wireframe omits a control its own requirement mandates.

**Change to:** either add Snooze to Figure 11 and build it (see §3.1), or withdraw the Snooze
control from FR-07/UC-5. Do not ship the paper with both.

### 0.11 The Context DFD promises a data store the Level-1 DFD does not have

**Where:** Context Level (Figure 5): the Administrator _"receives comprehensive user directories
**and audit logs**"_. Level 1 (Figure 6): _"six primary sub-processes supported by **four**
localized data stores"_ — D1 User, D2 Camera, D3 Detection Log, D4 System Health. There is no
audit store, and no process that would write one.

**Change to:** add a fifth data store, **D5 Audit Log**, to Figure 6 — matching the schema's
`audit_log` table (§2.1) — and wire it the way the real system writes it, rather than inventing a
new dedicated process. `backend/app/models/audit.py:10-37` enumerates 26 audited actions; grouped
by which existing process performs them:

| Process                                      | Audited actions it writes to D5                                                                        |
| -------------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| 1.0 Authenticate and Authorize Session       | `LOGIN_SUCCESS`, `LOGIN_FAILURE`, `LOGOUT`                                                             |
| 3.0 Manage Incident Alerts                   | `ALERT_CONFIRM`, `ALERT_DISMISS`, `ALERT_RESOLVE`, `ALERT_CORRECTION`, `ALERT_SNOOZE`                  |
| 4.0 Manage Camera Configurations             | `CAMERA_CREATE`, `CAMERA_UPDATE`, `CAMERA_ENABLE`, `CAMERA_DISABLE`, `CAMERA_DELETE`                   |
| 6.0 Administer User Directory                | `USER_CREATE`, `USER_UPDATE`, `USER_ENABLE`, `USER_DISABLE`, `USER_ROLE_CHANGE`, `USER_PASSWORD_RESET` |
| 5.0 Process Analytics and Hardware Telemetry | `REPORT_EXPORT`, `AUDIT_EXPORT`                                                                        |

Each of these is a **write** arrow into D5, on the same transaction as the primary action it
records (the guarantee documented in §2.6: an audited state change and its `audit_log` row commit
together, or neither does — there is no path that produces one without the other). 5.0 additionally
gets a **read** arrow from D5, gated to the Administrator (`GET /api/audit-logs/` and its
`/export` both require `get_current_admin`) — that read arrow is the mechanism that actually
satisfies the Context DFD's promised "audit logs" output, and is what turns 5.0 from an
Operator-only reporting process into the shared process its own Context-level promise requires.

**One loose end worth a sentence, not a redraw:** five actions in the same 26-action catalog don't
map onto any of the six named processes at all — `USER_PROFILE_UPDATE` and `USER_PASSWORD_CHANGE`
(self-service, available to Operators too, but 6.0 is described as "isolated for Administrator
use"; see also §0.15), and `ALARM_SETTINGS_UPDATE`, `BACKUP_TRIGGER`, `RESTORE_TRIGGER` (no
process covers alarm settings or maintenance at all). Adding D5 closes the contradiction this item
is about; those five are a smaller, separate gap in the six-process decomposition itself, worth
flagging here but not worth redrawing the whole diagram over.

### 0.12 The restore procedure is stranded inside the Wireframes section

The five-step "Flag and Restart" description sits after Figure 17 and before Deployment
Architecture, inside a section introduced as depicting "interface layouts". It is not a
wireframe.

**Change to:** move it to Deployment Architecture or a Maintenance subsection. While moving it,
fix _"hydrating the dashboard for the **Supervisor**"_ — the schema knows only `Admin` and
`Operator` (`backend/app/models/enums.py:4-6`). The Use Case Diagram narrative does license
"Supervisor" as an informal alias for Administrator, so either use the alias consistently or
drop it; right now it appears in the restore steps, UAT step 4, and Administrator Training
without ever being introduced in those sections.

### 0.13 Tense asserts things that did not happen

Project Scope is future-tense ("_will be_ trained", "_is scheduled_"); Deployment Architecture,
Deployment & Implementation, and UAT are past/present ("the server _is physically installed_",
"UAT _was conducted_"). This is the surface symptom of §1.0 — fix them together, not separately.

### 0.14 Ch. 1 Scope and Ch. 3 Research Design are near-duplicate paragraphs that have drifted

The two paragraphs are otherwise identical but differ on the Administrator's remit (§0.5).
Make one canonical and have the other cross-reference it, rather than restating.

### 0.15 UC-2's "Change Password" vs the FRS's wording

UC-2 step 2 lists _"Change Password"_ among Administrator actions. FR-03 calls the same thing
_"change passwords"_. The implementation is an admin-initiated **reset** that revokes all of the
target user's sessions (`backend/app/api/routes/users.py:400-409`, reason `password_reset`) —
materially different from the self-service change in UC-3. Worth distinguishing the two by name
in both FR-03 and UC-2, since they have different security consequences. (The modal itself is
titled "Change Password", `frontend/src/pages/users/ResetPasswordModal.tsx:76` — so the UI
matches the paper; it is the naming collision with UC-3 that is the problem.)

### 0.16 "over 418 CCTV cameras"

Ch. 2's Deep Learning synthesis says the project _"must process live RTSP streams from **over
418** CCTV cameras"_. 418 is the total, not a floor. Elsewhere the paper consistently says 418.

---

## Priority 1 — Claims the evidence contradicts

### 1.0 The deployment overclaim — a full-document sweep

**This is the most important item in the audit.** The paper repeatedly narrates a production
installation at the Lipa CDRRMO command center that never took place, and it does so in the
same document that twice states the opposite. The system is a proof-of-concept and needs to
read as one throughout.

**The paper already says it was never deployed**, in three places, all accurate:

- Ch. 1 Scope: _"All system testing and performance evaluations took place exclusively on
  **researchers' independent hardware in a simulated environment** to avoid disrupting active
  emergency monitoring."_
- Project Scope → Out of Scope: _"All performance evaluations and testing procedures will be
  conducted on the **research team's independent hardware** to simulate the live deployment
  environment."_
- Testing Strategy Overview: _"all testing was conducted exclusively within a **controlled,
  isolated LAN staging environment**"_, with MediaMTX standing in for the DSS Pro media gateway.
  ✓ Accurate — see `ai_engine/README.md:49-52`, `scripts/start-sim.ps1`, `mediamtx.yml`.

**Against that, the following passages assert a real installation.** Each needs rewording.

#### A. Outcome claims — the strongest overclaim in the paper

Ch. 1 Scope and Ch. 3 Research Design (the duplicated paragraph, §0.14) both open:

> _"The project involved the development, evaluation, and **edge-server deployment** of a
> real-time road accident detection & alert system **that accelerated emergency response times
> in Lipa City, Batangas**…"_

This asserts a measured real-world outcome — that response times in the city actually improved
— two clauses before calling the architecture a "proof-of-concept". No such measurement exists
or could exist. The same paragraph also says _"**Deployed on** a dedicated edge inference
server, the system **integrated**…"_ and _"RBAC **was enforced**"_.

**Change to:** something like —

> The project covers the development and evaluation of a real-time road accident detection and
> alert system **intended to reduce** emergency notification latency in Lipa City, Batangas.
> The proof-of-concept was built and measured on the research team's own hardware against an
> isolated LAN that simulates the CDRRMO's VMS; it was not installed on agency infrastructure.

#### B. Significance of the Study states benefits as realised fact

_"reduces cognitive overload"_, _"minimizes operator fatigue"_, _"enables staff to transition
from passive observation to active, effective dispatching"_, _"facilitates faster deployment for
units such as local police"_, _"addresses the urgent needs associated with severe medical trauma
by **reducing the notification gap from minutes to seconds**. This improvement **ensures** that
victims receive timely medical intervention"_, _"**fosters** a sense of security … **makes the
city safer**"_.

**Change to:** conditional throughout — "is intended to", "would allow", "is designed to". A
Significance section may argue for prospective benefit; it may not report it as achieved. The
notification-gap claim in particular is the study's headline and currently reads as a finding.

#### C. Deployment Architecture — the densest cluster, uniformly past tense

> the system _"utilized"_ a localized deployment architecture; _"this system **consolidated** all
> processing onto a high-performance physical machine **deployed directly within the Lipa CDRRMO
> command center**"_; client workstations _"**connected** to the server exclusively through the
> internal LAN"_; the server _"simultaneously **hosted**"_ and _"**served** the compiled React
> frontend"_; this _"**eliminated** network transit latency"_; _"The deployment environment
> **employed** enterprise-grade hardware"_; _"The hardware specification **included** a Dell
> PowerEdge R760xa…"_; _"The server **featured** a multi-GPU array of 8 NVIDIA L4"_; _"The edge
> server **ran** a modern 64-bit enterprise Linux distribution"_; _"The edge server **connected**
> via a Gigabit copper port (8GT) to one of the command center's **Ruijie Reyee aggregation
> switches** and **was assigned** a static IP address"_; _"This setup **placed** the server on the
> same subnetwork as the VMS, specifically the **Dahua DSS Pro** server"_; _"the URL **included**
> the subtype=1 parameter"_; _"The database **was configured** with WAL … This configuration
> **eliminated** database locking errors."_

#### D. Design Constraints and Assumptions asserts the agency granted real access

> _"The Lipa CDRRMO IT administration **authorized** connection of the edge server to the core
> network switches and **allocated** a static IP address within the restricted CCTV VLAN.
> Furthermore, the agency **provided the necessary system credentials**, specifically the
> authorized usernames, passwords, and server IP configurations, required for the system to
> authenticate and request streams from the infrastructure."_

Also: _"An array of eight NVIDIA L4 GPUs **supported** up to 418 cameras"_; _"The system
**interfaced directly** with the Dahua DSS Pro Server. Operating as a headless client, the edge
server **transmitted** automated RTSP requests"_; and an asserted, tested failure mode —
_"If the command center's external ISP fiber connection **was severed** during a natural
disaster, localized RTSP ingestion, AI inference, and intra-VLAN WebSocket alert deliveries
**remained operational**."_

This paragraph is the most exposed in the whole document: it names specific credentials and
authorisations from a named third-party agency. If those were granted, the paper should evidence
it; if they were assumptions, it must say so — the section is literally titled "Assumptions".

#### E. The VLAN topology is written as an existing network

_"The infrastructure's logical network topology **is divided** into four distinct broadcast
domains"_; VLAN 50 _"**Houses** the edge inference server, central management servers, and NAS
arrays"_; _"Cross-VLAN communication **is executed** via a Router-on-a-Stick topology"_.

**Change to:** present it as the designed target topology (Figure 18 is a design artifact, which
is fine) — "the design segments the network into four broadcast domains", "VLAN 50 would house…".

#### F. Definition of Terms — Edge Inference Server

_"The localized, enterprise-grade physical computer **deployed within the CDRRMO network** that
hosts the database, web application, and AI processes."_ Reword to describe the role, not a
completed installation.

#### G. Phase 5 and the Deployment & Implementation chapter

_"The hardware **is permanently installed** within the Lipa CDRRMO command center and
**integrated securely** into the agency's existing CCTV VLAN"_; _"the enterprise-grade inference
server (equipped with NVIDIA L4 GPUs) **is physically installed** within the command center"_;
_"The edge server **is rack-mounted** and connected to the command center's core aggregation
switches"_; _"The system **is securely authenticated** as a headless client to the Dahua DSS Pro
server"_; camera metadata _"**are exported** from the Dahua VMS and systematically **migrated**
into the system database"_.

This whole chapter reads best as an explicit **deployment plan** — retitle it or open it with a
sentence establishing that it describes the intended procedure, not work performed.

#### H. Training Protocol

_"…before the finalized .engine model was pulled down and **deployed locally to the independent
edge server** for Phase 4 LAN stress testing."_ Compounds §1.4's TensorRT problem with a
deployment claim; both go in the same edit.

#### I. UAT is reported as completed with no results

_"UAT **was conducted** to validate the system's operational lifecycle…"_ — followed by
participants, a five-step procedure, and five assessment domains, all in past tense. No results
appear anywhere in the document, and Chapters 4–5 do not exist.

**Change to:** future/planned tense until results exist. If UAT has genuinely run, the results
belong in the paper; if it has not, "was conducted" cannot stand.

#### J. The omission — the paper never says what hardware was actually used

Every measurement in the evidence base comes from a **GTX 1650**
(`ai_engine/docs/port-handover.md:27`, `ai_engine/machine_profile.json`). That machine appears
nowhere in the paper. Adding it matters as much as softening the R760xa language: it is what
turns the 418-camera figure from an assertion into a documented extrapolation from a real
measurement.

#### Recommended global treatment

Split every passage above into two clearly-labelled registers. This is standard practice in a
systems paper and concedes nothing:

> **Prototype (built and measured).** Single-GPU development workstation (NVIDIA GTX 1650),
> MediaMTX simulating the Dahua DSS Pro media gateway over an isolated LAN, evaluated against 17
> held-out Lipa CCTV clips. Measured sustainable capacity: 8 cameras at 15 FPS, 13 at 10 FPS.
>
> **Target production specification (designed for, not executed).** Dell PowerEdge R760xa,
> 8× NVIDIA L4, the four-VLAN topology, Dahua DSS Pro substream ingest, 418 cameras.

The R760xa design and the 418-camera target both survive — as a specification the measurements
scale toward, rather than as a history. That is a stronger position than the current text,
because it is one the team can defend line by line.

---

### 1.1 Remove mAP as an acceptance criterion — and fix all ten sites

**Currently (NFR-01):** _"The AI inference engine shall maintain a minimum Mean Average Precision
(mAP) of 85% and an Intersection over Union (IoU) threshold of ≥ 0.50…"_

**Change to** an event-level criterion measured on held-out deployment footage:

> The system achieves event-level recall of at least 75% on standard-difficulty collisions in
> held-out Lipa CCTV footage, with a false-alarm rate at or below 0.5 events per minute of
> ordinary traffic.

**Why.** `adas_transfer/SPEC.md:400-408` records that the v3 run's `accident` mAP50 of **0.956**
is **leaked**: the incident-level validation split failed and was skipped, so near-duplicate
frames of the same crash sat in both training and validation. For scale, a model already known
to be broken — one that fired 0.89 confidence on a normally-driving red sedan — scored **0.986**
by the same measure (`SPEC.md:31-35`). The repository carries a standing rule, in five separate
files, never to quote that number.

Quoting mAP as an acceptance threshold commits the study to a figure its own evidence rejects.
The replacement is **more** demanding, not less: recall and false-alarms-per-minute on real
footage from the target city is a stronger claim than a benchmark score, and the reasoning for
rejecting mAP is itself a defensible research finding.

**Numbers available to quote** (`SPEC.md:328-336`, native frame rate): **8/10** standard recall
(80%), **0/6** hard recall, **3** false positives over ~11 minutes (**0.27/min**), **0** false
positives on the crash-free clip, **+3.02 s** median alert latency. Report standard and hard
**separately** — a blended 8/16 hides which crashes were winnable.

**Propagation — all ten sites:**

| #   | Site                                                | What it says now                                                                                                                  |
| --- | --------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| 1   | Objective 3                                         | "achieving a minimum Mean Average Precision (mAP) of 85% (at IoU ≥ 0.50)"                                                         |
| 2   | Ch. 2 → Performance Metrics and Hardware Trade-offs | a **four-paragraph subsection** whose entire purpose is to justify 85%                                                            |
| 3   | Ch. 2 → Synthesis                                   | "balancing mAP with low inference latency"                                                                                        |
| 4   | Project Scope → Evaluation Scope                    | "detection accuracy, as measured by the mean average precision (mAP) … on a held-out test set"                                    |
| 5   | Phase 1                                             | "formally establishing an 85% mAP baseline"                                                                                       |
| 6   | Phase 3                                             | "continues strictly until the model successfully breaches the predefined 85% mAP and 0.50 IoU thresholds"                         |
| 7   | Table 1, Phase 3 row                                | "Hit mAP/IoU target thresholds"                                                                                                   |
| 8   | NFR-01                                              | the requirement itself                                                                                                            |
| 9   | Training Protocol intro                             | "To achieve the 85% mAP operational threshold…"                                                                                   |
| 10  | Model Architecture Selection + the FP16 bullet      | "the 85% mAP threshold required for accurate scene classification"; "without a mathematically significant drop in the target mAP" |

All ten quotes above were re-checked directly against the live Doc on 2026-08-14; site 2 is four
paragraphs, not five as the previous pass counted, but is otherwise as described.

### Site-by-site replacement text, ready to paste

Every block below is drop-in replacement text for the quoted passage at that site — copy the
blockquote over the current sentence/paragraph/cell. Paraphrased connective text outside the
blockquotes is guidance, not something to paste.

**Site 1 — Objective 3.** This sentence also carries the latency-framing problem from §0.4
("alert propagation" vs. end-to-end); both are fixed together since they're the same sentence.

> To validate the system's performance by achieving an event-level recall of at least 75% on
> standard-difficulty collisions in held-out CCTV footage, with a false-alarm rate at or below 0.5
> events per minute of ordinary traffic, and a sub-15-second end-to-end collision-to-operator-
> decision latency, ensuring effective minimization of the notification gap and facilitating
> faster emergency intervention to mitigate injury severity and traffic congestion.

**Site 2 — Performance Metrics and Hardware Trade-offs.** Rewritten to keep all five citations
(Ahmed et al. 2023, Li et al. 2025, Minh et al. 2025, Gurusamy et al. 2025, Sousa & Junior 2025)
and the literature's actual finding — that lightweight single-stage models in the 80–88% mAP
range are consistently judged deployment-ready, and that sub-1% mAP differences are treated as
immaterial next to inference speed — while retargeting the argument at _why mAP itself should not
be the acceptance gate_, using this project's own leaked-split finding as the closing evidence:

> Recent literature emphasizes that in real-time surveillance and edge-computing applications,
> inference speed and hardware constraints necessitate a strategic trade-off regarding model
> accuracy, and that lightweight single-stage architectures scoring in the 80%–85% mAP range are
> consistently judged deployment-ready rather than deficient. Ahmed et al. (2023) developed a
> real-time computer vision system for traffic accident detection and severity classification
> using a YOLOv5 architecture that attained an mAP of 83.3% and proved highly effective at
> triggering automated alert messages to emergency responders. Li et al. (2025) similarly found
> that a baseline YOLOv5n at 82.4% mAP50 delivered strong, stable real-time performance, and
> explicitly cautioned against chasing higher accuracy through heavier two-stage models such as
> Faster R-CNN, whose 28.2 million parameters and 37.52 GFLOPs drastically increase inference time
> for a marginal accuracy gain. Research on live CCTV feeds specifically has gone lower still:
> Minh et al. (2025) reported that YOLOv8 models scoring only 60.9%–67.4% mAP50 remained highly
> capable of classifying traffic conditions as "Normal" or "Accident" without critical failures.
>
> This convergence — real systems shipping and succeeding well below any fixed mAP ceiling —
> is itself evidence against using mAP as an acceptance threshold, not for it. Gurusamy et al.
> (2025) reinforce the same point from the opposite direction: their improved YOLOv5, trained on a
> custom, self-built dataset, reached 88.7% mAP, and Sousa & Junior (2025) found that on embedded
> NVIDIA platforms, mAP differences under 1% routinely justify choosing the faster, lighter model
> anyway. Across this literature, mAP functions as a rough development-time health check, not a
> deployment gate — and for good reason: it is computed against a benchmark split curated by the
> dataset's own authors, which measures how well a model fits that split, not how it behaves on
> live, unlabelled footage of events it has never seen.
>
> This distinction is not theoretical for this project. During training, an incident-level
> validation split — designed specifically to keep near-duplicate frames of the same crash from
> leaking across train/validation — failed silently on one run and fell back to a frame-level
> split. Under that leaked split, a YOLO checkpoint already known to be broken (it had fired 0.89
> confidence on an ordinary, normally-driving sedan) scored 0.986 mAP50: a near-perfect benchmark
> result from a model that could not be trusted in the field. A metric that cannot tell a broken
> model from a working one under a routine split failure cannot be the criterion this study is
> judged against, however well-supported it is in the literature as a training-time signal.
>
> Synthesizing these findings, the architecture of the proposed system requires processing
> multiple simultaneous RTSP streams via multiprocessing on localized edge hardware. Prioritizing
> a lightweight model in the same performance class as the literature's reported 80–88% mAP range
> — evaluated at deployment time by event-level recall and false-alarm rate on held-out footage,
> not by mAP itself — prevents the severe latency bottlenecks identified above. Because the system
> also implements a strict Human-in-the-Loop workflow, where operators verify every snapshot
> before dispatch, this performance tier is sufficient for rapid early-warning detection without
> demanding the prohibitive computational resources that a heavier, higher-capacity model would
> otherwise require.

**Site 3 — Ch. 2 Synthesis.**

> The YOLO architecture is identified as the most suitable technical solution, balancing detection
> reliability with low inference latency (FPS).

**Site 4 — Project Scope → Evaluation Scope.** Only the first criterion changes; the NFR-04/NFR-09
references are already correct (§0.1 was applied).

> Evaluation Scope: System performance will be evaluated against four primary criteria: detection
> accuracy, as measured by event-level recall on standard-difficulty collisions and false-alarm
> rate per minute of ordinary traffic in held-out Lipa CCTV footage; alert latency, defined as the
> time elapsed from AI detection to dashboard alert delivery, with a target ceiling of 2 seconds as
> specified in NFR-04; inference speed, targeting a minimum of 10 to 15 frames per second per
> camera stream; and operational effectiveness, specifically the reduction in the notification gap
> as measured against the 15-second detection-to-dispatch target in NFR-09.

**Site 5 — Phase 1.** (While in this sentence: it also still reads "Track 1 (MLDC)" where §0.9
wants "MLDLC" — worth fixing in the same pass since you're already editing this line.)

> Track 1 (MLDLC) defines the model's target detection parameters, formally establishing an
> event-level recall and false-alarm-rate baseline to optimize real-time edge inference. This
> phase simultaneously evaluates the physical constraints of the Lipa City CCTV network, such as
> variable lighting, frame rates, and camera angles, and sets the corresponding data collection and
> annotation protocols required to train the model within these real-world limitations.

**Site 6 — Phase 3.** The new framing is also more accurate to what actually happens — checkpoint
selection really is done by scoring against held-out footage, not by a mAP/IoU gate (§1.5).

> Track 1 (MLDLC) executes its core experimental loop. The YOLO model architecture is configured
> and trained on the prepared hybrid dataset, and each checkpoint is subsequently evaluated against
> the strict operational targets established in Phase 1: an event-level recall of at least 75% on
> standard-difficulty collisions and a false-alarm rate at or below 0.5 events per minute, measured
> on held-out deployment footage rather than a training-side validation split. Failure modes
> identified during evaluation, such as degraded detection under nighttime glare or occluded
> vehicles, prompt targeted dataset curation, augmentation, and retraining. This iterative
> train-evaluate-refine cycle continues until a checkpoint reaches the predefined recall and
> false-alarm-rate thresholds. Once selected, the model weights are locked, and the inference
> engine is exported and optimized for deployment on the localized edge server to ensure it meets
> the low-latency processing requirements of the command center's Human-in-the-Loop workflow.

**Site 7 — Table 1, Phase 3 row.** Change the bullet _"Hit mAP/IoU target thresholds"_ to:

> Hit recall/false-alarm-rate target thresholds

**Site 8 — NFR-01.**

> NFR-01 Algorithmic Accuracy — The AI inference engine shall achieve an event-level recall of at
> least 75% on standard-difficulty vehicle-to-vehicle collisions and a false-alarm rate at or below
> 0.5 events per minute of ordinary traffic, measured on held-out deployment footage.

**Site 9 — Training Protocol intro.**

> To achieve the event-level recall and false-alarm-rate operational thresholds while maintaining
> sub-15-second end-to-end alert latency, the AI model underwent a strict configuration and
> training pipeline optimized for edge deployment. The implementation was broken down into dataset
> preparation, architecture selection, hyperparameter tuning, and hardware-specific compilation.

**Site 10 — Model Architecture Selection paragraph, and the FP16 bullet.** Two different fixes:

> …perfectly balancing the high-speed computational requirements necessary for concurrent live
> RTSP stream ingestion with the recall and false-alarm-rate thresholds required for reliable
> accident classification.

replaces just the trailing clause of the Model Architecture Selection paragraph (keep everything
before it — §1.5 already confirms the YOLO26-nano claim itself is correct). The FP16 bullet's
_"without a mathematically significant drop in the target mAP"_ phrase becomes moot rather than
needing its own edit: §1.6 replaces the entire FP16/Dynamic Batching/Batch Sizing bullet list with
a paragraph about measured batching and unexercised export flags that doesn't mention mAP at all.
Apply §1.6 alongside this site rather than patching the phrase in isolation.

### 1.2 Report the hard-difficulty result honestly

**Add**, near the revised NFR-01:

> The clip set was stratified into `standard` and `hard` **before any model was run**. Every
> `hard` clip is missed, without exception. This is a data-coverage limit — the training source
> never contained crashes of that geometry — not a tuning shortfall.

**Why.** Stating it plainly, with the pre-registration
(`ai_engine/eval/labels.csv`, difficulty column), converts an apparent weakness into evidence of
honest methodology. Discovered by a panel instead, it looks concealed.

### 1.3 The dataset description is materially wrong

**Currently (Training Protocol):** _"The model was trained on a hybrid dataset consisting of
publicly available vehicular collision imagery and custom archival footage curated from the Lipa
CDRRMO CCTV network. … the dataset was partitioned into a 80% Training, 10% Validation, and 10%
Testing split."_

**Four separate problems**, per `adas_transfer/NOTICE.md:47-88` and `SPEC.md`:

1. **The Lipa CCTV footage was never trained on.** It is the 17-clip evaluation corpus, held out
   as test-only and permanently so (`SPEC.md:338-340`).
2. **The accident imagery is partly synthetic.** The sole `accident` source,
   `vehicle-accident-m2ryw`, contains Gemini-generated images, Sri Lankan road photographs, and
   PASCAL VOC files (`NOTICE.md:74-78`).
3. **The 80/10/10 split cannot be claimed.** The incident-level validation split failed and was
   skipped — that is precisely why the mAP is leaked (§1.1). A stated split and a skipped split
   cannot both be true.
4. **Data Scope claims coverage the corpus lacks** — _"augmented to represent … nighttime glare,
   **rain**, and varying intersection geometries"_. There is no rain footage in the evaluation
   set at all. Night is genuinely covered (8 of 17 clips) and should be kept.

**Change to** an accurate description of the three Roboflow sources, the class-collapse mapping,
the synthetic component, and the fact that the Lipa corpus is held-out evaluation data. Note
also that Ch. 2's Synthesis promises the Lipa footage would _"calibrate the inference engine to
recognize region-specific vehicles, such as jeepneys and tricycles"_ — the outcome was achieved
(`SPEC.md:375-378`: the Philippine retrain removed jeepney/tricycle false alarms without costing
recall) but by a different mechanism, via the two Roboflow vehicle datasets. Align the Synthesis
with what was actually done.

**Ready-to-paste fix for the Ch. 2 Synthesis paragraph** (_"To address this 'sim-to-real'
gap..."_, the paragraph directly preceding the mAP/FPS sentence fixed in §1.1 site 3):

> To address this "sim-to-real" gap, the literature recommends developing a highly localized,
> hybrid dataset. By combining the public accident repository with dedicated, publicly available
> Philippine vehicle datasets covering jeepneys and tricycles
> (`ai_engine/adas_transfer/training-configuration.md:98-103`: `traffic-vehicle-detection-e6kgi`
> and `kent-rafiel/vehicle-5kcdl`, both Roboflow Universe, CC BY 4.0), the inference engine can be
> calibrated to recognize these region-specific vehicles as a discriminative foil, thereby
> enabling high-confidence anomaly detection where generic AI models are ineffective. The Lipa
> CDRRMO's own archival CCTV footage is reserved entirely as a held-out evaluation corpus,
> measuring detection performance on real local footage the model never trained on, rather than
> being folded into the training set.

This keeps the paragraph's role in the Synthesis (setting up the hybrid-dataset methodology Ch. 3
elaborates on) while fixing the actual mechanism: the jeepney/tricycle calibration came from two
public Philippine vehicle datasets acting as a discriminative foil, not from CDRRMO's own
footage, which never enters training at all (§1.3 problem 1) — it is the fixed, permanent
evaluation corpus the whole recall/false-alarm story in §1.1 is measured against.

### 1.4 Licence exposure is undocumented

`adas_transfer/NOTICE.md:114-120` records two open items the paper never mentions:

- **`vehicle-accident-m2ryw` — licence NOT ESTABLISHED**, and BMD-45 (`iisc-aim/BMD-45`) **NOT
  VERIFIED**. The other two datasets are verified CC BY 4.0.
- **Ultralytics 8.4.104 is AGPL-3.0**, whose network-use copyleft is flagged in-repo as a
  submission blocker.

**Add** a short Limitations paragraph. An academic paper that ships a model trained on
unestablished-licence data, and served through AGPL software, is better off naming the exposure
than being asked about it.

### 1.5 Weights, epoch count, and TensorRT

**Currently:** _"The model was trained over **150 epochs**…"_ and _"the finalized PyTorch weights
(.pt) were exported and compiled into a highly optimized NVIDIA **TensorRT engine format
(.engine)**"_; _"…before the finalized **.engine** model was pulled down and deployed locally…"_.

**Change to:**

> The deployed model is a YOLO26-nano detector (2.4 M parameters) trained for **50 epochs**,
> loaded directly from its PyTorch checkpoint (`epoch50.pt`), with **no TensorRT compilation step
> in the deployment path**.

**Why.** `ai_engine/config.py:44` sets `WEIGHTS_PATH` to `epoch50.pt` and loads it directly —
there is no engine build anywhere in the running system, and `ai_engine/tests/test_config.py`
asserts `best.pt` and `best.engine` **do not exist**. Both were deleted during the detection-core
port: `best.pt` had lost checkpoint selection across all three training runs, and `main.py` had
been _preferring_ a stale TensorRT build of it, silently running the wrong model on every launch.
`ai-trt` (`pyproject.toml:76`) is an opt-in extra nothing in the codebase imports.

**The architecture claim is correct** — YOLO26-nano is what was adopted (`SPEC.md:323`), chosen
after scoring all eight exported checkpoints. Keep it.

### 1.6 FP16 export flags presented as enforced execution parameters

**Currently:** _"The following execution parameters were **enforced** to maximize hardware
utilization…: FP16 Precision (half=True) … Dynamic Batching (dynamic=True) … Batch Sizing
(batch=8)…"_

**Change to:**

> Batching is real and load-bearing — the pipeline groups all active cameras into a single
> inference call per tick, and per-batch latency was measured directly (16.5 ms at batch = 1,
> rising to 114.1 ms at batch = 16; see §4.1). `half`, `dynamic`, and `batch=8` are TensorRT
> _export_ flags, meaningful only for an engine build; since no engine is built (§1.5), they
> describe an export configuration that was prepared but never exercised.

**Why.** This is not a retraction of the batching claim — batching is measured, real, and exactly
what makes multi-camera throughput viable on one GPU (`ai_engine/detector.py:90-105`,
`ai_engine/pipeline.py:135-166`). Separating "batching happens" (true) from "via a compiled
TensorRT engine" (false) leaves the stronger claim standing on its own evidence.

### 1.7 Password hashing algorithm

**Currently:** _"passlib with **bcrypt** for cryptographic password hashing"_ (Frameworks and
Libraries) and _"The **bcrypt-hashed** password"_ (Table 9, `password_hash`).

**Change to:**

> Passwords are hashed with **Argon2id** via `passlib`'s Argon2 backend. Argon2id was the only
> algorithm the codebase ever used for this purpose; there is no bcrypt code path to migrate
> away from.

**Why.** `backend/app/core/security.py:13` configures
`CryptContext(schemes=["argon2"], deprecated="auto")`, and the adjoining comment reads
_"No bcrypt->argon2 migration path is needed"_. `pyproject.toml` lists `argon2-cffi` and
`passlib[argon2]`, not `passlib[bcrypt]`. Argon2id is memory-hard and the current OWASP default,
so this upgrades the security story rather than merely fixing a name.

**Worth adding while you are there:** the unknown-user path burns a real Argon2id verification
against a fixed dummy hash (`security.py:18, 25-29`) specifically so response timing cannot be
used to enumerate usernames.

### 1.8 GPU telemetry library

**Currently:** _"For hardware monitoring, psutil and **gputil** are employed…"_

**Change to:**

> System health monitoring uses `psutil` for CPU/memory/disk telemetry and **`nvidia-ml-py`**
> (the official NVIDIA Management Library binding, imported as `pynvml`) for GPU telemetry.

**Why.** `gputil` is not a dependency anywhere in the project.
`backend/app/services/hardware.py:151` lazily imports `pynvml` inside `read_gpus()` so that
importing the health module doesn't require an NVIDIA driver on machines without a GPU;
`backend/app/core/monitor.py:132` calls it to populate each health sample. `nvidia-ml-py` is
NVIDIA-published and actively maintained; `gputil` has been unmaintained for years.

### 1.9 `confidence_score` semantics — four sites, not three

**Currently**, in four places (re-checked directly against the live Doc, 2026-08-14; all four
are still unedited):

| Site                                                                         | Says                                                                                                                                                    |
| ---------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Table 11 (`confidence_score`)                                                | "The probability score (e.g., **0.88** for 88%) outputted by the YOLO model indicating its certainty of the vehicle collision."                         |
| Definition of Terms → Confidence Score                                       | "A probability metric generated by the YOLO model indicating its mathematical certainty that a detected visual anomaly is an actual vehicle collision." |
| Figure 17 narrative (the **Ongoing** Accident Details Modal specifically)    | "...critical incident telemetry, including Timestamp, Camera Name, and **AI-Confidence Score**, is displayed..."                                        |
| **UC-9 step 7** (Logs tab / historical record modal — not previously listed) | "...the complete core telemetry (**AI-Confidence Score**), and the operational Audit Trail..."                                                          |

**Change to:**

> `confidence_score` is the **peak per-frame confidence observed within an accumulated event**,
> not a single-frame probability (`ai_engine/accident.py:77`, `event.peak_conf`).

**The audit's own original fix for the worked example doesn't hold up — read before pasting.**
The previous version of this item said to "pick a value inside the genuine range instead" of
0.88. That range doesn't exist in the evidence base: `SPEC.md:269-272` only records the
**adopted** model's three **false-positive** peaks (**0.869 / 0.844 / 0.649**); the
genuine-detection figures (**0.536 / 0.459 / 0.741**) belong to the **previous** model — the
exact substitution error the superseded audit made (see
[Corrections](#corrections-to-the-superseded-audit)). Inventing an adopted-model true-positive
number to fill the gap would repeat the sourcing failure this document exists to catch.

**Better fix: use the false-positive numbers to make the actual point, instead of dodging it.**

> `confidence_score` — the peak per-frame confidence the YOLO model observed while the
> accumulator built this event, not a single-frame probability. A value in the 0.84–0.87 range
> was measured on both a genuine collision and on one of the system's three recorded false
> positives — confidence alone does not distinguish them; persistence over time does (§4.9).

Drop this in place of Table 11's `0.88` example and fold the same framing into the Definition of
Terms entry. **No numeric example is currently available for a confirmed adopted-model true
positive** — if one is needed, it has to come from re-running `eval/sweep.py` against the Lipa
clips, not from either of the two numbers already circulating in the paper.

**Sites 3 and 4 (Figure 17, UC-9) need no wording change**, only consistency once the definition
above is fixed — both just use "AI-Confidence Score" as a field label, and neither claims a false
semantic on its own. Optional: rename the label to "Peak Confidence Score" in both places for
extra clarity, but that's cosmetic, not a correction.

### 1.10 The Definition of Terms calls JWT "stateless"

**Currently:** _"JSON Web Token (JWT): The token-based, **stateless** authentication mechanism
used to securely manage persistent user sessions…"_

**Change to:** the opposite, which is both what the code does and the stronger claim —

> A JWT delivered as an `HttpOnly`, `Secure` cookie and backed by a server-side `auth_session`
> row, so an individual session can be revoked ahead of its natural expiry. The design is
> deliberately **stateful**: a purely stateless JWT cannot be revoked at all.

→ `backend/app/models/user.py:81-105`, `backend/app/api/dependencies.py:48-101`. See also §2.5.

### 1.11 WSS is credited with pushing hardware telemetry

**Currently:** _"WebSocket Secure (WSS): The bi-directional communication protocol utilized by
the backend to instantly push real-time collision alerts **and hardware telemetry** to the client
browser…"_ — and UC-6 step 3: _"Every 10 to 15 seconds, the system **receives a batched telemetry
packet**…"_

**Change to:** telemetry is **REST-polled by the client**, not pushed. The seven WebSocket event
types (`backend/app/schemas/events.py:21-31`) are `CONNECTION_READY`, `NEW_DETECTION`,
`ALERT_STATUS_UPDATE`, `CAMERA_STATUS_UPDATE`, `SNOOZE_ACTIVATED`, `RE_ALARM`,
`MAINTENANCE_NOTICE`. None carries health data. The System Health page polls live metrics every
15 s and the status pill every 30 s (`frontend/src/pages/SystemHealth.tsx:176, 181-184`), while
the backend samples into memory every **5 s** (`HEALTH_SAMPLE_SECONDS`). See §4.4 for NFR-05.

### 1.12 NFR-16 (daily restart) and NFR-18 (daily backup) are both unimplemented

**NFR-16** — _"the system shall automatically restart every 24 hours … at 3:00 AM, completing
memory flush and recovery in under 10 seconds."_ No such job exists.
`backend/app/main.py:145-242` registers every scheduled job — cooldown sweep, snooze sweep,
expired-session cleanup, five health jobs, export-artifact cleanup, WS session revalidation —
and none is a daily restart.

**NFR-18** — _"The system shall execute **automated daily backups** of the SQLite database…"_
Equally unscheduled. There is no backup job in `main.py`; backups run only via
`POST /api/system/backups` or an external orchestrator calling `python -m app.maintenance`
(`backend/app/maintenance/cli.py:316-355`, which takes `--origin manual|scheduled`, i.e. expects
to be driven by cron/systemd).

**And `MAINTENANCE_HOUR_LOCAL` (default 3) is dead config** — zero references anywhere in `app/`
outside `config.py:117`. It looks like the hook for both requirements and was never wired up.

**Compounding this**, the Maintenance and Support Plan refers to downloading _"the **scheduled**
database backup and its associated visual snapshots from the **air-gapped Network Attached
Storage (NAS)**"_. Neither the schedule nor any NAS integration exists; `BACKUP_DIR` is
`var/backups` on the server itself (`config.py:62`).

**These are code gaps, not documentation errors.** Two honest paths for each: implement the
scheduled job (a `trigger="cron", hour=MAINTENANCE_HOUR_LOCAL` entry alongside the existing jobs,
which is a small change given the setting already exists), or restate the requirements as
orchestrator-driven with the operational procedure documented. Which is right is a team decision
— flagged here so it isn't discovered live.

### 1.13 Annotation methodology overclaims manual work

**Currently**, in two places:

| Site                                                                          | Says                                                                                                                                   |
| ----------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| Phase 2 (Design and Data Preparation)                                         | _"This is followed by systematic **manual bounding-box annotation** and the application of image augmentation techniques…"_            |
| Development Tools and Technologies → Machine Learning Environments → Roboflow | _"Utilized primarily as the central dataset management platform for **bounding-box annotation** and programmatic image augmentation."_ |

**Change to:**

> No manual bounding-box annotation occurs anywhere in this pipeline. Every source dataset
> arrives pre-annotated by its original creators; the one coverage gap — nyanko's accident images
> missing boxes for the bystander vehicles in frame — is closed by an automated pseudo-labeling
> step, not by hand. Roboflow's role was hosting, forking, and managing these already-annotated
> Universe datasets and running the class-collapse and ratio-capping pipeline against them, not
> drawing boxes.

**Why.** `ai_engine/adas_transfer/training-configuration.md:105-107` (§4, "Data sources and how
they were combined") is explicit: _"None of these arrive as raw/unannotated images… There is no
manual bounding-box drawing anywhere in this pipeline."_ The pseudo-labeling step that closes
nyanko's bystander-vehicle gap uses a COCO-pretrained `yolo26s.pt` at high confidence, with any
pseudo-box dropped wherever it would overlap an existing accident box — automated and
precision-favouring by design, not a research-team annotation effort. This is the same source
file that resolves §0.6; both errors trace back to the same drifted sentence in Phase 2 and should
be fixed together.

---

## Priority 2 — Architecture and schema drift

### 2.1 The ERD shows five tables; the schema has ten plus an FTS index

**Where:** Figure 7 and the Data Dictionary (Tables 9–13); repeated in the Level-1 DFD's four
data stores.

| Table               | In Figure 7? | Notes                                                 |
| ------------------- | ------------ | ----------------------------------------------------- |
| `user`              | yes          | see 2.5 / §1.10 for the auth claims                   |
| `camera`            | yes          | but see 2.2 — 9 of 20 columns                         |
| `detection_log`     | yes          | but see 2.3                                           |
| `sys_health_raw`    | yes          | —                                                     |
| `sys_health_hourly` | yes          | —                                                     |
| `audit_log`         | **no**       | FR-21 and NFR-21 depend on it entirely                |
| `auth_session`      | **no**       | server-side revocable sessions (§2.5)                 |
| `alarm_settings`    | **no**       | FR-08 / UC-11 depend on it                            |
| `export_job`        | **no**       | FR-19 async export jobs (§4.12)                       |
| `help_article`      | **no**       | FR-20 Help Center                                     |
| `help_article_fts`  | **no**       | FTS5 external-content virtual table + 3 sync triggers |

Verified by `grep -rn 'table=True' backend/app/models/` — ten declarations — plus the virtual
table created by an `after_create` listener at `backend/app/models/help.py:42-95`.

**Change to:** add the five missing tables to Figure 7 and their columns to the Data Dictionary;
add an **Audit Log data store (D5)** to the Level-1 DFD, which the Context DFD already implies
(§0.11).

**Why.** The paper argues the schema _"strictly adhered to 3NF"_ while omitting exactly the
tables that carry the audit trail and session state — the two subsystems its own security and
compliance requirements most depend on. An ERD that shows the happy-path tables and drops the
accountability tables reads as though those concerns were never designed for. The actual schema
does the opposite. Completing the diagram doesn't change what the system does; it makes the
diagram match a system that already does more than the diagram shows.

### 2.2 `camera` — Table 10 lists 9 columns; the model has 20

**Change to** the full definition (`backend/app/models/camera.py:73-104`), with the
desired/observed split called out:

> **Backend-owned (desired state, set by operator action):** `desired_ai_state`,
> `desired_state_reason`, `cooldown_until`, `config_version`.
> **AI-owned (observed state, reported on heartbeat):** `applied_config_version`,
> `last_heartbeat_at`, `measured_fps`, `inference_latency_ms`, `last_error_code`,
> `last_error_message`.

**Also fix the paper-internal naming conflict:** Figure 7 labels the column **`channel_no`**;
Table 10 correctly says **`channel_id`**, matching the code. Align the figure to the dictionary.

**Why.** The desired/observed split is the central design idea of the camera subsystem, not an
implementation detail — it is what lets an operator's pause and the AI's own self-blindfold
coexist without either silently overwriting the other, and what lets a heartbeat reconcile engine
state with backend intent after a restart (§2.4). Omitting it means the paper documents a camera
table that could not support the HITL guard behaviour it describes elsewhere.

**Worth documenting alongside:** `ux_camera_name_active`, a **unique expression index on
`lower(camera_name)`, partial `WHERE is_active = 1`** — the one index Alembic autogenerate cannot
express, hand-written in the migration
(`backend/alembic/versions/09e6d3163265_initial_production_schema.py:47-50`), and
`ux_camera_channel_active`, its counterpart on `channel_id`. Together they are what actually
enforces UC-4's duplicate-prevention rule.

### 2.3 `detection_log` — Table 11

**Change to:** add `source_event_id` (the idempotency key that makes AI-engine retries of the
same collision safe — a duplicate POST to `/api/internal/alert` returns 200 rather than creating
a second row), `snoozed_at` / `snoozed_until` / `snoozed_by_id` (described narratively in UC-5
step 4 but carried nowhere in the schema), and `created_at` / `updated_at`. Rename
`snapshot_path` → **`snapshot_key`** — the client never receives a filesystem path; the snapshot
is served through `GET /api/alerts/{log_id}/snapshot` and the stored value is an opaque key.

**Also document `ux_detection_open_camera`**, a partial unique index on `camera_id`
`WHERE detection_status IN ('Unverified','Ongoing')`, guaranteeing "at most one open incident per
camera" **at the database level** rather than in application logic
(`backend/app/models/detection.py:32-47`).

**Why.** `source_event_id` and the snooze columns are the schema-level evidence for two
requirements that would otherwise look unimplemented on paper despite being implemented in code.
The `snapshot_path` → `snapshot_key` correction matters because "path" implies a filesystem
detail leaking to the client, which is exactly what the endpoint-mediated access avoids. The
partial unique index is a genuine design contribution — enforcing a business invariant in the
database instead of trusting application code to check first — and currently appears nowhere.

### 2.4 The AI↔backend seam is bidirectional, and the DFD draws the wrong arrow

**Currently:** Figure 2 (Client-Server), Figure 6 (Level-1 DFD), and the AI Engine paragraph all
show a single arrow: AI Engine → internal HTTP webhook → Backend.

**Worse:** the Level-1 DFD has process **2.0 (Ingest Video and Execute AI Inference)**
_"**references the Camera Data Store (D2) for configuration metadata**"_. The AI engine holds no
camera configuration and never touches the database. It learns which cameras exist, and where to
reach them, from the heartbeat response.

**Change to** a second arrow and a rewritten paragraph:

> `POST /api/internal/alert` — idempotent detection ingest, keyed on `source_event_id`; a
> duplicate returns 200, a genuinely new event 201.
>
> `POST /api/internal/heartbeat` — the engine reports observed per-camera state, and the backend
> responds **in the same call** with the desired state: the camera list, constructed RTSP URLs,
> `desired_ai_state`, `cooldown_until`, `config_version`, and the heartbeat interval itself
> (fixed at 3 s).
>
> The engine holds no persistent camera configuration of its own — the backend pushes it down on
> every heartbeat. This is what lets the self-blindfold pause and the dismiss cooldown survive an
> engine restart: on reconnect, the first heartbeat response re-establishes whatever state the
> backend already committed.

**Why.** A single outbound arrow describes a fire-and-forget webhook, which is not what keeps
camera pause state consistent across a restart — if the engine held its own configuration, a
restart would silently resume ingestion on a camera the backend still considers paused. The
second arrow is the mechanism the paper's own self-blindfold and cooldown claims rely on.
Documenting it turns "the AI engine posts detections" into "the backend and AI engine maintain a
reconciled view of camera state across restarts", which is a considerably stronger reliability
claim and already true.

→ `backend/app/api/routes/internal.py:108-228`, `backend/app/schemas/internal.py`,
`ai_engine/supervisor.py:43-204`, `ai_engine/backend_client.py:40-95`

**This also fixes UC-4.** Steps 5–6 say the system _"executes a network handshake using the
constructed URL, verifies stream integrity, and starts an isolated AI inference worker process
for that feed"_ and, on removal, _"gracefully terminates the active AI worker process … drops the
network socket"_. Neither happens at request time: creating a camera writes a row, and the engine
picks it up on the next heartbeat (≤ 3 s). And **inference is batched across all cameras in one
process** — only _decode_ is a per-camera thread (`ai_engine/camera.py:61-62`) — so "an isolated
AI inference worker process for that feed" describes a pipeline that no longer exists. The same
wording appears in UC-4's postcondition.

### 2.5 Session authentication — NFR-19

**Currently:** _"secure, token-based authentication \[e.g., JSON Web Tokens(JWT)\]"_.

**Change to:**

> Authentication uses a JWT delivered as an `HttpOnly`, `Secure`, `SameSite=Strict` cookie
> (`adas_session`), never exposed to JavaScript, backed by a server-side `auth_session` row so
> individual sessions are revocable ahead of their natural expiry. Seven revocation reasons are
> tracked: `logout`, `password_change`, `password_reset`, `role_change`, `account_disabled`,
> `admin_revoke`, `expired_cleanup`. There is no bearer-token path anywhere in the API; the
> WebSocket handshake authenticates off the same cookie. Session lifetime is 480 minutes.

**Why.** "Token-based authentication \[e.g., JWT\]" is not wrong, but it describes the weaker and
more common pattern — a bearer token an attacker with XSS can read out of storage and replay.
This system doesn't do that: the token never touches JS-reachable storage, and because it's
backed by a database row rather than being purely self-contained, a compromised session can be
revoked server-side before its JWT expiry, which a stateless design cannot do at all.

→ `backend/app/core/config.py:31-33`, `backend/app/models/user.py:81-105`,
`backend/app/api/dependencies.py:48-115`, `backend/app/main.py:404-490` (WS handshake)

### 2.6 RBAC enforcement and the audit guarantee

**Currently:** _"The Backend … enforced RBAC through JWT validation."_

**Change to:**

> Authorization is enforced per-route via FastAPI dependencies and re-checked against the
> **current database role** on every request — the JWT's `role` claim is used only to initialise
> the frontend. Every state-changing action subject to audit runs as a single transaction
> together with its `audit_log` row: if the audit insert fails, the entire action rolls back, so
> an unaudited state change cannot persist. A `denied` or `failure` outcome is recorded in a
> separate short transaction after that rollback, so the attempt is never lost even when the
> action is rejected.

**And document the NFR-21 mechanism.** NFR-21 states audit records are append-only as a _policy_.
It is enforced physically: two SQLite triggers, `trg_audit_log_no_update` and
`trg_audit_log_no_delete`, raise `ABORT 'audit_log is append-only'`
(`backend/app/models/audit.py:91-116`). There is also a 26-action CHECK constraint generated from
the same tuple the API's query validation uses, so the two can never drift, and 15 banned detail
keys are redacted before any audit row is written (`backend/app/services/audit.py:16-48`).

**Why.** "RBAC through JWT validation" describes only authentication and gestures at
authorization without saying how it is enforced or recorded. The real guarantee is stronger and
testable: the system cannot reach a state where a privileged action happened but left no audit
trail, because the two are the same transaction.

---

## Priority 3 — Frontend, wireframes, and use cases

The UI has settled enough to audit against. This section was marked provisional in the
superseded file.

### 3.1 Four requirements where the backend is built and the frontend never calls it

These are the most significant findings in this section, because in each case the paper's
requirement is satisfied server-side and unreachable by an operator.

**FR-08 / UC-11 — Alarm Settings has no UI at all.** No route, no page, no modal, no sidebar
entry, and no service call. A grep across `frontend/src/services` for `settings` returns zero
matches. The backend has `GET`/`PUT /api/settings/alarm`
(`backend/app/api/routes/settings.py:27-80`) with defaults `alarm_sound="default"`, `volume=80`,
`snooze_duration=30`. UC-11's entire nine-step main flow describes a panel that does not exist.

Two further problems with UC-11 as written even if it were built: step 3's _"library of available
audio options"_ is a single option (`ALARM_SOUND_KEYS = ["default"]`, `config.py:77`), and
step 4's real-time preview has nothing to preview. Its **rules**, however, are all correct —
alt-7a/7b's 15 s and 60 s bounds match `SNOOZE_MIN_SECONDS`/`SNOOZE_MAX_SECONDS` and a DB CHECK,
and alt-8a's "no redundant record" matches the no-op-save behaviour at `settings.py:41-80`.

**FR-07 / UC-5 step 4 — the Snooze button does not exist.** The Zustand store handles snooze
state (`snoozedUntil`, `activateSnooze`, `isSnoozedNow` —
`frontend/src/store/useAlertStore.ts:38-58`) and the WebSocket bridge consumes `SNOOZE_ACTIVATED`
and `RE_ALARM` (`RealtimeAlertsBridge.tsx:86-95`), and the backend exposes
`POST /api/alerts/{log_id}/snooze`. But there is no control anywhere that triggers it — the
operator's UI only _reacts_ to a snooze initiated elsewhere. See also §0.10: Figure 11 doesn't
show the button either.

**FR-20 / UC-10 — the Help Center is hardcoded static content.** `pages/HelpCenter.tsx` has no
queries and no state: three quick-link cards and four procedure steps as literal arrays, plus a
hardcoded "within 15 minutes" SLA claim, and **three "View guide →" buttons with no `onClick`**.
Meanwhile the backend has role-filtered articles with FTS5 search and a `top_faqs` fallback that
implements UC-10's alt-4a behaviour exactly (`backend/app/api/routes/help.py:18-58`). None of it
is called. UC-10's steps 2–6 — role-aware navigation, search bar, filtered results, article view
— are all unimplemented, as is its postcondition about hiding administrative guides from
Operators.

**UC-3 — the Profile page is unreachable.** `/admin/profile` and `/user/profile` exist
(`App.tsx:61, 79`), but nothing in the UI links to them. The sidebar user chip is styled
clickable, with a chevron, and has **no `onClick`** (`Sidebar.tsx:139-152`). The page is
reachable only by typing the URL. Also note UC-3's actor list says **Operator** only; the page
serves both roles.

### 3.2 Wireframe mismatches, Figures 8–17

| Figure                | Paper says                                                                          | Actual                                                                                           |
| --------------------- | ----------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| 8 Login               | "system logo in the **upper-left corner**"                                          | centered 400 px card with the logo inside it (`Login.tsx:103-118`)                               |
| 9 Sidebar             | profile block with "an **ellipsis icon** for contextual account management actions" | a chevron (`RiArrowUpSLine`), **no handler**, no actions (`Sidebar.tsx:151`)                     |
| 10 Dashboard          | "a time-series **line graph** tracks 'Peak Accident **Times** (24H)'"               | an **AreaChart** titled "Peak Accident **Hours** (24H)" (`Dashboard.tsx:176-240`)                |
| 11 Alert modal        | "**horizontally divided**": snapshot left panel, telemetry right panel              | vertically stacked `max-w-md` card — banner, snapshot, metadata rows (`GlobalAlerts.tsx:85-174`) |
| 11 Alert modal        | "omits a standard window-close ('X') control"                                       | ✓ **correct** — no X, no backdrop close, no Escape listener                                      |
| 12 Cameras            | filters for "Network Connection" and "AI Detection Status"                          | **three** dropdowns; the third filters by enablement (`Cameras.tsx:153-207`)                     |
| 12 Cameras            | Actions column includes "the **active state toggle**"                               | the `Switch` is rendered **`disabled`** — a read-only indicator (`Cameras.tsx:253`)              |
| 12 Cameras            | pagination "uses **row-count selectors**"                                           | "Items per page" is a static `<span>`, not adjustable (`PaginationFooter.tsx:29-34`)             |
| 14 Edit Camera        | footer shows "Date Added" and "**Last Updated**"                                    | "Date Added" and "**Last Changes**" (`EditCameraModal.tsx:152-155`)                              |
| 15 Delete confirm     | destructive button "labeled '**Delete**'"                                           | labeled "**Continue**" (`ConfirmDeleteModal.tsx:51`)                                             |
| 16 Detections Ongoing | table contains "**only** accident records with an 'Ongoing' status"                 | shows `Unverified` **and** `Ongoing` (`Detections.tsx:48`)                                       |
| 17 Details modal      | "**bifurcated** layout", evidence left / metadata right                             | vertically stacked (`Detections.tsx:472-644`)                                                    |

Figures 11 and 17 share the same error — both describe a two-panel horizontal split; both are
vertically stacked cards. Either redraw the wireframes or rebuild the modals; they are currently
the two most-referenced figures in the HITL narrative.

Figure 11 also omits two things the modal actually has: the queue counter ("+N more alert(s)
queued") and the status-coloured header banner (red `ACCIDENT DETECTED` for Unverified, amber
`ONGOING ACCIDENT` for Ongoing).

### 3.3 Wireframe coverage is incomplete

The section opens: _"The wireframes below depict the interface layouts for **each major system
view**."_ It supplies ten. Missing entirely: **System Health, AI Performance, User Management,
Add User, Edit User, Reset Password, Delete User Confirmation, the Detections _Logs_ tab, the
Closed Accident Details modal, Help Center, and Profile Settings** — eleven views that exist in
the application and have use cases written for them. The superseded ITCAPROJ1 draft carried 19
wireframes covering most of these.

Either restore the missing figures or soften the opening sentence to say which views are
depicted and why.

### 3.4 Use-case ↔ UI mismatches

- **UC-2 alt-5a's "Primary Administrator Lockout" UI does not exist.** The use case describes the
  system disabling the delete button, locking the Role radio buttons, and showing a tooltip
  reading "Cannot modify or delete the final active Administrator". A grep across
  `frontend/src/` for any last-admin guard returns **nothing**. The backend does enforce the rule
  (`routes/users.py:255, 433`), so the action fails — but the operator discovers this from an
  error after submitting, not from a disabled control.
- **UC-1 alt-3b** says a deactivated account gets a distinct _"security message"_. In fact
  unknown username, wrong password, and inactive account all return a byte-identical 401
  `AUTH_INVALID_CREDENTIALS` (`routes/auth.py:75-93`), deliberately, to prevent enumeration. The
  implementation is the better posture — correct the use case toward it.
- **UC-1 has no rate-limiting flow.** Ten failed attempts in 300 s, keyed independently by IP and
  by username, returns 429 with `Retry-After` (§4.12). Worth an alternative flow.
- **UC-4 step 4** says uniqueness is checked on the _constructed RTSP URL_. It is enforced on
  `channel_id` and `lower(camera_name)` by two partial unique indexes (§2.2).
- **UC-4 alt-5a** implies a single failed handshake flags `Unresponsive`. It takes three
  consecutive failures (`UNRESPONSIVE_AFTER_FAILURES = 3`, `ai_engine/config.py:38`). The
  10-second reconnect interval is ✓ correct.
- **UC-5 step 5** — _"reviews the snapshot **and/or live feed**"_. There is no live video anywhere
  in the application: no `<video>` element, no HLS/WebRTC/MJPEG player, no stream URL field. The
  only imagery is the still snapshot.
- **UC-5 step 3** — _"triggers an audible alarm **at the user's configured sound and volume
  level**"_. The alarm is a fixed looping asset (`utils/detectionSound.ts:4-7`); no configuration
  reaches it (§3.1).
- **UC-6 step 3** — telemetry push cadence; see §1.11 and §4.4.
- **UC-7 step 4 and the Use Case Diagram narrative** put **inference latency and FPS** on the AI
  Performance page. Both live on System Health. The AI Performance page shows Total Accidents,
  Total Dismissed, Avg Precision, Avg Confidence, Avg Dismissed Score
  (`AiPerformance.tsx:94-129`).
- **UC-7 step 5** conflates the AI-Performance CSV export with the separate, Admin-only
  `POST /api/exports/retraining`, which always produces a **zip** and always runs asynchronously.
- **UC-8 step 3** names the first KPI **"Pending"**; the UI card is **"Ongoing Accidents"**.
- **UC-9 step 3** offers filters by **Status** and by **Operator**. In the Logs tab, status is a
  static decorative chip reading "Dismissed & Resolved" — not interactive — and the operator
  select is rendered **only for Administrators** (`Detections.tsx:298-321`).
- **UAT step 3** claims evaluators reviewed **RTSP network latency** and **CPU thermal** metrics.
  Neither exists on the System Health page: its four tiles are Server Uptime, Inference Latency,
  Processing Speed, Disk Storage Usage, and its four charts are CPU utilisation, GPU utilisation,
  GPU temperature, and RAM utilisation. `cpu_temp` is a nullable column documented as "null on
  Windows" (`backend/app/models/health.py:16`).

### 3.5 Two places the paper undersells what was built

- **NFR-10 promises three clicks; the alarm modal takes one.** `handleConfirm` / `handleDismiss` /
  `handleResolve` each POST directly with no secondary confirmation, no reason field, no notes
  box (`GlobalAlerts.tsx:32-72`). State the real figure.
- **UC-6 alt-4a's thresholds are exactly right** — "Core Temp > 85 °C, or RAM > 95%" matches
  `GPU_TEMP_CRITICAL_C = 85` and `RAM_CRITICAL_PCT = 95` (`config.py:88-89`). Keep and cite it;
  it is one of the few numeric claims in the paper that lands precisely.

### 3.6 Dead controls and placeholder text to clean up before the demo

Not paper edits, but each is visible to a panel driving the UI:

| Item                                                                                                                        | Location                          |
| --------------------------------------------------------------------------------------------------------------------------- | --------------------------------- |
| "Compared to last month" on two KPI tiles — **no delta is ever computed**; `StatCard` supports `delta` props no page passes | `Dashboard.tsx:348, 356`          |
| Three "View guide →" buttons with no handler                                                                                | `HelpCenter.tsx:72-74`            |
| Sidebar user chip styled clickable, no handler — the only plausible route to Profile                                        | `Sidebar.tsx:139-152`             |
| Camera enable `Switch` rendered `disabled`                                                                                  | `Cameras.tsx:253`                 |
| "Items per page" rendered as a control but static                                                                           | `PaginationFooter.tsx:29-34`      |
| Static filter chips styled identically to the real dropdowns beside them                                                    | `Detections.tsx:298-301, 350-359` |
| Profile subtitle says "and preferences"; there are none                                                                     | `ProfileSettings.tsx:154`         |
| Hardcoded "Critical system issues: within 15 minutes" SLA                                                                   | `HelpCenter.tsx:57`               |

---

## Priority 4 — Capacity, cadence, and descriptive corrections

### 4.1 Capacity and latency figures — and a live discrepancy

**The superseded audit's numbers are stale.** It quoted 17.5 ms at batch = 1 and 124 ms at
batch = 16. `ai_engine/machine_profile.json` records **16.49 ms** and **114.12 ms**.

**More importantly, the artifact and the prose docs disagree on capacity.** Every document says
**12 cameras at 10 FPS** (`port-handover.md:27`, `eval/README.md:40, 83`,
`calibration-capacity-design.md:24`). The committed profile says **13** — and 13 is
arithmetically correct against its own latency table (batch 13 = 92.06 ms ≤ 100 ms; batch 14 =
100.75 ms exceeds it). The profile is evidently a later re-run than the prose.

**Before quoting either figure, resolve it** — re-run `uv run python ai_engine/capacity.py`, or
cite the profile and note the docs are behind.

**Also state the caveat:** `verification` in the profile is permanently `"unverified"` because
the build-and-verify steps are unimplemented (`ai_engine/eval/README.md:93-106`). Every capacity
figure is therefore a **floor**, not a ceiling — which is the conservative direction, and worth
saying so.

**Deployment hardware** (Hosting Environment) should be reframed per §1.0 C, with the measured
prototype numbers supplying the basis for the 418-camera extrapolation:

> The target production specification is a Dell PowerEdge R760xa with 8× NVIDIA L4 GPUs, sized
> to carry 418 cameras city-wide. This specification was not deployed during the capstone; the
> system was developed and measured on a single prototype GPU (NVIDIA GTX 1650). On that
> prototype, capacity benchmarking recorded 8 cameras sustainable at 15 FPS and 13 at 10 FPS,
> with per-batch inference latency scaling from 16.5 ms at batch = 1 to 114.1 ms at batch = 16.
> Scaling this measured per-GPU capacity across the L4 fleet is the basis for the 418-camera
> production target.

### 4.2 The pilot phase is sized above measured capacity

Phase 1 of the Phased Implementation Strategy activates _"only 10 to 15 known high-risk
intersections"_. Measured sustainable capacity on the prototype is **8 cameras at 15 FPS**. Tie
the pilot size to the measurement, or state which hardware the pilot assumes.

Related: **the 418-camera figure depends on multi-GPU scheduling that does not exist**
(`ai_engine/docs/2026-08-10-detection-core-port-design.md:187`). The current pipeline drives one
model on one device. So 418 is a design target twice over — unbuilt scheduling on unpurchased
hardware. Worth one honest sentence.

### 4.3 NFR-06 conflicts with the export architecture

**Currently:** _"The system shall generate and initiate the download of requested analytical
reports and historical log exports **within 5 seconds** for datasets covering up to 30 days."_

**Change to** something that describes both paths. Small exports are synchronous; large ones are
a job queue: `POST /api/exports/jobs` returns **202** with a `job_id`, the client polls
`GET /api/exports/jobs/{id}`, then downloads. Synchronous exports are hard-capped and return
**413 `PAYLOAD_TOO_LARGE`** naming the async endpoint above **10,000 rows (PDF)** or **50,000
rows (CSV)** (`backend/app/services/reports/common.py:19-42`). Artifacts expire after 72 hours.

UC-7 alt-6a and UC-8 alt-6a's _"displays a visual spinner and processes the export
asynchronously"_ undersells this considerably — it is a real job queue with crash recovery
(§4.12).

### 4.4 NFR-05 — the live push cadence is 5 s, not 10–15 s

**Currently:** _"the backend shall transmit real-time hardware and AI inference metrics to the
System Health dashboard **every 10 to 15 seconds** using in-memory data."_

**Change to:** sampling into memory happens every **5 seconds** (`HEALTH_SAMPLE_SECONDS`,
`config.py:84`; job registered at `main.py:179-185`), and the dashboard polls it over REST rather
than receiving a push (§1.11).

**The rest of NFR-05 is already correct** and needs no change: raw samples persisted every 300 s,
pruned after 48 h, rolled up hourly, retained 30 days — all four scheduled jobs exist and match
(`main.py:186-213`).

### 4.5 The 10–15 FPS band is a thermal constraint, not a detection requirement

The thermal justification in Scalability and Performance Considerations is **correct and needs no
change**. **Add**, near it or in Limitations:

> Detection performance was measured across sampling rates from 3 to 30 frames per second on the
> full clip set. Event-level recall was unchanged (8 of 16 at every rate but one) and false-alarm
> counts varied between 2 and 5 with no relationship to rate. The 10–15 FPS operating band is
> therefore a compute and thermal constraint, not a detection requirement: the accumulator
> integrates evidence over elapsed time rather than counting frames, so sampling less often does
> not slow evidence accumulation.

Source: `ai_engine/docs/cadence-measurement.md:26-53`, raw data at `eval/cadence_sweep.json`.

**Do not overclaim it.** 16 crashes and 2–5 false positives per run is a small sample; the honest
statement is "no measured effect", not "no effect". Nothing below 3 FPS was tested, and the
sweep's own caveat notes that the requested 15 and 12 FPS both resolve to stride 2 — so **four
distinct rates were tested, not five**.

**And do not cite `measured_fps` as evidence for this band.** It is the **decode** rate, observed
at 16–31 FPS live, with no relationship to inference cadence
(`ai_engine/docs/port-handover.md:116`). Roughly half of every decoded frame is discarded. It is
the most citable-looking number in the system that does not mean what the paper needs it to mean.

### 4.6 MediaMTX, and "standard RGB video feeds"

The Testing Strategy Overview describes MediaMTX correctly ✓. But Ch. 1 Scope and Ch. 3 Research
Design both say the system processes _"standard RGB video feeds obtained via a **MediaMTX RTSP
proxy**"_ — which makes the test harness sound like the deployment architecture, and sits oddly
beside the Definition of Terms entry naming **Dahua DSS Pro** as the media gateway. Clarify:
MediaMTX simulates the VMS in the test environment; DSS Pro is the production gateway.

**"RGB" is also worth a word** — see §4.7; frames are converted to grayscale before inference.

### 4.7 Grayscale inference normalisation — currently undocumented

**Add** to the AI Engine description and the training discussion:

> All frames are converted to grayscale and replicated to three channels before inference,
> matching the training pipeline. The accident source is 100% grayscale and the vehicle source
> ~98% colour, so without this normalisation the cheapest rule available to the model is
> "colour ⇒ vehicle, grayscale ⇒ accident" — which on colour deployment footage means it never
> fires.

**Why.** This is the single most consequential preprocessing decision in the system and it is
undocumented. It is also a good defence answer: it shows a shortcut was anticipated and
eliminated before it could reach deployment footage. → `ai_engine/detector.py:23-33`,
`adas_transfer/SPEC.md:257-262`

### 4.8 The two-class design and the discarded foil

**Add** to the model description:

> The model is trained on two classes, `accident` and `vehicle`, but only `accident` is alerted
> on (`ACCIDENT_CLASS_ID = 0`; class 1 is discarded at inference). The `vehicle` class is a
> discriminative foil. Under single-class training an ordinary car is background, and since
> nearly every accident image is a crash scene full of vehicles, the two concepts entangle and
> the model degenerates into a vehicle detector — which measurably happened to an earlier model
> that reported 0.986 mAP50 and then fired 0.89 confidence on a normally-driving red sedan.

**Why.** The paper currently describes a YOLO model detecting collisions without explaining the
class structure behind it. The foil is the core design insight and reads well as a research
contribution — the difference between "we trained a detector" and "we identified and corrected a
specific, measured failure mode of a naive single-class detector."
→ `ai_engine/config.py:48`, `SPEC.md:20-37`

### 4.9 `DETECTOR_CONF = 0.15` is a closed lever, not a tuning knob

**Add** alongside §4.8:

> The detector confidence threshold is fixed at 0.15, deliberately low. Measured false positives
> score _higher_ than measured genuine detections, so any confidence threshold high enough to
> remove the false alarms removes the real crashes first. Precision in this system comes from the
> temporal accumulator — evidence persisting across frames — not from the per-frame confidence
> gate.

**Cite the figures carefully** (see §1.9): the adopted model's three false positives measured
**0.869 / 0.844 / 0.649**; the genuine-detection figures **0.536 / 0.459 / 0.741** come from the
**previous** model (`SPEC.md:269-272`). Either present both sets with their provenance, or
present the qualitative finding without numbers.

**Why this matters beyond the model section.** It is also what makes the confidence-gating test
cases describe behaviour the system cannot exhibit — see [Deferred](#deferred--test-case-chapter).

**Ready-to-paste location, checked against the live Doc's `__main__` tab (2026-08-14).** The
accumulator is currently undocumented everywhere in the paper — the closest existing text is
"The AI Engine" component paragraph under System Architecture and Design → Client-Server
Architecture Diagram, which currently reads:

> "The AI Engine. This component used OpenCV to ingest and decode RTSP streams. The decoded
> frames were processed by the Ultralytics YOLO framework for real-time inference. Upon collision
> detection, the module captured a bounding-box snapshot and sent a secure internal HTTP
> (Hypertext Transfer Protocol) webhook to the backend to register the event."

"Upon collision detection... captured a snapshot" reads as a single-frame fire, which is exactly
the claim §4.9/§4.10 correct. Replace the paragraph wholesale — this single location covers both
items, so §4.10 doesn't need a separate site:

> **The AI Engine.** This component used OpenCV to ingest and decode RTSP streams. The decoded
> frames were processed by the Ultralytics YOLO framework for real-time inference, using a
> deliberately low, fixed confidence threshold — measured false positives scored _higher_ than
> measured genuine detections, so raising the threshold to suppress false alarms would remove
> real crashes first. Rather than alerting on any single frame, the engine's temporal accumulator
> persists evidence across frames, linking detections in the same region over time and firing an
> event only once that accumulated evidence crosses a threshold; this is also what gives the
> system its deliberate ~3-second latency floor after impact, since evidence must persist before
> an alert can fire. Once an event fires, the module captured a bounding-box snapshot and sent a
> secure internal HTTP (Hypertext Transfer Protocol) webhook to the backend to register the event.

This keeps the paragraph's original length and register (matching the Data Source/Backend/
Database/Frontend component paragraphs around it) while folding in §4.9's threshold finding and
§4.10's latency-floor framing in the one place a reader first learns what the AI Engine does. The
two-class/vehicle-foil design (§4.8) is deliberately left out of this paragraph — it's a training-
data decision, not a runtime-pipeline one, and fits better as an addition to Model Architecture
Selection in the Training Protocol section instead.

### 4.10 Alert latency is a designed floor, not a shortfall

**Add** wherever detection latency is discussed. §4.9 now has the primary ready-to-paste site (the
AI Engine paragraph, above) — this item's content is folded into that same replacement text, so no
separate location is needed unless latency is discussed again elsewhere in the paper.

> Alerts land a median 3.02 seconds after impact. This is a deliberate consequence of requiring
> evidence to persist before firing, and is what buys the system's precision. It is a floor, not
> a defect.

**Note two coexisting figures**: SPEC records a **+3.02 s median** across the corpus
(`SPEC.md:336`); the calibration design doc says **~2.3 s** dominated by the accumulator
(`calibration-capacity-design.md:270`), matching the parity clip's `age_s = 2.31`. They measure
different things. State which one you are quoting — the AI Engine paragraph above uses the
rounder "~3-second" framing deliberately to avoid committing to one figure over the other; cite a
specific number only where the paper needs the precision.

### 4.11 State the operator-facing false-alarm rate

**Add** to Significance or Limitations:

> At 0.27 false alarms per minute per camera, an operator monitoring a single camera can expect
> roughly 16 false alerts per hour. The system is a triage aid that keeps a human in the loop,
> not an autonomous dispatcher.

**Why.** This number is a design input for the HITL workflow — the paper's own click-efficiency
criterion (NFR-10) exists because of it. Stating it makes those requirements look derived rather
than arbitrary, and it is far better volunteered than extracted under questioning.
→ `adas_transfer/README.md:79-84`

### 4.12 Undocumented subsystems

Each exists, is load-bearing, and appears nowhere in the paper. These need **adding**, not
correcting.

- **Durable outbox** — `ai_engine/outbox.py`. One JSON file per pending event, written `.tmp`
  then `os.replace` so a crash mid-write cannot corrupt the queue, with a `quarantine/`
  subdirectory for events that fail to parse back, exponential backoff capped at 300 s, and a
  synchronous startup drain before the inference loop begins. If the backend is unreachable when
  a collision fires, the event survives on disk and is retried. This directly supports the
  paper's reliability narrative and currently goes unclaimed.
- **Audit-log subsystem** — the `audit_log` table (§2.1), the transaction helpers in
  `backend/app/services/audit.py`, `GET /api/audit-logs/` and `/export`. FR-21 and NFR-21 describe
  the _requirement_; nothing describes the mechanism. Note the export carries a watermark
  (`audit_id <= max_existing_id`) so the `AUDIT_EXPORT` row can never appear in its own export.
- **Async export jobs** — the `export_job` table and a four-endpoint lifecycle, plus a dedicated
  `POST /api/exports/retraining` for the off-site retraining dataset FR-19 and the Maintenance
  Plan both describe in prose without knowing it exists. Jobs left `queued`/`processing` by a
  crash are re-enqueued at boot (`backend/app/main.py:249-259`).
- **Login rate limiting** — a sliding window (`backend/app/core/rate_limit.py`), **10 failed
  attempts per 300 seconds**, keyed independently by source IP _and_ by lowercased username, with
  only failures counting and a success resetting both. Every rejection writes a `LOGIN_FAILURE` /
  `denied` audit row. No NFR covers this; there probably should be one.
- **Backup / restore** — the "Flag and Restart" description is broadly right in outline, but says
  "Linux systemd pre-start script" where the code's own comment
  (`backend/app/maintenance/restore.py:6`) says the restore is called by an external orchestrator
  "(PowerShell/systemd) **only**" — both platforms. The paper also omits rollback, post-restore
  health finalisation, and the audit record of the outcome, all of which are implemented.
  Retention is 30 daily / 10 manual. The restore route is triple-gated: re-submitted admin
  password, exact confirmation string, and a validated backup id — and it writes only a flag
  file, never touching `adas.db`.
- **Three health routers by design** — `routes/system.py` (unauthenticated `/healthz/*`, for load
  balancers that cannot hold a session cookie), `routes/system_health.py` (authenticated
  telemetry), `routes/maintenance.py` (backup/restore). Worth one sentence that the split is
  deliberate.
- **`GET /api/events/schema`** — a published WebSocket event-schema endpoint, letting a client
  discover `/ws/alerts` payload shapes without reading backend source.
- **WebSocket connection limits** — 50 total, 5 per user, with a bounded per-connection send
  queue. A new connection over the limit is rejected rather than displacing an established
  dashboard (`main.py:445`) — a deliberate choice worth stating.
- **FTS5 help search** — `help_article_fts`, an external-content virtual table with three sync
  triggers, guarded so that SQLite builds without FTS5 fall back to LIKE rather than failing.

---

## Corrections to the superseded audit

Four errors in the 2026-08-12 file, fixed rather than propagated:

1. **Confidence provenance.** `SPEC.md:269-272` attributes 0.536 / 0.459 / 0.741 (genuine) and
   0.887 / 0.900 / 0.856 (false positives) to the **previous** model; the adopted model's three
   false positives are 0.869 / 0.844 / 0.649. The old §4.6/§4.7 presented the first set as the
   adopted model's true positives. Corrected in §1.9 and §4.9.
2. **Batch-latency and capacity figures.** 17.5 ms / 124 ms / 12 cameras were quoted; the
   artifact records 16.49 ms / 114.12 ms / 13 cameras. Corrected in §4.1.
3. **`ai_engine/supervisor.py` is not where the tick loop lives.** Scheduling and batched
   inference are in `ai_engine/pipeline.py`; `supervisor.py` owns heartbeat reconciliation. The
   old §1.4 pointed at the wrong file.
4. **`docs/results.md` is not in this repository.** It is cited by `accumulate.py:121` and
   `SPEC.md:508` but lives in the research repo, so the four-model comparison it backs cannot be
   verified here. Don't cite it.

The old audit also listed **10 tables**; the correct count is 10 SQLModel tables **plus** the
`help_article_fts` virtual table and its triggers (§2.1).

---

## Deferred — test-case chapter

The test-case chapter (Tables 15–35, 81 cases) gets its own overhaul once the system is final.
These items are **parked, not dropped**, and should not need re-discovering.

### TC-U-302 — Confidence thresholding

**Currently:** mock YOLO outputs `[0.45, 0.88, 0.60]` against a threshold of 0.75; expected that
the filter returns only 0.88.

**For the rewrite:** a test of _class filtering and accumulator hand-off_, not confidence gating —

> A mock YOLO output containing both `accident` (class 0) and `vehicle` (class 1) boxes is passed
> to the filter. Expected: all class-1 boxes are discarded, and every class-0 box above the 0.15
> detector confidence is forwarded to the accumulator regardless of its individual score.

Reasoning: under `conf = 0.15` all three mock values pass through, and the old expectation is
backwards — a 0.75 gate removes real crashes before it removes any false alarm (§4.9).

### TC-AI-301 — Sub-threshold false-positive suppression

**Currently:** a near-miss yielding 60% confidence, expected to be intercepted by a 75% threshold.

**For the rewrite:** a persistence test —

> A near-miss produces intermittent `accident` detections that do not persist in one location.
> Expected: accumulated evidence decays below the firing threshold and no alert is emitted.

Reasoning: 60% is inside the range where genuine detections live; the mechanism that actually
suppresses near-misses is temporal, not a confidence cutoff.

### TC-AI-103 — Sustained tracking / flicker

**Currently:** expects bounding boxes across a 10-second sequence "without the detection
'flickering' or dropping".

**For the rewrite:** a test of the accumulator's tolerance for gaps —

> Across a 10-second sequence of a stationary wreck, the accumulator maintains a single linked
> region and fires exactly one event, despite intermittent frames in which the detector produces
> no box.

Reasoning: the detector _does_ flicker and the design assumes it will. A postmortem clip held 302
candidate frames and 12.35 s of dwell that never assembled an unbroken run under the old logic,
and emitted nothing. The accumulator replaced that logic precisely so a dropped frame costs
progress rather than erasing it.

### TC-AI-202 / 203 / 204 — Environmental robustness

**Currently:** expected true-positive detection under heavy rain (202), correct rejection of
headlight glare (203), and successful detection with 30% occlusion (204).

**For the rewrite:** remove, or restate as untested limitations. None of the 17 evaluation clips
cover rain, glare, or partial occlusion. TC-AI-204 is the most exposed: a fully-occluded clip was
deliberately excluded from the label set on the grounds that no camera-based system could detect
it, which makes a 30%-occlusion success claim hard to defend.

Night is the exception and worth keeping — 8 of 17 clips are night footage and night recall
exceeds day recall. Night is a _precision_ weakness only: all three false positives are
night-time.

**Note this interacts with Ch. 2.** The "Challenges and Strategies" subsection builds an extended
case about weather, glare, and occlusion. If these test cases go, that subsection should
acknowledge the evaluation did not cover them.

### TC-R-302 — Fault isolation

**Currently:** an exception injected into "Camera 1's YOLO worker thread"; expected that thread
crashes safely while Cameras 2 and 3 continue.

**For the rewrite:** the same guarantee against the batched pipeline —

> A deliberate exception is injected into the inference step for Camera 1's frame. Expected: the
> engine isolates the failure to Camera 1, marks that camera as errored in its heartbeat report,
> and continues processing Cameras 2 and 3 in subsequent cycles. The FastAPI application is
> unaffected.

Reasoning: inference is batched through a single call, so "per-camera worker thread" no longer
describes the pipeline. The isolation guarantee is preserved — a failing batch is re-run frame by
frame to identify the culprit, which is then excluded (`ai_engine/pipeline.py:151-164`) — but the
mechanism differs. Decode-side isolation is unchanged and matches the original wording: each
camera has its own reader thread.

### TC-R-201 — UI alert latency

**Currently:** _"A stopwatch is initiated at the moment of detection… in strictly under 2.0
seconds."_

**For the rewrite:** _"A stopwatch is initiated at the moment the alert is **emitted by the AI
engine**…"_ This test measures backend → WebSocket → UI plumbing. Anchoring it to impact folds
~3 seconds of accumulation into a 2-second budget, failing a path that is genuinely fast. A
clarification of what the test always measured, not a relaxation.

### TC-S-103 — Operator response time

**Currently:** _"…click 'Confirm' in strictly under 15 seconds from the moment of actual
detection."_

**For the rewrite:** _"…from the moment of **collision**."_ This is the metric supporting the
study's central claim of reducing the notification gap from minutes to seconds, so it should
honestly include the detector's own latency. After the port, `detected_at` in the database **is**
the estimated collision time (`ai_engine/accident.py:52`), so this becomes directly measurable as
`verified_at − detected_at`.

**Budget check before committing to 15 s:** ~3 s accumulating + < 2 s plumbing leaves ~10 s of
operator time. Achievable, but tighter than the original wording implies — confirm during live
testing.

---

## Verified correct — no change needed

Re-confirmed against the live document and current code:

- **Table 14** (database engine comparison) and the SQLite / WAL / 3NF rationale — accurate as
  written, including the PRAGMA-per-connection detail.
- **NFR-08's indexing claim** — indexes on detection status, camera identifier, and timestamp all
  exist (`ix_detection_status_time`, `ix_detection_camera_time`).
- **Snooze bounds 15–60 s** (UC-11 alt-7a/7b) — `SNOOZE_MIN_SECONDS` / `SNOOZE_MAX_SECONDS` and a
  DB CHECK constraint agree.
- **Dismiss cooldown of one minute** (FR-11, Cooldown Timer definition) —
  `DISMISS_COOLDOWN_SECONDS = 60`.
- **10-second reconnect interval** (NFR-14) — `RECONNECT_INTERVAL_SECONDS = 10`.
- **NFR-05's persistence and retention** — 5-minute raw persistence, 48-hour prune, hourly
  rollup, 30-day retention; all four jobs exist. (Only the push cadence needed correcting, §4.4.)
- **UC-6 alt-4a's 85 °C / 95% thresholds** — exact match.
- **UC-9's table columns** — Accident No., Timestamp, Camera Name, Status, Last Handled By, Last
  Updated: all six present, in that order.
- **UC-11 alt-8a** — a no-op save writes no audit row.
- **Figure 11's omission of an 'X' control** — correct and deliberate; the alarm modal is the one
  modal with no close affordance at all.
- **The HITL state machine** `Unverified → Ongoing → Resolved` / `→ Dismissed`, and the
  self-blindfold pause ordering — matches the code and the CHECK constraints. Exactly four legal
  transitions, each a conditional UPDATE.
- **FR-19's CSV _and_ PDF export** — both real; `fpdf2` is present with fonts bundled.
- **MediaMTX as the VMS simulator** in Testing Strategy Overview.
- **The named Lipa deployment points** (Crossing-Banaybanay, Air Base Intersection, Lipa Town
  Center-Tambo, Petron Banaybanay, Unitop Star Tollway) — 14 of the 17 evaluation clips confirm a
  Lipa location from the burned-in caption strip. Note `jeep-motor` and `car-uturn-motor` share
  one camera, so the corpus covers **at most 16 distinct viewpoints**.
- **The `Admin` → `Administrator` naming difference is not a defect** — an explicit display
  mapping (`frontend/src/utils/auth.ts:4-5`). Table 9's "Admin or Operator" is correct for the
  stored value.
- **Ch. 2's literature review** — the YOLO-family argument supports the actual choice
  (YOLO26-nano), and the ~87 °C thermal-throttling figure is consistent with
  `GPU_TEMP_CRITICAL_C = 85`.

---

## Appendix — reference map

Doc heading anchors, for building deep links of the form
`https://docs.google.com/document/d/1MkTrdBPrrXpw8JGC4xrS475wbF7Yn-9YCaXIN-xd0aw/edit#heading=<anchor>`:

| Section                                                     | Page | Anchor           |
| ----------------------------------------------------------- | ---- | ---------------- |
| Objectives of the Study                                     | 13   | `h.i915dp9uqgc7` |
| Scope and Delimitations                                     | 14   | `h.vzemw0fx8zr5` |
| Significance of the Study                                   | 15   | `h.8lhmxmy8gz1i` |
| Definition of Terms                                         | 16   | `h.9xlknafqio6m` |
| Performance Metrics and Hardware Trade-offs                 | 29   | `h.jdktvzpl3tjg` |
| Challenges and Strategies of Computer Vision Implementation | 31   | `h.qx4xthgc2jsl` |
| Synthesis (Ch. 2)                                           | 40   | `h.sugutvwn4jqt` |
| Research Design                                             | 42   | `h.345pfe8wzom4` |
| Project Scope and Boundaries                                | 44   | `h.x0xow8ub05ki` |
| Phase 1: Planning and Requirements Analysis                 | 50   | `h.g6dt4vpi542h` |
| Phase 2: Design and Data Preparation                        | 51   | `h.edt9lk7ux2qz` |
| Phase 3: Development and Model Engineering                  | 52   | `h.40bsxc9dfhle` |
| Phase 4: Testing and System Integration                     | 52   | `h.3zo4depjufvz` |
| Phase 5: Deployment and Implementation                      | 53   | `h.1s44qz7mi3dp` |
| Timelines and Milestones (Table 1)                          | 53   | `h.sowbpxa60z20` |
| Functional Requirements Specification (Table 2)             | 55   | `h.sactxtj4km6d` |
| Non-Functional Requirements Specification (Tables 3–8)      | 59   | `h.zy1hxw64o5r`  |
| Use Cases (UC-1 – UC-11)                                    | 63   | `h.719njq1gvqvc` |
| Client-Server Architecture Diagram (Figure 2)               | 82   | `h.z6jixeegunxa` |
| Swimlane Diagram (Figure 3)                                 | 84   | `h.hbly8te2zj2v` |
| Use Case Diagram (Figure 4)                                 | 86   | `h.hcgrz374khyh` |
| Data Flow Diagram (Figures 5–6)                             | 90   | `h.yoa0wlh9x05m` |
| Entity Relationship Diagram (Figure 7)                      | 94   | `h.u1hk5hkitslf` |
| Data Dictionary (Tables 9–13)                               | 96   | `h.pqu45sbuxex5` |
| Wireframes (Figures 8–17)                                   | 101  | `h.x1og53kui9j0` |
| Deployment Architecture (Figures 18–19)                     | 116  | `h.1rovgmi9hjo8` |
| Frameworks and Libraries                                    | 123  | `h.9b01jk78qnkg` |
| Database Technologies (Table 14)                            | 125  | `h.q84u7u7dijyw` |
| Deep Learning Implementation and Training Protocol          | 128  | `h.89tgw19olp4j` |
| Testing Strategy Overview                                   | 130  | `h.9oue7q9hssbz` |
| Types of Testing Conducted                                  | 131  | `h.maht674oj24f` |
| Test Cases (Tables 15–35)                                   | 133  | `h.4q09ijmnt34f` |
| User Acceptance Testing                                     | 155  | `h.s7x79joubd5q` |
| Deployment and Implementation                               | 158  | `h.n0isf6mgn7r0` |

**Numbering, for cross-checking:** Tables 1–35, Figures 1–19. Requirements: FR-01 – FR-21
(**no FR-10**, §0.2); NFR-01 – NFR-22; UC-1 – UC-11.
