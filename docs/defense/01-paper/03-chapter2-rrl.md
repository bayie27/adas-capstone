# 03 — Chapter 2: Review of Related Literature and Studies

> **One-liner:** Chapter 2 connects the need for automated collision alerts to a YOLO-based, edge-hosted, human-supervised design and explains the evidence behind its accuracy target.
> **Panel risk:** high — the chapter is used to defend the detector family and the 85% mAP target, while the literature and ADAS results use different datasets, metrics, and test conditions.

## 1. What it is

Chapter 2 is the rationale for ADAS. It brings together research on human limits in continuous monitoring, detector architectures, edge hardware, difficult traffic scenes, human oversight, and Philippine local-government readiness.

The chapter is organized into six themes and a synthesis:

- Manual surveillance limitations and emergency response latency.
- Deep learning architectures for real-time traffic accident detection.
- Performance metrics and hardware trade-offs in edge-based computer vision.
- Challenges and strategies in dynamic traffic environments.
- Human-in-the-loop (HITL) approaches in automated surveillance.
- AI integration in city surveillance systems and emergency management.
- Synthesis: how those strands support ADAS’s chosen design.

The central argument is that ADAS should detect candidate vehicle-to-vehicle collisions quickly on local computing, then present an alert for human review. The literature explains why those choices are reasonable; it is not a measurement of ADAS’s own detection performance.

A key distinction for the defense:

- Published mAP describes benchmark detection performance under each cited study’s own setup.
- ADAS’s 85% mAP@0.50 target is a frame-level validation target.
- ADAS’s event-level recall on local footage is separate evidence about whether whole crash clips produce alerts.
- Published results do not replace the test tracker’s qualified ADAS results.

## 2. Where it lives

### In the paper

The authoritative source is Group 7 Defense Document, Chapter 2, “Review of Related Literature and Studies,” printed pages 28–47.

| Chapter 2 location                                                                          | Printed page | Use it for                                            |
| ------------------------------------------------------------------------------------------- | -----------: | ----------------------------------------------------- |
| Manual Surveillance Limitations and Emergency Response Latency                              |           28 | Human monitoring limits and the notification gap      |
| Deep Learning Architectures for Real-Time Traffic Accident Detection                        |           32 | Why the paper selects the YOLO family                 |
| Performance Metrics and Hardware Trade-offs in Edge-Based Computer Vision                   |           36 | The 85% mAP target and accuracy-versus-speed argument |
| Challenges and Strategies of Computer Vision Implementation in Dynamic Traffic Environments |           38 | Noise, occlusion, local vehicle types, and hardware   |
| HITL Approaches in Automated Surveillance                                                   |           42 | Human authority, automation bias, and alert fatigue   |
| AI Integration in City Surveillance Systems and Emergency Management                        |           44 | Philippine LGU policy and infrastructure context      |
| Synthesis                                                                                   |           47 | The joined design rationale                           |

Chapter 2 has no numbered table or figure for these literature claims. Cite the named subsection and printed page. The paper’s reference list begins on printed page 199; the guide keeps each study’s author-year citation as printed in Chapter 2.

The accuracy result used in the comparison below comes from the tracker, not from a published comparator: ADAS Test Execution.xlsx, “AI Model Validation,” AI-VAL-001 through AI-VAL-010. The test plan states that the mAP result is a qualified validation-split result and event-level performance is reported separately.

### In the code

These files show how the literature-motivated choices operate in the current implementation. They are mechanism references, not evidence that a published benchmark transfers to Lipa.

- Model runtime: ai_engine/config.py:47 selects epoch50.pt by default; ai_engine/detector.py:162 and ai_engine/detector.py:177 construct the Ultralytics YOLO detector.
- Frame preparation and class selection: ai_engine/detector.py:28 converts frames to grayscale; ai_engine/detector.py:202 runs batched prediction; ai_engine/detector.py:342 retains the accident class.
- RTSP capture and edge processing: ai_engine/camera.py:40 defines the camera reader; ai_engine/camera.py:165 opens the stream; ai_engine/pipeline.py:111 gathers newest eligible frames; ai_engine/pipeline.py:149 runs inference.
- Temporal event evidence: ai_engine/config.py:111 sets the frame-confidence parameter; ai_engine/config.py:119, ai_engine/config.py:120, ai_engine/config.py:121, and ai_engine/config.py:122 define accumulator values; ai_engine/accumulate.py:65, ai_engine/accumulate.py:77, ai_engine/accumulate.py:108, and ai_engine/accumulate.py:123 link boxes and accumulate evidence over time.
- Alert pause and human decision: ai_engine/pipeline.py:222 and ai_engine/pipeline.py:224 pause the camera before event handoff; backend/app/services/incidents.py:229 and backend/app/services/incidents.py:268 enforce conditional incident transitions; backend/app/api/routes/alerts.py:464 and backend/app/api/routes/alerts.py:476 expose operator confirmation.

## 3. How it works

The chapter makes a chain of design arguments.

