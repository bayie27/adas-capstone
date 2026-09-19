# 19 — Human-in-the-Loop State Machine

> **One-liner:** The AI raises a potential collision, while an operator decides whether it is a real incident and when it is finished.
> **Panel risk:** High — this is the system’s central safety and accountability workflow, so the panel can probe races, mistakes, restart behavior, and the limits of automation.

## 1. What it is

### Explain it in one breath

ADAS does not treat an AI detection as an official accident decision.
The system creates an **Unverified** incident and presents its snapshot to an operator.
The operator either confirms it as a true positive or dismisses it as a false positive.

A confirmed incident becomes **Ongoing** until an operator marks the scene **Cleared**.
If the operator realizes that a confirmation was a mistake, the Ongoing record can instead be dismissed as a human correction.
The four permitted transitions are:

- **Unverified → Ongoing** when the operator confirms a genuine collision.
- **Ongoing → Cleared** when the operator says the scene has been cleared.
- **Unverified → Dismissed** when the operator rejects a false positive.
- **Ongoing → Dismissed** when the operator corrects an earlier mistaken confirmation.

Use the paper’s word **Cleared** for the end of a genuine incident.
The system keeps the incident record after the alert leaves the active dashboard.
The record retains the decision and who made it for later review.

The AI is not allowed to mark an incident cleared by itself.
The camera’s detection state is also managed through the incident lifecycle.
After a collision event, the AI pauses that camera before asking the backend to save the alert.

The backend then records the incident and mirrors the pause before the operator acts.
The pause prevents the same scene from immediately creating repeated alerts.
The incident status and the camera’s AI state are related but separate facts.

For example, a dismissed false positive is terminal as an incident, while the camera stays paused briefly for its cooldown.
After a true-positive incident is cleared, the incident record is terminal and the camera can resume monitoring.
Keep the distinction simple:

- The **incident status** says what the operator concluded about this event.
- The **camera state** says whether automated detection should currently run on that feed.

The record answers, “What happened to this alert?”
The camera state answers, “Should the detector be watching this camera now?”

## 2. Where it lives

### In the paper

- **Chapter 1, Definition of Terms:** “Human-in-the-Loop (HITL)” assigns the human operator final authority to confirm, dismiss, or clear an incident.
- **Chapter 1, Definition of Terms:** “Verification Status” defines Unverified, Ongoing, Cleared, and Dismissed as incident lifecycle states.
- **Chapter 1, Definition of Terms:** “Cooldown Timer” defines the one-minute pause after an operator dismisses a false-positive alert.
- **Chapter 3, Requirements Analysis → Functional Requirements Specification (FRS), Table 2:** FR-06 starts a generated alert as Unverified; FR-09 requires Confirm or Dismiss; FR-10 specifies the false-positive cooldown; FR-11 specifies the confirmed-incident lifecycle; FR-20 requires an audit trail.
- **Chapter 3, Requirements Analysis → Use Cases, “Verify Accident Alert”:** the basic flow, alternative flows 6a and 10a, and postconditions describe false-positive dismissal, human correction, immediate camera resumption, and durable incident history.
- **Chapter 3, System Architecture and Design → Swimlane Diagram, Figure 3:** separates automated detection from operator verification and clearance.
- **Chapter 3, System Architecture and Design → Use Case Diagram, Figure 4:** shows the operator’s collision-review and clearance responsibilities.
- **Chapter 3, System Architecture and Design → Data Dictionary, Table 10 (Camera):** defines desired AI state, its reason, and the cooldown deadline.
- **Chapter 3, System Architecture and Design → Data Dictionary, Table 11 (Detection Log):** defines the incident lifecycle status and the operator attribution fields.
- **Chapter 3, User Interface Designs, Figures 12 and 14:** the Ongoing modal offers Dismiss and Cleared actions; the Cleared record is displayed as terminal with no further action buttons.

### In the code

**State model and atomic transition service**

