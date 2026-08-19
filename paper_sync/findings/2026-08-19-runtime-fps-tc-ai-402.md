---
section: "Table 26, TC-AI-402"
page/s: unconfirmed
required_revision: Correct AI engine FPS and capacity behavior
notes: Capacity is standalone; runtime inference FPS drives warnings
status: Not started
assigned_to: Daniboy
synced: false
---

## Where

Table 26, TC-AI-402 Target FPS Maintenance expected result, observed in the
live defense document on 2026-08-19.

## OLD

> System telemetry confirms the AI engine is actively evaluating a steady 10 to
> 15 frames per second, maintaining real-time parity without bottlenecking.

## NEW

System telemetry confirms that the AI engine is scheduled at a fixed 15 FPS
target. After the rolling successful-inference measurement window is
established, telemetry reports each active camera's measured_fps; a value
below 10 FPS carries INFERENCE_FPS_BELOW_MIN so the operator can identify a
runtime shortfall without a capacity-based schedule change.

## Justification

`ai_engine/pipeline.py:95-103, 211-225` uses a fixed 15 FPS scheduler.
`ai_engine/camera.py:114-140, 227-261` defines `measured_fps` as rolling
successful inference and reports the below-minimum diagnostic in the heartbeat.

## Propagation

- NFR-03 Frame Rate Maintenance.
- Table 10, `measured_fps` definition.
- Table 17, TC-U-301 FPS Downsampling Logic.
