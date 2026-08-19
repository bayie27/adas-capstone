---
section: Scalability and Performance Considerations
page/s: unconfirmed
required_revision: Correct AI engine FPS and capacity behavior
notes: Capacity is inference-only; runtime inference FPS drives warnings
status: Not started
assigned_to: Daniboy
synced: false
---

## Where

Scalability and Performance Considerations, Hardware Utilization &
Computational Load Balancing bullet, observed in the live defense document on
2026-08-19.

## OLD

> Hardware Utilization & Computational Load Balancing: To prevent GPU thermal
> throttling, the AI engine limited inference to a hardware-optimized rate of
> 10 to 15 FPS per camera.

## NEW

Hardware Utilization & Runtime Monitoring: The AI engine schedules batched inference at a fixed 15 FPS target. The existing heartbeat reports each active camera’s rolling successful-inference rate; a rate below 10 FPS is surfaced as the diagnostic INFERENCE_FPS_BELOW_MIN without reducing the production schedule. Capacity measurement is an optional inference-only diagnostic that prints a rough estimate and never configures production.

## Justification

`ai_engine/pipeline.py:95-103, 211-225` establishes fixed-15-FPS production
scheduling. `ai_engine/camera.py:227-261` reports the rolling successful
inference rate and diagnostic. `ai_engine/capacity.py:1-7, 84-146` makes
capacity an inference-only diagnostic that starts no streams, writes no report,
and never changes production.

## Propagation

- NFR-03 Frame Rate Maintenance.
- Table 17, TC-U-301 FPS Downsampling Logic.
- Table 26, TC-AI-402 Target FPS Maintenance.
