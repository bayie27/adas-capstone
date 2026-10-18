# P3 — MFA frontend components, inactive until cutover

> **For agentic workers:** Execute inline in the manually started Luna Max conversation. Use the established frontend design system and relevant UI skill instructions; no automatic implementer delegation or new conversations.

**Goal:** Deliver tested screens/adapters that implement the frozen backend contract without changing the currently active login/Profile flow.  
**Branch:** `feat/mfa-frontend`, from P2's merged main.  
**Read:** Overview, contract §§1/3/6, matrix, CLAUDE.md, existing Login/Profile components and UI patterns.  
**Prerequisites:** P1/P2 merged with their documented exported interfaces. Verify against actual code, not this plan alone.

**Architecture:** Typed cookie-based API adapters, focused transient-state components, and an inactive root-level sensitive-flow provider.  
**Tech stack:** React 19/TypeScript, existing house UI, Axios, qrcode.react, Vitest/Testing Library.  
**Spec:** [01_CONTRACTS.md](01_CONTRACTS.md), especially §§3/6.

## Owned files and interfaces

- Add qrcode.react to frontend/package.json and update pnpm-lock.yaml. Inspect its current React-compatible API; use QRCodeSVG.
- Create `frontend/src/api/mfa.ts` with shared challenge/completion/status types matching contract §3 and adapters for every MFA endpoint. Use an auth-specific Axios instance with withCredentials so proof failures do not trigger the global session-loss interceptor. Preserve real session-loss handling for authenticated management operations.
- Create `frontend/src/pages/auth/MfaChallengePanel.tsx`, `MfaEnrollmentPanel.tsx`, `RecoveryCodesPanel.tsx`, and `MfaLoginFlow.tsx`, each with focused tests; create `frontend/src/pages/profile/MfaSettingsCard.tsx` and `frontend/src/components/auth/MfaSensitiveFlowProvider.tsx` with their tests. The provider/hook interface is fixed in contract §6. Do not wire Login.tsx/ProfileSettings.tsx or mount the provider at the production router root until P4.
- API exports: `beginMfaLogin(credentials)`, `getMfaChallenge()`, `cancelMfaChallenge()`, `getMfaEnrollment()`, `confirmMfaEnrollment(code)`, `verifyMfaChallenge(method, code)`, `getMfaStatus()`, `rotateMfaRecoveryCodes(password, code)`, `beginMfaReplacement(password, code)`, `beginMfaEnrollmentFromSession(password)`. Typed promises use the exact contract response shape; never assume a user profile exists in ChallengeState.
- Components accept callbacks rather than navigating or mutating global stores internally: MfaLoginFlow takes `onAuthenticated(user)`; MfaSettingsCard takes `onSessionRevoked()` immediately after successful replacement and `onSignedOut()` after its code acknowledgment. RecoveryCodesPanel takes `codes`, `accountName`, and `onAcknowledged`; MfaEnrollmentPanel takes `challenge`, `onCompleted(result)`, and `onCancel`; MfaChallengePanel takes `challenge`, `onCompleted(result)`, and `onCancel`. Keep code/seed/password values in local transient state (component or sensitive-flow provider), never persisted stores.

## Task 1 — typed adapters and proof-error handling

- [x] Read current auth.ts, api/client.ts, useAuthStore, realtime close behavior, redirect suspension, Login.tsx, ProfileSettings.tsx, and their tests. Preserve current role labels and component patterns.
- [x] Write failing adapter tests for form-urlencoded password login, JSON MFA submissions, withCredentials, discriminated completion vs challenge handling, and the password-only response not matching the final MFA type. Do not change the currently active auth.ts LoginResponse yet.
- [x] Implement the isolated adapters/types. A 401 MFA_INVALID_CODE or wrong step-up password stays inline; a true expired/revoked management session follows current app behavior. Avoid a blanket ignore-all-401s rule.
- [x] Write countdown tests driven by server expires_at/Retry-After with fake time. Preserve fallback for absent/invalid Retry-After, and prevent changing method/input or restarting password from resetting the server limit. Expired/superseded challenges return to password entry with a clear message.

