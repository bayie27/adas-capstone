# 13 — Security Architecture

> **One-liner:** ADAS protects human and machine access with hashed passwords, short-lived cookie sessions that the server can revoke, role checks, origin controls, and encrypted LAN transport.
> **Panel risk:** high — the April security document described Bearer tokens, while the current system uses browser cookies and server-side session records; panelists may ask what changed and how CSRF is handled.

## 1. What it is

ADAS has two separate kinds of credentials.

Human users sign in with a username and password. The server never stores the password itself; it stores a password hash.

After sign-in, the browser receives a signed session token in an HttpOnly cookie. JavaScript cannot read that credential, and the browser sends it automatically with requests to the ADAS site.

The signed token points to an auth_session row in the database. The row lets ADAS end a session immediately instead of waiting for the token's natural expiry.

The server checks the user’s current account status and role on protected requests. A role saved in an old token does not grant Administrator access if the database now says the user is an Operator.

The AI engine uses a different credential from human users: a shared internal API key for its backend webhook requests.

Because browsers attach cookies automatically, the cookie design also needs cross-site request protections. ADAS uses a strict same-site cookie policy and server-side Origin checks for state-changing requests.

The LAN demo runs its browser and backend traffic over HTTPS and WSS using the adas.local certificate. This protects the session in transit when the client trusts the certificate.

## 2. Where it lives

### In the paper

The paper’s security requirements are spread across the requirements and architecture sections.

- Chapter 3, Requirements Analysis, Functional Requirements Specification, Table 2:
  - FR-01 requires username-and-password sign-in before dashboard access.
  - FR-02 establishes role-based access control.
- Chapter 3, Requirements Analysis, Security Requirements, Table 7:
  - NFR-19 sets the maximum session lifetime at 8 hours.
  - It requires session protection and immediate ending on logout, password change, or Administrator revocation.
- Definition of Terms, “Session,” describes an HttpOnly, Secure cookie backed by an auth_session database row and capable of individual revocation.
- Chapter 3, System Architecture and Design, Figure 2, “Client-Server Architecture,” states that REST traffic uses HTTPS and real-time alert delivery uses secure WebSockets.

The paper does not collect the current implementation into one security-architecture section. Use the requirements above for the project claim and the code below for the current mechanism.

### In the code

- Password hashing and token format:
  - **backend/app/core/security.py:13** configures the Argon2 password-hashing context.
  - **backend/app/core/security.py:21** verifies a submitted password.
  - **backend/app/core/security.py:32** hashes passwords for storage.
  - **backend/app/core/security.py:36** issues the signed session token and its claims.
  - **backend/app/core/security.py:54** decodes the token with explicit algorithm, issuer, audience, and expiry validation.
- Cookie and server-side session:
  - **backend/app/core/security.py:69** sets the cookie attributes; **backend/app/core/security.py:81** clears it.
  - **backend/app/services/sessions.py:14** creates the auth_session record; **backend/app/services/sessions.py:38** checks whether it is active.
  - **backend/app/services/sessions.py:52** revokes a selected session; **backend/app/services/sessions.py:63** revokes all sessions for a user.
  - **backend/app/models/user.py:81** defines AuthSession; fields are at **backend/app/models/user.py:96** and **backend/app/models/user.py:101**.
- Authentication, role checks, and login throttling:
  - **backend/app/api/dependencies.py:24** checks the internal API key.
  - **backend/app/api/dependencies.py:48** validates a user session; **backend/app/api/dependencies.py:104** reads the cookie for HTTP requests.
  - **backend/app/api/dependencies.py:118** builds the Administrator dependency; the role check is at **backend/app/api/dependencies.py:133**.
  - **backend/app/api/routes/auth.py:40** handles sign-in; the limiter check is at **backend/app/api/routes/auth.py:54**.
  - **backend/app/core/rate_limit.py:8** defines the in-process sliding-window limiter; **backend/app/core/rate_limit.py:45** checks it.
  - **backend/app/core/config.py:27** through **backend/app/core/config.py:49** contains the configured token, session, cookie, origin, limiter, and internal-key settings.