1. Human-factor studies describe why an operator can miss an event among many feeds. ADAS therefore generates a visible collision candidate and alert instead of relying only on continuous manual scanning.
2. Detector studies compare accuracy with compute cost and latency. The paper uses that trade-off to select a single-stage YOLO-family detector for live video.
3. Benchmark studies supply an accuracy range for the objective. The paper sets an mAP@0.50 target of at least 0.85; this is a project target informed by prior results, not a universal safety cutoff.
4. Traffic-environment studies describe low image quality, glare, occlusion, unusual vehicles, and hardware limits. The paper uses that context to motivate a localized, resource-conscious design and evaluation on Lipa footage.
5. Human-oversight studies warn against fully autonomous decisions and alert overload. ADAS presents candidate incidents for an operator to confirm, dismiss, or clear.
6. Philippine policy and LGU-readiness sources explain why a local system must fit constrained staff and infrastructure. They motivate the system context; they do not prove its measured accuracy.

The current ADAS result must be explained alongside, not substituted for, those studies:

- The tracker records accident-class mAP@0.50 = 0.956 (95.6%) for epoch50.pt on the recorded validation split.
- The tracker qualifies that value: the original split was not available for a fresh rerun, and frame-level incident leakage is disclosed. It is not independent operational detection accuracy.
- The frozen local-clip run records 8/16 overall crash recall, 8/10 standard recall, 0/6 hard recall, and 3 false positives over 11.0 clean minutes (0.27 FP/min).
- Therefore “95.6% mAP” does not mean “95.6% of road crashes will be caught.” The metric, corpus, and qualification must be named.

## 4. Why it was built this way

The study ledger below follows the paper’s own summaries. “No quantitative result stated” means Chapter 2 does not provide a number for that source; the guide does not fill one in from memory. The implementation link states the ADAS decision the study supports, not that the paper proves that decision will work under every Lipa camera condition.

### Our claim → supporting reference

| Our claim                                                         | Supporting reference in the paper                                                                     | Specific ADAS decision it supports                                                                                                   |
| ----------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| Continuous manual scanning can miss visible incidents under load. | Goh et al. (2021); De Bruyne et al. (2021); Williot et al. (2024), Ch. 2, pp. 28–29                   | Generate an alert for candidate collisions instead of relying only on the operator’s visual scan.                                    |
| Faster notification matters in trauma response.                   | Khan et al. (2024); Rickenbach et al. (2024), Ch. 2, pp. 29–31                                        | Prioritize rapid detection and alert presentation; do not claim ADAS changes mortality or dispatch outcomes.                         |
| A one-stage YOLO detector is a practical live-video choice.       | Li et al. (2025a); Chen, Q. (2025); Sapkota and Karkee (2025); Arefin et al. (2025), Ch. 2, pp. 32–35 | Use the YOLO family for the detector pipeline; select the current size and engine using the paper’s methods and evaluation evidence. |
| An 85% mAP@0.50 target is plausible and demanding.                | Ahmed et al. (2023); Li et al. (2025a); Gurusamy et al. (2025), Ch. 2, pp. 36–37                      | Set Objective 3’s validation-split target at mAP@0.50 ≥ 0.85.                                                                        |
| An mAP target alone does not establish event detection in Lipa.   | Minh et al. (2025), plus AI-VAL-002 and AI-VAL-003 in the tracker                                     | Report local event recall by difficulty separately from frame-level mAP.                                                             |
| Traffic conditions can break transfer from structured data.       | Wen et al. (2025); Padia et al. (2024); Fu et al. (2024); Serrano et al. (2026), Ch. 2, pp. 38–41, 47 | Use locally relevant vehicle data and reserve Lipa footage for the held-out evaluation described in the paper.                       |
| Continuous inference belongs on local, capable hardware.          | Masum and Islam (2025); Rossi and Saponara (2024); Quimba et al. (2025), Ch. 2, pp. 39–41, 44–46      | Run inference on the edge server and keep the operator’s workstation available for the dashboard.                                    |
| High-stakes alerts require human authority.                       | Frenette (2023); Tilbury and Flowerday (2024); Baruwal Chhetri et al. (2024), Ch. 2, pp. 42–43        | Keep operator verification in the incident workflow; the system does not make dispatch decisions.                                    |
| Adding alerts can itself create cognitive load.                   | Baruwal Chhetri et al. (2024); Booker (2025); Tilbury and Flowerday (2024), Ch. 2, pp. 42–43          | Treat false alarms and alert fatigue as issues to measure and disclose, not assume away.                                             |
| Local policy and capacity shape the deployment context.           | DILG (2023); Quimba et al. (2025); NDRRMC (2020, 2022); Calosa et al. (2025), Ch. 2, pp. 44–47        | Fit the intended CDRRMO workflow and local infrastructure; do not claim agency-wide deployment from the paper’s proof of concept.    |

### 4.1 Manual surveillance limitations and emergency response latency

**Goh et al. (2021) — multitask surveillance and functional field of view.**

- Investigated: how increased cognitive load affects operators during multitask surveillance.
- Finding: heavier load narrows the functional field of view, so operators can miss peripheral events that are still visible. Chapter 2 reports no numerical effect size.
- ADAS decision: put a candidate collision in front of the operator instead of relying only on a visual scan of the camera grid.
- Paper: Ch. 2, Manual Surveillance Limitations and Emergency Response Latency, printed p. 28.

**De Bruyne et al. (2021) — realistic surveillance prototypes.**

- Investigated: operator performance while multitasking in realistic surveillance prototypes.
- Finding: multitasking and high cognitive load reduce target-detection speed and overall accuracy. Chapter 2 reports no quantitative result for this source.
- ADAS decision: use computer vision to surface candidate events; keep the operator responsible for the decision.
- Paper: Ch. 2, Manual Surveillance Limitations and Emergency Response Latency, printed p. 28.

