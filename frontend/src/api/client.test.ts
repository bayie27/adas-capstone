import { afterEach, describe, expect, it, vi } from "vitest"

import { useAuthStore } from "@/store/useAuthStore"
import api from "./client"

/**
 * The response interceptor isn't exported — it's registered on the shared
 * axios instance in client.ts. Reaching into `interceptors.response`'s
 * internal handler list is the only way to invoke it directly without
 * standing up a fake HTTP layer for what is a pure error-classification
 * branch.
 */
function getRejectedHandler() {
  const handlers = (api.interceptors.response as unknown as { handlers: unknown[] }).handlers
  const last = handlers[handlers.length - 1] as { rejected: (error: unknown) => Promise<never> }
  return last.rejected
}

function make401(code?: string) {
  return {
    response: {
      status: 401,
      data: code ? { code, detail: "irrelevant" } : {},
    },
  }
}

/**
 * JSDOM's `window.location.replace` is a non-configurable own property, so
 * `vi.spyOn` can't touch it directly — the whole `location` property has to
 * be swapped for a stub carrying only what `redirectToLogin` reads.
 */
function stubLocation(pathname: string) {
  const original = Object.getOwnPropertyDescriptor(window, "location")!
  const replace = vi.fn()
  Object.defineProperty(window, "location", {
    configurable: true,
    value: { pathname, replace },
  })
  return {
    replace,
    restore: () => Object.defineProperty(window, "location", original),
  }
}

describe("api response interceptor", () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it("does not clear the session or redirect for AUTH_INVALID_CREDENTIALS — a re-auth failure, not a lost session", async () => {
    const clearSession = vi.fn()
    useAuthStore.setState({ clearSession })
    const location = stubLocation("/maintenance")

    try {
      await expect(getRejectedHandler()(make401("AUTH_INVALID_CREDENTIALS"))).rejects.toBeTruthy()

      expect(clearSession).not.toHaveBeenCalled()
      expect(location.replace).not.toHaveBeenCalled()
    } finally {
      location.restore()
    }
  })

  it.each(["AUTH_REQUIRED", "AUTH_EXPIRED", "AUTH_REVOKED"])(
    "clears the session and redirects to /login for a genuine %s",
    async (code) => {
      const clearSession = vi.fn()
      useAuthStore.setState({ clearSession })
      const location = stubLocation("/maintenance")

      try {
        await expect(getRejectedHandler()(make401(code))).rejects.toBeTruthy()

        expect(clearSession).toHaveBeenCalledOnce()
        expect(location.replace).toHaveBeenCalledWith("/login")
      } finally {
        location.restore()
      }
    },
  )

  it("still redirects for a 401 with no ApiError envelope (safe default)", async () => {
    const clearSession = vi.fn()
    useAuthStore.setState({ clearSession })
    const location = stubLocation("/maintenance")

    try {
      await expect(getRejectedHandler()(make401())).rejects.toBeTruthy()

      expect(clearSession).toHaveBeenCalledOnce()
      expect(location.replace).toHaveBeenCalledWith("/login")
    } finally {
      location.restore()
    }
  })

  it("leaves a non-401 error alone", async () => {
    const clearSession = vi.fn()
    useAuthStore.setState({ clearSession })
    const location = stubLocation("/maintenance")

    try {
      await expect(
        getRejectedHandler()({ response: { status: 500, data: {} } }),
      ).rejects.toBeTruthy()

      expect(clearSession).not.toHaveBeenCalled()
      expect(location.replace).not.toHaveBeenCalled()
    } finally {
      location.restore()
    }
  })

  it("does not redirect again if already on the login page", async () => {
    const clearSession = vi.fn()
    useAuthStore.setState({ clearSession })
    const location = stubLocation("/login")

    try {
      await expect(getRejectedHandler()(make401("AUTH_EXPIRED"))).rejects.toBeTruthy()

      expect(clearSession).toHaveBeenCalledOnce()
      expect(location.replace).not.toHaveBeenCalled()
    } finally {
      location.restore()
    }
  })
})
