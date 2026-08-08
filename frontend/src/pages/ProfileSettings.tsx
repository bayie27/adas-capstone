import { useMemo, useState, type FormEvent } from "react"
import { useNavigate } from "react-router-dom"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import type { NoticeState } from "@/components/ui/NoticeBanner"
import { getMyProfile, updateMyProfile } from "@/services/users"
import { useAuthStore } from "@/store/useAuthStore"
import { getApiErrorMessage } from "@/utils/api"
import { formatUserRole, getUserFullName, getUserInitials } from "@/utils/users"
import { ChangePasswordModal } from "@/pages/profile/ChangePasswordModal"

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
  const token = useAuthStore((state) => state.token)
  const role = useAuthStore((state) => state.role)
  const username = useAuthStore((state) => state.username)
  const userId = useAuthStore((state) => state.userId)
  const setSession = useAuthStore((state) => state.setSession)
  const clearSession = useAuthStore((state) => state.clearSession)
  const [profileForm, setProfileForm] = useState<ProfileFormState>(EMPTY_PROFILE_FORM)
  const [profileNotice, setProfileNotice] = useState<NoticeState | null>(null)
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
        clearSession()
        navigate("/login", {
          replace: true,
          state: {
            message: "Username updated. Please sign in again with your new username.",
          },
        })
        return
      }

      if (token && role) {
        setSession(token, role, updatedProfile.username, userId ?? updatedProfile.user_id)
      }

      setProfileNotice({ tone: "success", message: "Profile updated successfully." })
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

  const displayRole = profile ? formatUserRole(profile.role) : (role ?? "Unknown Role")
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

    setProfileNotice(null)

    const nextFirstName = profileForm.first_name.trim()
    const nextLastName = profileForm.last_name.trim()
    const nextUsername = profileForm.username.trim()

    if (!nextFirstName || !nextLastName || !nextUsername) {
      setProfileNotice({
        tone: "error",
        message: "First name, last name, and username are required.",
      })
      return
    }

    const payload: ProfileFormState = {
      first_name: nextFirstName,
      last_name: nextLastName,
      username: nextUsername,
    }

    if (
      payload.first_name === profile.first_name &&
      payload.last_name === profile.last_name &&
      payload.username === profile.username
    ) {
      setProfileNotice({ tone: "error", message: "No profile changes to save." })
      return
    }

    updateProfileMutation.mutate(payload)
  }

  return (
    <div className="mx-auto max-w-3xl p-8">
      <div className="mb-8">
        <h1 className="mb-1 text-2xl font-semibold text-white">My Profile</h1>
        <p className="text-sm text-[#A1A1AA]">Manage your personal information and preferences.</p>
      </div>

      <div className="rounded-xl border border-[#2A2A2A] bg-[#111111] p-8">
        {profileQuery.isLoading ? (
          <div className="py-16 text-center text-sm text-[#A1A1AA]">Loading profile...</div>
        ) : profileQuery.isError ? (
          <div className="space-y-4 py-12 text-center">
            <p className="text-sm text-[#F87171]">
              {getApiErrorMessage(profileQuery.error, "Unable to load your profile.")}
            </p>
            <button
              type="button"
              onClick={() => profileQuery.refetch()}
              className="rounded-md border border-[#333] px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-[#1A1A1A]"
            >
              Retry
            </button>
          </div>
        ) : (
          <>
            <div className="mb-8 flex items-center gap-6">
              <div className="flex h-24 w-24 items-center justify-center rounded-full border border-[#27272A] bg-[#18181B] text-3xl font-bold text-white">
                {initials}
              </div>
              <div>
                <h2 className="text-xl font-semibold text-white">
                  {displayName || "Unnamed User"}
                </h2>
                <p className="text-[#A1A1AA]">
                  {profileForm.username || "username"} ({displayRole})
                </p>
              </div>
            </div>

            <form onSubmit={handleProfileSubmit} className="max-w-sm space-y-6">
              <div>
                <label className="mb-1.5 block text-sm font-medium text-[#E4E4E7]">
                  First Name
                </label>
                <input
                  type="text"
                  value={profileForm.first_name}
                  onChange={(event) => {
                    setProfileNotice(null)
                    setProfileForm((current) => ({ ...current, first_name: event.target.value }))
                  }}
                  className="w-full rounded-md border border-[#333] bg-[#141414] px-3 py-2 text-sm text-white focus:border-[#555] focus:outline-none"
                />
              </div>
              <div>
                <label className="mb-1.5 block text-sm font-medium text-[#E4E4E7]">Last Name</label>
                <input
                  type="text"
                  value={profileForm.last_name}
                  onChange={(event) => {
                    setProfileNotice(null)
                    setProfileForm((current) => ({ ...current, last_name: event.target.value }))
                  }}
                  className="w-full rounded-md border border-[#333] bg-[#141414] px-3 py-2 text-sm text-white focus:border-[#555] focus:outline-none"
                />
              </div>
              <div>
                <label className="mb-1.5 block text-sm font-medium text-[#E4E4E7]">Username</label>
                <input
                  type="text"
                  value={profileForm.username}
                  onChange={(event) => {
                    setProfileNotice(null)
                    setProfileForm((current) => ({ ...current, username: event.target.value }))
                  }}
                  className="w-full rounded-md border border-[#333] bg-[#141414] px-3 py-2 text-sm text-white focus:border-[#555] focus:outline-none"
                />
              </div>

              {profileNotice ? (
                <p
                  className={`text-xs ${
                    profileNotice.tone === "success" ? "text-emerald-400" : "text-[#F87171]"
                  }`}
                >
                  {profileNotice.message}
                </p>
              ) : null}

              {updateProfileMutation.isError ? (
                <p className="text-xs text-[#F87171]">
                  {getApiErrorMessage(
                    updateProfileMutation.error,
                    "Unable to update your profile.",
                  )}
                </p>
              ) : null}

              <div className="flex flex-wrap gap-3">
                <button
                  type="submit"
                  disabled={!isProfileDirty || updateProfileMutation.isPending}
                  className="rounded-md bg-white px-4 py-2 text-sm font-medium text-black transition-colors hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {updateProfileMutation.isPending ? "Saving..." : "Save Profile"}
                </button>
                <button
                  type="button"
                  onClick={() => setModal({ kind: "password" })}
                  className="rounded-md border border-[#333] px-4 py-2 text-sm font-medium text-[#E4E4E7] transition-colors hover:bg-[#1A1A1A] hover:text-white"
                >
                  Change Password
                </button>
              </div>
            </form>
          </>
        )}
      </div>

      {modal.kind === "password" && (
        <ChangePasswordModal
          onClose={() => setModal({ kind: "closed" })}
          onSuccess={() => {
            setProfileNotice({ tone: "success", message: "Password updated successfully." })
            setModal({ kind: "closed" })
          }}
        />
      )}
    </div>
  )
}
