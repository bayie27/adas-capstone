# A1 — LAN + TLS end-to-end drill

**Run this pack first.** Everything else is easier to judge once the system has actually run over
the network it will be demoed on. This pack also confirms or kills F5 and F8 empirically.

> **Read before starting:** `CLAUDE.md` (run everything from repo root, `uv run` never bare
> `python`), `be_plan/01_CONTRACTS.md` §5 and §9, `be_audit/00_FINDINGS.md`.

## Why this exists

The realistic deployment ceiling for this project is **this laptop as the server, a second laptop
as the client on the same LAN**. That path has never been run. It contains one guaranteed failure
(F4) and one silent defect (F5):

- `SESSION_COOKIE_SECURE=true` + plain `http://192.168.x.x` → browsers grant the Secure-cookie
  exemption to `localhost` **only**, never to a LAN IP. The cookie is dropped without an error;
  login returns 200 and every subsequent request is 401. This looks like an auth bug and isn't.
- The paper's Technical Scope claims "HTTPS for standard API requests and WebSockets." Nothing in
  `be_plan/` implements it. **Owner decision: do real self-signed TLS**, which fixes F4 and makes
  the paper claim true at the same time.

## Scope

Backend + the two contract seams. Do not refactor AI-engine or frontend internals. The only
frontend files this pack may touch are `frontend/vite.config.ts` and `frontend/src/utils/env.ts`,
and both changes must be **opt-in so CI and plain `localhost` dev are unaffected**.

---

## Step 0 — Topology

**Read `be_audit/DEMO_TOPOLOGY.md` first.** It carries the architecture rationale, the demo-day
runbook and the fallback ladder; this pack is the implementation.

The short version you need to execute against: Lipa CDRRMO wires its operator PCs to the edge
server over Ethernet, so the target topology is **two laptops on a direct Ethernet cable with
static IPs** — `192.168.50.1` (server) and `192.168.50.2` (client), no gateway. Not Wi-Fi.

Two OS-level preconditions on the server laptop, both of which fail *silently* if skipped:

```powershell
Set-NetConnectionProfile -InterfaceAlias "Ethernet" -NetworkCategory Private
New-NetFirewallRule -DisplayName "ADAS 8000" -Direction Inbound -LocalPort 8000 -Protocol TCP -Action Allow -Profile Private
New-NetFirewallRule -DisplayName "ADAS 5173" -Direction Inbound -LocalPort 5173 -Protocol TCP -Action Allow -Profile Private
```

A gateway-less link is classified "Unidentified network" → **Public** → inbound blocked with no
error at either end. Verify with `Test-NetConnection adas.local -Port 8000` from the client before
debugging anything in the application.

## Step 1 — Certificate, issued to a hostname

A CN-only certificate is rejected by every current browser, so SANs are mandatory. **Issue to
`adas.local`, not to an IP** — an IP-pinned cert breaks the moment the address changes, and there
is no clickable bypass for a failed `wss://` handshake.

```bash
mkdir -p certs && MSYS_NO_PATHCONV=1 openssl req -x509 -newkey rsa:2048 -sha256 -days 825 -nodes -keyout certs/adas-key.pem -out certs/adas-cert.pem -subj "/CN=adas.local" -addext "subjectAltName=DNS:adas.local,DNS:localhost,IP:192.168.50.1,IP:127.0.0.1"
```

The client resolves the name with one hosts-file line (`C:\Windows\System32\drivers\etc\hosts`,
requires an elevated editor):

```
192.168.50.1  adas.local
```

Including `localhost` / `127.0.0.1` in the same SAN list is deliberate: the identical certificate
then covers the single-laptop fallback with no reconfiguration.

Gotchas that will cost you an hour each:
- **`MSYS_NO_PATHCONV=1` is required.** Git Bash rewrites `/CN=...` into a Windows path otherwise.
- **825 days is the maximum** Safari/iOS accept. Longer certs are rejected outright.
- Confirm the result: `openssl x509 -in certs/adas-cert.pem -noout -text` must list `DNS:adas.local`.
- `certs/` must be **gitignored**. A private key in git history is not recoverable from.

## Step 2 — Backend over TLS

`fastapi run` does not expose SSL flags, so drive uvicorn directly. `--app-dir backend` replaces
what the FastAPI CLI normally does for `sys.path` (see `CLAUDE.md`).

```bash
uv run uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000 --ssl-keyfile certs/adas-key.pem --ssl-certfile certs/adas-cert.pem
```

Confirm in the startup log that `websockets` is the WS implementation (see A4/F6) and note
uvicorn's default `--ws-ping-interval 20 --ws-ping-timeout 20`.

## Step 3 — Frontend over TLS, bound to the LAN

`frontend/vite.config.ts` currently has no `server` block. Add one that is **conditional on an env
var** so `pnpm dev`, `pnpm build` and the Playwright `webServer` config keep working untouched:

```ts
// only when ADAS_TLS_CERT_DIR is set; otherwise dev/CI behave exactly as before
server: process.env.ADAS_TLS_CERT_DIR
  ? {
      host: true,
      https: {
        key: fs.readFileSync(`${process.env.ADAS_TLS_CERT_DIR}/adas-key.pem`),
        cert: fs.readFileSync(`${process.env.ADAS_TLS_CERT_DIR}/adas-cert.pem`),
      },
    }
  : undefined,
```

## Step 4 — Protocol-aware client origins

`frontend/src/utils/env.ts:14,18` derives the API and WS hosts from `window.location.hostname`
(so LAN already works) but **hardcodes `http://` and `ws://`**. Under TLS that produces mixed
content and a failed socket.

