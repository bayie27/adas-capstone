import { Link, useLocation, useNavigate } from "react-router-dom"

import { logoutUser } from "@/services/auth"
import { useAuthStore } from "@/store/useAuthStore"
import { getUserInitials } from "@/utils/users"
import { cn } from "@/utils/cn"
import {
  RiArrowUpSLine,
  RiCameraLine,
  RiDashboardLine,
  RiLayoutGridLine,
  RiLogoutBoxRLine,
  RiPulseLine,
  RiQuestionLine,
  RiScan2Line,
  RiUserLine,
} from "@remixicon/react"

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

  const basePath = role === "Administrator" ? "/admin" : "/user"

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
        role === "Administrator" ? [{ name: "Users", to: "/admin/users", icon: RiUserLine }] : [],
    },
  ]

  const displayName = username || "guest"
  const displayRole = role ?? "Unknown Role"

  const initials = getUserInitials("", "", displayName)

  const handleLogout = () => {
    // Best-effort — clear the local session either way. The cookie may
    // already be gone, and the user shouldn't be stuck if the request fails.
    logoutUser().catch(() => {})
    clearSession()
    navigate("/login", { replace: true })
  }

  return (
    <aside className="fixed left-0 top-0 flex h-screen w-60 flex-col border-r border-[#2A2A2A] bg-[#141414] text-sm">
      <div className="flex h-16 items-center px-5 border-b border-[#2A2A2A]">
        <div className="flex items-center gap-2.5">
          <img src="/adas-logo.png" alt="ADAS Logo" className="h-auto w-7 object-contain" />
          <span className="font-logo text-base font-semibold tracking-[0.25em] text-white">
            ADAS
          </span>
        </div>
      </div>

      <div className="flex flex-1 flex-col gap-5 overflow-y-auto px-3 py-4">
        {navGroups
          .filter((group) => group.links.length > 0)
          .map((group) => (
            <div key={group.title}>
              <h3 className="mb-1.5 px-3 text-[10px] font-semibold tracking-widest text-[#555]">
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
                        className={cn(
                          "relative flex items-center gap-3 rounded-md px-3 py-2 transition-all duration-150",
                          isActive
                            ? "bg-[#1E1E1E] text-white"
                            : "text-[#737373] hover:bg-[#1A1A1A] hover:text-[#D4D4D4]",
                        )}
                      >
                        {/* Active left accent bar */}
                        {isActive && (
                          <span className="absolute left-0 top-1/2 -translate-y-1/2 h-4 w-[3px] rounded-r-full bg-white" />
                        )}
                        <link.icon size={16} className={isActive ? "text-white" : "text-[#555]"} />
                        <span className="text-[13px] font-medium">{link.name}</span>
                      </Link>
                    </li>
                  )
                })}
              </ul>
            </div>
          ))}
      </div>

      <div className="border-t border-[#2A2A2A] p-3 space-y-0.5">
        <button
          type="button"
          onClick={() => navigate(`${basePath}/help`)}
          className={cn(
            "flex w-full items-center gap-3 rounded-md px-3 py-2 transition-colors",
            location.pathname === `${basePath}/help`
              ? "bg-[#1E1E1E] text-white"
              : "text-[#555] hover:bg-[#1A1A1A] hover:text-[#D4D4D4]",
          )}
        >
          <RiQuestionLine
            size={16}
            className={location.pathname === `${basePath}/help` ? "text-white" : "text-[#555]"}
          />
          <span className="text-[13px] font-medium">Help Center</span>
        </button>

        <div className="group flex cursor-pointer items-center justify-between rounded-md px-3 py-2 transition-colors hover:bg-[#1A1A1A]">
          <div className="flex items-center gap-2.5">
            <div className="flex h-7 w-7 items-center justify-center rounded-full border border-[#333] bg-[#222] text-[10px] font-bold text-[#A1A1AA]">
              {initials || <RiUserLine size={14} className="text-[#A1A1AA]" />}
            </div>
            <div className="flex flex-col">
              <span className="text-[13px] font-medium leading-tight text-[#D4D4D4] group-hover:text-white">
                {displayName}
              </span>
              <span className="text-[11px] text-[#555]">{displayRole}</span>
            </div>
          </div>
          <RiArrowUpSLine size={16} className="text-[#555]" />
        </div>

        <button
          type="button"
          onClick={handleLogout}
          className="flex w-full items-center gap-3 rounded-md px-3 py-2 text-[#555] transition-colors hover:bg-[#1A1A1A] hover:text-[#D4D4D4]"
        >
          <RiLogoutBoxRLine size={16} className="text-[#555]" />
          <span className="text-[13px] font-medium">Log Out</span>
        </button>
      </div>
    </aside>
  )
}