- The allowlist of four legal edges is in backend/app/services/incidents.py:37.
- The conditional status update and audit-field selection are in backend/app/services/incidents.py:229.
- The special Dismiss path, which selects Unverified or Ongoing before making the same guarded update, is in backend/app/services/incidents.py:284.

**Alert routes, persistence, and operator feedback**

- The 409 conflict response is built in backend/app/api/routes/alerts.py:104.
- Confirm is handled in backend/app/api/routes/alerts.py:464.
- Dismiss, including the distinction between false-positive cooldown and human correction, is handled in backend/app/api/routes/alerts.py:517.
- Clear is handled in backend/app/api/routes/alerts.py:602.
- The notice shown to the losing operator is in frontend/src/components/ui/IncidentHandledNotice.tsx:33.
- The frontend parses conflict details in frontend/src/api/alerts.ts:44.

**Detection pause and backend mirror**

- The AI pipeline pauses the camera before snapshot or network work in ai_engine/pipeline.py:222.
- The camera’s pause and resume methods are in ai_engine/camera.py:79; the paused reader path is in ai_engine/camera.py:194.
- Snapshot creation and durable outbox enqueueing are in ai_engine/accident.py:46.
- Backend incident creation starts in backend/app/services/incidents.py:158; the camera pause update is at backend/app/services/incidents.py:190.
- The internal route broadcasts only after the ingest service has committed in backend/app/api/routes/internal.py:132.

**Camera state and restart recovery**

- Desired-state rules for disabled cameras, open incidents, cooldowns, and normal activity are in backend/app/services/cameras.py:326.
- Startup recomputation is in backend/app/services/cameras.py:368.
- Cooldown expiry, restart rescheduling, and the safety sweep are in backend/app/services/cameras.py:413, backend/app/services/cameras.py:454, and backend/app/services/cameras.py:482.
- Backend startup invokes camera-state reconciliation in backend/app/main.py:139.
- The AI supervisor reconciles its streams against the backend heartbeat snapshot in ai_engine/supervisor.py:43; its heartbeat loop starts at ai_engine/supervisor.py:216.
- Heartbeat ingestion and the full desired-state snapshot start in backend/app/api/routes/internal.py:139.
- The default dismissal cooldown setting is in backend/app/core/config.py:94.

**Regression coverage**

- Competing confirm requests are covered in backend/tests/test_alerts.py:1524.
- The absence of routes that reopen terminal states is checked in backend/tests/test_alerts.py:1078.
- Camera-state side effects for dismiss and clear are covered in backend/tests/test_alerts.py:1113.

## 3. How it works

### The legal state graph

AI detection → **Unverified** → Confirm → **Ongoing** → Clear scene → **Cleared**

**Unverified** → Dismiss false positive → **Dismissed**

**Ongoing** → Dismiss correction → **Dismissed**

There are four legal status transitions: two steps for a confirmed accident, one direct false-positive dismissal, and one correction after a mistaken confirmation.

| Starting status | Operator action                    | New status | Camera effect                               |
| --------------- | ---------------------------------- | ---------- | ------------------------------------------- |
| No incident row | AI reports a collision event       | Unverified | Pause for the incident                      |
| Unverified      | Confirm a true positive            | Ongoing    | Stay paused for the incident                |
| Ongoing         | Mark the scene cleared             | Cleared    | Resume immediately if the camera is enabled |
| Unverified      | Dismiss a false positive           | Dismissed  | Stay paused until the cooldown deadline     |
| Ongoing         | Dismiss a human-error confirmation | Dismissed  | Resume immediately if the camera is enabled |

These are the only legal edges.
Cleared and Dismissed are terminal incident statuses.

### Detection creates an Unverified incident

The AI detector evaluates the stream and its temporal accumulator decides when the evidence is strong enough to emit an event.
When an event fires, the pipeline calls the camera’s pause method before it invokes the event handler.
The local camera state changes first, so another inference tick will skip that feed while snapshot and delivery work proceeds.

The reader may still grab stream frames to keep the video buffer current, but the paused feed is not decoded into new inference work.
The event handler writes an annotated snapshot and places the event in the engine’s durable outbox.
The outbox delivers the event to the backend and retains it for retry if delivery cannot be acknowledged.

