import fs from "node:fs/promises"
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool"

const path = process.argv[2]
const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(path))
console.log(
  (
    await workbook.inspect({
      kind: "table",
      range: "'Security Testing'!A1:J3",
      include: "values,formulas",
      tableMaxRows: 3,
      tableMaxCols: 10,
    })
  ).ndjson,
)
const preview = await workbook.render({
  sheetName: "Security Testing",
  range: "A1:J3",
  scale: 1,
  format: "png",
})
await fs.mkdir("var/test-evidence/previews", { recursive: true })
await fs.writeFile(
  "var/test-evidence/previews/security-before.png",
  new Uint8Array(await preview.arrayBuffer()),
)
