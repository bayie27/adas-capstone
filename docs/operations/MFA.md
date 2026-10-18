# MFA operations

[Operations index](README.md) · [Validation guide](../validation/mfa-validation.md)

This guide covers the MFA behavior in the current application. It does not authorize a
production cutover or a live database repair. Normal user sessions require a password
and a TOTP authenticator proof. A recovery code starts recovery; it does not create a
normal session by itself.

## User enrollment and recovery

At first sign-in, enter the account password, scan the displayed QR code with an
authenticator app or enter the manual setup key, then confirm with the current
six-digit code. ADAS shows a new batch of ten one-time recovery codes after successful
enrollment. The user must save them before acknowledging the screen. ADAS does not
verify that a file or paper copy exists, and it cannot redisplay the batch after the
screen is dismissed or reloaded.

Keep the authenticator's device copy and recovery-code copy under the organization's
credential-handling policy. Store recovery codes away from the phone. If the
authenticator offers cloud sync, the user should disable sync for this entry where the
app supports it and use an approved configuration. ADAS cannot inspect or enforce the
authenticator app's storage or cloud-sync behavior.

If a user can still authenticate but has misplaced the recovery batch, **Profile →
Rotate recovery codes** requires the current password and a fresh TOTP proof. It
replaces the entire batch and leaves current sessions active. Codes from the old batch
stop working.

If the authenticator is unavailable, the user can submit one unused recovery code at
sign-in. That immediately consumes the code, disables the old authenticator, and
revokes all sessions. The user must enroll a new authenticator and confirm its TOTP
code before ADAS issues a replacement recovery batch and creates a normal session. If
the challenge expires or the browser flow is lost, the user must start again with a
different unused recovery code. Using the final code and then losing or expiring the
pending setup leaves no code to restart recovery.

Voluntary replacement is different from recovery. While the current authenticator
works, **Profile → Replace authenticator** requires the password and a fresh current
TOTP. The old authenticator stays active until the new one is confirmed. Cancel or
expiry leaves the old factor in place. Confirmation switches factors, issues a new
recovery batch, and signs the user out on every device. The one-time code screen stays
visible until acknowledgment; if it is lost or reloaded, ADAS cannot redisplay that
batch.

There is no in-app or Administrator MFA reset. Resetting a password changes only the
password and does not bypass the authenticator. If the user loses the authenticator
and all unused recovery codes, the application has no recovery path; follow a
separately approved organizational escalation process, if one exists. Do not use a
database edit or restore as a routine factor-reset procedure.

## Generate and protect the stable encryption key

Each deployment needs one stable Fernet key in `MFA_ENCRYPTION_KEY`. Startup fails if
the key is missing or malformed, or if stored seeds cannot be decrypted. The key is
not a backup artifact and must not appear in source control, normal backup manifests,
command arguments, screenshots, logs, PR descriptions, or shared cloud notes.

Generate it once on the deployment host from the repository root, writing directly to
a restricted file so the key is not printed into the terminal:

```powershell
$secretDir = 'C:\ProgramData\ADAS\secrets'
$servicePrincipal = 'MACHINE\adas-service'
New-Item -ItemType Directory -Force -Path $secretDir | Out-Null
icacls $secretDir /inheritance:r /grant:r `
  "${servicePrincipal}:(OI)(CI)F" "SYSTEM:(OI)(CI)F" "BUILTIN\Administrators:(OI)(CI)F"
$env:ADAS_MFA_KEY_PATH = Join-Path $secretDir 'mfa-encryption.key'
uv run python -c "import os; from pathlib import Path; from cryptography.fernet import Fernet; Path(os.environ['ADAS_MFA_KEY_PATH']).write_bytes(Fernet.generate_key())"
Remove-Item Env:ADAS_MFA_KEY_PATH
icacls (Join-Path $secretDir 'mfa-encryption.key') /inheritance:r /grant:r `
  "${servicePrincipal}:F" "SYSTEM:F" "BUILTIN\Administrators:F"
```

