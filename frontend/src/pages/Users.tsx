import { useState, type FormEvent } from "react"
import { useNavigate } from "react-router-dom"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import SearchLineIcon from "remixicon-react/SearchLineIcon"
import AddLineIcon from "remixicon-react/AddLineIcon"
import PencilLineIcon from "remixicon-react/PencilLineIcon"
import Key2LineIcon from "remixicon-react/Key2LineIcon"
import DeleteBinLineIcon from "remixicon-react/DeleteBinLineIcon"
import UserAddLineIcon from "remixicon-react/UserAddLineIcon"
import LockLineIcon from "remixicon-react/LockLineIcon"
import AlertLineIcon from "remixicon-react/AlertLineIcon"
import EyeOffLineIcon from "remixicon-react/EyeOffLineIcon"
import EyeLineIcon from "remixicon-react/EyeLineIcon"
import ArrowLeftSLineIcon from "remixicon-react/ArrowLeftSLineIcon"
import ArrowRightSLineIcon from "remixicon-react/ArrowRightSLineIcon"
import { Modal } from "@/components/ui/Modal"
import { useDebouncedValue } from "@/hooks/useDebouncedValue"
import { usePagination } from "@/hooks/usePagination"
import {
  createUser,
  deleteUser,
  getUsers,
  resetUserPassword,
  updateUser,
} from "@/services/users"
import { useAuthStore } from "@/store/useAuthStore"
import type { ApiUserRole } from "@/types/auth"
import type { CreateUserInput, UpdateUserInput, UserRecord } from "@/types/users"
import { getDefaultRouteForRole, mapApiRoleToAppRole } from "@/utils/auth"
import { getApiErrorMessage } from "@/utils/api"
import {
  formatRelativeDateTime,
  formatShortDateTime,
  formatUserRole,
  getUserFullName,
} from "@/utils/users"

const USERS_QUERY_KEY = ["users"] as const
const USERS_PAGE_SIZE = 10

type NoticeState = {
  tone: "success" | "error"
  message: string
}

type CreateUserFormState = {
  first_name: string
  last_name: string
  username: string
  role: ApiUserRole
  password: string
  confirm_password: string
}

type EditUserFormState = {
  first_name: string
  last_name: string
  username: string
  role: ApiUserRole
}

type ResetPasswordFormState = {
  new_password: string
  confirm_password: string
}

const EMPTY_CREATE_FORM: CreateUserFormState = {
  first_name: "",
  last_name: "",
  username: "",
  role: "Operator",
  password: "",
  confirm_password: "",
}

const EMPTY_EDIT_FORM: EditUserFormState = {
  first_name: "",
  last_name: "",
  username: "",
  role: "Operator",
}

const EMPTY_RESET_PASSWORD_FORM: ResetPasswordFormState = {
  new_password: "",
  confirm_password: "",
}

type PasswordInputProps = {
  label: string
  value: string
  visible: boolean
  onToggle: () => void
  onChange: (value: string) => void
}

function PasswordInput({ label, value, visible, onToggle, onChange }: PasswordInputProps) {
  return (
    <div>
      <label className="mb-2 block text-[11px] font-semibold text-[#E4E4E7]">{label}</label>
      <div className="relative">
        <input
          type={visible ? "text" : "password"}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          className="w-full rounded-md border border-[#2A2A2A] bg-[#141414] px-3 py-2 pr-10 text-sm text-white focus:border-[#555] focus:outline-none"
        />
        <button
          type="button"
          onClick={onToggle}
          className="absolute right-3 top-1/2 -translate-y-1/2 text-[#555] transition-colors hover:text-white"
        >
          {visible ? <EyeLineIcon size={14} /> : <EyeOffLineIcon size={14} />}
        </button>
      </div>
    </div>
  )
}

