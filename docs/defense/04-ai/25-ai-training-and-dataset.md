# 25 — AI Training and Dataset

> **One-liner:** The detector was initialized from COCO-pretrained YOLO26n, trained on a filtered two-class public dataset, and selected by event-level behavior on local clips.
> **Panel risk:** high — the panel can probe non-local accident imagery, the incomplete incident-level split, and why `epoch50.pt` was selected over `best.pt`.

## 1. What it is

The model is the frame-level visual part of the accident pipeline.
It looks at a video image and proposes labeled boxes for either an accident or an ordinary vehicle.
A separate temporal stage combines repeated accident boxes into an event.

The training target is a vehicle-to-vehicle collision event and its immediate aftermath.
The model does not decide on its own that an alert is final.
The event pipeline later filters the boxes and checks whether accident evidence persists.

The final detector is YOLO26n, a nano-sized object detector initialized from COCO-pretrained weights.
The project fine-tuned that starting model for two project classes: `accident` and `vehicle`.
It was chosen to fit the prototype's edge-inference budget, not to claim that YOLO26n is the most accurate possible model.

The final v3 corpus contains public, pre-annotated image sources.
Local Lipa CDRRMO CCTV clips were kept out of training and validation, then used for event-level checkpoint selection and evaluation.
They were held out from training, but the paper states that they are not an untouched post-selection test set.

## 2. Where it lives

### In the paper

- Chapter 3, “Deep Learning Implementation and Training Protocol,” pp. 172–180.
- Table 20, “Dataset Sources, Roles, and Final Composition of the v3 Training Corpus,” p. 173.
- Table 21, “Data Augmentation Configuration and Methodological Purpose,” pp. 176–177.
- Table 22, “YOLO26n Training Configuration and Methodological Purpose,” p. 178.
- The checkpoint-selection procedure is on p. 179.
- The Google Colab training environment is described on p. 169; the full-run Colab T4 detail is on p. 178.
- The prototype inference host is listed separately in Table 23, p. 182.

### In the code

- `ai_engine/config.py:47` sets `epoch50.pt` as the default model artifact.
- `ai_engine/config.py:85` resolves the selected model path and fails if the artifact is missing.
- `ai_engine/config.py:105` defines class `0` as the alertable accident class; class `1` is vehicle.
- `ai_engine/detector.py:28` converts a BGR frame to grayscale and replicates it to three channels.
- `ai_engine/detector.py:167` loads the chosen weights through the YOLO model wrapper.
- `ai_engine/detector.py:188` sends batches through inference; `ai_engine/detector.py:330` keeps only accident-class boxes.
- `ai_engine/main.py:38` resolves the configured artifact before constructing the detector.

The paper is the source for the training data, augmentation, and optimizer schedule.
These code references show how the adopted artifact and class design are used at inference.

## 3. How it works

### Architecture and pretraining

The detector starts from `yolo26n.pt`, which already carries general visual features from COCO pretraining.
The training run adapts those weights to the project's accident and vehicle labels instead of starting from random weights.

YOLO26n's nano-sized model was selected because the system processes live camera frames on prototype hardware.
The paper presents this as a deployment-oriented choice that fits the edge-inference budget.
It does not claim a head-to-head accuracy win over larger architectures.

A detector box is still only frame-level evidence.
The deployed pipeline takes only class `0` boxes into event formation.
The `vehicle` class is not an alert class.

### The two-class label design

The classes are:

| Class ID | Class name | Training meaning                                       | Inference use                     |
| -------- | ---------- | ------------------------------------------------------ | --------------------------------- |
| `0`      | `accident` | Collision and immediate aftermath                      | Eligible to enter event formation |
| `1`      | `vehicle`  | Ordinary traffic that is not itself collision evidence | Discarded before alert formation  |

The vehicle label is a discriminative foil.
It gives the detector a positive label for ordinary vehicles rather than making vehicles in normal traffic part of the accident class.

That matters because vehicles are also visible in accident images.
Without an ordinary-vehicle class, the detector could learn an overly broad vehicle-to-accident association.
The paper says the second class reduces the risk of a single-class model firing on normally driving cars.

Class `1` is useful during training, then discarded before the event stage.
The application therefore does not use the model as a vehicle counter.

