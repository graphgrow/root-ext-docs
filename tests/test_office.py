"""Office extraction keeps structure: headings, tables, notes."""

from root_ext_docs import office


def test_docx_keeps_headings_and_tables(sample_docx):
    report = office.docx_extract(str(sample_docx))
    assert "# Interface Control" in report["text"]
    assert "four M4 bolts" in report["text"]
    assert "| Bolt | Torque |" in report["text"]
    assert "| M4 | 2.9 Nm |" in report["text"]
    assert report["tables"] == 1
    assert report["truncated"] is False


def test_pptx_keeps_slides_and_notes(sample_pptx):
    report = office.pptx_extract(str(sample_pptx))
    assert "## Slide 1 — Design Review" in report["text"]
    assert "Mass budget holds at 1.2 kg" in report["text"]
    assert "> Notes: Confirm with thermal team" in report["text"]
    assert report["slides"] == 1
