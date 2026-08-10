# A3 — AI engine contract seam

The seam the owner cares most about: "my backend, the scripts, and its interaction with the
ai_engine." Two changes plus a live re-verification.

> **Read before starting:** `be_plan/01_CONTRACTS.md` §6, `be_plan/15_PKG_ai_engine_integration.md`,
> `be_plan/16_HEARTBEAT_VS_POLLING.md`, `be_audit/00_FINDINGS.md`.
> This pack **does** modify `ai_engine/` only if the live drill exposes a mismatch — otherwise
> backend-only.

---

## F3 — Delete the two clientless v1 camera routes (High)

**Owner decision, already made: delete both.**

PR #67 (`947531e` "remove the legacy v1 poll path", `33b94aa` "report observed state via heartbeat
instead of PATCH") removed the AI engine's callers. Two backend routes remain with no client:

| Route | File | Why it goes |
|---|---|---|
| `GET /api/internal/cameras` | `backend/app/api/routes/internal.py:249` | No caller since PR #67. Also carries a deliberately confusing contract — it reports `desired_ai_state` under the `ai_status` field name. |
| `PATCH /api/internal/cameras/{camera_id}/status` | `backend/app/api/routes/internal.py:273` | **The real problem.** Writes `connection_status` and `ai_status` directly, bypassing `apply_observed()`: no fps sanity check, no `error_message` redaction, no `last_heartbeat_at` stamp. A camera updated this way stays presented as Unresponsive because nothing refreshed its heartbeat clock. |

F3's substance is that `apply_observed()` is documented as **the only writer** of AI-owned observed
columns (D-003 single-writer rule) and this route is a second one that skips every guard the first
one applies.

`POST /api/internal/alert` accepts both v1 and v2 shapes. **Remove the v1 branch** —
Delete also `backend/scripts/seed_alerts_via_api.py`, a live consumer that posts v1-shaped payloads against a
running backend.

### Test fallout

`backend/tests/test_internal.py` — delete or repoint:
- `TestLegacyCameraPoll` (2 tests, incl. `test_ai_status_field_reports_desired_state_not_observed`)
- `TestUpdateCameraStatus` (6 defs / 10 parametrized cases)

Several of those assert behaviour that still matters and must survive against the **heartbeat**
path instead of being deleted with the route:
- rejecting an `ai_status=Active` override while an alert is open (the HITL guard),
- rejecting reports for disabled / inactive cameras,
- broadcasting a `CAMERA_STATUS_UPDATE` on a real change.

Check `test_internal.py::TestHeartbeat` first — some are already covered there. Only port the gaps.

### Also update

- `be_plan/01_CONTRACTS.md` §6.1 — mark the two routes removed, with the date and this pack as the
  reason. Do **not** rewrite history; append.
- Any reference in `backend/README.md` or `CLAUDE.md`.

---

## F9 — Heartbeat request hardening (Med)

`backend/app/schemas/internal.py:33`:

```python
class HeartbeatRequest(SQLModel):
    engine_id: str
    sent_at: datetime
    cameras: list[HeartbeatCameraReport] = []
```

Three gaps, all visible against the care taken one class above (`HeartbeatCameraReport` bounds
`measured_fps`, bounds `inference_latency_ms`, caps `error_message` at 1000 chars and rejects null
bytes in both string fields):

1. **`engine_id`** has no `max_length` and no null-byte validator, and is **accepted and never
   used anywhere**. Add both constraints.
2. **`cameras`** is an unbounded list. A malformed or hostile engine can post an arbitrarily large
   body. Add a `max_length` generous enough for the paper's 418-camera target with headroom.
3. **`sent_at`** is parsed and discarded — no clock-skew detection, even though the response
   already returns `server_time` for exactly that purpose on the client side.

### Edge case 1.18 — two engine instances

`14_EDGE_CASES.md` row 1.18 ("two heartbeats from different engine instances") currently degrades
quietly: both engines get the full authoritative snapshot, both open the same RTSP paths, and the
duplicate detections are absorbed by `ux_detection_open_camera` as 409s. Nothing warns anyone.
`17_AI_OWNER_OPEN_ITEMS.md` §4 flags this as "the kind of thing that happens accidentally during
a demo."

**Make `engine_id` earn its place:** track the last-seen `engine_id` and log a warning when a
second distinct one heartbeats within the staleness window. A warning is sufficient — do not
build a lease or reject the second engine; the backend is not the right place to arbitrate that,
and rejecting could take down a legitimate failover.

If you decide against using it, say so explicitly in a comment on the field rather than leaving it
looking like an oversight.

**Tests:** over-long `engine_id` → 422 · null byte in `engine_id` → 422 · over-length `cameras`
list → 422 · a second `engine_id` logs a warning and still processes normally.

---

## Live seam re-verification

After the changes, with the real stack running (see `A1_lan_tls_drill.md` steps 3–4):

1. Engine starts, heartbeats, dashboard shows `Connected` / `Active` — not `Reconnecting`.
2. Disable a camera in the UI → engine stops that stream within one heartbeat cycle.
3. Change `RTSP_URL_TEMPLATE` in `.env`, restart the backend → the engine picks up the new URL
   with **no engine-side change** (`supervisor.py:79-95` `REAPPLY_CONFIG`, deliberately not gated
   on `config_version`).
4. **The durability drill — the one that matters most** (`15_PKG` Step 8): stop the backend, let
   the engine detect a collision, confirm the JPEG was written and an event is sitting in
   `OUTBOX_DIR` and the camera stayed paused; restart the backend; assert **exactly one** incident
   appears. Then repeat with the *engine* also restarted mid-outage.
5. Kill the engine → every camera presents `Unresponsive` within ~10s.

Record the results in `be_audit/00_FINDINGS.md`. Anything that does not behave as described is a
new finding, not something to adjust the test around.

---

## Acceptance criteria

- Both v1 camera routes gone; no orphaned tests; the behaviours worth keeping are asserted against
  the heartbeat path.
- `apply_observed()` is once again the only writer of observed camera columns — verify by grepping
  for direct assignment to `connection_status` / `ai_status` outside `services/cameras.py`
  (`app/main.py`'s startup reset is the one legitimate exception).
- Heartbeat schema bounded on all three fields; second-engine warning fires.
- `uv run pytest` and `pnpm check` green; live drill steps 1–5 executed and recorded.

## Commits

`feat(internal)!:` for the route removal (breaking, note it in the body) ·
`fix(internal):` for the schema hardening · `docs(planning):` for the contract append.
