# 5 FPS Warning Floor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Align the AI engine's per-camera low-FPS warning and the System Health Processing Speed indicator to a strict below-5-FPS threshold, without changing the fixed 15-FPS scheduler or any paper artifact.

**Architecture:** The AI engine owns the per-camera threshold through `config.FPS_BAND_MIN`; both software and GPU readers already consume it. System Health separately classifies aggregate `avg_fps` in the frontend, so it needs the same threshold and copy updates. No API or schema changes are needed.

**Tech Stack:** Python 3.12, pytest, Ruff, React, TypeScript, Vitest, Testing Library.

**Spec:** This document consolidates the approved Codex conversation scope; paper findings, `paper_sync/TRACKER.md`, and Google Drive are explicitly out of scope.

## Global Constraints

- The scheduler remains fixed at `FPS_BAND_MAX = 15.0`; do not introduce a 5-FPS production scheduling mode.
- “Below 5 FPS” is strict: `measured_fps < 5.0` warns and `measured_fps == 5.0` is healthy.
- Preserve `INFERENCE_FPS_BELOW_MIN` and the existing heartbeat/API response shape.
- Do not edit `paper_sync/`, historical reports, dated design documents, or Google Drive.
- The working tree already has unrelated evaluation artifacts and paper-sync edits. Stage only files named in this plan; never reset, clean, or overwrite existing work.

---

### Task 1: Align the AI engine's per-camera warning threshold

**Files:**

- Modify: `ai_engine/config.py:124-127`
- Modify: `ai_engine/tests/test_config.py:24-27`
- Modify: `ai_engine/tests/test_camera.py:258-275`
- Modify: `ai_engine/tests/test_gpu_camera.py:305-319`
- Modify: `ai_engine/README.md:104-113`

**Interfaces:**

- Consumes: `config.FPS_BAND_MIN`, imported by `CameraStream.observed_state()` and `GpuCameraStream.observed_state()`.
- Produces: unchanged heartbeat fields; low-rate reports use `error_code == "INFERENCE_FPS_BELOW_MIN"` only when the measured rate is below 5.0.

- [ ] **Step 1: Write the failing configuration and CPU-reader boundary tests**

Change the band assertion to the intended value and add a boundary test beside `test_low_inference_rate_uses_existing_heartbeat_error_fields`:

```python
def test_frame_rate_band_matches_the_paper():
    assert config.FPS_BAND_MIN == 5.0
    assert config.FPS_BAND_MAX == 15.0


def test_five_fps_does_not_report_a_low_inference_rate(stream_without_thread, monkeypatch):
    stream_without_thread.connection_status = "Connected"
    stream_without_thread.ai_status = "Active"
    stream_without_thread.start_inference_measurement(now=100.0)
    for index in range(25):
        stream_without_thread.record_inference(now=100.0 + index / 5)
    monkeypatch.setattr(camera.time, "monotonic", lambda: 105.0)

    report = stream_without_thread.observed_state()

    assert report["measured_fps"] == 5.0
    assert report["error_code"] is None
    assert report["error_message"] is None
```

- [ ] **Step 2: Run the tests to verify the expected failure**

Run:

```powershell
uv run pytest ai_engine/tests/test_config.py ai_engine/tests/test_camera.py -q
```

Expected: the config assertion fails because the current minimum is `10.0`; the new boundary test must not be weakened to accommodate that old value.

- [ ] **Step 3: Write the failing GPU-reader boundary test**

Extend the existing GPU low-rate test so it asserts the emitted report, then add an exact-5-FPS case using `_make_stream()` and `record_inference()`:

```python
def test_gpu_reader_treats_five_fps_as_healthy(monkeypatch):
    stream = _make_stream()
    stream.connection_status = "Connected"
    stream.ai_status = "Active"
    stream.start_inference_measurement(now=100.0)
    for index in range(25):
        stream.record_inference(now=100.0 + index / 5)
    monkeypatch.setattr(gpu_camera.time, "monotonic", lambda: 105.0)

    report = stream.observed_state()

    assert report["measured_fps"] == 5.0
    assert report["error_code"] is None
    assert report["error_message"] is None
```