### Final v3 corpus by source

Table 20 gives the images admitted to the prepared v3 corpus after source filtering, label normalization, and vehicle-quota selection.
These are the prepared-run counts, not totals of every image available in each public source.

| Final v3 source                              | Training role                                 | Images used | Domain contribution or limit                                                                        |
| -------------------------------------------- | --------------------------------------------- | ----------: | --------------------------------------------------------------------------------------------------- |
| Nyanko `vehicle-accident-m2ryw` project fork | Accident source plus some vehicle annotations |       8,664 | The only labeled accident source in the final retrain; heterogeneous and includes non-local imagery |
| BMD-45 `iisc-aim/BMD-45`                     | Vehicle-only ordinary-traffic foil            |       1,687 | Indian traffic, mainly daytime, with no accident labels                                             |
| `traffic-vehicle-detection-e6kgi`            | Vehicle-only Philippine foil                  |         374 | Fixed-camera daytime tricycle and motorcycle coverage                                               |
| `vehicle-5kcdl`                              | Vehicle-only Philippine foil                  |         688 | Jeepney, tricycle, car, and night imagery; limited camera-view diversity                            |
| **Prepared v3 total**                        | —                                             |  **11,413** | —                                                                                                   |

Paper source: Chapter 3, Table 20, p. 173.

Nyanko was the only source of labeled accident imagery in the final retrain.
The other three sources supplied ordinary-traffic vehicle examples.
No Philippine accident imagery was added to the v3 training corpus.

The two Philippine sources add local vehicle appearance, including tricycles and jeepneys.
They do not make the accident examples locally representative.

### Vehicle quota

Vehicle imagery was capped at an **8:1 vehicle-box-to-accident-box ratio**.
This is a ratio of labeled boxes, not images.

The cap was intended to provide ordinary-traffic foil without letting vehicle boxes dominate the training signal.
A box ratio must not be restated as an image ratio.

The v3 allocation gave the BMD-45 and Philippine vehicle sources space inside that existing vehicle budget.
They were not added on top of the 8:1 box cap.

Paper source: Chapter 3, “Dataset Preparation and Quality Controls,” p. 175.

### Dataset split and local clips

The team attempted an incident-level split to keep near-duplicate frames from one crash together.
That safeguard did not complete for the recorded v3 run.
The accident-source images therefore used the recorded frame-level split.

The vehicle-only sources had no accident events and were not incident-split.
The paper does not provide the final number of images in the training split and validation split, or their split percentages.
Use `[UNSOURCED — verify]` if asked for those counts; do not fill in a familiar split ratio from memory.

The 17 Lipa CDRRMO clips consisted of 16 crash-labeled clips and one declared negative clip.
They were excluded from training and validation.
They were later used for event-level checkpoint selection and evaluation.

That makes them held out from training, but not an untouched post-selection test set.
This wording comes from the paper's training protocol and should be said plainly.

Paper source: Chapter 3, “Dataset Preparation and Quality Controls,” p. 175.

### Dataset preparation and quality controls

Source-specific labels were normalized into the two final classes.
Accident-related labels became `accident`.
Ordinary vehicle labels became `vehicle`.

Negation labels such as `no-accident` were excluded.
This avoids treating a label such as “no accident” as an accident label because its name contains the same word.

The team checked accident images for visible bystander vehicles that had no vehicle boxes.
It added high-confidence vehicle pseudo-labels using a COCO-pretrained YOLO26s model.
Pseudo-boxes overlapping existing accident boxes were excluded.

This was automated label completion on existing images.
The paper says the project team performed no additional manual bounding-box annotation.
The pseudo-label step adds vehicle labels; it does not add new collision images.

### Geometry filter

The preparation removed images whose **largest accident box exceeded 25% of the frame area**.
An image stays only if its largest accident box is at or below that cutoff.

The reason was a framing mismatch.
Close-up accident images can show the accident region filling much of the image.
A fixed CCTV view usually places the relevant vehicles smaller within a wider road scene.

Removing the oversized accident boxes kept the training geometry closer to the object scale seen from fixed cameras.
The paper records the cutoff and rationale, but does not report an ablation showing how another cutoff would perform.

