import { useMemo, useState, type FormEvent } from "react"
import { useNavigate } from "react-router-dom"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Button } from "@/components/ui/Button"
import { Card } from "@/components/ui/Card"
import { Input } from "@/components/ui/Input"
import { QueryErrorBanner } from "@/components/ui/QueryErrorBanner"
import { getMyProfile, updateMyProfile, type UpdateMyProfileInput } from "@/api/users"
import { useAuthStore } from "@/store/useAuthStore"
import { getApiErrorMessage } from "@/api/client"
import { formatUserRole, getUserFullName, getUserInitials } from "@/utils/format"
import { ChangePasswordModal } from "@/pages/profile/ChangePasswordModal"
import { AlarmSettingsCard } from "@/pages/profile/AlarmSettingsCard"
import { toast } from "@/store/useToastStore"

const PROFILE_QUERY_KEY = ["my-profile"] as const

type ProfileFormState = {
  first_name: string
  last_name: string
  username: string
}

type ModalState = { kind: "closed" } | { kind: "password" }

const EMPTY_PROFILE_FORM: ProfileFormState = {
  first_name: "",
  last_name: "",
  username: "",
}

export default function ProfileSettings() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const role = useAuthStore((state) => state.role)
  const username = useAuthStore((state) => state.username)
  const userId = useAuthStore((state) => state.userId)
  const setSession = useAuthStore((state) => state.setSession)
  const clearSession = useAuthStore((state) => state.clearSession)
  const [profileForm, setProfileForm] = useState<ProfileFormState>(EMPTY_PROFILE_FORM)
  const [modal, setModal] = useState<ModalState>({ kind: "closed" })
  const [hasHydratedProfileForm, setHasHydratedProfileForm] = useState(false)

  const profileQuery = useQuery({
    queryKey: PROFILE_QUERY_KEY,
    queryFn: getMyProfile,
  })

  // Seed the editable form once the profile loads. Adjusting state during
  // render (instead of an effect) makes this fire exactly once, the moment
  // profileQuery.data first becomes available — later background refetches
  // (e.g. window refocus) won't stomp on in-progress edits.
  if (profileQuery.data && !hasHydratedProfileForm) {
    setHasHydratedProfileForm(true)
    setProfileForm({
      first_name: profileQuery.data.first_name,
      last_name: profileQuery.data.last_name,
      username: profileQuery.data.username,
    })
  }

  const updateProfileMutation = useMutation({
    mutationFn: updateMyProfile,
    onSuccess: (updatedProfile) => {
      queryClient.setQueryData(PROFILE_QUERY_KEY, updatedProfile)
      queryClient.invalidateQueries({ queryKey: PROFILE_QUERY_KEY })

      const usernameChanged = username !== null && updatedProfile.username !== username

      if (usernameChanged) {
        toast.info("Username updated. Please sign in again.")
        clearSession()
        navigate("/login", {
          replace: true,
          state: {
            message: "Username updated. Please sign in again with your new username.",
          },
        })
        return
      }

      if (role) {
        setSession(role, updatedProfile.username, userId ?? updatedProfile.user_id)
      }

      toast.success("Profile updated successfully.")
    },
    onError: (error) => {
      toast.error(getApiErrorMessage(error, "Unable to update your profile."))
    },
  })

  const profile = profileQuery.data

  const displayName = useMemo(() => {
    if (profile) {
      return getUserFullName(profile)
    }

    return getUserFullName({
      first_name: profileForm.first_name,
      last_name: profileForm.last_name,
    })
  }, [profile, profileForm.first_name, profileForm.last_name])

  const displayRole = formatUserRole(profile?.role ?? role)
  const initials = getUserInitials(
    profileForm.first_name,
    profileForm.last_name,
    profileForm.username,
  )

  const isProfileDirty = profile
    ? profileForm.first_name.trim() !== profile.first_name ||
      profileForm.last_name.trim() !== profile.last_name ||
      profileForm.username.trim() !== profile.username
    : false

  const handleProfileSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()

    if (!profile) {
      return
    }

    const nextFirstName = profileForm.first_name.trim()
    const nextLastName = profileForm.last_name.trim()
    const nextUsername = profileForm.username.trim()

    if (!nextFirstName || !nextLastName || !nextUsername) {
      toast.error("First name, last name, and username are required.")
      return
    }

    const payload: UpdateMyProfileInput = {}
    if (nextFirstName !== profile.first_name) payload.first_name = nextFirstName
    if (nextLastName !== profile.last_name) payload.last_name = nextLastName
    if (nextUsername !== profile.username) payload.username = nextUsername

    if (Object.keys(payload).length === 0) {
      toast.info("No profile changes to save.")
      return
    }

    updateProfileMutation.mutate(payload)
  }

  return (
    <div className="mx-auto max-w-3xl p-8">
      <div className="mb-8">
        <h1 className="mb-0.5 text-xl font-semibold text-fg">My Profile</h1>
        <p className="text-secondary text-fg-muted">
          Manage your personal information and preferences.
        </p>
      </div>

      <Card className="p-8">
        {profileQuery.isLoading ? (
          <div className="py-16 text-center text-secondary text-fg-muted">Loading profile...</div>
        ) : profileQuery.isError ? (
          <QueryErrorBanner
            error={profileQuery.error}
            fallback="Unable to load your profile."
            onRetry={() => profileQuery.refetch()}
          />
        ) : (
          <>
            <div className="mb-8 flex items-center gap-6">
              <div className="flex h-24 w-24 items-center justify-center rounded-full border border-stroke-strong bg-surface-2 text-h2 font-bold text-fg">
                {initials}
              </div>
              <div>
                <h2 className="text-h3 font-semibold text-fg">{displayName || "Unnamed User"}</h2>
                <p className="text-body text-fg-muted">
                  {profileForm.username || "username"} ({displayRole})
                </p>
              </div>
            </div>

            <form onSubmit={handleProfileSubmit} className="max-w-sm space-y-6">
              <Input
                label="First Name"
                type="text"
                value={profileForm.first_name}
                onChange={(event) => {
                  setProfileForm((current) => ({ ...current, first_name: event.target.value }))
                }}
              />
              <Input
                label="Last Name"
                type="text"
                value={profileForm.last_name}
                onChange={(event) => {
                  setProfileForm((current) => ({ ...current, last_name: event.target.value }))
                }}
              />
              <Input
                label="Username"
                type="text"
                value={profileForm.username}
                onChange={(event) => {
                  setProfileForm((current) => ({ ...current, username: event.target.value }))
                }}
              />

              <div className="flex flex-wrap gap-3">
                <Button
                  type="submit"
                  disabled={!isProfileDirty}
                  isLoading={updateProfileMutation.isPending}
                  loadingLabel="Saving..."
                >
                  Save Profile
                </Button>
                <Button variant="outline" onClick={() => setModal({ kind: "password" })}>
                  Change Password
                </Button>
              </div>
            </form>
          </>
        )}
      </Card>

      <div className="mt-8">
        <AlarmSettingsCard />
      </div>

      {modal.kind === "password" && (
        <ChangePasswordModal
          onClose={() => setModal({ kind: "closed" })}
          onSuccess={() => {
            toast.success("Password updated successfully.")
            setModal({ kind: "closed" })
          }}
        />
      )}
    </div>
  )
}
