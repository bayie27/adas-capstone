import { RiSearchLine } from "@remixicon/react"

export function SearchInput({
  value,
  onChange,
  placeholder,
}: {
  value: string
  onChange: (value: string) => void
  placeholder?: string
}) {
  return (
    <div className="relative">
      <RiSearchLine size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-fg-muted" />
      <input
        type="text"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        className="w-60 rounded-md border border-stroke bg-surface-1 py-1.5 pl-8 pr-4 text-xs text-white focus:border-stroke-strong focus:outline-none"
      />
    </div>
  )
}
