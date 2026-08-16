import { Link, useLocation, useNavigate } from "react-router-dom"

import { logoutUser } from "@/api/auth"
import { useAlertStore } from "@/store/useAlertStore"
import { useAuthStore } from "@/store/useAuthStore"
import { formatUserRole, getUserInitials } from "@/utils/format"
import { formatDuration } from "@/utils/datetime"
import { cn } from "@/utils/cn"
import { focusRing } from "@/components/ui/Button"
import {
  RiAlertLine,
  RiCameraLine,
  RiDashboardLine,
  RiFileHistoryLine,
  RiHardDrive2Line,
  RiLayoutGridLine,
  RiLogoutBoxRLine,
  RiPulseLine,
  RiQuestionLine,
  RiScan2Line,
  RiUserLine,
} from "@remixicon/react"

/**
 * D-13: correct silently everywhere a relative time renders (useNow,
 * formatRelativeDateTime), but don't correct *silently* past this point — a
 * console whose clock disagrees with the server by more than a trivial
 * amount is itself worth knowing about, not just working around. Below the
 * threshold, correction happens with no visible trace, since a few seconds
 * of skew is normal network/NTP noise, not a fact an operator needs.
 */
const CLOCK_SKEW_WARNING_MS = 60_000

type NavLinkItem = {
  name: string
  to: string
  icon: typeof RiLayoutGridLine
}

