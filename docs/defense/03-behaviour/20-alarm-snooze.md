# 20 — Alarm Snooze

> **One-liner:** Each operator keeps personal alarm settings, while a snooze is shared state on the incident so every dashboard quiets the same pending alert.
> **Panel risk:** high — a panelist can easily mistake a user's preferred snooze duration for a user-only mute, or challenge whether a shared mute can hide an emergency.

## 1. What it is

Alarm snooze has two separate meanings.

**Alarm preference** belongs to one user. It contains the sound choice, volume, and the
duration that user's next snooze action will use. It is saved automatically after an edit
settles; there is no separate Save button.

**Incident snooze** belongs to an Unverified incident. It records that the incident is
temporarily muted, when the mute began, when it ends, and who started it. The mute is
shared: every connected operator dashboard treats that same incident as snoozed.

| Question                                            | Alarm preference                                                    | Incident snooze                                           |
| --------------------------------------------------- | ------------------------------------------------------------------- | --------------------------------------------------------- |
| What does it describe?                              | How one user wants alarms to sound and how long their snooze lasts. | Whether a particular pending incident is muted right now. |
| Who owns it?                                        | One user account.                                                   | The incident record, shared across dashboards.            |
| When is it used?                                    | When that user configures or triggers an alarm.                     | After an operator snoozes an Unverified incident.         |
| What is saved?                                      | Sound, volume, and configured duration.                             | Snooze start, expiry, and acting user.                    |
| Does it make every operator's preference identical? | No. Each user keeps their own sound and volume.                     | No. It shares only the incident's muted state and expiry. |

The short version is: the preference answers “how long should my snooze last?” The incident
state answers “which alert is currently snoozed for everyone?”

The mute does not verify, dismiss, or close an incident. The incident remains Unverified
and visible for an operator to review. When the snooze expires, the alarm becomes active
again unless the incident was handled first.

## 2. Where it lives

### In the paper

- Chapter 3, “Functional Requirements Specification,” Table 2:
  - FR-07, “Audible Alert Timeout and Escalation,” requires a Mute/Snooze action and
    automatic re-alarm if an alert remains Unverified too long. The paper gives 30 seconds
    as an example.
  - FR-08, “Alarm Configuration Module,” calls for user settings for alarm tone, volume,
    and snooze duration.
- Chapter 3, “Use Cases,” “Verify Accident Alert,” describes the operator snoozing while
  reviewing the snapshot, the countdown using the user's configured duration, re-alarm
  when the duration expires, and suppression of re-alarm after Confirm or Dismiss.
- Chapter 3, “Use Cases,” “Configure Alarm Settings,” describes loading the user's saved
  values, choosing sound and volume, entering a duration, autosaving after a brief pause,
  validating the range, and restoring settings on the user's next login.
- Chapter 3, “Data Dictionary,” Table 11, “Detection Log,” documents snoozed_at,
  snoozed_until, and snoozed_by_id on the incident record.
- Chapter 3, “Data Dictionary,” Table 16, “Alarm Settings,” documents user_id as unique,
  plus alarm_sound, volume, and snooze_duration. The paper specifies snooze duration in
  seconds from 15 to 60, with a default of 30. It specifies volume from 0 to 100, with a
  default of 80.
- Chapter 3, “User Interface Designs,” Figure 28, “Profile Page,” is the paper pointer for
  the Alarm Settings panel.

### In the code

**User preference**

- The one-row-per-user AlarmSettings model and persisted values are in
  backend/app/models/user.py:108.
- The authenticated GET and PUT endpoints are in backend/app/api/routes/settings.py:31
  and backend/app/api/routes/settings.py:52.
- The API schema enforces the volume and snooze-duration bounds in
  backend/app/schemas/settings.py:28.
- The profile card loads the saved values, validates edits, and queues an automatic save in
  frontend/src/pages/profile/AlarmSettingsCard.tsx:129,
  frontend/src/pages/profile/AlarmSettingsCard.tsx:201, and
  frontend/src/pages/profile/AlarmSettingsCard.tsx:245. It flushes a pending edit when the
  card unmounts at frontend/src/pages/profile/AlarmSettingsCard.tsx:258.

