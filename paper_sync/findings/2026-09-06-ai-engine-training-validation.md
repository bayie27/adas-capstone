---
section: System Architecture and Design; Deep Learning Implementation and Training Protocol; AI Model Validation Tracker
page/s: "Final rendered PDF mapping: p. 102 for the AI Engine passage; pp. 173–183 for the Deep Learning Implementation and Training Protocol passage; ADAS_Paper_Audit pp. 12–13 for the TensorRT supersession note"
required_revision: Separate the AI Engine architecture description from the reproducible deep-learning methodology and define the AI validation activities in the test-execution tracker only.
notes: "Applied 2026-09-09 and read back from the live Docs/Sheets targets. Objective 3's existing 85% mAP at IoU >= 0.50 and 25-second collision-to-operator-decision target is preserved by user direction. TensorRT is retained as the deployed prototype runtime artifact; epoch50.pt is its source checkpoint."
status: Applied and verified
assigned_to: Daniboy
synced: 2026-09-09
---

# Application status

This finding records the approved application of the package to the live defense document, ADAS_Paper_Audit, ADAS_Paper_Audit_Tracker, and AI Model Validation sheet. The live Docs/Sheets targets were re-read after each approved write. The validation activities were added to the separate execution tracker only; no validation results were fabricated and no AI-VAL row was inserted into the paper.

Live paper revision after application and pagination cleanup: ANLCKQkIsXfW1ZKNyq7BcyEc7wEQRNxYgnqp-rIqCNtFtXwkFvtv6u7aiRbbVY-zPmAK12IJYHOK4ztxdqMnnPzA-8DYXzsWZtDHPQ2BBUQ
Live audit-document revision after application: ANLCKQlG1qXtULfGIosDnPRoH_Oi9fSqJZ-nSvS7kbwpP5Xh28PIj2zclMr24mxLXIOij40VrocLnyrtvn5X7P42Acbd1kjjnk4vDb4IOQY

Package ID: PS-20260906-AI-ENGINE-TRAINING-VALIDATION

## Changes

### 1. Defense paper — System Architecture and Design, “The AI Engine”

Page/s: p. 102 in the final rendered PDF; native range 137066–138262 after application, tab t.y7ms6bhlk4qn

#### Change metadata

Operation: replace
Scope: logical paragraph
Changed target: the AI Engine paragraph beginning “The AI Engine is the edge component” and ending with the two-endpoint reconciliation protocol introduction
Preserve: the following alert-ingestion, heartbeat, and durable-outbox paragraphs, plus the surrounding heading and formatting
Comment target: the complete replacement paragraph; resolve the native range after the replacement is read back

#### OLD

> The AI Engine. This component ingests RTSP streams with OpenCV, samples the latest frames for batched Ultralytics YOLO inference, and converts them to grayscale replicated across three channels to match the accident training data and prevent color-based classification shortcuts. Because some measured false positives exceeded genuine detection scores, the system uses a deliberately low confidence threshold and relies on temporal accumulation for precision. The accumulator links overlapping detections and builds confidence-weighted evidence over time, firing only after persistence crosses a threshold. The engine then pauses the camera, captures an annotated snapshot, and securely queues the event for backend delivery. This persistence requirement produces a measured alert delay of roughly three seconds. The AI Engine communicated with the backend via a bidirectional two-endpoint reconciliation protocol:

#### NEW

The AI Engine is the component responsible for receiving configured RTSP streams, selecting the latest available frames, and invoking the trained YOLO detector in batches. Each frame is converted to grayscale and replicated across three channels before inference. The detector produces candidate bounding boxes, after which only the accident class is eligible to generate an alert; vehicle detections remain a discriminative class and are not themselves alerted on.

To avoid treating a single-frame detection as a confirmed collision event, the engine applies a per-camera temporal accumulator. The accumulator associates spatially overlapping accident detections across successive frames and builds confidence-weighted evidence until the persistence condition is met. When an event is fired, the engine pauses ingestion for that camera, writes an annotated snapshot to local storage, and persists the event payload in the durable outbox for backend delivery. The exact detector and accumulator configuration is documented in the Deep Learning Implementation and Training Protocol section. The AI Engine communicates with the backend through a bidirectional two-endpoint reconciliation protocol:

#### Evidence