- Internal AI webhook:
  - **backend/app/api/routes/internal.py:30** protects the internal router with a dependency; **backend/app/api/routes/internal.py:93** receives an AI alert.
  - **backend/app/api/dependencies.py:24** uses constant-time comparison for the key.
  - **ai_engine/backend_client.py:17** attaches the key as an x-api-key header.
- CORS, Origin validation, and WebSocket handshake:
  - **backend/app/main.py:330** lists unsafe HTTP methods; **backend/app/main.py:333** creates the Origin middleware.
  - **backend/app/main.py:341** applies that check to state-changing HTTP requests.
  - **backend/app/main.py:442** starts the alert WebSocket route; **backend/app/main.py:459** checks its Origin.
  - The WebSocket then reads the cookie and opens the database session at **backend/app/main.py:464** and **backend/app/main.py:469**.
  - **backend/app/main.py:571** configures credentialed CORS; **backend/app/main.py:584** installs Origin validation.
- HTTPS/WSS demo profile:
  - **scripts/start-dev.ps1:442** launches the backend with the certificate and private key.
  - **frontend/vite.config.ts:22** enables HTTPS for the frontend when the TLS directory is configured.
  - **frontend/src/utils/env.ts:26** selects WSS when the dashboard page is HTTPS.
  - **docs/operations/LAN_SETUP.md:67** identifies adas.local as the certificate hostname.
  - **docs/operations/LAN_SETUP.md:216** through **docs/operations/LAN_SETUP.md:230** explains certificate trust and keeping the private key on the server.

### In the test tracker

Use the local tracker at docs/ADAS Test Execution.xlsx.

- The “Security Testing” sheet contains TC-SEC-001 through TC-SEC-027, all recorded as Pass.
- Session and cookie cases are TC-SEC-016 and TC-SEC-019 through TC-SEC-024.
- The main webhook-key case is TC-SEC-018.
- Role-boundary cases include TC-SEC-003, TC-SEC-005, and TC-SEC-006.
- “System E2E Testing” TC-SYS-021 records logout, browser return-to-login behavior, cookie replay rejection, and closure of the live socket.

## 3. How it works

### A. Passwords do not go into the database as readable text

1. On account creation or password update, ADAS runs the password through the Argon2id password-hashing context.
2. The database stores the encoded hash in the user row’s password_hash field.
3. At login, the submitted password is verified against that hash; the plaintext is not compared to a stored password.
4. When the username does not exist, the login path still verifies against a fixed dummy Argon2id hash. That uses comparable verification work so an unknown username does not get an obviously faster response.
5. Wrong passwords, unknown usernames, and inactive accounts receive the same generic login failure. The login flow also records failed attempts.

### B. A successful login creates both a cookie and a revocable row

1. Before the password lookup, the login route checks the limiter using the source IP and normalized username.
2. If the request passes the limit and the password is valid, the backend creates an auth_session row.
3. The row contains the session identifier, user identifier, creation time, fixed expiry, revocation time and reason, user-agent metadata, and source-IP metadata.
4. The login audit row and session row are committed as part of the login operation.
5. The backend signs a JWT with the user identifier, session identifier, current role value, issue and expiry times, issuer, and audience.
6. It returns the user display data and sets the JWT only as the session cookie. The response body contains no session token.
7. The frontend sends cookies with credentialed API requests. It does not construct an Authorization: Bearer header.
8. The frontend may keep role, username, and user ID as a display cache in localStorage. That cache is not proof of login and contains no session token.

### C. Cookie attributes define how the browser handles the credential

- HttpOnly prevents page JavaScript from reading the session cookie.
- Secure tells the browser to send the cookie over HTTPS connections only when enabled.
- SameSite=Strict limits when the browser sends the cookie in a cross-site context.
- The cookie is scoped to the site path and carries the same fixed lifetime as the server-side session.
- The HTTPS/LAN profile uses Secure cookies. The tracker notes that its isolated plain-HTTP test profile intentionally omitted Secure; do not describe that test profile as the LAN configuration.
- The frontend sends the cookie automatically to REST requests and to the WebSocket handshake. The server has no bearer-token fallback.

### D. Every protected request validates the token and the database row