**Williot et al. (2024) — gaze support and vigilance.**

- Investigated: surveillance behavior with a real-time, gaze-based support tool integrated with augmented reality.
- Finding: fatigue is associated with screen neglect and attention concentrated on limited screen regions. Chapter 2 reports no quantitative result for this source.
- ADAS decision: present incident evidence and the affected camera directly; do not claim ADAS reproduces the study’s gaze-support tool.
- Paper: Ch. 2, Manual Surveillance Limitations and Emergency Response Latency, printed p. 29.

**Babu and Rajitha (2022) — manual traffic surveillance.**

- Investigated: limitations of traditional human-observed traffic monitoring.
- Finding: continuous manual viewing is labor-intensive and vulnerable to cognitive fatigue, error, and poor scalability. Chapter 2 reports no quantitative result for this source.
- ADAS decision: automate candidate-event detection as an aid to municipal monitoring.
- Paper: Ch. 2, Manual Surveillance Limitations and Emergency Response Latency, printed p. 29.

**Sharif et al. (2023) — deep-learning detection and automated alerts.**

- Investigated: computer-vision frameworks for identifying and classifying incidents and sending alerts.
- Finding: automated identification can reduce delay and the human and financial costs associated with late reporting. Chapter 2 reports no quantitative result for this source.
- ADAS decision: deliver an alert promptly; this source does not establish ADAS-specific time savings or outcomes.
- Paper: Ch. 2, Manual Surveillance Limitations and Emergency Response Latency, printed p. 29.

**Hegedüs and Tóth (2024) — human perceptual differences.**

- Investigated: variation in operators’ sensory, perceptual, and attentional abilities.
- Finding: human-factor differences make manual detection inconsistent, especially under environmental stress. Chapter 2 reports no quantitative result for this source.
- ADAS decision: offer a consistent machine-generated cue while retaining a human verifier.
- Paper: Ch. 2, Manual Surveillance Limitations and Emergency Response Latency, printed p. 29.

**Rickenbach et al. (2024) — trauma response timing.**

- Investigated: the emergency-care interval after traumatic injury, including pediatric trauma registry patterns.
- Finding: early detection and dispatch are important even where physiological decline is not linear. Chapter 2 reports no quantitative result for this source.
- ADAS decision: prioritize timely incident notification; the study does not test ADAS or prove a patient-outcome benefit.
- Paper: Ch. 2, Manual Surveillance Limitations and Emergency Response Latency, printed pp. 29–30.

**Khan et al. (2024) — response time and road-trauma outcomes in Balochistan.**

- Investigated: road-traffic accident cases across tertiary hospitals and the association between response interval and outcome.
- Finding: response times above 15 minutes were associated with higher mortality than the 8–15 minute group and lower full-recovery likelihood. Reported values: mortality was 11.3% for response times above 15 minutes and 4.7% for 8–15 minutes.
- ADAS decision: support a faster notification workflow; these are Balochistan clinical figures, not Lipa’s baseline and not an ADAS impact estimate.
- Paper: Ch. 2, Manual Surveillance Limitations and Emergency Response Latency, printed p. 30.

### 4.2 Deep-learning architectures for real-time traffic accident detection

**Chen, Q. (2025) — traffic object detectors and YOLOv12.**

- Investigated: traffic object detection architectures, including YOLOv12.
- Finding: two-stage models use region proposals and classification; YOLOv12 adds Area Attention and R-ELAN while targeting low compute cost. Reported value: YOLOv12 reports 93.8% mAP@0.5.
- ADAS decision: select a single-stage YOLO-family detector for real-time processing; this comparison does not show that YOLOv12 is ADAS’s deployed model.
- Paper: Ch. 2, Deep Learning Architectures for Real-Time Traffic Accident Detection, printed pp. 32–35.

**Li et al. (2025a) — improved YOLO11-AMF for traffic accidents.**

- Investigated: an improved YOLO11 architecture for complex traffic scenarios and compared it with heavier detection models.
- Finding: the YOLO11-based design has a smaller reported compute footprint than Faster R-CNN while maintaining strong precision. Reported values: 96.5% precision and 66.0% mAP50–95 for YOLO11-AMF; 2.7 million parameters and 6.8 GFlops. Faster R-CNN is reported at 66.1% mAP50–95, 28.2 million parameters, and 37.52 GFlops.
- ADAS decision: prefer a light, fast YOLO-family model for live streams over a heavier two-stage model; do not compare mAP50–95 directly with mAP@0.50.
- Paper: Ch. 2, Deep Learning Architectures for Real-Time Traffic Accident Detection, printed pp. 32–34; Performance Metrics and Hardware Trade-offs, printed p. 36.

**Sapkota and Karkee (2025) — YOLO detector evolution and deployment.**

- Investigated: the YOLO family and related detector choices, including RT-DETR and YOLO26.
- Finding: the review describes accuracy and compute trade-offs, with a deployment-first direction for YOLO26. Reported values: RT-DETR is approximately 51–54% mAP; YOLO26 CPU inference is approximately 38.9 ms.
- ADAS decision: defend a YOLO-family approach with attention to deployment cost; neither reported figure is an ADAS measurement.
- Paper: Ch. 2, Deep Learning Architectures for Real-Time Traffic Accident Detection, printed pp. 33–35.

