---
section: Project Development Model and Deployment Architecture
page/s: "unconfirmed rendered pages; TOC pp. 54 and 129"
required_revision: Replace completed CDRRMO installation, integration, and rollout claims with a clearly labelled target-production design.
notes: The completed proof of concept was evaluated on researcher-controlled hardware. No live CDRRMO deployment, citywide rollout, or staff handover is claimed.
status: Not started
assigned_to: Enjey
synced: 2026-08-27
---

## Changes

### 1. Defense paper — Chapter 3, Project Development Model, Phase 5: Deployment and Implementation

Page/s: unconfirmed rendered page (TOC: 54).

#### OLD

> The parallel development tracks formally unify as the finalized software architecture is deployed to the physical edge-inference server. The hardware is permanently installed within the Lipa CDRRMO command center and integrated securely into the agency's existing CCTV VLAN. Operating as a headless client, the system is configured to passively ingest video substreams directly from the proprietary Dahua VMS. The implementation executes a phased rollout strategy, beginning with a pilot deployment at high-risk intersections to monitor real-world hardware telemetry before incrementally scaling to integrate the entirety of the agency's 418-camera network. The lifecycle concludes with the formal handover of the system, which includes comprehensive operational training for dispatchers, security management training for administrators, and the establishment of long-term AI retraining and hardware maintenance protocols.

#### NEW

The parallel development tracks formally unified in a target production deployment plan. The completed proof of concept was evaluated on researcher-controlled hardware; it was not installed in the Lipa CDRRMO command center or connected to the agency's CCTV VLAN. If CDRRMO later adopts the system, it could operate as a headless client that passively ingests authorized video substreams from the Dahua VMS. Pilot activation, scaling beyond the demonstration environment, formal handover, staff training, AI retraining, and hardware maintenance would require separate CDRRMO authorization and post-capstone implementation.

#### Evidence

The live paragraph was re-read on 2026-08-27 at native range `t.y7ms6bhlk4qn:88762–89687`. The defense paper's Scope and Delimitations identifies the project as a proof of concept on researcher-controlled hardware and explicitly excludes production-scale deployment.

#### Proposed comment (same gate as associated replacement)

Previous: The parallel development tracks formally unify as the finalized software architecture is deployed to the physical edge-inference server. The hardware is permanently installed within the Lipa CDRRMO command center and integrated securely into the agency's existing CCTV VLAN. Operating as a headless client, the system is configured to passively ingest video substreams directly from the proprietary Dahua VMS. The implementation executes a phased rollout strategy, beginning with a pilot deployment at high-risk intersections to monitor real-world hardware telemetry before incrementally scaling to integrate the entirety of the agency's 418-camera network. The lifecycle concludes with the formal handover of the system, which includes comprehensive operational training for dispatchers, security management training for administrators, and the establishment of long-term AI retraining and hardware maintenance protocols.

Codex ID: PS-20260827-CDRRMO-DEPLOYMENT-OVERCLAIM

Done by Codex.

### 2. Defense paper — Chapter 3, Deployment Architecture, Figure 18 narrative

Page/s: unconfirmed rendered page (TOC: 129).

#### OLD

> Cross-VLAN communication is executed via a Router-on-a-Stick topology. The core router utilizes trunking encapsulation and virtual sub-interfaces to securely route traffic between these isolated networks. This configuration enables the edge server (VLAN 50) to securely transmit real-time WebSocket alerts and REST API payloads to the operator terminals (VLAN 60) without exposing the overarching command center network to unnecessary broadcast traffic.

#### NEW

The target production topology uses Router-on-a-Stick cross-VLAN communication. The core router would use trunking encapsulation and virtual sub-interfaces to route traffic between the isolated networks. This configuration would allow the edge server (VLAN 50) to transmit real-time WebSocket alerts and REST API payloads to operator terminals (VLAN 60) without exposing the wider command center network to unnecessary broadcast traffic.

#### Evidence

The live paragraph was re-read on 2026-08-27 at native range `t.y7ms6bhlk4qn:187931–188384`. It follows a target-production specification but states its behavior as an already operating topology.

#### Proposed comment (same gate as associated replacement)

