# 31 — Demo-day LAN runbook

> Keep this open on the operator laptop. Follow the gates in order; when a gate fails, repair that layer before moving down the page.

## Fast reference

This is the **three-device Globe router setup**: the Linux VMS publishes RTSP, the Windows ADAS server runs the application and AI engine, and the operator laptop uses a browser. [VMS_SIMULATOR_SETUP.md](../../operations/VMS_SIMULATOR_SETUP.md) supplies the topology and current deployment addresses; [LAN_SETUP.md](../../operations/LAN_SETUP.md) supplies the TLS, hostname, firewall, secure-cookie, and WebSocket checks condensed here. If the venue or router changes, replace the addresses below with the router's current reservations before running commands.

| Device / service               | Current value                                             |
| ------------------------------ | --------------------------------------------------------- |
| Router gateway                 | `192.168.254.254`                                         |
| Linux VMS                      | `192.168.254.195`; wired interface `enxec9a0c1c556e`      |
| Windows ADAS server            | `192.168.254.196`                                         |
| Operator laptop                | `192.168.254.197` (or non-guest Wi-Fi on the same router) |
| RTSP                           | TCP `8554`, Windows ADAS server → Linux VMS only          |
| Backend API + alerts WebSocket | HTTPS/WSS `8000`, operator → Windows ADAS server          |
| Dashboard                      | HTTPS `5173`, operator → Windows ADAS server              |
| Operator URL                   | `https://adas.local:5173`                                 |

The three router-connected devices should be on `192.168.254.0/24`. The operator does not need RTSP access. Do not use Guest Wi-Fi, client isolation, port forwarding, DMZ, bridge mode, or the router reset button. `LAN_SETUP.md` also documents a separate two-device direct-cable profile; its `192.168.50.x` addresses do not belong in this three-device run.

## Before anyone starts a process

- [ ] Plug all three machines into ordinary LAN ports on the same Globe router. The operator may use regular router Wi-Fi if it is not Guest Wi-Fi and client isolation is off.
- [ ] Check the router's Static DHCP list for the VMS and ADAS MAC-to-IP reservations. The current operator reservation is also recorded above.
- [ ] Bring the Linux VMS cable, USB-to-Ethernet adapter if needed, and power supplies. On the VMS, have `ffmpeg`, `mediamtx`, the repo, `mediamtx-vms.yml`, and `scripts/start-vms-sim.sh` ready.
- [ ] On the Windows ADAS server, have the repo, dependencies, model weights, configured repo-root `.env`, `certs/adas-cert.pem`, and `certs/adas-key.pem` ready. Keep the private key on this machine.
- [ ] On the operator laptop, have Edge or Chrome, the public `adas-cert.pem` only, and permission to edit the hosts file and trust store. Never copy `adas-key.pem` to the operator.
- [ ] Confirm the Windows `.env` contains the remote VMS RTSP template and the LAN web settings:

  ```env
  RTSP_URL_TEMPLATE=rtsp://192.168.254.195:8554/channel{channel_id}
  SESSION_COOKIE_SECURE=true
  CORS_ORIGINS=https://adas.local:5173,https://localhost:5173
  ```

- [ ] Confirm the certificate is unexpired and covers `DNS:adas.local`. Trust it on the operator before the panel arrives; do not plan to click through a warning.
- [ ] If the VMS address, ADAS address, or router was changed since rehearsal, update the router reservations, RTSP template, VMS firewall source, and operator hosts entry together.

## Bring-up order

### 1. Linux VMS laptop — link, firewall, then RTSP

Open a terminal at the VMS repository root. Keep the simulator terminal open during the demo.

```bash
# Linux VMS — discover the wired interface and verify link/address/route
ip -br link
ip -4 addr show dev enxec9a0c1c556e
cat /sys/class/net/enxec9a0c1c556e/carrier
ip route
```

Proceed only when the wired interface shows `LOWER_UP`, `carrier` prints `1`, it has `192.168.254.195/24`, and the preferred `192.168.254.0/24` route uses that interface. If your adapter has a different name, use that name in the commands below.

Check that RTSP is restricted to the ADAS server, then start the feeds:

