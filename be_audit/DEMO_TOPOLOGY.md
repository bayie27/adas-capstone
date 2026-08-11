# Demo topology — why wired LAN, and how to run it on the day

Audience: teammates, the writing team, and anyone bringing the demo up without having been in the
session that designed it. Read this before `A1_lan_tls_drill.md`; A1 is the execution pack, this is
the reasoning and the day-of playbook.

---

## 1. What Lipa CDRRMO actually runs

The deployment target is an **on-premise wired network**. There is no internet path in the design
at all:

- A **Dell PowerEdge R760xa edge server** (dual Xeon Platinum 8468, 512 GB ECC DDR5, dual 2 TB NVMe
  in RAID 1, **8× NVIDIA L4**, Ubuntu Server LTS) with a **static IP inside the CCTV VLAN**,
  sitting alongside the Dahua DSS Pro server.
- **Operator client PCs connected over Ethernet** through a Ruijie Reyee aggregation switch.
- Four VLANs — 50 Core Management, 51 Video Archival, **52 Edge Surveillance**, **60 Operations** —
  with router-on-a-stick cross-VLAN routing between the server and the operator workstations.
- Cameras reach the server as **RTSP `subtype=1` 720p substreams** from the Dahua VMS.
- **NFR-20**: all data stored and processed exclusively on the edge server's physical drives, never
  transmitted to external cloud services.
- **HTTPS for API requests and WebSockets** (Technical Scope).

Two consequences fall straight out of that, and they are the reason this document exists:

1. **The client PCs are wired to the server.** A direct-Ethernet demo is not a compromise forced by
   budget — it is a faithful reproduction of the production link, with a cable standing in for a
   cable through a switch.
2. **Any cloud tunnel is disqualified, not merely inelegant.** ngrok, Cloudflare Tunnel, a VPS,
   Tailscale — all of them would demo smoothly and all of them violate NFR-20 explicitly. If
   someone suggests one as a convenience, the answer is no, and the reason is in the paper.

## 2. How the demo maps to production

One server node, one operator workstation, same protocols end to end.

| Production | Demo stand-in | Same? |
|---|---|---|
| Dell R760xa edge server, Ubuntu LTS | This laptop (i5-12500H, RTX 3050 Ti 4 GB, Win 11) | Different scale and OS, **same software** |
| 8× NVIDIA L4 | 1× RTX 3050 Ti Laptop | Different capacity, same inference path |
| Dahua DSS Pro, RTSP `subtype=1` 720p | `mediamtx` + `ffmpeg` replaying `ai_engine/sample_vids/` | **Same protocol** — RTSP, same URL shape |
| Operator PC on VLAN 60, wired | Second laptop, wired | **Identical** — browser over Ethernet |
| Ruijie switch + router-on-a-stick | Direct cable (or a small switch) | Same L2/L3 reachability, fewer hops |
| HTTPS + WSS | HTTPS + WSS, self-signed cert | **Same protocols**, demo-grade trust anchor |
| No internet egress (NFR-20) | No internet egress | **Identical** |

The honest caveats to state in the paper and in the room: **node count** (1 operator PC, not N),
**GPU capacity** (which is what actually bounds the 418-camera claim — see
`be_plan/16_HEARTBEAT_VS_POLLING.md`: at 418 cameras the heartbeat is ~56 KB/s, 0.05% of a gigabit
link, so *networking was never the constraint — VRAM is*), and **certificate trust** (self-signed
here, a real CA or an internal PKI in production).

Everything else on that list is genuinely the same code doing the same thing.

## 3. Alternatives, and why they were rejected

| Option | Verdict |
|---|---|
| Cloud tunnel / hosted demo | **Violates NFR-20.** Not a judgement call. |
| Docker | Rejected in `be_plan/13_WSL2_LINUX_PATH.md` — GPU passthrough means matching drivers and rebuilding TensorRT inside the container, plus RTSP across the container boundary. Large new failure surface, zero demo benefit. |
| WSL2 | Same doc, same answer for demo purposes. WSL2 is worth doing *later* to move NFR-16/NFR-18 from "reviewed, unverified" to "verified on Linux" — but that is a backend-and-SQLite-only exercise with a faked engine, not a demo path. |
| Wi-Fi between the laptops | Works, but adds failure modes production does not have (see §7). Keep as fallback, not primary. |
| Everything on one laptop | The reliable fallback. Loses the "operator workstation" half of the story but demonstrates every backend behaviour. |