The current paragraph combines component architecture, preprocessing, accumulator behavior, and measured outcomes. The proposed wording preserves the system-level behavior while moving numerical configuration to the methodology section and measured delay to Chapter 4. The following alert-ingestion, heartbeat, and durable-outbox paragraphs remain in the architecture section, where they document system interfaces rather than model training.

#### Proposed comment

Comment scope: logical paragraph; the complete replacement AI Engine paragraph

Previous: The AI Engine. This component ingests RTSP streams with OpenCV, samples the latest frames for batched Ultralytics YOLO inference, and converts them to grayscale replicated across three channels to match the accident training data and prevent color-based classification shortcuts. Because some measured false positives exceeded genuine detection scores, the system uses a deliberately low confidence threshold and relies on temporal accumulation for precision. The accumulator links overlapping detections and builds confidence-weighted evidence over time, firing only after persistence crosses a threshold. The engine then pauses the camera, captures an annotated snapshot, and securely queues the event for backend delivery. This persistence requirement produces a measured alert delay of roughly three seconds. The AI Engine communicated with the backend via a bidirectional two-endpoint reconciliation protocol:

Codex ID: PS-20260906-AI-ENGINE-TRAINING-VALIDATION

Done by Codex.

### 2. Defense paper — Deep Learning Implementation and Training Protocol

Page/s: pp. 173–183 in the final rendered PDF; native range 208203–220772 after application, tab t.y7ms6bhlk4qn

#### Change metadata

Operation: replace
Scope: logical paragraph
Changed target: the complete Deep Learning Implementation and Training Protocol passage supplied in NEW
Preserve: the section heading, surrounding paper content, and formatting; render the dataset-composition pipe table as a native Google Docs table rather than literal pipe-delimited text
Comment target: the replacement methodology passage; resolve the native range after the replacement is read back

#### OLD

