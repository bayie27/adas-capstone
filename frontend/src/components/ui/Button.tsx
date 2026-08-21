import type { ButtonHTMLAttributes, ReactNode } from "react"

import { cn } from "@/utils/cn"

/**
 * FE_Implementation.md §2.8 — the focus treatment for every interactive
 * primitive. Figma draws focus nowhere, so this is specified rather than
 * copied: an operator console is keyboard-driven under load, `focus-visible`
 * avoids the ring on a mouse click, and --color-stroke-strong is the only
 * neutral with enough contrast against both --color-surface-1 and
 * --color-primary.
 */
export const focusRing =
  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-stroke-strong focus-visible:outline-solid focus:outline-none"

/** §2.8 — opacity only, no colour change, consistent across the app. */
export const disabledTreatment = "disabled:cursor-not-allowed disabled:opacity-60"

export type ButtonVariant = "primary" | "secondary" | "outline" | "destructive" | "ghost"
export type ButtonSize = "sm" | "md" | "icon"

const VARIANTS: Record<ButtonVariant, string> = {
  // §2.2 — the near-white action: Add Camera, Add User, Login, Confirm/Resolve.
  primary: "bg-primary text-fg-on-primary hover:bg-primary-hover",
  // §2.2 — Dark/Secondary fill; §2.8 hover raises it to the elevated surface.
  secondary: "bg-surface-3 text-fg hover:bg-surface-2",
  outline: "border border-border bg-transparent text-fg hover:bg-surface-2",
  destructive: "bg-danger text-fg-on-primary hover:bg-danger/90",
  ghost: "bg-transparent text-fg hover:bg-surface-2",
}

const SIZES: Record<ButtonSize, string> = {
  // §2.3 — 40px is the toolbar control height.
  md: "h-10 px-4 text-sm",
  sm: "h-8 px-3 text-xs",
  icon: "h-10 w-10",
}

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant
  size?: ButtonSize
  /**
   * §2.8 — a button in flight keeps its size, swaps its label for the
   * present-progressive verb and disables itself. No spinner: the label is
   * the progress indicator.
   */
  isLoading?: boolean
  loadingLabel?: string
  children?: ReactNode
}

export function Button({
  variant = "primary",
  size = "md",
  isLoading = false,
  loadingLabel,
  disabled,
  className,
  children,
  type = "button",
  ...rest
}: ButtonProps) {
  return (
    <button
      type={type}
      disabled={disabled || isLoading}
      aria-busy={isLoading || undefined}
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-md font-medium transition-colors duration-150",
        VARIANTS[variant],
        SIZES[size],
        focusRing,
        disabledTreatment,
        className,
      )}
      {...rest}
    >
      {isLoading && loadingLabel ? loadingLabel : children}
    </button>
  )
}