```bash
# Linux VMS — allow only the ADAS server to reach RTSP
sudo ufw status numbered
```

If the firewall is not active or the rule is missing, run this locally on the VMS (not over SSH unless SSH already has an allow rule):

```bash
# Linux VMS
sudo ufw default deny incoming
sudo ufw allow from 192.168.254.196 to any port 8554 proto tcp comment 'ADAS VMS RTSP'
sudo ufw enable
sudo ufw status numbered

# Linux VMS — repository root; leave this running
./scripts/start-vms-sim.sh
```

The startup log should show MediaMTX listening on `:8554` and the configured channels online. In a second VMS terminal, verify a local feed if `ffplay` is available:

```bash
ffplay -rtsp_transport tcp rtsp://localhost:8554/channel1
```

`Ctrl+C` in the simulator terminal stops MediaMTX and its FFmpeg publishers together. The profile publishes `channel1` through `channel5`; use the channel names in `mediamtx-vms.yml` if the profile was intentionally changed.

### 2. Windows ADAS server — verify RTSP reachability, then launch

Use an elevated PowerShell for adapter/firewall checks. The ADAS server must use its Globe-wired interface, not Wi-Fi or a virtual adapter.

```powershell
# Windows ADAS server — elevated PowerShell
Get-NetAdapter | Where-Object Status -eq 'Up' | Select-Object Name,InterfaceDescription,LinkSpeed
Get-NetIPAddress -AddressFamily IPv4 | Format-Table InterfaceAlias,IPAddress,PrefixLength
```

The wired address should be `192.168.254.196`. Set the wired network to Private and ensure both dashboard ports have inbound rules. These checks add a rule only if it is missing:

```powershell
# Windows ADAS server — elevated PowerShell; select the adapter holding 192.168.254.196
$AdasIp = '192.168.254.196'
$IfAlias = (Get-NetIPAddress -AddressFamily IPv4 -IPAddress $AdasIp -ErrorAction Stop).InterfaceAlias
Set-NetConnectionProfile -InterfaceAlias $IfAlias -NetworkCategory Private

if (-not (Get-NetFirewallRule -DisplayName 'ADAS 8000' -ErrorAction SilentlyContinue)) {
  New-NetFirewallRule -DisplayName 'ADAS 8000' -Direction Inbound -LocalPort 8000 -Protocol TCP -Action Allow -Profile Private
}
if (-not (Get-NetFirewallRule -DisplayName 'ADAS 5173' -ErrorAction SilentlyContinue)) {
  New-NetFirewallRule -DisplayName 'ADAS 5173' -Direction Inbound -LocalPort 5173 -Protocol TCP -Action Allow -Profile Private
}
Get-NetConnectionProfile -InterfaceAlias $IfAlias
Get-NetFirewallRule -DisplayName 'ADAS 8000','ADAS 5173' | Select-Object DisplayName,Enabled,Profile
```

Before the application starts, prove the VMS path from Windows:

```powershell
# Windows ADAS server
Test-NetConnection 192.168.254.195 -Port 8554
```

Require `TcpTestSucceeded : True`. If `ffplay` is installed on Windows, this also checks that a stream plays across the router:

```powershell
ffplay -rtsp_transport tcp rtsp://192.168.254.195:8554/channel1
```

At the Windows repository root, start the remote-VMS stack:

```powershell
# Windows ADAS server — repo root; this is the remote-VMS command
pwsh -File scripts/start-dev.ps1 -Lan -Backend -Frontend -Ai
```

Do **not** run bare `-Lan` for the three-device setup; it also starts the Windows-local MediaMTX simulator. The remote-VMS command starts the backend and frontend over TLS plus the AI engine, and passes the certificate path needed for the engine's HTTPS calls.

On the ADAS server itself, confirm `https://localhost:8000/healthz/ready` returns `200` and `https://localhost:5173` shows the login page. After the AI heartbeat, each enabled, fed camera should read **Connected / Active**. If a camera says `Reconnecting`, stop here and repair the RTSP path before testing the operator machine.

### 3. Operator laptop — hostname, trust, then browser

On a Windows operator laptop, edit `C:\Windows\System32\drivers\etc\hosts` in an elevated editor and add:

```text
192.168.254.196 adas.local
```

Then flush name resolution and check the address in brackets. ICMP replies are optional; the resolved address is the check.

```powershell
# Operator laptop
ipconfig /flushdns
ping adas.local
```

Copy `adas-cert.pem` from the ADAS server to the operator, never the key. In an elevated PowerShell, replace the path with the copied certificate's actual location and install it into the Local Machine Trusted Root store:

```powershell
# Operator laptop — elevated PowerShell
$CertPath = 'C:\path\to\adas-cert.pem'
certutil -addstore -f Root $CertPath
```

Restart Edge or Chrome after import. Firefox has its own trust store and needs a separate import. Do not accept a browser warning as a substitute for installing the certificate.

Check both dashboard ports, then browse by hostname (not the raw server IP):

```powershell
# Operator laptop
Test-NetConnection adas.local -Port 8000
Test-NetConnection adas.local -Port 5173
```

Open `https://adas.local:5173`, sign in as username `admin` with `DEFAULT_ADMIN_PASSWORD` from the server's `.env`, and navigate once to confirm the session persists. In DevTools → Network → WS, the alerts connection should remain open and receive `CONNECTION_READY`.

## Validation gates: one layer at a time

| Gate                   | Check and expected result                                                                                                  | If it passes, the next likely fault is…                                                                           |
| ---------------------- | -------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------- |
| 1. Physical LAN        | On Linux, `cat /sys/class/net/enxec9a0c1c556e/carrier` prints `1`; `ip link` shows `LOWER_UP`.                             | Addressing, DHCP reservation, or wrong adapter selection.                                                         |
| 2. Addressing          | Router shows the reservations; Linux has `192.168.254.195/24`; Windows has `192.168.254.196`; operator is on the same LAN. | VMS process, channel profile, or Linux UFW rule.                                                                  |
| 3. VMS publisher       | VMS launcher reports `:8554` and channels online; local `ffplay` can play `rtsp://localhost:8554/channel1`.                | Windows-to-VMS reachability, UFW source rule, or router client isolation.                                         |
| 4. RTSP over LAN       | On Windows, `Test-NetConnection 192.168.254.195 -Port 8554` returns `True`; optional Windows `ffplay` plays `channel1`.    | ADAS RTSP template, a channel-name mismatch, or backend not restarted after `.env` changed.                       |
| 5. Local ADAS services | On Windows, `/healthz/ready` returns `200`, frontend opens on `localhost:5173`, cameras become `Connected / Active`.       | Operator-side network, firewall, host mapping, certificate trust, or browser session.                             |
| 6. Operator TCP        | `Test-NetConnection adas.local -Port 8000` and `-Port 5173` both return `True`.                                            | Host mapping if name is wrong; Windows Private profile or inbound firewall if the IP path also fails.             |
| 7. HTTPS and login     | `https://adas.local:5173` has no certificate warning; login stays active after navigation.                                 | Secure cookie / URL scheme if login drops; origin or certificate trust if requests or WS fail.                    |
| 8. Alert channel       | DevTools shows the alerts WebSocket open with `CONNECTION_READY`; a simulated detection appears and its snapshot renders.  | Camera feed and AI engine if the socket is healthy; certificate or exact CORS origin if the socket does not open. |

Do not use ping as a required gate: Windows may block ICMP even while TCP ports work. Also verify that the operator cannot reach `192.168.254.195:8554`; the VMS firewall intentionally limits RTSP to the ADAS server.

## Troubleshooting cards

### Linux wired adapter has no carrier

```bash
# Linux VMS
ip -br link
cat /sys/class/net/enxec9a0c1c556e/carrier
```

If the adapter says `NO-CARRIER` or `carrier` is `0`, reseat the Ethernet cable, try a known-good dongle/cable, and try another ordinary router LAN port. Do not troubleshoot IPs or applications until the interface reaches `LOWER_UP` and carrier is `1`.

### Machines show the wrong subnet

```bash
# Linux VMS
ip -br -4 addr
ip route
```

```powershell
# Windows ADAS server or operator
ipconfig
Get-NetIPAddress -AddressFamily IPv4 | Format-Table InterfaceAlias,IPAddress,PrefixLength
```

