# Three-device Globe LAN: remote Linux VMS simulator

This is the repeatable setup for a **Linux VMS laptop**, a **Windows ADAS
server**, and a **browser-only operator laptop** connected to the same Globe
Huawei router. MediaMTX and FFmpeg run on Linux; the ADAS server reads RTSP
from Linux; the operator browser reads HTTPS/WSS from Windows.

Do not use the bare `-Lan` launcher in this topology: it also starts a local
MediaMTX simulator on Windows. Use the remote-VMS launcher command in
[Start the ADAS stack](#7-start-the-adas-stack) instead.

## Contents

1. [Network model and ports](#1-network-model-and-ports)
2. [Deployment record](#2-deployment-record)
3. [Before each session](#3-before-each-session)
4. [Configure the Globe router](#4-configure-the-globe-router)
5. [Prepare and start the Linux VMS](#5-prepare-and-start-the-linux-vms)
6. [Prepare the Windows ADAS server](#6-prepare-the-windows-adas-server)
7. [Start the ADAS stack](#7-start-the-adas-stack)
8. [Prepare the operator laptop](#8-prepare-the-operator-laptop)
9. [Validate end to end](#9-validate-end-to-end)
10. [Troubleshooting](#10-troubleshooting)
11. [Shutdown, reuse, and return to local simulation](#11-shutdown-reuse-and-return-to-local-simulation)

## 1. Network model and ports

Connect the three laptops to ordinary Globe router LAN ports. Do **not** use a
guest Wi-Fi network, port forwarding, DMZ, bridge mode, or the router reset
button. The router only supplies the private LAN and DHCP reservations; no
service in this guide is exposed to the internet.

```text
Linux VMS  ── TCP RTSP 8554 ──>  Windows ADAS server  ── HTTPS/WSS 8000, 5173 ──>  Operator browser
     MediaMTX + FFmpeg                 backend + frontend + AI engine
```

| Port       | Direction                | Purpose                       | Who may reach it  |
| ---------- | ------------------------ | ----------------------------- | ----------------- |
| `8554/TCP` | Windows ADAS → Linux VMS | RTSP camera feeds             | Windows ADAS only |
| `8000/TCP` | Operator → Windows ADAS  | HTTPS API and alert WebSocket | Operator browser  |
| `5173/TCP` | Operator → Windows ADAS  | HTTPS dashboard               | Operator browser  |

The operator laptop never connects to RTSP. Linux UFW blocks RTSP for every
device except the Windows ADAS server.

## 2. Deployment record

Use the table as a record, not a hard-coded requirement. If the router is
replaced/reset or a different venue is used, fill the placeholders again and
update the commands that refer to them.

| Item                   | Placeholder         | Current Globe deployment record |
| ---------------------- | ------------------- | ------------------------------- |
| Router gateway         | `<ROUTER_GATEWAY>`  | `192.168.254.254`               |
| Linux VMS address      | `<VMS_IP>`          | `192.168.254.195`               |
| Linux VMS wired MAC    | `<VMS_MAC>`         | `ec:9a:0c:1c:55:6e`             |
| Windows ADAS address   | `<ADAS_SERVER_IP>`  | `192.168.254.196`               |
| Windows ADAS wired MAC | `<ADAS_SERVER_MAC>` | `e4:a8:df:e1:30:6d`             |
| Operator address       | `<OPERATOR_IP>`     | `192.168.254.197`               |
| Operator wired MAC     | `<OPERATOR_MAC>`    | `08:8f:c3:36:01:30`             |

The reservation binds a MAC address to an address. It is normal for the router
home page to show an offline laptop while it is powered down; the binding still
appears in its DHCP Static IP/Static DHCP list.

## 3. Before each session

Complete this checklist before starting applications:

- All three devices use regular LAN ports on the same Globe router. The
  operator may use regular router Wi-Fi instead, provided it is not Guest Wi-Fi
  and client isolation is disabled.
- The VMS and ADAS reservations appear in the router's static-DHCP list.
- The Linux VMS has `ffmpeg`, `mediamtx`, this repository checkout,
  `mediamtx-defense-vms.yml`, and `scripts/start-vms-sim.sh`.
- The Windows ADAS server has the repository, dependencies, model weights,
  `certs/adas-cert.pem`, `certs/adas-key.pem`, and its configured `.env`.
- The operator has only a supported browser, the public certificate
  (`adas-cert.pem`, never `adas-key.pem`), and permission to edit its hosts
  file/trust store.

On Linux, Wi-Fi may remain connected for internet/Codex access. The wired route
is preferred when it has the lower route metric. Check the current values with:

```bash
ip -4 addr show dev <VMS_ETHERNET_INTERFACE>
ip route
```

For the current VMS laptop the interface is `enxec9a0c1c556e`. A healthy wired
link contains `LOWER_UP`, and the preferred `192.168.254.0/24` route uses that
interface.

## 4. Configure the Globe router

### 4.1 Open the administration page

Browse to `http://<ROUTER_GATEWAY>`; the current deployment uses
`http://192.168.254.254`. Sign in only with authorized Globe/router
credentials. Do not reset the ONT and do not use credentials copied from the
internet.

On the Huawei HG8145V5 interface, the normal path is:

```text
Advanced Configuration
→ LAN Configuration
→ DHCP Static IP Configuration
→ New
```

Some Globe firmware labels the final page **Static DHCP**, **DHCP Reservation**,
or **Address Reservation**.

### 4.2 Add or verify reservations

Create these bindings, substituting the values in the deployment record:

| Role                | MAC address         | Reserved address   |
| ------------------- | ------------------- | ------------------ |
| Linux VMS           | `<VMS_MAC>`         | `<VMS_IP>`         |
| Windows ADAS server | `<ADAS_SERVER_MAC>` | `<ADAS_SERVER_IP>` |
| Operator laptop     | `<OPERATOR_MAC>`    | `<OPERATOR_IP>`    |

Click **Apply** after each binding. Do not change the WAN profile, DHCP pool,
bridge mode, port-forwarding rules, or firewall settings on the router.

### 4.3 Prove the reservations work

The reservation page listing the exact MAC-to-IP pairs is the definitive
check. Then reconnect each Ethernet cable (or reboot each laptop one at a
time) and verify the leases:

```bash
# Linux VMS
ip -4 addr show dev <VMS_ETHERNET_INTERFACE>
```

```powershell
# Windows ADAS or Windows operator
ipconfig
```

The displayed IPv4 addresses must match `<VMS_IP>`, `<ADAS_SERVER_IP>`, and
`<OPERATOR_IP>`. The Globe home page's Wired devices table is useful for
checking the connected MAC, LAN port, and current lease, but it does not by
itself prove that a static reservation exists.

> A red internet/WAN warning in the Globe home page does not prevent local
> DHCP or the wired LAN from working. Do not run One-Click Diagnosis merely to
> set up this isolated LAN.

## 5. Prepare and start the Linux VMS

### 5.1 Identify the wired adapter and confirm its address

```bash
ip link
ip -4 addr show dev <VMS_ETHERNET_INTERFACE>
cat /sys/class/net/<VMS_ETHERNET_INTERFACE>/carrier
```

`carrier` must print `1`. If it prints `0` or `ip link` shows `NO-CARRIER`,
check the cable, USB-to-Ethernet adapter, and Globe LAN port before changing
software settings.

### 5.2 Install or verify MediaMTX and FFmpeg

First check what is already installed:

```bash
command -v ffmpeg
ffmpeg -version
command -v mediamtx
mediamtx --version
```

On Ubuntu, install FFmpeg when it is missing:

```bash
sudo apt update
sudo apt install -y ffmpeg curl tar
```

The profile in this repository was validated with MediaMTX `v1.18.0`. If
`mediamtx` is missing, install that compatible release once (internet required):

```bash
VMS_MTX_VERSION=1.18.0
curl -fLO "https://github.com/bluenviron/mediamtx/releases/download/v${VMS_MTX_VERSION}/mediamtx_v${VMS_MTX_VERSION}_linux_amd64.tar.gz"
tar -xzf "mediamtx_v${VMS_MTX_VERSION}_linux_amd64.tar.gz"
mkdir -p "$HOME/.local/bin"
install -m 0755 mediamtx "$HOME/.local/bin/mediamtx"
export PATH="$HOME/.local/bin:$PATH"
mediamtx --version
```

Add `$HOME/.local/bin` to the shell startup file you actually use if
`command -v mediamtx` stops finding it in a new terminal.

### 5.3 Select clips in the profile

`mediamtx-defense-vms.yml` is the source of truth for the eight-camera defense
profile. It defines `channel1` through `channel8` and contains two complete
switchable publisher groups: an eight-camera silent baseline and a seven-
silent-plus-one-positive group. The launcher is deliberately clip-agnostic.

To use a different clip, edit only the source after `-i` for the chosen
channel, keeping the looping, TCP, output, and `$RTSP_PORT/$MTX_PATH` portions
of the command unchanged:

```yaml
runOnInit: ffmpeg -re -stream_loop -1 -i /absolute/path/to/clip.mp4 -c copy -rtsp_transport tcp -f rtsp rtsp://localhost:$RTSP_PORT/$MTX_PATH
```

Use quotes around a source path containing spaces. When the source is relative,
it is relative to the repository root because the launcher starts MediaMTX
there.

### 5.4 Restrict RTSP to the ADAS server

Run this locally on the VMS laptop, replacing `<ADAS_SERVER_IP>` with the
reserved Windows address. Do not enable this policy over SSH until SSH has an
explicit allow rule.

```bash
sudo ufw default deny incoming
sudo ufw allow from <ADAS_SERVER_IP> to any port 8554 proto tcp comment 'ADAS VMS RTSP'
sudo ufw enable
sudo ufw status numbered
```

This allows `Windows ADAS → Linux VMS:8554` and blocks operator access to RTSP.
It does not block Linux outbound Wi-Fi traffic, including Codex. If the Windows
reservation changes, inspect the old rule, delete its numbered entry, and add
the new source address:

```bash
sudo ufw status numbered
sudo ufw delete <OLD_RULE_NUMBER>
sudo ufw allow from <NEW_ADAS_SERVER_IP> to any port 8554 proto tcp comment 'ADAS VMS RTSP'
```

### 5.5 Start and check the VMS

From the VMS repository root:

```bash
./scripts/start-vms-sim.sh --config mediamtx-defense-vms.yml
```

Leave this terminal running. It starts MediaMTX and its eight FFmpeg publishers;
`Ctrl+C` stops them together. A successful log opens `:8554` and reports each
configured channel online.

In a second terminal, verify one local stream if `ffplay` is available:

```bash
ffplay -rtsp_transport tcp rtsp://localhost:8554/channel1
```

## 6. Prepare the Windows ADAS server

### 6.1 Identify the Globe-wired adapter

Run PowerShell as Administrator:

```powershell
Get-NetAdapter | Where-Object Status -eq 'Up' | Select-Object Name, InterfaceDescription, LinkSpeed
Get-NetIPAddress -AddressFamily IPv4 | Format-Table InterfaceAlias,IPAddress,PrefixLength
```

Use the adapter whose address is `<ADAS_SERVER_IP>`, not Wi-Fi, Hyper-V,
VirtualBox, WSL, or another virtual adapter. The current deployment expects
the Globe-wired adapter to have `192.168.254.196`.

### 6.2 Permit the dashboard traffic

Set the wired adapter's profile to Private, then add the two required inbound
rules. Replace `<WINDOWS_ETHERNET_ALIAS>` with the name reported above.

```powershell
Set-NetConnectionProfile -InterfaceAlias "<WINDOWS_ETHERNET_ALIAS>" -NetworkCategory Private
New-NetFirewallRule -DisplayName "ADAS 8000" -Direction Inbound -LocalPort 8000 -Protocol TCP -Action Allow -Profile Private
New-NetFirewallRule -DisplayName "ADAS 5173" -Direction Inbound -LocalPort 5173 -Protocol TCP -Action Allow -Profile Private
Get-NetConnectionProfile -InterfaceAlias "<WINDOWS_ETHERNET_ALIAS>"
Get-NetFirewallRule -DisplayName "ADAS 8000","ADAS 5173" | Select-Object DisplayName,Enabled,Profile
```

Windows may block inbound ping; that does not prevent either the dashboard or
RTSP. Add this optional diagnostic rule only if ping is useful during setup:

```powershell
New-NetFirewallRule -DisplayName "ADAS ICMPv4 Echo" -Direction Inbound -Protocol ICMPv4 -IcmpType 8 -Action Allow -Profile Private
```

### 6.3 Configure TLS and the remote RTSP template

The existing certificate must contain `DNS:adas.local` and be unexpired:

```powershell
openssl x509 -in certs/adas-cert.pem -noout -text | Select-String -Pattern "Subject Alternative Name" -Context 0,1
openssl x509 -in certs/adas-cert.pem -noout -enddate
```

If it is missing or unsuitable, generate a new certificate from Git Bash at
the repository root. Keep the private key on Windows only:

```bash
mkdir -p certs
MSYS_NO_PATHCONV=1 openssl req -x509 -newkey rsa:2048 -sha256 -days 825 -nodes \
  -keyout certs/adas-key.pem -out certs/adas-cert.pem -subj "/CN=adas.local" \
  -addext "subjectAltName=DNS:adas.local,DNS:localhost,IP:127.0.0.1"
```

Set these exact values in the Windows repo-root `.env`, substituting the
reserved VMS address:

```env
RTSP_URL_TEMPLATE=rtsp://<VMS_IP>:8554/channel{channel_id}
SESSION_COOKIE_SECURE=true
CORS_ORIGINS=https://adas.local:5173,https://localhost:5173
```

The backend loads `RTSP_URL_TEMPLATE` only at startup. Restart the backend and
AI engine after changing it. Use `adas.local` on the operator laptop; do not
browse the router-assigned Windows IP because the certificate is intentionally
issued to the stable hostname instead.

### 6.4 Prove Windows can read the VMS before starting ADAS

```powershell
Test-NetConnection <VMS_IP> -Port 8554
```

`TcpTestSucceeded` must be `True`. If FFmpeg is installed on Windows, this is
an optional video check:

```powershell
ffplay -rtsp_transport tcp rtsp://<VMS_IP>:8554/channel1
```

## 7. Start the ADAS stack

With the VMS launcher still running, open PowerShell at the Windows repository
root and run:

```powershell
pwsh -File scripts/start-dev.ps1 -Lan -Backend -Frontend -Ai
```

This starts the backend and frontend over TLS plus the AI engine, without a
local `-Sim` process. The launcher checks the certificate and LAN `.env` keys.
The AI engine receives its backend certificate path automatically in this
route, so do not replace the command with an ordinary non-LAN manual launch.

On the Windows server itself, confirm:

```text
https://localhost:8000/healthz/ready  → 200
https://localhost:5173                → login page
```

After the AI heartbeat, the enabled fed cameras should show `Connected / Active`.
If they show `Reconnecting`, stop and repair the VMS/RTSP path before testing
the operator laptop.

## 8. Prepare the operator laptop

The operator is browser-only. It needs no repository, FFmpeg, MediaMTX, AI
weights, or RTSP access.

### 8.1 Give `adas.local` its current server address

Map the stable hostname to the reserved Windows address:

```text
<ADAS_SERVER_IP> adas.local
```

On a Windows operator laptop, open an elevated editor for
`C:\Windows\System32\drivers\etc\hosts`, add that line, then run:

```powershell
ipconfig /flushdns
ping adas.local
```

The ping output must resolve `adas.local` to `<ADAS_SERVER_IP>`. Replies may
time out if the optional Windows ICMP rule was not installed; name resolution
is still correct when the bracketed address matches.

On a Linux operator laptop, add the same line to `/etc/hosts` and use Chromium
or another browser that trusts the system certificate store:

```bash
echo '<ADAS_SERVER_IP> adas.local' | sudo tee -a /etc/hosts
```

### 8.2 Trust the Windows ADAS certificate

Copy **only** `certs/adas-cert.pem` from the Windows server to the operator.
Never copy `adas-key.pem`.

On Windows, in an elevated PowerShell:

```powershell
certutil -addstore -f Root C:\path\to\adas-cert.pem
```

Restart Edge or Chrome after importing. Firefox uses its own trust store and
needs a separate certificate import.

On Ubuntu/Debian Linux:

```bash
sudo install -m 0644 /path/to/adas-cert.pem /usr/local/share/ca-certificates/adas-cert.crt
sudo update-ca-certificates
```

### 8.3 Open the dashboard

Use Edge or Chrome and browse:

```text
https://adas.local:5173
```

Do not click through a certificate warning. A trusted certificate is required
for the secure login cookie and WebSocket alerts to work reliably.

## 9. Validate end to end

Run the checks in this order. Each successful layer narrows the next failure.

| Layer        | Command/action                                                 | Expected result                                                  |
| ------------ | -------------------------------------------------------------- | ---------------------------------------------------------------- |
| Router       | Static DHCP list                                               | All three MAC-to-IP bindings appear                              |
| Linux VMS    | `ip link`                                                      | Wired interface is `LOWER_UP`                                    |
| Linux VMS    | `./scripts/start-vms-sim.sh --config mediamtx-defense-vms.yml` | Listener opens on TCP `:8554`; eight configured channels publish |
| Windows ADAS | `Test-NetConnection <VMS_IP> -Port 8554`                       | `TcpTestSucceeded : True`                                        |
| Windows ADAS | `ffplay ...channel1` when available                            | Selected replay appears                                          |
| Windows ADAS | `https://localhost:8000/healthz/ready`                         | HTTP 200                                                         |
| Windows ADAS | Camera status after AI heartbeat                               | Fed cameras are `Connected / Active`                             |
| Operator     | `Test-NetConnection adas.local -Port 8000`                     | `TcpTestSucceeded : True`                                        |
| Operator     | `Test-NetConnection adas.local -Port 5173`                     | `TcpTestSucceeded : True`                                        |
| Operator     | `https://adas.local:5173`                                      | Login persists after navigation; alerts arrive                   |
| Operator     | `Test-NetConnection <VMS_IP> -Port 8554`                       | Fails after UFW restriction                                      |

## 10. Troubleshooting

| Symptom                                             | Likely cause                                                                            | Check and correction                                                                                                 |
| --------------------------------------------------- | --------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| Linux wired adapter shows `NO-CARRIER`              | Cable, dongle, or router LAN port has no physical link                                  | Re-seat cable, try another known-good cable/LAN port, and require `LOWER_UP` before changing IP settings.            |
| Devices have different subnets                      | One laptop is on an old static address, another router, Guest Wi-Fi, or virtual adapter | Confirm each Globe-wired address is `192.168.254.x`; reconnect to DHCP and verify the router reservation.            |
| Address changed after restart                       | Missing/incorrect reservation                                                           | Check the router's static-DHCP list, then verify the exact Ethernet MAC and renew/reconnect the device.              |
| Linux cannot ping Windows but Windows reaches Linux | Windows blocks inbound ICMP                                                             | This does not block Windows → VMS RTSP. Add the optional ICMP rule only if ping is required.                         |
| Windows port `8554` test fails                      | VMS not running, UFW source address is stale, wrong VMS address, or router isolation    | Check VMS logs, `sudo ufw status numbered`, the Windows reservation, and that both devices use ordinary LAN ports.   |
| `ffplay` works locally but not from Windows         | UFW or wrong remote template                                                            | Confirm `Test-NetConnection <VMS_IP> -Port 8554`; ensure `.env` names the Linux VMS address, not `localhost`.        |
| Cameras remain `Reconnecting`                       | No RTSP source, invalid clip path, or backend was not restarted after `.env` change     | Repair the VMS profile/path, relaunch MediaMTX, then restart backend and AI engine.                                  |
| Operator cannot reach ports `8000`/`5173`           | Windows wired network is Public or firewall rules are absent                            | Re-run the Private-profile and `ADAS 8000`/`ADAS 5173` rules on the correct Ethernet adapter.                        |
| Browser warns about certificate                     | Certificate is untrusted, expired, or hostname mapping is wrong                         | Trust `adas-cert.pem`, restart browser, and confirm `adas.local` resolves to `<ADAS_SERVER_IP>`.                     |
| Login returns 200 then every request is 401         | Dashboard was opened through HTTP or cookie is not secure                               | Use `https://adas.local:5173`; keep `SESSION_COOKIE_SECURE=true`.                                                    |
| Dashboard loads but no alerts arrive                | CORS origin/certificate/WebSocket mismatch                                              | Use exactly `https://adas.local:5173` and ensure it is in `CORS_ORIGINS`; do not click through certificate warnings. |
| Globe home page says internet/WAN abnormal          | ISP internet link is down                                                               | The local private LAN may still work. Do not reset the router while diagnosing ADAS LAN traffic.                     |

## 11. Shutdown, reuse, and return to local simulation

For an ordinary shutdown, stop the VMS terminal with `Ctrl+C`, then stop the
Windows stack:

```powershell
pwsh -File scripts/stop-dev.ps1
```

Keep the router reservations, Windows firewall rules, certificate, hostname
mapping, and Linux UFW allow rule for the next remote-VMS session. Before the
next run, repeat the checks in [Before each session](#3-before-each-session)
and [Validate end to end](#9-validate-end-to-end).

To return to the old server-local simulator, stop the Linux VMS and change the
Windows `.env` back to:

```env
RTSP_URL_TEMPLATE=rtsp://localhost:8554/channel{channel_id}
```

Restart the backend, then use the normal Windows `-Sim` route documented in
[README.md](README.md) and [LAN_SETUP.md](LAN_SETUP.md).
