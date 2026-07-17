"""PDF capabilities against a hand-assembled, pdfium-validated PDF."""

import pytest

from root_ext_docs import files, pdfdoc


def test_info_names_text_and_scan_pages(pdf_two_pages):
    report = pdfdoc.info(str(pdf_two_pages))
    assert report["page_count"] == 2
    assert report["pages"][0]["has_text_layer"] is True
    assert report["pages"][1]["has_text_layer"] is False
    assert report["pages_without_text_layer"] == [2]
    assert "ocr_pdf" in report["note"]


def test_extract_text_reads_the_text_layer(pdf_two_pages):
    report = pdfdoc.extract_text(str(pdf_two_pages), pages="1")
    assert "Torque spec 42 Nm" in report["text"]
    assert report["pages"] == [1]
    assert report["truncated"] is False


def test_pages_to_images_lands_in_derived(pdf_two_pages):
    report = pdfdoc.pages_to_images(str(pdf_two_pages), pages="1-2", dpi=72)
    written = report["written"]
    assert [w["page"] for w in written] == [1, 2]
    for entry in written:
        assert "/derived/" in entry["path"]
        assert entry["path"].endswith((".png"))
        assert entry["width_px"] > 100
    # 612×792pt at 72 dpi ≈ 612×792 px
    assert abs(written[0]["width_px"] - 612) <= 2


def test_render_dpi_and_format_are_bounded(pdf_two_pages):
    with pytest.raises(ValueError, match="dpi"):
        pdfdoc.pages_to_images(str(pdf_two_pages), dpi=1200)
    with pytest.raises(ValueError, match="image_format"):
        pdfdoc.pages_to_images(str(pdf_two_pages), image_format="tiff")


def test_page_spec_grammar_and_caps():
    assert files.parse_pages("1-3", 10, 20) == [0, 1, 2]
    assert files.parse_pages("2,4,9-10", 10, 20) == [1, 3, 8, 9]
    with pytest.raises(ValueError, match="backwards"):
        files.parse_pages("5-2", 10, 20)
    with pytest.raises(ValueError, match="selects nothing"):
        files.parse_pages("99", 10, 20)
    with pytest.raises(ValueError, match="cap is 3"):
        files.parse_pages("1-4", 10, 3)


def test_not_a_pdf_is_a_named_error(tmp_path):
    fake = tmp_path / "fake.pdf"
    fake.write_bytes(b"not a pdf at all")
    with pytest.raises(ValueError, match="not a readable PDF"):
        pdfdoc.info(str(fake))
