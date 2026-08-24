import { describe, expect, it } from "vitest"
import {
  formatChangedFields,
  formatCheckLabel,
  formatTargetType,
  hasResolvedName,
  humanizeDetailKey,
  humanizeReasonValue,
  isLongHexId,
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

  describe("isLongHexId", () => {
    it("is true for a 32-char uuid4().hex-shaped id", () => {
      expect(isLongHexId("a3f9e1c204b84d7a9e6f8b1c2d3e4f50")).toBe(true)
    })

    it("is false for a dashed uuid -- that is isUuid's job", () => {
      expect(isLongHexId("458f0a83-c7f0-4db5-9876-c5415f7b89f6")).toBe(false)
    })

    it("is false for a short numeric id", () => {
      expect(isLongHexId("118")).toBe(false)
    })
  })

  describe("formatTargetType", () => {
    it("maps known target types to human-friendly labels", () => {
      expect(formatTargetType("restore")).toBe("Restore Point")
      expect(formatTargetType("backup")).toBe("Backup")
    })

    it("falls back to title-casing an unknown target type", () => {
      expect(formatTargetType("maintenance_window")).toBe("Maintenance Window")
    })
  })

  describe("formatChangedFields", () => {
    it("formats array of changed fields", () => {
      expect(formatChangedFields(["camera_name", "channel_id"])).toBe("Camera Name, Channel Id")
    })
  })

  describe("hasResolvedName", () => {
    it("is true for camera_id when a sibling camera_name string is present", () => {
      expect(hasResolvedName("camera_id", { camera_id: 3, camera_name: "Front Entrance" })).toBe(
        true,
      )
    })

    it("is false when the sibling name key is absent", () => {
      expect(hasResolvedName("camera_id", { camera_id: 3 })).toBe(false)
    })

    it("is false when the sibling name key is null", () => {
      expect(hasResolvedName("camera_id", { camera_id: 3, camera_name: null })).toBe(false)
    })

    it("is false for a key with no known sibling name key", () => {
      expect(hasResolvedName("channel_id", { channel_id: 5 })).toBe(false)
    })

    it("is false when detail is undefined or null", () => {
      expect(hasResolvedName("camera_id", undefined)).toBe(false)
      expect(hasResolvedName("camera_id", null)).toBe(false)
    })
  })
})
