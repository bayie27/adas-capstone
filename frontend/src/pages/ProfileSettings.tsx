import { useEffect, useMemo, useState, type FormEvent } from "react"
import { useNavigate } from "react-router-dom"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import EyeLineIcon from "remixicon-react/EyeLineIcon"
import EyeOffLineIcon from "remixicon-react/EyeOffLineIcon"
import LockLineIcon from "remixicon-react/LockLineIcon"
import { Modal } from "@/components/ui/Modal"
import type { NoticeState } from "@/components/ui/NoticeBanner"
import {
  changeMyPassword,
  getMyProfile,
  updateMyProfile,
} from "@/services/users"
import { useAuthStore } from "@/store/useAuthStore"
import { getApiErrorMessage } from "@/utils/api"
import { formatUserRole, getUserFullName, getUserInitials } from "@/utils/users"

const PROFILE_QUERY_KEY = ["my-profile"] as const

type ProfileFormState = {
  first_name: string
  last_name: string
  username: string
}

type PasswordFormState = {
  old_password: string
  new_password: string
  confirm_password: string
}

const EMPTY_PROFILE_FORM: ProfileFormState = {
  first_name: "",
  last_name: "",
  username: "",
}

const EMPTY_PASSWORD_FORM: PasswordFormState = {
  old_password: "",
  new_password: "",
  confirm_password: "",
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
  const [passwordForm, setPasswordForm] = useState<PasswordFormState>(EMPTY_PASSWORD_FORM)
  const [profileNotice, setProfileNotice] = useState<NoticeState | null>(null)
  const [passwordNotice, setPasswordNotice] = useState<NoticeState | null>(null)
  const [isPasswordOpen, setIsPasswordOpen] = useState(false)
  const [showCurrentPassword, setShowCurrentPassword] = useState(false)
  const [showNewPassword, setShowNewPassword] = useState(false)
  const [showConfirmPassword, setShowConfirmPassword] = useState(false)

  const profileQuery = useQuery({
    queryKey: PROFILE_QUERY_KEY,
    queryFn: getMyProfile,
  })

  useEffect(() => {
    if (!profileQuery.data) {
      return
    }

    setProfileForm({
      first_name: profileQuery.data.first_name,
      last_name: profileQuery.data.last_name,
      username: profileQuery.data.username,
    })
  }, [profileQuery.data])

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

  const changePasswordMutation = useMutation({
    mutationFn: changeMyPassword,
    onSuccess: () => {
      setPasswordForm(EMPTY_PASSWORD_FORM)
      setPasswordNotice(null)
      setProfileNotice({ tone: "success", message: "Password updated successfully." })
      setShowCurrentPassword(false)
      setShowNewPassword(false)
      setShowConfirmPassword(false)
      setIsPasswordOpen(false)
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

  const displayRole = profile ? formatUserRole(profile.role) : role ?? "Unknown Role"
  const initials = getUserInitials(profileForm.first_name, profileForm.last_name, profileForm.username)

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
      setProfileNotice({ tone: "error", message: "First name, last name, and username are required." })
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

  const handlePasswordSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setPasswordNotice(null)

    if (
      !passwordForm.old_password ||
      !passwordForm.new_password ||
      !passwordForm.confirm_password
    ) {
      setPasswordNotice({ tone: "error", message: "Complete all password fields." })
      return
    }

    if (passwordForm.new_password !== passwordForm.confirm_password) {
      setPasswordNotice({ tone: "error", message: "New password and confirmation do not match." })
      return
    }

    changePasswordMutation.mutate({
      old_password: passwordForm.old_password,
      new_password: passwordForm.new_password,
    })
  }

  const closePasswordModal = () => {
    setPasswordForm(EMPTY_PASSWORD_FORM)
    setPasswordNotice(null)
    setShowCurrentPassword(false)
    setShowNewPassword(false)
    setShowConfirmPassword(false)
    setIsPasswordOpen(false)
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
                <h2 className="text-xl font-semibold text-white">{displayName || "Unnamed User"}</h2>
                <p className="text-[#A1A1AA]">
                  {profileForm.username || "username"} ({displayRole})
                </p>
              </div>
            </div>

            <form onSubmit={handleProfileSubmit} className="max-w-sm space-y-6">
              <div>
                <label className="mb-1.5 block text-sm font-medium text-[#E4E4E7]">First Name</label>
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
                  {getApiErrorMessage(updateProfileMutation.error, "Unable to update your profile.")}
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
                  onClick={() => {
                    setPasswordNotice(null)
                    setIsPasswordOpen(true)
                  }}
                  className="rounded-md border border-[#333] px-4 py-2 text-sm font-medium text-[#E4E4E7] transition-colors hover:bg-[#1A1A1A] hover:text-white"
                >
                  Change Password
                </button>
              </div>
            </form>
          </>
        )}
      </div>

      <Modal
        isOpen={isPasswordOpen}
        onClose={closePasswordModal}
        title="Change Password"
        subtitle="Update your account password."
        icon={
          <div className="flex h-10 w-10 items-center justify-center rounded-full border border-[#333] bg-transparent">
            <LockLineIcon size={20} className="text-white" />
          </div>
        }
      >
        <form onSubmit={handlePasswordSubmit} className="mt-4 flex flex-col gap-6">
          <div className="space-y-4">
            <div>
              <label className="mb-2 block text-[11px] font-semibold text-[#E4E4E7]">Current Password</label>
              <div className="relative">
                <input
                  type={showCurrentPassword ? "text" : "password"}
                  value={passwordForm.old_password}
                  onChange={(event) => {
                    setPasswordNotice(null)
                    setPasswordForm((current) => ({
                      ...current,
                      old_password: event.target.value,
                    }))
                  }}
                  className="w-full rounded-md border border-[#2A2A2A] bg-[#141414] px-3 py-2 pr-10 text-sm text-white focus:border-[#555] focus:outline-none"
                />
                <button
                  type="button"
                  onClick={() => setShowCurrentPassword((current) => !current)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-[#555] transition-colors hover:text-white"
                >
                  {showCurrentPassword ? <EyeLineIcon size={14} /> : <EyeOffLineIcon size={14} />}
                </button>
              </div>
            </div>

            <div>
              <label className="mb-2 block text-[11px] font-semibold text-[#E4E4E7]">New Password</label>
              <div className="relative">
                <input
                  type={showNewPassword ? "text" : "password"}
                  value={passwordForm.new_password}
                  onChange={(event) => {
                    setPasswordNotice(null)
                    setPasswordForm((current) => ({
                      ...current,
                      new_password: event.target.value,
                    }))
                  }}
                  className="w-full rounded-md border border-[#2A2A2A] bg-[#141414] px-3 py-2 pr-10 text-sm text-white focus:border-[#555] focus:outline-none"
                />
                <button
                  type="button"
                  onClick={() => setShowNewPassword((current) => !current)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-[#555] transition-colors hover:text-white"
                >
                  {showNewPassword ? <EyeLineIcon size={14} /> : <EyeOffLineIcon size={14} />}
                </button>
              </div>
            </div>

            <div>
              <label className="mb-2 block text-[11px] font-semibold text-[#E4E4E7]">Confirm New Password</label>
              <div className="relative">
                <input
                  type={showConfirmPassword ? "text" : "password"}
                  value={passwordForm.confirm_password}
                  onChange={(event) => {
                    setPasswordNotice(null)
                    setPasswordForm((current) => ({
                      ...current,
                      confirm_password: event.target.value,
                    }))
                  }}
                  className="w-full rounded-md border border-[#2A2A2A] bg-[#141414] px-3 py-2 pr-10 text-sm text-white focus:border-[#555] focus:outline-none"
                />
                <button
                  type="button"
                  onClick={() => setShowConfirmPassword((current) => !current)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-[#555] transition-colors hover:text-white"
                >
                  {showConfirmPassword ? <EyeLineIcon size={14} /> : <EyeOffLineIcon size={14} />}
                </button>
              </div>
            </div>

            <p className="text-[10px] text-[#737373]">
              Must be at least 8 characters long and contain at least 1 number.
            </p>
          </div>

          {passwordNotice ? (
            <p
              className={`text-xs ${
                passwordNotice.tone === "success" ? "text-emerald-400" : "text-[#F87171]"
              }`}
            >
              {passwordNotice.message}
            </p>
          ) : null}

          {changePasswordMutation.isError ? (
            <p className="text-xs text-[#F87171]">
              {getApiErrorMessage(changePasswordMutation.error, "Unable to update your password.")}
            </p>
          ) : null}

          <div className="flex items-center justify-end gap-3">
            <button
              type="button"
              onClick={closePasswordModal}
              className="rounded-md border border-[#333] bg-transparent px-4 py-2 text-xs font-medium text-[#E4E4E7] transition-colors hover:text-white"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={changePasswordMutation.isPending}
              className="rounded-md bg-white px-4 py-2 text-xs font-medium text-black transition-colors hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {changePasswordMutation.isPending ? "Saving..." : "Save Changes"}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  )
}
