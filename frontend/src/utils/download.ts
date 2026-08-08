import type { AxiosResponse } from "axios"

function extractFilename(contentDisposition: string | undefined, fallback: string) {
  if (!contentDisposition) {
    return fallback
  }

  const utf8Match = contentDisposition.match(/filename\*=UTF-8''([^;]+)/i)

  if (utf8Match?.[1]) {
    return decodeURIComponent(utf8Match[1])
  }

  const asciiMatch = contentDisposition.match(/filename="?([^"]+)"?/i)

  if (asciiMatch?.[1]) {
    return asciiMatch[1]
  }

  return fallback
}

export function downloadBlobResponse(response: AxiosResponse<Blob>, fallbackFilename: string) {
  const filename = extractFilename(response.headers["content-disposition"], fallbackFilename)

  const blobUrl = window.URL.createObjectURL(response.data)
  const link = document.createElement("a")

  link.href = blobUrl
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  window.URL.revokeObjectURL(blobUrl)
}