The backend validates that the camera is available and that a duplicate or another open incident is not being inserted.
It creates a Detection Log row whose status is Unverified.
In the same backend transaction, it records the camera’s desired AI state as Paused for reason incident.

The transaction commits the alert and the camera pause together.
Only after that commit does the route broadcast the new alert and camera status over the dashboard channel.
The operator therefore sees an incident that is already durable and a camera that is already marked paused.

No operator click is needed to initiate the pause.
The next engine heartbeat receives the backend’s authoritative desired state and applies it locally.

### Confirm moves the record to Ongoing

Confirm is the operator’s statement that the detected event is a genuine collision.

The backend attempts the Unverified → Ongoing transition.

It records the confirming operator and verification time on the incident.
The camera remains paused because the incident is still open.
The dashboard receives the committed status update after the database transaction succeeds.

No emergency conclusion is inferred just from the AI score or snapshot.
The operator has to make the confirmation decision.

### Clear closes a genuine incident

After the emergency scene has been handled, an operator marks the Ongoing incident Cleared.

The backend attempts the Ongoing → Cleared transition.

It records who closed the incident and when.
For an enabled camera, the backend recomputes the desired state and resumes detection immediately.
The camera status update is broadcast after the state has been committed.

Cleared is a final record of the event, not a button to erase it.
The incident remains available for audit and reporting.

### Dismiss has two meanings

The Dismiss action can be used from Unverified or Ongoing.
The source state determines which of two different workflows is taking place.

**Unverified → Dismissed: false-positive dismissal**

- The operator says the AI alert is not a genuine accident.
- The record becomes Dismissed and the operator is recorded as the verifier.
- The camera enters a one-minute cooldown before detection resumes.
- The backend stores the cooldown deadline on the camera record.
- The dashboard clears the active alert and receives the camera’s cooldown status.

**Ongoing → Dismissed: human correction**

- The operator previously confirmed the alert but now identifies that confirmation as an error.
- The record becomes Dismissed while retaining the original verification history.
- The correcting operator and time are recorded as closure details.
- An enabled camera resumes immediately.
- This path does not start the false-positive cooldown.

The two paths share the word Dismissed because both mean the incident record is not being carried forward as a confirmed accident.
They differ in source status, audit meaning, and camera behavior.

### Why there are no other transitions

The state machine does not allow Unverified → Cleared.

That would skip the required human confirmation and imply that an incident had been addressed before it had even been accepted as genuine.

The state machine does not allow Ongoing → Unverified.

If an operator confirms by mistake, the record goes to Dismissed as a correction; it is not rewound to look as though nobody acted.
The state machine does not allow a terminal Cleared or Dismissed record to be reopened or changed into the other terminal status.
That preserves the human decision and the time and actor attached to it.

If a later collision occurs on the same camera, it is a new incident row, not a revival of old history.
There is no general-purpose status-edit or delete route for an incident.

### A transition is one guarded database update

Each allowed transition specifies an expected current status and a new status.
The backend writes the new value with one conditional database statement:

UPDATE DetectionLog
SET detection_status = new_status, actor_and_time_fields = values
WHERE log_id = incident_id AND detection_status = expected_status

The database checks the current status as part of the update itself.
It is not a separate “read the status, then later write a new one” sequence.
If two operators try the same action at nearly the same time, the first update that changes the row succeeds.

The second update no longer matches the expected old status.
It affects no row, and the backend reloads the current incident state.
If the incident does not exist, the route reports Not Found.

If it exists but has already moved, the route reports HTTP 409 Conflict.
The response detail says, “This incident was already handled by another operator.”
It includes the incident’s current status, the action that landed, the handler’s name, and the handling time.

The frontend notice presents the result in plain language, such as “another operator confirmed this incident,” followed by the current status and time.
Other connected dashboards receive the same result through the status broadcast.
The conditional update prevents the losing request from overwriting the winning operator’s decision.

