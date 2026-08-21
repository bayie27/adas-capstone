import re

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

content = re.sub(
    r'const USERS_QUERY_KEY = \["users"\] as const',
    audit_action_map + '\nconst USERS_QUERY_KEY = ["users"] as const',
    content,
)
if audit_action_map not in content:
    # try putting it right after the imports
    start_idx = content.find("const AUDIT_QUERY_KEY")
    if start_idx != -1:
        content = content[:start_idx] + audit_action_map + "\n" + content[start_idx:]
    else:
        print("Could not find where to place AUDIT_ACTION_MAP")

old_action_cell = (
    '<TableCell className="font-mono text-caption">{entry.action}</TableCell>'
)
new_action_cell = (
    "<TableCell>{AUDIT_ACTION_MAP[entry.action] || entry.action}</TableCell>"
)
content = content.replace(old_action_cell, new_action_cell)

old_expanded_view = """            <div className="grid grid-cols-1 gap-4 py-2 md:grid-cols-[1fr_auto]">
              <pre className="overflow-x-auto rounded-md border border-stroke bg-surface-1 p-3 text-caption text-fg-body">
                {entry.detail ? JSON.stringify(entry.detail, null, 2) : "No detail recorded."}
              </pre>
              <div className="space-y-1 text-caption text-fg-muted">
                <div>
                  <span className="font-semibold text-fg-body">Request ID:</span>{" "}
                  {entry.request_id ?? "-"}
                </div>
                <div>
                  <span className="font-semibold text-fg-body">Source IP:</span>{" "}
                  {entry.source_ip ?? "-"}
                </div>
              </div>
            </div>"""

new_expanded_view = """            <div className="grid grid-cols-1 gap-6 py-2 md:grid-cols-[1fr_auto]">
              <div>
                <h4 className="mb-2 text-xs font-semibold text-fg-muted">Action Details</h4>
                {entry.detail && Object.keys(entry.detail).length > 0 ? (
                  <div className="flex flex-col gap-1.5 text-sm">
                    {Object.entries(entry.detail).map(([key, value]) => (
                      <div key={key} className="flex gap-2">
                        <span className="text-fg-muted capitalize">
                          {key.replace(/_/g, " ")}:
                        </span>
                        <span className="font-medium text-fg">{String(value)}</span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-sm text-fg-muted">No detail recorded.</div>
                )}
              </div>
              <div className="space-y-1 text-caption text-fg-muted">
                <h4 className="mb-2 text-xs font-semibold text-fg-muted">Diagnostic Data</h4>
                <div>
                  Request ID: {entry.request_id ?? "-"}
                </div>
                <div>
                  Source IP: {entry.source_ip ?? "-"}
                </div>
              </div>
            </div>"""

content = content.replace(old_expanded_view, new_expanded_view)

with open("frontend/src/pages/AuditLog.tsx", "w") as f:
    f.write(content)
