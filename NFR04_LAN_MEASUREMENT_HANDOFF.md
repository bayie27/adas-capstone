# Handoff — get a genuine two-machine LAN NFR-04 figure

**For the session that runs this:** the two-machine LAN/TLS drill (`LAN_DEMO_HANDOFF.md`) ran in full
on 2026-08-17 — every other item is closed. The one thing it could not produce honestly is a real
**NFR-04 alert-delivery latency figure measured over the actual LAN link**, between the two physical
machines. This handoff is scoped to exactly that one number. Read this file, then
`be_plan/EVIDENCE.md`'s "LAN-measured NFR-04" section (search for that heading) for the full account
of what was already tried and why it didn't land — do not re-derive that reasoning, and in particular
do not repeat the one approach already known to fail (see §3 below).

Prepared 2026-08-17. Owner: Dani (present at the keyboard — the client-side steps need a second
machine's hands, same as the original drill).

---

## 1. Goal and definition of done

`be_plan/EVIDENCE.md`'s NFR-04 row currently reads "not captured" for the real two-laptop LAN case.
Every other figure in that table is measured; this is the one gap. Done means:

1. A **real** number — time from an event's `occurred_at` (as embedded in the `NEW_DETECTION`
   WebSocket payload) to the moment it's received on the **client** machine, over the actual
   `192.168.50.1` ↔ `192.168.50.2` link, not loopback.
2. The method is defensible — sub-second precision, not a human eyeballing two screens.
3. `be_plan/EVIDENCE.md`, `be_audit/DEMO_TOPOLOGY.md` §11, and `be_audit/00_FINDINGS.md`'s
   resolution log are updated with the real figure and the method, replacing "not captured."

If, after a genuine attempt, the number still can't be produced defensibly — **say so and why**,
same as the previous two passes did. Do not publish a number the method can't support.

---

## 2. Current physical state — read before touching anything

Both machines were **deliberately left set up** after the 2026-08-17 drill, specifically so a
follow-up session like this one wouldn't need to redo the physical setup:

| Thing                   | State                                                                                                                            |
| ----------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| Server (`192.168.50.1`) | Static IP, `Private` profile, three `ADAS*` firewall rules — all still in place                                                  |
| Client (`192.168.50.2`) | Static IP, hosts entry (`192.168.50.1 adas.local`), certificate trusted in **Local Machine → Trusted Root** — all still in place |
| Application stack       | **Stopped.** `stop-dev.ps1` was run at the end of the drill; nothing is listening on 8000/5173/8554                              |
| Database                | **Freshly reseeded** via `backend/scripts/reseed_dev.py` (demo profile) — no leftover incidents from the drill                   |
| Physical cable          | Still connected between the two machines                                                                                         |

So Phase A and Phase B of the original drill (`LAN_DEMO_HANDOFF.md`) are **already done** — don't
repeat them. If a `ping 192.168.50.1` from the client fails, or `Get-NetConnectionProfile` on the
server doesn't read `Private`, treat that as drift since 2026-08-17 (see F32 in `00_FINDINGS.md` —
the profile is known to revert spontaneously) and fix it before going further, but don't reassign
IPs or reinstall the certificate unless something is actually wrong.

Bring the stack up the same way the original drill did:

```powershell
pwsh -File scripts/start-dev.ps1 -Lan -MediaMtxDir "C:\Users\Dani\OneDrive - dlsl.edu.ph\Desktop\ACADEMICS\mediamtx_v1.18.0_windows_amd64"
```

Verify the same Phase C hard gate as before: every fed, enabled camera reads `Connected` on the
server's own browser (channel 6/Dagatan has no feed by design; North Exit has detection disabled by
design — both are expected exceptions, not defects).

---

## 3. What was already tried, and must not be repeated blind

Two independent attempts failed in the 2026-08-17 session. Read the full account in
`be_plan/EVIDENCE.md`'s NFR-04 section; summary:

1. **`w32tm /resync` needs an elevated shell**, which the agent didn't have that session. If you
   have one, this is worth doing early — tighter clock sync makes any method's error bars smaller.
   Not a blocker on its own; the method below doesn't strictly need synced clocks (see §4).
