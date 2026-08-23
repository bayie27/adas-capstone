import { describe, expect, it } from "vitest"
import {
  formatChangedFields,
  formatCheckLabel,
  humanizeDetailKey,
  humanizeReasonValue,
  isUuid,
  truncateId,
} from "./auditFormat"

describe("auditFormat", () => {
  describe("formatCheckLabel", () => {
    it("maps known validation check keys to human-friendly labels", () => {
      expect(formatCheckLabel("checksum")).toBe("File Integrity")
      expect(formatCheckLabel("quick_check")).toBe("Database Structure")
      expect(formatCheckLabel("foreign_key_check")).toBe("Data Links")
    })

    it("falls back to title-casing unmapped check keys", () => {
      expect(formatCheckLabel("custom_integrity_check")).toBe("Custom Integrity Check")
    })
  })

  describe("humanizeDetailKey", () => {
    it("maps known detail keys", () => {
      expect(humanizeDetailKey("checks")).toBe("Validation Checks")
      expect(humanizeDetailKey("backup_id")).toBe("Backup ID")
    })
  })

  describe("humanizeReasonValue", () => {
    it("maps known internal reason codes", () => {
      expect(humanizeReasonValue("self_delete")).toBe("Cannot delete own account")
    })
  })

  describe("truncateId and isUuid", () => {
    it("handles UUID detection and truncation", () => {
      const id = "458f0a83-c7f0-4db5-9876-c5415f7b89f6"
      expect(isUuid(id)).toBe(true)
      expect(truncateId(id)).toBe("458f0a83…7b89f6")
    })
  })

  describe("formatChangedFields", () => {
    it("formats array of changed fields", () => {
      expect(formatChangedFields(["camera_name", "channel_id"])).toBe("Camera Name, Channel Id")
    })
  })
})
