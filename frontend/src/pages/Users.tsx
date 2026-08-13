import { useState } from "react"
import { useNavigate } from "react-router-dom"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { RiAddLine, RiPencilLine, RiKey2Line, RiDeleteBinLine } from "@remixicon/react"
import { ConfirmDeleteModal } from "@/components/ui/ConfirmDeleteModal"
import { NoticeBanner, type NoticeState } from "@/components/ui/NoticeBanner"
import { PaginationFooter } from "@/components/ui/PaginationFooter"
import { SearchInput } from "@/components/ui/SearchInput"
import { TableStateRow } from "@/components/ui/TableStateRow"
import { useDebouncedValue } from "@/hooks/useDebouncedValue"
import { usePagination } from "@/hooks/usePagination"
import { deleteUser, getUsers } from "@/api/users"
import { useAuthStore } from "@/store/useAuthStore"
import type { UserRecord } from "@/api/users"
import { getDefaultRouteForRole, mapApiRoleToAppRole } from "@/utils/auth"
import { getApiErrorMessage } from "@/api/client"
import { formatRelativeDateTime } from "@/utils/datetime"
import { formatUserRole, getUserFullName } from "@/utils/users"
import { AddUserModal } from "@/pages/users/AddUserModal"
import { EditUserModal } from "@/pages/users/EditUserModal"
import { ResetPasswordModal } from "@/pages/users/ResetPasswordModal"

const USERS_QUERY_KEY = ["users"] as const
const USERS_PAGE_SIZE = 10

type ModalState =
  | { kind: "closed" }
  | { kind: "add" }
  | { kind: "edit"; user: UserRecord }
  | { kind: "password"; user: UserRecord }
  | { kind: "delete"; user: UserRecord }

