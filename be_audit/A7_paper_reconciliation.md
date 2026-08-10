# A7 — Paper ↔ implementation reconciliation

Documentation only. No code. The output is a list the writing team can act on directly.

> **Read before starting:** `final_paper_text.txt`, `be_plan/TRACEABILITY.md` (its five-item
> "contract amendments" section), `be_plan/00_INDEX.md`, `be_audit/00_FINDINGS.md`.

## Why this exists

`TRACEABILITY.md` lists **five** paper amendments. A systematic comparison of the paper against the
implemented contract found roughly **twenty-five**. None of the twenty new ones are wrong on the
code side — the code is right and the paper describes an earlier design. But the paper is what the
panel reads, and a Data Dictionary that documents bcrypt against an Argon2id implementation is the
kind of thing that gets found in the room.

**Deliverable: `be_audit/PAPER_AMENDMENTS.md`**, replacing and superseding the five-item list.
Each row: paper location · what it says · what the system does · who fixes it · severity.

---

## Group A — Paper text is stale, the code is correct

The five already on the list:

1. TC-I-202's "ceases frame ingestion" wording.
2. TC-U-205 must acknowledge `source_event_id`.
3. Use Case 5 step 10 says "Closed"; the canonical terminal status is `Resolved` (`Closed` is not
   a status — only the `closed_by_id` / `closed_at` column names survive).
4. Evaluation Scope cites NFR-03 for the 2s alert target (it is **NFR-04**) and NFR-06 for the 15s
   detection-to-dispatch target (it is **NFR-09**).
5. The Data Dictionary has no home for `alarm_settings` (FR-08) or `audit_log` (FR-21).

The twenty found in this audit:

| # | Paper says | System does | Sev |
|---|---|---|---|
| 6 | ERD/Data Dictionary omit `auth_session`, `export_job`, `help_article` (+`help_article_fts`) | Ten tables in `01_CONTRACTS.md` §3; these three are real and load-bearing | Med |
| 7 | `password_hash` is "the bcrypt-hashed password"; Frameworks says "passlib with bcrypt" | **Argon2id**; P2 removed bcrypt entirely. TC-U-201's own wording says "bcrypt/argon2" so the test case survives — the prose does not | **High** |
| 8 | Frameworks names `gputil` for hardware monitoring | **`nvidia-ml-py`**; P5 Step 0 removed GPUtil (it shells out to `nvidia-smi` and last shipped in 2018) | Med |
| 9 | Backups use "the native sqlite3 `.backup` command" | Python `sqlite3.Connection.backup()` API — same guarantee, different mechanism, deliberate in D-011/P7 | Med |
| 10 | `detection_log.snapshot_path`, "the local file path to the saved image", Not Null | `snapshot_key` (a normalized relative key) plus a derived `snapshot_url`; the contract **forbids** ever returning a filesystem path (§1.6) | Med |
| 11 | `camera_name` and `channel_id` are globally `Unique` | **Partial** unique indexes scoped to `is_active = 1`, specifically so a soft-deleted camera's name and channel can be reused | Med |
| 12 | `sys_health_raw` / `sys_health_hourly` have `gpu_usage` and `gpu_temperature` Not Null, no CPU temp, no VRAM; names `hourly_sys_health_id` / `created_at_hour` | Every GPU column nullable (a GPU-less machine must still return 200); adds `cpu_temp`, `gpu_mem_pct_max`, `peak_cpu_temp`, `peak_gpu_temp`, `sample_count`; names `hourly_id` / `hour_start` | Med |
| 13 | FR-15 lists connection status as "**Connecting**" | Everything else in the paper *and* the contract says "**Reconnecting**" — an internal paper inconsistency | Low |
| 14 | **UC-4 step 5**: camera create "executes a network handshake using the constructed URL, verifies stream integrity, and starts an isolated AI inference worker"; 5a flags a failed handshake `Unresponsive` | P4 Step 10 deliberately does the **opposite**: create must **not** block on an RTSP handshake (D-003), and a new camera presents as `Reconnecting` until its first heartbeat | **High** |
| 15 | UC-4 step 4 requires uniqueness of the **constructed RTSP URL** | Uniqueness is enforced on `channel_id`. Functionally equivalent under the current template, but not the same rule | Low |
| 16 | TC-I-304 conflates disabling a camera with setting it "Disconnected" | Connection status is AI-owned observed state; "disabled" must never be inferred from it (D-003/D-009) | Med |
| 17 | UC-11 steps 3–4 promise "a library of available audio options" with preview | One asset exists (`frontend/public/detection_sound.mp3`); `ALARM_SOUND_KEYS` is a one-entry allowlist | Low |
| 18 | TC-R-203 / NFR-06: export ≤5s for a 30-day, ~10,000-row dataset | Re-scoped by owner decision to the real envelope — **~10 incidents/day ⇒ ~300 rows for 30 days**. The 10,000-row measurement is retained as a documented ceiling (see `A6_manual_evidence.md`) | **High** |
| 19 | Restore is "an automated **Linux systemd** pre-start script" | Windows PowerShell orchestrator is the primary path; the systemd units ship reviewed-but-unverified and labelled production-target | Med |
| 20 | The FR table jumps **FR-09 → FR-11** (no FR-10) yet UC-2 cites "FRS-10 auditing purposes" | Numbering hole in the paper; nothing in `be_plan` ever noticed it | Low |

