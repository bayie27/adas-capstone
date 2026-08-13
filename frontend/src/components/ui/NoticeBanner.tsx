/** Shared shape for success/error notices. This is the one home for the type. */
export type NoticeState = { tone: "success" | "error"; message: string }

export function NoticeBanner({ notice }: { notice: NoticeState }) {
  return (
    <div
      className={`mb-4 rounded-md border px-4 py-3 text-xs ${
        notice.tone === "success"
          ? "border-success-border bg-success-subtle text-success"
          : "border-danger-border bg-danger-subtle text-danger"
      }`}
    >
      {notice.message}
    </div>
  )
}
