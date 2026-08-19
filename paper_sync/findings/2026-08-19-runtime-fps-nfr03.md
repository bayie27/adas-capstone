---
section: NFR-03 Frame Rate Maintenance
page/s: unconfirmed
required_revision: Correct AI engine FPS and capacity behavior
notes: Capacity is standalone; runtime inference FPS drives warnings
status: Not started
assigned_to: Daniboy
synced: false
---

## Where

NFR-03 Frame Rate Maintenance, observed in the live defense document on
2026-08-19.

## OLD

> The edge server shall process connected camera streams at a minimum of 10 to
> 15 frames per second (FPS), minimizing computational overhead while
> maintaining real-time incident detection.

## NEW

The AI engine shall schedule batched inference at a fixed target of 15 frames
per second for all active camera streams. Each active camera shall report its
rolling successful-inference cadence through the existing heartbeat as
measured_fps. After the rolling measurement window is established, a rate
below 10 FPS shall carry the diagnostic INFERENCE_FPS_BELOW_MIN without
changing the production schedule.

## Justification

`ai_engine/pipeline.py:95-103` fixes the target at `config.FPS_BAND_MAX`, and
`ai_engine/pipeline.py:211-225` runs that fixed-period scheduler without a
capacity-based band switch. `ai_engine/camera.py:120-140, 227-261` records the
rolling successful-inference rate and sends `INFERENCE_FPS_BELOW_MIN` below
`FPS_BAND_MIN`.

## Propagation

- Table 10, `measured_fps` definition.
- Table 17, TC-U-301 FPS Downsampling Logic.
- Table 26, TC-AI-402 Target FPS Maintenance.
- Scalability and Performance Considerations.
