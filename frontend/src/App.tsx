import { Suspense, lazy } from "react"
import { BrowserRouter as Router, Routes, Route, Navigate } from "react-router-dom"
import AppLayout from "@/components/layouts/AppLayout"
import AuthLayout from "@/components/layouts/AuthLayout"
import { GlobalAlerts } from "@/components/GlobalAlerts"
import { MaintenanceNotice } from "@/components/MaintenanceNotice"
import { DeliveryBacklogNotice } from "@/components/DeliveryBacklogNotice"
import { ProtectedRoute } from "@/components/ProtectedRoute"
import { RealtimeAlertsBridge } from "@/components/RealtimeAlertsBridge"
import { ErrorBoundary } from "@/components/ErrorBoundary"
import { DevPanelTrigger } from "@/components/dev/DevPanelTrigger"
import { ExportJobsTray } from "@/components/exports/ExportJobsTray"
import { OngoingIncidentsTray } from "@/components/alerts/OngoingIncidentsTray"
import { ToastContainer } from "@/components/ui/ToastContainer"
import { useDeliveryBacklog } from "@/hooks/useDeliveryBacklog"

const Login = lazy(() => import("@/pages/Login"))
const Dashboard = lazy(() => import("@/pages/Dashboard"))
const Cameras = lazy(() => import("@/pages/Cameras"))
const Detections = lazy(() => import("@/pages/Detections"))
const SystemHealth = lazy(() => import("@/pages/SystemHealth"))
const AiPerformance = lazy(() => import("@/pages/AiPerformance"))
const ProfileSettings = lazy(() => import("@/pages/ProfileSettings"))
const HelpCenter = lazy(() => import("@/pages/HelpCenter"))
const Users = lazy(() => import("@/pages/Users"))
const AuditLog = lazy(() => import("@/pages/AuditLog"))
const Maintenance = lazy(() => import("@/pages/Maintenance"))

function RouteFallback() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-canvas text-sm text-fg-muted">
      Loading...
    </div>
  )
}

function App() {
  const deliveryBacklog = useDeliveryBacklog()

  return (
    <Router>
      <RealtimeAlertsBridge />
      <GlobalAlerts />
      {/* Same placement as GlobalAlerts: inside Router (useNavigate) and
          QueryClientProvider (useQueryClient), but outside ErrorBoundary and
          Suspense so it survives a page crash and lazy-route loading — and
          so it is available on /login too. */}
      <MaintenanceNotice />
      {/* useDeliveryBacklog always returns null today (G5) -- mounted
          anyway, same idiom as MaintenanceNotice, so this renders live and
          simply has nothing to say most of the time. */}
      {deliveryBacklog ? <DeliveryBacklogNotice {...deliveryBacklog} /> : null}
      <DevPanelTrigger />
      {/* Lower right floating overlays: Tray buttons & Toasts */}
      <div className="fixed bottom-5 right-5 z-[9990] flex flex-col items-end gap-3 pointer-events-none">
        <div className="flex items-center gap-3">
          <ExportJobsTray />
          <OngoingIncidentsTray />
        </div>
        <ToastContainer />
      </div>
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
              <Route path="audit" element={<AuditLog />} />
              <Route path="maintenance" element={<Maintenance />} />
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
