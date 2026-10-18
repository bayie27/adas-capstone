import { expect, test } from "@playwright/test"

import { totpCode } from "./support/mfa"

test("independent TOTP helper matches RFC 6238 SHA-1 vectors", () => {
  const publishedSecret = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"
  expect(totpCode(publishedSecret, 59, 8)).toBe("94287082")
  expect(totpCode(publishedSecret, 1_111_111_109, 8)).toBe("07081804")
})