The router-connected addresses should be in `192.168.254.0/24`. Check that you are reading the wired adapter (not Wi-Fi, WSL, Hyper-V, or VirtualBox), that all devices are on the same router, and that the operator is not on Guest Wi-Fi. If you see `192.168.50.x`, you have settings from the separate direct-cable profile; use the three-device router reservations above.

### An address changed after restart

Verify the current Ethernet MAC-to-IP reservation in the router, then verify the lease on that same adapter:

```bash
# Linux VMS
ip -4 addr show dev enxec9a0c1c556e
```

```powershell
# Windows ADAS server or operator
ipconfig /all
```

Reconnect that device's wired link and check again. If the reservation is wrong, correct it in the router's Static DHCP list and renew/reconnect before launching services. If the ADAS address changes, update the VMS UFW allow rule and the operator hosts line. If the VMS address changes, update `RTSP_URL_TEMPLATE` in the server `.env`; restart the backend and AI engine after the change. Do not use a stale address merely because it worked in rehearsal.

### Windows cannot pass the RTSP port test

On Windows, first ensure the VMS terminal is still running and retest:

```powershell
# Windows ADAS server
Test-NetConnection 192.168.254.195 -Port 8554
```

On Linux, inspect the listener log and the source-restricted UFW rule:

```bash
# Linux VMS
sudo ufw status numbered
```

The allow rule must name the current ADAS server address as source and TCP `8554` as destination port. If an old source-address rule remains, delete that numbered entry after inspecting it, then add the current one:

```bash
# Linux VMS — replace the number with the stale rule shown above
sudo ufw delete <OLD_RULE_NUMBER>
sudo ufw allow from 192.168.254.196 to any port 8554 proto tcp comment 'ADAS VMS RTSP'
```

Also confirm both machines are on ordinary LAN ports and use the current VMS address. Windows blocking ping does not block Windows → VMS RTSP.

### Cameras stay at `Reconnecting`

Fix this on the ADAS side before debugging the operator laptop:

1. Check the VMS terminal: MediaMTX must be running, each configured publisher should be online, and the source clip path must exist.
2. If available, from Windows run `ffplay -rtsp_transport tcp rtsp://192.168.254.195:8554/channel1`.
3. Check that the server `.env` says `RTSP_URL_TEMPLATE=rtsp://192.168.254.195:8554/channel{channel_id}` and that the configured camera channels exist in `mediamtx-vms.yml`.
4. If `.env` changed after startup, stop and relaunch the ADAS backend and AI engine with the remote-VMS command above.

Do not proceed to the panel browser until fed cameras show **Connected / Active**.

### Operator cannot reach dashboard ports 8000 or 5173

From the operator laptop, distinguish hostname trouble from server/firewall trouble:

```powershell
# Operator laptop
ping adas.local
Test-NetConnection 192.168.254.196 -Port 8000
Test-NetConnection 192.168.254.196 -Port 5173
```

The address in `ping` brackets must be `192.168.254.196`; replies may time out. If the IP port tests fail but the ADAS server's services are listening, reapply the Private profile and inbound rules on the Windows ADAS server:

```powershell
# Windows ADAS server — elevated PowerShell
$AdasIp = '192.168.254.196'
$IfAlias = (Get-NetIPAddress -AddressFamily IPv4 -IPAddress $AdasIp -ErrorAction Stop).InterfaceAlias
Set-NetConnectionProfile -InterfaceAlias $IfAlias -NetworkCategory Private
Get-NetTCPConnection -State Listen -LocalPort 8000,5173
Get-NetFirewallRule -DisplayName 'ADAS 8000','ADAS 5173' | Select-Object DisplayName,Enabled,Profile
```

If the listeners are absent, repair/restart the ADAS stack. If listeners exist but rules are absent, use the idempotent firewall commands in Bring-up step 2. If raw-IP tests pass but `adas.local` resolves incorrectly, repair the operator hosts entry and run `ipconfig /flushdns`.

### Browser shows a certificate warning

Use `https://adas.local:5173` and verify the operator hosts entry maps `adas.local` to the current ADAS address. On the Windows ADAS server, verify the certificate name and expiry:

