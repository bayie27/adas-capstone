import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter } from "react-router-dom"
import { beforeEach, describe, expect, it, vi } from "vitest"

import ProfileSettings from "./ProfileSettings"
import type { UserRecord } from "@/api/users"

vi.mock("@/api/users", async () => {
  const actual = await vi.importActual<typeof import("@/api/users")>("@/api/users")
  return {
    ...actual,
    getMyProfile: vi.fn(),
    updateMyProfile: vi.fn(),
  }
})

vi.mock("@/api/settings", async () => {
  const actual = await vi.importActual<typeof import("@/api/settings")>("@/api/settings")
  return {
    ...actual,
    getAlarmSettings: vi.fn().mockResolvedValue({
      alarm_sound: "default",
      volume: 80,
      snooze_duration: 30,
      options: {
        alarm_sound_keys: ["default", "chime"],
        snooze_min_seconds: 15,
        snooze_max_seconds: 60,
        volume_min: 0,
        volume_max: 100,
      },
    }),
    updateAlarmSettings: vi.fn(),
  }
})

import { getMyProfile, updateMyProfile } from "@/api/users"
import { updateAlarmSettings } from "@/api/settings"
import { ToastContainer } from "@/components/ui/ToastContainer"
import { toast } from "@/store/useToastStore"

const mockProfile: UserRecord = {
  user_id: 10,
  username: "ibrahim.mahdi",
  first_name: "Ibrahim",
  last_name: "Mahdi",
  role: "Operator",
  is_active: true,
  created_at: "2026-01-15T08:00:00Z",
  updated_at: "2026-08-01T12:00:00Z",
  password_changed_at: "2026-07-20T10:00:00Z",
  last_login: "2026-08-25T14:30:00Z",
}

function renderProfileSettings() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <ToastContainer />
        <ProfileSettings />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe("ProfileSettings Page", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    toast.clear()
  })

  it("renders profile details in card-based layout", async () => {
    vi.mocked(getMyProfile).mockResolvedValue(mockProfile)

    renderProfileSettings()

    expect(await screen.findByText("Ibrahim Mahdi")).toBeInTheDocument()
    expect(screen.getByText("@ibrahim.mahdi")).toBeInTheDocument()
    expect(screen.getByText("Personal Information")).toBeInTheDocument()
    expect(screen.getByText("Security & Password")).toBeInTheDocument()
    expect(screen.getByText("Active")).toBeInTheDocument()
  })

  it("opens edit profile modal and submits updates", async () => {
    const user = userEvent.setup()
    vi.mocked(getMyProfile).mockResolvedValue(mockProfile)
    vi.mocked(updateMyProfile).mockResolvedValue({
      ...mockProfile,
      first_name: "Ibrahim Jr",
    })

    renderProfileSettings()

    const editButton = await screen.findByRole("button", { name: "Edit" })
    await user.click(editButton)

    expect(screen.getByText("Edit Personal Information")).toBeInTheDocument()

    const firstNameInput = screen.getByLabelText("First Name")
    await user.clear(firstNameInput)
    await user.type(firstNameInput, "Ibrahim Jr")

    const saveButton = screen.getByRole("button", { name: "Save Changes" })
    await user.click(saveButton)

    expect(updateMyProfile).toHaveBeenCalledWith({
      first_name: "Ibrahim Jr",
    })
  })

  it("opens change password modal", async () => {
    const user = userEvent.setup()
    vi.mocked(getMyProfile).mockResolvedValue(mockProfile)

    renderProfileSettings()

    const changePasswordButton = await screen.findByRole("button", {
      name: "Change Password",
    })
    await user.click(changePasswordButton)

    expect(screen.getByRole("heading", { name: "Change Password" })).toBeInTheDocument()
  })

  it("allows clearing and typing a new snooze duration without leading zero bug, autosaved after it settles", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const user = userEvent.setup({ delay: null, advanceTimers: vi.advanceTimersByTime })
    vi.mocked(getMyProfile).mockResolvedValue(mockProfile)
    vi.mocked(updateAlarmSettings).mockResolvedValue({
      alarm_sound: "default",
      volume: 80,
      snooze_duration: 15,
      options: {
        alarm_sound_keys: ["default", "chime"],
        snooze_min_seconds: 15,
        snooze_max_seconds: 60,
        volume_min: 0,
        volume_max: 100,
      },
    })

    renderProfileSettings()

    const snoozeInput = await screen.findByLabelText("Snooze Duration (seconds)")
    expect(snoozeInput).toHaveValue(30)
    expect(await screen.findByText("All changes saved")).toBeInTheDocument()

    await user.clear(snoozeInput)
    expect(snoozeInput).toHaveValue(null)

    await user.type(snoozeInput, "15")
    expect(snoozeInput).toHaveValue(15)
    expect(screen.getByText("Unsaved changes")).toBeInTheDocument()
    expect(updateAlarmSettings).not.toHaveBeenCalled()

    // No Save button anymore — the edit autosaves once the field has sat
    // still for the debounce window.
    await vi.advanceTimersByTimeAsync(1000)

    expect(updateAlarmSettings).toHaveBeenCalledTimes(1)
    expect(updateAlarmSettings).toHaveBeenCalledWith(
      expect.objectContaining({
        snooze_duration: 15,
      }),
    )
    expect(await screen.findByText("All changes saved")).toBeInTheDocument()

    vi.useRealTimers()
  })

  it("coalesces rapid alarm-settings edits into a single autosave call", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const user = userEvent.setup({ delay: null, advanceTimers: vi.advanceTimersByTime })
    vi.mocked(getMyProfile).mockResolvedValue(mockProfile)
    vi.mocked(updateAlarmSettings).mockResolvedValue({
      alarm_sound: "default",
      volume: 80,
      snooze_duration: 45,
      options: {
        alarm_sound_keys: ["default", "chime"],
        snooze_min_seconds: 15,
        snooze_max_seconds: 60,
        volume_min: 0,
        volume_max: 100,
      },
    })

    renderProfileSettings()

    const snoozeInput = await screen.findByLabelText("Snooze Duration (seconds)")
    await user.clear(snoozeInput)

    // Simulates a user still deciding — a few quick keystrokes well inside
    // the debounce window — rather than one settled edit.
    await user.type(snoozeInput, "4")
    await vi.advanceTimersByTimeAsync(300)
    await user.type(snoozeInput, "5")

    await vi.advanceTimersByTimeAsync(1000)

    expect(updateAlarmSettings).toHaveBeenCalledTimes(1)
    expect(updateAlarmSettings).toHaveBeenCalledWith(
      expect.objectContaining({ snooze_duration: 45 }),
    )

    vi.useRealTimers()
  })

  it("blocks an out-of-range snooze duration without a Retry action, since retrying can't fix an invalid value", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const user = userEvent.setup({ delay: null, advanceTimers: vi.advanceTimersByTime })
    vi.mocked(getMyProfile).mockResolvedValue(mockProfile)

    renderProfileSettings()

    const snoozeInput = await screen.findByLabelText("Snooze Duration (seconds)")
    await user.clear(snoozeInput)
    await user.type(snoozeInput, "5")

    await vi.advanceTimersByTimeAsync(1000)

    expect(await screen.findByText("Fix errors to save")).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "Retry" })).not.toBeInTheDocument()
    expect(updateAlarmSettings).not.toHaveBeenCalled()

    vi.useRealTimers()
  })
})
