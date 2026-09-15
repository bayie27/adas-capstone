import fs from 'node:fs/promises'
import { FileBlob, SpreadsheetFile } from '@oai/artifact-tool'

const [source, target, evidence] = process.argv.slice(2)
const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(source))
const sheet = workbook.worksheets.getItem('Security Testing')
if (sheet.getRange('A2').values[0][0] !== 'TC-SEC-001') throw new Error('Unexpected case row')
if (sheet.getRange('G2').values[0][0]) throw new Error('Refusing to overwrite an executed case')
sheet.getRange('D2').values = [['From repo root: uv run python scripts/testing/run_tracker.py --case TC-SEC-001. Disposable fixtures compare three login denials and audit rows. Timing uses fixture password cost.']]
sheet.getRange('F2').values = [[new Date('2026-09-15T00:00:00Z')]]
sheet.getRange('F2').setNumberFormat('yyyy-mm-dd')
sheet.getRange('G2').values = [['Pass']]
sheet.getRange('H2').values = [['Three identical 401 denials and three denied LOGIN_FAILURE audit rows. Timings: 156.619, 136.238, 162.615 ms at fixture cost only. Local evidence, not uploaded.']]
sheet.getRange('I2').values = [[evidence]]
sheet.getRange('J2').values = [['No new defect. See docs/validation/ADAS_TESTING_GUIDE.md for reproduction and exclusions.']]
sheet.getRange('D14').values = [['From repo root: uv run python scripts/testing/run_tracker.py --case TC-SEC-013. Selector includes TestHostileAndDegenerateInput, omitted in the prior binding. Existing result and evidence retained pending verification.']]
const exclusions = { 'System E2E Testing': ['TC-SYS-019'], 'AI Model Validation': null, 'Backup & Recovery': null, 'Performance & Load Testing': ['TC-PERF-002'], 'Security Testing': ['TC-SEC-015', 'TC-SEC-027'] }
const edits = [{ sheet: sheet.name, range: 'D2:J2' }, { sheet: sheet.name, range: 'D14' }]
for (const [name, ids] of Object.entries(exclusions)) {
  const tab = workbook.worksheets.getItem(name)
  const values = tab.getUsedRange().values
  for (let index = 1; index < values.length; index++) {
    const row = values[index]
    if (!String(row[0] || '').match(/^(TC-|AI-VAL-)/) || row[6] || (ids && !ids.includes(row[0]))) continue
    const reason = row[0] === 'TC-PERF-002' ? 'Skipped this cycle by user instruction. Engine FPS_BAND_MIN is unchanged and does not match the requested 5 to 15 target.' : 'Skipped this cycle by user instruction. No AI validation or backup and restore testing was executed. Existing results are preserved.'
    const address = `H${index + 1}`
    tab.getRange(address).values = [[row[7] ? `${row[7]}\n${reason}` : reason]]
    edits.push({ sheet: name, range: address })
  }
}
workbook.recalculate()
await fs.writeFile('var/test-evidence/tracker-edits.json', JSON.stringify(edits, null, 2))
await fs.writeFile('var/test-evidence/previews/security-after.png', new Uint8Array(await (await workbook.render({ sheetName: 'Security Testing', range: 'A1:J3', scale: 1, format: 'png' })).arrayBuffer()))
await (await SpreadsheetFile.exportXlsx(workbook)).save(target)
console.log(`Staged ${edits.length} targeted ranges`)