export default function Users() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const currentRole = useAuthStore((state) => state.role)
  const currentUsername = useAuthStore((state) => state.username)
  const currentUserId = useAuthStore((state) => state.userId)
  const setSession = useAuthStore((state) => state.setSession)
  const clearSession = useAuthStore((state) => state.clearSession)

  const [searchTerm, setSearchTerm] = useState("")
  const debouncedSearchTerm = useDebouncedValue(searchTerm.trim(), 300)
  const [notice, setNotice] = useState<NoticeState | null>(null)
  const [modal, setModal] = useState<ModalState>({ kind: "closed" })

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

  const deleteUserMutation = useMutation({
    mutationFn: deleteUser,
    onSuccess: () => {
      const deletedUser = modal.kind === "delete" ? modal.user : null

      setNotice({
        tone: "success",
        message: `${deletedUser?.username ?? "User"} was removed from the active user list.`,
      })

      if (users.length === 1 && page > 1) {
        prev()
      }

      setModal({ kind: "closed" })
      queryClient.invalidateQueries({ queryKey: USERS_QUERY_KEY })
    },
  })

  return (
    <div className="mx-auto max-w-[1400px] p-8">
      <div className="mb-6">
        <h1 className="mb-0.5 text-xl font-semibold text-fg">User Management</h1>
        <p className="text-xs text-fg-muted">Manage user accounts & system access roles</p>
      </div>

      {notice ? <NoticeBanner notice={notice} /> : null}

      <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
        <SearchInput
          value={searchTerm}
          onChange={(value) => {
            setNotice(null)
            reset()
            setSearchTerm(value)
          }}
          placeholder="Search..."
        />
        <button
          type="button"
          onClick={() => {
            setNotice(null)
            setModal({ kind: "add" })
          }}
          className="flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-xs font-semibold text-fg-on-primary transition-colors hover:bg-primary-hover"
        >
          <RiAddLine size={14} />
          Add User
        </button>
      </div>

      <div className="overflow-hidden rounded-xl border border-stroke bg-surface-1">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-stroke bg-surface-1 text-fg-muted">
                <th className="px-6 py-4 text-xs font-medium">Full Name</th>
                <th className="px-6 py-4 text-xs font-medium">Username</th>
                <th className="px-6 py-4 text-xs font-medium">Role</th>
                <th className="px-6 py-4 text-xs font-medium">Last Login</th>
                <th className="px-6 py-4 text-right text-xs font-medium">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-stroke">
              {usersQuery.isLoading ? (
                <TableStateRow colSpan={5}>Loading users...</TableStateRow>
              ) : usersQuery.isError ? (
                <TableStateRow colSpan={5} tone="error">
                  {getApiErrorMessage(usersQuery.error, "Unable to load users.")}
                </TableStateRow>
              ) : users.length === 0 ? (
                <TableStateRow colSpan={5}>No users found.</TableStateRow>
              ) : (
                users.map((user) => (
                  <tr
                    key={user.user_id}
                    className="text-fg-body transition-colors hover:bg-surface-1"
                  >
                    <td className="px-6 py-4 text-xs font-medium">{getUserFullName(user)}</td>
                    <td className="px-6 py-4 text-xs">{user.username}</td>
                    <td className="px-6 py-4 text-xs">{formatUserRole(user.role)}</td>
                    <td className="px-6 py-4 text-xs">{formatRelativeDateTime(user.last_login)}</td>
                    <td className="px-6 py-4">
                      <div className="flex items-center justify-end gap-1.5">
                        <button
                          type="button"
                          onClick={() => {
                            setNotice(null)
                            setModal({ kind: "edit", user })
                          }}
                          className="rounded p-1.5 text-fg-muted transition-colors hover:bg-surface-2 hover:text-fg"
                        >
                          <RiPencilLine size={14} />
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            setNotice(null)
                            setModal({ kind: "password", user })
                          }}
                          className="rounded p-1.5 text-fg-muted transition-colors hover:bg-surface-2 hover:text-fg"
                        >
                          <RiKey2Line size={14} />
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            setNotice(null)
                            setModal({ kind: "delete", user })
                          }}
                          className="rounded p-1.5 text-fg-muted transition-colors hover:bg-surface-2 hover:text-fg"
                        >
                          <RiDeleteBinLine size={14} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        <PaginationFooter
          page={page}
          totalPages={totalPages}
          rangeStart={rangeStart}
          rangeEnd={rangeEndValue}
          totalFiltered={totalUsers}
          pageSize={USERS_PAGE_SIZE}
          isFetching={usersQuery.isFetching}
          onPrev={prev}
          onNext={next}
        />
      </div>

      {modal.kind === "add" && (
        <AddUserModal
          onClose={() => setModal({ kind: "closed" })}
          onSuccess={(user) => {
            setNotice({
              tone: "success",
              message: `${user.username} was created successfully.`,
            })
            reset()
            setModal({ kind: "closed" })
            queryClient.invalidateQueries({ queryKey: USERS_QUERY_KEY })
          }}
        />
      )}

      {modal.kind === "edit" && (
        <EditUserModal
          user={modal.user}
          onClose={() => setModal({ kind: "closed" })}
          onSuccess={(updatedUser) => {
            setNotice({
              tone: "success",
              message: `${updatedUser.username} was updated successfully.`,
            })
            setModal({ kind: "closed" })
            queryClient.invalidateQueries({ queryKey: USERS_QUERY_KEY })

            if (updatedUser.username !== currentUsername) {
              return
            }

            if (!updatedUser.is_active || updatedUser.username !== modal.user.username) {
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

            if (mappedRole) {
              setSession(mappedRole, updatedUser.username, currentUserId ?? updatedUser.user_id)

              if (mappedRole !== currentRole) {
                navigate(getDefaultRouteForRole(mappedRole), { replace: true })
              }
            }
          }}
        />
      )}

      {modal.kind === "password" && (
        <ResetPasswordModal
          user={modal.user}
          onClose={() => setModal({ kind: "closed" })}
          onSuccess={() => {
            setNotice({
              tone: "success",
              message: `Password reset for ${modal.user.username} completed successfully.`,
            })
            setModal({ kind: "closed" })
            queryClient.invalidateQueries({ queryKey: USERS_QUERY_KEY })
          }}
        />
      )}

      <ConfirmDeleteModal
        isOpen={modal.kind === "delete"}
        title="Are you absolutely sure?"
        description={
          modal.kind === "delete"
            ? `This action will deactivate account "${getUserFullName(modal.user)}" and remove it from the active user list.`
            : ""
        }
        isPending={deleteUserMutation.isPending}
        error={deleteUserMutation.error}
        onClose={() => setModal({ kind: "closed" })}
        onConfirm={() => {
          if (modal.kind === "delete") {
            setNotice(null)
            deleteUserMutation.mutate(modal.user.user_id)
          }
        }}
      />
    </div>
  )
}
