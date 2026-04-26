import { Suspense, lazy } from "react"
import { BrowserRouter as Router, Routes, Route, Navigate } from "react-router-dom"
import AdminLayout from "@/components/AdminLayout"
import UserLayout from "@/components/UserLayout"
import AuthLayout from "@/components/AuthLayout"
import { ProtectedRoute } from "@/components/ProtectedRoute"

const Login = lazy(() => import("@/pages/Login"))
const Dashboard = lazy(() => import("@/pages/Dashboard"))
const Cameras = lazy(() => import("@/pages/Cameras"))
const Detections = lazy(() => import("@/pages/Detections"))
const SystemHealth = lazy(() => import("@/pages/SystemHealth"))
const AiPerformance = lazy(() => import("@/pages/AiPerformance"))
const ProfileSettings = lazy(() => import("@/pages/ProfileSettings"))
const Users = lazy(() => import("@/pages/Users"))

function RouteFallback() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-[#0A0A0A] text-sm text-[#A1A1AA]">
      Loading...
    </div>
  )
}

function App() {
  return (
    <Router>
      <Suspense fallback={<RouteFallback />}>
        <Routes>
          <Route element={<AuthLayout />}>
            <Route path="/login" element={<Login />} />
          </Route>
          <Route path="/" element={<Navigate to="/login" replace />} />

          <Route
            path="/admin"
            element={
              <ProtectedRoute requiredRole="Administrator">
                <AdminLayout />
              </ProtectedRoute>
            }
          >
            <Route index element={<Dashboard />} />
            <Route path="cameras" element={<Cameras />} />
            <Route path="detections" element={<Detections />} />
            <Route path="health" element={<SystemHealth />} />
            <Route path="ai" element={<AiPerformance />} />
            <Route path="profile" element={<ProfileSettings />} />
            <Route path="users" element={<Users />} />
          </Route>

          <Route
            path="/user"
            element={
              <ProtectedRoute requiredRole="Operator">
                <UserLayout />
              </ProtectedRoute>
            }
          >
            <Route index element={<Dashboard />} />
            <Route path="cameras" element={<Cameras />} />
            <Route path="detections" element={<Detections />} />
            <Route path="health" element={<SystemHealth />} />
            <Route path="ai" element={<AiPerformance />} />
            <Route path="profile" element={<ProfileSettings />} />
          </Route>

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Suspense>
    </Router>
  )
}

export default App