## 4. The demo network, concretely

**Link:** one Cat5e/Cat6 cable between the two laptops. Modern NICs are auto-MDIX, so an ordinary
patch cable works — you do not need a crossover cable. USB-C→Ethernet dongles if either laptop
lacks a port.

**Addressing:** static, on both ends. Do not rely on DHCP — there is no DHCP server on a two-node
cable, and Windows APIPA addresses (`169.254.x.x`) change between boots.

| | Server laptop | Client laptop |
|---|---|---|
| IPv4 | `192.168.50.1` | `192.168.50.2` |
| Mask | `255.255.255.0` | `255.255.255.0` |
| Gateway | *(leave blank)* | *(leave blank)* |

Leaving the gateway blank is deliberate: it stops Windows trying to route internet traffic over the
demo link, and it means the laptops keep working normally on Wi-Fi at the same time.

**Naming:** the certificate is issued to a **hostname**, `adas.local`, not to an IP. The client gets
one line in `C:\Windows\System32\drivers\etc\hosts`:

```
192.168.50.1  adas.local
```

This is the single most important design choice in the setup. A cert pinned to an IP dies the moment
the address changes — a different venue, a different cable, a fallback to a hotspot — and you cannot
click past a certificate error on a `wss://` handshake. With a hostname, changing networks is a
one-line hosts-file edit instead of regenerating and re-trusting a certificate under pressure.

**Origins:** `https://adas.local:5173` (dashboard) and `https://adas.local:8000` (API + WebSocket).
`CORS_ORIGINS` must contain the first; `SESSION_COOKIE_SECURE=true` stays true because everything
is genuinely HTTPS.

**Ports that must be reachable from the client:** `8000` and `5173`. That is all. RTSP (`8554`)
never crosses the cable — mediamtx, ffmpeg, the AI engine and the backend all live on the server
laptop, exactly as they would all live on the edge server in production.

## 5. Demo-day runbook

Work top to bottom. Every step has a check; do not proceed past a failed check.

### Phase 0 — Physical and OS (10 minutes)

| # | Do | Check | If it fails |
|---|---|---|---|
| 0.1 | Both laptops **plugged into mains** | Battery icon shows charging | The RTX 3050 Ti throttles hard on battery and will wreck your FPS and latency numbers |
| 0.2 | Set power plan so neither machine sleeps or turns off the display | `powercfg /change standby-timeout-ac 0` | Sleep drops the Ethernet link and the WebSocket |
| 0.3 | **Pause OneDrive sync on the server laptop** | OneDrive icon shows paused | See §7 — this is a real hazard, not a nicety |
| 0.4 | Connect the Ethernet cable | Link light on both ends; adapter shows "Network" not "Unplugged" | Try the other dongle/cable — carry spares |

### Phase 1 — Network (10 minutes)

| # | Do | Check | If it fails |
|---|---|---|---|
| 1.1 | Set static IPs per §4 | `ipconfig` shows `192.168.50.1` / `.2` on the Ethernet adapter | Confirm you edited the Ethernet adapter, not Wi-Fi |
| 1.2 | Set the Ethernet profile to **Private** on the server:<br>`Set-NetConnectionProfile -InterfaceAlias "Ethernet" -NetworkCategory Private` | `Get-NetConnectionProfile` shows `Private` | A gateway-less link is classified "Unidentified network" → **Public** → firewall drops inbound **silently**. This is the #1 cause of a demo that looks broken for no reason |
| 1.3 | Allow the two ports on the server (admin PowerShell):<br>`New-NetFirewallRule -DisplayName "ADAS 8000" -Direction Inbound -LocalPort 8000 -Protocol TCP -Action Allow -Profile Private`<br>(repeat for 5173) | `Get-NetFirewallRule -DisplayName "ADAS*"` | Needs an elevated shell |
| 1.4 | Add the hosts entry on the **client** | `ping adas.local` resolves to `192.168.50.1` | Notepad must be run as administrator to save the hosts file |
| 1.5 | Reachability | From the client: `Test-NetConnection adas.local -Port 8000` → `TcpTestSucceeded : True` | If ping works but the port does not, it is 1.2 or 1.3 |

