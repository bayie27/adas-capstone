with open("frontend/src/pages/AuditLog.tsx") as f:
    content = f.read()

audit_action_map = """const AUDIT_ACTION_MAP: Record<string, string> = {
  LOGIN_SUCCESS: "Successful Login",
  LOGIN_FAILURE: "Failed Login",
  LOGOUT: "Logged Out",
  ALERT_CONFIRM: "Confirmed Alert",
  ALERT_DISMISS: "Dismissed Alert",
  ALERT_RESOLVE: "Resolved Alert",
  ALERT_CORRECTION: "Corrected Alert",
  ALERT_SNOOZE: "Snoozed Alert",
  CAMERA_CREATE: "Created Camera",
  CAMERA_UPDATE: "Updated Camera",
  CAMERA_ENABLE: "Enabled Camera",
  CAMERA_DISABLE: "Disabled Camera",
  CAMERA_DELETE: "Deleted Camera",
  REPORT_EXPORT: "Exported Report",
  AUDIT_EXPORT: "Exported Audit Log",
  USER_CREATE: "Created User",
  USER_UPDATE: "Updated User",
  USER_ENABLE: "Enabled User",
  USER_DISABLE: "Disabled User",
  USER_ROLE_CHANGE: "Changed User Role",
  USER_PASSWORD_RESET: "Reset User Password",
  USER_PROFILE_UPDATE: "Updated User Profile",
  USER_PASSWORD_CHANGE: "Changed Password",
  ALARM_SETTINGS_UPDATE: "Updated Alarm Settings",
  BACKUP_TRIGGER: "Triggered Backup",
  RESTORE_TRIGGER: "Triggered Restore",
}
"""

start_idx = content.find("const ITEMS_PER_PAGE")
if start_idx == -1:
    start_idx = content.find("export default function AuditLog")

content = content[:start_idx] + audit_action_map + "\n" + content[start_idx:]

with open("frontend/src/pages/AuditLog.tsx", "w") as f:
    f.write(content)
