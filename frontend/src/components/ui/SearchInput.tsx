import SearchLineIcon from "remixicon-react/SearchLineIcon"

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
      <SearchLineIcon size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#555]" />
      <input
        type="text"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        className="w-60 rounded-md border border-[#2A2A2A] bg-[#141414] py-1.5 pl-8 pr-4 text-xs text-white focus:border-[#52525B] focus:outline-none"
      />
    </div>
  )
}
