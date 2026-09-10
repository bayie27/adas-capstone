"""A/B the GPU reader's frame-queue depth, rigorously.

Why this exists: the first attempt at this measurement was invalidated because
each arm was launched a different way, and the launch method turned out to
move measured FPS more than the change under test did. So:

  * every arm is launched by THIS script, identically (same command, same env
    except the one variable, no console window, output redirected to a file)
  * arms alternate A,B,A,B so a drift in machine state shows up as
    disagreement between the two runs of the same arm rather than as a fake win
  * WARMUP_S is discarded -- the engine needs ~90s to reach steady state, and
    sampling inside that window is what produced several bogus readings
  * the engine is this script's own child, so it is stopped by PID (with /T,
    because `uv run` wraps the real python and killing the wrapper alone
    orphans the child)

Reads measured_fps straight from the live DB, which is where the operator
dashboard gets it -- so the number under test is the number that matters.

Run from the repo root:
    uv run python <this> [warmup_s] [sample_s] [reps]
"""

import os
import re
import sqlite3
import statistics
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(r"C:\Users\Dani\OneDrive - dlsl.edu.ph\Desktop\ACADEMICS\adas-capstone")
DB = REPO / "adas.db"
LOGDIR = Path(os.environ.get("AB_LOGDIR", REPO / "var" / "log"))

WARMUP_S = float(sys.argv[1]) if len(sys.argv) > 1 else 120.0
SAMPLE_S = float(sys.argv[2]) if len(sys.argv) > 2 else 240.0
REPS = int(sys.argv[3]) if len(sys.argv) > 3 else 2
SAMPLE_EVERY = float(os.environ.get("AB_SAMPLE_EVERY", "10"))
VAR = os.environ.get("AB_VAR", "AI_GPU_FRAME_QUEUE_DEPTH")
ARMS = [a.strip() for a in os.environ.get("AB_ARMS", "1,3").split(",")]

CAM_Q = """select measured_fps, inference_latency_ms, ai_status, connection_status
           from camera where is_active=1"""


def log(msg):
    print(f"{time.strftime('%H:%M:%S')} {msg}", flush=True)


def stop_engines():
    """Kill any ai_engine process, whoever started it."""
    ps = (
        "Get-CimInstance Win32_Process -Filter \"Name='python.exe' OR Name='uv.exe'\" "
        "| Where-Object { $_.CommandLine -match 'ai_engine' } "
        "| ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
    )
    subprocess.run(
        ["pwsh", "-NoProfile", "-Command", ps], capture_output=True, timeout=60
    )
    time.sleep(6)


def start_engine(depth):
    env = dict(os.environ)
    env["AI_GPU_DECODE"] = "1"
    env["PYTHONUTF8"] = "1"
    env[VAR] = str(depth)
    env["AI_BACKEND_BASE_URL"] = "https://127.0.0.1:8000"
    env["REQUESTS_CA_BUNDLE"] = str(REPO / "certs" / "adas-cert.pem")
    LOGDIR.mkdir(parents=True, exist_ok=True)
    # Deliberately not a context manager: this handle is the child's stdout
    # and must stay open for the engine's whole run, which outlives this
    # function. Closing it here would break the pipe on the first write.
    out = open(  # noqa: SIM115
        LOGDIR / f"ab-engine-{depth}-{int(time.time())}.log", "w"
    )
    proc = subprocess.Popen(
        ["uv", "run", "python", "ai_engine/main.py"],
        cwd=str(REPO),
        env=env,
        stdout=out,
        stderr=subprocess.STDOUT,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    return proc


def kill_tree(proc):
    subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
    time.sleep(5)


def wait_for_cameras(timeout=180):
    """Block until the engine has all its streams up (its own ffmpeg remux
    process per camera is the cheapest reliable signal)."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        out = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq ffmpeg.exe"],
            capture_output=True,
            text=True,
        ).stdout
        if len(re.findall(r"ffmpeg\.exe", out)) >= 20:
            return True
        time.sleep(5)
    return False


def sample(seconds):
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True, timeout=5)
    means, lats, n_active, n_paused = [], [], [], []
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        rows = list(con.execute(CAM_Q))
        act = [r[0] for r in rows if r[2] == "Active" and r[0] is not None]
        lat = [r[1] for r in rows if r[1] is not None]
        n_paused.append(sum(1 for r in rows if r[2] == "Paused"))
        if act:
            means.append(statistics.fmean(act))
            n_active.append(len(act))
        if lat:
            lats.append(lat[0])
        time.sleep(SAMPLE_EVERY)
    con.close()
    return means, lats, n_active, n_paused


def main():
    log(f"A/B {VAR}. warmup={WARMUP_S:.0f}s sample={SAMPLE_S:.0f}s reps={REPS}")
    log(f"arm order: {[a for _ in range(REPS) for a in ARMS]}")
    results = {a: [] for a in ARMS}

    for rep in range(REPS):
        for depth in ARMS:
            log(f"--- rep {rep + 1} arm {VAR}={depth}: restarting engine ---")
            stop_engines()
            proc = start_engine(depth)
            if not wait_for_cameras():
                log("  WARN cameras did not all come up; measuring anyway")
            log(f"  warming up {WARMUP_S:.0f}s (discarded)")
            time.sleep(WARMUP_S)
            log(f"  sampling {SAMPLE_S:.0f}s")
            means, lats, n_active, n_paused = sample(SAMPLE_S)
            kill_tree(proc)
            if means:
                m = statistics.fmean(means)
                results[depth].append(m)
                log(
                    f"  {VAR}={depth} rep={rep + 1}: mean={m:.2f} FPS "
                    f"(min_window={min(means):.2f} max_window={max(means):.2f}, "
                    f"n_samples={len(means)}, active~{statistics.fmean(n_active):.1f}, "
                    f"paused~{statistics.fmean(n_paused):.1f}, "
                    f"lat_median={statistics.median(lats) if lats else float('nan'):.1f}ms)"
                )
            else:
                log(f"  {VAR}={depth} rep={rep + 1}: NO DATA")

    log("=========== RESULT ===========")
    for depth in ARMS:
        vals = results[depth]
        if vals:
            log(
                f"{VAR}={depth}: runs={[f'{v:.2f}' for v in vals]} "
                f"overall_mean={statistics.fmean(vals):.2f} FPS"
            )
    if all(results[a] for a in ARMS):
        base = statistics.fmean(results[ARMS[0]])
        fix = statistics.fmean(results[ARMS[1]])
        log(
            f"{ARMS[1]} / {ARMS[0]} = {fix / base:.2f}x   ({base:.2f} -> {fix:.2f} FPS)"
        )
        spread1 = (
            max(results[ARMS[0]]) - min(results[ARMS[0]])
            if len(results[ARMS[0]]) > 1
            else 0
        )
        spread3 = (
            max(results[ARMS[1]]) - min(results[ARMS[1]])
            if len(results[ARMS[1]]) > 1
            else 0
        )
        log(
            f"within-arm spread: {ARMS[0]}={spread1:.2f} {ARMS[1]}={spread3:.2f} "
            f"-- the effect is only believable if it exceeds these"
        )


if __name__ == "__main__":
    main()