**Shared incident state**

- The alert route authenticates the operator, records the audit event, commits the snooze,
  broadcasts the activation, and schedules expiry in backend/app/api/routes/alerts.py:663.
- The request model accepts no duration field; extra fields are forbidden in
  backend/app/schemas/detection.py:60.
- The service reads the acting user's saved duration and only writes a snooze while the
  incident is Unverified in backend/app/services/snoozes.py:30.
- The atomic expiry, replaceable date job, periodic safety sweep, and startup reconciliation
  are in backend/app/services/snoozes.py:84,
  backend/app/services/snoozes.py:126,
  backend/app/services/snoozes.py:157, and
  backend/app/services/snoozes.py:177.
- Startup calls reconciliation and schedules pending snoozes in
  backend/app/main.py:141, backend/app/main.py:145, and
  backend/app/main.py:161. The sweep is registered at backend/app/main.py:166.
- A terminal incident transition clears the snooze fields in the same conditional update as
  the status change in backend/app/services/incidents.py:229.
- The server event is broadcast to connected dashboards in
  backend/app/services/realtime.py:132. The event builders are in
  backend/app/services/events.py:83 and backend/app/services/events.py:93.
- The browser maps SNOOZE_ACTIVATED and RE_ALARM into shared incident state in
  frontend/src/components/RealtimeAlertsBridge.tsx:121. Its sound queue counts only
  unsnoozed Unverified incidents in frontend/src/store/useAlertStore.ts:122.
- In the blocking alert popup, one global Snooze Alarm action targets the current
  Unverified queue and submits a snooze request per incident:
  frontend/src/components/GlobalAlerts.tsx:171 and
  frontend/src/components/GlobalAlerts.tsx:181.

### In the test tracker

- Unit Testing: TC-UNIT-021 covers using the acting user's saved duration; TC-UNIT-022
  covers startup recovery; TC-UNIT-025 covers the snooze-duration bounds.
- System E2E Testing: TC-SYS-006 covers expiry, repeat snooze, and suppression after
  Confirm. TC-SYS-007 covers automatic settings persistence and use in a later session.
- Reliability & Endurance: TC-REL-001 covers snooze recovery after a server restart.
- UAT Journeys and UAT Traceability map FR-07 to the global Snooze action and re-alarm
  behavior, and FR-08 to alarm configuration. See
  docs/ADAS Test Execution.xlsx, sheets Unit Testing, System E2E Testing, Reliability &
  Endurance, UAT Journeys, and UAT Traceability.

## 3. How it works

### A. Personal settings

1. The signed-in user opens Profile → Alarm Settings. The card loads the settings attached
   to that account and applies the saved sound and volume to that browser.
2. The user changes a tone, moves the volume control, or edits snooze duration.
3. The card validates the duration and volume. A value outside the allowed range is not
   sent to the server.
4. After the edit settles, the card sends the full preference set automatically. The user
   sees a save-status badge; there is no separate save action.
5. The backend stores the preference against the current user's AlarmSettings row. A later
   session loads the same settings again.

The configured duration is a preference, not a current mute. Changing it does not extend
an incident that is already snoozed; it supplies the duration for a subsequent snooze
action.

### B. Snoozing the active alert queue

1. An alert arrives as Unverified. The alert stays on the dashboard while operators inspect
   its snapshot and other available context.
2. An operator presses Snooze Alarm in the blocking alert popup. The popup selects its
   current Unverified queue. This one control fans out a separate request for each
   incident in that queue; a new incident arriving after the click is not part of the
   requests already sent.
3. Each request identifies an incident but supplies no duration. The backend reads the
   signed-in operator's saved snooze_duration instead. A client-supplied duration is
   rejected, so a browser cannot extend the interval by changing the request.
4. The service first checks that the incident is Unverified. It then calculates one
   snoozed_until deadline from the server's current UTC time and the actor's saved
   duration.
5. A conditional database update writes snoozed_at, snoozed_until, snoozed_by_id, and
   updated_at only while that same incident is still Unverified. If another operator
   confirms or dismisses it before the update lands, the snooze loses the race rather than
   silently applying to a handled incident.
