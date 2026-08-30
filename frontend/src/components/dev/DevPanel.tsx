import { useState } from "react"
import { useQueryClient } from "@tanstack/react-query"
import { useNavigate } from "react-router-dom"

import { NoticeBanner, type NoticeState } from "@/components/ui/NoticeBanner"
import { SidePanel } from "@/components/ui/SidePanel"
import { DEV_STATUS_QUERY_KEY, useDevTools } from "@/hooks/useDevTools"
import { suspendAuthRedirect } from "@/api/client"
import {
  generateHealthHistory,
  injectDetection,
  loginAs,
  reseedProfile,
  resetUatSession,
  setCameraState,
  type DevSeedResult,
  type DevSessionUser,
} from "@/api/dev"
import { useAlertStore } from "@/store/useAlertStore"
import { useAuthStore } from "@/store/useAuthStore"
import { toApiRole } from "@/utils/auth"
import { getApiErrorMessage } from "@/api/client"

const SLOW_PROFILE = "perf"
const SEEDED_ACCOUNTS = ["admin", "dsahagun", "ealonzo", "smeer", "jtenorio"]

interface DevPanelProps {
  isOpen: boolean
  onClose: () => void
}

export default function DevPanel({ isOpen, onClose }: DevPanelProps) {
  const { profiles } = useDevTools()
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const [notice, setNotice] = useState<NoticeState | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [pendingReseedProfile, setPendingReseedProfile] = useState<string | null>(null)
  const [cameraId, setCameraId] = useState("")
  const [confidence, setConfidence] = useState(87)

  const setSession = useAuthStore((state) => state.setSession)
  const bumpSessionEpoch = useAuthStore((state) => state.bumpSessionEpoch)
  const currentRole = useAuthStore((state) => state.role)

  // `inputMode="numeric"` is only a mobile-keyboard hint, not validation —
  // pasted or typed non-digit text still reaches here. Number("abc") is NaN,
  // and JSON.stringify silently turns NaN into null in the request body, so
  // without this check a typo becomes "auto-pick a camera" with no feedback
  // instead of a clear error.
  const trimmedCameraId = cameraId.trim()
  const parsedCameraId = trimmedCameraId === "" ? null : Number(trimmedCameraId)
  const cameraIdIsInvalid =
    parsedCameraId !== null && (!Number.isInteger(parsedCameraId) || parsedCameraId < 1)

  /**
   * Everything a reseed invalidates, in this order.
   *
   * clearAlerts() is the one people forget: handledIds live in
   * sessionStorage, so freshly seeded alerts reusing an old log_id would be
   * silently suppressed. It also stops a playing siren, which matters if you
   * reseed while an alarm is up.
   */
  function applyNewSession(session: DevSessionUser, wipeCache: boolean) {
    if (wipeCache) {
      // The app's query keys are ad-hoc across eight pages, so no scoped
      // invalidation can cover them; clear() is the correct tool here.
      queryClient.clear()
      // ...but clear() also drops the dev-tools probe, which would unmount
      // this very panel. Put it straight back.
      queryClient.setQueryData(DEV_STATUS_QUERY_KEY, {
        enabled: true,
        profiles,
      })
      useAlertStore.getState().clearAlerts()
    } else {
      // login-as changes who is looking, not what there is to look at —
      // but role-scoped responses can differ, so invalidate rather than clear.
      void queryClient.invalidateQueries()
    }

    const appRole = toApiRole(session.role)
    if (!appRole) return
    setSession(appRole, session.username, session.user_id)
    // Both callers of applyNewSession (reseed, login-as) mint a brand new
    // cookie server-side — the live alerts socket must not outlive it. See
    // useAuthStore's sessionEpoch doc: this is deliberately NOT inside
    // setSession() itself, since plain profile edits call that too without
    // rotating anything.
    bumpSessionEpoch()

    // /admin and /user are separate route trees behind ProtectedRoute, so
    // an admin -> operator switch that stayed on /admin/users would bounce.
    if (appRole !== currentRole) {
      navigate(appRole === "Admin" ? "/admin" : "/user")
    }
  }

  async function run(key: string, action: () => Promise<string>) {
    setBusy(key)
    setNotice(null)
    try {
      setNotice({ tone: "success", message: await action() })
    } catch (error) {
      setNotice({
        tone: "error",
        message: getApiErrorMessage(error, "That dev action failed."),
      })
    } finally {
      setBusy(null)
    }
  }

  function handleReseed(profile: string) {
    setPendingReseedProfile(null)
    return run(`reseed:${profile}`, async () => {
      // Awaiting the reseed is necessary but NOT sufficient, which is what
      // driving this in a real browser showed: the wipe deletes every
      // auth_session row, so requests *other components* already had in
      // flight — the alert poll, the camera list, the WebSocket
      // revalidation — come back 401 and the interceptor bounces the
      // operator to /login mid-reseed. Reproduced 2/2 before this guard.
      //
      // So: cancel what is outstanding, and suspend the redirect across the
      // whole operation plus a short grace window for anything that had
      // already left before cancelQueries could reach it.
      const resumeAuthRedirect = suspendAuthRedirect()
      const graceMs = 2000
      try {
        await queryClient.cancelQueries()
        const result = await reseedProfile(profile)
        applyNewSession(result.session, true)
        window.setTimeout(resumeAuthRedirect, graceMs)
        return buildReseedMessage(result)
      } catch (error) {
        resumeAuthRedirect()
        throw error
      }
    })
  }

  function buildReseedMessage(result: DevSeedResult) {
    return (
      `Seeded '${result.profile}': ${result.detections} detections, ` +
      `${result.cameras} cameras, ${result.users} users, ` +
      `${result.health_samples} health rows, ${result.export_jobs} exports, ` +
      `${result.snapshots} snapshots. Signed in as ${result.session.username}.`
    )
  }

  function handleUatReset(
    phase: "operator" | "administrator" | "administrator_healthy",
    label: string,
  ) {
    return run(`uat:${phase}`, async () => {
      const result = await resetUatSession(phase)
      useAlertStore.getState().clearAlerts()
      await queryClient.invalidateQueries()
      return (
        `${label} ready. Cleared ${result.removed_session_detections} prior session ` +
        `detection(s) and preserved ${result.preserved_audit_rows} audit row(s).`
      )
    })
  }

  return (
    <SidePanel
      isOpen={isOpen}
      onClose={onClose}
      title="Dev tools"
      subtitle="Seed data, fire incidents and switch accounts without the AI engine."
    >
      {notice && (
        <div className="mb-4">
          <NoticeBanner notice={notice} />
        </div>
      )}

      <Section title="Data">
        <div className="flex flex-col gap-2">
          {profiles.map((profile) => (
            <button
              key={profile.name}
              type="button"
              disabled={busy !== null}
              aria-pressed={pendingReseedProfile === profile.name}
              onClick={() => {
                setNotice(null)
                setPendingReseedProfile(profile.name)
              }}
              className="rounded-lg border border-stroke bg-surface-1 px-3 py-2 text-left transition-colors hover:border-stroke-strong disabled:opacity-50"
            >
              <span className="text-sm font-medium text-fg">
                {profile.name}
                {profile.name === SLOW_PROFILE && (
                  <span className="ml-2 text-[10px] uppercase tracking-wide text-warning">
                    slow
                  </span>
                )}
              </span>
              <span className="mt-0.5 block text-xs text-fg-muted">
                {busy === `reseed:${profile.name}` ? "Seeding..." : profile.description}
              </span>
            </button>
          ))}
        </div>

        {pendingReseedProfile && (
          <div
            role="alert"
            className="mt-3 rounded-lg border border-danger-border bg-danger-subtle p-3"
          >
            <p className="text-sm font-semibold text-danger">Confirm destructive reseed</p>
            <p className="mt-1 text-xs leading-relaxed text-danger">
              Reseeding &apos;{pendingReseedProfile}&apos; permanently replaces the development
              database and active sessions. This cannot be undone from this panel.
              {pendingReseedProfile === SLOW_PROFILE
                ? " The perf profile also writes 100,000 incidents and can take about 15 seconds."
                : ""}
            </p>
            <div className="mt-3 flex gap-2">
              <button
                type="button"
                disabled={busy !== null}
                onClick={() => handleReseed(pendingReseedProfile)}
                className="flex-1 rounded-lg border border-danger-border bg-danger px-3 py-2 text-xs font-semibold text-surface-3 disabled:opacity-50"
              >
                Confirm reseed &apos;{pendingReseedProfile}&apos;
              </button>
              <button
                type="button"
                disabled={busy !== null}
                onClick={() => setPendingReseedProfile(null)}
                className="rounded-lg border border-stroke bg-surface-1 px-3 py-2 text-xs text-fg disabled:opacity-50"
              >
                Cancel reseed
              </button>
            </div>
          </div>
        )}
      </Section>

      <Section title="Simulate">
        <label className="mb-1 block text-xs text-fg-muted">
          Camera ID (blank picks a free one)
        </label>
        <input
          value={cameraId}
          onChange={(e) => setCameraId(e.target.value)}
          type="number"
          min={1}
          step={1}
          inputMode="numeric"
          placeholder="auto"
          className="mb-3 w-full rounded-lg border border-stroke bg-canvas px-3 py-2 text-sm text-fg"
        />
        {cameraIdIsInvalid && (
          <p className="-mt-2 mb-3 text-xs text-danger">
            Enter a whole camera ID, or leave it blank.
          </p>
        )}
        <label className="mb-1 block text-xs text-fg-muted">
          Confidence: {(confidence / 100).toFixed(2)}
        </label>
        <input
          type="range"
          min={0}
          max={100}
          value={confidence}
          onChange={(e) => setConfidence(Number(e.target.value))}
          className="mb-3 w-full"
        />
        <PanelButton
          disabled={busy !== null || cameraIdIsInvalid}
          onClick={() =>
            run("inject", async () => {
              const result = await injectDetection({
                ...(parsedCameraId !== null ? { camera_id: parsedCameraId } : {}),
                confidence: confidence / 100,
              })
              await queryClient.invalidateQueries()
              return `Incident ${result.log_id} raised on camera ${result.camera_id}.`
            })
          }
        >
          Inject a detection
        </PanelButton>

        <div className="mt-2 grid grid-cols-2 gap-2">
          <PanelButton
            disabled={busy !== null || parsedCameraId === null || cameraIdIsInvalid}
            onClick={() =>
              run("stale", async () => {
                // Disabled above whenever parsedCameraId isn't a valid
                // integer, so this branch only runs with a real value.
                await setCameraState(parsedCameraId as number, { stale_heartbeat: true })
                await queryClient.invalidateQueries()
                return `Camera ${cameraId} now presents as Unresponsive.`
              })
            }
          >
            Make stale
          </PanelButton>
          <PanelButton
            disabled={busy !== null || parsedCameraId === null || cameraIdIsInvalid}
            onClick={() =>
              run("cooldown", async () => {
                await setCameraState(parsedCameraId as number, { clear_cooldown: true })
                await queryClient.invalidateQueries()
                return `Cooldown cleared on camera ${cameraId}.`
              })
            }
          >
            Clear cooldown
          </PanelButton>
        </div>

        <div className="mt-2">
          <PanelButton
            disabled={busy !== null}
            onClick={() =>
              run("health", async () => {
                const rows = await generateHealthHistory(7)
                await queryClient.invalidateQueries()
                return rows === 0
                  ? "History already present — nothing written."
                  : `Wrote ${rows} health rows over 7 days.`
              })
            }
          >
            Generate 7 days of health history
          </PanelButton>
        </div>
      </Section>

      {profiles.some((profile) => profile.name === "uat") && (
        <Section title="UAT session preparation">
          <p className="mb-3 text-xs text-fg-muted">
            Use these after seeding uat. They restore journey fixtures without erasing earlier
            participant audit evidence.
          </p>
          <div className="flex flex-col gap-2">
            <PanelButton
              disabled={busy !== null}
              onClick={() => handleUatReset("operator", "Operator session")}
            >
              {busy === "uat:operator" ? "Preparing..." : "Prepare next Operator"}
            </PanelButton>
            <PanelButton
              disabled={busy !== null}
              onClick={() => handleUatReset("administrator", "Administrator session")}
            >
              {busy === "uat:administrator" ? "Preparing..." : "Prepare next Administrator"}
            </PanelButton>
            <PanelButton
              disabled={busy !== null}
              onClick={() =>
                handleUatReset("administrator_healthy", "Administrator healthy baseline")
              }
            >
              {busy === "uat:administrator_healthy"
                ? "Restoring..."
                : "Restore AD-J02 healthy baseline"}
            </PanelButton>
          </div>
        </Section>
      )}

      <Section title="Session">
        <div className="flex flex-wrap gap-2">
          {SEEDED_ACCOUNTS.map((username) => (
            <button
              key={username}
              disabled={busy !== null}
              onClick={() =>
                run(`login:${username}`, async () => {
                  const { session } = await loginAs(username)
                  applyNewSession(session, false)
                  return `Signed in as ${session.username} (${session.role}).`
                })
              }
              className="rounded-lg border border-stroke bg-surface-1 px-3 py-1.5 text-xs text-fg transition-colors hover:border-stroke-strong disabled:opacity-50"
            >
              {username}
            </button>
          ))}
        </div>
      </Section>
    </SidePanel>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mb-6">
      <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-fg-muted">{title}</h4>
      {children}
    </section>
  )
}

function PanelButton({ children, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      {...props}
      className="w-full rounded-lg border border-stroke bg-surface-1 px-3 py-2 text-sm text-fg transition-colors hover:border-stroke-strong disabled:opacity-50"
    >
      {children}
    </button>
  )
}
