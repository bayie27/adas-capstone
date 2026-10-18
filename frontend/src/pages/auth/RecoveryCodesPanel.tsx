import { useId, useRef, useState } from "react"

import { Button } from "@/components/ui/Button"
import { Card } from "@/components/ui/Card"

interface RecoveryCodesPanelProps {
  codes: string[]
  accountName: string
  onAcknowledged: () => void
}

function safeFilenamePart(value: string): string {
  return (
    value
      .trim()
      .replace(/[^a-z0-9._-]+/gi, "-")
      .replace(/^-+|-+$/g, "") || "account"
  )
}

export function RecoveryCodesPanel({
  codes,
  accountName,
  onAcknowledged,
}: RecoveryCodesPanelProps) {
  const checkboxId = useId()
  const [acknowledged, setAcknowledged] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [working, setWorking] = useState<"copy" | "download" | null>(null)
  const [continued, setContinued] = useState(false)
  const acknowledgedRef = useRef(false)
  const [generatedAt] = useState(() => new Date())
  const generatedLabel = new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(
    generatedAt,
  )

  async function handleCopy() {
    setError(null)
    setWorking("copy")
    try {
      if (!navigator.clipboard?.writeText) {
        throw new Error("Clipboard access is unavailable")
      }
      await navigator.clipboard.writeText(codes.join("\n"))
    } catch {
      setError("Couldn't copy the codes. Select them below and copy them manually.")
    } finally {
      setWorking(null)
    }
  }

  function handleDownload() {
    setError(null)
    setWorking("download")
    let objectUrl: string | null = null
    let anchor: HTMLAnchorElement | null = null
    try {
      const content = [
        "ADAS recovery codes",
        `Account: ${accountName}`,
        `Generated: ${generatedLabel}`,
        "Keep this file offline in a secure place. Anyone with these codes can access your account.",
        "ADAS cannot verify that this file was saved.",
        "",
        ...codes,
        "",
      ].join("\n")
      const blob = new Blob([content], { type: "text/plain;charset=utf-8" })
      objectUrl = URL.createObjectURL(blob)
      anchor = document.createElement("a")
      anchor.href = objectUrl
      anchor.download = `ADAS-recovery-codes-${safeFilenamePart(accountName)}-${generatedAt
        .toISOString()
        .slice(0, 10)}.txt`
      anchor.style.display = "none"
      document.body.appendChild(anchor)
      anchor.click()
    } catch {
      setError("Couldn't download the codes. Copy them or select and save them manually.")
    } finally {
      anchor?.remove()
      if (objectUrl) URL.revokeObjectURL(objectUrl)
      setWorking(null)
    }
  }

  function handleContinue() {
    if (!acknowledged || acknowledgedRef.current) return
    acknowledgedRef.current = true
    setContinued(true)
    onAcknowledged()
  }

  return (
    <Card className="w-full max-w-[560px] p-6 sm:p-8">
      <div className="mb-6 space-y-2">
        <h1 className="text-xl font-semibold text-fg">Save your recovery codes</h1>
        <p className="text-secondary text-fg-muted">
          These codes are shown once. Store them offline; each code works one time. ADAS cannot
          retrieve this batch or verify that you saved it.
        </p>
        <p className="text-caption text-fg-muted">
          Account: <span className="font-medium text-fg">{accountName}</span> · Generated{" "}
          {generatedLabel}
        </p>
      </div>

      <div className="mb-5 grid grid-cols-1 gap-3 sm:grid-cols-2">
        <Button
          type="button"
          variant="outline"
          disabled={working !== null}
          isLoading={working === "copy"}
          loadingLabel="Copying…"
          onClick={() => void handleCopy()}
        >
          Copy codes
        </Button>
        <Button
          type="button"
          variant="outline"
          disabled={working !== null}
          isLoading={working === "download"}
          loadingLabel="Preparing…"
          onClick={handleDownload}
        >
          Download .txt
        </Button>
      </div>

      {error ? (
        <p
          role="alert"
          className="mb-4 rounded-md border border-danger-border bg-danger-subtle px-4 py-3 text-caption text-danger"
        >
          {error}
        </p>
      ) : null}

      <ul
        aria-label="One-time recovery codes"
        className="mb-6 grid grid-cols-1 gap-2 rounded-md border border-stroke bg-surface-2 p-4 sm:grid-cols-2"
      >
        {codes.map((code) => (
          <li key={code}>
            <code className="block break-all rounded bg-surface-1 px-3 py-2 text-center text-secondary font-semibold tracking-[0.08em] text-fg">
              {code}
            </code>
          </li>
        ))}
      </ul>

      <div className="mb-5 space-y-2">
        <p className="text-caption text-fg-muted">
          If you lose your authenticator and all unused codes, ADAS has no account recovery path.
          Keep this batch separate from your device.
        </p>
        <label htmlFor={checkboxId} className="flex items-start gap-2 text-caption text-fg-body">
          <input
            id={checkboxId}
            type="checkbox"
            checked={acknowledged}
            onChange={(event) => setAcknowledged(event.target.checked)}
            className="mt-0.5 accent-primary"
          />
          <span>I saved these codes and understand they cannot be shown again.</span>
        </label>
      </div>

      <Button
        type="button"
        className="w-full"
        disabled={!acknowledged || continued}
        onClick={handleContinue}
      >
        Continue
      </Button>
    </Card>
  )
}
