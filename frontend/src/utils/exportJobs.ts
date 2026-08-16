/**
 * The two failure_category values the worker actually assigns
 * (`services/reports/jobs.py`), mapped to a distinguishable sentence each —
 * there is no free-text detail field on ExportJobRead to render instead.
 */
export function failureMessage(category: string | null): string {
  if (category === "generation_failed") {
    return "The export failed while generating the file. Try again, or narrow the filter set."
  }
  if (category === "artifact_write_failed") {
    return "The export generated but could not be saved to disk. Try again."
  }
  return "The export failed for an unrecorded reason."
}