**Sousa and Aquino-Junior (2024) — single-stage detector design.**

- Investigated: detector architectures that predict boxes and classes in one network pass, alongside SSD and EfficientDet design approaches.
- Finding: single-stage designs avoid the region-proposal stage; the paper’s review says YOLO is faster for the intended real-time use. Chapter 2 reports no quantitative result for this source.
- ADAS decision: use a single-stage detector for live streams; the RRL does not establish that every single-stage model is equally fast.
- Paper: Ch. 2, Deep Learning Architectures for Real-Time Traffic Accident Detection, printed p. 33.

**Li et al. (2025b) — DSGF-YOLO and overlapping collision vehicles.**

- Investigated: a lightweight traffic-accident detector and severity classifier using a Focaler-IoU strategy.
- Finding: the paper describes prioritizing difficult, overlapping vehicles during collisions. Chapter 2 reports no quantitative result for this source.
- ADAS decision: account for overlapping objects when evaluating collisions; do not claim ADAS implements Focaler-IoU.
- Paper: Ch. 2, Deep Learning Architectures for Real-Time Traffic Accident Detection, printed p. 33.

**Minh et al. (2025) — YOLOv8 on live CCTV traffic.**

- Investigated: real-time traffic-accident detection using YOLOv8.
- Finding: the paper reports useful Normal-versus-Accident classification at a lower mAP range than the ADAS target. Reported value: mAP@0.50 of 60.9%–67.4%.
- ADAS decision: support a fast YOLO detector for CCTV and remind the team that a published mAP value is dataset- and task-specific.
- Paper: Ch. 2, Deep Learning Architectures for Real-Time Traffic Accident Detection, printed p. 33; Performance Metrics and Hardware Trade-offs, printed p. 36.

**Shreya et al. (2025) — SafeLane traffic management and accident detection.**

- Investigated: a YOLO-and-LSTM system for real-time traffic management and accident detection.
- Finding: the paper highlights YOLOv8’s anchor-free approach for locating vehicles in dense traffic and a decoupled detection head. Chapter 2 reports no quantitative result for this source.
- ADAS decision: cite YOLO’s localization design as support for the detector family, not as an ADAS benchmark.
- Paper: Ch. 2, Deep Learning Architectures for Real-Time Traffic Accident Detection, printed p. 33.

**Arefin et al. (2025) — rapid accident detection in Bangladesh.**

- Investigated: GPU-based YOLOv11 detection for road accidents.
- Finding: the study reports fast per-frame inference with high precision and less-than-perfect recall. Reported values: 19.93 ms per frame, over 130 FPS, precision 1.0, recall 0.8249.
- ADAS decision: support a low-latency YOLO-family choice; these precision and recall results are not mAP and come from another traffic setting.
- Paper: Ch. 2, Deep Learning Architectures for Real-Time Traffic Accident Detection, printed p. 34.

### 4.3 Performance metrics and hardware trade-offs

This subsection gives context for the 85% objective. The values below use different metrics and test conditions; they are literature anchors, not a leaderboard.

| Study                     | Number reported in Chapter 2                                                  | What it supports                                                     | Comparison caution                                                                       |
| ------------------------- | ----------------------------------------------------------------------------- | -------------------------------------------------------------------- | ---------------------------------------------------------------------------------------- |
| Ahmed et al. (2023)       | YOLOv5 mAP 83.3%                                                              | An 85% target is in range of reported traffic-accident detectors.    | The RRL does not state the IoU basis for this mAP.                                       |
| Li et al. (2025a)         | YOLOv5n mAP@0.50 82.4%; YOLO11-AMF mAP50–95 66.0%                             | Light YOLO models can report strong results at low compute cost.     | mAP@0.50 and mAP50–95 are different metrics.                                             |
| Minh et al. (2025)        | YOLOv8 mAP@0.50 60.9%–67.4%                                                   | Lower mAP can still support the study’s Normal-versus-Accident task. | Not a direct ADAS event-recall comparison.                                               |
| Gurusamy et al. (2025)    | Improved YOLOv5 mAP 88.7%                                                     | Custom data can support a target in the 85%–88% range.               | The RRL does not specify matching classes or IoU.                                        |
| Chen, Q. (2025)           | YOLOv12 mAP@0.5 93.8%                                                         | A recent YOLO detector can report a higher mAP@0.5.                  | Different model, dataset, and evaluation conditions.                                     |
| Li et al. (2025a)         | Faster R-CNN mAP50–95 66.1%, 28.2 million parameters, 37.52 GFlops            | Accuracy should be balanced with inference cost.                     | The model’s lower parameter efficiency is a hardware trade-off, not proof it cannot run. |
| Arefin et al. (2025)      | Precision 1.0; recall 0.8249; latency 19.93 ms/frame                          | YOLOv11 can have low reported GPU inference latency.                 | Precision and recall are not mAP.                                                        |
| Sapkota and Karkee (2025) | RT-DETR mAP approximately 51%–54%; YOLO26 CPU inference approximately 38.9 ms | Transformer and deployment-focused models have different trade-offs. | Review-level figures use distinct evaluation setups.                                     |

**Ahmed et al. (2023) — YOLOv5 accident detection and severity classification.**

