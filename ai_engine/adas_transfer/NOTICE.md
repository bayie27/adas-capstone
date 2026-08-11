# Attribution and licences

ADAS road-accident detection core — De La Salle Lipa, BSIT capstone, for the Lipa CDRRMO.

This file records every third-party source used to build the detector, its licence, and what was
changed. **CC BY 4.0 requires all three: credit the creator, link the licence, and state that
changes were made.** Several sources here are CC BY 4.0, so this file is an obligation, not a
courtesy.

**It must travel with the model.** Anything that ships `epoch50.pt` — the system repo, a handover
to CDRRMO, a defence submission — is a distribution of work derived from these sources.

---

## ⚠️ Read first: two licence facts that affect deployment, not just credit

### The detector is built on Ultralytics YOLO, which is **AGPL-3.0**

Verified from the installed package metadata (`ultralytics` 8.4.104, `License: AGPL-3.0`).

AGPL-3.0 is a strong copyleft licence, and its distinguishing feature is that it reaches
**network use**: making a modified work available to users over a network can trigger an
obligation to offer the corresponding source. A road-accident alerting system used by CDRRMO staff
over a dashboard is exactly that shape.

Ultralytics also sells a commercial licence for organisations that cannot meet AGPL terms.

**This is a flag, not legal advice, and nobody on this project is qualified to give any.** Raise it
with your adviser before the system is handed over. The likely outcomes are that academic use is
fine, or that the project's own source is disclosed anyway — but it should be a decision, not an
oversight.

### The Lipa CCTV clips are NOT redistributable

`prototype/samples/` holds 17 clips of real road accidents from Lipa City CCTV, supplied for this
project. They carry **no public licence**, they show identifiable vehicles, people and locations,
and several capture injuries.

**Do not publish them, commit them to a public repository, or include them in a public dataset.**
They are gitignored for this reason. They may be copied between this project's own repositories
for testing. Treat any further distribution as needing CDRRMO's explicit permission.

---

## Training data

### Philippine vehicle imagery — `vehicle` class

| | |
|---|---|
| **Source** | `vehicle-counting-capstone/traffic-vehicle-detection-e6kgi` |
| **URL** | https://universe.roboflow.com/vehicle-counting-capstone/traffic-vehicle-detection-e6kgi |
| **Licence** | **CC BY 4.0** — https://creativecommons.org/licenses/by/4.0/ (verified via the Roboflow API) |
| **Used for** | Tricycle imagery for the `vehicle` foil class |
| **Changes made** | Forked; regenerated without static crop and without rotation augmentation; auto-oriented; resized to fit within 640×640; all 7 exported classes collapsed to a single `vehicle` class; converted to grayscale; subsampled to a box budget |

| | |
|---|---|
| **Source** | `kent-rafiel/vehicle-5kcdl` |
| **URL** | https://universe.roboflow.com/kent-rafiel/vehicle-5kcdl |
| **Licence** | **CC BY 4.0** — https://creativecommons.org/licenses/by/4.0/ (verified via the Roboflow API) |
| **Used for** | Jeepney and night-time imagery for the `vehicle` foil class |
| **Changes made** | As above; all 9 classes collapsed to `vehicle` |

### Accident imagery — `accident` class

| | |
|---|---|
| **Source** | `vehicle-accident-m2ryw` (Roboflow Universe), used via a fork in the project workspace |
| **Licence** | ⚠️ **NOT ESTABLISHED.** The Roboflow API returns no licence field for this project, unlike the two above. **Verify on the Universe page and complete this entry before the work is submitted or handed over.** |
| **Used for** | The only source of `accident` class imagery |
| **Changes made** | 22 classes collapsed to `accident` / `vehicle`; negation classes dropped; converted to grayscale; close-up images removed by a geometry filter; vehicle-only images subsampled |

⚠️ **This source is heterogeneous and partly synthetic.** It contains AI-generated crash images
(`Gemini_Generated_Image_*`), Sri Lankan road photographs, and files following PASCAL VOC naming,
plus duplicate images. This does not affect any measured result — every reported number comes from
the Lipa clips, never from this data — but **do not describe it as genuine fixed-CCTV accident
footage.**

### Ordinary traffic — `vehicle` class

| | |
|---|---|
| **Source** | BMD-45, `iisc-aim/BMD-45` on Hugging Face |
| **Licence** | ⚠️ **NOT VERIFIED IN THIS REPOSITORY.** Check the dataset card and complete this entry. |
| **Used for** | Indian street traffic containing no accidents, teaching the model that a scene can correctly produce zero detections |
| **Changes made** | Subsampled to a box budget; all 13 classes mapped to `vehicle`; converted to grayscale; resized to 640 |

---

## Software

| Component | Licence | Notes |
|---|---|---|
| **Ultralytics YOLO** (`ultralytics` ≥ 8.4) | **AGPL-3.0** | The detector architecture and training framework. COCO-pretrained `yolo26n.pt` is the starting checkpoint. See the warning above. |
| PyTorch | BSD-3-Clause | |
| OpenCV (`opencv-python`) | Apache-2.0 | |
| NumPy | BSD-3-Clause | |
| PyYAML | MIT | |

Licences for the four libraries below Ultralytics are the projects' standard terms and are
permissive; verify against the installed versions if an exact statement is needed.

---

## The trained model

`models/weights_v3/epoch50.pt` is a derivative work of the COCO-pretrained Ultralytics checkpoint
and of every dataset listed above. **Any distribution of it carries the obligations of all of
them**, which is why this file exists and why it must travel alongside the weights.

---

## Outstanding — complete before submission

1. **Establish the accident dataset's licence.** It is the single largest contributor to the
   `accident` class and its terms are unknown.
2. **Establish BMD-45's licence** from its Hugging Face dataset card.
3. **Raise the AGPL-3.0 question** with your adviser, in the specific context of handing a
   network-accessible system to a government agency.

*Last updated 2026-08-10.*
