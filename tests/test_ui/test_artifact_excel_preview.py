"""Tests for lightweight artifact previews."""

from __future__ import annotations

from pathlib import Path
import zipfile

from openharness.web import server
from openharness.web.server import _read_xlsx_preview


def test_read_xlsx_preview_reads_first_sheet(tmp_path: Path):
    xlsx = tmp_path / "preview.xlsx"
    _write_minimal_xlsx(xlsx)

    preview = _read_xlsx_preview(xlsx)

    assert preview["sheet_name"] == "Sheet1"
    assert preview["rows"][:3] == [
        ["gene", "score"],
        ["TP53", "0.91"],
        ["EGFR", "0.82"],
    ]
    assert preview["total_rows"] == 3
    assert preview["total_cols"] == 2


def test_list_session_output_file_refs_recurses_and_reports_size(tmp_path: Path, monkeypatch):
    session_root = tmp_path / "web_sessions"
    legacy_root = tmp_path / "legacy"
    sandbox_root = tmp_path / "sandbox"
    session_id = "session-1"
    output_dir = session_root / "output" / session_id
    nested = output_dir / "figures"
    nested.mkdir(parents=True)
    (output_dir / "report.html").write_text("<img src='figures/plot.png'>", encoding="utf-8")
    (nested / "plot.png").write_bytes(b"png")

    monkeypatch.setattr(server, "_project_session_dir", lambda cwd: session_root)
    monkeypatch.setattr(server, "_legacy_runtime_output_dir", lambda cwd, sid: legacy_root / sid)
    monkeypatch.setattr(server, "_sandbox_output_dir", lambda sid: sandbox_root / sid)

    refs = server._list_session_output_file_refs(str(tmp_path), session_id)

    refs_by_path = {ref["path"]: ref for ref in refs}
    assert set(refs_by_path) == {"report.html", "figures/plot.png"}
    assert refs_by_path["report.html"]["size_bytes"] == len("<img src='figures/plot.png'>")
    assert refs_by_path["figures/plot.png"]["url"] == (
        "/api/session-output/session-1/figures/plot.png"
    )
    assert server._resolve_session_output_file(
        str(tmp_path), session_id, "figures/plot.png"
    ) == nested / "plot.png"
    assert server._resolve_session_output_file(
        str(tmp_path), session_id, "../outside.txt"
    ) is None
    assert server._resolve_pdf_export_source(
        str(tmp_path),
        session_id,
        content_url="/api/session-output/session-1/report.html",
        file_path="",
    ) == output_dir / "report.html"


def _write_minimal_xlsx(path: Path) -> None:
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr(
            "[Content_Types].xml",
            """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>
</Types>""",
        )
        zf.writestr(
            "_rels/.rels",
            """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>""",
        )
        zf.writestr(
            "xl/workbook.xml",
            """<?xml version="1.0" encoding="UTF-8"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets>
    <sheet name="Sheet1" sheetId="1" r:id="rId1"/>
  </sheets>
</workbook>""",
        )
        zf.writestr(
            "xl/_rels/workbook.xml.rels",
            """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
</Relationships>""",
        )
        zf.writestr(
            "xl/sharedStrings.xml",
            """<?xml version="1.0" encoding="UTF-8"?>
<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="5" uniqueCount="5">
  <si><t>gene</t></si>
  <si><t>score</t></si>
  <si><t>TP53</t></si>
  <si><t>EGFR</t></si>
</sst>""",
        )
        zf.writestr(
            "xl/worksheets/sheet1.xml",
            """<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetData>
    <row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="s"><v>1</v></c></row>
    <row r="2"><c r="A2" t="s"><v>2</v></c><c r="B2"><v>0.91</v></c></row>
    <row r="3"><c r="A3" t="s"><v>3</v></c><c r="B3"><v>0.82</v></c></row>
  </sheetData>
</worksheet>""",
        )