Replace the example service principal with the identity that runs the backend and
maintenance coordinator. On a development laptop, the current account may own the
key file. Verify the resulting ACL with `icacls`; restrict access to the service
identity and named recovery custodians. Host administrators can override file ACLs,
so this is an operator control, not an ADAS-enforced guarantee.

For Linux, use a directory outside the checkout with owner-only access, for example
`install -d -m 0700 /etc/adas/secrets`, and create the file with mode `0600`. The
service identity and recovery custodian must be recorded in the deployment runbook.

Load the file into the service's environment through the deployment's protected
secret mechanism. For a temporary PowerShell launch, the value can be read into the
process environment without placing it in the command line:

```powershell
$env:MFA_ENCRYPTION_KEY = (Get-Content -Raw $keyPath).Trim()
pwsh -File scripts/start-dev.ps1 -Backend
Remove-Item Env:MFA_ENCRYPTION_KEY
```

The child backend receives the variable from its parent process. Do not pass the key
as a command argument or print it for copy/paste. Persistent services should inject
the environment variable from a protected secret store or a file whose ACL is
restricted to the service and recovery identities.

Keep a second escrow copy in an independently secured offline location, separate
from the ADAS host and its ordinary backup set. Assign named custody and recovery
responsibilities, and periodically prove that the escrow copy decrypts a disposable
current-head backup on an isolated candidate. The demo laptop cannot satisfy this
physical separation by itself. ADAS does not track escrow custody. Version 1 has no
key-rotation command; retained backups require the same key that encrypted their
seeds. Copying only the database to a replacement host is insufficient.

## Preflight before a development cutover

Before any separately approved operational cutover, the operator and system owner
should confirm all of the following:

- A current, verified backup exists and can be restored with the escrowed key.
- The selected restore point matches the current MFA-enabled migration head; older or
  pre-MFA snapshots are refused and are not auto-migrated.
- The required stable key is present through the protected service environment and
  the offline escrow copy has been tested separately.
- `DEV_TOOLS_ENABLED=false` is set explicitly for operational use. Demo sessions are
  visibly labeled and rejected when the flag is off.
- Real user accounts, rather than demo impersonation, are ready for planned
  enrollment. Users have access to an approved authenticator and know where to store
  the one-time recovery batch.
- Host time synchronization, HTTPS certificates, Secure-cookie handling, WebSocket
  access, backup storage, service restart, and recovery ownership have been checked
  for the target environment.

Scheduling with Lipa CDRRMO, live enrollment, and production acceptance are separate
human decisions. A one-laptop code exercise does not qualify the deployment.

## Restore and emergency rollback

The supported restore accepts a backup made with the current MFA-capable schema and
the matching stable key. It validates a temporary candidate copy, verifies every
stored seed, invalidates candidate sessions and pending challenges, writes the
restore-invalidation audit event, then verifies the transformed candidate before
swap. It does not alter the selected backup or silently migrate an older snapshot.
The emergency rollback candidate follows the same session and challenge invalidation
policy.

After either path, users must authenticate again. The selected snapshot's
authenticator and recovery state returns with its database contents. An older
authenticator seed or previously unused recovery code can therefore become usable
again. Review affected accounts and, when needed, replace retired factors or rotate
recovery batches through their normal fresh-proof flows before operational
acceptance. Do not restore a compromised factor as a recovery technique. Keep the
matching application code and stable key with each retained backup set.

For the normal operator workflow, use **Maintenance → Restore this backup** and let
the supervised coordinator stop services, swap the validated database, restart the
stack, and confirm readiness. The offline CLI is for the host recovery procedure
while services are stopped; it is not a database repair or password-reset tool. A
restore drill must record the actual end-to-end time through service readiness and
the required heartbeat. Database replacement time alone does not establish the
existing 60-second recovery target.