- [ ] **Step 4: Run the GPU test to verify the expected failure**

Run:

```powershell
uv run pytest ai_engine/tests/test_gpu_camera.py -q
```

Expected: the new 5-FPS test fails while the current threshold remains 10.0.

- [ ] **Step 5: Implement the shared threshold change**

In `ai_engine/config.py`, replace only the constant value and revise the adjacent comment to distinguish the fixed 15-FPS target from the 5-FPS warning floor:

```python
FPS_BAND_MIN = 5.0
FPS_BAND_MAX = 15.0
```

Do not change the `< FPS_BAND_MIN` comparisons or the warning code/message construction in either camera module; they already consume the shared constant correctly.

- [ ] **Step 6: Update the active AI-engine documentation**

In the “Runtime FPS and heartbeat health” section of `ai_engine/README.md`, replace the below-10-FPS warning statement with below 5 FPS. Keep the distinction between successful-inference cadence and decoder rate intact.

- [ ] **Step 7: Verify the engine task is green**

Run:

```powershell
uv run pytest ai_engine/tests/test_config.py ai_engine/tests/test_camera.py ai_engine/tests/test_gpu_camera.py -q
uv run ruff check ai_engine/config.py ai_engine/camera.py ai_engine/gpu_camera.py ai_engine/tests/test_config.py ai_engine/tests/test_camera.py ai_engine/tests/test_gpu_camera.py
uv run ruff format --check ai_engine/config.py ai_engine/tests/test_config.py ai_engine/tests/test_camera.py ai_engine/tests/test_gpu_camera.py
```

Expected: all tests pass; Ruff reports no lint or formatting changes required.

- [ ] **Step 8: Commit only the engine task files**

First inspect `git diff --` for only the five files listed in this task. If unrelated files appear in `git status`, leave them unstaged. Then:

```powershell
git add ai_engine/config.py ai_engine/tests/test_config.py ai_engine/tests/test_camera.py ai_engine/tests/test_gpu_camera.py ai_engine/README.md
git commit -m "fix(ai-engine): lower fps warning floor to five"
```

### Task 2: Align System Health’s aggregate Processing Speed presentation

**Files:**

- Modify: `frontend/src/pages/SystemHealth.tsx:130-164,613-627`
- Modify: `frontend/src/pages/SystemHealth.test.tsx:204-222`
- Modify: `frontend/src/pages/HealthMetricsReferenceModal.tsx:39-50`
- Modify: `frontend/src/pages/HealthMetricsReferenceModal.test.tsx:27-36`

**Interfaces:**

- Consumes: unchanged `SystemHealthLiveResponse.avg_fps` aggregate from `GET /api/system-health/live`.
- Produces: unchanged UI structure, with amber Processing Speed only when `avg_fps < 5.0` and matching explanatory copy.

- [ ] **Step 1: Write the failing System Health card tests**

Replace the existing 8.5-FPS warning fixture with a 4.9-FPS warning fixture. Add a success-boundary test at exactly 5.0 FPS that asserts the rendered value and has no amber Processing Speed dot:

```tsx
it("renders a green Processing Speed dot at exactly 5.0 fps", async () => {
  vi.mocked(getSystemHealthLive).mockResolvedValue({
    ...mockLive,
    sample_camera_count: 2,
    avg_inference_latency_ms: 25.0,
    avg_fps: 5.0,
  })
  vi.mocked(getSystemHealthHistory).mockResolvedValue(mockHistory)

  const { container } = renderSystemHealth()

  expect(await screen.findByText("5.0 fps")).toBeInTheDocument()
  expect(container.querySelectorAll(".bg-warning.rounded-full")).toHaveLength(0)
})
```

When asserting dots, keep inference latency in the healthy range so the test isolates Processing Speed.

- [ ] **Step 2: Run the card tests to verify the expected failure**

Run:

```powershell
pnpm --filter frontend test:run -- SystemHealth.test.tsx
```

