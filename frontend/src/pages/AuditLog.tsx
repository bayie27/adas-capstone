import { useMemo, useState } from "react"
import { useMutation, useQuery } from "@tanstack/react-query"
import { RiArrowDownSLine, RiArrowRightSLine, RiFileCopyLine } from "@remixicon/react"

import {
  filterActiveEntries,
  formatChangedFields,
  formatCheckLabel,
  formatScalarDetailValue,
  formatTargetDisplayName,
  formatTargetType,
  hasResolvedName,
  humanizeDetailKey,
  isLongHexId,
  isOpaqueIdKey,
  isPlainObject,
  isUnsetValue,
  isUuid,
  truncateId,
} from "@/utils/auditFormat"

import {
  AUDIT_ACTIONS,
  AUDIT_RESULTS,
  AUDIT_TARGET_TYPES,
  exportAuditLogs,
  getAuditLogs,
} from "@/api/audit"
import type { AuditLogEntry, AuditSortField, SortOrder } from "@/api/audit"
import { Badge } from "@/components/ui/Badge"
import { ClearFiltersButton } from "@/components/ui/ClearFiltersButton"
import { DateRangePicker } from "@/components/ui/DateRangePicker"
import { ExportButton, type ExportFormat } from "@/components/ui/ExportButton"
import { FilterSelect } from "@/components/ui/FilterSelect"
import { PaginationFooter } from "@/components/ui/PaginationFooter"
import { QueryErrorBanner } from "@/components/ui/QueryErrorBanner"
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
import { useDebouncedValue } from "@/hooks/useDebouncedValue"
import { usePagination } from "@/hooks/usePagination"
import { useCameraOptions } from "@/hooks/useCameraOptions"
import { useUserOptions } from "@/hooks/useUserOptions"
import { useExportJobSubmit } from "@/hooks/useExportJobSubmit"
import { formatFullDateTime } from "@/utils/datetime"
import { getUserFullName } from "@/utils/format"

const AUDIT_PAGE_SIZE = 20

/**
 * Column label -> AUDIT_SORT_FIELDS key. Only the columns that have a
 * header get an entry; audit_id and result-adjacent lookups with no column
 * on this table (result *does* have a column, but result's own text is
 * short enough that sorting by it has little practical use beyond
 * grouping identical values, so it's included for completeness against the
 * backend's allowlist) stay reachable only if a column is ever added for
 * them. An unlisted value is a 422 server-side, so this map is the only
 * source of a sort key this page will ever send.
 */
const SORTABLE: Record<string, AuditSortField> = {
  Time: "created_at",
  Actor: "user_id",
  Action: "action",
  Target: "target_type",
  Result: "result",
}

const RESULT_TONE: Record<string, "success" | "warning" | "danger"> = {
  success: "success",
  // A denied attempt is the guard working, but it's an anomaly worth a
  // second look — an operator hitting a wall they shouldn't be able to, or
  // an actual intrusion attempt — so it gets a tone between "fine" and
  // "broken" rather than either extreme.
  denied: "warning",
  failure: "danger",
}

function ResultBadge({ result }: { result: string }) {
  return (
    <Badge variant="subtle" tone={RESULT_TONE[result] ?? "neutral"}>
      {result}
    </Badge>
  )
}

/**
 * D-1 (settled): third `ADMINISTRATION` nav row. D-4 (design authority, no
 * Figma frame): closest existing precedent is Detections' Logs tab — a
 * toolbar with the full filter set, a sortable table, pagination and export
 * — so this screen follows that shape rather than inventing a new one.
 */
const AUDIT_ACTION_MAP: Record<string, string> = {
  LOGIN_SUCCESS: "Successful Login",
  LOGIN_FAILURE: "Failed Login",
  LOGOUT: "Logged Out",
  ALERT_CONFIRM: "Confirmed Alert",
  ALERT_DISMISS: "Dismissed Alert",
  ALERT_RESOLVE: "Resolved Alert",
  ALERT_CORRECTION: "Corrected Alert",
  ALERT_SNOOZE: "Snoozed Alert",
  CAMERA_CREATE: "Created Camera",
  CAMERA_UPDATE: "Updated Camera",
  CAMERA_ENABLE: "Enabled Camera",
  CAMERA_DISABLE: "Disabled Camera",
  CAMERA_DELETE: "Deleted Camera",
  REPORT_EXPORT: "Exported Report",
  AUDIT_EXPORT: "Exported Audit Log",
  USER_CREATE: "Created User",
  USER_UPDATE: "Updated User",
  USER_ENABLE: "Enabled User",
  USER_DISABLE: "Disabled User",
  USER_ROLE_CHANGE: "Changed User Role",
  USER_PASSWORD_RESET: "Reset User Password",
  USER_PROFILE_UPDATE: "Updated User Profile",
  USER_PASSWORD_CHANGE: "Changed Password",
  ALARM_SETTINGS_UPDATE: "Updated Alarm Settings",
  BACKUP_TRIGGER: "Triggered Backup",
  RESTORE_TRIGGER: "Triggered Restore",
  CAMERA_RESTORE: "Restored Camera",
}

