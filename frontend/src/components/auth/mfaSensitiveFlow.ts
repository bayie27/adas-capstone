import { createContext, useContext } from "react"

export interface ShowMfaRecoveryCodesOptions {
  codes: string[]
  accountName: string
  onAcknowledged: () => void
  onDismissed?: () => void
}

export interface MfaSensitiveFlowContextValue {
  showCodes: (options: ShowMfaRecoveryCodesOptions) => void
  clearCodes: () => void
}

export const MfaSensitiveFlowContext = createContext<MfaSensitiveFlowContextValue | null>(null)

export function useMfaSensitiveFlow(): MfaSensitiveFlowContextValue {
  const value = useContext(MfaSensitiveFlowContext)
  if (!value) {
    throw new Error("useMfaSensitiveFlow must be used inside MfaSensitiveFlowProvider.")
  }
  return value
}
