---
section: Data Dictionary — Table 14 (Audit Log)
page/s: unconfirmed
required_revision: Document that the audit_log `detail` field is redacted before it is written, not just that it holds "context and state diffs"
notes: Secondary site is Table 7, NFR-21 (Audit Trail Integrity), which already promises "complete forensic visibility" without saying sensitive values are kept out of the ledger in the first place.
status: Not started
assigned_to: Daniboy
synced: false
---

## Where

Data Dictionary, Table 14 _Audit Log_, the `detail` field row. Also Table 7, NFR-21 (Security Requirements). Observed in the live Doc text export on 2026-08-18; page numbers not confirmed (see note above — the Drive plain-text export has no page breaks).

## OLD

> detail | String | Structured JSON or text providing context and state diffs. | Nullable

## NEW

detail | String | Structured JSON or text providing context and state diffs; a fixed set of sensitive keys (password, token, API key, and similar) is always fully masked before the row is written, and free-text values are independently scanned and redacted for secret-shaped substrings. | Nullable

## Justification

`backend/app/services/audit.py:16-31` defines `_BANNED_DETAIL_KEYS`, a set of 14 key names (`password`, `old_password`, `new_password`, `password_hash`, `token`, `access_token`, `jwt`, `cookie`, `session_token`, `api_key`, `internal_api_key`, `secret_key`, `secret`, `authorization`) that `_redact_detail_value()` (`audit.py:34-48`) fully replaces with `"***REDACTED***"` inside any `detail` dict, recursively through nested dicts and lists, before `record()` (`audit.py:51-96`) ever constructs the `AuditLog` row. Every string value — banned key or not — also passes through `redact_text()` (`app/core/redaction.py`), a second, independent text-level pass. Neither the Data Dictionary's field description nor NFR-21 currently says this happens; a reader would reasonably assume `detail` is a raw dump of whatever the route passed in.

This is a real correction, not a restatement of what's already covered: NFR-21 and Table 14 were already updated in tracker row 2.6 ("RBAC enforcement and the audit guarantee") to describe the atomic transaction and the out-of-band failure path, and the live Doc text confirms both of those landed (line ~1082: "committed atomically alongside its audit log entry... while recording failed attempts out-of-band"). Redaction is a distinct guarantee that row never added — the Doc's `detail` field description still reads exactly as it did before that pass.

**Caution for whoever applies this:** the source `ADAS_Paper_Audit` Doc (Priority 2, §2.6) already drafted a version of this sentence and gave the count as "15 banned detail keys." Counted directly from `_BANNED_DETAIL_KEYS` in the current file, there are **14**, not 15. That §2.6 sentence never made it into the live Doc's `detail` row (confirmed by re-reading the Doc text on 2026-08-18), so there is no live paper claim to correct yet — but if that audit-doc sentence gets copied verbatim later, it will carry the wrong number. Use the count in this finding instead.

## Propagation

- **Table 14, Audit Log, `detail` row** — primary site, quoted above.
- **Table 7, NFR-19/NFR-21 (Security Requirements)** — NFR-21's text ("Failed or unauthorized access attempts shall be recorded in an isolated transaction to ensure complete forensic visibility") could gain a clause noting that the forensic record itself never carries credentials in the clear — optional, only worth doing if NFR-21 is being edited anyway for something else.
- **`ADAS_Paper_Audit` Doc, §2.6** — flag the "15 banned detail keys" sentence there as carrying a stale count, so it isn't copied forward with the error.