- Investigated: a real-time computer-vision system for detecting and classifying traffic incidents.
- Finding: the paper reports that the YOLOv5 approach detected collisions and triggered alert messages. Reported value: mAP 83.3%.
- ADAS decision: set an ambitious validation target near this reported range while also evaluating local event-level behavior.
- Paper: Ch. 2, Performance Metrics and Hardware Trade-offs in Edge-Based Computer Vision, printed p. 36.

**Gurusamy et al. (2025) — custom data for road-accident detection.**

- Investigated: improved YOLOv5 models trained on custom, self-built datasets for accident detection and severity assessment.
- Finding: the study is described as providing robust real-time performance in complex road environments. Reported value: mAP 88.7%.
- ADAS decision: motivate locally relevant data and show that an 85%–88% target is plausible in a custom-data study.
- Paper: Ch. 2, Performance Metrics and Hardware Trade-offs in Edge-Based Computer Vision, printed p. 37.

**Sousa and Junior (2025) — YOLO versions on NVIDIA Jetson Orin.**

- Investigated: comparative YOLOv9, YOLOv10, and YOLOv11 performance on embedded hardware for service robotics.
- Finding: the review uses the study to argue that small accuracy differences may justify a faster, lighter model. Reported comparison: accuracy differences are often less than 1% mAP.
- ADAS decision: consider FPS and latency when choosing model size; the study is robotics evidence, not traffic-accident validation.
- Paper: Ch. 2, Performance Metrics and Hardware Trade-offs in Edge-Based Computer Vision, printed p. 37.

### 4.4 Dynamic traffic environments and local conditions

**Wen et al. (2025) — video quality and near-miss analysis.**

- Investigated: YOLO-based object detection and near-miss analysis in high- and low-quality traffic video.
- Finding: controlled training conditions and degraded real footage can differ, with image quality affecting reliable detection. Chapter 2 reports no quantitative result for this source.
- ADAS decision: evaluate the adopted detector on CCTV-style footage and disclose resolution sensitivity.
- Paper: Ch. 2, Challenges and Strategies of Computer Vision Implementation in Dynamic Traffic Environments, printed p. 38.

**Lin et al. (2025) — atmospheric noise and detection.**

- Investigated: visual degradation from adverse weather and lighting in computer-vision settings.
- Finding: rain, fog, snow, headlight glare, and sunlight can degrade features and increase unstable boxes or missed detections. Chapter 2 reports no quantitative result for this source.
- ADAS decision: treat weather and glare as conditions to validate locally rather than assume the benchmark transfers.
- Paper: Ch. 2, Challenges and Strategies of Computer Vision Implementation in Dynamic Traffic Environments, printed p. 38.

**Padia et al. (2024) — structured datasets and developing-region traffic.**

- Investigated: the limits of transferring models trained on structured road datasets into heterogeneous traffic scenes.
- Finding: dense traffic, irregular maneuvers, and local vehicle types can expose a generalization gap. Chapter 2 reports no quantitative result for this source.
- ADAS decision: use local traffic context in dataset preparation and hold out local footage for evaluation.
- Paper: Ch. 2, Challenges and Strategies of Computer Vision Implementation in Dynamic Traffic Environments, printed pp. 38–39, and Synthesis, p. 47.

**Fu et al. (2024) — image quality, occlusion, and object continuity.**

- Investigated: computer-vision behavior under compressed or low-resolution video and traffic occlusion.
- Finding: degraded detail and vehicles blocking one another can disrupt localization and tracking continuity. Chapter 2 reports no quantitative result for this source.
- ADAS decision: evaluate vehicle-to-vehicle collision evidence in realistic camera views and avoid assuming every small object remains trackable.
- Paper: Ch. 2, Challenges and Strategies of Computer Vision Implementation in Dynamic Traffic Environments, printed pp. 38–40.

**Serrano et al. (2026) — vehicle classification and region-specific traffic.**

- Investigated: YOLOv8m vehicle classification with an alpha-scaled gradient-normalized sigmoid activation.
- Finding: the RRL uses this work to discuss visually distinct local vehicles, including jeepneys and tricycles, and traffic occlusion. Chapter 2 reports no quantitative result for this source.
- ADAS decision: include Philippine vehicle appearances in the paper’s training-data rationale; do not claim this paper validates ADAS on Lipa footage.
- Paper: Ch. 2, Challenges and Strategies of Computer Vision Implementation in Dynamic Traffic Environments, printed p. 39.

**Rossi and Saponara (2024) — sustained edge-GPU workloads.**

- Investigated: constraints in continuous edge-device inference compared with CPU processing.
- Finding: parallel GPU processing is still subject to system-level limits under continuous workloads. Chapter 2 reports no quantitative result for this source.
- ADAS decision: assign inference to the dedicated server rather than burden the operator workstation.
- Paper: Ch. 2, Challenges and Strategies of Computer Vision Implementation in Dynamic Traffic Environments, printed p. 40.

**Masum and Islam (2025) — hardware-aware YOLO inference.**

- Investigated: consumer-GPU acceleration strategies for YOLOv10s and limits from memory bandwidth and host-to-device transfers.
- Finding: continuous inference can cause thermal throttling that degrades speed and stability. Reported condition: thermal throttling is described as often triggering around 87°C on consumer-grade hardware.
- ADAS decision: use a hardware-conscious edge-server architecture; do not claim the cited temperature is ADAS’s measured operating temperature.
- Paper: Ch. 2, Challenges and Strategies of Computer Vision Implementation in Dynamic Traffic Environments, printed p. 40.

