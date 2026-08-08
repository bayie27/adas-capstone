import { describe, expect, it } from "vitest"
import { cn } from "./cn"

describe("cn", () => {
  it("joins simple class names", () => {
    expect(cn("a", "b")).toBe("a b")
  })

  it("drops falsy values", () => {
    expect(cn("a", false, undefined, null, "b")).toBe("a b")
  })

  it("resolves conflicting tailwind utilities to the last one", () => {
    expect(cn("px-2", "px-4")).toBe("px-4")
  })

  it("merges conditional class objects", () => {
    expect(cn("base", { active: true, disabled: false })).toBe("base active")
  })
})