For a successful action, the status update and audit entry are committed in the same transaction.
The dashboard broadcast happens after commit, so it does not announce a change that could still roll back.
Dismiss first reads the row only to choose which source status to expect.

The final update still includes that expected status in its condition, so a change between the peek and write is caught.

### Self-blindfold ordering

The self-blindfold is the coordinated pause across the AI engine, backend database, and operator dashboard.
The order is deliberate:

- The accumulator fires an incident event.
- The AI engine pauses that camera immediately.
- The AI engine captures the annotated snapshot and persists the event in its outbox.
- The backend creates the Unverified incident and marks the camera Paused for reason incident in one transaction.
- The backend commits the durable state.
- The backend broadcasts the new incident and camera state.
- The engine applies the authoritative desired state on its heartbeat.
- An operator then confirms, dismisses, or later clears the incident.

The engine must pause before disk or network work.
That makes the pause local and immediate even if snapshot encoding or the backend request takes time.
The backend must persist the incident pause before the alert is broadcast.

That makes the database the durable authority before clients are told that the new alert exists.
If the engine performed network or disk work before its local pause, the camera could keep producing inference while delivery is delayed.
The same event could then trigger repeated alerts from a feed that should already be held.

If the backend broadcast the alert before committing the camera pause, a dashboard could show an active incident while the database still said the camera should run.
A heartbeat or restart reconciliation could then tell the engine to resume from stale state.
If the transaction later failed, the dashboard would have been told about an alert that was never durably recorded.

This is why the workflow pauses locally first, commits backend state second, and broadcasts after commit.

### Incident status and camera state are separate

The incident row represents the operator’s judgement about one event.
The camera record represents the backend’s desired runtime state for a feed.
An open incident makes the camera Paused for reason incident.

A false-positive dismissal closes the incident but changes the pause reason to cooldown until the stored deadline.
A cleared incident or a human correction removes the incident pause and resumes detection immediately for an enabled camera.
If an administrator has disabled the camera, it remains Inactive even when an incident is cleared.

The camera state is recomputed from current facts: whether the camera is enabled, whether an incident remains open, and whether a cooldown is still active.
This rule prevents a timer callback from blindly turning a camera Active when a newer incident has already opened.

### The one-minute cooldown is durable

The paper specifies a one-minute cooldown after an Unverified alert is dismissed as a false positive.
The reason is persistent environmental noise: immediately reopening detection can repeat the same false alarm and overwhelm the operator with redundant notifications.
The cooldown does not change the incident back to open or mark it Ongoing.

The incident remains Dismissed while the camera is temporarily paused for cooldown.
The backend stores a UTC cooldown deadline in the camera row.
The scheduled job is only a prompt to recheck that durable deadline.

The database state, not the in-memory job, decides whether the camera should resume.
On startup, the backend recomputes desired camera states from open incidents and stored cooldown deadlines.
It reschedules any cooldown that is still in progress.

A periodic sweep can also find an expired deadline whose one-shot job did not run.
At expiry, the backend rereads the camera and open-incident state before deciding whether to resume.
If a new incident is open, the camera stays Paused for reason incident.

If the camera is disabled, it stays Inactive.
Only when no higher-priority pause applies does it return to Active.
An in-memory-only timer would disappear when the process exits.

After a restart during the cooldown, the system would then lose the exact resume deadline.
Depending on how it recovered, the camera could remain paused indefinitely or resume earlier than intended.
Persisting the deadline makes the timer recoverable and keeps the restart behavior deterministic.

The Ongoing → Dismissed correction is different by design.

The paper says that a human correction resumes AI detection immediately.
That action corrects a mistaken operator confirmation; it is not the direct rejection of a new Unverified alert.

The false-positive cooldown applies to Unverified → Dismissed, while an Ongoing correction removes the open-incident pause and resumes the enabled camera.

### What happens across a restart

The incident status and camera cooldown deadline are stored in the application database.
If the backend restarts during an Ongoing incident, the record remains Ongoing.
Startup reads open incidents and recomputes the desired camera state as Paused.