export default function AuditLog() {
  const [searchTerm, setSearchTerm] = useState("")
  const debouncedSearch = useDebouncedValue(searchTerm.trim(), 300)
  const [startDate, setStartDate] = useState("")
  const [endDate, setEndDate] = useState("")
  const [action, setAction] = useState("")
  const [result, setResult] = useState("")
  const [userId, setUserId] = useState("")
  const [targetType, setTargetType] = useState("")
  const [expandedId, setExpandedId] = useState<number | null>(null)
  // created_at desc is the default and the only sane resting state for an
  // append-only log — the newest entries are what an admin opens this for.
  const [sort, setSort] = useState<{ key: AuditSortField; order: SortOrder }>({
    key: "created_at",
    order: "desc",
  })

  const hasFilters = Boolean(startDate || endDate || action || result || userId || targetType)

  const usersQuery = useUserOptions()
  const camerasQuery = useCameraOptions()

  const userMap = useMemo(() => {
    const map = new Map<string, string>()
    for (const u of usersQuery.data?.users ?? []) {
      map.set(String(u.user_id), u.username)
    }
    return map
  }, [usersQuery.data?.users])

  const cameraMap = useMemo(() => {
    const map = new Map<string, string>()
    for (const c of camerasQuery.data?.cameras ?? []) {
      map.set(String(c.camera_id), c.camera_name)
    }
    return map
  }, [camerasQuery.data?.cameras])

  const userOptions = [
    { value: "", label: "All actors" },
    ...(usersQuery.data?.users ?? []).map((u) => ({
      value: String(u.user_id),
      label: getUserFullName(u) || u.username,
    })),
  ]

  const actionOptions = [
    { value: "", label: "All actions" },
    ...AUDIT_ACTIONS.map((a) => ({ value: a, label: a })),
  ]

  const resultOptions = [
    { value: "", label: "All results" },
    ...AUDIT_RESULTS.map((r) => ({ value: r, label: r })),
  ]

  const targetTypeOptions = [
    { value: "", label: "All target types" },
    ...AUDIT_TARGET_TYPES.map((t) => ({ value: t, label: formatTargetType(t) })),
  ]

  // usePagination derives rangeStart/rangeEnd/totalPages from the total it's
  // seeded with -- seeding it with a literal 0 (the total isn't known until
  // the query resolves) meant rangeStart's own `totalFiltered === 0 ? 0 :
  // ...` check was permanently true, so the footer read "0-0 of N" forever
  // on every render, not just the first. Users.tsx already has the fix:
  // mirror the query's real total into state, synced during render.
  const [seenTotal, setSeenTotal] = useState(0)
  const {
    page,
    pageSize,
    offset,
    totalPages,
    rangeStart,
    rangeEnd,
    next,
    prev,
    goTo,
    setPageSize,
    reset,
  } = usePagination(seenTotal, AUDIT_PAGE_SIZE)

  const filters = {
    search: debouncedSearch || undefined,
    start_date: startDate || undefined,
    end_date: endDate || undefined,
    action: action ? [action as (typeof AUDIT_ACTIONS)[number]] : undefined,
    result: result ? [result as (typeof AUDIT_RESULTS)[number]] : undefined,
    user_id: userId ? [Number(userId)] : undefined,
    target_type: targetType || undefined,
    sort_by: sort.key,
    sort_order: sort.order,
  }

  const auditQuery = useQuery({
    queryKey: ["audit-logs", filters, pageSize, offset],
    queryFn: () => getAuditLogs({ ...filters, limit: pageSize, offset }),
    placeholderData: (previousData) => previousData,
  })

  const rows = auditQuery.data?.items ?? []
  const totalFiltered = auditQuery.data?.total_filtered ?? 0
  if (totalFiltered !== seenTotal) {
    setSeenTotal(totalFiltered)
  }
  const rangeEndValue = rangeEnd(rows.length)

  // Same filter set and the same sort_by/sort_order the list route uses —
  // without forwarding the sort, an export of a user_id-sorted view would
  // arrive in created_at order and quietly not match what was on screen.
  const exportMutation = useMutation({
    mutationFn: (format: ExportFormat) => exportAuditLogs(filters, format),
  })

  const exportJobMutation = useExportJobSubmit()

  /**
   * D-8(a)'s two-state pattern, reused rather than reinvented: clicking the
   * active column flips direction; clicking any other column takes over at
   * desc. No third click clears — "no sort" isn't a state the backend can
   * express, since omitting sort_by just means created_at desc, a sort like
   * any other.
   */
  function handleSort(key: string) {
    const sortKey = key as AuditSortField
    reset()
    setSort((prev) =>
      prev.key === sortKey
        ? { key: sortKey, order: prev.order === "asc" ? "desc" : "asc" }
        : { key: sortKey, order: "desc" },
    )
  }

  function sortFor(label: string) {
    const key = SORTABLE[label]
    if (!key) return undefined
    return { key, active: sort.key === key ? sort.order : null, onSort: handleSort }
  }

  function clearFilters() {
    setStartDate("")
    setEndDate("")
    setAction("")
    setResult("")
    setUserId("")
    setTargetType("")
    reset()
  }

  return (
    <div className="mx-auto max-w-[1400px] p-8">
      <div className="mb-6">
        <h1 className="mb-0.5 text-xl font-semibold text-fg">Audit Log</h1>
        <p className="text-xs text-fg-muted">
          Every audited state change in the system — logins, HITL transitions, camera and user
          mutations, exports and backups
        </p>
      </div>

      {auditQuery.isError ? (
        <QueryErrorBanner
          error={auditQuery.error}
          fallback="Unable to load the audit log."
          onRetry={() => auditQuery.refetch()}
        />
      ) : null}

      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2.5">
          <SearchInput
            value={searchTerm}
            onChange={(value) => {
              reset()
              setSearchTerm(value)
            }}
            placeholder="Search username, target, detail..."
          />
          <DateRangePicker
            start={startDate}
            end={endDate}
            onStartChange={(value) => {
              reset()
              setStartDate(value)
            }}
            onEndChange={(value) => {
              reset()
              setEndDate(value)
            }}
            label="Filter audit log by date"
          />
          <FilterSelect
            value={action}
            options={actionOptions}
            onChange={(value) => {
              reset()
              setAction(value)
            }}
          />
          <FilterSelect
            value={result}
            options={resultOptions}
            onChange={(value) => {
              reset()
              setResult(value)
            }}
          />
          <FilterSelect
            value={userId}
            options={userOptions}
            onChange={(value) => {
              reset()
              setUserId(value)
            }}
          />
          <FilterSelect
            value={targetType}
            options={targetTypeOptions}
            onChange={(value) => {
              reset()
              setTargetType(value)
            }}
          />
          {hasFilters ? <ClearFiltersButton onClick={clearFilters} /> : null}
        </div>
        {/*
          total_filtered is already on this query, so the pre-flight count
          is free. Both formats stay enabled here — confirmed directly
          against routes/audit.py that GET /api/audit-logs/export's
          synchronous route genuinely returns a real PDF today, not a stub
          waiting on Phase 17's job queue.

          ExportJobCreate gained action/result/target_type in P21 Step 5 --
          the async job path can now carry the same three filters the
          synchronous export always could, so the job no longer needs to be
          withheld while any of them is active (previously disabled here,
          since a job submitted without them would silently export a
          different set than what the screen showed).
        */}
        <ExportButton
          rowCount={totalFiltered}
          isExporting={exportMutation.isPending}
          exportHasError={exportMutation.isError}
          onExport={(format) => exportMutation.mutate(format)}
          isSubmittingJob={exportJobMutation.isPending}
          onExportJob={(format) =>
            exportJobMutation.mutateAsync({
              report_type: "audit",
              format,
              search: debouncedSearch || undefined,
              start_date: startDate || undefined,
              end_date: endDate || undefined,
              user_id: userId ? [Number(userId)] : undefined,
              action: action ? [action] : undefined,
              result: result ? [result] : undefined,
              target_type: targetType ? [targetType] : undefined,
              sort_by: sort.key,
              sort_order: sort.order,
            })
          }
        />
      </div>

      {exportMutation.isError ? (
        <QueryErrorBanner error={exportMutation.error} fallback="Unable to export the audit log." />
      ) : null}

      {exportJobMutation.isError ? (
        <QueryErrorBanner
          error={exportJobMutation.error}
          fallback="Unable to start the background export job."
        />
      ) : null}

      <TableContainer
        footer={
          <PaginationFooter
            page={page}
            totalPages={totalPages}
            rangeStart={rangeStart}
            rangeEnd={rangeEndValue}
            totalFiltered={totalFiltered}
            pageSize={pageSize}
            isFetching={auditQuery.isFetching}
            onPrev={prev}
            onNext={next}
            onPageChange={goTo}
            onPageSizeChange={setPageSize}
          />
        }
      >
        <Table>
          <TableHead>
            <TableHeaderCell sort={sortFor("Time")}>Time</TableHeaderCell>
            <TableHeaderCell sort={sortFor("Actor")}>Actor</TableHeaderCell>
            <TableHeaderCell sort={sortFor("Action")}>Action</TableHeaderCell>
            <TableHeaderCell sort={sortFor("Target")}>Target</TableHeaderCell>
            <TableHeaderCell sort={sortFor("Result")}>Result</TableHeaderCell>
            <TableHeaderCell className="text-right">Detail</TableHeaderCell>
          </TableHead>
          <TableBody>
            {auditQuery.isLoading ? (
              <TableStateRow colSpan={6}>Loading audit log...</TableStateRow>
            ) : rows.length === 0 ? (
              <TableStateRow colSpan={6}>
                No audit entries found for the current filters.
              </TableStateRow>
            ) : (
              rows.map((entry) => (
                <AuditRow
                  key={entry.audit_id}
                  entry={entry}
                  expanded={expandedId === entry.audit_id}
                  onToggle={() =>
                    setExpandedId((current) => (current === entry.audit_id ? null : entry.audit_id))
                  }
                  cameraMap={cameraMap}
                  userMap={userMap}
                />
              ))
            )}
          </TableBody>
        </Table>
      </TableContainer>
    </div>
  )
}

