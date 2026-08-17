# Handoff — execute the two-machine LAN/TLS drill

**For the session that runs this:** you are executing [`LAN_SETUP.md`](LAN_SETUP.md) for real, on two
physical machines, and writing the results back into the repo. All of the research is already done and
is captured below — do not re-derive it. Read this file, read `LAN_SETUP.md`, then start at Phase A.

Prepared 2026-08-16. Owner: Dani (present at the keyboard for the whole run — this is not an
unattended task).

---

## 1. Goal and definition of done

`be_audit/DEMO_TOPOLOGY.md` §10 and the A1 resolution log in `be_audit/00_FINDINGS.md` both record the
same gap: the A1 LAN/TLS drill ran on **one physical machine**, so every step needing a second
machine's hands was never executed. `be_plan/EVIDENCE.md` carries the consequence — the NFR-04 figure
"measured over the network to a second laptop" is still marked `⏳ owed before the real demo`.

A second machine is now available. **You are closing that gap.**

Done means all of the following, in a **real browser window on the client machine**:

1. `https://adas.local:5173` loads with **no certificate warning**
2. Login as `admin` succeeds and survives navigation (the Secure-cookie path — this is F4 closed on
   real hardware, not on loopback)
3. DevTools shows the WebSocket open with `CONNECTION_READY` received
4. A **live** detection arrives, its snapshot renders, and the camera goes `Paused`
5. Confirm → `Ongoing` → Resolve → camera resumes; a second alert → Dismiss → cooldown → resumes
6. Killing the AI engine drives every fed camera to `Unresponsive` within ~10 s
7. The results are written back into `LAN_SETUP.md`, `be_audit/DEMO_TOPOLOGY.md`,
   `be_audit/00_FINDINGS.md` and `be_plan/EVIDENCE.md` (Phase E)

Not done if any of those was substituted with a loopback or scripted equivalent. The whole point of
this run is that it happens on two machines in a browser.

---

## 2. Read these first, in this order

| File                                       | Why                                                                                      |
| ------------------------------------------ | ---------------------------------------------------------------------------------------- |
| `CLAUDE.md`                                | Run everything from repo root; `uv run python`, never bare `python`                      |
| `LAN_SETUP.md`                             | **The procedure you are executing.** Phases below map onto its steps.                    |
| `be_audit/DEMO_TOPOLOGY.md` §4–§8          | Addressing rationale, known hazards, the fallback ladder if something breaks             |
| `be_audit/A1_lan_tls_drill.md` steps 1–7   | The pack that built the TLS profile; step 6 is the certificate trust story               |
| `be_audit/00_FINDINGS.md` rows F4, F5, F20 | F4 is what this proves; F5 has a browser check still owed; F20 explains the outbox drain |

You do not need to read `be_plan/` beyond `EVIDENCE.md`'s NFR-04 section.

---

## 3. Pre-verified environment — do not spend budget re-checking

Verified on the server laptop on 2026-08-16. Re-check only if something contradicts it.