Paper source: Chapter 3, “Dataset Preparation and Quality Controls,” p. 175.
If asked how many images the filter removed, use `[UNSOURCED — verify]`; the defense paper and tracker give the rule, not a removed-image count.

### Grayscale preprocessing

Every training image was converted to grayscale, then the grayscale channel was replicated to three channels.
At inference, each incoming BGR frame received the same conversion and replication before the detector saw it.

This is **preprocessing, not augmentation**.
The transformation makes the training and inference input domains match.

The recorded source characterization described Nyanko as essentially grayscale and BMD-45 as approximately 98% color.
Without a shared grayscale representation, color could become a shortcut for “vehicle” and grayscale a shortcut for “accident.”
That shortcut could make the model miss a collision in color CCTV footage.

The three-channel replication preserves the input shape expected by the COCO-pretrained model.
It does not restore color information; all three channels contain the same grayscale values.

Paper source: Chapter 3, “Preprocessing and Augmentation,” pp. 175–176, and Table 21, pp. 176–177.
Code reference: `ai_engine/detector.py:28`.

### Augmentation

The paper distinguishes grayscale normalization from synthetic image transformations.
Grayscale is applied consistently to training and inference.
The listed augmentations vary the training samples to cover composition, scale, orientation, lighting, and obstruction.

| Operation               | Final setting                              | Purpose recorded in the paper                                                    |
| ----------------------- | ------------------------------------------ | -------------------------------------------------------------------------------- |
| Input size              | `imgsz=640`                                | Match the model's input canvas and prototype compute budget                      |
| Mosaic                  | `mosaic=1.0`; close with `close_mosaic=10` | Vary compositions and object scales, then use ordinary geometry late in training |
| Horizontal flip         | `fliplr=0.5`                               | Add left-right orientation variation                                             |
| Vertical flip           | `flipud=0.0`                               | Disabled because CCTV road scenes keep a meaningful up/down orientation          |
| Rotation                | `degrees=5.0`                              | Represent small camera-mount or alignment deviations                             |
| Translation             | `translate=0.1`                            | Represent modest framing and camera-position variation                           |
| Scale jitter            | `scale=0.9`                                | Vary apparent object size; not a distinct cropping operation                     |
| Brightness/value jitter | `hsv_v=0.4`                                | Perturb lighting and exposure, including glare or night-like conditions          |
| Saturation jitter       | `hsv_s=0.0`                                | Disabled because grayscale inputs have no useful saturation variation            |
| Random erasing          | `erasing=0.4`                              | Introduce partial occlusion or temporary obstruction                             |

Paper source: Chapter 3, Table 21, pp. 176–177.
The table note says this augmentation configuration was reused for the recorded full retraining runs.

### Training configuration and hardware

The final training configuration is listed in Table 22.

| Setting                 | Final value              | What it controls                                                                    |
| ----------------------- | ------------------------ | ----------------------------------------------------------------------------------- |
| Classes                 | 2: `accident`, `vehicle` | Keep collision evidence distinct from ordinary traffic                              |
| Image size              | `imgsz=640`              | Match the model input used by the inference pipeline                                |
| Training batch          | `batch=64`               | Batch used for optimization in the recorded Colab environment                       |
| Maximum epochs          | 60                       | Upper bound for the full retraining schedule                                        |
| Early-stopping patience | 15                       | Stop if the monitored validation signal does not improve within the patience window |
| Random seed             | `seed=0`                 | Record the seed used for training repeatability                                     |
| Data-loader workers     | `workers=2`              | Record the dataset-loading setting                                                  |
| Checkpoint interval     | `save_period=10`         | Save numbered weights for event-level comparison                                    |

The recorded full training runs used Google Colab with a T4 GPU.
That was the training environment, separate from the prototype device used for LAN and pipeline measurements.

The **training batch of 64** is not the TensorRT export profile.
The paper lists export batch `32` separately on p. 179.
Do not use the export profile to answer a training batch question.

Paper source: Chapter 3, Table 22, p. 178, and “Runtime Optimization and TensorRT Export,” p. 179.

The paper does not list every optimizer detail, such as learning rate or weight decay.
If asked for a value that is absent from Tables 21–22, answer `[UNSOURCED — verify]` rather than supplying a default from YOLO documentation.