When the AI engine reconnects, the heartbeat snapshot reapplies that desired state.
If the backend restarts during the false-positive cooldown, the stored deadline remains available.
Startup recomputes the camera as Paused for cooldown and schedules its remaining wait.

The system does not silently turn the incident into Cleared or Dismissed just because a process restarted.
If the engine restarts while an event is still waiting in its local outbox, it retries that event.
The supervisor avoids honoring a stale Active snapshot for a camera with a pending event.

After successful delivery, the backend stores the incident and its Paused desired state.

## 4. Why it was built this way

### Human judgment remains the final incident decision

The detector is useful for noticing a potential event in a stream that is difficult to monitor continuously.
It cannot determine by itself whether an emergency is real, whether responders have handled it, or whether the initial confirmation was mistaken.
The paper makes Confirm, Dismiss, and Clear operator actions rather than automatic model outcomes.

That is the safety boundary the team should defend.

### Each edge represents a real decision

Unverified → Ongoing means “a human accepts this as a real accident.”

Ongoing → Cleared means “a human says the scene has been cleared.”

Unverified → Dismissed means “a human rejects this detection.”

Ongoing → Dismissed means “a human corrects an earlier confirmation.”

There is no meaningful fifth edge that adds information without skipping a decision or rewriting history.
The allowed edges also preserve who verified or closed the record.

### One database condition resolves competing actions

A read-then-write guard can let two requests read Unverified before either one writes.
Both would then act on a stale assumption.
Placing the expected status in the update’s WHERE condition makes the database decide the winner at the write boundary.

The losing operator receives the current record and the name and action of the winner.
The design therefore exposes a clear conflict instead of silently overwriting a colleague.

### Durable state supports recovery

An incident decision and its camera pause must still agree after a process restart.
A database row survives where a Python task, timer handle, or browser’s local state does not.
The backend derives desired camera state from the current incident and cooldown facts rather than trusting whichever process last held a timer.

The engine then reconciles its runtime to that desired state through heartbeat.

### The cooldown and correction paths solve different problems

After a direct false-positive dismissal, the camera waits briefly so persistent environmental noise does not immediately create the same alert again.
After a human correction of an Ongoing incident, the operator has withdrawn a mistaken confirmation and monitoring resumes immediately.
The paper explicitly gives these different outcomes.

Do not explain the second path as a shortened cooldown.
It is a distinct transition with a different source state and meaning.

### Alternatives the implementation avoids

- A memory-only cooldown would be lost on restart.
- A read followed by an unguarded status write would allow stale requests to race.
- A frontend-only pause would not survive a reload, another operator’s dashboard, or engine reconciliation.
- Broadcasting before commit could publish a state change that is not durable.
- Reopening terminal records would make the recorded verification history ambiguous.

## 5. What changed since the 28 April defense

The paper’s human decision sequence remains the explanation to give the panel: Unverified, then Ongoing or Dismissed, then Cleared or corrected Dismissed.
The repository history after the April defense baseline shows that the backend now enforces those paper transitions through one central atomic transition service.
The service allowlist and conditional update arrived in commit bca852c; the confirm, dismiss, and clear routes were rewired to use it in commit 75a96a1.

Camera desired-state recomputation, restart reconciliation, and cooldown recovery followed in commits 6841433 and 8bceadc.
Lifecycle and camera-side-effect regressions were added in commits b1b2ce1 and df110d4.
The current implementation therefore makes the paper workflow explicit in the database and route behavior rather than relying on separate route-level status edits.

For the defense, describe the paper’s status model first, then explain the newer enforcement: one guarded update, an audit-aware commit, and a post-commit broadcast.

## 6. Limits and honest caveats

The one-minute cooldown is the paper’s specified workflow behavior.
It reduces redundant alerts after a dismissed false positive; it does not prove that the detector will never create another false positive.
The cooldown is tied to a direct Unverified dismissal.

It does not apply after an Ongoing human correction, which resumes an enabled camera immediately.
Only an Ongoing record can be corrected through the normal Dismiss action.
Cleared and Dismissed records are terminal in this workflow; do not promise that an operator can reopen them through the dashboard.