1. The HTTP dependency reads the credential only from the named cookie.
2. The JWT decoder verifies the signature, expiry, configured algorithm allowlist, configured issuer, and configured audience.
3. The backend requires the token’s subject and session ID.
4. It loads the matching auth_session row. A missing, revoked, or expired row is rejected.
5. It confirms that the row belongs to the same user named by the token.
6. It loads the user row and rejects a missing or inactive account.
7. The resulting User object carries the current database role. The server authorizes against that current value rather than trusting a possibly old role claim.
8. Administrator-only route handlers inject the Administrator dependency. A direct API call receives a forbidden response even if the user edits the frontend or visits a hidden route.

### E. Revocation changes the server’s decision, not just the browser display

- Logout marks the matching session row revoked with a logout reason and timestamp.
- After the database commit, the backend clears the cookie and closes the WebSocket tied to that session.
- An Administrator password reset, account deactivation, or role change revokes the user’s active session rows and closes their connected sockets.
- A request with a revoked cookie is rejected on its next protected request, even though the cookie’s original expiry is still in the future.
- A new session expires at its creation-time deadline. Ordinary activity does not extend the deadline.
- A session naturally expires no later than 8 hours after sign-in, matching NFR-19 and the tracked expiry case.

### F. The AI engine authenticates separately from browser users

1. The AI process reads INTERNAL_API_KEY from its environment and adds it to internal webhook calls as x-api-key.
2. The backend’s internal router applies verify_internal_api_key before its alert and heartbeat handlers.
3. A missing or wrong key gets an unauthorized response before alert ingestion.
4. The comparison uses secrets.compare_digest rather than a normal early-exit string equality check.
5. This key proves possession of the shared machine credential. It does not prove that the caller is a particular physical computer if the key has been copied.

### G. Login attempts are throttled in memory

- The limiter keeps separate counters keyed by source IP and normalized username.
- A failed login adds to both counters; a successful login clears both.
- When either configured threshold is reached, the route returns a rate-limit response with Retry-After and records the denial.
- The limiter state lives in the backend process. This is the current single-worker design; multiple independent workers would need a shared limiter to enforce one common count.
- The test tracker does not list a separate Security Testing case for the configured login limiter. Explain its code path, but do not claim that the Security Testing sheet independently validated a threshold.

### H. CSRF protection is layered around automatic cookies

- CORS allows credentialed browser requests only from configured origins. An allowed-origin list is necessary for browser access, but CORS alone does not guarantee that a request was never sent.
- The HTTP Origin middleware checks state-changing methods: POST, PUT, PATCH, and DELETE.
- If an unsafe request carries an Origin outside the configured list, the server returns 403 ORIGIN_REJECTED before the route handler runs.
- An absent Origin is allowed for same-origin non-browser callers such as curl or TestClient. This is why Origin is a browser CSRF signal, not an authentication credential.
- The internal AI router is exempt from this browser-origin check because it uses the x-api-key credential instead.
- The WebSocket route applies its own Origin allowlist before creating a database Session. It then requires the same session cookie and validates that session before accepting the socket.
- A WebSocket client cannot set an Authorization header through the browser API. The browser cookie is the handshake credential.
- There is no separate synchronizer CSRF token in this design. The browser control is SameSite=Strict plus server-side Origin validation for state changes.

### I. HTTPS and WSS carry the session across the LAN

- The LAN launch profile enables TLS on the backend and frontend, using adas-cert.pem and adas-key.pem.
- When the dashboard URL uses HTTPS, the frontend derives a WSS URL for the alert channel.
- The certificate is issued for adas.local, and the client trusts it through an explicit local certificate-store installation.
- Only the public certificate is installed on client machines. The private key stays on the server and is kept out of version control.
- A self-signed certificate is not automatically trusted by a browser. Trusting the certificate and matching the requested hostname are what let the browser authenticate the intended LAN server.
- If the certificate warning is clicked through instead of installing trust, do not claim the client has verified the server identity; the WebSocket may fail.

## 4. Why it was built this way

Argon2id is the current password-hashing scheme. It turns a password into a one-way verifier, so a database read does not reveal reusable plaintext passwords.

The token remains a compact signed JWT, but the session is not treated as stateless. Its sid claim joins the token to a row the server can revoke.

