"""Bounded-memory reader for the original inline-string dataset release workbooks."""

import hashlib
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile

from openpyxl.utils.datetime import MAC_EPOCH, WINDOWS_EPOCH

from devtools.database_seed import SeedError, convert_cell

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"


def file_sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _column(reference: str) -> int:
    value = 0
    for char in reference:
        if not char.isalpha():
            break
        value = value * 26 + ord(char.upper()) - 64
    return value - 1


def _value(cell):
    if cell.find(NS + "f") is not None or cell.get("t") == "e":
        raise SeedError("Workbook contains a formula or Excel error")
    kind = cell.get("t")
    if kind == "inlineStr":
        return "".join(cell.itertext())
    value = cell.find(NS + "v")
    if value is None or value.text is None:
        return None
    if kind == "b":
        return value.text == "1"
    if kind in ("str", "d"):
        return value.text
    if kind == "s":
        raise SeedError("Use the original release workbook, without shared-string conversion")
    raw = value.text
    return float(raw) if "." in raw or "e" in raw.lower() else int(raw)


class StreamWorkbook:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.sha256 = file_sha256(self.path)
        self.archive = ZipFile(self.path)
        names = self.archive.namelist()
        if len(names) != len(set(names)):
            self.close()
            raise SeedError("Workbook ZIP contains duplicate entries")
        workbook = ET.fromstring(self.archive.read("xl/workbook.xml"))
        props = workbook.find(NS + "workbookPr")
        self.epoch = (
            MAC_EPOCH
            if props is not None and props.get("date1904") in ("1", "true")
            else WINDOWS_EPOCH
        )
        relationships = ET.fromstring(self.archive.read("xl/_rels/workbook.xml.rels"))
        targets = {item.get("Id"): item.get("Target") for item in relationships}
        self.sheets = {}
        for sheet in workbook.find(NS + "sheets"):
            target = targets[sheet.get(REL)].lstrip("/")
            if not target.startswith("xl/"):
                target = "xl/" + target
            if not target.startswith("xl/worksheets/") or ".." in target.split("/"):
                raise SeedError("Unexpected workbook worksheet relationship")
            self.sheets[sheet.get("name")] = target

    def close(self):
        self.archive.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def crc(self, sheet_name):
        return self.archive.getinfo(self.sheets[sheet_name]).CRC

    def records(self, sheet_name, table):
        with self.archive.open(self.sheets[sheet_name]) as source:
            data = None
            header = True
            for event, element in ET.iterparse(source, events=("start", "end")):
                if event == "start" and element.tag == NS + "sheetData":
                    data = element
                if event != "end" or element.tag != NS + "row":
                    continue
                values = [None] * len(table.columns)
                for cell in element:
                    if cell.tag != NS + "c":
                        continue
                    index = _column(cell.get("r"))
                    if index >= len(values):
                        raise SeedError(f"Unexpected extra column in {sheet_name}")
                    values[index] = _value(cell)
                if header:
                    if values != [name for name, _ in table.columns]:
                        raise SeedError(f"Header mismatch in {sheet_name}")
                    header = False
                elif any(value is not None for value in values):
                    try:
                        yield {
                            name: convert_cell(value, kind, self.epoch)
                            for (name, kind), value in zip(table.columns, values, strict=True)
                        }
                    except (ValueError, TypeError) as error:
                        raise SeedError(f"Invalid value in {sheet_name}") from error
                element.clear()
                if data is not None:
                    data.remove(element)
            if header:
                raise SeedError(f"Missing header in {sheet_name}")