> To achieve reliable event-level detection on real deployment footage while remaining light enough for edge inference, the AI model underwent a strict configuration and training pipeline. The implementation is described below in four stages: dataset preparation, architecture selection, training duration and checkpoint selection, and deployment format.
>
> Dataset Preprocessing and Augmentation
>
> The model was trained on a two-class scheme, accident and vehicle, assembled from four Roboflow-hosted sources: a primary collision dataset supplying the accident-class imagery, a large public vehicle-detection dataset of 35,792 images, and two Philippine-specific vehicle datasets totaling 1,464 images and covering jeepneys and tricycles absent from the other sources. Every source arrives pre-annotated by its original creators. Because vehicle images vastly outnumber accident images across these sources, vehicle imagery was capped at an 8:1 ratio against accident boxes, roughly half sourced from the public vehicle dataset, a quarter from the Philippine sources, and the remainder from the accident dataset's own vehicle-only images, to prevent the imbalance from training the model toward silence.
>
> The vehicle class exists only as a discriminative foil: it is never alerted on inference. Without it, a single-class model would entangle "vehicle" and "accident", because nearly every accident image also contains vehicles, and will degenerate into a vehicle detector that fires on a normally-driving car. The accident-source data was split by collision incident rather than by frame, holding out entire incidents for validation so that near-duplicate frames of the same crash cannot leak between the two sets; the vehicle-only foil sources, which contain no accidents, were not incident-split. The 17 archival CCTV clips obtained from the Lipa CDRRMO were reserved exclusively as held-out evaluation footage and were never included in training or validation.
>
> Preprocessing: All images were strictly resized to a 640×640 resolution (imgsz=640) to standardize the input tensor for the YOLO architecture, and converted to grayscale and replicated to three channels before both training and inference. This step is load-bearing rather than cosmetic: the accident-class source is entirely grayscale while the vehicle-class sources are almost entirely colour, so without it the model could learn the shortcut "colour = vehicle, grayscale = accident", which would leave it silent on colour CCTV footage at deployment.
>
> Augmentation Strategy: To improve robustness within the deployment domain, targeted augmentations, unchanged across both training runs, were applied. This included mosaic compositing, horizontal flipping, small-angle rotation (±5°) and translation, scale jitter, and random erasing, alongside randomized brightness adjustment (±40%) to simulate nighttime camera glare. Saturation jitter and vertical flipping were deliberately left disabled: the model trains on grayscale-normalized frames, so saturation jitter is a no-op, and CCTV footage has a fixed up/down orientation that a vertical flip would violate.
>
> Model Architecture Selection
>
> The YOLO26n (Nano) architecture was selected as the foundational object detection model. As established in the literature, deploying heavier, multi-stage deep learning models introduces severe latency bottlenecks. The YOLO26n variant was specifically chosen because it features an ultra-lightweight parameter count. This minimal architectural footprint fits comfortably within a single GPU's VRAM, balancing the high-speed computational requirements necessary for concurrent live RTSP stream ingestion against the accuracy needed to sustain reliable event-level detection on real CCTV footage, rather than against a benchmark mAP score.
>
> Training Duration, Checkpoint Selection, and Deployment Export
>
> The model was trained for up to 60 epochs per run, with early stopping (a patience of 15 epochs without improvement) guarding against overfitting, and a checkpoint saved every 10 epochs. Rather than trusting Ultralytics' own best.pt label or validation mAP, a benchmark score that does not predict event-level behaviour on live CCTV, every saved checkpoint was independently scored against the held-out Lipa CDRRMO clips for event-level recall and false-positive rate. The epoch-50 checkpoint was adopted as the deployed model on this basis, outperforming the run's own best.pt-labelled checkpoint, a result that has held across all three training runs evaluated this way. The deployed weights are loaded directly from this PyTorch checkpoint. A TensorRT engine export is then compiled and deployed as a further inference-speed optimization. The following parameters configure the TensorRT export. Batching is already real and load-bearing in the deployed PyTorch pipeline: all active cameras are grouped into a single inference call per scheduling tick, with per-batch latency measured directly on the prototype hardware.
>
> FP16 Precision (half=True): The model weights were quantized from 32-bit floating-point down to 16-bit. This reduced the VRAM footprint by 50% and significantly accelerated inference speed without a mathematically significant drop in the target mAP.
>
> Dynamic Batching (dynamic=True): Enabled the inference engine to dynamically adjust the input tensor sizes at runtime, preventing memory allocation errors during variable network traffic.
>
> Batch Sizing (batch=32): The TensorRT export was completed at a batch size of 32. This establishes the batch size used for the optimized inference configuration without assuming eventual citywide scale. Extending toward the full 418-camera network would require a larger export batch.
>
> Training Environment
>
> The initial model training, dataset compilation, and weight optimization were executed within a cloud-based Jupyter Notebook environment (Google Colab). This leveraged cloud GPU acceleration for the up-to-60-epoch training cycle before the selected PyTorch checkpoint was pulled down and loaded directly into the AI engine running on the research team's own prototype GPU for Phase 4 LAN stress testing, the hardware every measurement in this document is drawn from.

#### NEW

This section documents the end-to-end methodology used to develop the event-level accident-detection pipeline, from dataset preparation through model training, deployment optimization, and inference-time event formation. It is organized around the design problem addressed by each step: providing accident examples, preventing ordinary vehicles from becoming accident evidence, matching the training and deployment input domains, selecting an edge-suitable model, and converting weak frame-level detections into camera-level events. Comparative performance results are reserved for Chapter 4.

Dataset Sources, Roles, and Final Composition

The final v3 detector used two classes: `accident` (class 0) and `vehicle` (class 1). The final v3 composition contained 11,413 images after source filtering, label normalization, and vehicle-quota selection. These are the images admitted to the prepared v3 corpus, not the public source-pool totals:

| Dataset and identifier                                                                                                                     | Role and contribution                                                                                           | Domain relevance or limitation                                                                                                                                                         | Final images used |
| ------------------------------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------: |
| Nyanko vehicle-accident — original slug `vehicle-accident-m2ryw`; project fork recorded as `enjeys-workspace/vehicle-accident-m2ryw-qqdie` | Accident source plus some vehicle annotations; the only source of labeled accident imagery in the final retrain | Heterogeneous accident source, including non-local imagery; the recorded source was essentially grayscale                                                                              |             8,664 |
| BMD-45 — `iisc-aim/BMD-45`                                                                                                                 | Vehicle-only ordinary-traffic foil                                                                              | Indian traffic; retained as supplementary foil because its road context is reasonably related to Philippine traffic; predominantly daytime and contains no accident labels             |             1,687 |
| `traffic-vehicle-detection-e6kgi` — `vehicle-counting-capstone/traffic-vehicle-detection-e6kgi`                                            | Vehicle-only Philippine foil                                                                                    | Fixed-camera, tricycle- and motorcycle-oriented daytime coverage; adds local vehicle appearance                                                                                        |               374 |
| `vehicle-5kcdl` — `kent-rafiel/vehicle-5kcdl`                                                                                              | Vehicle-only Philippine foil                                                                                    | Contributes Philippine jeepney, tricycle, and car imagery, including nighttime scenes, to represent normal local traffic; the source is concentrated around a limited camera viewpoint |               688 |
| **Total**                                                                                                                                  | **Prepared v3 composition**                                                                                     | —                                                                                                                                                                                      |        **11,413** |