An HttpOnly cookie keeps the session secret out of JavaScript-facing storage. It also lets the browser send the same credential through the REST and WebSocket paths without a client-generated bearer header.

That choice changes the browser threat model: cookies are automatic, so cross-site submission must be considered. SameSite=Strict and the server’s allowlisted Origin check are the two controls for browser state changes.

Pinning the configured JWT algorithm, issuer, and audience means the decoder applies the backend’s expected token rules instead of accepting values supplied by an untrusted token.

Authorization reads the current database role through FastAPI dependency injection. An administrator demotion or account disable takes effect on the next request, even if an old signed token still contains the previous role.

The webhook API key is separate from a human session. Constant-time comparison checks the shared secret without an ordinary prefix-by-prefix equality path.

Login throttling adds friction to repeated guesses while generic failure responses and dummy password verification reduce account-enumeration clues.

TLS is needed for more than confidentiality: the Secure cookie depends on an HTTPS origin, and the LAN browser must trust the certificate to use the WSS channel without warnings.

## 5. What changed since the 28 April defense

The April security document is the before picture. It described a stateless JWT sent as an Authorization: Bearer token, bcrypt password hashes, role authorization from the JWT payload, and a Bearer-token CSRF rationale. The current system retains signed JWTs and the internal AI key, but changes how human sessions are carried and revoked.

| Design area             | April document: before                                                                                                 | Current implementation: after                                                                                                                                           |
| ----------------------- | ---------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Human session transport | JWT sent explicitly as a Bearer value in the HTTP Authorization header; described as stateless.                        | Signed JWT is carried in an HttpOnly cookie with Secure enabled in the HTTPS/LAN profile and SameSite=Strict. The browser attaches it to REST and WebSocket handshakes. |
| Server-side revocation  | No auth_session record is described; the document calls the token stateless and gives it an eight-hour shift lifetime. | The token’s sid points to a revocable auth_session row. A revoked or expired row fails the next protected request. NFR-19 still caps the lifetime at 8 hours.           |
| Password hashing        | Passlib bcrypt with a random salt.                                                                                     | Argon2id through the configured Argon2 password context.                                                                                                                |
| Role authorization      | The PDF says role is encoded in the JWT payload and checked for protected routes.                                      | The role claim is for frontend initialization; backend route dependencies authorize from the current user row.                                                          |
| Token validation detail | PyJWT token generation and decoding are described; the chapter does not detail algorithm, issuer, or audience pinning. | Decoder restricts the algorithm and verifies the configured issuer, audience, signature, and expiry.                                                                    |
| AI-to-backend webhook   | INTERNAL_API_KEY is described as an environment-provided secret for internal webhooks.                                 | The same machine credential is sent in x-api-key; the backend compares it with secrets.compare_digest. TC-SEC-018 records wrong-key rejection before ingestion.         |
| CSRF explanation        | The Bearer header was described as avoiding automatic browser cookies, and therefore avoiding CSRF.                    | The cookie is automatic, so the current design pairs SameSite=Strict with an allowlisted Origin check on state-changing requests.                                       |
| Transport               | The document already describes HTTPS for REST and WSS for alerts.                                                      | The LAN launch profile configures HTTPS/WSS using the adas.local certificate and the client trust procedure.                                                            |
| Login throttling        | The old security chapter does not describe a login limiter.                                                            | Current login code checks an in-process sliding window by source IP and username and returns Retry-After when throttled.                                                |

### What the session change means in practice

The JWT format did not disappear. The credential is still a signed token, but its delivery moved from a caller-supplied Authorization header to a browser-managed cookie.

The browser no longer exposes the token to page JavaScript. The frontend keeps only non-secret display fields in localStorage; the actual proof of authentication remains the HttpOnly cookie.

The server now reads the database session row as part of authentication. That adds a state check to requests, and it enables immediate revocation without waiting for the signed token’s expiry.

The eight-hour limit is still the upper bound. Current code sets an absolute expiry at login rather than extending it whenever the user is active.

The cookie is sent automatically, so the design no longer treats CSRF as structurally absent. SameSite=Strict limits cross-site cookie sending, and Origin validation rejects state-changing requests from an unapproved browser origin.