export function Sidebar() {
  const location = useLocation()
  const navigate = useNavigate()
  const role = useAuthStore((state) => state.role)
  const username = useAuthStore((state) => state.username)
  const clearSession = useAuthStore((state) => state.clearSession)
  const clockOffsetMs = useAlertStore((state) => state.clockOffsetMs)
  const clockIsSkewed = Math.abs(clockOffsetMs) > CLOCK_SKEW_WARNING_MS
  const connectionId = useAlertStore((state) => state.connectionId)

  const basePath = role === "Admin" ? "/admin" : "/user"

  /**
   * Design gate D-1, settled: `Administration` is three flat nav items —
   * Users, Audit Log, Maintenance — with the same treatment as every other
   * row, no sub-group and no fourth eyebrow. The last two ship with their
   * screens in Phases 16 and 18; adding them is one entry each rather than a
   * sidebar rebuild, which is what the gate existed to prevent.
   */
  const navGroups: Array<{ title: string; links: NavLinkItem[] }> = [
    {
      title: "OPERATIONS",
      links: [
        { name: "Dashboard", to: basePath, icon: RiLayoutGridLine },
        { name: "Cameras", to: `${basePath}/cameras`, icon: RiCameraLine },
        { name: "Detections", to: `${basePath}/detections`, icon: RiScan2Line },
      ],
    },
    {
      title: "MONITORING",
      links: [
        { name: "System Health", to: `${basePath}/health`, icon: RiPulseLine },
        { name: "AI Performance", to: `${basePath}/ai`, icon: RiDashboardLine },
      ],
    },
    {
      title: "ADMINISTRATION",
      links:
        role === "Admin"
          ? [
              { name: "Users", to: "/admin/users", icon: RiUserLine },
              { name: "Audit Log", to: "/admin/audit", icon: RiFileHistoryLine },
              { name: "Maintenance", to: "/admin/maintenance", icon: RiHardDrive2Line },
            ]
          : [],
    },
  ]

  const displayName = username || "guest"
  const displayRole = formatUserRole(role)

  const initials = getUserInitials("", "", displayName)

  const handleLogout = () => {
    // Best-effort — clear the local session either way. The cookie may
    // already be gone, and the user shouldn't be stuck if the request fails.
    logoutUser().catch(() => {})
    clearSession()
    navigate("/login", { replace: true })
  }

  const isHelpActive = location.pathname === `${basePath}/help`

  // §2.8 — nav rest / hover / active, shared by the links and the two footer
  // buttons so the Help Center row cannot drift from the rows above it.
  const navRow = "flex items-center gap-3 rounded-md px-3 py-2 transition-colors duration-150"
  const navInactive = "text-fg-muted hover:bg-surface-1 hover:text-fg-body"
  const navActive = "bg-surface-2 text-fg"

  return (
    <aside className="fixed left-0 top-0 flex h-screen w-[272px] flex-col border-r border-stroke bg-surface-1 text-sm">
      <div className="flex h-16 items-center border-b border-stroke px-5">
        <div className="flex items-center gap-2.5">
          <img src="/adas-logo.png" alt="ADAS Logo" className="h-auto w-7 object-contain" />
          <span className="text-base font-bold tracking-[0.25em] text-fg">ADAS</span>
        </div>
      </div>

      <nav aria-label="Main" className="flex flex-1 flex-col gap-5 overflow-y-auto px-5 py-4">
        {navGroups
          .filter((group) => group.links.length > 0)
          .map((group) => (
            <div key={group.title}>
              <h3 className="mb-1.5 px-3 text-[10px] font-semibold tracking-widest text-fg-muted">
                {group.title}
              </h3>
              <ul className="space-y-0.5">
                {group.links.map((link) => {
                  const isActive =
                    location.pathname === link.to ||
                    (link.to !== basePath && location.pathname.startsWith(`${link.to}/`))

                  return (
                    <li key={link.name}>
                      <Link
                        to={link.to}
                        aria-current={isActive ? "page" : undefined}
                        className={cn(
                          "relative",
                          navRow,
                          isActive ? navActive : navInactive,
                          focusRing,
                        )}
                      >
                        {/* Active left accent bar — in the code, not the Figma
                            symbol; a small, good addition kept deliberately. */}
                        {isActive && (
                          <span className="absolute left-0 top-1/2 h-4 w-[3px] -translate-y-1/2 rounded-r-full bg-primary" />
                        )}
                        <link.icon size={16} className={isActive ? "text-fg" : "text-fg-muted"} />
                        <span className="text-[13px] font-medium">{link.name}</span>
                      </Link>
                    </li>
                  )
                })}
              </ul>
            </div>
          ))}
      </nav>

      <div className="space-y-0.5 border-t border-stroke p-3">
        {clockIsSkewed ? (
          <div
            role="status"
            className="mb-1 flex items-start gap-1.5 rounded-md border border-warning-border bg-warning-subtle px-3 py-2 text-[11px] text-warning"
          >
            <RiAlertLine size={13} className="mt-0.5 shrink-0" aria-hidden="true" />
            <span>
              This device's clock is off by{" "}
              {formatDuration(Math.round(Math.abs(clockOffsetMs) / 1000))} from the server. Relative
              times are corrected automatically, but the system clock itself should be fixed.
            </span>
          </div>
        ) : null}

        <button
          type="button"
          onClick={() => navigate(`${basePath}/help`)}
          aria-current={isHelpActive ? "page" : undefined}
          className={cn("w-full", navRow, isHelpActive ? navActive : navInactive, focusRing)}
        >
          <RiQuestionLine size={16} className={isHelpActive ? "text-fg" : "text-fg-muted"} />
          <span className="text-[13px] font-medium">Help Center</span>
        </button>

        {/* Identity label, not a control. This carried `cursor-pointer`, a
            hover fill and a disclosure chevron while having no handler at all,
            so it advertised a menu that was never built — and the one screen
            such a menu would lead to, /profile, has no inbound link anywhere
            in the app. Whether the chip becomes a link or a real dropdown is
            a design question (D-3); until it is answered the honest render is
            a static label that does not claim to be clickable. */}
        <div className="flex items-center gap-2.5 px-3 py-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-full border border-stroke-strong bg-surface-2 text-[10px] font-bold text-fg-muted">
            {initials || <RiUserLine size={14} className="text-fg-muted" />}
          </div>
          <div className="flex flex-col">
            <span className="text-[13px] font-medium leading-tight text-fg-sidebar">
              {displayName}
            </span>
            <span className="text-[11px] text-fg-muted">{displayRole}</span>
          </div>
        </div>

        <button
          type="button"
          onClick={handleLogout}
          className={cn("w-full", navRow, navInactive, focusRing)}
        >
          <RiLogoutBoxRLine size={16} className="text-fg-muted" />
          <span className="text-[13px] font-medium">Log Out</span>
        </button>

        {/*
          ConnectionReadyData.connection_id — the handle that identifies this
          socket in the backend log. Purely diagnostic, so it gets the
          lowest-priority treatment in the footer: truncated, monospace, no
          affordance. Its only job is to be quotable in a support
          conversation ("the alerts stopped updating on session a1b2c3d4"),
          which a full UUID doesn't need to be to serve.
        */}
        {connectionId ? (
          <p
            className="truncate px-3 pt-1 font-mono text-[10px] text-fg-muted"
            title={connectionId}
          >
            Session {connectionId.slice(0, 8)}
          </p>
        ) : null}
      </div>
    </aside>
  )
}
