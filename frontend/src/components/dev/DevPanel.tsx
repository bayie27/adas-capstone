import { useState } from "react"
import { useQueryClient } from "@tanstack/react-query"
import { useNavigate } from "react-router-dom"

import { NoticeBanner, type NoticeState } from "@/components/ui/NoticeBanner"
import { SidePanel } from "@/components/ui/SidePanel"
import { DEV_STATUS_QUERY_KEY, useDevTools } from "@/hooks/useDevTools"
import { suspendAuthRedirect } from "@/services/api"
import {
  generateHealthHistory,
  injectDetection,
  loginAs,
  reseedProfile,
  setCameraState,
  type DevSeedResult,
  type DevSessionUser,
} from "@/services/dev"
import { useAlertStore } from "@/store/useAlertStore"
import { useAuthStore } from "@/store/useAuthStore"
import { mapApiRoleToAppRole } from "@/utils/auth"
import { getApiErrorMessage } from "@/utils/api"

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
  const [confirmingSlow, setConfirmingSlow] = useState(false)
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

    const appRole = mapApiRoleToAppRole(session.role)
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
      navigate(appRole === "Administrator" ? "/admin" : "/user")
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
    if (profile === SLOW_PROFILE && !confirmingSlow) {
      setConfirmingSlow(true)
      setNotice({
        tone: "error",
        message: "perf seeds 100,000 incidents (~15s). Click again to confirm.",
      })
      return
    }
    setConfirmingSlow(false)

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
              disabled={busy !== null}
              onClick={() => handleReseed(profile.name)}
              className="rounded-lg border border-[#2A2A2A] bg-[#161616] px-3 py-2 text-left transition-colors hover:border-[#3A3A3A] disabled:opacity-50"
            >
              <span className="text-sm font-medium text-white">
                {profile.name}
                {profile.name === SLOW_PROFILE && (
                  <span className="ml-2 text-[10px] uppercase tracking-wide text-[#F59E0B]">
                    slow
                  </span>
                )}
              </span>
              <span className="mt-0.5 block text-xs text-[#A1A1AA]">
                {busy === `reseed:${profile.name}` ? "Seeding..." : profile.description}
              </span>
            </button>
          ))}
        </div>
      </Section>

      <Section title="Simulate">
        <label className="mb-1 block text-xs text-[#A1A1AA]">
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
          className="mb-3 w-full rounded-lg border border-[#2A2A2A] bg-[#0F0F0F] px-3 py-2 text-sm text-white"
        />
        {cameraIdIsInvalid && (
          <p className="-mt-2 mb-3 text-xs text-[#F87171]">
            Enter a whole camera ID, or leave it blank.
          </p>
        )}
        <label className="mb-1 block text-xs text-[#A1A1AA]">
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
              className="rounded-lg border border-[#2A2A2A] bg-[#161616] px-3 py-1.5 text-xs text-white transition-colors hover:border-[#3A3A3A] disabled:opacity-50"
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
      <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-[#71717A]">{title}</h4>
      {children}
    </section>
  )
}

function PanelButton({ children, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      {...props}
      className="w-full rounded-lg border border-[#2A2A2A] bg-[#161616] px-3 py-2 text-sm text-white transition-colors hover:border-[#3A3A3A] disabled:opacity-50"
    >
      {children}
    </button>
  )
}
