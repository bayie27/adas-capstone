import { useState } from "react"
import { useMutation, useQuery } from "@tanstack/react-query"
import { RiArrowDownSLine, RiArrowRightSLine, RiFileHistoryLine } from "@remixicon/react"

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
    ...AUDIT_TARGET_TYPES.map((t) => ({ value: t, label: t })),
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
      <div className="mb-6 flex items-center gap-2.5">
        <RiFileHistoryLine size={18} className="text-fg-muted" />
        <div>
          <h1 className="mb-0.5 text-xl font-semibold text-fg">Audit Log</h1>
          <p className="text-xs text-fg-muted">
            Every audited state change in the system — logins, HITL transitions, camera and user
            mutations, exports and backups
          </p>
        </div>
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
                />
              ))
            )}
          </TableBody>
        </Table>
      </TableContainer>
    </div>
  )
}

function AuditRow({
  entry,
  expanded,
  onToggle,
}: {
  entry: AuditLogEntry
  expanded: boolean
  onToggle: () => void
}) {
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
        <TableCell className="font-mono text-caption">{entry.action}</TableCell>
        <TableCell className="text-fg-muted">
          {entry.target_type
            ? `${entry.target_type}${entry.target_ref ? ` · ${entry.target_ref}` : ""}`
            : "-"}
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
              source_ip and request_id are the forensic columns; request_id
              is what correlates this row with a line in the backend log,
              which is the only reason the field exists, so both live in
              the expanded view rather than the row.
            */}
            <div className="grid grid-cols-1 gap-4 py-2 md:grid-cols-[1fr_auto]">
              <pre className="overflow-x-auto rounded-md border border-stroke bg-surface-1 p-3 text-caption text-fg-body">
                {entry.detail ? JSON.stringify(entry.detail, null, 2) : "No detail recorded."}
              </pre>
              <div className="space-y-1 text-caption text-fg-muted">
                <div>
                  <span className="font-semibold text-fg-body">Request ID:</span>{" "}
                  {entry.request_id ?? "-"}
                </div>
                <div>
                  <span className="font-semibold text-fg-body">Source IP:</span>{" "}
                  {entry.source_ip ?? "-"}
                </div>
              </div>
            </div>
          </TableCell>
        </TableRow>
      ) : null}
    </>
  )
}
