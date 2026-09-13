# Testing and validation

Use [CONTRIBUTING.md](../../CONTRIBUTING.md) and [CLAUDE.md](../../CLAUDE.md#verification-policy) for authoritative check commands and lifecycle gates. Run commands from the repository root; use disposable test data.

```powershell
uv run pytest backend/tests/test_alerts.py
pnpm --filter frontend test:run
pnpm --filter frontend typecheck
```

The default Python suite excludes `slow`, `clips` and `gpu` tiers. Explicitly select those only with their required data and hardware. A skipped or unavailable check is not a pass. Preserve meaningful environmental skips and the documented performance expected failure.

## Validation references

- [Test execution and validation plan](test-execution-validation-plan.md)
- [Unit-testing selection and traceability](unit-testing-coverage-review.md)
- [Frontend visual checklist](../../frontend/VISUAL_CHECKLIST.md)
- [End-to-end and screenshot tests](../../e2e/README.md)
- [Backend test fixtures and helpers](../../backend/tests/README.md)
- [AI engine test tiers](../../ai_engine/tests/README.md)
- [AI evaluation](../../ai_engine/eval/README.md)
- [Historical execution evidence](../archive/README.md)

The local validation plan and unit-test selection are dated references, not replacements for the live documents and tracker listed in [CLAUDE.md](../../CLAUDE.md#live-google-drive-resources). Preserve historical results and consult current sources before asserting readiness.

## Operating-system restart checks

Restart scheduling belongs to Windows Scheduled Task `\\ADAS\\DailyRestart` or the systemd maintenance timer. Python unit tests cannot establish those operating-system triggers. Verify them using the deployment procedures on the target machine. In-process backup timezone/DST and scheduler misfire behavior have separate tests in `test_maintenance_schedule.py` and `test_scheduler.py`.
