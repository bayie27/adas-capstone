import { Suspense, lazy } from "react"
import { BrowserRouter as Router, Routes, Route, Navigate } from "react-router-dom"
import AppLayout from "@/components/layouts/AppLayout"
import AuthLayout from "@/components/layouts/AuthLayout"
import { GlobalAlerts } from "@/components/GlobalAlerts"
import { MaintenanceNotice } from "@/components/MaintenanceNotice"
import { ProtectedRoute } from "@/components/ProtectedRoute"
import { RealtimeAlertsBridge } from "@/components/RealtimeAlertsBridge"
import { ErrorBoundary } from "@/components/ErrorBoundary"
import { DevPanelTrigger } from "@/components/dev/DevPanelTrigger"

const Login = lazy(() => import("@/pages/Login"))
const Dashboard = lazy(() => import("@/pages/Dashboard"))
const Cameras = lazy(() => import("@/pages/Cameras"))
const Detections = lazy(() => import("@/pages/Detections"))
const SystemHealth = lazy(() => import("@/pages/SystemHealth"))
const AiPerformance = lazy(() => import("@/pages/AiPerformance"))
const ProfileSettings = lazy(() => import("@/pages/ProfileSettings"))
const HelpCenter = lazy(() => import("@/pages/HelpCenter"))
const Users = lazy(() => import("@/pages/Users"))

function RouteFallback() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-canvas text-sm text-fg-muted">
      Loading...
    </div>
  )
}

function App() {
  return (
    <Router>
      <RealtimeAlertsBridge />
      <GlobalAlerts />
      {/* Same placement as GlobalAlerts: inside Router (useNavigate) and
          QueryClientProvider (useQueryClient), but outside ErrorBoundary and
          Suspense so it survives a page crash and lazy-route loading — and
          so it is available on /login too. */}
      <MaintenanceNotice />
      <DevPanelTrigger />
      <ErrorBoundary>
        <Suspense fallback={<RouteFallback />}>
          <Routes>
            <Route element={<AuthLayout />}>
              <Route path="/login" element={<Login />} />
            </Route>
            <Route path="/" element={<Navigate to="/login" replace />} />

            <Route
              path="/admin"
              element={
                <ProtectedRoute requiredRole="Admin">
                  <AppLayout />
                </ProtectedRoute>
              }
            >
              <Route index element={<Dashboard />} />
              <Route path="cameras" element={<Cameras />} />
              <Route path="detections" element={<Detections />} />
              <Route path="health" element={<SystemHealth />} />
              <Route path="ai" element={<AiPerformance />} />
              <Route path="profile" element={<ProfileSettings />} />
              <Route path="help" element={<HelpCenter />} />
              <Route path="users" element={<Users />} />
            </Route>

            <Route
              path="/user"
              element={
                <ProtectedRoute requiredRole="Operator">
                  <AppLayout />
                </ProtectedRoute>
              }
            >
              <Route index element={<Dashboard />} />
              <Route path="cameras" element={<Cameras />} />
              <Route path="detections" element={<Detections />} />
              <Route path="health" element={<SystemHealth />} />
              <Route path="ai" element={<AiPerformance />} />
              <Route path="profile" element={<ProfileSettings />} />
              <Route path="help" element={<HelpCenter />} />
            </Route>

            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Suspense>
      </ErrorBoundary>
    </Router>
  )
}

export default App