### Phase 2 — Certificate (5 minutes, ideally done the day before)

| # | Do | Check |
|---|---|---|
| 2.1 | Generate the cert with a hostname SAN (see `A1_lan_tls_drill.md` step 1) | `openssl x509 -in certs/adas-cert.pem -noout -text` lists `DNS:adas.local` |
| 2.2 | Copy the **certificate only** — never the key — to the client | The `.pem`/`.crt` file is on the client |
| 2.3 | Install it into **Trusted Root Certification Authorities** (double-click → Install Certificate → Local Machine → place in Trusted Root) | Browsing `https://adas.local:8000/` shows no warning at all |
| 2.4 | Use **Edge or Chrome** on the client | Firefox keeps its own certificate store and needs a separate import |

Properly trusting the cert is what makes `wss://` work. If you only click through a browser warning
for `:5173`, the dashboard will load and the WebSocket will fail **silently** — no events, no error.
That symptom always means step 2.3 was skipped.

### Phase 3 — Bring up the stack, server laptop (10 minutes)

Start in this order and verify each before the next.

| # | Do | Check |
|---|---|---|
| 3.1 | Start `mediamtx` + the `ffmpeg` feeds (see `scripts/start-sim.ps1`) | `rtsp://localhost:8554/channel1` plays in VLC/ffplay |
| 3.2 | Start the backend over TLS (`A1` step 2) | `https://localhost:8000/healthz/ready` → 200 |
| 3.3 | Build and serve the frontend over TLS | `https://localhost:5173` loads on the server itself |
| 3.4 | Start the AI engine — `uv run python ai_engine/main.py` | Log shows heartbeats being accepted |
| 3.5 | Confirm state on the server's own browser | Cameras read **Connected / Active** — *not* `Reconnecting` |

Per `be_plan/15_PKG_ai_engine_integration.md`: if it still says `Reconnecting`, nothing else matters
— stop and fix that before going to the client.

### Phase 4 — Client and the scenario (5 minutes)

| # | Do | Check |
|---|---|---|
| 4.1 | Browse `https://adas.local:5173` from the client | No cert warning; login page renders |
| 4.2 | Log in | Dashboard loads and **stays** logged in on navigation — this is the Secure-cookie path working |
| 4.3 | Devtools → Network → WS | Connection open, `CONNECTION_READY` received |
| 4.4 | Trigger a detection | Alert on the client in **under 2 s** (NFR-04), snapshot renders, camera goes `Paused` |
| 4.5 | Confirm | `Ongoing`; camera stays paused |
| 4.6 | Resolve | Camera resumes immediately |
| 4.7 | Second detection → Dismiss | `Paused`/`cooldown`; resumes after 60 s |
| 4.8 | Optional, if asked | Kill the AI engine → cameras present `Unresponsive` within ~10 s |

## 6. Kit list

- Cat5e/Cat6 cable — **plus a spare**
- 2× USB-C→Ethernet dongles (assume neither laptop has a port)
- Both power adapters
- USB stick with `adas-cert.pem`, the hosts-file line written out, and this document
- A small travel router or switch (fallback tier 2)
- A phone with hotspot enabled (fallback tier 3)
- **A screen recording of a successful full run** (fallback tier 4)

## 7. Known hazards

