import "@testing-library/jest-dom/vitest"

// Mock localStorage for JSDOM
const localStorageMock = (function () {
  let store: Record<string, string> = {}
  return {
    getItem: function (key: string) {
      return store[key] || null
    },
    setItem: function (key: string, value: string) {
      store[key] = value.toString()
    },
    removeItem: function (key: string) {
      delete store[key]
    },
    clear: function () {
      store = {}
    },
  }
})()

Object.defineProperty(window, "localStorage", {
  value: localStorageMock,
})

// JSDOM doesn't implement layout, so scrollIntoView doesn't exist at all —
// stub it as a no-op so components that call it (e.g. to surface an
// off-screen validation error) don't crash under test.
if (!Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = function () {}
}
