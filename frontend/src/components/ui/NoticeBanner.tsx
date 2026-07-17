/** Shared shape for success/error notices. This is the one home for the type. */
export type NoticeState = { tone: "success" | "error"; message: string }

export function NoticeBanner({ notice }: { notice: NoticeState }) {
  return (
    <div
      className={`mb-4 rounded-md border px-4 py-3 text-xs ${
        notice.tone === "success"
          ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300"
          : "border-[#F87171]/30 bg-[#F87171]/10 text-[#FCA5A5]"
      }`}
    >
      {notice.message}
    </div>
  )
}