/**
 * Renders a truncated ID with a copy-to-clipboard button. The full value is
 * available on hover via a title attribute.
 */
function CopyableId({ value }: { value: string }) {
  const [copied, setCopied] = useState(false)
  const display = truncateId(value)
  const isLong = display !== value

  function handleCopy(e: React.MouseEvent) {
    e.stopPropagation()
    navigator.clipboard.writeText(value).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    })
  }

  return (
    <span className="inline-flex items-center gap-1">
      <span title={isLong ? value : undefined} className="font-mono text-xs">
        {display}
      </span>
      {isLong ? (
        <button
          type="button"
          onClick={handleCopy}
          className="inline-flex items-center rounded p-0.5 text-fg-muted transition-colors hover:text-fg"
          title={copied ? "Copied!" : "Copy full ID"}
        >
          <RiFileCopyLine size={12} />
        </button>
      ) : null}
    </span>
  )
}

/**
 * Renders a single detail value. Handles nested objects, arrays, UUIDs,
 * opaque numeric IDs, and enum/reason codes — never lets a raw object hit the
 * DOM as `[object Object]` or renders literal `null`/`undefined`.
 */
function DetailValue({
  detailKey,
  value,
  detail,
}: {
  detailKey: string
  value: unknown
  detail?: Record<string, unknown> | null
}) {
  // Null, undefined, empty string, or unset structure
  if (isUnsetValue(value)) {
    return <span className="italic text-fg-muted">Not set</span>
  }

  // Boolean
  if (typeof value === "boolean") {
    return (
      <span className={value ? "font-medium text-success" : "font-medium text-danger"}>
        {value ? "✓ Passed" : "✗ Failed"}
      </span>
    )
  }

  // Arrays (e.g. changed_fields: ["camera_name", "channel_id"] or camera_id: [1, 2])
  if (Array.isArray(value)) {
    if (detailKey === "changed_fields") {
      return <span className="font-medium text-fg">{formatChangedFields(value)}</span>
    }
    const formattedItems = value.map((item) =>
      isUnsetValue(item) ? "Not set" : formatScalarDetailValue(detailKey, item),
    )
    return <span className="font-medium text-fg">{formattedItems.join(", ")}</span>
  }

  // Nested objects fallback if rendered directly
  if (isPlainObject(value)) {
    if (detailKey === "checks") {
      const checkEntries = Object.entries(value)
      if (checkEntries.length === 0) {
        return <span className="italic text-fg-muted">Not set</span>
      }
      return (
        <div className="flex flex-wrap items-center gap-2">
          {checkEntries.map(([name, ok]) => {
            const passed = Boolean(ok)
            return (
              <Badge
                key={name}
                variant="outline"
                tone={passed ? "success" : "danger"}
                uppercase={false}
              >
                {formatCheckLabel(name)}: {passed ? "Passed" : "Failed"}
              </Badge>
            )
          })}
        </div>
      )
    }

    const activeEntries = filterActiveEntries(value)
    if (activeEntries.length === 0) {
      return <span className="italic text-fg-muted">None</span>
    }

    return (
      <div className="grid grid-cols-1 gap-x-6 gap-y-1.5 rounded-lg border border-stroke bg-surface-2 p-3 sm:grid-cols-2">
        {activeEntries.map(([subKey, subVal]) => (
          <div key={subKey} className="flex flex-wrap items-center gap-2 text-xs">
            <span className="text-fg-muted">{humanizeDetailKey(subKey)}:</span>
            <DetailValue detailKey={subKey} value={subVal} />
          </div>
        ))}
      </div>
    )
  }

  const strValue = String(value).trim()

  // UUID-shaped strings get truncated with copy button
  if (isUuid(strValue)) {
    return <CopyableId value={strValue} />
  }

  // Long hex strings (e.g. non-hyphenated backup IDs)
  if (isLongHexId(strValue)) {
    return <CopyableId value={strValue} />
  }

  // Opaque numeric IDs — append a clarifying suffix, unless a sibling key
  // in this same detail payload already spells out the name (P25 audit
  // target labels — e.g. camera_id next to camera_name).
  if (isOpaqueIdKey(detailKey) && /^\d+$/.test(strValue) && !hasResolvedName(detailKey, detail)) {
    return (
      <span className="font-medium text-fg">
        {strValue} <span className="text-caption text-fg-muted">(internal reference)</span>
      </span>
    )
  }

  // Default: formatted scalar string
  const formatted = formatScalarDetailValue(detailKey, value)
  return <span className="font-medium text-fg">{formatted}</span>
}