BMD-45 was obtained through Hugging Face, whereas the other source datasets were accessed through Roboflow. The Nyanko source was accessed through the recorded project-workspace fork and then prepared for training through filtering, label normalization, grayscale conversion, pseudo-labeling, and quota selection. BMD-45 and the two Philippine datasets were not intended to supply accident examples. They were included as ordinary-traffic foil so that normal vehicles, especially Philippine jeepneys and tricycles, would not be treated as evidence of an accident. No Philippine accident imagery was added.

Dataset Preparation and Quality Controls

Source-specific labels were normalized into the two final classes. Accident-related labels became `accident`, ordinary vehicle labels became `vehicle`, and negation labels such as `no-accident` were excluded instead of being matched by a naive substring rule. The `vehicle` class was retained as a discriminative foil: it gives ordinary vehicles a positive non-accident label, while vehicle detections are discarded before alert formation. This reduces the risk that a single-class detector will confuse the vehicles present in accident scenes with the accident class itself.

The preparation pipeline also applied a geometry filter to remove images whose largest accident box exceeded 25% of the frame. This addressed the mismatch between close-up accident imagery and the smaller objects normally seen from a fixed CCTV viewpoint. A co-occurrence check found that some Nyanko accident images lacked boxes for visible bystander vehicles. To reduce that label gap, the preparation added high-confidence vehicle pseudo-labels using a COCO-pretrained YOLO26s model and excluded pseudo-boxes overlapping existing accident boxes. This was automated label completion; no additional manual bounding-box annotation was performed by the project team.

Vehicle imagery was capped at an 8:1 vehicle-box-to-accident-box ratio. The ratio refers to labeled boxes, not image counts. It was chosen to provide enough ordinary-traffic foil without allowing vehicle examples to dominate the training signal and push the detector toward predicting `vehicle` everywhere and `accident` nowhere. The v3 allocation reserved space for BMD-45 and the Philippine sources within this existing vehicle budget rather than appending them on top of it.

An incident-level split was attempted as a safeguard against near-duplicate collision frames. The safeguard did not complete for the recorded v3 run, so the accident-source data used the recorded frame-level split. The vehicle-only sources contained no accident events and were not incident-split. The 17 Lipa CDRRMO CCTV clips, 16 crash-labelled clips and one declared negative clip, were excluded from training and validation. They were later used for event-level checkpoint selection and evaluation; therefore, they are held out from training but are not an untouched post-selection test set.

Preprocessing and Augmentation

Every training image was converted to grayscale and the grayscale channel was replicated to three channels during dataset preparation. During inference, each incoming BGR frame underwent the same grayscale conversion and three-channel replication before model inference. This was a domain-control decision rather than a visual-style choice: the recorded source characterization described Nyanko as entirely grayscale and BMD-45 as approximately 98% color. Without a common grayscale representation, the model could learn the shortcut “color means vehicle, grayscale means accident,” which could cause it to miss accidents in color CCTV footage. Replicating the grayscale channel to three channels preserved compatibility with the three-channel input expected by the COCO-pretrained YOLO model. Grayscale conversion is preprocessing, not an augmentation.