Previous: Cross-VLAN communication is executed via a Router-on-a-Stick topology. The core router utilizes trunking encapsulation and virtual sub-interfaces to securely route traffic between these isolated networks. This configuration enables the edge server (VLAN 50) to securely transmit real-time WebSocket alerts and REST API payloads to the operator terminals (VLAN 60) without exposing the overarching command center network to unnecessary broadcast traffic.

Codex ID: PS-20260827-CDRRMO-DEPLOYMENT-OVERCLAIM

Done by Codex.

### 3. Defense paper — Chapter 3, Deployment Architecture, Figure 19 introduction

Page/s: unconfirmed rendered page (TOC: 129).

#### OLD

> The system utilized a localized deployment architecture based on the edge computing paradigm. Unlike traditional web applications that distribute web and database servers across remote cloud infrastructure, this system consolidated all processing onto a high-performance physical machine deployed directly within the Lipa CDRRMO command center (see Figure 19).

#### NEW

The proof of concept was evaluated on localized researcher-controlled hardware based on the edge-computing paradigm. Unlike traditional web applications that distribute web and database servers across remote cloud infrastructure, the target production design would consolidate processing on a high-performance physical machine within the Lipa CDRRMO command center (see Figure 19).

#### Evidence

The live paragraph was re-read on 2026-08-27 at native range `t.y7ms6bhlk4qn:188385–188745`. The CDRRMO physical-machine assertion conflicts with the live Scope and Delimitations boundary.

#### Proposed comment (same gate as associated replacement)

Previous: The system utilized a localized deployment architecture based on the edge computing paradigm. Unlike traditional web applications that distribute web and database servers across remote cloud infrastructure, this system consolidated all processing onto a high-performance physical machine deployed directly within the Lipa CDRRMO command center (see Figure 19).

Codex ID: PS-20260827-CDRRMO-DEPLOYMENT-OVERCLAIM

Done by Codex.

### 4. Defense paper — Chapter 3, Deployment Architecture, Hosting Environment heading

Page/s: unconfirmed rendered page (TOC: 129).

#### OLD

> Hosting Environment. The deployment environment employed enterprise-grade hardware capable of supporting the agency's extensive video ingestion pipeline.

#### NEW

Target Production Hosting Environment. The proposed deployment environment would require enterprise-grade hardware capable of supporting the agency's extensive video ingestion pipeline.

#### Evidence

The live heading was re-read on 2026-08-27 at native range `t.y7ms6bhlk4qn:189230–189383`. It describes a target production environment as already employed.

#### Proposed comment (same gate as associated replacement)

Previous: Hosting Environment. The deployment environment employed enterprise-grade hardware capable of supporting the agency's extensive video ingestion pipeline.

Codex ID: PS-20260827-CDRRMO-DEPLOYMENT-OVERCLAIM

Done by Codex.

### 5. Defense paper — Chapter 3, Deployment Architecture, Server Specifications

Page/s: unconfirmed rendered page (TOC: 129).

#### OLD

> Server Specifications: Parallel deep learning object detection and asynchronous routing for 418 cameras required an enterprise-grade edge server. The hardware specification included a Dell PowerEdge R760xa, dual Intel Xeon Platinum 8468 processors, 512GB ECC DDR5 RAM, and dual 2 TB NVMe Gen4 SSDs in RAID 1 for high-speed database input/output. The server featured a multi-GPU array of 8 NVIDIA L4 Tensor Core GPUs, collectively providing sufficient VRAM (Video Random Access Memory) to support hundreds of concurrent streams without Out-of-Memory (OOM) errors.

#### NEW

Server Specifications: A target deployment serving 418 cameras would require an enterprise-grade edge server. The proposed hardware specification includes a Dell PowerEdge R760xa, dual Intel Xeon Platinum 8468 processors, 512GB ECC DDR5 RAM, dual 2 TB NVMe Gen4 SSDs in RAID 1, and a multi-GPU array of 8 NVIDIA L4 Tensor Core GPUs. This configuration is designed to provide sufficient VRAM for hundreds of concurrent streams.

#### Evidence

The live paragraph was re-read on 2026-08-27 at native range `t.y7ms6bhlk4qn:189384–189946`. The named server and eight-GPU configuration are target-production assumptions, not installed project hardware.

