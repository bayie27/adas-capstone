# A4 — Realtime and observability hardening

Small pack. One of the three items turned out to be mostly a documentation job — read F6 before
writing any code.

> **Read before starting:** `be_plan/04_PKG_realtime.md`, `be_plan/01_CONTRACTS.md` §9,
> `be_audit/00_FINDINGS.md`.

---

## F6 — WebSocket keepalive: verify and document, do **not** build (Low)

`04_PKG_realtime.md` Step 5 specifies "ping/pong + a 60s `ws_session_revalidation` job." The
revalidation job exists (`app/services/realtime_revalidation.py`); no application-level ping does.

**Before concluding that is a gap:** `websockets 16.0` is installed and `wsproto` is not, so
uvicorn's `ws="auto"` resolves to its websockets implementation, which defaults to
`ping_interval=20.0` and `ping_timeout=20.0`. **RFC 6455 keepalive is already active** and a
half-open socket is closed after roughly 20–40 seconds. An application-level ping on top of that
is redundant machinery on the hot path.

**Work owed:**
1. Confirm the ping settings are actually in effect for the launch commands that will be used —
   `uv run fastapi dev`, the TLS uvicorn invocation in `A1_lan_tls_drill.md` step 2, and whatever
   `scripts/adas-maintenance.ps1 -Action Start` runs. Record the observed values.
2. Pin them explicitly (`--ws-ping-interval` / `--ws-ping-timeout`) rather than relying on a
   library default that a future uvicorn bump could change, and document the choice next to the
   launch command.
3. Amend `04_PKG_realtime.md` Step 5 to record that ping/pong is satisfied at the ASGI-server
   layer, not the application layer — so the next reader does not re-raise this.
4. **Only if step 1 shows keepalive is not actually active**, implement an application-level ping.
   Write down what you observed either way.

Manual check worth doing during A1's drill: connect the dashboard from the second laptop, then
disable its Wi-Fi without closing the browser. The server should drop the connection within ~40s
and free the slot against `WS_MAX_CONNECTIONS_PER_USER=5`.

---

## F8 — Request ID is lost on 500s (Med) — **reproduce first**

**Only proceed if A1 step 8 confirmed this.** If A1 found a real request id on a 500, mark F8
`void` in `00_FINDINGS.md` and skip.

### The mechanism

Starlette builds its stack as `ServerErrorMiddleware` → *user middleware* → `ExceptionMiddleware`.
A handler registered for the bare `Exception` class is served by **`ServerErrorMiddleware`, which
is outermost** — outside `request_id_middleware` (`app/main.py:242`). By the time
`global_exception_handler` (`app/main.py:336`) runs, the `finally: request_id_ctx.reset(token)`
has already executed, so `request_id_ctx.get()` returns the `"-"` default. The response also never
passes back through the middleware that attaches `X-Request-ID`.

Handlers for `HTTPException`, `RequestValidationError` and `OperationalError` are *not* affected —
those run in `ExceptionMiddleware`, which sits inside the user stack. `test_logging.py` covers 200s
and 404s, which is why this was never caught.

The net effect: the single error class where correlation matters most is the only one that loses it.

### Fix

Do **not** try to reorder middleware — user middleware cannot wrap `ServerErrorMiddleware`.

Instead stop depending on the contextvar in that one handler. `request_id_middleware` already has
the id; also store it on `request.state` (backed by the ASGI `scope`, which *is* shared with the
handler's `Request`). Then `global_exception_handler` reads it from `request.state` and sets the
`X-Request-ID` header on the 500 response itself. Apply the same header treatment to
`operational_error_handler`'s 503, which currently logs the id but does not return it.

Keep the contextvar — it is what feeds `RequestIdFilter` for ordinary log lines.

**Tests** (`backend/tests/test_logging.py`): a route that raises returns a 500 carrying an
`X-Request-ID` matching the logged id; the 503 lock path does the same.

---

## F16 (partial) — Binary WebSocket frame logs as an unexpected error (Low)

`app/main.py:422` calls `await websocket.receive_text()` in the read loop. A client sending a
binary frame raises, which is caught by the generic `except Exception` at `:425` and logged via
`logger.exception("Unexpected error in /ws/alerts read loop…")`. A misbehaving or merely
unfashionable client can therefore fill the log with stack traces for something that is not an
error condition.

Clients never mutate state over the socket (D-008), so all inbound frames are ignorable.

**Fix:** use `await websocket.receive()` and branch on the message `type` — break on
`websocket.disconnect`, ignore everything else. This preserves the existing invariant that every
exit path still runs `finally: await manager.disconnect(...)`.

**Test:** a client sending a binary frame is not disconnected and produces no error log; the
connection is still deregistered exactly once on close.

---

## Acceptance criteria

- Keepalive behaviour observed, recorded, and pinned; `04_PKG_realtime.md` amended.
- F8 either fixed with a regression test, or marked `void` with the evidence.
- Binary frame handled without an error log; existing `test_realtime.py` coverage still green
  (in particular `test_read_loop_deregisters_connection_on_non_disconnect_exception`).
- `uv run pytest` and `pnpm check` green.

## Commits

`docs(planning):` for the realtime amendment · `fix(logging):` for the request-id fix ·
`fix(realtime):` for the frame handling.