**OneDrive sync on the server laptop.** The repository lives under
`C:\Users\Dani\OneDrive - dlsl.edu.ph\...`, which means `adas.db`, its `-wal`/`-shm` sidecars,
`ai_engine/snapshots/`, `var/backups/` and `var/exports/` are all inside a live cloud-sync folder.
SQLite in WAL mode plus a sync client that opens, locks and uploads files underneath it is a
well-known bad combination — it can produce file-locking errors, sync conflict copies of the
database, and partially-uploaded snapshots. **Pause OneDrive for the whole demo.** Longer term this
is worth fixing properly; it is tracked as **F17** in `00_FINDINGS.md`.

**Windows network profile.** Covered in step 1.2 and worth repeating because the failure is silent:
Public profile blocks inbound connections with no error on either end. The client just hangs.

**Power and thermals.** The AI engine on a 4 GB laptop GPU is the hot path. On battery, Windows
throttles the GPU and your latency and FPS figures stop resembling the recorded evidence. Plugged in,
on a hard surface, not on a table cloth.

**Sleep/hibernate.** Drops the link, kills the WebSocket, and can make APScheduler jobs misfire
(`14_EDGE_CASES.md` row 5.11). Disable sleep on both machines for the duration.

**Cert expiry.** 825 days from generation. Not a demo-day risk, but if this project is picked up a
year from now, regenerating is step one.

## 8. Fallback ladder

Decide in the room; each tier below costs you part of the story, not the whole thing.

1. **Direct Ethernet** — primary. Matches production exactly.
2. **Both laptops into your own switch or travel router** — still wired, still matches production;
   IP may change, so edit the client's hosts entry.
3. **Phone hotspot** — Wi-Fi, so it no longer mirrors the wired production link, and beware AP
   client isolation. Update the hosts entry to the new server IP.
4. **Single laptop, `https://localhost:5173`** — the same certificate already covers `localhost`
   and `127.0.0.1`, so this needs no reconfiguration. You lose the second-operator narrative and
   keep every backend behaviour.
5. **The recording.** Have it. You will almost certainly not need it.

Venue Wi-Fi is deliberately absent from this list. Institutional SSIDs commonly enable AP/client
isolation, which blocks laptop-to-laptop traffic entirely while everything *looks* connected, and
you cannot fix it from your side.

## 9. Questions a panel is likely to ask

**"Why not deploy this to the cloud?"** NFR-20 requires all data to stay on the edge server's
physical drives. CCTV footage of road incidents is sensitive, the agency owns the infrastructure,
and the architecture is deliberately air-gapped from the internet. The weekly archival tier goes to
a CDRRMO-managed NAS, not to a cloud provider.

**"Does this work over the internet?"** By design, no. Operator workstations are wired to the same
on-premise network as the edge server, across VLANs 52 and 60. Remote access was not a requirement
and would conflict with NFR-20.

**"Is one laptop representative of the real server?"** For the software, yes — it is the same code,
the same protocols, the same database engine, the same auth. For capacity, no, and we do not claim
it: every performance number in `EVIDENCE.md` is explicitly labelled demo-validated on this laptop.
The 418-camera figure is a VRAM calculation against 8× L4, not something this hardware can
demonstrate.

**"Why is the browser warning about the certificate?"** It should not be, if the cert was installed
into Trusted Root. If it is, the honest answer is that this is a self-signed certificate for the
demo; production would use the agency's internal PKI or a CA-issued certificate. The transport
security — TLS for HTTPS and WSS — is real either way; only the trust anchor differs.

**"What happens if the network drops mid-incident?"** The incident is already committed to SQLite
before any broadcast goes out. The dashboard reconnects and rehydrates via REST — `CONNECTION_READY`
then `GET /api/alerts/?status=Unverified&status=Ongoing` (NFR-17). WebSocket delivery is
at-most-once and best-effort by design; REST is the recovery path. The AI engine, independently,
holds undelivered detections in a durable outbox and the camera stays paused until the backend
acknowledges.

---

## 10. A1 drill log — what was actually run (2026-08-10)

**Constraint hit immediately: this session had one physical machine, not two.** Everything that
needs a second laptop's hands — plugging in the cable, setting its static IP, installing the
certificate into *its* Trusted Root store, clicking through Edge/Chrome — could not be executed by
the agent. What follows is what *was* verified on this laptop, using the documented **single-laptop
fallback** (§8 tier 4, `https://localhost`) as the closest reachable proxy, plus the reasoning for
why each substitution is still a valid check of the underlying claim.