2. **Do not wrap `window.WebSocket` in a `Proxy` from the browser console.** This was tried as a
   way to log the delta between each message's server-side `occurred_at` and the client's
   high-resolution receive time, using `CONNECTION_READY` as a clock-skew calibration point. On
   reload it broke the live WebSocket connection entirely (`/ws/alerts` failed to establish, and
   Vite's own HMR socket failed too) instead of producing a number. Proxying the native `WebSocket`
   constructor is not safe to do against a page whose own code also constructs one. If a
   browser-console approach is worth retrying at all, it would need to avoid replacing the global
   constructor — e.g. patching `WebSocket.prototype.addEventListener` instead of the constructor —
   but this was not attempted and is unproven.

---

## 4. Recommended approach — reuse A3's own loopback method, just over the real link

The existing **loopback** NFR-04 figure in `EVIDENCE.md` (~0.53s, ~0.84s, well under the 2s budget)
was produced by a real WebSocket client script — not `TestClient`, not the browser — logging
wall-clock receive time against each event's `occurred_at`. That method already works and is already
trusted enough to be published. The straightforward move is to **run the same kind of script from
the client machine, pointed at the real LAN address instead of loopback**:

1. On the **client**, with Python available (or run it as a `uv run python` one-off if the repo is
   also checked out there — otherwise a bare `pip install websockets` in a throwaway venv is enough,
   since this script has no dependency on the app's own code):
   - `POST` to `https://adas.local:8000/api/auth/login` with form-encoded `username=admin` and
     `password=<DEFAULT_ADMIN_PASSWORD from the server's .env>` (this is `OAuth2PasswordRequestForm`
     — form data, not JSON; see `backend/app/api/routes/auth.py`) to get the session cookie.
   - Open a `websockets` connection to `wss://adas.local:8000/ws/alerts`, with
     `ssl.create_default_context(cafile="path/to/adas-cert.pem")` for TLS verification and the
     session cookie attached as a header.
   - For every message received, record `time.time()` (or `datetime.now(UTC)`) immediately, parse
     the JSON, and compare against the message's own `occurred_at` field. Every event envelope has
     one (`backend/app/schemas/events.py`) — `CONNECTION_READY` first, then `NEW_DETECTION` as
     alerts fire.
2. This script is **independent of the operator dashboard** — it doesn't touch the browser, doesn't
   share a WebSocket connection with anything else, and can't break the live UI the way the console
   patch did. Run it alongside the dashboard, not instead of it.
3. Since the feed loops crash footage, detections fire repeatedly without needing to force anything
   — just let the script sit connected for a minute or two and it will see several `NEW_DETECTION`
   events.
4. If clock skew between the two machines is a concern, use the same self-calibration idea that was
   planned for the browser-console approach: the delta measured for `CONNECTION_READY` (the very
   first message) is a skew estimate; subtract it from each subsequent event's raw delta. This works
   because both `occurred_at` values come from the same server clock, so a constant per-session skew
   cancels out even without a perfect `w32tm` sync.
5. Report the **raw range** of measured deltas (not just one number), same style as the existing
   loopback figures, and note however many samples were taken.

If this script approach also fails for some reason not anticipated here, fall back to the honest
"not captured, because X" outcome — don't force a number.

---

## 5. Write the result back

Same three files the original drill updated, same conventions (dated entries, don't rewrite
existing text in `be_plan/` or delete rows in `00_FINDINGS.md`):

1. **`be_plan/EVIDENCE.md`** — replace the "LAN-measured NFR-04 — attempted 2026-08-17, still not
   captured" section's content with the real figure and method, and update the summary table row.
2. **`be_audit/DEMO_TOPOLOGY.md` §11** — add a dated note under the existing 2026-08-17 log entry
   (don't delete or rewrite it) recording that the NFR-04 gap it left open is now closed, with the
   figure and method.
3. **`be_audit/00_FINDINGS.md`** — append one dated resolution-log line.

---

## 6. Guardrails

- **No application code changes are needed for this.** The measurement script lives outside the
  repo's own runtime path (a throwaway script, not committed) — if you find yourself editing
  `backend/app/`, `frontend/src/`, or `ai_engine/`, stop and reconsider; that's out of scope here.
- **Do not fabricate a number.** "Not captured, because X" is a valid, expected, and already
  twice-precedented outcome in this file's history if the genuine attempt doesn't pan out.
- **Don't print secrets** (`DEFAULT_ADMIN_PASSWORD`, `SECRET_KEY`, `INTERNAL_API_KEY`, `DSS_*`) into
  the transcript.
- **`be_plan/` is append-only.**
- Both machines are expected to stay in their current LAN/TLS-configured state until after the real
  demo — see the 2026-08-17 drill's conversation for why (informal decision, not written elsewhere):
  reverting and re-setting-up twice is more risk than leaving it configured on dedicated hardware.
  Don't run the `LAN_SETUP.md` §11 revert steps as part of this task.
