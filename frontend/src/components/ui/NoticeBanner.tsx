/** Shared shape for success/error/warning notices. This is the one home for the type. */
export type NoticeState = { tone: "success" | "error" | "warning"; message: string }

export function NoticeBanner({ notice }: { notice: NoticeState }) {
  const toneClass =
    notice.tone === "success"
      ? "border-success-border bg-success-subtle text-success"
      : notice.tone === "warning"
        ? "border-warning-border bg-warning-subtle text-warning"
        : "border-danger-border bg-danger-subtle text-danger"

  return (
    <div className={`mb-4 rounded-md border px-4 py-3 text-xs ${toneClass}`}>{notice.message}</div>
  )
}