function AuditRow({
  entry,
  expanded,
  onToggle,
  cameraMap,
  userMap,
}: {
  entry: AuditLogEntry
  expanded: boolean
  onToggle: () => void
  cameraMap: Map<string, string>
  userMap: Map<string, string>
}) {
  const hasRequestId = entry.request_id && entry.request_id !== "-"
  const hasSourceIp = entry.source_ip && entry.source_ip !== "-"
  const hasDiagnostics = hasRequestId || hasSourceIp

  const targetDisplay = formatTargetDisplayName({
    targetType: entry.target_type,
    targetRef: entry.target_ref,
    detail: entry.detail,
    cameraMap,
    userMap,
  })

  return (
    <>
      <TableRow className="cursor-pointer" onClick={onToggle}>
        <TableCell className="text-fg-muted">{formatFullDateTime(entry.created_at)}</TableCell>
        <TableCell>
          {entry.username ?? (entry.actor_type === "system" ? "System" : "Unknown")}
          {entry.role ? (
            <span className="ml-1 text-caption text-fg-muted">({entry.role})</span>
          ) : null}
        </TableCell>
        <TableCell>{AUDIT_ACTION_MAP[entry.action] || entry.action}</TableCell>
        <TableCell className="text-fg-muted">
          {entry.target_type ? (
            <span
              title={
                entry.target_ref && targetDisplay !== entry.target_ref
                  ? `${formatTargetType(entry.target_type)} ID: ${entry.target_ref}`
                  : (entry.target_ref ?? undefined)
              }
            >
              {formatTargetType(entry.target_type)}
              {targetDisplay ? ` · ${targetDisplay}` : ""}
            </span>
          ) : (
            <span className="text-caption italic text-fg-muted">Not applicable</span>
          )}
        </TableCell>
        <TableCell>
          <ResultBadge result={entry.result} />
        </TableCell>
        <TableCell className="text-right">
          {expanded ? (
            <RiArrowDownSLine size={16} className="ml-auto text-fg-muted" />
          ) : (
            <RiArrowRightSLine size={16} className="ml-auto text-fg-muted" />
          )}
        </TableCell>
      </TableRow>
      {expanded ? (
        <TableRow className="hover:bg-transparent">
          <TableCell colSpan={6} className="bg-canvas">
            {/*
              detail is stored as a JSON string backend-side and exposed as
              a parsed object by a field_validator — it arrives as real
              structure and must not be re-parsed as a string here.
            */}
            <div className="space-y-4 py-2">
              {/* — Action Details (operational, always visible) — */}
              <div>
                <h4 className="mb-2 text-xs font-semibold text-fg-muted">Action Details</h4>
                {entry.detail && Object.keys(entry.detail).length > 0 ? (
                  <div className="grid grid-cols-1 gap-x-8 gap-y-2.5 text-xs md:grid-cols-2">
                    {Object.entries(entry.detail).map(([key, value]) => {
                      if (isPlainObject(value)) {
                        if (key === "checks") {
                          const checkEntries = Object.entries(value)
                          return (
                            <div key={key} className="col-span-full flex flex-col gap-1.5">
                              <span className="font-medium text-fg-muted">
                                {humanizeDetailKey(key)}:
                              </span>
                              <div className="pl-3">
                                {checkEntries.length === 0 ? (
                                  <span className="italic text-fg-muted">Not set</span>
                                ) : (
                                  <div className="flex flex-wrap items-center gap-2">
                                    {checkEntries.map(([name, ok]) => {
                                      const passed = Boolean(ok)
                                      return (
                                        <Badge
                                          key={name}
                                          variant="outline"
                                          tone={passed ? "success" : "danger"}
                                          uppercase={false}
                                        >
                                          {formatCheckLabel(name)}: {passed ? "Passed" : "Failed"}
                                        </Badge>
                                      )
                                    })}
                                  </div>
                                )}
                              </div>
                            </div>
                          )
                        }

                        const activeEntries = filterActiveEntries(value)
                        if (activeEntries.length === 0) {
                          return (
                            <div key={key} className="flex items-center gap-2">
                              <span className="text-fg-muted">{humanizeDetailKey(key)}:</span>
                              <span className="italic text-fg-muted">None</span>
                            </div>
                          )
                        }

                        return (
                          <div key={key} className="col-span-full flex flex-col gap-1.5">
                            <span className="font-medium text-fg-muted">
                              {humanizeDetailKey(key)}:
                            </span>
                            <div className="pl-3">
                              <div className="grid grid-cols-1 gap-x-6 gap-y-1.5 rounded-lg border border-stroke bg-surface-2 p-3 sm:grid-cols-2">
                                {activeEntries.map(([subKey, subVal]) => (
                                  <div
                                    key={subKey}
                                    className="flex flex-wrap items-center gap-2 text-xs"
                                  >
                                    <span className="text-fg-muted">
                                      {humanizeDetailKey(subKey)}:
                                    </span>
                                    <DetailValue
                                      detailKey={subKey}
                                      value={subVal}
                                      detail={entry.detail}
                                    />
                                  </div>
                                ))}
                              </div>
                            </div>
                          </div>
                        )
                      }

                      return (
                        <div key={key} className="flex flex-wrap items-center gap-2">
                          <span className="text-fg-muted">{humanizeDetailKey(key)}:</span>
                          <DetailValue detailKey={key} value={value} detail={entry.detail} />
                        </div>
                      )
                    })}
                  </div>
                ) : (
                  <div className="text-xs text-fg-muted">No detail recorded.</div>
                )}
              </div>

              {/* — Technical Details (diagnostic, collapsible) — */}
              <details className="group">
                <summary className="cursor-pointer select-none text-caption text-fg-muted transition-colors hover:text-fg">
                  <span className="ml-1">Technical Details</span>
                </summary>
                <div className="mt-2 space-y-1 pl-4 text-caption text-fg-muted">
                  <div>
                    Request ID:{" "}
                    {hasRequestId ? (
                      <CopyableId value={entry.request_id!} />
                    ) : (
                      <span className="italic">N/A (system-initiated)</span>
                    )}
                  </div>
                  <div>
                    Source IP:{" "}
                    {hasSourceIp ? (
                      <span>{entry.source_ip}</span>
                    ) : (
                      <span className="italic">
                        {hasDiagnostics ? "N/A" : "N/A (system-initiated)"}
                      </span>
                    )}
                  </div>
                </div>
              </details>
            </div>
          </TableCell>
        </TableRow>
      ) : null}
    </>
  )
}
