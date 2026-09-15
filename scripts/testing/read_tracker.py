"""Read tracker case records without modifying the workbook."""

import argparse
import json
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def read_cases(path: Path) -> list[dict]:
    with zipfile.ZipFile(path) as archive:
        strings = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            strings = ["".join(x.itertext()) for x in root]
        rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        targets = {r.attrib["Id"]: r.attrib["Target"] for r in rels}
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        cases = []
        for sheet in workbook.findall("s:sheets/s:sheet", NS):
            rid = sheet.attrib[
                "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
            ]
            target = targets[rid]
            member = target.lstrip("/") if target.startswith("/") else "xl/" + target
            root = ET.fromstring(archive.read(member))
            for row in root.findall("s:sheetData/s:row", NS):
                values = {}
                for cell in row.findall("s:c", NS):
                    column = "".join(c for c in cell.attrib["r"] if c.isalpha())
                    value = cell.find("s:v", NS)
                    if cell.attrib.get("t") == "s" and value is not None:
                        text = strings[int(value.text)]
                    elif cell.attrib.get("t") == "inlineStr":
                        text = "".join(t.text or "" for t in cell.findall(".//s:t", NS))
                    else:
                        text = value.text if value is not None else ""
                    values[column] = text
                if values.get("A", "").startswith(("TC-", "AI-VAL-")):
                    cases.append(
                        {
                            "sheet": sheet.attrib["name"],
                            "row": int(row.attrib["r"]),
                            "id": values["A"],
                            "objective": values.get("B", ""),
                            "scenario": values.get("C", ""),
                            "steps": values.get("D", ""),
                            "acceptance": values.get("E", ""),
                            "date": values.get("F", ""),
                            "result": values.get("G", ""),
                            "notes": values.get("H", ""),
                            "evidence": values.get("I", ""),
                            "defect": values.get("J", ""),
                        }
                    )
        return cases


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workbook", type=Path)
    parser.add_argument("--prefix", default="")
    args = parser.parse_args()
    print(
        json.dumps(
            [c for c in read_cases(args.workbook) if c["id"].startswith(args.prefix)],
            indent=2,
        )
    )