### Run history across model versions

The current defense paper documents the final v3 corpus and adopted checkpoint.
The test tracker records the v3 checkpoint-selection evidence.

A repo training-run manifest provides the qualitative earlier sequence as supporting context:

- The initial detector baseline used Nyanko for accident and vehicle labels.
- The next full retrain added BMD-45 as ordinary-traffic vehicle foil.
- The final v3 retrain retained Nyanko and added BMD-45 plus the two Philippine vehicle-only sources.
- A v3 smoke run checked the revised data path; it was not a performance run or an adopted model.

Supporting context: `ai_engine/docs/training_docs/training-run-manifest.md:31` and `:36-39`; final v3 composition is authoritative in paper Table 20, p. 173.

The paper and test tracker do not document earlier-run image counts, validation metrics, or exact adoption dates.
Those earlier figures are `[UNSOURCED — verify]` for a panel answer.

### Checkpoint selection

The training configuration saved numbered checkpoints at the paper's `save_period=10` interval.
Each saved checkpoint was then compared with an event-level harness on Lipa CDRRMO clips.
The recorded comparison used event recall and false-positive rate, not validation mAP alone.

The paper gives the reason: the validation mAP came from a frame-level split after the intended incident-level safeguard failed.
That result was not an independent estimate of behavior on deployment footage.

The tracker records that the v3 sweep evaluated eight exported checkpoints.
`epoch50.pt` matched `best.pt` on recall and had three false positives versus five for `best.pt`.
The historical selection record says no fresh checkpoint sweep was run for the later evidence update.

The selected PyTorch checkpoint was `epoch50.pt`.
It was then exported to TensorRT for the prototype runtime.

Paper source: Chapter 3, Table 22 and “Checkpoint Selection,” p. 179.
Tracker source: `ADAS Test Execution.xlsx`, “AI Model Validation,” AI-VAL-005.

## 4. Why it was built this way

### Start from a pretrained nano model

Training from COCO weights gives the detector general visual features to adapt to the project's two classes.
Starting from `yolo26n.pt` also supports a smaller edge-oriented model footprint than a design chosen only for maximum model size.

The paper's rationale is deployment fit.
It does not claim a measured accuracy advantage over every larger model.

### Keep ordinary vehicles as a foil class

Traffic contains vehicles in both normal and crash scenes.
Giving ordinary vehicles their own positive label lets the model learn that a visible vehicle is not automatically an accident.

That choice is reflected at both ends of the pipeline.
Training learns the vehicle boundary.
Inference discards vehicle-class boxes so only accident boxes can enter event formation.

### Use the vehicle sources for local appearance

The accident source is heterogeneous and non-local.
The vehicle-only Philippine sets introduce ordinary local vehicle appearance, especially tricycles and jeepneys, that generic sources do not provide in the same way.

Their role is to help distinguish local normal traffic from accident evidence.
They do not provide local crash examples, so they cannot substitute for local accident training data.

### Cap the vehicle signal

Vehicle examples are useful as negative evidence, but they should not overwhelm the accident class.
The 8:1 cap is calculated over labeled boxes, not the number of images.

That distinction matters because a small number of dense traffic images can contain many vehicle boxes.
The cap controls the relative label signal rather than merely counting source files.

### Match camera geometry

Fixed CCTV footage usually shows a broad scene where vehicles occupy a smaller share of the frame than in close-up crash photos.
The geometry filter removes frames where the largest accident box takes up more than a quarter of the image.

This helps align accident examples with the visual scale of the deployment view.
The exact 25% cutoff is documented; a comparison against alternative cutoffs is not.

### Match grayscale inputs

Nyanko's accident imagery and the vehicle-source imagery differ strongly in color content.
Converting both training images and live frames to grayscale blocks an easy color-based class shortcut.

Repeating grayscale into three channels keeps the pretrained model's three-channel input contract.
It also makes training and inference receive the same kind of image.

### Use augmentations that fit CCTV views

Horizontal flips, small rotations, modest translation, scale jitter, value jitter, mosaic, and erasing introduce controlled variation.
Vertical flips remain off because they reverse the physical orientation of a road scene.
Saturation changes remain off because the input has already been normalized to grayscale.