Preferred fix — three lines, keeping the existing `typeof window === "undefined"` guard:

```ts
function getDefaultApiBaseUrl() {
  return `${getBrowserProtocol()}//${getBrowserHostname()}:8000/api`
}
function getDefaultWsBaseUrl() {
  return `${getBrowserProtocol() === "https:" ? "wss:" : "ws:"}//${getBrowserHostname()}:8000`
}
```

`frontend/src/utils/env.test.ts` asserts the current defaults and will need updating.
Also grep for `BACKEND_ORIGIN` (used by `frontend/src/services/health.ts:16`) and apply the same
treatment.

**Zero-frontend-change fallback** if the frontend owner would rather not take the diff: set
`VITE_API_BASE_URL=https://<LAN_IP>:8000/api` and `VITE_WS_BASE_URL=wss://<LAN_IP>:8000`. Flag the
choice to them rather than deciding unilaterally.

## Step 5 — Backend env for the LAN profile

```
SESSION_COOKIE_SECURE=true
CORS_ORIGINS=https://adas.local:5173,https://localhost:5173
```

`SameSite=Strict` is fine — same host, different port is same-site. Add a commented **LAN demo
profile** block to `.env.example` documenting all three values together.

## Step 6 — Trust the certificate on the client laptop

This is the step that is never written down and always costs an hour.

1. Copy **the certificate only — never `adas-key.pem`** — to the client laptop.
2. Install it into **Trusted Root Certification Authorities**: double-click → Install Certificate →
   Local Machine → "Place all certificates in the following store" → Trusted Root.
3. Use **Edge or Chrome**. Firefox maintains its own certificate store and needs a separate import.

Trusting it properly is what makes `wss://` work. If you instead click through a browser warning
for `:5173` only, the dashboard will load and the WebSocket will fail **silently** — no events, no
error, nothing in the console that names the cause. That symptom always means this step was
skipped. (If you are forced to fall back to clicking through warnings, you must visit
`https://adas.local:8000/` once and accept it *separately* from `:5173`.)

## Step 7 — The drill

From the **second laptop**, against the server laptop:

1. Log in. Confirm `Set-Cookie` carries `Secure; HttpOnly; SameSite=Strict` and that a follow-up
   `GET /api/users/me` returns 200 — this is F4 closed.
2. Confirm the WebSocket reaches `CONNECTION_READY` (browser devtools → Network → WS).
3. Start the camera simulator. Read `scripts/start-sim.ps1` first for its preflight expectations;
   `mediamtx` lives at
   `C:\Users\Dani\OneDrive - dlsl.edu.ph\Desktop\ACADEMICS\mediamtx_v1.18.0_windows_amd64`
   and feeds `rtsp://<host>:8554/channel{1..5}` from `ai_engine/sample_vids/`.
4. Start the AI engine: `uv run python ai_engine/main.py` (needs `uv sync --extra ai`).
5. Confirm the dashboard shows `Connected` / `Active` — **not** `Reconnecting`. Per
   `15_PKG_ai_engine_integration.md`: if it still says `Reconnecting`, nothing else matters.
6. Trigger a real detection. Assert: alert on the client in **under 2s** (NFR-04), snapshot
   renders (authenticated `GET /api/alerts/{id}/snapshot`, cookie-carried), camera goes `Paused`.
7. Confirm → `Ongoing`, camera stays paused. Resolve → camera resumes immediately.
8. Second detection → Dismiss → camera `Paused`/`cooldown`, resumes after 60s.
9. Kill the AI engine. Within ~10s every camera presents `Unresponsive` and
   `/api/system/health/live` reports `sample_camera_count: 0` with a stale warning.

## Step 8 — Reproduce F5 and F8

- **F5:** trigger a CSV export from the browser UI. If the saved file uses the fallback name
  rather than the server's `Content-Disposition` filename, F5 is confirmed — the fix is
  `expose_headers=["Content-Disposition", "X-Request-ID"]` on `CORSMiddleware`
  (`backend/app/main.py:475`), owned by A2.
- **F8:** force an unhandled 500 (temporarily raise in a route, or point `DATABASE_URL` somewhere
  broken). Check whether the response carries an `X-Request-ID` header and whether the logged
  `[request_id]` is a real uuid or `-`. Record the answer in `00_FINDINGS.md` — if it is `-`,
  F8 is confirmed and A4 fixes it; if not, mark F8 `void`.

---

## Deliverables

1. **`be_audit/DEMO_TOPOLOGY.md` updated in place** with the commands you actually ran and any
   step that turned out wrong. Do not create a second runbook — that document is already the
   day-of playbook and a competing copy will drift from it.
2. A commented **LAN demo profile** block in `.env.example`.
3. `certs/` added to `.gitignore`.
4. `frontend/vite.config.ts` + `frontend/src/utils/env.ts` changes (opt-in), or the documented
   `VITE_*` fallback if the frontend owner prefers that.
5. `00_FINDINGS.md` updated: F4 → `fixed`, F5 and F8 → confirmed or `void`, plus any new `F17+`.

## Acceptance criteria

- A second laptop on the LAN completes login → live alert → confirm → resolve entirely over
  `https://` / `wss://`, with `SESSION_COOKIE_SECURE=true`.
- `uv run pytest` and `pnpm check` still pass; **Playwright still runs unchanged** (the TLS block
  must be inert when `ADAS_TLS_CERT_DIR` is unset).
- Every step in the runbook was actually executed, and anything that failed is written down as a
  finding rather than worked around silently.

## Commits

`docs(audit):` for the runbook · `feat(ops):` for the TLS profile and `.env.example`
`fix(frontend):` for the env/vite changes. Conventional Commits, enforced by commitlint.
