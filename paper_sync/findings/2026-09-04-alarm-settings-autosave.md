---
section: Use Cases — Use Case 11 (Configure Alarm Settings)
page/s: "unconfirmed"
required_revision: Replace UC-11's Save-button flow with the live autosave behavior
notes: Alt-flows 7a/7b (validation blocking) remain accurate as written and need no change. Table 14/NFR-21's existing audit-detail wording ("context and state diffs") already covers the newly enriched ALARM_SETTINGS_UPDATE detail; the audit-viewer burst-grouping display change has no corresponding paper claim to correct.
status: Not started
assigned_to: Daniboy
synced: false
---

## Changes

### 1. Defense paper — Use Case 11, Main Flow steps 8-9

Page/s: unconfirmed (Use Cases section starts at TOC p. 71; needs a rendered-PDF page check before this is entered in the tracker Sheet)

#### OLD

> 8. The user clicks "Save Settings."
>
> 9. The system validates the input, commits the updated configuration to the database, and displays a success confirmation message.

#### NEW

8. After a brief pause in activity, the system automatically validates the input and saves the updated configuration to the database, without requiring the user to click a save button.

9. The system displays a live status indicator reflecting the outcome, showing "Saving," "All changes saved," or an error state if the save could not be completed.

#### Evidence

`frontend/src/pages/profile/AlarmSettingsCard.tsx` — no submit button exists; `scheduleSave`/`flush` debounce the save (900ms, extended by a Test-button press), and `SaveStatusBadge` renders exactly these states (Saving… / Unsaved changes / Fix errors to save / Couldn't save + Retry / All changes saved). Merged to `main` in bayie27/adas-capstone#203.

#### Comment scope

Logical-paragraph scope — steps 8 and 9 change together as one continuous behavior shift (button click replaced by autosave plus a status indicator), not a small contiguous phrase.

#### Proposed comment (same gate as associated replacement)

Previous: 8. The user clicks "Save Settings." 9. The system validates the input, commits the updated configuration to the database, and displays a success confirmation message.

Codex ID: PS-20260904-ALARM-SETTINGS-AUTOSAVE

Done by Codex.

### 2. Defense paper — Use Case 11, Alternative Flow 8a

Page/s: unconfirmed (same page as above)

#### OLD

> 8a. No Changes Made: If the user clicks "Save Settings" without modifying any control, the system processes the request normally and confirms success without writing a redundant record to the database.

#### NEW

8a. No Changes Made: If no control's value differs from what was last saved, the system does not send a save request and no redundant record is written to the database.

#### Evidence

`backend/app/api/routes/settings.py:66-71` — the `sound_changed`/`volume_changed`/`snooze_changed` checks still gate the audit write exactly as before this session's changes; `AlarmSettingsCard.tsx`'s `flush()` additionally now skips the network request client-side when nothing differs from the last-synced value, whereas the prior button-driven flow always sent the request and relied on the backend alone to dedup.

#### Comment scope

Logical-paragraph scope — the full alternative-flow sentence is rewritten, not a short contiguous span within it.

#### Proposed comment (same gate as associated replacement)

Previous: 8a. No Changes Made: If the user clicks "Save Settings" without modifying any control, the system processes the request normally and confirms success without writing a redundant record to the database.

Codex ID: PS-20260904-ALARM-SETTINGS-AUTOSAVE

Done by Codex.

## Approval / sync ledger

Package ID: `PS-20260904-ALARM-SETTINGS-AUTOSAVE`

| Target                        | Approved scope | Applied/read back | Skipped/pending | Blocked |
| ----------------------------- | -------------- | ----------------- | --------------- | ------- |
| Defense paper                 | —              | —                 | blocks 1, 2     | —       |
| ADAS_Paper_Audit plus tracker | —              | —                 | —               | —       |
| Standalone comments           | —              | —                 | —               | —       |
