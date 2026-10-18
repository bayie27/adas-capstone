import { randomBytes, randomUUID } from "node:crypto"
import { mkdirSync } from "node:fs"
import path from "node:path"

export const E2E_BACKEND_ORIGIN = "http://127.0.0.1:18000"
export const E2E_FRONTEND_ORIGIN = "http://127.0.0.1:15173"

const REPO_ROOT = path.resolve(import.meta.dirname, "..")

function sqliteUrl(databasePath) {
  return `sqlite:///${databasePath.replaceAll("\\", "/")}`
}

export function createIsolatedE2EEnvironment({
  repoRoot = REPO_ROOT,
  disposableDemo = false,
} = {}) {
  const runId = randomUUID()
  const scratchParent = path.resolve(repoRoot, "var", "tmp")
  mkdirSync(scratchParent, { recursive: true })
  const root = path.resolve(repoRoot, "var", "tmp", `mfa-e2e-${runId}`)
  mkdirSync(root, { recursive: false })

  const adminPassword = randomBytes(24).toString("hex")
  const mfaKey = `${randomBytes(32).toString("base64url")}=`
  const storagePath = (name) => path.join(root, name)
  const apiOrigin = E2E_BACKEND_ORIGIN

  return {
    root,
    environment: {
      ...process.env,
      MFA_E2E_MODE: "isolated",
      MFA_E2E_CONTEXT_ID: runId,
      MFA_E2E_ROOT: root,
      ENVIRONMENT: "development",
      SECRET_KEY: randomBytes(32).toString("hex"),
      INTERNAL_API_KEY: randomBytes(32).toString("hex"),
      DEFAULT_ADMIN_PASSWORD: adminPassword,
      E2E_ADMIN_PASSWORD: adminPassword,
      MFA_ENCRYPTION_KEY: mfaKey,
      DATABASE_URL: sqliteUrl(path.join(root, "database.db")),
      SESSION_COOKIE_NAME: "adas_session",
      SESSION_COOKIE_SECURE: "false",
      CORS_ORIGINS: E2E_FRONTEND_ORIGIN,
      SQLITE_BUSY_TIMEOUT_MS: "5000",
      SCHEDULER_ENABLED: "false",
      DEV_TOOLS_ENABLED: disposableDemo ? "true" : "false",
      SNAPSHOT_ROOT: storagePath("snapshots"),
      LEGACY_SNAPSHOT_DIR: storagePath("legacy-snapshots"),
      BACKUP_DIR: storagePath("backups"),
      PROTECTED_BACKUP_DIR: "",
      EXPORT_DIR: storagePath("exports"),
      ARCHIVE_DIR: storagePath("archive"),
      PROTECTED_ARCHIVE_DIR: "",
      LOG_DIR: storagePath("logs"),
      E2E_BACKEND_ORIGIN: apiOrigin,
      E2E_API_BASE_URL: `${apiOrigin}/api`,
      E2E_WS_BASE_URL: "ws://127.0.0.1:18000",
      VITE_API_BASE_URL: `${apiOrigin}/api`,
      VITE_WS_BASE_URL: "ws://127.0.0.1:18000",
    },
  }
}
