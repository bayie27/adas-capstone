# MFA implementation validation and evidence

**Status:** Automated P1–P4 evidence is reused from the recorded package commits. P5 required full gate and one-laptop help/restore evidence passed. A local simulated full-stack restore reached fresh AI heartbeat and explicit CLI completion in 13.193 seconds, under the 60-second target for this run. Physical authenticator, second-client LAN/TLS, and independent offline-escrow checks remain not run.

**P5 branch:** `docs/mfa-validation-operations` from merged P4 `38a5c5d`.
**P4 code tree:** `d39f0ba12d0d1dc7e855ecac522c3ad0b65587d4` (P4 branch commit
`598049a84e4fe20732a0feeec5b35658b469b783`; identical tree to merged main
`38a5c5d0d9d2a3abeae6df2470b52e76e1bf4ba8`).
**P5 full gate commit:** `8d4ccfda5ba332f8ec6ec5e54752ebefd6e6c1ef`.

## Environment and scope

The P5 scoped checks and one-laptop restore/rollback exercises ran on Windows build
`10.0.26200.0`, Python 3.12.13, Node 22.23.1, and pnpm 11.17.0. Databases, accounts,
factors, backup artifacts, and the stable test key were disposable. The restore
exercises used unique directories under `var/tmp`; they removed their databases and
key files after writing safe metadata to
[`var/test-evidence/mfa-p5-one-laptop-e0bd670e26.json`](../../var/test-evidence/mfa-p5-one-laptop-e0bd670e26.json).
The fresh-process check is recorded in
[`var/test-evidence/mfa-p5-loopback-76edf34f0d.json`](../../var/test-evidence/mfa-p5-loopback-76edf34f0d.json).
These ignored JSON files contain no code, seed, key, token, or account password.

The P5 exercise ran on one laptop with a disposable database and key. A temporary copy
of the MediaMTX config used loopback RTSP port 18554 because Windows denied binding the
default port 8554; the repository config was unchanged. The restarted frontend,
backend, MediaMTX simulator, and AI engine confirmed fresh backend readiness and an AI
heartbeat. This does not prove a physical authenticator's storage/cloud-sync policy,
second-client LAN/TLS, or independent protected-device custody. No physical phone,
second LAN client, or separate backup device was used.

## Reused P1–P4 evidence

The P4 merge tree is identical to the tree on which the recorded P4 full gate passed,
so those results are reused instead of repeating the same code suites for this report.

| Matrix rows      | Evidence source                                    | Recorded result and qualification                                                                                                                                                      |
| ---------------- | -------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| F01–F08, G01–G03 | [P1 completion](../plans/mfa/02_PKG_foundation.md) | Focused crypto/migration/config/harness checks and disposable Chromium login passed; P1 `pnpm full:check` passed on its recorded commit.                                               |
| B01–B13, C01–C05 | [P2 completion](../plans/mfa/03_PKG_backend.md)    | Service/API/limiter/audit/concurrency assertions are mapped row by row; P2 full gate passed with recorded test defaults and two xdist workers.                                         |
| U01–U08          | [P3 completion](../plans/mfa/04_PKG_frontend.md)   | Adapter/component/provider behavior and P3's existing-flow regressions passed; P3 full gate passed.                                                                                    |
| X01–X10, R01–R06 | [P4 completion](../plans/mfa/05_PKG_cutover.md)    | P4 full gate passed: backend 1,375 passed/5 skipped, frontend 395 passed, build passed, Chromium E2E 6/6. R01–R05 were test evidence; R06 still lacked an operational escrow exercise. |

The earlier notes contain the actual selectors and assertion descriptions for each
row. P5 does not rewrite their historical results. P4's six isolated browser cases
covered ordinary enrollment/login, recovery and re-enrollment, replacement through
sign-out/socket close, recovery-code rotation and invalidation, wrong-code countdown,
and an RFC 6238 vector. The run used disposable accounts, a unique DB/key, and no
secret-bearing screenshots, traces, video, or error attachments.

## P5 scoped commands and results

