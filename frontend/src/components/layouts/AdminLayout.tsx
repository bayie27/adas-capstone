import { Outlet } from "react-router-dom"
import { Sidebar } from "@/components/layouts/Sidebar"

export default function AdminLayout() {
  return (
    <div className="flex h-screen bg-[#0A0A0A] overflow-hidden">
      <Sidebar />
      <main className="flex-1 ml-60 overflow-y-auto">
        <Outlet />
      </main>
    </div>
  )
}
