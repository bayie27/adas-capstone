---
section: Technical Scope; Frameworks and Libraries
page/s: "50, 170 (rendered PDF verified 2026-09-14)"
required_revision: Document the optional GPU-resident RTSP input path
notes: Default OpenCV path remains; do not treat PR #226 throughput as deployment evidence
status: Not started
assigned_to: Daniboy
synced: 2026-09-14
---

## Changes

### 1. Defense paper — Technical Scope

Page/s: 50; live Doc range `t.y7ms6bhlk4qn:75403–75518` read back 2026-09-14

#### Change metadata

Operation: replace
Scope: span
Changed target: `with OpenCV for RTSP frame capture`
Preserve: the remainder of the Technical Scope paragraph, including the described local proof-of-concept stack and HTTPS/WSS transport
Comment target: exact NEW span after replacement; resolve native indexes before writing

#### OLD

> Technical Scope: The system uses a client-server architecture designed for local, on-premises edge deployment; the proof-of-concept is evaluated on researcher-controlled test hardware. The server-side stack consists of a custom-trained YOLO object detection model executed via the Ultralytics framework with OpenCV for RTSP frame capture, a FastAPI backend providing REST API and WebSocket endpoints, and a SQLite relational database configured with Write-Ahead Logging (WAL). The client-side consists of a React-based Single Page Application using TypeScript, Zustand for state management, TanStack Query for data fetching, and Recharts for data visualization, styled with Tailwind CSS and reusable custom interface components. Communication between the server and clients uses HTTPS for standard API requests and secure WebSockets for real-time alert delivery.

#### NEW

Technical Scope: The system uses a client-server architecture designed for local, on-premises edge deployment; the proof-of-concept is evaluated on researcher-controlled test hardware. The server-side stack consists of a custom-trained YOLO object detection model executed via the Ultralytics framework with OpenCV as its default RTSP software reader and an opt-in NVIDIA GPU-resident input path for supported hardware, a FastAPI backend providing REST API and WebSocket endpoints, and a SQLite relational database configured with Write-Ahead Logging (WAL). The client-side consists of a React-based Single Page Application using TypeScript, Zustand for state management, TanStack Query for data fetching, and Recharts for data visualization, styled with Tailwind CSS and reusable custom interface components. Communication between the server and clients uses HTTPS for standard API requests and secure WebSockets for real-time alert delivery.

#### Evidence

Live paper identity: `Group7_Capstone Project Defense Document - ITCAPROJ2`, final read-back revision `ANLCKQlUfK7KVo-3ahzxuJnLoFiS1GkM-xVdUXUutGfn1XUcG00thcjd2ZtLbceSYkLp1PUc40G_kX7rebt4g1yF2-TOmxUsq4a3nPkbxQ8`. PR #226 added `GPU_DECODE` in `ai_engine/config.py`; `ai_engine/main.py` selects and validates the GPU path only when enabled, while the unset flag keeps the OpenCV software reader. PR #226 also added `ai_engine/gpu_camera.py`, `ai_engine/gpu_preprocess.py`, and the optional `ai-gpu` dependency group in `pyproject.toml`. The revised passage rendered on PDF page 50.

#### Proposed comment (same gate as replacement)

Comment scope: span; OLD `with OpenCV for RTSP frame capture`; NEW `with OpenCV as its default RTSP software reader and an opt-in NVIDIA GPU-resident input path for supported hardware`

Previous: with OpenCV for RTSP frame capture

Codex ID: PS-20260914-GPU-RESIDENT-DECODE

Done by Codex.

### 2. Defense paper — Frameworks and Libraries, AI Engine Layer

Page/s: 170; live Doc range `t.y7ms6bhlk4qn:204569–205183` read back 2026-09-14

#### Change metadata

Operation: replace
Scope: logical paragraph
Changed target: the AI Engine Layer paragraph
Preserve: the Ultralytics/YOLO description and the rest of the Frameworks and Libraries section
Comment target: the complete revised logical paragraph; resolve native indexes before writing

#### OLD

> AI Engine Layer (Ultralytics, YOLO, & OpenCV): The core collision-detection engine was developed using the Ultralytics framework, which provided an optimized Python environment for deploying the YOLO deep learning model. OpenCV was used to capture, decode, and preprocess RTSP video feeds from the IP cameras before passing the frames to the model for real-time inference.

#### NEW