## Task 2 — login, recovery, and enrollment components

- [x] Write meaningful failing tests for password→mfa_required, initial enrollment, recovery-code choice→recovery_enroll, refresh→safe challenge status, cancellation, and a stale flow. Assert onAuthenticated is never called before final MFA completion and recovery-code acknowledgment where applicable.
- [x] Implement MfaLoginFlow with local state and callback integration seams. Clear the submitted password after success. Do not store ChallengeState as authenticated global role/user state. UI tests run in a small harness with mocked adapters; production Login remains unchanged.
- [x] Implement one ordinary six-digit input with paste and leading-zero support, a deliberate recovery-code choice, accessible labels/error association/focus, keyboard submission, pending-button disabling, and generic inline failures. Do not make six separate boxes whose paste/focus behavior requires an unrelated widget system.
- [x] Fetch provisioning only through the challenge-authorized POST adapter. Render SVG QR plus manual secret, ADAS/account label, expiry guidance, local-only authenticator/cloud-sync-disabled instructions, and confirmation input. No QR SaaS or remote image API.
- [x] Keep seeds/provisioning outside TanStack Query caches and persistence. Refresh resumes through a valid cookie and re-fetches the same pending seed; it never regenerates a seed or extends the deadline. Clear transient state on cancellation, completion, or unmount.
- [x] Test QR URI/manual key consistency, confirmation failure without navigation, expiry, recovery interruption restart instructions, canceled replacement preserving the old factor, and unsupported storage/clipboard conditions. Use only disposable fake secrets in component fixtures.

## Task 3 — recovery-code save screen

- [x] Write failing tests for explicit Copy and Download .txt, inline saving errors, disabled Continue before acknowledgment, completion callback once after acknowledgment, and disappearance of codes after unmount. Add no backend acknowledgment call.
- [x] Implement RecoveryCodesPanel with 10 formatted codes, local Blob download, object URL cleanup, account/date labeling, and offline-storage guidance. Never auto-copy or auto-download. Codes may be manually saved exactly as the product decision allows; ADAS must not claim it verified the save.
- [x] Simulate a lost confirmation response and reloaded code screen. Explain that existing codes cannot be retrieved and the working authenticator allows fresh login/rotation. Do not cache plaintext or introduce idempotent redisplay of a committed batch.
- [x] Test component and route-control callbacks so full enrollment waits for acknowledgment before client auth navigation. The server already issued its cookie; do not misrepresent this UI step as an authorization boundary.

## Task 4 — Profile management and replacement closure

- [x] Write status/failure tests, then implement MfaSettingsCard: factor status/date, remaining-code count, replacement and code-rotation entry points, and fresh password/current-TOTP proof inputs. Never expose a seed via GET status or a disable/admin-reset control.
- [x] For enrolled demo sessions, require the same proofs. For unenrolled demo sessions, offer first enrollment only after fresh password verification; recovery_pending directs the user through password+recovery login. Do not infer that impersonation proves possession of any factor.
- [x] Test voluntary replacement cancellation and confirmation callbacks: only confirmation signs out; rotation leaves current app session active. Use old-factor code only at start and new-factor code at confirmation. Explain that a code just used may require waiting for the next authenticator code.
- [x] Build the provider/handoff seam for successful replacement: register the code display before onSessionRevoked, keep it outside the route guard while local auth clears, and invoke onSignedOut only after acknowledgment. Test the provider in a harness now; P4 mounts it in the production router. Acquire the existing scoped redirect suspension before confirmation so a socket close cannot win the response race; release it on failure/acknowledgment/unmount and do not globally suppress expiry behavior.
- [x] Add route-harness tests proving an unrelated real session loss is still handled, duplicate submissions do not replace a saved batch twice, and secret-bearing values never enter storage/query cache/URL/console calls.

## Verification and completion

```powershell
pnpm --filter frontend test:run src/api/mfa.test.ts src/pages/auth src/pages/profile/MfaSettingsCard.test.tsx
pnpm --filter frontend test:run src/components/auth/MfaSensitiveFlowProvider.test.tsx
pnpm --filter frontend test:run src/pages/Login.test.tsx src/pages/ProfileSettings.test.tsx
pnpm --filter frontend typecheck
```