6. The route commits the incident update and its ALERT_SNOOZE audit record before
   broadcasting SNOOZE_ACTIVATED. The event identifies the incident, the person who
   snoozed it, and the shared deadline.
7. Every connected dashboard receives the event and mutes that incident until the same
   deadline. The alert remains visible and Unverified. Each dashboard still uses its own
   stored tone and volume for other alarms.
8. A new incident that was not included in the popup's current queue has no snooze fields,
   so it remains alarm-active. Existing Ongoing or closed incidents are not snoozed.

At the database level, each incident has its own snooze fields. The popup's single action
can create several such incident snoozes, but it does not write a user-local mute flag.
The deadline for each snoozed incident is shared by the dashboards that display it.

### C. Expiry and re-alarm

The saved deadline is the source of truth. The scheduler job is a prompt to check it, not
the only place where the deadline exists.

- After a successful snooze commit, the backend registers a one-shot date job to run at
  snoozed_until.
- Its stable job identifier is snooze:{log_id}. Re-snoozing the same incident replaces
  the earlier job with the same identifier and a later deadline.
- When a job fires, it attempts a conditional update. The database clears the snooze
  fields only if the row is still Unverified and snoozed_until is due.
- Only the call that changes a row commits and broadcasts RE_ALARM. A duplicate job, an
  obsolete job, or a job that runs after the incident was handled updates no row and
  stays silent.
- The scheduler also runs a periodic snooze sweep every 30 seconds. The sweep finds due
  Unverified incidents and sends each through the same expiry function, covering a
  one-shot job that was lost.
- A dashboard also schedules a local timer from the shared deadline so its own alarm
  state can change promptly. The server-side database update remains the authority for
  the shared expiry event.

The conditional update checks the incident ID, Unverified status, a non-null snooze
deadline, and deadline ≤ current time. This handles two difficult races:

| Race                                                         | Database result                                                          | Audible result                                                                  |
| ------------------------------------------------------------ | ------------------------------------------------------------------------ | ------------------------------------------------------------------------------- |
| Two expiry paths run together.                               | At most one update clears the due row.                                   | Only the winner broadcasts RE_ALARM.                                            |
| An old job fires after a re-snooze moved the deadline later. | The row is not yet due, so the update changes nothing.                   | The old job stays silent; the new deadline remains active.                      |
| Confirm or Dismiss wins before expiry.                       | The transition has already cleared the snooze fields and changed status. | The expiry path finds no eligible row and stays silent.                         |
| The snooze expires while the server is down.                 | Startup reconciliation sees a due Unverified row and clears its snooze.  | The reconnected dashboard reconstructs an unsnoozed alert from persisted state. |

### D. Recovery after a restart

At startup, the backend reads persisted Unverified incidents that still have a snooze
deadline.

- If the deadline passed while the backend was stopped, reconciliation clears the expired
  snooze before the scheduler starts. The incident is still open, so it is alarm-active
  again when dashboards reconnect and rebuild their active-alert state.
- If the deadline is still in the future, reconciliation returns that incident to the
  startup path. Once the scheduler exists, the backend registers a fresh date job for the
  remaining deadline.
- The 30-second periodic sweep remains registered as a fallback for due rows whose
  one-shot job is missing.

This means a process restart does not reset the snooze clock. It resumes from the
persisted deadline, whether that deadline is still pending or already expired.

### E. Why a terminal transition cancels snooze state

Confirm, Dismiss, Clear, and terminal Dismiss update the incident status and clear
snoozed_at, snoozed_until, and snoozed_by_id in the same conditional database update.
The audit log retains who snoozed and when, while the active incident row no longer claims
to be snoozed.

The scheduler may still hold an in-memory date job after an operator handles the incident.
That job cannot re-alarm it: the database row is no longer Unverified and no longer has a
snooze deadline. The atomic expiry predicate is therefore the correctness guard; removing
the scheduled job is only cleanup.

## 4. Why it was built this way

### Preference and incident state have different owners