“Resume immediately” assumes that the camera remains enabled.
Administrative disablement still keeps its desired AI state Inactive.
The code has a regression test for competing confirm requests, but the test sends requests in sequence and is not a measured multi-operator load test.

The restart behavior described here is the implemented database reconciliation design.
Do not turn it into a quantitative uptime or recovery-time claim unless the test tracker contains a result for that exact condition.
The paper’s FR-07 says the alarm sounds again if an alert remains Unverified too long and gives 30 seconds as an example.

Do not present that example as a measured response-time result for this state machine.

## 7. Likely panel questions

### “What if two operators click at once?”

Both requests ask the database to change the same incident from its expected status.
Only the update that matches the current status succeeds; the other gets HTTP 409 with the winning action, operator, time, and current status.
The UI tells the losing operator that the incident was already handled and shows who handled it.

### “Why blind your own camera at exactly the moment of the accident?”

The engine pauses that feed before it does snapshot or network work, so delivery delay cannot leave it detecting the same event again.
The backend then records the pause and broadcasts it before the operator can act.

### “Can an operator undo a mistake?”

If the operator mistakenly confirmed an incident and it is still Ongoing, they can dismiss it as a human correction.
That records the correction and resumes an enabled camera immediately.
Cleared and Dismissed records are terminal; the ordinary workflow does not reopen them.

### “What if the operator never responds?”

The incident stays Unverified and the camera stays paused for that incident until a permitted operator action changes the state.
The paper’s FR-07 says the audible alarm re-sounds if the alert remains unverified too long, using 30 seconds as an example.

### “Why have a cooldown after a dismissal?”

A false positive may come from environmental noise that is still present in the next frames.
The one-minute pause avoids immediately repeating the same camera alert and contributing to notification fatigue.

### “What happens to the state machine if the server restarts mid-incident?”

The incident status is stored in the database, so an Ongoing incident remains Ongoing after the backend restarts.
Startup recomputes the camera pause from open incidents; the engine reapplies it from the heartbeat snapshot.
An in-progress false-positive cooldown is rebuilt from its stored deadline.

### “Why not go straight from Unverified to Cleared?”

Cleared means a confirmed incident’s scene has been handled.
Unverified still needs a human decision: confirm it as Ongoing or dismiss it.
Skipping the confirm step would collapse detection and human verification into one decision.

### “Why does a Dismissed alert sometimes pause the camera and sometimes resume it?”

The starting status tells us which decision happened.
An Unverified false-positive dismissal starts the cooldown; an Ongoing dismissal corrects a mistaken confirmation and resumes immediately.

### “What if the backend is unavailable when the AI detects a collision?”

The engine pauses locally before delivery and puts the event in its durable outbox for retry.
While that event is pending, the supervisor does not accept a stale Active snapshot that would resume the feed.
Once delivery succeeds, the backend records the incident and its desired pause.

### “Is the camera itself disabled after Dismiss?”

No. A false-positive dismissal creates a temporary cooldown pause, after which an enabled camera resumes.
An Ongoing correction resumes immediately; an administratively disabled camera remains Inactive.

## 8. Cram summary

- The machine creates **Unverified**; the human decides what the event means.
- The four legal edges are Unverified → Ongoing, Ongoing → Cleared, Unverified → Dismissed, and Ongoing → Dismissed.
- Use **Cleared** for the end of a real incident.
- Only one conditional database update can win a competing transition.
- The loser receives HTTP 409 and sees the current status and who handled the incident.
- The AI pauses locally before snapshot or network work.
- The backend commits the incident and camera pause before broadcasting the alert.
- Direct false-positive dismissal holds the camera for the paper’s one-minute cooldown.
- The deadline is stored in the database and rebuilt after a backend restart.
- An Ongoing-to-Dismissed human correction resumes an enabled camera immediately.
- Terminal incident records do not reopen; a later event is a new record.
- Incident status and camera desired AI state are separate facts.