| Command / exercise                                                                                                                                       | Result                                         | Evidence and limits                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| -------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `uv run python -m pytest backend/tests/test_help.py backend/tests/test_mfa_restore.py -q --basetemp var/tmp/p5-pytest-e5635ca168e94202b49d5d18cded9e4a9` | **Exit 0 — 40 passed**                         | Help parsing/role visibility plus current-head restore, candidate rejection, pre-MFA refusal, emergency rollback, and the new consumed-code resurrection assertion. One existing Passlib deprecation and SQLite expression-index reflection warnings.                                                                                                                                                                                                                                                                                                                                                                                             |
| `P5-1L-RESTORE-ESCROW-01`                                                                                                                                | **Passed for the isolated local assertions**   | Safe run record: [mfa-p5-one-laptop-e0bd670e26.json](../../var/test-evidence/mfa-p5-one-laptop-e0bd670e26.json). Correct key was read from an ACL-restricted file outside the backup set; key bytes were absent from the selected DB artifact and manifest; snapshot factor/code state returned; sessions/challenges were invalidated; the consumed recovery code could be used again after restoring its earlier snapshot; emergency rollback invalidated sessions/challenges.                                                                                                                                                                   |
| Restore function timing                                                                                                                                  | **130.31 ms**                                  | Database candidate restore/swap function only, on this laptop and disposable DB. The separate full-stack result below measures service startup, readiness, and a fresh AI heartbeat.                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| Emergency rollback function timing                                                                                                                       | **95.46 ms**                                   | Candidate rollback function only; no application restart or readiness observation.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| `uv run python -m pytest backend/tests/test_mfa_restore.py -q --basetemp var/tmp/p5-rollback-auth-7373e0de8cf942cf9dd06028699e486d`                      | **Exit 0 — 8 passed**                          | The emergency-rollback test now signs a disposable pre-outage session token and asserts the fresh post-rollback authentication dependency rejects it as `AUTH_REVOKED`. Existing missing/malformed/wrong/corrupt-key and old-schema refusal cases passed in the same module.                                                                                                                                                                                                                                                                                                                                                                      |
| `P5-1L-POST-ROLLBACK-AUTH-01`                                                                                                                            | **Passed for the isolated local assertions**   | Safe run record: [mfa-p5-loopback-76edf34f0d.json](../../var/test-evidence/mfa-p5-loopback-76edf34f0d.json). After emergency rollback, a fresh loopback backend process became ready in **4.279 s** and rejected a pre-restore signed session cookie with **401 `AUTH_REVOKED`**. The rollback database and manifest remained intact.                                                                                                                                                                                                                                                                                                             |
| `P5-1L-FULLSTACK-RESTORE-HEARTBEAT`                                                                                                                      | **Passed for this one-laptop simulated stack** | Safe record: [mfa-p5-full-stack-04432d05.json](../../var/test-evidence/mfa-p5-full-stack-04432d05.json). After an offline restore, the post-restart readiness probe returned ready in 0.032 s and confirmed a fresh AI heartbeat within 1.579 s of probe start. The full interval from starting restore through heartbeat and explicit CLI finalization was 13.193 s, under 60 s for this run. The selected backup and manifest remained unchanged; key bytes were absent. The offline CLI required `restore --finalize completed`; the coordinator did not auto-finalize this CLI-started restore. No second client or physical device was used. |
| Restore readiness qualification                                                                                                                          | **Passed for one local simulated run**         | The 13.193-second result includes the offline restore command, service restart, fresh backend readiness, AI heartbeat, and CLI finalization. The 60-second target is met for this one-laptop run only; it does not establish production or a physical-device/LAN drill.                                                                                                                                                                                                                                                                                                                                                                           |
| Local test-key ACL                                                                                                                                       | **Verified on this laptop**                    | The temporary test key file had an ACL restricted to the current user, SYSTEM, and local Administrators. It was removed with the disposable drill directory. This does not prove independent offline escrow or replacement-host custody.                                                                                                                                                                                                                                                                                                                                                                                                          |
| `uv run pytest ...` first scoped attempt                                                                                                                 | **Unavailable before collection**              | The Windows `uv` console-script trampoline could not canonicalize `pytest`; rerunning through `uv run python -m pytest` avoided that wrapper. The first Python-module attempt also hit the sandbox's read-only default pytest temp path; the passing run set `--basetemp` under ignored `var/tmp`.                                                                                                                                                                                                                                                                                                                                                |
| `pnpm full:check` on `8d4ccfda5ba332f8ec6ec5e54752ebefd6e6c1ef`                                                                                          | **Exit 0 — passed**                            | Windows 10.0.26200.0, Python 3.12.13, Node 22.23.1, pnpm 11.17.0. Backend 1,377 passed/5 skipped; frontend 395 passed across 62 files; Ruff format/lint, Prettier, ESLint, and typecheck passed; production build passed; Chromium E2E 6/6 passed. Default sandbox initially denied pnpm workspace realpath; the same gate passed when retried with permitted workspace access. Existing deprecation, reflection, Vite-config, and jsdom media warnings were non-failing.                                                                                                                                                                         |