**Abdulhaq and Ahmed (2025) — embedded object detection.**

- Investigated: real-time object detection and recognition on embedded systems using open-source computer-vision frameworks.
- Finding: model optimization, including quantization and pruning, can reduce hardware burden while preserving useful detection. Chapter 2 reports no quantitative result for this source.
- ADAS decision: make model size and deployment efficiency part of the design; this citation does not prove ADAS needs or uses quantization.
- Paper: Ch. 2, Challenges and Strategies of Computer Vision Implementation in Dynamic Traffic Environments, printed p. 40.

**Chen, X. (2025) — edge-computing smart cameras.**

- Investigated: smart-camera video processing and recognition using edge computing.
- Finding: centralized cloud inference can add bandwidth and latency dependence; edge-cloud distribution moves analysis closer to data. Chapter 2 reports no quantitative result for this source.
- ADAS decision: run local inference and keep the system usable without relying on an external cloud service.
- Paper: Ch. 2, Challenges and Strategies of Computer Vision Implementation in Dynamic Traffic Environments, printed pp. 40–41.

### 4.5 HITL approaches in automated surveillance

**Frenette (2023) — oversight, control, and accountability.**

- Investigated: a framework for human control and accountability in high-performance AI systems.
- Finding: oversight should be part of system design, especially in high-stakes decisions. Chapter 2 reports no quantitative result for this source.
- ADAS decision: require operator action on candidate incidents; AI does not make emergency-dispatch decisions.
- Paper: Ch. 2, HITL Approaches in Automated Surveillance, printed pp. 42–43.

**Kapoor (2025) — human roles in AI evaluation.**

- Investigated: the evolving role of human-in-the-loop evaluations in advanced AI.
- Finding: people remain interpreters and bias-identification specialists rather than replaceable components. Chapter 2 reports no quantitative result for this source.
- ADAS decision: keep the operator’s verification step and account for human judgment in the incident workflow.
- Paper: Ch. 2, HITL Approaches in Automated Surveillance, printed p. 42.

**Balbaa and Abdurashidova (2024) — support primitives for human-AI work.**

- Investigated: human-machine collaboration and ways to support appropriate trust.
- Finding: evidence checklists and uncertainty communication can help people retain an active, critical role. Chapter 2 reports no quantitative result for this source.
- ADAS decision: surface the incident snapshot and an explicit operator action; do not claim ADAS implements every support primitive in the cited work.
- Paper: Ch. 2, HITL Approaches in Automated Surveillance, printed pp. 42–43.

**Tilbury and Flowerday (2024) — automation bias in security operations.**

- Investigated: automation bias and complacency among security-operation analysts.
- Finding: over-trust can cause errors of commission and omission when people accept incorrect recommendations or miss what automation did not flag. Chapter 2 reports no quantitative result for this source.
- ADAS decision: keep a human in the decision loop and do not present an AI alert as a confirmed accident.
- Paper: Ch. 2, HITL Approaches in Automated Surveillance, printed p. 43.

**Boonprakong et al. (2023) — transparency and accountability.**

- Investigated: transparency in collaborative human-AI settings.
- Finding: limited visibility into AI reasoning can make accountability difficult; uncertainty communication supports calibrated trust. Chapter 2 reports no quantitative result for this source.
- ADAS decision: present evidence with the alert and preserve an auditable human decision.
- Paper: Ch. 2, HITL Approaches in Automated Surveillance, printed p. 43.

**Baruwal Chhetri et al. (2024) — alert fatigue and A2C teamwork.**

- Investigated: alert fatigue in security operations and an Automated, Augmented, Collaborative task-allocation model.
- Finding: AI can filter routine triage and escalate ambiguous or high-risk cases for human verification; excess notifications can desensitize operators. Chapter 2 reports no quantitative result for this source.
- ADAS decision: use alerts to prioritize candidate incidents while measuring false alarms; do not send every frame as an alert.
- Paper: Ch. 2, HITL Approaches in Automated Surveillance, printed pp. 43–44.

**Booker (2025) — control-room workload.**

- Investigated: the relationship between control-room design, automation, and operator cognitive demand.
- Finding: automation shifts people toward supervisory work but can raise cognitive demand if poorly integrated. Chapter 2 reports no quantitative result for this source.
- ADAS decision: design the dashboard around a manageable incident-review workflow and avoid claiming automation removes operator workload.
- Paper: Ch. 2, HITL Approaches in Automated Surveillance, printed p. 43.

### 4.6 City surveillance systems and emergency management

**DILG (2023) — technology-driven local governance.**

- Investigated: national policy direction for technology use by local government units and local emergency-operation centers.
- Finding: the cited directives call for technology, CCTV, and digital applications to improve communication and disaster response. Chapter 2 reports no quantitative result for this source.
- ADAS decision: frame the system around the CDRRMO’s local emergency-monitoring workflow; the policy is not a product-performance result.
- Paper: Ch. 2, AI Integration in City Surveillance Systems and Emergency Management, printed p. 44.

**Sumad-On et al. (2024) — MMDA no-contact apprehension.**