#### Proposed comment (same gate as associated replacement)

Previous: Server Specifications: Parallel deep learning object detection and asynchronous routing for 418 cameras required an enterprise-grade edge server. The hardware specification included a Dell PowerEdge R760xa, dual Intel Xeon Platinum 8468 processors, 512GB ECC DDR5 RAM, and dual 2 TB NVMe Gen4 SSDs in RAID 1 for high-speed database input/output. The server featured a multi-GPU array of 8 NVIDIA L4 Tensor Core GPUs, collectively providing sufficient VRAM (Video Random Access Memory) to support hundreds of concurrent streams without Out-of-Memory (OOM) errors.

Codex ID: PS-20260827-CDRRMO-DEPLOYMENT-OVERCLAIM

Done by Codex.

### 6. Defense paper — Chapter 3, Deployment Architecture, Operating System

Page/s: unconfirmed rendered page (TOC: 129).

#### OLD

> Operating System: The edge server ran a modern 64-bit enterprise Linux distribution, such as Ubuntu Server LTS. This environment ensured kernel stability and supported the NVIDIA CUDA Toolkit and cuDNN drivers required for sustained deep learning execution and efficient resource management.

#### NEW

Operating System: The target edge server would run a modern 64-bit enterprise Linux distribution, such as Ubuntu Server LTS. This environment would support the NVIDIA CUDA Toolkit and cuDNN drivers required for sustained deep learning execution and resource management.

#### Evidence

The live paragraph was re-read on 2026-08-27 at native range `t.y7ms6bhlk4qn:189947–190238`. It presents the target production server as running in CDRRMO already.

#### Proposed comment (same gate as associated replacement)

Previous: Operating System: The edge server ran a modern 64-bit enterprise Linux distribution, such as Ubuntu Server LTS. This environment ensured kernel stability and supported the NVIDIA CUDA Toolkit and cuDNN drivers required for sustained deep learning execution and efficient resource management.

Codex ID: PS-20260827-CDRRMO-DEPLOYMENT-OVERCLAIM

Done by Codex.

### 7. Defense paper — Chapter 3, Deployment Architecture, Network Configuration

Page/s: unconfirmed rendered page (TOC: 129).

#### OLD

> Network Configuration: The edge server connected via a Gigabit copper port (8GT) to one of the command center's Ruijie Reyee aggregation switches and was assigned a static IP address within the agency's dedicated CCTV Virtual LAN (VLAN). This setup placed the server on the same subnetwork as the VMS, specifically the Dahua DSS Pro server, enabling zero-latency intranet communication without traversing external firewalls. For client access, dispatchers used standard workstation browsers to navigate to the edge server’s static IP address and designated frontend port, facilitated by cross-VLAN routing rules within the core router.

#### NEW

Network Configuration: In the target production design, the edge server would connect via a Gigabit copper port (8GT) to a command-center aggregation switch and receive a static IP address within the agency's dedicated CCTV VLAN. This setup would place the server on the same subnetwork as the Dahua DSS Pro VMS and allow low-latency intranet communication without traversing external firewalls. Authorized client workstations would reach the edge server through the planned cross-VLAN routing rules.

#### Evidence

The live paragraph was re-read on 2026-08-27 at native range `t.y7ms6bhlk4qn:190239–190874`. It claims actual CDRRMO switch, VLAN, VMS, and dispatcher-workstation use.

#### Proposed comment (same gate as associated replacement)

Previous: Network Configuration: The edge server connected via a Gigabit copper port (8GT) to one of the command center's Ruijie Reyee aggregation switches and was assigned a static IP address within the agency's dedicated CCTV Virtual LAN (VLAN). This setup placed the server on the same subnetwork as the VMS, specifically the Dahua DSS Pro server, enabling zero-latency intranet communication without traversing external firewalls. For client access, dispatchers used standard workstation browsers to navigate to the edge server’s static IP address and designated frontend port, facilitated by cross-VLAN routing rules within the core router.

Codex ID: PS-20260827-CDRRMO-DEPLOYMENT-OVERCLAIM

Done by Codex.

### 8. Defense paper — Chapter 3, Deployment Architecture, Scalability and Performance Considerations heading

Page/s: unconfirmed rendered page (TOC: 129).