The one-laptop tests used disposable databases and file-backed test keys. One exercise
confirmed that a fresh backend rejects the signed pre-outage cookie after emergency
rollback. A separate full-stack offline restore confirmed a fresh AI heartbeat after
restarting the local MediaMTX simulator, backend, frontend, and AI engine. The CLI
restore state was finalized explicitly only after readiness and heartbeat passed;
this drill did not exercise the Maintenance UI's coordinator-driven auto-finalization.
Missing, malformed, wrong keys, corrupt ciphertext, and pre-MFA schema refusals were
asserted by `test_mfa_restore.py`; each rejection left the disposable primary and
selected backup unchanged. No production or working database was opened or changed.

## Security and route audit

The P4 source and assertion audit found no normal MFA-disable, Administrator MFA-reset,
or password-only session-mint route. `create_session` requires an explicit method;
post-cutover session dependencies reject `password` sessions and require a current
enrolled credential/version for TOTP sessions. The only demo mint is the existing
flag-gated, visibly labeled `demo_impersonation` path, and the P4 tests verify denial
when demo tools are off. Recovery rows contain `code_hash` and consumption metadata,
not plaintext codes; one-time plaintext batches are transient service responses and
frontend memory. Startup and restore require the configured key and validate
ciphertext. The P5 evidence file has no secrets. This conclusion combines source
inspection with the P1–P4 tests and P5 restore assertions; a string search alone is not
treated as proof.

## V01–V05 acceptance

| ID  | Result                                                                       | Evidence / remaining prerequisite                                                                                                                                                                                                                                                                                                                                            |
| --- | ---------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| V01 | **Not run**                                                                  | No physical phone/authenticator was used. QR/manual setup and real device storage/cloud-sync settings require a human-held authenticator. ADAS cannot verify a provider's sync policy.                                                                                                                                                                                       |
| V02 | **Not run**                                                                  | No second LAN client or physical clock check was available. P4 localhost browser E2E is not LAN HTTPS/WSS or real-device evidence.                                                                                                                                                                                                                                           |
| V03 | **Verified**                                                                 | [MFA operations](../operations/MFA.md), role-visible help content, password-reset clarification, setup links, and `test_help.py` cover one-time codes, storing codes away from the phone, next-code waiting, recovery interruption/final-code lockout, replacement versus recovery, stable-key custody, restore snapshot semantics, and no in-app/Admin MFA reset.           |
| V04 | **Draft prepared; page mapping blocked**                                     | Current live paper and trackers were read; local paper finding and validation proposals are prepared. Current live PDF export returned 403. The supplied 246-page PDF snapshot predates MFA and is not used for current page numbers. No Drive writes/comments were made.                                                                                                    |
| V05 | **Scoped gate and one-laptop readiness passed; manual prerequisites remain** | P5 `pnpm full:check` passed on `8d4ccfda5ba332f8ec6ec5e54752ebefd6e6c1ef`: backend 1,377/5 skipped, frontend 395 across 62 files, build passed, Chromium E2E 6/6. The disposable full-stack restore reached explicit CLI completion in 13.193 s with a fresh AI heartbeat. Phone, LAN/TLS, cloud-sync observation, and independent offline escrow remain explicitly not run. |

## Proposed additions to the live validation plan and tracker