- Investigated: the effectiveness of the No-Contact Apprehension Policy and the MMDA’s Project CATCH-ALL context.
- Finding: the RRL describes CCTV-supported traffic enforcement as a metropolitan precedent, while noting its dependence on funding, upgrades, and infrastructure. Chapter 2 reports no quantitative result for this source.
- ADAS decision: use urban surveillance as context, not as proof that an accident-alert tool has the same effects as traffic enforcement.
- Paper: Ch. 2, AI Integration in City Surveillance Systems and Emergency Management, printed p. 44.

**Quimba et al. (2025) — AI readiness among Philippine LGUs.**

- Investigated: local-government readiness to adopt AI outside the National Capital Region.
- Finding: the RRL reports low-to-moderate readiness tied to infrastructure, budgets, and shortages of ICT-skilled staff. Chapter 2 reports no readiness score.
- ADAS decision: prioritize a resource-conscious local deployment model suited to provincial LGU constraints.
- Paper: Ch. 2, AI Integration in City Surveillance Systems and Emergency Management, printed pp. 45–46.

**NDRRMC (2022) — local DRRM staffing.**

- Investigated: staffing and operating conditions for local disaster-risk-reduction offices.
- Finding: local offices are responsible for extensive plans and response requirements with limited permanent staff. Reported averages: city offices have 6 permanent staff; municipalities have 1.
- ADAS decision: build a monitoring aid for existing staff capacity; these national averages are not a count of Lipa CDRRMO personnel.
- Paper: Ch. 2, AI Integration in City Surveillance Systems and Emergency Management, printed p. 45.

**Calosa et al. (2025) — Lipa CDRRMO context.**

- Investigated: personnel and resource constraints affecting Lipa CDRRMO’s ability to respond across dispersed areas.
- Finding: the RRL uses this source to ground the operational problem locally. Chapter 2 reports no quantitative result for this source.
- ADAS decision: focus the problem framing on the intended local command center; this is context, not an evaluation of the completed system.
- Paper: Ch. 2, AI Integration in City Surveillance Systems and Emergency Management, printed p. 46.

**NDRRMC (2020) — national DRRM plan.**

- Investigated: the National Disaster Risk Reduction and Management Plan 2020–2030 and its strategic directions.
- Finding: the paper cites digital transformation, ICT, and innovation as directions for disaster mitigation and response. The plan’s title period is 2020–2030; no outcome measure is cited.
- ADAS decision: describe alignment with the national policy direction without claiming formal government adoption.
- Paper: Ch. 2, AI Integration in City Surveillance Systems and Emergency Management, printed p. 46.

### 4.7 Synthesis

The synthesis combines the six themes into one design rationale:

- Cognitive overload and vigilance decline explain why an alert can help a human operator notice a candidate collision.
- Detector comparisons support the YOLO family because it balances detection quality and speed for live video.
- Edge-computing work supports local inference where hardware, network, and staff capacity are constrained.
- Research on traffic heterogeneity supports locally relevant training data and held-out evaluation with Lipa footage.
- HITL literature supports human confirmation and accountability instead of fully autonomous incident decisions.
- Philippine policy and readiness sources explain the local need and deployment context.

The paper’s synthesis specifically connects local vehicle appearances, a hybrid dataset, held-out Lipa CDRRMO footage, YOLO, client-server edge processing, and HITL review. Cite Chapter 2, Synthesis, printed p. 47.

The synthesis supports a design direction. It does not establish that the current model detects every event, that ADAS improves patient outcomes, or that the system is already deployed across the city’s camera network.

## 5. What changed since the 28 April defense

The current source set provides the current paper and its Chapter 2, but it does not identify an earlier Chapter 2 version for a line-by-line comparison.

Specific RRL changes since the 28 April 2026 defense are [UNSOURCED — verify]. Do not guess which citations or claims were added or removed; compare against the version used at that defense before making a before-and-after claim.

## 6. Limits and honest caveats

### What the literature does not establish

- The cited mAP figures come from different datasets, class definitions, hardware, annotation practice, and test protocols.
- mAP@0.50, mAP50–95, precision, recall, and event-level recall are different measurements. Do not compare them as if they were one accuracy score.
- Chapter 2 does not cite a study that derives the exact runtime detector confidence value of 0.15. The code value is at ai_engine/config.py:111; defend its selection using the paper’s model method and evaluation record, not by attributing it to one RRL study.
- No cited study establishes a universal public-safety cutoff at 85% mAP. The paper sets that value as ADAS’s target; the cited traffic studies provide context for the target.
- The Balochistan response-time association does not prove ADAS reduces Lipa mortality, dispatch delay, or treatment time.
- The MMDA no-contact apprehension example is traffic enforcement, not a validation study for accident detection.
- HITL and alert-fatigue sources include security-operation and general AI contexts. They support oversight principles but do not measure ADAS operators’ performance.
- The RRL does not establish that ADAS is deployed across all Lipa CDRRMO cameras.

### What the ADAS tracker adds

- AI-VAL-001 records accident mAP@0.50 = 0.956 for epoch50.pt on the recorded validation split. Its qualification is explicit: the original split could not be rerun and frame-level incident leakage is disclosed.
- AI-VAL-002 records overall event recall of 8/16 (50%), standard recall of 8/10 (80%), hard recall of 0/6 (0%), and 0.27 false positives per minute over 11.0 clean minutes.
- AI-VAL-006 identifies 8 of 17 clips as night footage and reports that all 3 residual false positives were at night and involved nearby vehicles. The exact night-hit numerator is not recoverable from the current machine-readable labels.
- AI-VAL-009 records that reducing the source to 720p / 640×360 lowered recall from 8/16 to 6/16. That result reinforces the need to state source-resolution conditions when discussing transferability.
- These are project-specific results. Event recall and false-positive rate are descriptive evidence; the tracker does not set acceptance thresholds for them.