| Operation               | Final setting                                                            | Methodological purpose                                                                                                                                                   |
| ----------------------- | ------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Input size              | `imgsz=640`                                                              | Establishes the model input canvas and keeps the computation suitable for the prototype; it does not imply that every source image originally had a 640×640 aspect ratio |
| Grayscale normalization | BGR to grayscale, then replicate to three channels                       | Prevents a color-versus-grayscale class shortcut while preserving the model's three-channel input contract                                                               |
| Mosaic                  | `mosaic=1.0`; disabled during the final 10 epochs with `close_mosaic=10` | Exposes the model to varied image compositions and object scales, then lets late training use ordinary image geometry for more stable localization                       |
| Horizontal flip         | `fliplr=0.5`                                                             | Adds left-right orientation variation without violating the meaning of a road scene                                                                                      |
| Vertical flip           | `flipud=0.0`                                                             | Disabled because fixed-camera CCTV scenes preserve a physically meaningful up/down orientation                                                                           |
| Rotation                | `degrees=5.0`                                                            | Represents small camera-mount or alignment deviations rather than arbitrary viewpoints                                                                                   |
| Translation             | `translate=0.1`                                                          | Represents modest framing and camera-position variation                                                                                                                  |
| Scale jitter            | `scale=0.9`                                                              | Varies apparent object size; this is not a distinct cropping operation                                                                                                   |
| Brightness/value jitter | `hsv_v=0.4`                                                              | Perturbs illumination and exposure, including conditions resembling glare or nighttime footage                                                                           |
| Saturation jitter       | `hsv_s=0.0`                                                              | Explicitly disabled because the normalized inputs are grayscale, making saturation variation ineffective                                                                 |
| Random erasing          | `erasing=0.4`                                                            | Introduces partial occlusion or temporary obstruction of image regions                                                                                                   |

This augmentation configuration was reused for the recorded full retraining runs.

Model Architecture and Training Configuration

The detector was initialized from the COCO-pretrained `yolo26n.pt` model rather than trained from scratch, allowing the project to start from general visual features while adapting the detector to the two project classes. YOLO26n was selected because its nano-sized architecture is compatible with the prototype's edge-inference budget and concurrent batched processing of live RTSP streams. This is a deployment-oriented design decision, not a claim of superior accuracy.

Training and dataset compilation were performed in Google Colab using cloud GPU acceleration; the recorded full runs used a Colab T4, separate from the prototype device used for LAN and pipeline measurements. The principal training settings and their purposes were:

| Setting                 | Final value              | Methodological purpose                                                                                                            |
| ----------------------- | ------------------------ | --------------------------------------------------------------------------------------------------------------------------------- |
| Classes                 | 2: `accident`, `vehicle` | Preserve accident evidence while giving ordinary vehicles a non-accident class                                                    |
| Image size              | `imgsz=640`              | Match the model input used by the inference pipeline within the prototype compute budget                                          |
| Training batch          | `batch=64`               | Provide efficient batched optimization in the recorded Colab environment; this is distinct from the TensorRT export profile of 32 |
| Maximum epochs          | 60                       | Provide a fixed upper bound for the full retraining schedule                                                                      |
| Early-stopping patience | 15                       | Stop a run after the monitored validation signal shows no improvement for the configured patience window                          |
| Random seed             | `seed=0`                 | Record the seed used for repeatability of the training procedure                                                                  |
| Data-loader workers     | `workers=2`              | Record the execution setting used to load the prepared dataset                                                                    |
| Checkpoint interval     | `save_period=10`         | Produce numbered checkpoints for event-level comparison rather than relying only on `best.pt`                                     |

Checkpoint Selection

Each saved checkpoint was evaluated with the event-level harness and compared using event recall and false-positive rate on the Lipa CDRRMO clips. This selection procedure was used because validation mAP came from a frame-level split that did not complete the intended incident-level safeguard and therefore is not an independent estimate of deployment behavior. The final checkpoint choice and comparative measurements are reported in Chapter 4; this section records only the procedure and the source checkpoint used to produce the deployed TensorRT engine: `epoch50.pt`.

Runtime Optimization and TensorRT Export

After training, the selected PyTorch checkpoint was exported and compiled into a TensorRT engine. The resulting TensorRT engine was deployed on the prototype device and used for all recorded LAN and pipeline measurements. The following confirmed parameters describe the TensorRT export:

- FP16 precision (half=True): Converts model weights and computations from 32-bit to 16-bit floating point to reduce memory use and potentially improve inference speed on compatible hardware.
- Dynamic input support (dynamic=True): Allows the engine to accept supported runtime variation in input dimensions, including batch size, instead of requiring one fixed input shape.
- Export batch profile (batch=32): Defines 32 as the maximum or configured batch dimension for the exported TensorRT optimization profile; it does not claim that 32 cameras were tested simultaneously.
- Input image size (imgsz=640): Sets the YOLO input size to 640 pixels for the exported TensorRT engine.
- Export format (format=engine): Specifies TensorRT engine format as the output format for the export.

Inference and Temporal Event Formation

During inference, the engine invokes the detector with confidence threshold 0.15 and input size 640. The low confidence floor preserves weak frame-level evidence; temporal accumulation supplies the persistence needed to reject isolated noise. Only class-0 `accident` detections enter the event-formation stage because class 1 is the ordinary-vehicle foil and is not alertable. A separate accumulator is maintained per camera so evidence from different video sources cannot be combined into one event.

The accumulator links candidate accident boxes using IoU 0.30, increases evidence by confidence multiplied by elapsed time, applies unmatched-evidence decay of 0.30 multiplied by elapsed time, smooths box coordinates with EMA 0.50, and fires an event when evidence reaches 1.0 confidence-seconds. These choices provide spatial continuity, tolerate brief missed detections, reduce box jitter, and require sustained evidence rather than a single frame. The pipeline does not use a dedicated object tracker; instead, it links overlapping detector boxes through the per-camera temporal accumulator. This bases event formation on spatial-temporal evidence rather than requiring a track identity to survive occlusion, deformation, or identity switches. After an event fires, the engine performs the camera pause, snapshot, and durable-event handoff described in the AI Engine architecture subsection.

#### Evidence

The revised text is based on the executed v3 manifest, the recorded training call, the current detector and accumulator configuration, the current evaluation harness, and the user-confirmed TensorRT deployment on the prototype device. The earlier section conflated source-pool counts with final counts, intended incident splitting with the v3 fallback, and training configuration with results, while it did not clearly identify the TensorRT engine as the runtime used for prototype measurements; the replacement resolves those distinctions.

#### Proposed comment

Comment scope: logical paragraph; the complete replacement methodology passage

Previous (marked, intentionally non-verbatim): [[The source description used four Roboflow-hosted sources and public source-pool totals rather than the final v3 composition.]] [[It stated that incident-level splitting had been completed and that the 17 clips were an untouched evaluation set.]] [[It claimed a 50% VRAM reduction and significant acceleration from FP16, dynamic input adjustment for variable network traffic, and a PyTorch-first deployment path with TensorRT as a further optimization.]]

Codex ID: PS-20260906-AI-ENGINE-TRAINING-VALIDATION

Done by Codex.

### 3. ADAS_Paper_Audit — append a supersession note for the earlier TensorRT entries

Page/s: pp. 12–13 in the final rendered audit PDF; native audit document range 27264–27902, tab t.0; appended after the current AI-related audit entries

#### Change metadata

Operation: insert
Scope: logical paragraph
Changed target: the new TensorRT supersession note appended after the current AI-related audit entries
Preserve: existing audit entries 1.5 and 1.6 and all unrelated audit content
Comment target: the inserted supersession note; resolve the native range after insertion

#### OLD

> N/A — insertion-only. Existing audit entries 1.5 and 1.6 remain unchanged.

#### NEW

The earlier TensorRT retraction was based on the current capstone runtime tree, where the default prototype artifact is loaded directly from epoch50.pt and no engine is built automatically. Subsequent execution evidence confirms that the selected checkpoint was exported and compiled into a TensorRT engine. The engine was deployed on the prototype device and used for the recorded LAN and pipeline measurements, while the PyTorch checkpoint remains the source artifact from which it was produced. The existing 1.5 and 1.6 entries remain historical decisions; this note supersedes their no-export conclusion for the current paper wording.

#### Evidence

The live paper currently claims TensorRT export and deployment. The current repository identifies epoch50.pt as the default/source artifact, while the user has confirmed that the resulting TensorRT engine was deployed on the prototype device and used for the recorded LAN and pipeline measurements. The final wording therefore treats TensorRT as the prototype runtime artifact rather than as a separate-device performance result.

#### Proposed comment (same gate as insertion)

Comment scope: logical paragraph; the inserted TensorRT supersession note

