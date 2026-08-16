import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { RiArrowDownSLine, RiArrowRightSLine, RiFileHistoryLine } from "@remixicon/react"

import { AUDIT_ACTIONS, AUDIT_RESULTS, AUDIT_TARGET_TYPES, getAuditLogs } from "@/api/audit"
import type { AuditLogEntry } from "@/api/audit"
import { Badge } from "@/components/ui/Badge"
import { Button } from "@/components/ui/Button"
import { DateRangePicker } from "@/components/ui/DateRangePicker"
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
import { formatFullDateTime } from "@/utils/datetime"
import { getUserFullName } from "@/utils/format"

const AUDIT_PAGE_SIZE = 20

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

  const { page, pageSize, offset, rangeStart, rangeEnd, next, prev, goTo, setPageSize, reset } =
    usePagination(0, AUDIT_PAGE_SIZE)

  const filters = {
    search: debouncedSearch || undefined,
    start_date: startDate || undefined,
    end_date: endDate || undefined,
    action: action ? [action as (typeof AUDIT_ACTIONS)[number]] : undefined,
    result: result ? [result as (typeof AUDIT_RESULTS)[number]] : undefined,
    user_id: userId ? [Number(userId)] : undefined,
    target_type: targetType || undefined,
  }

  const auditQuery = useQuery({
    queryKey: ["audit-logs", filters, pageSize, offset],
    queryFn: () => getAuditLogs({ ...filters, limit: pageSize, offset }),
    placeholderData: (previousData) => previousData,
  })

  const rows = auditQuery.data?.items ?? []
  const totalFiltered = auditQuery.data?.total_filtered ?? 0
  const rangeEndValue = rangeEnd(rows.length)

  // usePagination is seeded with 0 above (the total isn't known until the
  // query resolves); re-derive totalPages/page against the real total so
  // the footer and the clamp agree with what actually came back.
  const realTotalPages = Math.max(1, Math.ceil(totalFiltered / pageSize))
  const realPage = Math.min(page, realTotalPages)

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
          {hasFilters ? (
            <Button variant="outline" size="sm" onClick={clearFilters}>
              Clear
            </Button>
          ) : null}
        </div>
      </div>

      <TableContainer
        footer={
          <PaginationFooter
            page={realPage}
            totalPages={realTotalPages}
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
            <TableHeaderCell>Time</TableHeaderCell>
            <TableHeaderCell>Actor</TableHeaderCell>
            <TableHeaderCell>Action</TableHeaderCell>
            <TableHeaderCell>Target</TableHeaderCell>
            <TableHeaderCell>Result</TableHeaderCell>
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