export default function Users() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const token = useAuthStore((state) => state.token)
  const currentRole = useAuthStore((state) => state.role)
  const currentUsername = useAuthStore((state) => state.username)
  const currentUserId = useAuthStore((state) => state.userId)
  const setSession = useAuthStore((state) => state.setSession)
  const clearSession = useAuthStore((state) => state.clearSession)
  const [searchTerm, setSearchTerm] = useState("")
  const debouncedSearchTerm = useDebouncedValue(searchTerm.trim(), 300)
  const [notice, setNotice] = useState<NoticeState | null>(null)
  const [isAddOpen, setIsAddOpen] = useState(false)
  const [isEditOpen, setIsEditOpen] = useState(false)
  const [isPasswordOpen, setIsPasswordOpen] = useState(false)
  const [isDeleteOpen, setIsDeleteOpen] = useState(false)
  const [selectedUser, setSelectedUser] = useState<UserRecord | null>(null)
  const [addForm, setAddForm] = useState<CreateUserFormState>(EMPTY_CREATE_FORM)
  const [editForm, setEditForm] = useState<EditUserFormState>(EMPTY_EDIT_FORM)
  const [resetPasswordForm, setResetPasswordForm] = useState<ResetPasswordFormState>(EMPTY_RESET_PASSWORD_FORM)
  const [addValidationError, setAddValidationError] = useState<string | null>(null)
  const [editValidationError, setEditValidationError] = useState<string | null>(null)
  const [passwordValidationError, setPasswordValidationError] = useState<string | null>(null)
  const [showAddPassword, setShowAddPassword] = useState(false)
  const [showAddConfirmPassword, setShowAddConfirmPassword] = useState(false)
  const [showResetPassword, setShowResetPassword] = useState(false)
  const [showResetConfirmPassword, setShowResetConfirmPassword] = useState(false)

  // usePagination derives `page`/`offset` from the total, but the query supplies
  // the total — so mirror it into state and sync during render (placeholderData
  // keeps it stable across refetches). This clamps the page without an effect.
  const [seenTotal, setSeenTotal] = useState(0)
  const { page, totalPages, offset, rangeStart, rangeEnd, next, prev, reset } = usePagination(
    seenTotal,
    USERS_PAGE_SIZE,
  )

  const usersQuery = useQuery({
    queryKey: [...USERS_QUERY_KEY, debouncedSearchTerm, USERS_PAGE_SIZE, offset],
    queryFn: () =>
      getUsers({
        search: debouncedSearchTerm || undefined,
        limit: USERS_PAGE_SIZE,
        offset,
      }),
    placeholderData: (previousData) => previousData,
  })

  const users = usersQuery.data?.users ?? []
  const totalUsers = usersQuery.data?.total_filtered ?? 0
  if (totalUsers !== seenTotal) {
    setSeenTotal(totalUsers)
  }
  const rangeEndValue = rangeEnd(users.length)

  const createUserMutation = useMutation({
    mutationFn: createUser,
    onSuccess: (createdUser) => {
      setNotice({
        tone: "success",
        message: `${createdUser.username} was created successfully.`,
      })
      reset()
      closeAddModal()
      queryClient.invalidateQueries({ queryKey: USERS_QUERY_KEY })
    },
  })

  const updateUserMutation = useMutation({
    mutationFn: ({ userId, input }: { userId: number; input: UpdateUserInput }) =>
      updateUser(userId, input),
    onSuccess: (updatedUser) => {
      const previousUser = selectedUser

      setNotice({
        tone: "success",
        message: `${updatedUser.username} was updated successfully.`,
      })
      closeEditModal()
      queryClient.invalidateQueries({ queryKey: USERS_QUERY_KEY })

      if (!previousUser || previousUser.username !== currentUsername) {
        return
      }

      if (!updatedUser.is_active || updatedUser.username !== previousUser.username) {
        clearSession()
        navigate("/login", {
          replace: true,
          state: {
            message: updatedUser.is_active
              ? "Your username was updated. Please sign in again."
              : "Your account was deactivated. Please contact an administrator.",
          },
        })
        return
      }

      const mappedRole = mapApiRoleToAppRole(updatedUser.role)

      if (token && mappedRole) {
        setSession(token, mappedRole, updatedUser.username, currentUserId ?? updatedUser.user_id)

        if (mappedRole !== currentRole) {
          navigate(getDefaultRouteForRole(mappedRole), { replace: true })
        }
      }
    },
  })

  const resetPasswordMutation = useMutation({
    mutationFn: ({ userId, newPassword }: { userId: number; newPassword: string }) =>
      resetUserPassword(userId, { new_password: newPassword }),
    onSuccess: () => {
      setNotice({
        tone: "success",
        message: `Password reset for ${selectedUser?.username ?? "user"} completed successfully.`,
      })
      closePasswordModal()
      queryClient.invalidateQueries({ queryKey: USERS_QUERY_KEY })
    },
  })

  const deleteUserMutation = useMutation({
    mutationFn: deleteUser,
    onSuccess: () => {
      const deletedUser = selectedUser

      setNotice({
        tone: "success",
        message: `${deletedUser?.username ?? "User"} was removed from the active user list.`,
      })

      if (users.length === 1 && page > 1) {
        prev()
      }

      closeDeleteModal()
      queryClient.invalidateQueries({ queryKey: USERS_QUERY_KEY })
    },
  })

  function closeAddModal() {
    setAddForm(EMPTY_CREATE_FORM)
    setAddValidationError(null)
    setShowAddPassword(false)
    setShowAddConfirmPassword(false)
    createUserMutation.reset()
    setIsAddOpen(false)
  }

  function closeEditModal() {
    setEditForm(EMPTY_EDIT_FORM)
    setEditValidationError(null)
    updateUserMutation.reset()
    setSelectedUser(null)
    setIsEditOpen(false)
  }

  function closePasswordModal() {
    setResetPasswordForm(EMPTY_RESET_PASSWORD_FORM)
    setPasswordValidationError(null)
    setShowResetPassword(false)
    setShowResetConfirmPassword(false)
    resetPasswordMutation.reset()
    setSelectedUser(null)
    setIsPasswordOpen(false)
  }

  function closeDeleteModal() {
    deleteUserMutation.reset()
    setSelectedUser(null)
    setIsDeleteOpen(false)
  }

  function openEdit(user: UserRecord) {
    setNotice(null)
    setSelectedUser(user)
    setEditValidationError(null)
    updateUserMutation.reset()
    setEditForm({
      first_name: user.first_name,
      last_name: user.last_name,
      username: user.username,
      role: user.role,
    })
    setIsEditOpen(true)
  }

  function openPassword(user: UserRecord) {
    setNotice(null)
    setSelectedUser(user)
    setPasswordValidationError(null)
    resetPasswordMutation.reset()
    setResetPasswordForm(EMPTY_RESET_PASSWORD_FORM)
    setShowResetPassword(false)
    setShowResetConfirmPassword(false)
    setIsPasswordOpen(true)
  }

  function openDelete(user: UserRecord) {
    setNotice(null)
    setSelectedUser(user)
    deleteUserMutation.reset()
    setIsDeleteOpen(true)
  }

  function handleCreateUser(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setAddValidationError(null)
    setNotice(null)

    const payload: CreateUserInput = {
      first_name: addForm.first_name.trim(),
      last_name: addForm.last_name.trim(),
      username: addForm.username.trim(),
      role: addForm.role,
      password: addForm.password,
    }

    if (!payload.first_name || !payload.last_name || !payload.username || !payload.password) {
      setAddValidationError("All user fields are required.")
      return
    }

    if (addForm.password !== addForm.confirm_password) {
      setAddValidationError("Password confirmation does not match.")
      return
    }

    createUserMutation.mutate(payload)
  }

  function handleEditUser(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()

    if (!selectedUser) {
      return
    }

    setEditValidationError(null)
    setNotice(null)

    const payload: EditUserFormState = {
      first_name: editForm.first_name.trim(),
      last_name: editForm.last_name.trim(),
      username: editForm.username.trim(),
      role: editForm.role,
    }

    if (!payload.first_name || !payload.last_name || !payload.username) {
      setEditValidationError("All user fields are required.")
      return
    }

    if (
      payload.first_name === selectedUser.first_name &&
      payload.last_name === selectedUser.last_name &&
      payload.username === selectedUser.username &&
      payload.role === selectedUser.role
    ) {
      setEditValidationError("No user changes to save.")
      return
    }

    updateUserMutation.mutate({
      userId: selectedUser.user_id,
      input: payload,
    })
  }

  function handleResetPassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()

    if (!selectedUser) {
      return
    }

    setPasswordValidationError(null)
    setNotice(null)

    if (!resetPasswordForm.new_password || !resetPasswordForm.confirm_password) {
      setPasswordValidationError("Both password fields are required.")
      return
    }

    if (resetPasswordForm.new_password !== resetPasswordForm.confirm_password) {
      setPasswordValidationError("Password confirmation does not match.")
      return
    }

    resetPasswordMutation.mutate({
      userId: selectedUser.user_id,
      newPassword: resetPasswordForm.new_password,
    })
  }

  const addErrorMessage =
    addValidationError ??
    (createUserMutation.isError
      ? getApiErrorMessage(createUserMutation.error, "Unable to create user.")
      : null)

  const editErrorMessage =
    editValidationError ??
    (updateUserMutation.isError
      ? getApiErrorMessage(updateUserMutation.error, "Unable to update user.")
      : null)

  const passwordErrorMessage =
    passwordValidationError ??
    (resetPasswordMutation.isError
      ? getApiErrorMessage(resetPasswordMutation.error, "Unable to reset password.")
      : null)

  const deleteErrorMessage = deleteUserMutation.isError
    ? getApiErrorMessage(deleteUserMutation.error, "Unable to delete user.")
    : null

  return (
    <div className="mx-auto max-w-[1400px] p-8">
      <div className="mb-6">
        <h1 className="mb-0.5 text-xl font-semibold text-white">User Management</h1>
        <p className="text-xs text-[#737373]">Manage user accounts & system access roles</p>
      </div>

      {notice ? (
        <div
          className={`mb-4 rounded-md border px-4 py-3 text-xs ${
            notice.tone === "success"
              ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300"
              : "border-[#F87171]/30 bg-[#F87171]/10 text-[#FCA5A5]"
          }`}
        >
          {notice.message}
        </div>
      ) : null}

      <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
        <div className="relative">
          <SearchLineIcon size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#555]" />
          <input
            type="text"
            value={searchTerm}
            onChange={(event) => {
              setNotice(null)
              reset()
              setSearchTerm(event.target.value)
            }}
            placeholder="Search..."
            className="w-64 rounded-md border border-[#2A2A2A] bg-[#141414] py-1.5 pl-8 pr-4 text-xs text-white focus:border-[#52525B] focus:outline-none"
          />
        </div>
        <button
          type="button"
          onClick={() => {
            setNotice(null)
            closeAddModal()
            setIsAddOpen(true)
          }}
          className="flex items-center gap-1.5 rounded-md bg-white px-3 py-1.5 text-xs font-semibold text-black transition-colors hover:bg-gray-100"
        >
          <AddLineIcon size={14} />
          Add User
        </button>
      </div>

      <div className="overflow-hidden rounded-xl border border-[#2A2A2A] bg-[#111111]">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-[#2A2A2A] bg-[#141414] text-[#737373]">
                <th className="px-6 py-4 text-xs font-medium">Full Name</th>
                <th className="px-6 py-4 text-xs font-medium">Username</th>
                <th className="px-6 py-4 text-xs font-medium">Role</th>
                <th className="px-6 py-4 text-xs font-medium">Last Login</th>
                <th className="px-6 py-4 text-right text-xs font-medium">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#2A2A2A]">
              {usersQuery.isLoading ? (
                <tr>
                  <td colSpan={5} className="px-6 py-8 text-center text-xs text-[#A1A1AA]">
                    Loading users...
                  </td>
                </tr>
              ) : usersQuery.isError ? (
                <tr>
                  <td colSpan={5} className="px-6 py-8 text-center text-xs text-[#F87171]">
                    {getApiErrorMessage(usersQuery.error, "Unable to load users.")}
                  </td>
                </tr>
              ) : users.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-6 py-8 text-center text-xs text-[#A1A1AA]">
                    No users found.
                  </td>
                </tr>
              ) : (
                users.map((user) => (
                  <tr key={user.user_id} className="text-[#D4D4D4] transition-colors hover:bg-[#1A1A1A]">
                    <td className="px-6 py-4 text-xs font-medium">{getUserFullName(user)}</td>
                    <td className="px-6 py-4 text-xs">{user.username}</td>
                    <td className="px-6 py-4 text-xs">{formatUserRole(user.role)}</td>
                    <td className="px-6 py-4 text-xs">{formatRelativeDateTime(user.last_login)}</td>
                    <td className="px-6 py-4">
                      <div className="flex items-center justify-end gap-1.5">
                        <button
                          type="button"
                          onClick={() => openEdit(user)}
                          className="rounded p-1.5 text-[#737373] transition-colors hover:bg-[#252525] hover:text-white"
                        >
                          <PencilLineIcon size={14} />
                        </button>
                        <button
                          type="button"
                          onClick={() => openPassword(user)}
                          className="rounded p-1.5 text-[#737373] transition-colors hover:bg-[#252525] hover:text-white"
                        >
                          <Key2LineIcon size={14} />
                        </button>
                        <button
                          type="button"
                          onClick={() => openDelete(user)}
                          className="rounded p-1.5 text-[#737373] transition-colors hover:bg-[#252525] hover:text-white"
                        >
                          <DeleteBinLineIcon size={14} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        <div className="flex items-center justify-between border-t border-[#2A2A2A] px-6 py-3 text-xs text-[#737373]">
          <span>
            {rangeStart}-{rangeEndValue} of {totalUsers}
          </span>
          <div className="flex items-center gap-2">
            <button
              type="button"
              disabled={page === 1 || usersQuery.isFetching}
              onClick={prev}
              className="flex items-center gap-1 transition-colors hover:text-white disabled:cursor-not-allowed disabled:opacity-50"
            >
              <ArrowLeftSLineIcon size={14} />
              Previous
            </button>
            <span className="rounded bg-[#1E1E1E] px-2 py-1 text-white">
              {page}/{totalPages}
            </span>
            <button
              type="button"
              disabled={page >= totalPages || usersQuery.isFetching}
              onClick={next}
              className="flex items-center gap-1 transition-colors hover:text-white disabled:cursor-not-allowed disabled:opacity-50"
            >
              Next
              <ArrowRightSLineIcon size={14} />
            </button>
          </div>
        </div>
      </div>

      <Modal
        isOpen={isAddOpen}
        onClose={closeAddModal}
        title="Add User"
        subtitle="Create a new user & assign an access role"
        icon={
          <div className="flex h-10 w-10 items-center justify-center rounded-full border border-[#333] bg-transparent">
            <UserAddLineIcon size={20} className="text-white" />
          </div>
        }
      >
        <form onSubmit={handleCreateUser} className="mt-4 flex flex-col gap-6">
          <div className="grid grid-cols-[100px_1fr] gap-4">
            <div className="pt-1 text-xs font-semibold text-[#E4E4E7]">User</div>
            <div className="space-y-4">
              <div className="mb-2">
                <label className="mb-2 block text-[11px] font-semibold text-[#E4E4E7]">Role</label>
                <div className="flex items-center gap-8">
                  <label className="flex cursor-pointer items-center gap-2 text-xs text-[#D4D4D4]">
                    <input
                      type="radio"
                      name="role"
                      className="accent-white"
                      checked={addForm.role === "Admin"}
                      onChange={() => {
                        setAddValidationError(null)
                        createUserMutation.reset()
                        setAddForm((current) => ({ ...current, role: "Admin" }))
                      }}
                    />
                    Administrator
                  </label>
                  <label className="flex cursor-pointer items-center gap-2 text-xs text-[#D4D4D4]">
                    <input
                      type="radio"
                      name="role"
                      className="accent-white"
                      checked={addForm.role === "Operator"}
                      onChange={() => {
                        setAddValidationError(null)
                        createUserMutation.reset()
                        setAddForm((current) => ({ ...current, role: "Operator" }))
                      }}
                    />
                    Operator
                  </label>
                </div>
              </div>

              <div>
                <label className="mb-2 block text-[11px] font-semibold text-[#E4E4E7]">First Name</label>
                <input
                  type="text"
                  value={addForm.first_name}
                  onChange={(event) => {
                    setAddValidationError(null)
                    createUserMutation.reset()
                    setAddForm((current) => ({ ...current, first_name: event.target.value }))
                  }}
                  className="w-full rounded-md border border-[#2A2A2A] bg-[#141414] px-3 py-2 text-sm text-white placeholder-[#555] focus:border-[#555] focus:outline-none"
                />
              </div>
              <div>
                <label className="mb-2 block text-[11px] font-semibold text-[#E4E4E7]">Last Name</label>
                <input
                  type="text"
                  value={addForm.last_name}
                  onChange={(event) => {
                    setAddValidationError(null)
                    createUserMutation.reset()
                    setAddForm((current) => ({ ...current, last_name: event.target.value }))
                  }}
                  className="w-full rounded-md border border-[#2A2A2A] bg-[#141414] px-3 py-2 text-sm text-white placeholder-[#555] focus:border-[#555] focus:outline-none"
                />
              </div>
              <div>
                <label className="mb-2 block text-[11px] font-semibold text-[#E4E4E7]">Username</label>
                <input
                  type="text"
                  value={addForm.username}
                  onChange={(event) => {
                    setAddValidationError(null)
                    createUserMutation.reset()
                    setAddForm((current) => ({ ...current, username: event.target.value }))
                  }}
                  className="w-full rounded-md border border-[#2A2A2A] bg-[#141414] px-3 py-2 text-sm text-white placeholder-[#555] focus:border-[#555] focus:outline-none"
                />
              </div>
            </div>
          </div>

          <div className="h-px w-full bg-[#2A2A2A]" />

          <div className="grid grid-cols-[100px_1fr] gap-4">
            <div className="pt-1 text-xs font-semibold text-[#E4E4E7]">Enter Password</div>
            <div className="grid grid-cols-2 gap-4">
              <PasswordInput
                label="Password"
                value={addForm.password}
                visible={showAddPassword}
                onToggle={() => setShowAddPassword((current) => !current)}
                onChange={(value) => {
                  setAddValidationError(null)
                  createUserMutation.reset()
                  setAddForm((current) => ({ ...current, password: value }))
                }}
              />
              <PasswordInput
                label="Confirm Password"
                value={addForm.confirm_password}
                visible={showAddConfirmPassword}
                onToggle={() => setShowAddConfirmPassword((current) => !current)}
                onChange={(value) => {
                  setAddValidationError(null)
                  createUserMutation.reset()
                  setAddForm((current) => ({ ...current, confirm_password: value }))
                }}
              />
              <div className="col-span-2 mt-1 text-[10px] text-[#737373]">
                Must be at least 8 characters long and contain at least 1 number.
              </div>
            </div>
          </div>

          {addErrorMessage ? <p className="text-xs text-[#F87171]">{addErrorMessage}</p> : null}

          <div className="h-px w-full bg-[#2A2A2A]" />

          <div className="flex items-center justify-end gap-3">
            <button
              type="button"
              onClick={closeAddModal}
              className="rounded-md border border-[#333] bg-transparent px-4 py-2 text-xs font-medium text-[#E4E4E7] transition-colors hover:text-white"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={createUserMutation.isPending}
              className="rounded-md bg-white px-4 py-2 text-xs font-medium text-black transition-colors hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {createUserMutation.isPending ? "Saving..." : "Save Changes"}
            </button>
          </div>
        </form>
      </Modal>

      <Modal
        isOpen={isEditOpen}
        onClose={closeEditModal}
        title="Edit User"
        subtitle="Update the user's account details and access role"
        icon={
          <div className="flex h-10 w-10 items-center justify-center rounded-full border border-[#333] bg-transparent">
            <PencilLineIcon size={20} className="text-white" />
          </div>
        }
      >
        <form onSubmit={handleEditUser} className="mt-4 flex flex-col gap-6">
          <div className="grid grid-cols-[100px_1fr] gap-4">
            <div className="pt-1 text-xs font-semibold text-[#E4E4E7]">User</div>
            <div className="space-y-4">
              <div className="mb-2">
                <label className="mb-2 block text-[11px] font-semibold text-[#E4E4E7]">Role</label>
                <div className="flex items-center gap-8">
                  <label className="flex cursor-pointer items-center gap-2 text-xs text-[#D4D4D4]">
                    <input
                      type="radio"
                      name="editRole"
                      className="accent-white"
                      checked={editForm.role === "Admin"}
                      onChange={() => {
                        setEditValidationError(null)
                        updateUserMutation.reset()
                        setEditForm((current) => ({ ...current, role: "Admin" }))
                      }}
                    />
                    Administrator
                  </label>
                  <label className="flex cursor-pointer items-center gap-2 text-xs text-[#D4D4D4]">
                    <input
                      type="radio"
                      name="editRole"
                      className="accent-white"
                      checked={editForm.role === "Operator"}
                      onChange={() => {
                        setEditValidationError(null)
                        updateUserMutation.reset()
                        setEditForm((current) => ({ ...current, role: "Operator" }))
                      }}
                    />
                    Operator
                  </label>
                </div>
              </div>

              <div>
                <label className="mb-2 block text-[11px] font-semibold text-[#E4E4E7]">First Name</label>
                <input
                  type="text"
                  value={editForm.first_name}
                  onChange={(event) => {
                    setEditValidationError(null)
                    updateUserMutation.reset()
                    setEditForm((current) => ({ ...current, first_name: event.target.value }))
                  }}
                  className="w-full rounded-md border border-[#2A2A2A] bg-[#141414] px-3 py-2 text-sm text-white focus:border-[#555] focus:outline-none"
                />
              </div>
              <div>
                <label className="mb-2 block text-[11px] font-semibold text-[#E4E4E7]">Last Name</label>
                <input
                  type="text"
                  value={editForm.last_name}
                  onChange={(event) => {
                    setEditValidationError(null)
                    updateUserMutation.reset()
                    setEditForm((current) => ({ ...current, last_name: event.target.value }))
                  }}
                  className="w-full rounded-md border border-[#2A2A2A] bg-[#141414] px-3 py-2 text-sm text-white focus:border-[#555] focus:outline-none"
                />
              </div>
              <div>
                <label className="mb-2 block text-[11px] font-semibold text-[#E4E4E7]">Username</label>
                <input
                  type="text"
                  value={editForm.username}
                  onChange={(event) => {
                    setEditValidationError(null)
                    updateUserMutation.reset()
                    setEditForm((current) => ({ ...current, username: event.target.value }))
                  }}
                  className="w-full rounded-md border border-[#2A2A2A] bg-[#141414] px-3 py-2 text-sm text-white focus:border-[#555] focus:outline-none"
                />
              </div>
            </div>
          </div>

          {editErrorMessage ? <p className="text-xs text-[#F87171]">{editErrorMessage}</p> : null}

          <div className="h-px w-full bg-[#2A2A2A]" />

          <div className="flex items-center justify-between">
            <div className="space-y-1 text-[10px] text-[#71717A]">
              <div>Date Added: {formatShortDateTime(selectedUser?.created_at ?? null)}</div>
              <div>Last Changes: {formatShortDateTime(selectedUser?.updated_at ?? null)}</div>
            </div>
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={closeEditModal}
                className="rounded-md border border-[#333] bg-transparent px-4 py-2 text-xs font-medium text-[#E4E4E7] transition-colors hover:text-white"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={updateUserMutation.isPending}
                className="rounded-md bg-white px-4 py-2 text-xs font-medium text-black transition-colors hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {updateUserMutation.isPending ? "Saving..." : "Save Changes"}
              </button>
            </div>
          </div>
        </form>
      </Modal>

      <Modal
        isOpen={isPasswordOpen}
        onClose={closePasswordModal}
        title="Change Password"
        subtitle="Update a user's password"
        icon={
          <div className="flex h-10 w-10 items-center justify-center rounded-full border border-[#333] bg-transparent">
            <LockLineIcon size={20} className="text-white" />
          </div>
        }
      >
        <form onSubmit={handleResetPassword} className="mt-4 flex flex-col gap-6">
          <div className="h-px w-full bg-[#2A2A2A]" />
          <div className="space-y-4">
            <p className="mb-4 text-xs text-[#A1A1AA]">
              Changing {selectedUser ? getUserFullName(selectedUser) : "this user's"} account password...
            </p>
            <PasswordInput
              label="New Password"
              value={resetPasswordForm.new_password}
              visible={showResetPassword}
              onToggle={() => setShowResetPassword((current) => !current)}
              onChange={(value) => {
                setPasswordValidationError(null)
                resetPasswordMutation.reset()
                setResetPasswordForm((current) => ({ ...current, new_password: value }))
              }}
            />
            <PasswordInput
              label="Confirm New Password"
              value={resetPasswordForm.confirm_password}
              visible={showResetConfirmPassword}
              onToggle={() => setShowResetConfirmPassword((current) => !current)}
              onChange={(value) => {
                setPasswordValidationError(null)
                resetPasswordMutation.reset()
                setResetPasswordForm((current) => ({ ...current, confirm_password: value }))
              }}
            />
            <div className="mt-2 mb-2 text-[10px] text-[#737373]">
              Must be at least 8 characters long and contain at least 1 number.
            </div>
          </div>

          {passwordErrorMessage ? <p className="text-xs text-[#F87171]">{passwordErrorMessage}</p> : null}

          <div className="h-px w-full bg-[#2A2A2A]" />

          <div className="flex items-center justify-between">
            <div className="text-[10px] text-[#71717A]">
              <div>Last Changes: {formatShortDateTime(selectedUser?.password_changed_at ?? null)}</div>
            </div>
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={closePasswordModal}
                className="rounded-md border border-[#333] bg-transparent px-4 py-2 text-xs font-medium text-[#E4E4E7] transition-colors hover:text-white"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={resetPasswordMutation.isPending}
                className="rounded-md bg-white px-4 py-2 text-xs font-medium text-black transition-colors hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {resetPasswordMutation.isPending ? "Saving..." : "Save Changes"}
              </button>
            </div>
          </div>
        </form>
      </Modal>

      <Modal isOpen={isDeleteOpen} onClose={closeDeleteModal} hideClose>
        <div className="flex flex-col items-center pt-6 text-center">
          <AlertLineIcon size={36} className="mb-4 text-[#ef4444]" />
          <h3 className="mb-2 text-[15px] font-bold text-white">Are you absolutely sure?</h3>
          <p className="mb-6 px-4 text-[11px] leading-relaxed text-[#A1A1AA]">
            This action will deactivate account "{selectedUser ? getUserFullName(selectedUser) : "this user"}"
            and remove it from the active user list.
          </p>
          {deleteErrorMessage ? <p className="mb-4 text-xs text-[#F87171]">{deleteErrorMessage}</p> : null}
          <div className="flex w-full items-center justify-end gap-3">
            <button
              type="button"
              onClick={closeDeleteModal}
              className="rounded-md border border-[#333] bg-transparent px-4 py-2 text-xs font-semibold text-white transition-colors hover:bg-[#1A1A1A]"
            >
              Cancel
            </button>
            <button
              type="button"
              disabled={!selectedUser || deleteUserMutation.isPending}
              onClick={() => {
                if (!selectedUser) {
                  return
                }

                setNotice(null)
                deleteUserMutation.mutate(selectedUser.user_id)
              }}
              className="rounded-md bg-white px-4 py-2 text-xs font-semibold text-black transition-colors hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {deleteUserMutation.isPending ? "Deleting..." : "Continue"}
            </button>
          </div>
        </div>
      </Modal>
    </div>
  )
}