Sound and volume describe an operator's workstation experience, so they are stored per
user. The mute describes the shared handling state of an incident, so it is stored on the
incident. This lets operators keep different sound and volume preferences while seeing
the same incident deadline.

If the mute were only browser-local, a second workstation could continue sounding for
the same pending incident after the first operator pressed Snooze. Persisting the deadline
and broadcasting it gives all connected dashboards one shared answer.

### The backend, not the browser, chooses the interval

The client asks to snooze an incident. It does not choose how long. The server derives the
deadline from the authenticated operator's saved preference and validates the preference
against the paper's range.

That prevents a modified browser request from asking for a much longer silence than the
settings screen permits. It also gives a clear audit answer: which operator acted, on
which incident, and until what deadline.

### Persisted deadlines survive process memory

A timer held only in memory disappears when the backend restarts. The incident row keeps
the deadline, so startup can distinguish an unexpired snooze from one that elapsed during
the outage.

The date job handles normal expiry near the deadline. The periodic sweep repairs a missed
job. Startup reconciliation handles the time when no backend process was running. All
three paths use the same database condition, so their presence does not create duplicate
re-alarms.

### Atomic updates settle races at the shared record

An ordinary read followed by an ordinary write would leave a gap: one operator could
confirm while a snooze request was still in flight, or two expiry paths could both decide
that a snooze is due.

The conditional update puts the status and deadline checks into the database write. One
caller gets the row; the others see that the eligibility condition no longer holds. The
audit entry and state change commit together.

### Terminal state owns the cleanup

When an incident leaves Unverified, the transition itself clears snooze fields in the same
update. The delayed scheduler job then has no authority to revive a handled alert. This
keeps the database state correct even if a job is late or remains in memory.

## 5. What changed since the 28 April defense

Repository history after the 28 April defense records the alarm behavior being completed
as an end-to-end flow: persisted per-user settings, automatic save, a shared incident
snooze, and durable expiry recovery. The current alert popup also applies its global
Snooze Alarm control to the Unverified items in the queue.

The current evidence set now exercises preference validation, the acting user's saved
duration, expiry, repeat snooze, and restart recovery. The tracker records these as
TC-UNIT-021, TC-UNIT-022, TC-UNIT-025, TC-SYS-006, TC-SYS-007, and TC-REL-001.

The defense explanation stays anchored to FR-07 and FR-08: temporary silencing must end
with a re-alarm if the incident remains Unverified, and operators can configure their own
alarm settings.

## 6. Limits and honest caveats

### One snooze is bounded; repeated snoozes are allowed

The allowed preference range is 15 to 60 seconds. One snooze therefore cannot set an
unlimited deadline. If the incident remains Unverified at expiry, the alarm is reactivated
and the operator may snooze it again.

The paper explicitly allows a new countdown after expiry. The system does not impose a
total count or lifetime cap on repeated snoozes, so do not claim that it prevents a
determined operator from postponing the alarm forever. Its guarantee is a bounded quiet
window followed by a re-alarm for each snooze.

### Volume zero is a valid personal setting

The paper and tracker allow volume 0 on the per-user setting. A shared RE_ALARM event
restores that incident to the alarm-active queue, but it does not override a user's volume
preference. If an operator has set volume to 0, that workstation will not produce an
audible sound even though the incident is no longer snoozed.

### The popup fan-out is not one all-or-nothing transaction

The global popup action sends an individual request for each Unverified incident in its
current queue. If one incident changes status during the requests, that incident can lose
the race while another request succeeds; successful incident snoozes are not rolled back
as one batch.

The popup surfaces a conflict or error and refreshes its alert data. Describe this as a
shared per-incident state change, not one database transaction covering the entire queue.

### Restart evidence is qualified

TC-REL-001 passed under accelerated restart simulation. The tracker says persisted
snoozes were reconciled from a fresh service lifecycle, pending deadlines stayed pending,
expired deadlines cleared, and duplicate clearing was harmless. It explicitly calls for a
real service restart to be repeated for deployment evidence.

TC-SYS-006 passed the expiry and re-alarm path with a 15-second preference. The tracker
recorded re-alarm play calls within 16 milliseconds and 13 milliseconds of the two tested
deadlines, then no play call during the 30-second observation after Confirm. Those
measurements are evidence for that test run, not a general production timing guarantee.

