import { describe, expect, it } from "vitest"

import { failureMessage } from "./exportJobs"

describe("failureMessage", () => {
  it("renders a distinct sentence for generation_failed", () => {
    expect(failureMessage("generation_failed")).toMatch(/generating the file/)
  })

  it("renders a distinct sentence for artifact_write_failed", () => {
    expect(failureMessage("artifact_write_failed")).toMatch(/could not be saved/)
  })

  it("falls back for a category the worker never actually assigns", () => {
    expect(failureMessage("row_limit_exceeded")).toMatch(/unrecorded reason/)
    expect(failureMessage(null)).toMatch(/unrecorded reason/)
  })
})
