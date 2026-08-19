---
section: "Table 10, camera"
page/s: unconfirmed
required_revision: Correct AI engine FPS and capacity behavior
notes: Capacity is standalone; runtime inference FPS drives warnings
status: Not started
assigned_to: Daniboy
synced: false
---

## Where

Table 10, `camera.measured_fps`, observed in the live defense document on
2026-08-19.

## OLD

> Real-time stream processing throughput measured in frames per second (FPS) by
> the AI worker.

## NEW

Rolling five-second cadence of successful inference for the active camera,
measured in frames per second and reported by the AI worker in its heartbeat.
The value is unavailable until the rolling measurement window is established;
when it is below 10 FPS, the heartbeat carries INFERENCE_FPS_BELOW_MIN.

## Justification

`ai_engine/camera.py:114-140` starts, retains, and calculates the five-second
successful-inference window. `ai_engine/camera.py:227-261` places that value in
`measured_fps` and sets `INFERENCE_FPS_BELOW_MIN` below the configured minimum.
Decoded FPS is a separate internal reader metric at `ai_engine/camera.py:101-112`.

## Propagation

- AI Engine heartbeat narrative.
- NFR-03 Frame Rate Maintenance.
- Table 26, TC-AI-402 Target FPS Maintenance.
