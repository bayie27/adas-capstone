# Connecting a client machine to the ADAS server over the LAN

How to run this project on one machine (the **server**) and reach the operator dashboard from a
second machine (the **client**) over HTTPS and WSS, on a wired link with no internet involved.

This is the procedure. For _why_ it is built this way — the Lipa CDRRMO topology it reproduces, why
cloud tunnels are disqualified by NFR-20, the fallback ladder, and the demo-day narrative — read
[`be_audit/DEMO_TOPOLOGY.md`](be_audit/DEMO_TOPOLOGY.md) instead. This document assumes that decision
is already made and just gets you connected.

> **Everything runs on the server.** MediaMTX, ffmpeg, the AI engine, the backend and the frontend
> all live on the server machine, exactly as they would all live on the edge server in production.
> The client is a browser and nothing else.

---

## Contents

1. [What you need](#1-what-you-need)
2. [Why a hostname and not an IP](#2-why-a-hostname-and-not-an-ip)
3. [Step 1 — Physical link and addressing](#step-1--physical-link-and-addressing)
4. [Step 2 — Server OS preparation](#step-2--server-os-preparation)
5. [Step 3 — Certificate](#step-3--certificate)
6. [Step 4 — Client name resolution](#step-4--client-name-resolution)
7. [Step 5 — Server environment file](#step-5--server-environment-file)
8. [Step 6 — Bring up the stack](#step-6--bring-up-the-stack)
9. [Step 7 — Verify from the client](#step-7--verify-from-the-client)
10. [Troubleshooting](#troubleshooting)
11. [After the demo — shut down and revert](#after-the-demo--shut-down-and-revert)

---

## 1. What you need

**Server machine** (this repo, Windows)

- The repo checked out, `uv sync --extra ai` and `pnpm install` already done
- `certs/adas-cert.pem` + `certs/adas-key.pem` (see [Step 3](#step-3--certificate))
- `ffmpeg` and `mediamtx` available (mediamtx may need adding to `PATH` — see Step 6)
- An **elevated PowerShell** for the network and firewall steps
- Model weights at `ai_engine/epoch50.pt` and clips in `ai_engine/eval/clips/`

**Client machine** (Windows 10/11)

- Administrator rights (static IP, hosts file, certificate install)
- **Edge or Chrome.** Firefox keeps its own certificate store and needs a separate import.
- A copy of `adas-cert.pem` — **the certificate only, never `adas-key.pem`**

**Link**

- One Cat5e/Cat6 patch cable. Modern NICs are auto-MDIX; you do _not_ need a crossover cable.
- USB-C→Ethernet dongles if either machine lacks a port.

**Ports that cross the link: `8000` and `5173`. That is all.** RTSP (`8554`) stays entirely on the
server — the AI engine and MediaMTX are both local to it.

| Port   | Serves                     | Crosses the link? |
| ------ | -------------------------- | ----------------- |
| `8000` | Backend API + `/ws/alerts` | **yes**           |
| `5173` | Frontend dashboard (Vite)  | **yes**           |
| `8554` | MediaMTX RTSP              | no — server-local |

---

## 2. Why a hostname and not an IP

The certificate is issued to the hostname **`adas.local`**, and the client resolves that name with a
single line in its hosts file.

A certificate pinned only to an IP address dies the moment the address changes — a different venue, a
different cable, a fallback to a phone hotspot — and **you cannot click past a certificate error on a
`wss://` handshake**. With a hostname, changing networks is a one-line hosts-file edit instead of
regenerating and re-trusting a certificate under pressure.

The certificate in this repo lists `adas.local`, `localhost`, `192.168.50.1` and `127.0.0.1`, so the
raw-IP URL works too as a fallback, and the same certificate covers running everything on one machine
at `https://localhost:5173`.

---

## Step 1 — Physical link and addressing

Connect the cable. Confirm a link light at both ends, and that the adapter reads "Network" rather
than "Unplugged".

### Direct cable between two machines (the default)

There is no DHCP server on a two-node cable, and the APIPA addresses Windows falls back to
(`169.254.x.x`) change between boots. **Assign static addresses on both ends.**

|             | Server                  | Client                  |
| ----------- | ----------------------- | ----------------------- |
| IPv4        | `192.168.50.1`          | `192.168.50.2`          |
| Subnet mask | `255.255.255.0` (`/24`) | `255.255.255.0` (`/24`) |
| Gateway     | _leave blank_           | _leave blank_           |
| DNS         | _leave blank_           | _leave blank_           |

Leaving the gateway blank is deliberate: it stops Windows trying to route internet traffic over the
demo link, so **both machines keep working normally on Wi-Fi at the same time**.

First find the adapter's name — it is not always `Ethernet`, and you must not edit the Wi-Fi adapter
or a virtual one (Hyper-V, VirtualBox and WSL all create adapters that look plausible):

```powershell
Get-NetAdapter | Where-Object Status -eq 'Up' | Select-Object Name, InterfaceDescription, LinkSpeed
```

Then, in an **elevated** PowerShell on each machine (substituting its own address):

```powershell
$If = "Ethernet"   # the adapter name from the command above
Remove-NetIPAddress -InterfaceAlias $If -AddressFamily IPv4 -Confirm:$false -ErrorAction SilentlyContinue
Remove-NetRoute -InterfaceAlias $If -AddressFamily IPv4 -Confirm:$false -ErrorAction SilentlyContinue
New-NetIPAddress -InterfaceAlias $If -IPAddress 192.168.50.1 -PrefixLength 24
Set-DnsClientServerAddress -InterfaceAlias $If -ResetServerAddresses
```

**Check:** `ipconfig` shows `192.168.50.1` (server) / `192.168.50.2` (client) on the right adapter,
with no default gateway listed for it.

### Variant — both machines into a switch or router

Still wired, still a faithful reproduction of production. Two differences:

- If the switch/router runs DHCP, let both machines take DHCP addresses and just read the server's
  with `ipconfig`. It will not be `192.168.50.1`.
- The client's hosts entry ([Step 4](#step-4--client-name-resolution)) must point `adas.local` at
  whatever the server's actual address turned out to be. **Nothing else changes** — this is the whole
  reason the certificate is issued to a hostname.

Venue Wi-Fi is deliberately not an option here: institutional networks commonly enable AP/client
isolation, which blocks machine-to-machine traffic entirely while everything still _looks_ connected,
and you cannot fix it from your side.

---

## Step 2 — Server OS preparation

**Both of the following fail silently if skipped.** No error appears on either machine; the client
simply hangs. This is the single most common cause of a setup that looks broken for no reason.

Run in an **elevated PowerShell** on the server:

```powershell
Set-NetConnectionProfile -InterfaceAlias "Ethernet" -NetworkCategory Private
New-NetFirewallRule -DisplayName "ADAS 8000" -Direction Inbound -LocalPort 8000 -Protocol TCP -Action Allow -Profile Private
New-NetFirewallRule -DisplayName "ADAS 5173" -Direction Inbound -LocalPort 5173 -Protocol TCP -Action Allow -Profile Private
New-NetFirewallRule -DisplayName "ADAS ICMPv4 Echo" -Direction Inbound -Protocol ICMPv4 -IcmpType 8 -Action Allow -Profile Private
```

Why each line matters:

- **The profile.** A gateway-less link is classified "Unidentified network" → **Public** → Windows
  drops inbound connections with no error at either end.
- **The two port rules.** Scoping them to `-Profile Private` means they apply on this wired link and
  **not** on the café Wi-Fi you join tomorrow.
- **The ICMP rule.** Windows does not answer ping by default. Without it `ping 192.168.50.1` fails
  from the client even when everything else works perfectly — which sends you debugging a problem you
  do not have.

> **Re-run `Set-NetConnectionProfile` after any addressing change — and be ready to re-run it even
> without one.** Windows regenerates the profile when the adapter's address changes, and it comes
> back as Public. A live two-machine drill (2026-08-17) also saw it revert to Public **mid-session
> with no addressing change at all**. The symptom looks exactly like a cabling or routing problem —
> `ping adas.local` resolves the name correctly but every reply times out — so if something that was
> working suddenly stops, check `Get-NetConnectionProfile` before anything else.

**Check:**

```powershell
Get-NetConnectionProfile -InterfaceAlias "Ethernet"   # NetworkCategory must read Private
Get-NetFirewallRule -DisplayName "ADAS*" | Select-Object DisplayName, Enabled, Profile
```

---

## Step 3 — Certificate

TLS is not decoration here. The session cookie is issued `Secure`, and browsers grant the
Secure-cookie exemption to `localhost` **only** — never to a LAN address. Over plain `http://`, login
returns 200, the cookie is silently discarded, and every subsequent request is a 401 that looks
exactly like an auth bug. Real TLS is what makes the LAN path work at all.

### 3a. Check whether the existing certificate already covers you

```bash
openssl x509 -in certs/adas-cert.pem -noout -text | grep -A1 "Subject Alternative Name"
openssl x509 -in certs/adas-cert.pem -noout -enddate
```

If the SAN list contains `DNS:adas.local` and the expiry is in the future, **you are done — skip to
3c.** Regenerating unnecessarily means re-installing on every client.

### 3b. Regenerate only if needed

From Git Bash, at the repo root:

```bash
mkdir -p certs && MSYS_NO_PATHCONV=1 openssl req -x509 -newkey rsa:2048 -sha256 -days 825 -nodes \
  -keyout certs/adas-key.pem -out certs/adas-cert.pem -subj "/CN=adas.local" \
  -addext "subjectAltName=DNS:adas.local,DNS:localhost,IP:192.168.50.1,IP:127.0.0.1"
```

Three gotchas, each worth an hour if you hit it blind:

- **`MSYS_NO_PATHCONV=1` is required.** Git Bash otherwise rewrites `/CN=...` into a Windows path.
- **825 days is the maximum** Safari/iOS accept. Longer certificates are rejected outright.
- **A CN-only certificate is rejected by every current browser** — the SANs are mandatory, not
  belt-and-braces. Include `localhost`/`127.0.0.1` so the same certificate covers the single-machine
  fallback with no reconfiguration.

`certs/` is gitignored. A private key in git history is not recoverable from — keep it that way.

### 3c. Install it on the client

1. Copy **`adas-cert.pem` only** to the client. **Never copy `adas-key.pem`.** The client needs to
   recognise the certificate, not to be able to issue one.
2. Double-click it → **Install Certificate** → **Local Machine** → "Place all certificates in the
   following store" → **Trusted Root Certification Authorities**.
   - **If double-click doesn't offer the import wizard** (seen on one client in the 2026-08-17
     two-machine drill), use the `mmc` snap-in instead: `Win+R` → `mmc` → File → Add/Remove
     Snap-in → **Certificates** → Add → **Computer account** → **Local computer** → OK. Then
     navigate to Certificates → Trusted Root Certification Authorities → Certificates, right-click
     → All Tasks → Import, and select the `.pem` (rename to `.cer` first if the file picker won't
     show it — Windows sniffs the content, not the extension, so this is safe). Same destination
     store, equally valid.
3. Use **Edge or Chrome**, and restart it after installing the certificate — some browsers cache
   the trust store at launch.

**This step is what makes `wss://` work.** If you instead click through a browser warning for `:5173`,
the dashboard will load and the WebSocket will fail **silently** — no events, no error, nothing in the
console that names the cause. That symptom always means this step was skipped or done wrong.

If you are ever forced to click through warnings instead, you must visit `https://adas.local:8000/`
once and accept it **separately** from `:5173`. Treat that as a last resort, not a shortcut.

---

## Step 4 — Client name resolution

Open `C:\Windows\System32\drivers\etc\hosts` in an **elevated** editor (right-click Notepad → Run as
administrator; it cannot save the file otherwise) and add one line:

```
192.168.50.1  adas.local
```

Then flush the cache:

```powershell
ipconfig /flushdns
```

**Check:** `ping adas.local` prints `Pinging adas.local [192.168.50.1]`. The address in the brackets
is the part that matters — if replies time out but the address is right, resolution works and you
have an ICMP rule missing, not a name problem.

> **No admin rights on the client?** Skip this step and browse `https://192.168.50.1:5173` instead —
> the certificate covers that IP. You will need `https://192.168.50.1:5173` present in the server's
> `CORS_ORIGINS` (it is, in the block below), and the certificate installed into the **Current User**
> Trusted Root store, which Edge and Chrome honour without elevation.

---

## Step 5 — Server environment file

Add these to the repo-root `.env` on the **server**:

```
SESSION_COOKIE_SECURE=true
CORS_ORIGINS=https://adas.local:5173,https://192.168.50.1:5173,https://localhost:5173
```

What each one does, and what its absence looks like:

| Key                     | Why                                                                                                                                                                                                                    |
| ----------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `SESSION_COOKIE_SECURE` | Already defaults to `true` in code; set it explicitly so nobody "fixes" a LAN login failure by turning it off. Turning it off does not help — it makes the cookie insecure _and_ still fails.                          |
| `CORS_ORIGINS`          | Used by **three** independent gates: `CORSMiddleware`, the origin-validation middleware (403 `ORIGIN_REJECTED` on any write), and the WebSocket handshake (immediate close). A mismatch here breaks all three at once. |

Origins are matched **exactly** — scheme, host and port, no trailing slash. `https://adas.local:5173`
and `https://192.168.50.1:5173` are different origins; include both so the fallback in Step 4 works.
Keeping `https://localhost:5173` lets you test on the server itself.

A commented **LAN demo profile** block already exists in `.env.example` if you would rather copy it
from there.

---

## Step 6 — Bring up the stack

### One command

```powershell
pwsh -File scripts/start-dev.ps1 -Lan
```

`-Lan` starts all four components over TLS, each in its own titled window, in the bring-up order
below. It preflights the two things that otherwise fail _silently_ — a missing or expired certificate,
and a `.env` without the LAN keys — then prints every address a client could reach the dashboard on,
flagging any interface whose firewall profile would block it.

If MediaMTX is not permanently on your `PATH` (it usually is not — it ships as a bare binary), point
the script at it once:

```powershell
pwsh -File scripts/start-dev.ps1 -Lan -MediaMtxDir "C:\path\to\mediamtx_v1.18.0_windows_amd64"
```

or set `ADAS_MEDIAMTX_DIR` in your environment and drop the flag. `-CertDir` overrides the certificate
location if it is not `certs/`. All the usual switches still work: `-Lan -Backend` starts only the
backend over TLS, `-Lan -Reseed demo` reseeds first.

**What `-Lan` does not do:** the OS-level work in Steps 1, 2 and 4 — static IPs, the Private connection
profile, firewall rules, the client's hosts entry and certificate trust. None of that is safe to do
implicitly to someone's machine, so it stays manual and stays yours.

Tear down with `pwsh -File scripts/stop-dev.ps1`, unchanged — it resolves processes by listening port,
so the TLS-launched ones stop exactly like the plain ones.

### The same thing by hand

Useful when you need one component in isolation, or to understand what `-Lan` is actually running. All
commands from the **repo root**, on the server, each in its own terminal, in this order — verify each
before moving to the next.

### 6.1 — Camera simulator (MediaMTX + ffmpeg)

```powershell
$env:PATH = "C:\Users\Dani\OneDrive - dlsl.edu.ph\Desktop\ACADEMICS\mediamtx_v1.18.0_windows_amd64;$env:PATH"
.\scripts\start-sim.ps1
```

`start-sim.ps1` hard-fails if `mediamtx` or `ffmpeg` are not on `PATH`; the first line handles
MediaMTX. It reads `mediamtx.yml`, which publishes five channels from `ai_engine/eval/clips/`.

**Check:** `rtsp://localhost:8554/channel1` plays in VLC or `ffplay`.

### 6.2 — Backend over TLS

```powershell
$env:PYTHONUTF8 = "1"
uv run uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000 `
  --ssl-keyfile certs/adas-key.pem --ssl-certfile certs/adas-cert.pem `
  --ws-ping-interval 20 --ws-ping-timeout 20
```

`--app-dir backend` replaces what the FastAPI CLI normally does for `sys.path`. The two `--ws-ping-*`
flags pin the WebSocket keepalive that would otherwise be an unstated library default — this is the
only launch path in the repo that _can_ pin it.

**Check:** the log reads `Uvicorn running on https://0.0.0.0:8000`, and `https://localhost:8000/healthz/ready`
returns 200 on the server's own browser.

### 6.3 — Frontend over TLS

```powershell
cd frontend
$env:ADAS_TLS_CERT_DIR = "../certs"
pnpm dev
```

The `server` block in `frontend/vite.config.ts` activates only when `ADAS_TLS_CERT_DIR` is set, so
ordinary `pnpm dev`, `pnpm build` and the Playwright config are unaffected.

**Check:** Vite prints `https://localhost:5173/` and a network address, and the page loads on the
server itself.

> **Do not add `allowedHosts` to `vite.config.ts`.** Vite installs its host-check middleware only when
> HTTPS is off, so `adas.local` is accepted as-is under this profile. Adding the option is harmless but
> misleading — it implies a problem that does not exist here.

### 6.4 — AI engine

```powershell
$env:AI_BACKEND_BASE_URL = "https://127.0.0.1:8000"
$env:REQUESTS_CA_BUNDLE  = (Resolve-Path .\certs\adas-cert.pem).Path
uv run python ai_engine/main.py
```

`REQUESTS_CA_BUNDLE` is not optional. The AI engine talks to the backend with `requests`, which
validates against the certifi bundle and **ignores the Windows certificate store** — so installing the
certificate into Trusted Root on the server does nothing for it. Without this variable every heartbeat
and every alert fails TLS verification.

**Check:** the backend log shows heartbeats being accepted, and on the server's own browser every fed,
enabled camera reads **Connected / Active**.

### 6.5 — The gate

**If any camera still reads `Reconnecting`, stop here and fix it before touching the client.** Nothing
downstream will work, and debugging it from the client machine only adds variables.

---

## Step 7 — Verify from the client

Work top to bottom. Each step's failure has a different cause, so do not skip ahead.

| #   | Do                                             | Expect                                                                                             |
| --- | ---------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| 7.1 | `ping 192.168.50.1`                            | Replies. Failure here is Step 1 or the ICMP rule in Step 2.                                        |
| 7.2 | `ping adas.local`                              | Resolves to `192.168.50.1` (check the bracketed address). Step 4.                                  |
| 7.3 | `Test-NetConnection adas.local -Port 8000`     | `TcpTestSucceeded : True`. Failure with 7.1 passing is Step 2.                                     |
| 7.4 | `Test-NetConnection adas.local -Port 5173`     | `TcpTestSucceeded : True`.                                                                         |
| 7.5 | Browse `https://adas.local:8000/healthz/ready` | `200`, and **no certificate warning at all**. A warning means Step 3c.                             |
| 7.6 | Browse `https://adas.local:5173`               | Login page renders.                                                                                |
| 7.7 | Log in as `admin`                              | Dashboard loads and **stays** logged in when you navigate. This is the Secure-cookie path working. |
| 7.8 | DevTools → Network → **WS**                    | Connection open, `CONNECTION_READY` received.                                                      |
| 7.9 | Wait for a detection                           | Alert appears in under 2 s, snapshot renders, the camera goes `Paused`.                            |

The login is the username `admin` — **not an email** — with `DEFAULT_ADMIN_PASSWORD` from the server's
`.env`.

Then exercise the incident workflow, which is the part a panel will ask about:

- **Confirm** → status `Ongoing`, camera stays paused.
- **Resolve** → camera resumes immediately.
- **Dismiss** (from a fresh alert) → camera enters cooldown, resumes after 60 s.
- **Kill the AI engine** → every fed camera eventually reads `Unresponsive`, but **not necessarily
  within 10s on a dashboard sitting idle**. The 10s figure is real (`HEARTBEAT_STALE_SECONDS`), but
  it is only recomputed when the frontend fetches — there is no background job that sweeps stale
  heartbeats and pushes the update over the WebSocket the way cooldowns/snoozes do. A live drill
  (2026-08-17) watched a dashboard sit on `Connected` for well over a minute with no page action,
  then flip to `Unresponsive` immediately on the next navigation. If you need to actually see this
  transition during a demo, refresh the page or click to a different tab rather than just waiting.
  Tracked as `be_audit/00_FINDINGS.md` F33.

Sample clips loop, so the same accident frame recurs every few seconds once a camera resumes. Expect
rapid re-triggering during a demo — that is a clip-length artifact, not a defect. Narrate it or trim
the clips.

---

## Troubleshooting

Ordered by how often each one actually happens.

| Symptom                                                                                                     | Cause                                                                                                                       | Fix                                                                                                                                                   |
| ----------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| Client hangs connecting; no error either end                                                                | Ethernet profile is **Public** ("Unidentified network")                                                                     | Step 2, `Set-NetConnectionProfile`. Re-run it after any IP change.                                                                                    |
| Something that was working suddenly stops mid-session, `ping` times out but the name resolves               | Ethernet profile silently reverted Public → no addressing change needed to trigger it                                       | Re-check `Get-NetConnectionProfile -InterfaceAlias "Ethernet"`; re-run `Set-NetConnectionProfile` from Step 2 if it reads Public                      |
| Cameras stay `Connected` for over a minute after the AI engine is killed, dashboard untouched               | No background sweep pushes the `Unresponsive` transition — it's computed only when the frontend fetches                     | Refresh the page, or navigate to a different tab; the underlying status is already correct, it just hasn't been pushed. `be_audit/00_FINDINGS.md` F33 |
| Console fills with `WebSocket connection to 'wss://localhost:5173/...' failed` / `[vite] failed to connect` | Vite's own HMR socket, not `/ws/alerts` — it targets `localhost`, which is the client itself when browsing via `adas.local` | Harmless for a demo; the real alerts WebSocket is unaffected. `be_audit/00_FINDINGS.md` F34                                                           |
| `ping` works, `Test-NetConnection` on 8000/5173 fails                                                       | Firewall rules missing or scoped to the wrong profile                                                                       | Step 2, the two `New-NetFirewallRule` lines                                                                                                           |
| `ping` fails but ports connect fine                                                                         | Windows does not answer ICMP by default                                                                                     | The `ADAS ICMPv4 Echo` rule — or just ignore it, nothing depends on ping                                                                              |
| Dashboard loads, but **no alerts ever arrive** and the console is clean                                     | Certificate was click-through-accepted, not installed into Trusted Root                                                     | Step 3c. This is the classic silent failure.                                                                                                          |
| Login returns 200, then every request is 401                                                                | Secure cookie dropped — you are on `http://`, not `https://`                                                                | Steps 3 and 6.2. Do **not** set `SESSION_COOKIE_SECURE=false`.                                                                                        |
| Writes return 403 `ORIGIN_REJECTED`, or the WebSocket closes instantly                                      | The browser's origin is not in `CORS_ORIGINS`                                                                               | Step 5 — match scheme, host and port exactly                                                                                                          |
| Browser warns about the certificate on the client                                                           | Not in Trusted Root, or you are using Firefox                                                                               | Step 3c; Firefox needs a separate import into its own store                                                                                           |
| `start-sim.ps1` exits immediately                                                                           | `mediamtx` or `ffmpeg` not on `PATH`                                                                                        | Pass `-MediaMtxDir`, set `ADAS_MEDIAMTX_DIR`, or use Step 6.1's `$env:PATH` line                                                                      |
| AI engine logs TLS/certificate verification errors on every heartbeat                                       | `REQUESTS_CA_BUNDLE` unset — `requests` ignores the Windows store                                                           | Step 6.4                                                                                                                                              |
| Cameras stuck on `Reconnecting`                                                                             | No RTSP feed for that channel, or MediaMTX is not running                                                                   | Step 6.1. Note `mediamtx.yml` defines five channels — a sixth camera in the DB has no feed by design.                                                 |
| Export downloads land under a generic filename                                                              | `Content-Disposition` not readable cross-origin                                                                             | Already fixed in `main.py`'s `expose_headers`; if it recurs, check that setting                                                                       |

---

## After the demo — shut down and revert

Easy to skip, and skipping it leaves firewall rules open, a foreign root certificate installed on
somebody else's machine, and a database in a state that blocks the next run. Work through it.

### 11.1 Drain before you stop anything

Check `ai_engine/outbox/` on the server is **empty** before killing the AI engine. Anything still
sitting there is a detected incident that was never delivered to the backend; it will replay on the
engine's next start against whatever the database looks like then, and can be discarded as a duplicate
if a newer incident for that camera opened in the meantime. If the outbox is not empty, leave the
backend up until it drains.

### 11.2 Stop the stack

```powershell
.\scripts\stop-dev.ps1
```

With no switches it stops all four components. It resolves the backend, frontend and MediaMTX by
**listening port** and the AI engine by command line, so it handles the TLS-launched processes above
without modification — and it tree-kills MediaMTX so its per-channel ffmpeg children go down with it.

**Check:** nothing is listening on `8000`, `5173` or `8554`:

```powershell
Get-NetTCPConnection -State Listen | Where-Object LocalPort -in 8000,5173,8554
```

### 11.3 Clean up drill data

Resolve or dismiss any `Unverified` / `Ongoing` incidents the drill created, so the database is not
left mid-workflow for the next person. This is not tidiness: `ux_detection_open_camera` is a partial
unique index enforcing **at most one open incident per camera**, so a leftover open incident silently
blocks the next run's detections on that camera.

If you would rather start clean next time, `uv run python backend/scripts/reseed_dev.py` resets and
reseeds — but it **deletes the SQLite file**, so it cannot run while the backend holds it open. Stop
the backend first.

### 11.4 Revert the server machine

```powershell
# Elevated PowerShell
Remove-NetFirewallRule -DisplayName "ADAS 8000", "ADAS 5173", "ADAS ICMPv4 Echo"
Remove-NetIPAddress -InterfaceAlias "Ethernet" -AddressFamily IPv4 -Confirm:$false
Set-NetIPInterface -InterfaceAlias "Ethernet" -Dhcp Enabled
Set-DnsClientServerAddress -InterfaceAlias "Ethernet" -ResetServerAddresses
```

Then unplug the cable.

Removing the firewall rules is the part that actually matters. They persist, and they are scoped to
"any Private network" — so they will quietly reopen ports 8000 and 5173 on the next Private network
this machine joins. Leaving the connection profile set to Private is fine on your own machine.

### 11.5 Revert the client machine

- Remove the `192.168.50.1  adas.local` line from its hosts file, then `ipconfig /flushdns`.
- Restore DHCP on its Ethernet adapter (same commands as 11.4, with its own adapter name).
- **Remove the certificate from Trusted Root if the machine is not yours.** This is not paranoia: a
  self-signed root certificate whose private key travels around on a USB stick can sign a valid-looking
  certificate for _any_ website. It should not outlive the demo on a machine you do not control.
  Run **`certlm.msc`** (the Local Machine store — `certmgr.msc` opens the Current User one and will not
  show it) → Trusted Root Certification Authorities → Certificates → delete the `adas.local` entry.

### 11.6 What to keep

Leave the `.env` additions from Step 5 in place. `SESSION_COOKIE_SECURE=true` is the code default
anyway, and the extra `CORS_ORIGINS` entries are additive — `https://localhost:5173` is still in the
list, so ordinary local development is unaffected. Only revert them if a teammate's plain-HTTP setup
depends on the old values.

Leave `certs/` alone too — it is gitignored, and the certificate is valid for years.

### 11.7 Confirm you are back to normal

```bash
pwsh -File scripts/start-dev.ps1
```

Log in at `http://localhost:5173`. If that works, the machine is genuinely back to its ordinary state
and you have not left the LAN profile half-applied.

### 11.8 Disk housekeeping (optional)

Each drill leaves JPEGs under `ai_engine/snapshots/` and possibly files in `var/exports/`. Both are
gitignored and neither is large, but the system health endpoint raises `DISK_WARNING` on low free
space independently of anything the demo did — worth clearing headroom before demo day so that warning
is not mistaken for something the drill broke.

---

## Related documents

- [`be_audit/DEMO_TOPOLOGY.md`](be_audit/DEMO_TOPOLOGY.md) — why wired LAN, the production mapping,
  demo-day runbook, hazards, fallback ladder, and the questions a panel is likely to ask
- [`be_audit/A1_lan_tls_drill.md`](be_audit/A1_lan_tls_drill.md) — the engineering pack that
  implemented the TLS profile
- [`be_audit/00_FINDINGS.md`](be_audit/00_FINDINGS.md) — F4 (the Secure-cookie failure this setup
  fixes), F5, F20
- [`CONTRIBUTING.md`](CONTRIBUTING.md) — scripts reference, migrations, CI