#### OLD

> Scalability and Performance Considerations. Despite the use of enterprise-grade local hardware, processing 400+ live video feeds requires rigorous software-level optimization and resource management to maintain system stability:

#### NEW

Target Scalability and Performance Considerations. A production design processing 400+ live video feeds would require rigorous software-level optimization and resource management to maintain system stability:

#### Evidence

The live heading was re-read on 2026-08-27 at native range `t.y7ms6bhlk4qn:190875–191103`. It presently presupposes that enterprise production hardware is in use.

#### Proposed comment (same gate as associated replacement)

Previous: Scalability and Performance Considerations. Despite the use of enterprise-grade local hardware, processing 400+ live video feeds requires rigorous software-level optimization and resource management to maintain system stability:

Codex ID: PS-20260827-CDRRMO-DEPLOYMENT-OVERCLAIM

Done by Codex.

### 9. Defense paper — Chapter 3, Deployment Architecture, Substream Targeting

Page/s: unconfirmed rendered page (TOC: 129).

#### OLD

> Substream Targeting: When requesting streams from the VMS Server, the URL included the subtype=1 parameter. This instructed the server to provide a 720p substream instead of a 2K main stream, significantly reducing inbound network traffic on the edge server and ensuring the system did not interfere with the NVRs' continuous 2K archival recording.

#### NEW

Substream Targeting: In the target VMS integration, stream requests would use the subtype=1 parameter to request a 720p substream instead of a 2K main stream. This approach would reduce inbound network traffic on the edge server and avoid interference with continuous 2K NVR archival recording.

#### Evidence

The live paragraph was re-read on 2026-08-27 at native range `t.y7ms6bhlk4qn:191104–191452`. It presents an unperformed CDRRMO VMS configuration as completed.

#### Proposed comment (same gate as associated replacement)

Previous: Substream Targeting: When requesting streams from the VMS Server, the URL included the subtype=1 parameter. This instructed the server to provide a 720p substream instead of a 2K main stream, significantly reducing inbound network traffic on the edge server and ensuring the system did not interfere with the NVRs' continuous 2K archival recording.

Codex ID: PS-20260827-CDRRMO-DEPLOYMENT-OVERCLAIM

Done by Codex.

### 10. Defense paper — Chapter 3, Deployment Architecture, Hardware Utilization and Computational Load Balancing

Page/s: unconfirmed rendered page (TOC: 129).

#### OLD

> Hardware Utilization & Computational Load Balancing: To manage computational and thermal load, the AI engine targeted an inference rate of 15 FPS per camera, with rates below 10 FPS flagged as a performance warning.

#### NEW

Hardware Utilization & Computational Load Balancing: The target production design uses an inference target of 15 FPS per camera, with rates below 10 FPS defined as a performance warning.

#### Evidence

The live paragraph was re-read on 2026-08-27 at native range `t.y7ms6bhlk4qn:191453–191668`. The 15/10-FPS rule is a system target, but its placement in an asserted live-deployment subsection needs an explicit target-production qualifier.

#### Proposed comment (same gate as associated replacement)

Previous: Hardware Utilization & Computational Load Balancing: To manage computational and thermal load, the AI engine targeted an inference rate of 15 FPS per camera, with rates below 10 FPS flagged as a performance warning.

Codex ID: PS-20260827-CDRRMO-DEPLOYMENT-OVERCLAIM

Done by Codex.

### 11. Defense paper — Chapter 3, Deployment Architecture, Vertical Hardware Scalability

Page/s: unconfirmed rendered page (TOC: 129).

#### OLD

> Vertical Hardware Scalability: The architecture supported seamless vertical scaling. If additional cameras were deployed at city intersections, system capacity could be increased by installing more GPU accelerators in the edge server without modifying the underlying codebase.

#### NEW

Vertical Hardware Scalability: The target production architecture is designed for vertical scaling. If additional cameras are deployed at city intersections in a future authorized rollout, system capacity could be increased by installing more GPU accelerators in the edge server without modifying the underlying codebase.

#### Evidence

The live paragraph was re-read on 2026-08-27 at native range `t.y7ms6bhlk4qn:191669–191945`. The planned hardware expansion is described as a production capability already supported in CDRRMO.

