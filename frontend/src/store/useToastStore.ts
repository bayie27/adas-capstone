import { create } from "zustand"

export type ToastTone = "success" | "error" | "info" | "warning"

export interface ToastItem {
  id: string
  tone: ToastTone
  title?: string
  message: string
  duration?: number
}

export interface ToastOptions {
  title?: string
  duration?: number
}

interface ToastState {
  toasts: ToastItem[]
  addToast: (toast: Omit<ToastItem, "id">) => string
  dismissToast: (id: string) => void
  clearAll: () => void
}

export const useToastStore = create<ToastState>((set) => ({
  toasts: [],
  addToast: (toast) => {
    const id = `toast-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`
    set((state) => ({
      toasts: [...state.toasts, { ...toast, id }],
    }))
    return id
  },
  dismissToast: (id) => {
    set((state) => ({
      toasts: state.toasts.filter((t) => t.id !== id),
    }))
  },
  clearAll: () => {
    set({ toasts: [] })
  },
}))

/**
 * Convenient standalone toast triggers that can be invoked from anywhere
 * (event handlers, react-query callbacks, api utilities).
 */
export const toast = {
  success: (message: string, options?: ToastOptions) =>
    useToastStore.getState().addToast({ tone: "success", message, ...options }),
  error: (message: string, options?: ToastOptions) =>
    useToastStore.getState().addToast({ tone: "error", message, ...options }),
  info: (message: string, options?: ToastOptions) =>
    useToastStore.getState().addToast({ tone: "info", message, ...options }),
  warning: (message: string, options?: ToastOptions) =>
    useToastStore.getState().addToast({ tone: "warning", message, ...options }),
  dismiss: (id: string) => useToastStore.getState().dismissToast(id),
  clear: () => useToastStore.getState().clearAll(),
}
