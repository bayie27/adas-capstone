import axios from "axios"

type ValidationIssue = {
  msg?: string
}

type ApiErrorBody = {
  detail?: string | ValidationIssue[]
}

export function getApiErrorMessage(error: unknown, fallback: string) {
  if (!axios.isAxiosError<ApiErrorBody>(error)) {
    return fallback
  }

  const detail = error.response?.data?.detail

  if (typeof detail === "string" && detail.trim()) {
    return detail
  }

  if (Array.isArray(detail)) {
    const validationMessage = detail
      .map((issue) => issue.msg?.trim())
      .filter((message): message is string => Boolean(message))
      .join(" ")

    if (validationMessage) {
      return validationMessage
    }
  }

  return fallback
}
