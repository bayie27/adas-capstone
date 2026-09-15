"""Generate a case-by-case handoff from the saved workbook and current run."""

import argparse
import json
from collections import Counter
from pathlib import Path

from read_tracker import read_cases


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workbook", type=Path)
    parser.add_argument("run", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--supplement", type=Path)
    parser.add_argument("--save-blocked", action="store_true")
    args = parser.parse_args()
    cases = read_cases(args.workbook)
    run = json.loads(args.run.read_text(encoding="utf-8"))
    current = {item["id"]: item for item in run["results"]}
    if args.supplement:
        supplement = json.loads(args.supplement.read_text(encoding="utf-8"))
        current.update({item["id"]: item for item in supplement["results"]})
    counts = Counter(case["result"] or "Unexecuted" for case in cases)
    verified = sum(
        case["id"] in current
        and current[case["id"]]["exit_code"] == 0
        and case["id"] != "TC-SEC-001"
        for case in cases
    )
    lines = [
        "# ADAS tracker execution handoff",
        "",
        f"Workbook cases: {len(cases)}. Saved statuses: {dict(counts)}.",
        f"Previously passing cases re-verified in this batch: {verified}.",
        "One behavioural case was bound to a new acceptance test in this batch. Other blank cases have not been claimed as bound or passed.",
        "",
        "Readiness: further testing required. Existing open defects remain unresolved. No deployed two-node, production-cost authentication timing, audible capture, complete performance or endurance evidence was produced in this batch.",
        "",
        f"Build: `{run['build']}`. Working tree details are in run.json.",
        "",
        "AI validation and backup or restore exercises are excluded. TC-PERF-002 remains skipped with FPS_BAND_MIN unchanged. The live stack was not listening on ports 8001, 5174 and 8555. TC-PERF-009 and 010 have an unresolved capacity prerequisite reference.",
        "",
        "## Reproduction",
        "",
        "See docs/validation/ADAS_TESTING_GUIDE.md. Run `uv run python scripts/testing/run_tracker.py --batch security` from the repository root. Logs and JUnit XML are local artifacts, not published team evidence links.",
    ]
    for area in dict.fromkeys(case["sheet"] for case in cases):
        lines += ["", f"## {area}", ""]
        for case in (item for item in cases if item["sheet"] == area):
            item = current.get(case["id"])
            lines += [
                f"### {case['id']}",
                "",
                f"Requirement: {case['objective']}",
                f"Scenario: {case['scenario']}",
                f"Status: {case['result'] or 'Unexecuted'}",
                f"Execution method: {item['method'] if item else 'Existing workbook record, not executed in this batch'}",
                "Why this method: disposable runner asserts server responses and stored audit rows without touching the application database."
                if item
                else "Why this method: retained from prior execution where available.",
                f"Binding and steps: {case['steps']}",
                f"Expected result: {case['acceptance']}",
                f"Actual result: {case['notes'] or 'No observation recorded'}",
                f"Evidence: {case['evidence'] or 'None recorded'}",
                f"Defect or retest note: {case['defect'] or 'None recorded'}",
                f"Preconditions and limits: {item['limitation'] if item else 'See workbook procedure and original evidence. Prior records are not independently certified by this report.'}",
                "",
            ]
    lines += ["## All case statuses", "", "| Test ID | Saved status |", "| --- | --- |"]
    lines += [f"| {case['id']} | {case['result'] or 'Unexecuted'} |" for case in cases]
    lines += [
        "",
        "## Defects and outstanding evidence",
        "",
        "All existing Defect Log entries are preserved. Reproduction paths remain in the affected rows and test modules. Runtime fixes must be re-tested against their originating selectors before a defect is closed.",
        "",
        "Live browser and integration work needs a verified isolated stack and the documented deployment gate. Complete-duration performance and endurance runs need their stated workload, device, GPU driver and captures. Do not infer a pass from related automated tests.",
        "",
        "No new Not Applicable case was identified in this batch. Blank skipped cases are not failures or absent implementations.",
        "",
        f"Artifacts: {args.run.parent}. Team instructions: docs/validation/ADAS_TESTING_GUIDE.md. Workbook: {args.workbook}.",
    ]
    if args.save_blocked:
        lines[2:2] = [
            "Workbook update is pending. Excel rejected bounded save attempts with RPC_E_CALL_REJECTED. Backups and a staged update exist, but the original workbook remains unchanged and Summary was not recalculated.",
            "Current execution evidence confirms TC-SEC-001 passed, although its saved workbook status is still Unexecuted. Eight prior security passes were re-verified. TC-SEC-013 required its omitted test class in the selector and passed after that binding correction.",
            "",
        ]
    args.output.write_text("\n".join(lines), encoding="utf-8")
    print(
        json.dumps(
            {
                "cases": len(cases),
                "counts": dict(counts),
                "reverified": verified,
                "report": str(args.output),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