The inserted note records that the earlier no-export conclusion is superseded by the subsequently confirmed TensorRT export and prototype-device use for the recorded LAN and pipeline measurements, without rewriting the historical audit entries.

Previous: N/A

Codex ID: PS-20260906-AI-ENGINE-TRAINING-VALIDATION

Done by Codex.

### 4. ADAS_Paper_Audit_Tracker — new current finding

Target: 🚩 Action Stream!A85:H85; row 85 was re-read blank immediately before insertion

#### Change metadata

Operation: insert
Scope: row
Changed target: the first fully blank row in the named Action Stream tab; current A1 range A85:H85
Preserve: all occupied rows, the existing row formatting and validation, and the Reviewed by cell H85
Comment target: the exact new text in A85:G85 colored orange; no Sheet comment

#### OLD

> No current row for this consolidated AI Engine / Deep Learning section reconciliation.

#### NEW

| Change Type | Section / Chapter | Page Number | Required Revision | Notes | Status | Assigned to | Reviewed by |
| Major | System Architecture and Design — AI Engine; Deep Learning Implementation and Training Protocol | Final rendered PDF p. 102 and pp. 173–183; native ranges 137066–138262 and 208203–220772 | Separate architecture from methodology, correct final dataset and split documentation, retain TensorRT as the deployed prototype runtime artifact, identify epoch50.pt as its source checkpoint, and document the accumulator without duplicating it across sections. | AI validation activities are planned in the separate ADAS Test Execution Tracker and are not inserted into the paper in this package. Supersedes the current no-TensorRT conclusion in historical audit entries 1.5 and 1.6. | For Review | Daniboy | |

#### Evidence

The live Action Stream had occupied content through row 84; row 85 was the first unoccupied row in the immediate pre-write read. The inserted row was read back at A85:H85 with H85 still blank and its owner validation preserved.

#### Formatting fallback (same gate as replacement)

Color all newly inserted non-empty text in A85:G85 orange (`#E67E22`); leave H85 blank and preserve the existing row formatting and validation.

### 5. ADAS Test Execution Tracker — AI Model Validation tab

Target: AI Model Validation!A2:J10. This is a separate execution tracker and is not inserted into the paper.

#### Change metadata

Operation: insert
Scope: row
Changed target: the nine data rows in A2:J10 below the existing header row
Preserve: the existing header row, Result dropdown validation, sheet formatting, and all other occupied cells
Comment target: the exact inserted text in columns A:E and G; no Sheet comment

#### OLD

> Rows A2:J10 are blank below the existing AI Model Validation header.

#### NEW

All proposed rows begin with Date Executed blank, Result set to Not Executed, Actual Result / Notes blank, Evidence Link blank, and Defect / Retest Note blank. The existing Result dropdown and sheet formatting are preserved.