Run scoped lint/Prettier checks, walk matrix U01–U08, and run `pnpm full:check` once at the pre-PR gate. P3's actual app must still use legacy login/Profile; its existing isolated browser login remains valid. Do not add broad screenshot baselines or rewrite Linux visual snapshots from Windows. Meaningful behavior tests and later P4 browser verification are required even when screenshots look correct.

## Completion notes — executor fills

- Status: PR #243 is open from `feat/mfa-frontend`; implementation and pre-PR verification are complete.
- P1/P2 prerequisites: Verified in updated `main`; P1 PR #241 and P2 PR #242 are merged. Branch HEAD is P2 merge commit `796ea436266d69d34d4d0f2c5521dbb7a54d6d7a`.
- Resolved QR dependency: `qrcode.react@^4.2.0`; React 19-compatible `QRCodeSVG` API typechecks and emits local SVG markup. Provisioning URI secret matches the displayed manual key in the component test.
- Focused MFA results: `pnpm --filter frontend test:run src/api/mfa.test.ts src/api/client.test.ts src/pages/auth/mfaUi.test.ts src/pages/auth/MfaChallengePanel.test.tsx src/pages/auth/MfaEnrollmentPanel.test.tsx src/pages/auth/RecoveryCodesPanel.test.tsx src/pages/auth/MfaLoginFlow.test.tsx src/pages/profile/MfaSettingsCard.test.tsx src/components/auth/MfaSensitiveFlowProvider.test.tsx --reporter=dot` exited 0; 9 files and 45 tests passed.
- Existing-flow regression: `Login.test.tsx` and `ProfileSettings.test.tsx`, 2 files and 11 tests passed. Legacy production flows are untouched.
- Behavior coverage: matrix U01–U08 exercised across adapter, challenge, enrollment, recovery-code, login-flow, Profile-card, provider, and session-interceptor tests. Coverage includes leading-zero paste, challenge refresh/expiry, Retry-After persistence/fallback, acknowledgement and save failures, recovery/replacement flow, sign-out handoff, duplicate confirmation submission, proof failures retaining sessions, and no secret writes to storage/query cache/URL/console.
- Scoped lint/typecheck/Prettier: scoped ESLint, `pnpm --filter frontend typecheck`, and scoped Prettier checks exited 0.
- Required pre-PR gate: first `pnpm full:check` inherited machine RTSP/protected-backup settings and produced two unrelated backend failures. The rerun with `RTSP_URL_TEMPLATE=rtsp://localhost:8554/channel{channel_id}`, `PROTECTED_BACKUP_DIR=` (unset equivalent), and `PYTEST_XDIST_AUTO_NUM_WORKERS=2` exited 0. Ruff: 238 Python files formatted and all checks passed; backend: 1,359 passed, 5 skipped; frontend: 62 files and 395 tests passed; TypeScript, ESLint, Prettier, production build, and Chromium E2E login: 1 passed.
- Existing notices: Vite's `configLoader: 'native'` warning, jsdom media-method notices, Passlib/SQLAlchemy/Starlette deprecations, and Node color-setting warning. No new gate failures remain.
- Paper sync: Local proposal `paper_sync/findings/2026-10-18-mfa-frontend.md` records the qrcode.react claim and pending tracker row 90. The paper and Sheet were read-only; no Drive writes were made.
- Branch/commit/PR: Implementation commit `b12176aa6145990204f1a23d168ce717a6b9dfdb`; [PR #243](https://github.com/bayie27/adas-capstone/pull/243) is open and unmerged. Push used `HUSKY=0` at the user's direction after the required full gate passed; the automatic pre-push `pnpm check` was skipped. The unrelated untracked defense note was preserved.
- Deviations/limitations: P3 components/provider remain unwired and unmounted until P4. Component mocks do not establish physical authenticator, browser camera, or production TLS behavior. No merge or P4 work was performed.

Update this section and the overview row. Leave production wiring to P4; do not start it or merge automatically.
