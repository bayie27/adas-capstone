---
section: "Table 17, TC-U-301"
page/s: unconfirmed
required_revision: Correct AI engine FPS and capacity behavior
notes: Capacity is standalone; runtime inference FPS drives warnings
status: Not started
assigned_to: Daniboy
synced: false
---

## Where

Table 17, TC-U-301 FPS Downsampling Logic expected result, observed in the
live defense document on 2026-08-19.

## OLD

> The utility array slicing correctly drops intermediate frames, outputting
> exactly 10 to 15 frames to match the hardware optimization rule.

## NEW

The inference pipeline schedules one batched inference tick every 1/15 second
and consumes only the newest available frame for each active camera. The test
verifies that the fixed production scheduler does not switch to a capacity-based
10 FPS mode and that successful inference remains separately observable through
the camera heartbeat metric.

## Justification

`ai_engine/pipeline.py:95-103, 211-225` fixes the target period at 15 FPS and
does not contain a capacity-driven scheduler branch. `ai_engine/camera.py:215-225`
defines newest-frame consumption, and `ai_engine/camera.py:227-261` exposes
rolling successful-inference cadence through the heartbeat.

## Propagation

- NFR-03 Frame Rate Maintenance.
- Table 26, TC-AI-402 Target FPS Maintenance.
- Scalability and Performance Considerations.