If an attacker obtains the cookie value itself, it is still a credential that can be replayed. The current implementation does not bind it cryptographically to one browser, IP address, or user-agent string.

### How to explain CSRF now

CSRF is a browser trick: a malicious site tries to make a victim’s browser send an authenticated state-changing request to another site.

The cookie carries credentials automatically, so the defense is not “the browser has no cookie.” The defense is that cross-site contexts do not normally send a SameSite=Strict cookie, and the backend independently rejects a state-changing request when its Origin is not allowed.

CORS supports the dashboard’s allowlisted origins, but the server-side Origin middleware is the part that rejects the unsafe request itself. This is why the current design is cookie-based with explicit CSRF defenses rather than a claim of Bearer-token immunity.

## 6. Limits and honest caveats

The tracker is evidence for the listed scenarios, not a claim that every possible security attack was tested. The Security Testing sheet records TC-SEC-001 through TC-SEC-027 as Pass; keep each result within its actual scope.

| Tracker evidence                   | What the record supports                                                                                                 | Qualification to keep                                                                                                                                         |
| ---------------------------------- | ------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| TC-SEC-003, TC-SEC-005, TC-SEC-006 | Operator requests to Administrator routes are refused, and self-service role escalation does not change the stored role. | These are scoped authorization scenarios, not proof that every route has been independently penetrated.                                                       |
| TC-SEC-007                         | No-cookie and revoked-cookie WebSocket handshakes are refused before any alert message; a valid Operator connects.       | This row does not independently test a foreign WebSocket Origin. The Origin-before-database ordering is documented by current code.                           |
| TC-SEC-016                         | A token signed with the wrong key is rejected.                                                                           | This case supports signature-key validation; it does not by itself establish algorithm, issuer, and audience pinning. Those are explicit in the decoder code. |
| TC-SEC-018                         | A wrong internal API key returns unauthorized and no incident is ingested.                                               | It tests the rejected-key path, not compromise or disclosure of the shared key.                                                                               |
| TC-SEC-019, TC-SEC-020             | An expired session is refused; logout marks the row revoked and replay is refused before natural expiry.                 | The expired-session check is on the next protected request.                                                                                                   |
| TC-SEC-021                         | The other active session is refused after password change and its row records password_change.                           | The tracker is evidence for that recorded two-session scenario, not a timing benchmark.                                                                       |
| TC-SEC-022                         | No token appears in the login response body or local/session storage; the cookie has HttpOnly and SameSite=Strict.       | The recorded isolated plain-HTTP profile omits Secure; the HTTPS/LAN profile enables it.                                                                      |
| TC-SEC-023                         | The issued expiry is exactly 8 hours after session creation, and the code has no activity-based expiry extension.        | The tracker says a full eight-hour wall-clock wait was not run; it used code-path and boundary-value evidence.                                                |
| TC-SEC-024                         | A foreign-Origin confirm attempt returns 403 ORIGIN_REJECTED and leaves the target incident unchanged.                   | The tracker still marks Pass, and its notes state that no audit row was written because middleware rejected the request before the audited service.           |
| TC-SYS-021                         | Logout clears the cookie, rejects replay, returns the browser to login, and closes the existing WebSocket.               | The scenario demonstrates logout behavior, not every possible WebSocket failure.                                                                              |

The Security Testing sheet has no separate case for the configured login-rate threshold. Describe the limiter from the code and avoid claiming a measured brute-force resistance result.

The tracked WebSocket authentication case does not establish the foreign-Origin ordering. The code checks Origin before it opens the database session, but the tracker’s WebSocket case focuses on unauthenticated and revoked-cookie handshakes.

A stolen cookie remains replayable until the session row is revoked or the absolute expiry passes. HttpOnly prevents a script from reading the cookie, but it does not stop a same-origin injected script from issuing requests through the victim’s browser.

The session row stores user-agent and source-IP metadata, but request authentication does not bind the cookie to those values. Do not say that the token becomes unusable if copied to a different browser or network.

The shared internal API key is a possession credential. If it is exposed from either process or copied from its environment, this check alone cannot distinguish the legitimate AI engine from another caller holding the same key.

