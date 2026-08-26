import { useState } from "react"
import { useNavigate } from "react-router-dom"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import {
  RiAddLine,
  RiArrowGoBackLine,
  RiDeleteBinLine,
  RiKey2Line,
  RiPencilLine,
} from "@remixicon/react"
import { Badge } from "@/components/ui/Badge"
import { Button, focusRing } from "@/components/ui/Button"
import { ClearFiltersButton } from "@/components/ui/ClearFiltersButton"
import { ConfirmDeleteModal } from "@/components/ui/ConfirmDeleteModal"
import { FilterSelect } from "@/components/ui/FilterSelect"
import { PaginationFooter } from "@/components/ui/PaginationFooter"
import { SearchInput } from "@/components/ui/SearchInput"
import {
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableHeaderCell,
  TableRow,
  TableStateRow,
} from "@/components/ui/Table"
import { cn } from "@/utils/cn"
import { useDebouncedValue } from "@/hooks/useDebouncedValue"
import { usePagination } from "@/hooks/usePagination"
import { deleteUser, getUsers, restoreUser } from "@/api/users"
import { useAuthStore } from "@/store/useAuthStore"
import type { UserRecord } from "@/api/users"
import { getDefaultRouteForRole, toApiRole } from "@/utils/auth"
import { getApiErrorMessage } from "@/api/client"
import { formatRelativeDateTime } from "@/utils/datetime"
import { formatUserRole, getUserFullName } from "@/utils/format"
import { AddUserModal } from "@/pages/users/AddUserModal"
import { EditUserModal } from "@/pages/users/EditUserModal"
import { ChangePasswordModal } from "@/pages/users/ChangePasswordModal"
import { toast } from "@/store/useToastStore"

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
  const [modal, setModal] = useState<ModalState>({ kind: "closed" })
  // "active" is a sentinel for "omit the param" — GET /api/users/ already
  // defaults to active-only when is_active is absent, so this preserves
  // today's behavior exactly rather than sending an explicit "true".
  const [activeFilter, setActiveFilter] = useState<"active" | "false" | "null">("active")

  const hasFilters = searchTerm.trim() !== "" || activeFilter !== "active"

  // usePagination derives `page`/`offset` from the total, but the query supplies
  // the total — so mirror it into state and sync during render (placeholderData
  // keeps it stable across refetches). This clamps the page without an effect.
  const [seenTotal, setSeenTotal] = useState(0)
  const {
    page,
    pageSize,
    totalPages,
    offset,
    rangeStart,
    rangeEnd,
    next,
    prev,
    reset,
    goTo,
    setPageSize,
  } = usePagination(seenTotal, USERS_PAGE_SIZE)

  const usersQuery = useQuery({
    queryKey: [...USERS_QUERY_KEY, debouncedSearchTerm, activeFilter, pageSize, offset],
    queryFn: () =>
      getUsers({
        search: debouncedSearchTerm || undefined,
        is_active: activeFilter === "active" ? undefined : activeFilter,
        limit: pageSize,
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
      const message = `${deletedUser?.username ?? "User"} was removed from the active user list.`

      toast.success(message)

      if (users.length === 1 && page > 1) {
        prev()
      }

      setModal({ kind: "closed" })
      queryClient.invalidateQueries({ queryKey: USERS_QUERY_KEY })
    },
  })

  const restoreUserMutation = useMutation({
    mutationFn: (userId: number) => restoreUser(userId),
    onSuccess: (updated) => {
      const message = `${updated.username} was restored.`
      toast.success(message)
      queryClient.invalidateQueries({ queryKey: USERS_QUERY_KEY })
    },
    onError: (error) => {
      const message = getApiErrorMessage(error, "Unable to restore this user.")
      toast.error(message)
    },
  })

  return (
    <div className="mx-auto max-w-[1400px] p-8">
      <div className="mb-6">
        <h1 className="mb-0.5 text-xl font-semibold text-fg">User Management</h1>
        <p className="text-xs text-fg-muted">Manage user accounts & system access roles</p>
      </div>

      <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
        <div className="flex flex-wrap items-center gap-2.5">
          <SearchInput
            value={searchTerm}
            onChange={(value) => {
              reset()
              setSearchTerm(value)
            }}
            placeholder="Search..."
          />
          <FilterSelect
            value={activeFilter}
            options={[
              { value: "active", label: "Active only" },
              { value: "false", label: "Deactivated only" },
              { value: "null", label: "All" },
            ]}
            onChange={(value) => {
              reset()
              setActiveFilter(value)
            }}
          />
          {hasFilters ? (
            <ClearFiltersButton
              onClick={() => {
                reset()
                setSearchTerm("")
                setActiveFilter("active")
              }}
            />
          ) : null}
        </div>
        <Button
          size="sm"
          onClick={() => {
            setModal({ kind: "add" })
          }}
        >
          <RiAddLine size={14} />
          Add User
        </Button>
      </div>

      <TableContainer
        footer={
          <PaginationFooter
            page={page}
            totalPages={totalPages}
            rangeStart={rangeStart}
            rangeEnd={rangeEndValue}
            totalFiltered={totalUsers}
            pageSize={pageSize}
            isFetching={usersQuery.isFetching}
            onPrev={prev}
            onNext={next}
            onPageChange={goTo}
            onPageSizeChange={setPageSize}
          />
        }
      >
        <Table>
          <TableHead>
            <TableHeaderCell>Full Name</TableHeaderCell>
            <TableHeaderCell>Username</TableHeaderCell>
            <TableHeaderCell>Role</TableHeaderCell>
            <TableHeaderCell>Last Login</TableHeaderCell>
            <TableHeaderCell>Status</TableHeaderCell>
            <TableHeaderCell className="text-right">Actions</TableHeaderCell>
          </TableHead>
          <TableBody>
            {usersQuery.isLoading ? (
              <TableStateRow colSpan={6}>Loading users...</TableStateRow>
            ) : usersQuery.isError ? (
              <TableStateRow colSpan={6} tone="error">
                {getApiErrorMessage(usersQuery.error, "Unable to load users.")}
              </TableStateRow>
            ) : users.length === 0 ? (
              <TableStateRow colSpan={6}>No users found.</TableStateRow>
            ) : (
              users.map((user) => {
                const isRestoring =
                  restoreUserMutation.isPending && restoreUserMutation.variables === user.user_id
                const rowBusy =
                  (deleteUserMutation.isPending &&
                    modal.kind === "delete" &&
                    modal.user.user_id === user.user_id) ||
                  isRestoring
                const iconButtonClass = cn(
                  "rounded p-1.5 text-fg-muted transition-colors duration-150 hover:bg-surface-2 hover:text-fg",
                  "disabled:cursor-not-allowed disabled:opacity-60 disabled:hover:bg-transparent disabled:hover:text-fg-muted",
                  focusRing,
                )

                return (
                  <TableRow key={user.user_id} className={rowBusy ? "opacity-50" : undefined}>
                    <TableCell className="font-medium text-fg">{getUserFullName(user)}</TableCell>
                    <TableCell className="text-fg-muted">{user.username}</TableCell>
                    <TableCell className="text-fg-muted">{formatUserRole(user.role)}</TableCell>
                    <TableCell className="text-fg-muted">
                      {formatRelativeDateTime(user.last_login)}
                    </TableCell>
                    <TableCell>
                      <Badge tone={user.is_active ? "success" : "danger"} variant="subtle">
                        {user.is_active ? "Active" : "Deactivated"}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right">
                      {user.is_active ? (
                        <div className="flex items-center justify-end gap-1.5">
                          <button
                            type="button"
                            disabled={rowBusy}
                            aria-label={`Edit ${getUserFullName(user)}`}
                            onClick={() => {
                              setModal({ kind: "edit", user })
                            }}
                            className={iconButtonClass}
                          >
                            <RiPencilLine size={14} />
                          </button>
                          <button
                            type="button"
                            disabled={rowBusy}
                            aria-label={`Reset password for ${getUserFullName(user)}`}
                            onClick={() => {
                              setModal({ kind: "password", user })
                            }}
                            className={iconButtonClass}
                          >
                            <RiKey2Line size={14} />
                          </button>
                          <button
                            type="button"
                            disabled={rowBusy}
                            aria-label={`Delete ${getUserFullName(user)}`}
                            onClick={() => {
                              setModal({ kind: "delete", user })
                            }}
                            className={cn(iconButtonClass, "hover:text-danger")}
                          >
                            <RiDeleteBinLine size={14} />
                          </button>
                        </div>
                      ) : (
                        <div className="flex items-center justify-end">
                          <button
                            type="button"
                            aria-label={`Restore ${getUserFullName(user)}`}
                            disabled={isRestoring || rowBusy}
                            onClick={() => {
                              restoreUserMutation.mutate(user.user_id)
                            }}
                            className={cn(
                              "flex items-center gap-1.5 rounded-sm text-xs text-fg-muted transition-colors duration-150 hover:text-fg",
                              "disabled:cursor-not-allowed disabled:opacity-60 disabled:hover:text-fg-muted",
                              focusRing,
                            )}
                          >
                            <RiArrowGoBackLine size={14} />
                            {isRestoring ? "Restoring…" : "Restore"}
                          </button>
                        </div>
                      )}
                    </TableCell>
                  </TableRow>
                )
              })
            )}
          </TableBody>
        </Table>
      </TableContainer>

      {modal.kind === "add" && (
        <AddUserModal
          onClose={() => setModal({ kind: "closed" })}
          onSuccess={(user) => {
            const message = `${user.username} was created successfully.`
            toast.success(message)
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
            const message = `${updatedUser.username} was updated successfully.`
            toast.success(message)
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

            const mappedRole = toApiRole(updatedUser.role)

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
        <ChangePasswordModal
          user={modal.user}
          onClose={() => setModal({ kind: "closed" })}
          onSuccess={() => {
            const message = `Password reset for ${modal.user.username} completed successfully.`
            toast.success(message)
            setModal({ kind: "closed" })
            queryClient.invalidateQueries({ queryKey: USERS_QUERY_KEY })
          }}
        />
      )}

      <ConfirmDeleteModal
        isOpen={modal.kind === "delete"}
        title="Are you absolutely sure?"
        description={
          modal.kind === "delete" ? (
            <>
              This action will deactivate account{" "}
              <span className="italic">"{getUserFullName(modal.user)}"</span> and remove it from the
              active user list.
            </>
          ) : (
            ""
          )
        }
        confirmText="Yes, deactivate user"
        isPending={deleteUserMutation.isPending}
        error={deleteUserMutation.error}
        onClose={() => setModal({ kind: "closed" })}
        onConfirm={() => {
          if (modal.kind === "delete") {
            deleteUserMutation.mutate(modal.user.user_id)
          }
        }}
      />
    </div>
  )
}
