import { Outlet } from "react-router-dom"
import { Sidebar } from "@/components/layouts/Sidebar"

/**
 * The one authenticated shell. AdminLayout and UserLayout were byte-identical
 * apart from their exported names — the role difference lives in the sidebar's
 * nav groups and in the route guard, not in the frame around them.
 */
export default function AppLayout() {
  return (
    <div className="flex h-screen overflow-hidden bg-canvas">
      <Sidebar />
      <main className="ml-[272px] flex-1 overflow-y-auto">
        <Outlet />
      </main>
    </div>
  )
}