These are local proposals only. The live `Capstone Test Execution and Validation
Plan` was read at revision
`AHj4eMSBVIam9BAtmOVWzWC8odNiGqpTR_EzXEgsCTXa3DIvCDKL-x0KQZ5359LmoT6xTylVpbF9SOAmjzAJ_ObLDASgUZxsKyTcg9HoizE`.
Its scope and deliverables include Security Testing and Backup & Recovery Testing but
do not name MFA cases. The live `ADAS Test Execution` Sheet has no MFA rows: Security
Testing ends at `TC-SEC-027` in `A28:J28`, and Backup & Recovery ends at `TC-BR-016`
in `A17:J17`. Proposed rows below append without changing existing IDs or results.

In the live validation Doc, add a separate MFA implementation-validation subsection
under **Security Testing**, and an MFA snapshot/key subsection under **Backup &
Recovery Testing**. State that repository checks use disposable local data and are
separate from the August three-device evaluation. Keep physical-device storage/cloud-sync,
second-client LAN/TLS, and independent offline-custody results `Not run` unless later
observed. Record the 13.193-second one-laptop restore result separately; it is not
production evidence.

| Proposed ID    | Live tracker tab / candidate rows                  | Result to record                  | Acceptance and evidence                                                                                                                                                                                                                                                                                                                                                |
| -------------- | -------------------------------------------------- | --------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| TC-MFA-001–005 | Security Testing, append after row 28 (`A29:J33`)  | Pass, automated/local             | Password-to-TOTP/enrollment, wrong/replayed proof, interrupted recovery and exhaustion, replacement/rotation, and enabled/disabled demo gating. Evidence: P4 service/API/component/E2E tests referenced in the package notes.                                                                                                                                          |
| TC-MFA-006     | Security Testing, row 34 (`A34:J34`)               | Blocked — not run                 | Physical authenticator setup, local storage/cloud-sync policy, device clock, and mobile-width usability. Requires a human-held phone; a browser TOTP is not a substitute.                                                                                                                                                                                              |
| TC-MFA-007     | Security Testing, row 35 (`A35:J35`)               | Blocked — not run                 | HTTPS Secure cookie and WebSocket operation from a second LAN client with verified time sync. Requires the authorized two-device network setup.                                                                                                                                                                                                                        |
| TC-MFA-008     | Backup & Recovery, append after row 17 (`A18:J18`) | Pass, disposable                  | Current-head snapshot restores enrolled/recovery-pending state, invalidates sessions/challenges, and does not mutate the selected backup. Evidence: `test_mfa_restore.py` and `P5-1L-RESTORE-ESCROW-01`.                                                                                                                                                               |
| TC-MFA-009     | Backup & Recovery, row 19 (`A19:J19`)              | Pass, disposable                  | Missing/malformed/wrong key, corrupt ciphertext, and pre-MFA schema are rejected before swap; primary, selected artifact, and manifest remain unchanged. Evidence: candidate matrix in `test_mfa_restore.py`.                                                                                                                                                          |
| TC-MFA-010     | Backup & Recovery, row 20 (`A20:J20`)              | Blocked — physical escrow not run | Local restricted-file key retrieval, key exclusion from backup/manifest, consumed-code resurrection, and emergency invalidation passed. A separate disposable full-stack restore was explicitly finalized after a fresh AI heartbeat; restore-to-completion took 13.193 s on one laptop. This does not prove independent offline custody or replacement-host recovery. |

The current Sheet grids end at rows 28 and 17 respectively; the proposed appends need
the grid extended. No rows were added. Existing `TC-BR-014` retains its prior live
57.04-second restore observation. P5's 13.193-second simulated one-laptop result is
additive; it does not replace TC-BR-014 or establish production recovery performance.

## Paper-sync artifacts

The detailed OLD/NEW blocks, redraw requirements, evidence, page-mapping limitation,
and tracker-row conflict are in
[`paper_sync/findings/2026-10-19-mfa-validation-operations.md`](../../paper_sync/findings/2026-10-19-mfa-validation-operations.md).
`paper_sync/TRACKER.md` is generated from the local findings. The native defense Doc,
paper-audit Sheet, validation Doc, and test tracker remain unchanged.
