"""Run a reviewed tracker batch and keep portable evidence, without editing Excel."""

import argparse
import json
import platform
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SECURITY = {
    "TC-SEC-001": ["backend/tests/test_tracker_security.py"],
    "TC-SEC-003": [
        "backend/tests/test_auth.py::TestRBAC::test_operator_cannot_access_user_management"
    ],
    "TC-SEC-004": [
        "backend/tests/test_analytics.py::test_operator_cannot_access_admin_only_performance_endpoints",
        "backend/tests/test_exports.py::TestPerformanceReportJobIsAdminOnly",
    ],
    "TC-SEC-008": [
        "backend/tests/test_auth.py::TestRBAC::test_operator_cannot_view_audit_logs"
    ],
    "TC-SEC-012": [
        "backend/tests/test_alerts.py::TestExportAlerts::test_export_alerts_neutralizes_formula_injection"
    ],
    "TC-SEC-013": [
        "backend/tests/test_reports.py::TestHostileAndDegenerateInput::test_formula_injection_camera_name_neutralized_in_pdf_too"
    ],
    "TC-SEC-016": [
        "backend/tests/test_auth.py::TestJWTVerification::test_wrong_signing_key_rejected"
    ],
    "TC-SEC-017": [
        "backend/tests/test_snapshots.py::test_hostile_snapshot_keys_all_rejected"
    ],
    "TC-SEC-018": [
        "backend/tests/test_internal.py::TestInternalAuth::test_internal_routes_require_valid_api_key"
    ],
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch", choices=["security"], default="security")
    parser.add_argument("--case", choices=sorted(SECURITY))
    parser.add_argument("--output", type=Path, default=ROOT / "var/test-evidence")
    args = parser.parse_args()
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    output = args.output.resolve() / stamp
    output.mkdir(parents=True, exist_ok=False)
    build = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    status = subprocess.check_output(["git", "status", "--short"], cwd=ROOT, text=True)
    results = []
    selected = {args.case: SECURITY[args.case]} if args.case else SECURITY
    for case, selectors in selected.items():
        command = [
            sys.executable,
            "-m",
            "pytest",
            "-s",
            "-ra",
            *selectors,
            f"--junitxml={output / (case + '.xml')}",
        ]
        started = datetime.now(UTC)
        run = subprocess.run(
            command,
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        log = output / f"{case}.log"
        log.write_text(run.stdout, encoding="utf-8")
        result = {
            "id": case,
            "selectors": selectors,
            "exit_code": run.returncode,
            "started_utc": started.isoformat(),
            "finished_utc": datetime.now(UTC).isoformat(),
            "log": log.name,
            "method": "isolated backend test runner",
            "limitation": "No browser or deployed two-node evidence. Fixture uses inexpensive Argon2 parameters, so timings are not production authentication benchmarks.",
        }
        results.append(result)
        print(f"{case}: exit={run.returncode} evidence={log}", flush=True)
    report = {
        "build": build,
        "working_tree": status,
        "platform": platform.platform(),
        "python": sys.version,
        "results": results,
        "excluded": [
            "AI Model Validation",
            "Backup & Recovery",
            "TC-SYS-019",
            "TC-SEC-014",
            "TC-SEC-015",
            "TC-SEC-027",
            "TC-PERF-002",
        ],
    }
    (output / "run.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Report: {output / 'run.json'}")
    return int(any(item["exit_code"] != 0 for item in results))


if __name__ == "__main__":
    raise SystemExit(main())