Mosaic is closed near the end of training so late optimization can use ordinary image geometry for localization.
These are the purposes documented in Table 21, not evidence that every weather or camera condition is covered.

### Select for events, not only boxes

Validation mAP summarizes frame-level box overlap and classification on the validation split.
The application needs camera-level collision events, so the checkpoint comparison ran saved weights through an event-level harness on labeled local clips.

The accident-source split was frame-level because the incident-level safeguard did not complete.
Repeated frames from a crash can therefore make the validation result less independent than an event-level local clip check.

The team selected `epoch50.pt` after comparing event recall and false positives.
The tracker records equal recall to `best.pt` and fewer false positives in that historical sweep.

## 5. What changed since the 28 April defense

The current defense paper now documents the final v3 training recipe: source roles, final source counts, class design, geometry filtering, grayscale preprocessing, augmentations, hyperparameters, and checkpoint-selection method.
The final v3 checkpoint used for export is `epoch50.pt`.

The version sequence in the supporting run manifest explains how the dataset expanded from the earlier baseline to the final v3 mix.
The paper's authoritative final composition is the v3 source table, not the earlier run notes.

The precise model artifact, dataset composition, and checkpoint that the panel saw on 28 April are not stated in the current paper or tracker.
If asked for an exact before-and-after number, use `[UNSOURCED — verify]` until the earlier defense record is checked.

## 6. Limits and honest caveats

- Only Nyanko supplied labeled accident imagery to the final v3 training corpus.
- The accident source was heterogeneous and included non-local imagery.
- The Philippine datasets supply ordinary vehicle examples, not local accident labels.
- The Lipa clips were not used in training or validation, but they were later used for checkpoint selection and evaluation.
- The accident-source split remained frame-level; the intended incident-level safeguard did not complete.
- The defense paper does not give exact training-image and validation-image counts or split percentages.
- The paper records the 25% geometry cutoff but not how many images it removed or an ablation over cutoffs.
- The paper records the main hyperparameters, but not every optimizer setting. Missing settings are `[UNSOURCED — verify]`.
- The tracker reports accident-class mAP@0.50 of 0.956 at epoch 50 as a qualified validation-split result. It is not independent operational detection accuracy.
- The historical checkpoint comparison was not repeated in the later evidence update; describe its 3-versus-5 false-positive comparison as archival selection evidence.
- The paper documents synthetic augmentation, but does not establish whether any original Nyanko images were AI-generated. A non-authoritative repo training note flags filename evidence for generated images; verify the source before making a yes-or-no claim. `[UNSOURCED — verify]`
- The exact v1 and v2 run counts, metrics, and adoption dates are not in the defense paper or test tracker. Do not quote them from memory.

Tracker source for the validation and checkpoint qualifications: `ADAS Test Execution.xlsx`, “AI Model Validation,” AI-VAL-001 and AI-VAL-005.
Supporting source for the generated-image verification lead: `ai_engine/docs/training_docs/training-methodology.md:79` and `:213`.

## 7. Likely panel questions

### “Why not just use the best checkpoint?”

**Answer:** The accident-source validation split was frame-level because the incident-level safeguard did not complete, so validation mAP was not an independent estimate of local event behavior. In the recorded v3 event-level sweep, `epoch50.pt` matched `best.pt` on recall and had three false positives instead of five; that historical comparison drove the selection.

### “Where did your accident images come from?”

**Answer:** The final retrain's accident images came from the public Nyanko vehicle-accident dataset accessed through its recorded Roboflow project fork. It was the only labeled accident source in the final v3 corpus; BMD-45 and both Philippine sources contributed ordinary-vehicle examples.

### “Is your training data representative of Lipa City?”

**Answer:** Not fully. The accident images are heterogeneous and non-local, while the Philippine sources add local vehicle appearances but no local crash labels; we used Lipa footage later for event-level selection and evaluation.

### “Why convert everything to grayscale?”

**Answer:** Nyanko's accident source was essentially grayscale while BMD-45 was about 98% color, so raw color could become a shortcut for the class label. We grayscale both training images and live frames, then replicate the channel three times for the pretrained model's input.