---

## Group B — The paper is right and the project owes it something

| # | Item | State | Action |
|---|---|---|---|
| 21 | **HTTPS/TLS.** Technical Scope: "HTTPS for standard API requests and WebSockets." `be_plan` never mentioned TLS anywhere | **Now genuinely implemented** by `A1_lan_tls_drill.md` | Record the implementation and the self-signed-for-demo caveat. The paper claim becomes true — do not leave it looking aspirational |
| 22 | **NFR-22** — update or replace AI model weights without web-application changes. Appears **nowhere** in `be_plan`; no package claims it, no test case maps to it | Arguably already satisfied: weights live entirely in `ai_engine/`, the backend never references the model, and `RTSP_URL_TEMPLATE` makes the stream source a `.env` change | Add an explicit `TRACEABILITY.md` row with that argument as its evidence. An unclaimed NFR reads as an unmet one |
| 23 | **NFR-12** — learnable within a 15-minute training session. Appears nowhere in `be_plan` | Frontend / UAT-owned | Add a row with a named owner and `pending`, per D-001's rule that no requirement is left unowned |
| 24 | **NFR-13** — 99.9% uptime | No measurement mechanism exists. The endurance run (TC-R-401/402) measures RAM, thermals and VRAM — **not availability** | Either define a measurement or record it as an explicit accepted gap. Do not let the endurance run stand in for it by implication |
| 25 | **FR-03** — "a dynamic search function for querying the user directory" | **The code has it** (`GET /api/users/` supports `search`; `test_users.py::TestGetAllUsers::test_search`). `01_CONTRACTS.md` §5.2's row omits the parameter | Fix the contract doc — this one is documentation lagging code, not the reverse |
| 26 | The Evaluation Scope's **fourth criterion** — "reduction in the notification gap as measured against the fifteen-second detection-to-dispatch target" | No measurement plan anywhere; TRACEABILITY assigns TC-S-103 to "frontend, UAT-style measurement", pending | Name an owner and a method, or record as an accepted gap |

---

## Group C — Repo doc hygiene (F15)

- **`be_plan/00_INDEX.md` P9 row** still reads "🔶 implemented, not pushed/PR'd". P9 merged as
  **PR #70 / `336a967`**. Update the row and its Merged column.
- **The nine-box "Definition of done for the whole effort"** is entirely unchecked, though 7–8 are
  now satisfied. Tick what is genuinely done; leave box 6 (manual procedures) unticked until
  `A6_manual_evidence.md` completes, and box 8 (AI owner's v2 cutover confirmation) until the AI
  owner answers `17_AI_OWNER_OPEN_ITEMS.md`. **Do not tick a box to make the list look finished.**
- **`CONTRIBUTING.md`** claims the backend "hard-fails on startup if any of the **10 keys** are
  missing". Only **three** `Settings` fields have no default: `SECRET_KEY`, `INTERNAL_API_KEY`,
  `DEFAULT_ADMIN_PASSWORD`. Correct the number.
- **`final_paper_text.txt` is untracked** in git despite `00_INDEX.md` listing it as a tier-3
  source of truth and P9's kickoff prompt instructing sessions to read it. Track it.
- `be_plan/12_AI_ENGINE_CONTRACT.md`, `16_HEARTBEAT_VS_POLLING.md` and `17_AI_OWNER_OPEN_ITEMS.md`
  are also untracked. Decide deliberately whether they belong in git — they are handoff docs for
  the AI owner and currently exist only on this machine.

---

## Acceptance criteria

- `be_audit/PAPER_AMENDMENTS.md` exists with all ~26 rows, each carrying an owner and a severity.
- `TRACEABILITY.md`'s amendments section points at it rather than keeping a divergent five-item list.
- New `TRACEABILITY.md` rows exist for NFR-22, NFR-12 and NFR-13 — no requirement left unowned.
- `01_CONTRACTS.md` §5.2 documents the `GET /api/users/` `search` parameter.
- Group C hygiene items all done; nothing ticked that is not true.

## Commits

`docs(planning):` throughout.