| Thing                                        | State                                                                                                                                                                  |
| -------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `Ethernet` (Realtek GbE, ifIndex 7)          | **Up at 1 Gbps**, APIPA `169.254.246.182` → cable is live, no DHCP on the link                                                                                         |
| Its network profile                          | **Public / "Unidentified network"** — must be changed to Private (Phase A)                                                                                             |
| `ADAS*` firewall rules                       | none exist yet                                                                                                                                                         |
| Server hosts file                            | no entries                                                                                                                                                             |
| `certs/adas-cert.pem`                        | valid to **Nov 2028**; SANs `adas.local, localhost, 192.168.50.1, 127.0.0.1` → **no regeneration needed**                                                              |
| Live `.env`                                  | LAN keys **already added** 2026-08-16 (`SESSION_COOKIE_SECURE=true`, `CORS_ORIGINS` with the three https origins). `start-dev.ps1 -Lan` preflights them anyway         |
| `SESSION_COOKIE_SECURE` code default         | `True` (`backend/app/core/config.py:33`) — already correct; set explicitly anyway                                                                                      |
| Vite host check                              | `vite@8.2.1` installs `hostValidationMiddleware` **only when `!server.https`** — with the TLS block active, `adas.local` is accepted with **no `allowedHosts` change** |
| `frontend/src/utils/env.ts`                  | already protocol-aware (`https:` → `wss:`); `BACKEND_ORIGIN` derives from it in `frontend/src/api/health.ts:97`                                                        |
| Backend TLS launch                           | the FastAPI CLI has no SSL flags — direct `uvicorn` is the only TLS path                                                                                               |
| AI engine → TLS backend                      | `requests` validates against certifi and ignores the Windows store → `REQUESTS_CA_BUNDLE` is mandatory                                                                 |
| `mediamtx`                                   | **not on `PATH`**; binary at `C:\Users\Dani\OneDrive - dlsl.edu.ph\Desktop\ACADEMICS\mediamtx_v1.18.0_windows_amd64`                                                   |
| `ffmpeg`, `uv`, `pnpm`, `openssl`            | all on `PATH`                                                                                                                                                          |
| clips / weights / `adas.db` / `node_modules` | all present                                                                                                                                                            |
| Admin login                                  | username `admin` (**not** an email) + `DEFAULT_ADMIN_PASSWORD` from `.env`                                                                                             |
| OneDrive (F17)                               | **out of scope — owner's call.** Do not add a "pause OneDrive" step.                                                                                                   |

**No application code changes are needed for this drill.** If you find yourself editing anything under
`backend/app/`, `frontend/src/` or `ai_engine/`, stop and re-read — either you have found a real bug
(record it as a finding) or you have gone off the procedure.

### Addressing

|               | Server (this laptop)    | Client (Windows 10 desktop) |
| ------------- | ----------------------- | --------------------------- |
| IPv4          | `192.168.50.1`          | `192.168.50.2`              |
| Mask          | `255.255.255.0` (`/24`) | `255.255.255.0` (`/24`)     |
| Gateway / DNS | _blank_                 | _blank_                     |

`192.168.50.1` is not arbitrary — the existing certificate lists it as an IP SAN, so both the
`adas.local` path and the raw-IP fallback work without touching the cert.

---

## 4. Division of labour — read this before Phase A

**You (the agent) run server-side commands only.** You have no access to the client machine.

**The owner runs every client-side step by hand**: setting its static IP, copying and installing the
certificate, editing its hosts file, and everything in a browser window. For each of those, state
exactly what to do, then **ask and wait for the result**. Do not assume a client step succeeded, and do
not proceed past a failed check.

Phase A's networking and firewall commands need an **elevated** shell. Test whether yours is elevated:

```powershell
([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
```

If it returns `False`, hand the owner a single copy-paste block for the elevated commands rather than
attempting them and reporting a confusing failure.

Long-running processes (Phase C) should be started in the background so you can keep reading their
logs — do not block a foreground call on a server that never exits.

---

## 5. Phase A — Server preparation

1. **Static address on `Ethernet`** (elevated). Confirm the adapter name first with `Get-NetAdapter`
   — do not touch Wi-Fi, `Ethernet 3` (VirtualBox) or `vEthernet (Default Switch)` (Hyper-V).

   ```powershell
   $If = "Ethernet"
   Remove-NetIPAddress -InterfaceAlias $If -AddressFamily IPv4 -Confirm:$false -ErrorAction SilentlyContinue
   Remove-NetRoute -InterfaceAlias $If -AddressFamily IPv4 -Confirm:$false -ErrorAction SilentlyContinue
   New-NetIPAddress -InterfaceAlias $If -IPAddress 192.168.50.1 -PrefixLength 24
   Set-DnsClientServerAddress -InterfaceAlias $If -ResetServerAddresses
   ```

2. **Profile and firewall** (elevated). Run these **after** the address change — Windows regenerates
   the connection profile when addressing changes and it comes back Public.

   ```powershell
   Set-NetConnectionProfile -InterfaceAlias "Ethernet" -NetworkCategory Private
   New-NetFirewallRule -DisplayName "ADAS 8000" -Direction Inbound -LocalPort 8000 -Protocol TCP -Action Allow -Profile Private
   New-NetFirewallRule -DisplayName "ADAS 5173" -Direction Inbound -LocalPort 5173 -Protocol TCP -Action Allow -Profile Private
   New-NetFirewallRule -DisplayName "ADAS ICMPv4 Echo" -Direction Inbound -Protocol ICMPv4 -IcmpType 8 -Action Allow -Profile Private
   ```