The LAN certificate is self-signed and must be installed as trusted on demo clients. This local trust setup is not the same claim as a publicly trusted production certificate. The private key must remain on the server.

A browser warning click-through is not equivalent to installing trust. Without the certificate being trusted and its hostname matching, do not claim that the browser has authenticated the server identity.

## 7. Likely panel questions

### “How is the session protected, and what happens if it leaks?”

The browser cannot read the HttpOnly cookie, Secure limits it to HTTPS when enabled, and SameSite=Strict limits cross-site sending. If the cookie value is stolen, it can be replayed until the server revokes its row or the 8-hour expiry arrives. Logout or an Administrator action makes the next request fail and closes the session’s WebSocket.

### “Why cookies instead of Bearer tokens?”

An HttpOnly cookie keeps the session token out of JavaScript and lets the browser attach it to API and WebSocket requests. It is still a credential if stolen, so we combine it with TLS, SameSite=Strict, Origin checks, and a revocable server-side row. The cookie choice also means we must explain CSRF defenses.

### “What stops a script on the same LAN from faking an accident alert?”

The alert webhook is not authenticated by a browser session; the AI engine sends INTERNAL_API_KEY in x-api-key. The backend checks that secret with constant-time comparison and rejects a wrong key before ingesting the alert; TC-SEC-018 records that rejection. A leaked key would need to be treated as compromised.

### “A self-signed certificate — isn’t that insecure?”

Self-signed means a browser does not trust the certificate automatically; it does not mean the traffic is sent in plaintext. In the LAN demo, clients install the adas.local certificate into their trust store, and the private key stays on the server. Clicking through a warning does not provide the same server-identity check.

### “How do you revoke access immediately?”

Logout marks that session row revoked and closes its matching WebSocket after the commit. An Administrator password reset, account disable, or role change revokes the user’s active rows and closes connected sockets. The tracker records that a revoked cookie fails on the next protected request.

### “Did moving to cookies reintroduce CSRF?”

Cookies are automatic, so the team does not claim Bearer-style structural immunity. SameSite=Strict restricts cross-site cookie sending, and an unsafe request with an unapproved Origin is rejected by the server before the route runs. TC-SEC-024 recorded the rejected state-changing request and no incident change.

### “Isn’t CORS enough to stop cross-site requests?”

No. CORS controls which browser origins can make credentialed cross-origin calls and read their responses; it is not the server’s only state-change check. The Origin middleware actively rejects unsafe requests from an unapproved Origin.

### “Can the JWT be decoded or altered if someone steals it?”

A signed JWT is not encrypted, so its claims can be read by someone holding the token. Changing the claims breaks the signature, and the decoder also checks the configured algorithm, issuer, audience, and expiry before it looks up the revocable session row.

### “Does HttpOnly protect you from an XSS flaw?”

It prevents injected page JavaScript from reading the session token directly. A same-origin script can still make authenticated requests using the browser’s cookie, so HttpOnly reduces credential extraction but does not replace preventing script injection.

### “Can user activity keep the session alive?”

No. The expiry is set when the server creates the session and does not slide forward on later requests. The project requirement caps it at 8 hours; TC-SEC-023 used code-path and boundary-value evidence rather than waiting the full period.

## 8. Cram summary

- Passwords are hashed with Argon2id; the database stores a hash, not readable passwords.
- The browser carries a signed JWT in an HttpOnly cookie with SameSite=Strict and Secure in the HTTPS/LAN profile.
- Every protected request validates the token and checks the linked auth_session row, active user, and current database role.
- Logout, password reset, account disable, and role change can revoke sessions before natural expiry; matching WebSockets are closed.
- The AI webhook uses a separate INTERNAL_API_KEY in x-api-key, checked with constant-time comparison.
- Cookie-based auth needs CSRF controls: SameSite=Strict plus an Origin allowlist for state-changing browser requests.
- WebSocket Origin is checked before the database session opens; the socket then requires the session cookie.
- HTTPS/WSS uses the adas.local certificate in the LAN demo; clients must trust the certificate and the private key stays server-side.
- The tracker records all Security Testing cases as Pass, with important scope notes: no full eight-hour wait, TC-SEC-024 writes no audit row, and rate limiting has no separate Security Testing case.