### Browser-pane limitation (read this before repeating the drill in a similar sandbox)

The available browser automation tool refused to navigate to `https://localhost:5173` at all —
no click-through, no `--ignore-certificate-errors` equivalent — while a plain `https://example.com`
load worked fine. So there is no headless way in this sandbox to reproduce steps 4.1-4.7 as an
actual rendered dashboard. Substituted with **cert-pinned scripted calls**
(`curl --cacert certs/adas-cert.pem`, and a Python `websockets` client using
`ssl.create_default_context(cafile=...)`) — this validates the exact same trust chain a real browser
would after step 6 (install into Trusted Root), just without a GUI. **The actual GUI walkthrough on
a second machine is still owed** and is not something this pack can close.

### Commands actually run, in order

```powershell
# Step 0 — skipped: Set-NetConnectionProfile / New-NetFirewallRule are meaningless without a
# second NIC on a real LAN link. Not run this session.
```

```bash
# Step 1 — certificate
mkdir -p certs && MSYS_NO_PATHCONV=1 openssl req -x509 -newkey rsa:2048 -sha256 -days 825 -nodes \
  -keyout certs/adas-key.pem -out certs/adas-cert.pem -subj "/CN=adas.local" \
  -addext "subjectAltName=DNS:adas.local,DNS:localhost,IP:192.168.50.1,IP:127.0.0.1"
openssl x509 -in certs/adas-cert.pem -noout -text | grep -A2 "Subject Alternative Name"
# -> DNS:adas.local, DNS:localhost, IP Address:192.168.50.1, IP Address:127.0.0.1
```

```bash
# Step 2 — backend over TLS
uv run uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000 \
  --ssl-keyfile certs/adas-key.pem --ssl-certfile certs/adas-cert.pem
# Confirmed: "Uvicorn running on https://0.0.0.0:8000"; `websockets 16.0` present, `wsproto`
# absent (ModuleNotFoundError) -> uvicorn's ws impl is `websockets` with its 20s/20s ping
# default, confirming F6's reasoning empirically, not just by reading the dependency list.
```

```bash
# Step 3 — frontend over TLS (ADAS_TLS_CERT_DIR gates the vite.config.ts block added by this pack)
cd frontend && ADAS_TLS_CERT_DIR="../certs" pnpm dev
# -> Local: https://localhost:5173/, https://adas.local:5173/ (vite reads the cert's own SAN
# list to print candidate origins; adas.local does NOT actually resolve without a hosts entry)
```

```powershell
# Camera simulator — mediamtx is not on PATH by default; scripts/start-sim.ps1 requires it there.
$env:PATH = "C:\Users\Dani\OneDrive - dlsl.edu.ph\Desktop\ACADEMICS\mediamtx_v1.18.0_windows_amd64;$env:PATH"
.\scripts\start-sim.ps1
```

```bash
# AI engine — needs the backend's TLS reached with real cert verification, not the OS trust
# store (nothing installed it there this session), so REQUESTS_CA_BUNDLE points `requests`
# (used unmodified in ai_engine/backend_client.py) at our cert directly.
AI_BACKEND_BASE_URL="https://127.0.0.1:8000" \
REQUESTS_CA_BUNDLE="$(pwd)/certs/adas-cert.pem" \
uv run python ai_engine/main.py
```

### What the live run actually showed

