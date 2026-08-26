---
section: Security Requirements — Table 7, NFR-21
page/s: "p. 70; audit Doc p. 21"
required_revision: Add compact audit-detail redaction wording to NFR-21 and correct the audit-note key count
notes: Defense paper NFR-21, audit Doc §2.6, and tracker row 65 were applied and verified on 2026-08-25; Table 14 was already live.
status: Not started
assigned_to: Daniboy
synced: 2026-08-25
---

## Changes

### 1. Defense paper — Table 7, NFR-21 (Audit Trail Integrity)

Page/s: p. 70

#### OLD

> Failed or unauthorized access attempts shall be recorded in an isolated transaction to ensure complete forensic visibility.

#### NEW

Failed or unauthorized access attempts shall be recorded in an isolated transaction to ensure complete forensic visibility, with sensitive audit-detail values redacted before persistence.

#### Evidence

The exact OLD sentence was read from the live native defense Doc through Google Drive MCP on 2026-08-25 and matched against the rendered PDF on p. 70. `backend/app/services/audit.py:16-31` defines 14 banned detail keys; `_redact_detail_value()` at `audit.py:34-48` masks those keys recursively before `record()` persists the row. String values also pass through `redact_text()` at `backend/app/core/redaction.py:36-54`.

#### Direct-edit status

Applied and read back successfully on 2026-08-25 under the defense-paper approval gate.

### 2. ADAS_Paper_Audit — §2.6

Page/s: p. 21

#### OLD

> There is also a 26-action CHECK constraint generated from the same tuple the API's query validation uses, so the two can never drift, and 15 banned detail keys are redacted before any audit row is written.

#### NEW

There is also a 26-action CHECK constraint generated from the same tuple the API's query validation uses, so the two can never drift, and 14 banned detail keys are redacted before any audit row is written.

#### Evidence

The exact OLD sentence was read from the live `ADAS_Paper_Audit` Doc and matched against its rendered PDF on p. 21. The count is 14, not 15: `_BANNED_DETAIL_KEYS` contains the 14 names at `backend/app/services/audit.py:16-31`.

#### Direct-edit status

Applied and read back successfully on 2026-08-25 under the combined audit-Doc and tracker-Sheet approval gate. The surrounding audit citation was preserved.

### 3. Tracker Sheet — `🚩 Action Stream`!A65:H65

Sheet tab/range: `🚩 Action Stream`!A65:H65

#### OLD

| Column         | A — Change Type | B — Section / Chapter | C — Page Number | D — Required Revision                                                                                                         | E — Notes                    | F — Status | G — Assigned to | H — Reviewed by |
| -------------- | --------------- | --------------------- | --------------- | ----------------------------------------------------------------------------------------------------------------------------- | ---------------------------- | ---------- | --------------- | --------------- |
| Existing value | blank           | blank                 | blank           | Document that the audit_log `detail` field is redacted before it is written, not just that it holds "context and state diffs" | Table 14 (Audit Log), NFR-21 | blank      | blank           | blank           |

#### NEW

| Column         | A — Change Type | B — Section / Chapter                   | C — Page Number | D — Required Revision                                                                     | E — Notes                                                                   | F — Status  | G — Assigned to | H — Reviewed by |
| -------------- | --------------- | --------------------------------------- | --------------- | ----------------------------------------------------------------------------------------- | --------------------------------------------------------------------------- | ----------- | --------------- | --------------- |
| Proposed value | Minor           | Security Requirements — Table 7, NFR-21 | 70              | Add compact audit-detail redaction wording to NFR-21 and correct the audit-note key count | ADAS_Paper_Audit §2.6, p. 21; Table 14 `detail`, p. 125, is already current | Not started | Daniboy         | blank           |

#### Evidence

The existing row was read from the live `ADAS_Paper_Audit_Tracker` Sheet at the named tab and range on 2026-08-25. The proposed row keeps the change in the same tracker row while making the paper page and audit-Doc follow-up explicit. The Sheet is targeted by tab and A1 range, not by a page number.

#### Direct-edit status

Updated `🚩 Action Stream`!A65:G65 and verified the full A65:H65 row. The existing H-column blank and cell formatting were preserved.

## Already applied

### Defense paper — Table 14, Audit Log, `detail`

Page/s: p. 125

#### Current live text

> Structured JSON or text providing context and state diffs; a fixed set of sensitive keys (password, token, API key, and similar) is always fully masked before the row is written, and free-text values are independently scanned and redacted for secret-shaped substrings.

#### Status

Already present in the live defense Doc; no replacement is proposed for this site in this run.

#### Evidence

The paragraph was read back from the live native Doc through Google Drive MCP and the same wording was located in the rendered PDF on p. 125. This finding therefore adds the missing NFR-21 wording instead of repeating a Table 14 write that has already landed.

## Standalone comment test (separate approval)

A native Google Docs comment was created and read back successfully on 2026-08-25 under the separate comments approval. It is anchored to the exact NFR-21 sentence through the Docs `insertComment` range request; the returned quote matches the full sentence. It remains open for manual confirmation and resolution. This was a standalone smoke test; future `Previous` comments will use the same approval gate as their associated replacement.
