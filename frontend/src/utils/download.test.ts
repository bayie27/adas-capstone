import type { AxiosResponse } from "axios"
import { afterEach, describe, expect, it, vi } from "vitest"

import { downloadBlobResponse } from "./download"

const originalCreateObjectUrl = Object.getOwnPropertyDescriptor(window.URL, "createObjectURL")
const originalRevokeObjectUrl = Object.getOwnPropertyDescriptor(window.URL, "revokeObjectURL")

function restoreUrlMethod(
  name: "createObjectURL" | "revokeObjectURL",
  descriptor?: PropertyDescriptor,
) {
  if (descriptor) {
    Object.defineProperty(window.URL, name, descriptor)
  } else {
    Reflect.deleteProperty(window.URL, name)
  }
}

function response(contentDisposition?: string): AxiosResponse<Blob> {
  return {
    data: new Blob(["export"]),
    status: 200,
    statusText: "OK",
    headers: contentDisposition ? { "content-disposition": contentDisposition } : {},
    config: { headers: {} } as AxiosResponse<Blob>["config"],
  }
}

describe("downloadBlobResponse", () => {
  afterEach(() => {
    vi.restoreAllMocks()
    restoreUrlMethod("createObjectURL", originalCreateObjectUrl)
    restoreUrlMethod("revokeObjectURL", originalRevokeObjectUrl)
  })

  it("downloads the Blob with the server-provided filename and revokes its URL", () => {
    const createObjectUrl = vi.fn(() => "blob:incident-export")
    const revokeObjectUrl = vi.fn()
    let clickedDownload = ""
    let clickedHref = ""

    Object.defineProperty(window.URL, "createObjectURL", {
      configurable: true,
      value: createObjectUrl,
    })
    Object.defineProperty(window.URL, "revokeObjectURL", {
      configurable: true,
      value: revokeObjectUrl,
    })
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (
      this: HTMLAnchorElement,
    ) {
      clickedDownload = this.download
      clickedHref = this.href
    })

    downloadBlobResponse(
      response('attachment; filename="adas_incident_export.pdf"'),
      "fallback.pdf",
    )

    expect(clickedDownload).toBe("adas_incident_export.pdf")
    expect(clickedHref).toBe("blob:incident-export")
    expect(createObjectUrl).toHaveBeenCalledTimes(1)
    expect(revokeObjectUrl).toHaveBeenCalledWith("blob:incident-export")
    expect(document.querySelector('a[download="adas_incident_export.pdf"]')).toBeNull()
  })

  it("uses the fallback filename when Content-Disposition is absent", () => {
    Object.defineProperty(window.URL, "createObjectURL", {
      configurable: true,
      value: vi.fn(() => "blob:fallback"),
    })
    Object.defineProperty(window.URL, "revokeObjectURL", {
      configurable: true,
      value: vi.fn(),
    })
    let clickedDownload = ""
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (
      this: HTMLAnchorElement,
    ) {
      clickedDownload = this.download
    })

    downloadBlobResponse(response(), "adas_incident_export.csv")

    expect(clickedDownload).toBe("adas_incident_export.csv")
  })
})