### Transferability to Lipa City

The RRL spans laboratory models, other countries, generic CCTV, embedded hardware, metropolitan enforcement, and national LGU studies. Those settings do not match every Lipa camera’s angle, resolution, lighting, traffic density, or event mix.

The strongest local relevance comes from the paper’s own use of held-out Lipa CDRRMO footage and the Lipa-specific operational context. That local evidence is still limited: the tracker’s hard stratum is 0/6, and the validation-split mAP is qualified. Present the literature as a reason for the design and the tracker as the bounded evidence for this build.

### Where the literature is thin

- No cited paper is a controlled head-to-head comparison of ADAS’s deployed YOLO26n configuration against Faster R-CNN, DETR, SSD, or other architectures on the same Lipa clips.
- No single cited paper establishes the 85% mAP target, the 0.15 runtime confidence, or the accumulator settings as universal values.
- Several studies have no numerical result reported in Chapter 2; defend their qualitative role without inventing effect sizes.
- The chapter spans 2021–2026, with architecture papers mainly from 2024–2026. The older human-monitoring work supports a stable human-factors rationale, while detector literature should be refreshed as models and deployment hardware change.

## 7. Likely panel questions

**Q: What accuracy do comparable systems report, and how does ADAS compare?**

**A:** Chapter 2 reports mAP values from 60.9%–67.4% for Minh et al., 82.4% mAP@0.50 for Li et al.’s YOLOv5n, 83.3% for Ahmed et al., and 88.7% for Gurusamy et al. The tracker records 95.6% mAP@0.50 for ADAS on a qualified validation split, but local event recall is 8/16 overall and 0/6 on hard clips, so those are different claims.

**Q: Which paper justifies your threshold?**

**A:** No single paper mathematically sets the 85% target. Ahmed’s 83.3%, Li’s YOLOv5n 82.4% mAP@0.50, and Gurusamy’s 88.7% frame a plausible target range; the separate runtime confidence value of 0.15 is not prescribed by a Chapter 2 citation.

**Q: Did any study contradict your approach?**

**A:** The literature qualifies it: Minh et al. report useful Normal-versus-Accident classification at 60.9%–67.4% mAP@0.50, so 85% is not a universal minimum for every task. The tracker also shows why benchmark mAP is not enough for Lipa: hard-event recall is 0/6.

**Q: Is any of your literature out of date?**

**A:** Chapter 2 cites work from 2021 through 2026, including recent detector studies from 2025 and 2026. The 2021 human-attention studies remain relevant to the cognitive argument, but detector comparisons should be refreshed before a production-scale model choice.

**Q: Is 95.6% mAP proof that ADAS catches 95.6% of crashes?**

**A:** No. That is accident-class mAP@0.50 on a validation split, qualified by the tracker because the original split was unavailable for a fresh run and frame-level incident leakage is disclosed. On the separate local event corpus, the recorded recall is 8/16 overall and 0/6 for hard clips.

**Q: Why use YOLO instead of Faster R-CNN or a transformer?**

**A:** Chapter 2 presents YOLO as a single-stage choice that balances accuracy and speed for live feeds. The cited Faster R-CNN and transformer results have different metrics and compute costs; our choice is supported by the paper’s latency and hardware rationale, not by claiming every alternative cannot run.

**Q: How do you know the published findings transfer to Lipa traffic?**

**A:** The papers give design rationale, not a guarantee of transfer. The tracker’s Lipa footage is the local evidence: it records 8/16 overall recall and 0/6 hard recall, so we disclose where the model still needs improvement instead of generalizing from a foreign benchmark.

**Q: How does HITL help if the system can still generate false alerts?**

**A:** HITL keeps an operator responsible for confirming or dismissing a candidate event; it does not erase false alarms. The tracker records 3 false positives over 11.0 clean minutes, so false-alarm behavior remains part of the evidence and a limitation to address.

## 8. Cram summary

- Chapter 2 builds the case for automated alerts from six themes: human monitoring limits, detector design, edge performance, difficult traffic, HITL, and Philippine LGU context.
- The literature supports a YOLO-family detector for live video and local edge processing; it does not prove one architecture is best on every Lipa camera.
- Ahmed (83.3%), Li’s YOLOv5n (82.4% mAP@0.50), and Gurusamy (88.7%) contextualize the paper’s 85% target. These values are not all measured under identical conditions.
- ADAS’s 95.6% mAP@0.50 is a qualified validation-split result, not independent operational accuracy.
- The local event-level result is 8/16 overall, 8/10 standard, and 0/6 hard; 3 false positives occurred over 11.0 clean minutes.
- Do not call mAP, precision, recall, and event recall the same “accuracy.”
- The exact runtime confidence of 0.15 is not set by a Chapter 2 citation.
- Human oversight remains necessary; literature warns against automation bias and alert fatigue.
- Use literature to justify why the system was designed this way, and use the tracker to describe what ADAS actually demonstrated.
