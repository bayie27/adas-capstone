import { describe, expect, it } from "vitest"
import {
  filterActiveEntries,
  formatChangedFields,
  formatCheckLabel,
  formatScalarDetailValue,
  formatTargetDisplayName,
  formatTargetType,
  hasResolvedName,
  humanizeDetailKey,
  humanizeReasonValue,
  isLongHexId,
  isOpaqueIdKey,
  isPlainObject,
  isUnsetValue,
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
      expect(humanizeDetailKey("report_type")).toBe("Report Type")
      expect(humanizeDetailKey("row_count")).toBe("Row Count")
      expect(humanizeDetailKey("filters")).toBe("Filters")
      expect(humanizeDetailKey("sort")).toBe("Sorting")
      expect(humanizeDetailKey("start_date")).toBe("Start Date")
      expect(humanizeDetailKey("end_date")).toBe("End Date")
    })

    it("falls back to title-casing unmapped keys", () => {
      expect(humanizeDetailKey("custom_filter_key")).toBe("Custom Filter Key")
    })
  })

  describe("humanizeReasonValue", () => {
    it("maps known internal reason codes", () => {
      expect(humanizeReasonValue("self_delete")).toBe("Cannot delete own account")
      expect(humanizeReasonValue("row_limit_exceeded")).toBe("Row limit exceeded")
    })
  })

  describe("truncateId and isUuid", () => {
    it("handles UUID detection and truncation", () => {
      const id = "458f0a83-c7f0-4db5-9876-c5415f7b89f6"
      expect(isUuid(id)).toBe(true)
      expect(truncateId(id)).toBe("458f0a83…7b89f6")
    })

    it("returns short IDs unchanged", () => {
      expect(truncateId("short-id")).toBe("short-id")
    })
  })

  describe("isPlainObject", () => {
    it("identifies plain objects", () => {
      expect(isPlainObject({})).toBe(true)
      expect(isPlainObject({ a: 1 })).toBe(true)
      expect(isPlainObject(null)).toBe(false)
      expect(isPlainObject([])).toBe(false)
      expect(isPlainObject("string")).toBe(false)
    })
  })

  describe("isUnsetValue", () => {
    it("identifies null and undefined as unset", () => {
      expect(isUnsetValue(null)).toBe(true)
      expect(isUnsetValue(undefined)).toBe(true)
    })

    it("identifies empty and whitespace strings as unset", () => {
      expect(isUnsetValue("")).toBe(true)
      expect(isUnsetValue("   ")).toBe(true)
      expect(isUnsetValue("valid")).toBe(false)
    })

    it("identifies empty arrays and arrays of unset values as unset", () => {
      expect(isUnsetValue([])).toBe(true)
      expect(isUnsetValue([null, ""])).toBe(true)
      expect(isUnsetValue(["active"])).toBe(false)
    })

    it("identifies empty objects and objects with all unset values as unset", () => {
      expect(isUnsetValue({})).toBe(true)
      expect(isUnsetValue({ action: null, user_id: null, search: "" })).toBe(true)
      expect(isUnsetValue({ action: "LOGIN_SUCCESS", user_id: null })).toBe(false)
    })
  })

  describe("filterActiveEntries", () => {
    it("filters out unset key-value pairs", () => {
      const filters = {
        action: null,
        user_id: null,
        start_date: "2026-08-01",
        search: "",
        camera_id: [1, 2],
      }
      const active = filterActiveEntries(filters)
      expect(active).toEqual([
        ["start_date", "2026-08-01"],
        ["camera_id", [1, 2]],
      ])
    })
  })

  describe("formatScalarDetailValue", () => {
    it("formats known enum/mode/format keys", () => {
      expect(formatScalarDetailValue("mode", "sync")).toBe("Direct Download")
      expect(formatScalarDetailValue("mode", "job")).toBe("Background Export")
      expect(formatScalarDetailValue("format", "csv")).toBe("CSV")
      expect(formatScalarDetailValue("report_type", "audit")).toBe("Audit Log")
      expect(formatScalarDetailValue("order", "desc")).toBe("Descending")
      expect(formatScalarDetailValue("field", "created_at")).toBe("Time")
      expect(formatScalarDetailValue("trigger", "manual")).toBe("Manual")
      expect(formatScalarDetailValue("row_count", 1250)).toBe("1,250")
    })

    it("returns Not set for unset values", () => {
      expect(formatScalarDetailValue("mode", null)).toBe("Not set")
      expect(formatScalarDetailValue("mode", "")).toBe("Not set")
    })
  })

  describe("isOpaqueIdKey", () => {
    it("identifies opaque id keys", () => {
      expect(isOpaqueIdKey("camera_id")).toBe(true)
      expect(isOpaqueIdKey("channel_id")).toBe(false)
      expect(isOpaqueIdKey("user_id")).toBe(false)
    })
  })

  describe("formatTargetDisplayName", () => {
    it("resolves camera name from detail payload", () => {
      expect(
        formatTargetDisplayName({
          targetType: "camera",
          targetRef: "3",
          detail: { camera_name: "Front Entrance" },
        }),
      ).toBe("Front Entrance")
    })

    it("resolves camera name from camera map fallback", () => {
      const cameraMap = new Map([["3", "Front Entrance"]])
      expect(
        formatTargetDisplayName({
          targetType: "camera",
          targetRef: "3",
          detail: {},
          cameraMap,
        }),
      ).toBe("Front Entrance")
    })

    it("resolves username from detail payload", () => {
      expect(
        formatTargetDisplayName({
          targetType: "user",
          targetRef: "5",
          detail: { username: "jhon.doe" },
        }),
      ).toBe("jhon.doe")
    })

    it("resolves username from user map fallback", () => {
      const userMap = new Map([["5", "jhon.doe"]])
      expect(
        formatTargetDisplayName({
          targetType: "user",
          targetRef: "5",
          detail: {},
          userMap,
        }),
      ).toBe("jhon.doe")
    })

    it("truncates long hex/uuid identifiers", () => {
      expect(
        formatTargetDisplayName({
          targetType: "restore",
          targetRef: "a3f9e1c204b84d7a9e6f8b1c2d3e4f50",
        }),
      ).toBe("a3f9e1c2…3e4f50")
    })

    it("returns raw targetRef when no special resolution applies", () => {
      expect(
        formatTargetDisplayName({
          targetType: "export",
          targetRef: "audit",
        }),
      ).toBe("audit")
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

    it("handles empty array cleanly", () => {
      expect(formatChangedFields([])).toBe("None")
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
