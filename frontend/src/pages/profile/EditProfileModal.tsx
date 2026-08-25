import { useState, type FormEvent } from "react"
import { useNavigate } from "react-router-dom"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { RiUser3Line } from "@remixicon/react"

import { Modal } from "@/components/ui/Modal"
import { Input } from "@/components/ui/Input"
import { Button } from "@/components/ui/Button"
import { updateMyProfile, type UpdateMyProfileInput, type UserRecord } from "@/api/users"
import { useAuthStore } from "@/store/useAuthStore"
import { getApiErrorMessage } from "@/api/client"
import { toast } from "@/store/useToastStore"

interface EditProfileModalProps {
  profile: UserRecord
  onClose: () => void
}

const PROFILE_QUERY_KEY = ["my-profile"] as const

export function EditProfileModal({ profile, onClose }: EditProfileModalProps) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const currentUsername = useAuthStore((state) => state.username)
  const currentRole = useAuthStore((state) => state.role)
  const currentUserId = useAuthStore((state) => state.userId)
  const setSession = useAuthStore((state) => state.setSession)
  const clearSession = useAuthStore((state) => state.clearSession)

  const [firstName, setFirstName] = useState(profile.first_name)
  const [lastName, setLastName] = useState(profile.last_name)
  const [username, setUsername] = useState(profile.username)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  const updateMutation = useMutation({
    mutationFn: (payload: UpdateMyProfileInput) => updateMyProfile(payload),
    onSuccess: (updatedProfile) => {
      queryClient.setQueryData(PROFILE_QUERY_KEY, updatedProfile)
      queryClient.invalidateQueries({ queryKey: PROFILE_QUERY_KEY })

      const usernameChanged =
        currentUsername !== null && updatedProfile.username !== currentUsername

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

      if (currentRole) {
        setSession(currentRole, updatedProfile.username, currentUserId ?? updatedProfile.user_id)
      }

      toast.success("Profile updated successfully.")
      onClose()
    },
    onError: (error) => {
      const message = getApiErrorMessage(error, "Unable to update your profile.")
      setErrorMessage(message)
      toast.error(message)
    },
  })

  const isDirty =
    firstName.trim() !== profile.first_name ||
    lastName.trim() !== profile.last_name ||
    username.trim() !== profile.username

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setErrorMessage(null)

    const nextFirstName = firstName.trim()
    const nextLastName = lastName.trim()
    const nextUsername = username.trim()

    if (!nextFirstName || !nextLastName || !nextUsername) {
      setErrorMessage("First name, last name, and username are required.")
      return
    }

    const payload: UpdateMyProfileInput = {}
    if (nextFirstName !== profile.first_name) payload.first_name = nextFirstName
    if (nextLastName !== profile.last_name) payload.last_name = nextLastName
    if (nextUsername !== profile.username) payload.username = nextUsername

    if (Object.keys(payload).length === 0) {
      onClose()
      return
    }

    updateMutation.mutate(payload)
  }

  return (
    <Modal
      isOpen
      onClose={onClose}
      title="Edit Personal Information"
      subtitle="Update your personal account details."
      icon={
        <div className="flex h-[64px] w-[64px] shrink-0 items-center justify-center rounded-full border border-stroke">
          <RiUser3Line size={28} className="text-fg" />
        </div>
      }
    >
      <form onSubmit={handleSubmit} className="flex flex-col">
        <hr className="mb-6 -mx-6 border-t border-stroke" />

        <div className="space-y-4">
          <Input
            label="First Name"
            type="text"
            value={firstName}
            onChange={(event) => {
              setErrorMessage(null)
              setFirstName(event.target.value)
            }}
          />

          <Input
            label="Last Name"
            type="text"
            value={lastName}
            onChange={(event) => {
              setErrorMessage(null)
              setLastName(event.target.value)
            }}
          />

          <Input
            label="Username"
            type="text"
            value={username}
            onChange={(event) => {
              setErrorMessage(null)
              setUsername(event.target.value)
            }}
          />
        </div>

        {errorMessage ? <p className="mt-4 text-xs text-danger">{errorMessage}</p> : null}

        <hr className="my-6 -mx-6 border-t border-stroke" />

        <div className="flex justify-end gap-2">
          <Button
            variant="outline"
            className="border-stroke-strong"
            onClick={onClose}
            disabled={updateMutation.isPending}
          >
            Cancel
          </Button>
          <Button
            type="submit"
            variant="primary"
            disabled={!isDirty}
            isLoading={updateMutation.isPending}
            loadingLabel="Saving..."
          >
            Save Changes
          </Button>
        </div>
      </form>
    </Modal>
  )
}
