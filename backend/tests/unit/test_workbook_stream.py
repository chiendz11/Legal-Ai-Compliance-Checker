"""Preserve PDF glyphs and literal OOXML escape sequences through seed import."""

import json
from zipfile import ZipFile

from devtools.database_schema import Table
from devtools.workbook_stream import StreamWorkbook


def test_stream_reader_decodes_ooxml_once_without_changing_source_offsets(tmp_path):
    path = tmp_path / "source.xlsx"
    ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    rel = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    text = "Bàn giao\x06 căn hộ; mã gốc _x0041_."
    payload = json.dumps({"quote": text}, ensure_ascii=False)
    # Encode a PDF control glyph; protect the literal escape's underscore.
    encoded = "Bàn giao_x0006_ căn hộ; mã gốc _x005F_x0041_."
    encoded_json = payload.replace("_x0041_", "_x005F_x0041_")
    with ZipFile(path, "w") as archive:
        archive.writestr(
            "xl/workbook.xml",
            f'<workbook xmlns="{ns}" xmlns:r="{rel}"><sheets>'
            '<sheet name="source" sheetId="1" r:id="rId1"/></sheets></workbook>',
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            '<Relationships><Relationship Id="rId1" '
            'Target="worksheets/sheet1.xml"/></Relationships>',
        )
        archive.writestr(
            "xl/worksheets/sheet1.xml",
            f'<worksheet xmlns="{ns}"><sheetData><row r="1">'
            '<c r="A1" t="inlineStr"><is><t>text</t></is></c>'
            '<c r="B1" t="inlineStr"><is><t>payload</t></is></c></row>'
            '<row r="2"><c r="A2" t="inlineStr"><is><t>'
            + encoded
            + '</t></is></c><c r="B2" t="inlineStr"><is><t>'
            + encoded_json
            + "</t></is></c></row></sheetData></worksheet>",
        )
    table = Table("runtime", "source", (("text", "TEXT"), ("payload", "JSONB")))
    with StreamWorkbook(path) as workbook:
        result = list(workbook.records("source", table))
    assert result == [{"text": text, "payload": {"quote": text}}]
    start = text.index("căn hộ")
    assert result[0]["text"][start : start + len("căn hộ")] == "căn hộ"
