import { Outlet } from "react-router-dom"
import { Sidebar } from "@/components/layouts/Sidebar"

export default function UserLayout() {
  return (
    <div className="flex h-screen bg-canvas overflow-hidden">
      <Sidebar />
      <main className="flex-1 ml-60 overflow-y-auto">
        <Outlet />
      </main>
    </div>
  )
}