Expected: the 4.9-FPS warning remains green under the old condition, but the exact-5-FPS green boundary test fails because the current 10-FPS condition still renders amber. The suite therefore fails for the intended threshold change.

- [ ] **Step 3: Write the failing metrics-reference modal expectations**

Change the current expectations to require:

```tsx
expect(screen.getByText("5.0–15.0 fps")).toBeInTheDocument()
expect(screen.getByText("Below 5.0 fps")).toBeInTheDocument()
```

- [ ] **Step 4: Run the modal test to verify the expected failure**

Run:

```powershell
pnpm --filter frontend test:run -- HealthMetricsReferenceModal.test.tsx
```

Expected: it fails because the current modal still renders 10.0–15.0 and “Below 10.0 fps.”

- [ ] **Step 5: Implement the frontend threshold and copy changes**

In `SystemHealth.tsx`:

```tsx
const tone = live.avg_fps < 5.0 ? "warning" : "success"
```

Update the Processing Speed state comment and tooltip to describe `5.0–15.0 fps` as the expected range and `Below 5.0 fps` as the warning condition. Preserve the existing neutral zero-camera and danger stream-error branches.

In `HealthMetricsReferenceModal.tsx`, update only the Processing Speed “Low FPS” and normal-range labels to the same 5.0-FPS threshold. Do not change latency, temperature, storage, or other reference states.

- [ ] **Step 6: Verify the frontend task is green**

Run:

```powershell
pnpm --filter frontend test:run -- SystemHealth.test.tsx HealthMetricsReferenceModal.test.tsx
pnpm --filter frontend lint
pnpm exec prettier --check frontend/src/pages/SystemHealth.tsx frontend/src/pages/SystemHealth.test.tsx frontend/src/pages/HealthMetricsReferenceModal.tsx frontend/src/pages/HealthMetricsReferenceModal.test.tsx
```

Expected: the card, tooltip/reference modal, and boundary behavior all pass without formatting drift.

- [ ] **Step 7: Commit only the frontend task files**

Inspect the task diff and stage only the four named frontend files:

```powershell
git add frontend/src/pages/SystemHealth.tsx frontend/src/pages/SystemHealth.test.tsx frontend/src/pages/HealthMetricsReferenceModal.tsx frontend/src/pages/HealthMetricsReferenceModal.test.tsx
git commit -m "fix(health): align fps warning floor with engine"
```

### Task 3: Final scoped verification and handoff

**Files:**

- Verify only files changed by Tasks 1–2.

**Interfaces:**

- Confirms the shared behavior: runtime heartbeat and System Health both use a strict below-5-FPS warning floor while preserving all existing API contracts.

- [ ] **Step 1: Run the complete focused verification set**

Run:

```powershell
uv run pytest ai_engine/tests/test_config.py ai_engine/tests/test_camera.py ai_engine/tests/test_gpu_camera.py -q
pnpm --filter frontend test:run -- SystemHealth.test.tsx HealthMetricsReferenceModal.test.tsx
uv run ruff check ai_engine/config.py ai_engine/camera.py ai_engine/gpu_camera.py ai_engine/tests/test_config.py ai_engine/tests/test_camera.py ai_engine/tests/test_gpu_camera.py
pnpm exec prettier --check frontend/src/pages/SystemHealth.tsx frontend/src/pages/SystemHealth.test.tsx frontend/src/pages/HealthMetricsReferenceModal.tsx frontend/src/pages/HealthMetricsReferenceModal.test.tsx
git diff --check
```

Expected: every command exits successfully. Do not run the full repository gate solely for this scoped threshold change.

- [ ] **Step 2: Inspect scope before handoff**

Run:

```powershell
git status --short
git log -2 --oneline
```

Confirm that the new commits contain only the named engine/frontend files and that pre-existing evaluation artifacts, paper-sync changes, and local findings remain untouched.

- [ ] **Step 3: Report the handoff result**

State the runtime and UI boundary behavior, the exact checks that passed, the commits created, and that paper/Drive artifacts were intentionally not modified.