#### Proposed comment (same gate as associated replacement)

Previous: Vertical Hardware Scalability: The architecture supported seamless vertical scaling. If additional cameras were deployed at city intersections, system capacity could be increased by installing more GPU accelerators in the edge server without modifying the underlying codebase.

Codex ID: PS-20260827-CDRRMO-DEPLOYMENT-OVERCLAIM

Done by Codex.

### 12. Defense paper — Chapter 3, Deployment Architecture, Database Optimization

Page/s: unconfirmed rendered page (TOC: 129).

#### OLD

> Database Optimization: The database was configured with WAL. This enabled the dashboard to perform intensive read operations concurrently with the AI engine's high-frequency writes. This configuration eliminated database locking errors.

#### NEW

Database Optimization: The proof-of-concept database uses WAL, enabling concurrent dashboard reads and AI-engine writes. A future production deployment would retain this configuration to support concurrent access and reduce database-locking risk.

#### Evidence

The live paragraph was re-read on 2026-08-27 at native range `t.y7ms6bhlk4qn:191946–192182`. WAL is a real proof-of-concept behavior, but the existing sentence presents its benefit as established in the unexecuted production deployment.

#### Proposed comment (same gate as associated replacement)

Previous: Database Optimization: The database was configured with WAL. This enabled the dashboard to perform intensive read operations concurrently with the AI engine's high-frequency writes. This configuration eliminated database locking errors.

Codex ID: PS-20260827-CDRRMO-DEPLOYMENT-OVERCLAIM

Done by Codex.

### 13. Defense paper — Chapter 3, Deployment Architecture, Client-Side Caching

Page/s: unconfirmed rendered page (TOC: 129).

#### OLD

> Client-Side Caching: To minimize redundant server queries, the React dashboard implemented TanStack Query, which temporarily cached API responses in the client browser. This approach significantly reduced backend load when multiple operators accessed analytics dashboards simultaneously.

#### NEW

Client-Side Caching: The React dashboard implements TanStack Query, which temporarily caches API responses in the client browser to reduce redundant server queries.

#### Evidence

The live paragraph was re-read on 2026-08-27 at native range `t.y7ms6bhlk4qn:192183–192470`. TanStack Query is implemented in the proof of concept; the replacement removes only the unsupported claim of measured multi-operator backend reduction.

#### Proposed comment (same gate as associated replacement)

Previous: Client-Side Caching: To minimize redundant server queries, the React dashboard implemented TanStack Query, which temporarily cached API responses in the client browser. This approach significantly reduced backend load when multiple operators accessed analytics dashboards simultaneously.

Codex ID: PS-20260827-CDRRMO-DEPLOYMENT-OVERCLAIM

Done by Codex.

### 14. Defense paper — Chapter 3, Deployment Architecture, Design Constraints and Assumptions heading

Page/s: unconfirmed rendered page (TOC: 129).

#### OLD

> Design Constraints and Assumptions. The deployment was subject to several operational constraints and technical assumptions:

#### NEW

Target Production Design Constraints and Assumptions. Any future deployment would be subject to the following operational constraints and technical assumptions:

#### Evidence

The live heading was re-read on 2026-08-27 at native range `t.y7ms6bhlk4qn:192471–192595`. Its following paragraphs are already correctly framed as target-production assumptions; this heading must match them.

#### Proposed comment (same gate as associated replacement)

Previous: Design Constraints and Assumptions. The deployment was subject to several operational constraints and technical assumptions:

Codex ID: PS-20260827-CDRRMO-DEPLOYMENT-OVERCLAIM

Done by Codex.

## Approval / sync ledger

Package ID: `PS-20260827-CDRRMO-DEPLOYMENT-OVERCLAIM`

| Target | Approved scope | Applied/read back | Skipped/pending | Blocked |
| --- | --- | --- | --- | --- |
| Defense paper | blocks 1–14 and their attached comments | blocks 1–14 and 14 anchored comments, verified 2026-08-27 | — | — |
| ADAS_Paper_Audit plus tracker | no live write proposed; existing Action Stream items 0.13 and 1.0 remain the live tracking records | — | — | — |
| Standalone comments | none; every comment is attached to its corresponding defense-paper replacement | — | — | — |