### “How much data is enough?”

**Answer:** There is no universal image count that proves coverage. The final v3 corpus had 11,413 prepared images, but the stronger question is whether it covers the scenes and event types the system must handle; the paper does not give exact train and validation image counts.

### “Did you use synthetic or generated images?”

**Answer:** The paper documents synthetic augmentations such as mosaic, flips, and brightness changes. It does not establish whether original Nyanko images were AI-generated, so that source-provenance detail is `[UNSOURCED — verify]` until checked against the source data.

### “Why have a vehicle class if you throw it away later?”

**Answer:** The vehicle class teaches the detector that ordinary traffic is a labeled non-accident case, rather than leaving every normal vehicle as background. At inference, vehicle boxes are discarded; only accident boxes can enter event formation.

### “Why throw out close-up accident images?”

**Answer:** The largest accident box was filtered when it exceeded 25% of the frame, because fixed CCTV scenes show vehicles smaller within a wider view. The cutoff and rationale are documented, but the paper does not give an ablation for other cutoffs.

### “Was the training and validation split independent by crash?”

**Answer:** No. The team attempted an incident-level safeguard, but it did not complete for the recorded v3 run, so accident-source images used the frame-level split. The tracker therefore treats the recorded mAP result as qualified rather than independent operational accuracy.

### “Did you use the Lipa clips to train the model?”

**Answer:** No. The 17 Lipa clips were excluded from training and validation, then used for event-level checkpoint selection and evaluation. Because those clips informed checkpoint selection, they are not an untouched post-selection test set.

### “Why use COCO-pretrained YOLO26n?”

**Answer:** COCO pretraining supplied general visual features to adapt to the project's accident and vehicle classes. YOLO26n was chosen for a nano-sized architecture that fits the prototype's edge-inference budget, not because the paper claims it beats every larger detector on accuracy.

### “What changed between the model versions?”

**Answer:** The supporting run history describes an early Nyanko-based baseline, then a retrain that added BMD-45 ordinary traffic, and finally v3 with Philippine vehicle-only sources. The defense paper gives the final v3 counts; earlier version counts and metrics are `[UNSOURCED — verify]` in the paper and tracker.

### “Did the team manually draw the pseudo-labels?”

**Answer:** No additional manual bounding-box annotation was performed. A COCO-pretrained YOLO26s model added high-confidence vehicle pseudo-labels to existing accident images when visible bystander vehicles lacked boxes; overlapping pseudo-boxes were removed.

### “Was the training GPU also the deployment hardware?”

**Answer:** No. The recorded full training runs used a Google Colab T4 GPU, while the paper lists the prototype inference host separately in Table 23. Do not describe the training GPU as the device that ran the LAN and pipeline measurements.

## 8. Cram summary

- The final detector is COCO-pretrained YOLO26n, fine-tuned for `accident` class `0` and `vehicle` class `1`.
- Vehicle is a training foil; only accident boxes survive the inference class filter.
- Final v3 prepared corpus: 11,413 images — Nyanko 8,664; BMD-45 1,687; `e6kgi` 374; `5kcdl` 688.
- Nyanko was the only labeled accident source; the other three datasets were vehicle-only. No Philippine accident imagery was added.
- Vehicle labels were capped at an 8:1 box ratio, not an image ratio.
- Images with a largest accident box over 25% of the frame were removed to better match the smaller objects in fixed CCTV views.
- Grayscale is preprocessing applied to training and inference, then replicated to three channels. It is not an augmentation.
- Training settings: image size 640, batch 64, maximum 60 epochs, patience 15, seed 0, workers 2, save every 10 epochs; full runs used a Colab T4.
- The v3 accident-source split was frame-level. Lipa clips were excluded from training and validation, but used for checkpoint selection and evaluation.
- The tracker records a qualified validation accident mAP@0.50 of 0.956 and a historical sweep where `epoch50.pt` matched `best.pt` recall with three rather than five false positives.
- `epoch50.pt` is the adopted checkpoint; do not call the validation score independent operational accuracy or the Lipa clips an untouched post-selection test set.
- Exact split counts, earlier-run counts and metrics, and AI-generated source-image provenance: `[UNSOURCED — verify]`.