3. **`.env`** — already done on 2026-08-16; confirm rather than re-add. It should carry:

   ```
   SESSION_COOKIE_SECURE=true
   CORS_ORIGINS=https://adas.local:5173,https://192.168.50.1:5173,https://localhost:5173
   ```

   If you do need to edit it, append — do not rewrite the file, and do not print secret values
   (`SECRET_KEY`, `INTERNAL_API_KEY`, `DEFAULT_ADMIN_PASSWORD`, `DSS_*`) into the transcript.

**Gate:** `Get-NetConnectionProfile -InterfaceAlias "Ethernet"` reads `Private`, `Get-NetIPAddress`
shows `192.168.50.1`, and `Get-NetFirewallRule -DisplayName "ADAS*"` lists four enabled rules. Do not
continue until all three hold.

`start-dev.ps1 -Lan` re-checks the `.env` half of this in its preflight and reports the firewall and
per-interface profile state, so Phase C's output doubles as a second check on this phase.

---

## 6. Phase B — Client preparation (owner runs these)

Hand these over one at a time and confirm each before giving the next.

1. Static `192.168.50.2/24` on the client's Ethernet adapter, **no gateway, no DNS**.
2. `ping 192.168.50.1` from the client → replies. **This is the gate for the whole drill.** If it
   fails, the problem is Phase A step 1 or 2, or the cable — not the application.
3. Copy `certs/adas-cert.pem` to the client. **Only the certificate. Never `adas-key.pem`** — and say
   so explicitly when you hand this step over.
4. On the client: double-click the `.pem` → Install Certificate → **Local Machine** → "Place all
   certificates in the following store" → **Trusted Root Certification Authorities**.
5. Add `192.168.50.1  adas.local` to `C:\Windows\System32\drivers\etc\hosts` (elevated Notepad), then
   `ipconfig /flushdns`.
6. `ping adas.local` → prints `Pinging adas.local [192.168.50.1]`.

**Gate:** step 2 and step 6 both pass. Certificate trust is not verifiable until Phase D — a warning
at 7.5 in `LAN_SETUP.md` means step 4 was done into the wrong store.

---

## 7. Phase C — Bring up the stack (server, repo root)

One command. `-Lan` starts all four components over TLS in the correct order, each in its own window:

```powershell
pwsh -File scripts/start-dev.ps1 -Lan -MediaMtxDir "C:\Users\Dani\OneDrive - dlsl.edu.ph\Desktop\ACADEMICS\mediamtx_v1.18.0_windows_amd64"
```

Its preflight blocks on a missing/expired certificate and on a `.env` without the LAN keys, prints the
certificate's SANs and expiry, and then lists every address a client could reach the dashboard on —
flagging any interface whose firewall profile would block it. Read that output; it is the fastest
check that Phase A actually took effect.

`-MediaMtxDir` is only needed because MediaMTX is not on `PATH` on this machine. The full manual
equivalent, with the rationale for every flag, is in `LAN_SETUP.md` §6 — read it if you need to run one
component in isolation, but **do not improvise alternatives** to those commands.

Verify as you go: RTSP plays → `https://localhost:8000/healthz/ready` returns 200 → Vite prints its
HTTPS URLs → the backend log shows heartbeats being accepted.

**Hard gate:** on the **server's own browser**, every fed and enabled camera reads
**`Connected` / `Active`**. If anything reads `Reconnecting`, stop and fix it before the client is
involved at all — debugging it from the client only adds variables. Note that `mediamtx.yml` defines
five channels while the seeded database has six cameras; the sixth has no feed by design and is not a
defect.

---

## 8. Phase D — The client drill

The owner drives the browser; you read server logs alongside and correlate. Follow `LAN_SETUP.md` §7,
then the incident workflow. Stop at the first failure and diagnose rather than pressing on.

Two extra items beyond the plain runbook:

**F5 re-verification (owed, worth closing).** Trigger a CSV export from the dashboard UI on the client
and check whether the saved file uses the **server's** `Content-Disposition` filename or a generic
fallback. `00_FINDINGS.md`'s F5 row says the fix is in but that "browser-level re-verification over the
LAN/TLS profile is still owed" — this is the run that can close it. Record the actual saved filename.

**LAN NFR-04 measurement (optional, and only if honest).** `be_plan/EVIDENCE.md` wants a real
two-machine alert-delivery figure. Both machines keep Wi-Fi up, so:

1. `w32tm /resync` on both, against the same source, and record the residual offset.
2. Only if the offset is small enough that a sub-2-second measurement means anything, capture the
   delta between an event's `occurred_at` and its arrival time on the client.
3. **If the clocks cannot be aligned well enough, write "not captured" and why.** Do not publish a
   number the method cannot support. `EVIDENCE.md` already carries a precedent for exactly this —
   the previous pass refused to manufacture a LAN figure and said so in the file.

---

## 9. Phase E — Write the results back

Nothing counts until this is done. Four files:

1. **`LAN_SETUP.md`** — correct any step that turned out wrong, and add anything that cost you time to
   the troubleshooting table. This is the document's whole purpose; a step that was subtly wrong and
   got silently worked around is the worst possible outcome.
2. **`be_audit/DEMO_TOPOLOGY.md` §10** — replace "What is still owed on real hardware" with a dated
   two-machine drill log: what ran, what was observed, what failed. Keep §10's existing single-machine
   history above it; do not delete it.
3. **`be_audit/00_FINDINGS.md`** — append one dated line to the resolution log. Update the **F5** row
   if the export filename was verified in a real browser. Add `F32`, `F33`… for anything new, naming
   this drill as the source. Do not delete rows; a finding leaves `open` only by being fixed or by
   being recorded as an accepted gap with a written rationale.
4. **`be_plan/EVIDENCE.md`** — update the "LAN-measured NFR-04 — still owed" section with either the
   real figure and its method, or an honest note that the two-machine drill ran and why the timing
   figure still was not captured.

Then walk `LAN_SETUP.md` §11 with the owner to shut down and revert both machines.

---

## 10. Guardrails

- **Do not regenerate the certificate.** It is valid to Nov 2028 and already covers every address in
  use. Regenerating means re-installing on every client.
- **Do not add `allowedHosts` to `frontend/vite.config.ts`.** Vite skips its host check when HTTPS is
  on; the option would imply a problem that does not exist.
- **Never copy `adas-key.pem` to the client**, or to a USB stick, or anywhere else. Certificate only.
- **Do not set `SESSION_COOKIE_SECURE=false`** to "fix" a login failure. It does not fix it and it
  makes the cookie insecure.
- **Do not edit `ai_engine/adas_transfer/`** — it is the frozen parity reference.
- **`be_plan/` is append-only** — add dated notes, never rewrite existing text.
- **Do not fabricate measurements.** "Not captured, because X" is a valid and expected result.
- **Record failures as findings**, in `00_FINDINGS.md`, rather than working around them silently. A
  drill that finds two real problems is more valuable than one that reports a clean sweep.
- **Do not print secrets** (`SECRET_KEY`, `INTERNAL_API_KEY`, `DEFAULT_ADMIN_PASSWORD`, `DSS_*`) into
  the transcript when working with `.env`.

---

## 11. Commits and gates

Conventional Commits, enforced by commitlint on `commit-msg`:

- `docs(ops):` — `LAN_SETUP.md` updates
- `docs(audit):` — `be_audit/` and `be_plan/EVIDENCE.md` updates

`LAN_SETUP.md` and this file live at the repo root, so **they are scanned by `prettier --check .`** in
the `pnpm check` pre-push gate (`.prettierignore` excludes `be_plan/` and `be_audit/`, not the root).
After editing either, run:

```bash
pnpm exec prettier --write LAN_SETUP.md LAN_DEMO_HANDOFF.md
```

Per the repo's verification policy: do not run `pnpm check` manually before pushing — `.husky/pre-push`
already runs it. This drill changes no application code, so there is no test scope to run beyond that.