| Test ID | Requirement / Objective | Scenario | Preconditions / Steps | Expected Result / Acceptance | Date Executed | Result | Actual Result / Notes | Evidence Link | Defect / Retest Note |
| AI-VAL-001 | Objective 3; NFR-01 Algorithmic Accuracy | Frame-level detector diagnostic on the recorded model validation split | Freeze epoch50.pt and the final two-class configuration; run mAP at IoU 0.50; record the evaluation split and artifact | Record mAP@0.50 and compare with the existing 85% target. State the frame-level split limitation and do not describe mAP as operational event accuracy. | | Not Executed | | | |
| AI-VAL-002 | Objective 1; Objective 3 supplementary event evidence | Event-level detection on 16 labeled Lipa crash clips | Run the frozen TensorRT-backed end-to-end pipeline on the prototype device; count a hit only inside [onset - 2 seconds, end + 15 seconds] | Record TP/FN per clip and aggregate event recall. | | Not Executed | | | |
| AI-VAL-003 | Objective 1; Objective 3 supplementary event evidence | Standard-versus-hard event evaluation | Use the frozen TensorRT-backed prototype pipeline and the preclassified 10 standard and 6 hard crash clips without retuning | Record recall separately for standard and hard groups. | | Not Executed | | | |
| AI-VAL-004 | Objective 1 supplementary operational evidence | False-positive evaluation on clean footage and the declared negative clip | Run the frozen TensorRT-backed prototype pipeline; count alerts outside all labeled event windows; record clean-footage duration | Record false-positive count and FP/min, including the denominator used. | | Not Executed | | | |
| AI-VAL-005 | Objective 3; NFR-04 Alert Response Time | Accident onset to generated alert | Use the frozen TensorRT-backed prototype pipeline on the same labeled clips and record the annotated first-visible onset and generated alert time | Report median, mean, and available tail delay. Keep this distinct from the 25-second operator-decision target. | | Not Executed | | | |
| AI-VAL-006 | Objective 3; NFR-09 Operational Efficiency | Collision-visible frame to operator Confirm or Dismiss decision | Replay the TensorRT-backed prototype pipeline through the dashboard and record the first visible collision frame and operator decision timestamp | Record each trial and compare the end-to-end interval with the 25-second target. | | Not Executed | | | |
| AI-VAL-007 | Objective 1; real-time pipeline evidence | Prototype TensorRT runtime and batched multi-camera processing | Run the exported TensorRT engine on the prototype device and record batch, FPS, latency, dropped frames, and GPU use | Produce a hardware-specific runtime report; do not infer tested 418-camera capacity. | | Not Executed | | | |
| AI-VAL-008 | Objective 1; runtime optimization evidence | TensorRT export and prototype-runtime verification | Record the export parameters, engine artifact, prototype runtime version, and inference decision consistency using the same deployed TensorRT engine | Record export provenance and measured latency/throughput or decision consistency only where actually tested. | | Not Executed | | | |
| AI-VAL-009 | Objective 1; supplementary false-positive evidence | Publicly sourced normal-driving CCTV-style footage | Later acquire footage with permitted reuse; retain URL, license, retrieval date, viewpoint, duration, and a normal-traffic review; run without retuning | Report clean duration and false alerts separately from the 17-clip baseline. Do not merge it into the baseline or use it for tuning before claiming independent evidence. | | Not Executed | | | |

#### Evidence

The live AI Model Validation tab contained a blank A2:J10 range below its header before application, and its Result column already had the Not Executed / Pass / Fail / Blocked / Retest Required dropdown. The nine approved activities were inserted and read back with Result set to Not Executed; Date Executed, Actual Result / Notes, Evidence Link, and Defect / Retest Note remain blank. The current evaluation harness supplies the baseline clip count, event window, and metric definitions. The normal-driving footage row is intentionally future work and carries no current result.

#### Formatting fallback (same gate as replacement)

Color the newly inserted text runs in A2:E10 and G2:G10 orange (`#E67E22`); leave Date Executed, Actual Result / Notes, Evidence Link, and Defect / Retest Note blank, and preserve the existing Result dropdown and all other sheet formatting.

## No change in this package

- The stale paper Testing and Validation section is not rewritten here.
- No AI-VAL test case or tracker row is inserted into the defense paper.
- No internet footage was searched for, downloaded, or added in this application.
- No code, model artifact, or TensorRT engine is changed.
- No old audit history is deleted.

## Approval / sync ledger

Package ID: PS-20260906-AI-ENGINE-TRAINING-VALIDATION

| Target | Approved scope | Applied/read back | Skipped/pending | Blocked |
| Defense paper | Blocks 1–2 and their attached comments | Yes — text, native tables, bullet list, comments, and final PDF pages verified | None | None |
| ADAS_Paper_Audit plus paper audit tracker | Blocks 3–4 and the Block 3 attached comment | Yes — supersession note, comment, row A85:G85, formatting, validation, and audit PDF pages verified | None | None |
| ADAS Test Execution Tracker | Block 5 rows A2:J10 | Yes — nine rows populated; result dropdown preserved; execution/evidence fields blank | Activities remain Not Executed pending future testing | None |
| Standalone comments | None proposed | No standalone comments | None | None |

Approval source: user message “alright I think I'm satisfied. time to apply 2026-09-06-ai-engine-training-validation.md” — all Blocks 1–5 and their bundled comments/formatting fallbacks approved.

Application completed 2026-09-09 after fresh target reads, revision-guarded Docs writes, bounded Sheets writes, native comment insertion, live read-back, PDF export, page mapping, and visual inspection of the affected paper and audit pages. The test-execution tracker remains separate from the paper-audit tracker and must not be confused with it.