AI Engine Layer (Ultralytics, YOLO, & OpenCV): The core collision-detection engine was developed using the Ultralytics framework, which provided an optimized Python environment for deploying the YOLO deep learning model. The default software path uses OpenCV to capture, decode, and preprocess RTSP video feeds from the IP cameras before passing the frames to the model for real-time inference. When explicitly enabled on supported NVIDIA hardware, an optional GPU-resident path uses NVDEC decoding and CUDA preprocessing; unavailable prerequisites stop startup rather than silently reverting to the software path.

#### Evidence

PR #226 `ai_engine/main.py` calls `validate_gpu_support()` and `detector.warm_up_gpu()` only when `AI_GPU_DECODE=1`; otherwise it logs the OpenCV/FFmpeg software reader. `ai_engine/gpu_camera.py` implements RTSP-to-NVDEC device-resident frames and fails before camera startup if CUDA, PyNvVideoCodec, or the preprocessing kernel is unavailable. `ai_engine/gpu_preprocess.py` converts NV12 frames to the model input on CUDA. `pyproject.toml` makes `pynvvideocodec==2.2.2` and `nvidia-cuda-runtime-cu12` an additive `ai-gpu` extra. The PR's clip-parity evidence supports functional equivalence, but its live ten-camera A/B ran before the MediaMTX write-queue correction, so no absolute FPS result is proposed for the paper. The revised passage rendered on PDF page 170.

#### Proposed comment (same gate as replacement)

Comment scope: logical paragraph; OLD is the complete paragraph above; NEW is the complete revised paragraph above

Previous (marked, intentionally non-verbatim): AI Engine Layer (Ultralytics, YOLO, & OpenCV): The core collision-detection engine was developed using the Ultralytics framework, which provided an optimized Python environment for deploying the YOLO deep learning model. [[OpenCV was used to capture, decode, and preprocess RTSP video feeds from the IP cameras before passing the frames to the model for real-time inference.]]

Codex ID: PS-20260914-GPU-RESIDENT-DECODE

Done by Codex.

### 3. Tracker Sheet — 🚩 Action Stream, current A86:G86

#### Change metadata

Operation: insert
Scope: row
Changed target: the first fully blank row in `🚩 Action Stream`, currently A86:G86
Preserve: occupied rows 1–85, existing formatting, validation, notes, and manual fields
Comment target: exact changed text colored orange (`#E67E22`); no Sheet comment

#### OLD

> Verified fully blank by `userEnteredValue` scan of `🚩 Action Stream!A1:G99` on 2026-09-14; rows 1–85 are occupied and the sheet's grid extends to row 99.

#### NEW

A86: Major
B86: Technical Scope; Frameworks and Libraries — AI Engine Layer
C86: 50, 170
D86: Document the optional GPU-resident RTSP input path
E86: PR #226 adds NVIDIA NVDEC/CUDA decoding and preprocessing behind AI_GPU_DECODE=1; OpenCV remains default.
F86: Not started
G86: Daniboy

#### Evidence

Live tracker identity: `ADAS_Paper_Audit_Tracker`, spreadsheet `1iTt2K-t9Jyae-lqApCY0PX9N7HXCrKE850pvJLHzfoQ`. A search of `🚩 Action Stream!A1:G99` found no existing `OpenCV`, `preprocess`, `NVDEC`, or PR #226 row; its existing GPU result is the completed telemetry-library item at row 27. The bounded `userEnteredValue` read established A86:G86 as the first fully blank append target. After write, A86:G86 was read back with the planned values and each cell's text color as `#E67E22`.

#### Formatting fallback (same gate as replacement)

Color every newly inserted character in A86:G86 orange (`#E67E22`) using rich-text `textFormatRuns`; preserve all other cell formatting.

## Approval / sync ledger

Package ID: PS-20260914-GPU-RESIDENT-DECODE
Approval source: User instruction “apply this finding” on 2026-09-14; blocks 1–3 and their attached comments/formatting authorized.

| Target              | Approved scope                              | Applied/read back                                                                                           | Skipped/pending | Blocked |
| ------------------- | ------------------------------------------- | ----------------------------------------------------------------------------------------------------------- | --------------- | ------- |
| Defense paper       | blocks 1–2 and their attached comments      | Applied; both exact replacement spans and both anchored comments read back. Rendered PDF pages: 50 and 170. | —               | —       |
| Tracker Sheet       | block 3 and its orange text-format fallback | Applied; A86:G86 values and `#E67E22` text color read back.                                                 | —               | —       |
| Standalone comments | Not applicable                              | —                                                                                                           | —               | —       |
