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

  it("allows clearing and typing a new snooze duration without leading zero bug", async () => {
    const user = userEvent.setup()
    vi.mocked(getMyProfile).mockResolvedValue(mockProfile)
    vi.mocked(updateAlarmSettings).mockResolvedValue({
      alarm_sound: "default",
      volume: 80,
      snooze_duration: 15,
      options: {
        alarm_sound_keys: ["default", "chime"],
        snooze_min_seconds: 15,
        snooze_max_seconds: 60,
      },
    })

    renderProfileSettings()

    const snoozeInput = await screen.findByLabelText("Snooze Duration (seconds)")
    expect(snoozeInput).toHaveValue(30)

    await user.clear(snoozeInput)
    expect(snoozeInput).toHaveValue(null)

    await user.type(snoozeInput, "15")
    expect(snoozeInput).toHaveValue(15)

    const saveAlarmButton = screen.getByRole("button", { name: "Save Alarm Settings" })
    await user.click(saveAlarmButton)

    expect(updateAlarmSettings).toHaveBeenCalledWith(
      expect.objectContaining({
        snooze_duration: 15,
      }),
    )
  })
})
