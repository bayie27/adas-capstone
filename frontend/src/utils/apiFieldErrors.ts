import { getApiError } from "@/api/client"

/**
 * Pulls one field's message out of a 422's `errors[]`.
 *
 * `errors[]` carries FastAPI's raw Pydantic shape (`{loc, msg, type}` — see
 * `be_plan/01_CONTRACTS.md` §"Errors"), not the `{field, message}` shape
 * `ApiValidationError` optimistically names; `loc` nests the field under a
 * location prefix (e.g. `["body", "new_password"]`), so this matches on its
 * last segment. Returns undefined for anything that isn't a 422 or doesn't
 * name this field — callers fall back to `getApiErrorMessage` for those.
 */
export function getFieldValidationMessage(error: unknown, field: string): string | undefined {
  const parsed = getApiError(error)
  if (!parsed || parsed.status !== 422) return undefined

  for (const issue of parsed.errors) {
    const loc = issue.loc
    const msg = issue.msg
    if (Array.isArray(loc) && loc[loc.length - 1] === field && typeof msg === "string") {
      return msg
    }
  }

  return undefined
}