### Sweep timing is a recovery interval, not the normal deadline timer

The normal path uses a one-shot date job for the persisted deadline. The periodic sweep
runs every 30 seconds to catch a due snooze if its job was lost. Do not present the sweep
interval as the promised re-alarm delay for the normal path.

### Disconnected dashboards need to reconnect

The activation and expiry events are delivered over the live alert channel. A dashboard
that is disconnected cannot receive an event at that moment; when it reconnects, it must
rebuild from the persisted alert state. Do not describe a disconnected browser as having
received a live broadcast.

## 7. Likely panel questions

### “If one operator snoozes, does everyone go quiet? Is that safe?”

Every connected dashboard applies the same snooze deadline to the affected Unverified
incident; the popup's global action targets its current Unverified queue. The alert stays
visible, and an alert arriving after the action is not part of that request set. Expiry
restores the alarm if an incident is still Unverified.

### “What stops an alert being silenced indefinitely?”

One snooze can last only 15 to 60 seconds, and an Unverified incident re-alarms when that
window ends. The operator may snooze again, so the system guarantees repeated prompts,
not a lifetime limit on how many times a human can defer them.

### “What happens if the server restarts mid-snooze?”

The deadline is stored on the incident, not only in a timer. Startup clears a deadline
that expired during downtime and reschedules one that is still pending; the restart test
passed under accelerated simulation, with a real service restart still needed for
deployment evidence.

### “Why is the snooze global rather than per-operator?”

The incident is one shared operational fact. If another workstation kept sounding after
the first operator muted the same incident, the team would have different alarm state for
one event; each person still keeps their own tone and volume preferences.

### “Can an operator snooze an incident someone else is already handling?”

Only while the incident is still Unverified. If Confirm or Dismiss changes it first, the
snooze is rejected; if the actions race, the conditional update lets only the update that
still matches the expected state succeed.

### “Can the browser ask for a five-minute snooze?”

No. The request carries the incident ID, not a duration, and the request schema rejects
extra duration fields. The backend uses the signed-in operator's saved and bounded
preference.

### “What if two expiry jobs run, or an old job runs after another snooze?”

Both use the same conditional database update. Only a due Unverified row can be cleared,
so the winner broadcasts RE_ALARM and a duplicate or obsolete job stays silent.

### “What happens if another alert arrives while this one is snoozed?”

The active popup action targets the queue that existed when the operator clicked. A later
incident has no snooze deadline, so it remains alarm-active; snooze is not a permanent
global mute switch.

### “What if the operator has set their volume to zero?”

The incident still leaves snoozed state at expiry, but the dashboard honors the operator's
saved volume. Volume zero is allowed, so re-alarm state does not guarantee audible sound
on a workstation configured to be silent.

### “Does snoozing remove the incident from the dashboard?”

No. Snooze temporarily suppresses the alarm; it does not make a Confirm or Dismiss
decision. The incident remains Unverified and visible until an operator handles it.

## 8. Cram summary

- Keep the two meanings separate: alarm preference is per user; active snooze is shared
  incident state.
- Sound, volume, and snooze duration autosave to the signed-in user's settings.
- The paper's preference bounds are 15–60 seconds; the saved duration defaults to 30.
- The backend takes the acting user's saved duration. A client-supplied duration is
  rejected.
- Snooze applies only while an incident is Unverified. The popup's global action sends a
  request for each current Unverified queue item.
- Each incident stores snoozed_at, snoozed_until, and snoozed_by_id. Every connected
  dashboard honors that same incident deadline.
- Expiry is an atomic conditional update. Only the caller that clears the due row commits
  and broadcasts RE_ALARM.
- The stable snooze:{log_id} date job is backed by a 30-second sweep and startup
  reconciliation from persisted deadlines.
- Confirm, Dismiss, and terminal transitions clear snooze fields in the same update as
  the status change, so a late job cannot re-alarm a handled incident.
- The per-snooze bound prevents a single indefinite mute, but operators can snooze again;
  restart evidence is simulation-qualified.