- **Login → cookie → follow-up request (F4).** `POST /api/auth/login` (username `admin`, **not**
  an email — the seed script's admin account has no email login) returned
  `Set-Cookie: adas_session=…; HttpOnly; Max-Age=28800; Path=/; SameSite=strict; Secure`, verified
  by direct header inspection. The same cookie jar then got `200` on `GET /api/users/me`. **F4 is
  closed** — this is the exact failure this pack exists to fix, and it no longer reproduces once
  `https://` + `SESSION_COOKIE_SECURE=true` are both real.
- **WebSocket over `wss://` (cert-verified).** `CONNECTION_READY` received immediately on connect.
- **Real live detections, not synthetic ones.** Of the seven sample clips, only **`car_car.mp4`
  (channel 1)** and **`red-car-motorcycle.mp4`** (channel 4) actually trigger the current model —
  worth knowing before demo day so nobody sits waiting on channels 2/3/5/6. The dev-seeded
  pre-existing `Unverified`/`Ongoing` rows on cameras 1 and 4 were cleared first (dismiss / resolve)
  so a fresh live detection could be observed end to end.
- **NFR-04 latency, measured, not assumed.** A WS listener logging wall-clock receive time against
  each event's `occurred_at` measured **~0.53s** and **~0.84s** from detection to `NEW_DETECTION`
  delivery — comfortably under the 2s budget. (This is one laptop over loopback, not the two-laptop
  wired link; treat as a floor, not the LAN number.)
- **Self-blindfold ordering, confirmed on the wire.** `NEW_DETECTION` was received strictly before
  the paired `CAMERA_STATUS_UPDATE` (`ai_status: Paused`) for the same camera, matching
  `CLAUDE.md`'s documented ordering.
- **Full HITL cycle exercised live:** confirm → resolve (camera resumes immediately, config_version
  bumps); confirm → dismiss as human correction from `Ongoing` (resumes immediately); dismiss
  straight from `Unverified` → `cooldown_until` set to **exactly** `verified_at + 60s`
  (`DISMISS_COOLDOWN_SECONDS`).
- **Snapshot fetch (cookie-carried, TLS).** `GET /api/alerts/{id}/snapshot` returned a real
  99 KB JPEG (1008×560) with `200`.
- **Sample clips loop fast.** `-stream_loop -1` on a short clip means the same accident frame
  recurs roughly every few seconds once a camera resumes — expect rapid re-triggering during the
  demo, which is a clip-length artifact, not a system defect. Worth either trimming the clips or
  just narrating it if it happens live.
- **Engine loss → `Unresponsive` (step 9).** Killing the AI engine process pair, both cameras it
  was feeding read `Unresponsive` within the poll window, and `GET /api/system/health/live`
  reported `sample_camera_count: 0` with an `AI_HEARTBEAT_STALE` warning and `state: "degraded"` —
  matches the runbook's expected symptom exactly.
- **F5, confirmed by header inspection, not by a browser.** A real cross-origin request
  (`Origin: https://localhost:5173` against `https://localhost:8000`) got back
  `content-disposition: attachment; filename="adas_incident_export.csv"` on the wire, but **no**
  `Access-Control-Expose-Headers` — which is what actually gates whether browser JS can read that
  header, regardless of which browser is used. F5 stands confirmed. Fix owned by A2.
- **F8, confirmed by forcing a real unhandled exception** (temporary debug route, added, tested,
  and removed in the same session — `git diff` showed a clean `backend/app/main.py` afterward).
  The `500` response carried no `X-Request-ID` header, and the server log read
  `Unhandled exception on GET …/… [request_id=-]`. F8 stands confirmed. Fix owned by A4.
- **Pre-flight worth adding to the kit list:** this laptop's disk is already at 85.8% used, which
  alone trips `DISK_WARNING` in `/api/system/health/live` independent of anything this pack did —
  worth clearing headroom before demo day so that warning isn't mistaken for something the drill
  broke.
- **F17 did not reproduce this session** — OneDrive was not even running (checked via `tasklist`),
  and no `OperationalError`/lock errors appeared in any backend log. Not evidence F17 is wrong,
  just that this session's conditions didn't exercise it either way.

### What is still owed on real hardware

Everything gated on a second physical machine: static IP assignment on both NICs, the
`Set-NetConnectionProfile`/firewall-rule pair, the client hosts-file entry, installing the
certificate into the client's Trusted Root store, and the actual GUI walkthrough (login → live
alert → confirm → resolve, watched in a real browser window on the second laptop). None of these
have a scriptable substitute — they need to be run once, by hand, before the real demo day, ideally
well before it per §6's "certificate … ideally done the day before."