```powershell
# Windows ADAS server — repository root
openssl x509 -in certs/adas-cert.pem -noout -text | Select-String -Pattern 'Subject Alternative Name' -Context 0,1
openssl x509 -in certs/adas-cert.pem -noout -enddate
```

The SAN must include `DNS:adas.local`, and the certificate must be unexpired. On the operator, install the public `adas-cert.pem` into Trusted Root and restart Edge/Chrome. Firefox requires its own import. Never copy or import `adas-key.pem`, and do not click through the warning; browser trust is required for WSS alerts.

### Login returns 200, then every request returns 401

Check the address bar first. Use `https://adas.local:5173`, not `http://` and not a different origin. Check that the server `.env` has `SESSION_COOKIE_SECURE=true`; keep it true. A Secure cookie is dropped over plain HTTP, so login may appear to succeed while later requests fail. Restart the backend if the server `.env` was changed.

### Dashboard loads but alerts do not arrive

Walk back from the browser to the engine:

1. Confirm the cameras on the ADAS dashboard are **Connected / Active**, the backend log has accepted AI heartbeats, and the VMS publishers are still running.
2. On the operator laptop, confirm the certificate warning is gone and the browser is at exactly `https://adas.local:5173`.
3. In DevTools → Network → WS, inspect the alerts socket on port `8000`. It should stay open and receive `CONNECTION_READY`.
4. The server `.env` must include the exact origin `https://adas.local:5173` in `CORS_ORIGINS` (scheme, host, and port; no trailing slash). Restart the backend after changing it.
5. If the AI engine logs TLS verification errors on every heartbeat, relaunch through `pwsh -File scripts/start-dev.ps1 -Lan -Backend -Frontend -Ai`; this remote-VMS launch path supplies the certificate bundle the engine needs.

A console error for Vite's `wss://localhost:5173` hot-reload socket is not the backend alerts socket. Check the port-8000 WS entry itself. If it is open but no event arrives, return to the camera/feed checks rather than resetting browser trust.

## If it breaks in front of the panel

**One person keeps talking; the other three split the checks.** The speaker can say: “The dashboard is up; we’re checking the video-ingest link in order, from the simulator to the server to the operator browser.” That is accurate and gives the team a moment to isolate the failing layer.

- **Speaker:** explain the next verified layer and continue the system walkthrough.
- **VMS operator:** check carrier, VMS publisher log, and local RTSP playback.
- **ADAS operator:** check port `8554`, camera state, backend readiness, and the launcher log.
- **Browser operator:** check ports `8000`/`5173`, hostname resolution, certificate trust, and the actual alerts WebSocket.

If the live stream cannot be recovered immediately, do not invent or claim a live detection. Continue with the login, dashboard, camera/incident views, backend readiness, and the alert lifecycle using an already available incident or a prepared local replay. Explain which live-feed layer is unavailable. A stored incident or snapshot can be shown if it is already present.

**Fastest recovery ladder:**

1. Use the validation table; do not restart the whole stack until the failed layer is known.
2. If Linux RTSP is down, restore carrier → VMS publisher → Windows port test → camera `Connected / Active`.
3. If only the operator path is down, check Private profile/firewall → operator port tests → hosts mapping → certificate → login → alerts WS.
4. If remote VMS hardware or the router cannot be restored quickly and the Windows local simulator was rehearsed, switch the server back to local simulation: stop the current stack, set `RTSP_URL_TEMPLATE=rtsp://localhost:8554/channel{channel_id}`, then run `pwsh -File scripts/start-dev.ps1 -Lan` at the Windows repo root. That profile starts the Windows-local simulator; verify cameras are **Connected / Active** and use `https://localhost:5173` on the server. The operator laptop is no longer the live dashboard endpoint in this fallback.

## When the demo ends

Stop the Linux VMS terminal with `Ctrl+C`, then stop the Windows stack from the repo root:

```powershell
# Windows ADAS server
pwsh -File scripts/stop-dev.ps1
```

For another three-device session, keep the reservations, firewall rules, certificate trust, hosts mapping, and UFW allow rule; repeat the address and end-to-end gates before starting the stack.
