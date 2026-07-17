"""Image transforms honor the charter; OCR refuses by name."""

import shutil

import pytest
from PIL import Image

from root_ext_docs import images


def test_convert_resizes_and_changes_format(sample_image, tmp_path):
    out = tmp_path / "derived" / "plot_small.jpg"
    report = images.convert(str(sample_image), str(out), max_dim=100)
    assert out.is_file()
    assert report["width_px"] == 100  # 320×200 → 100×63, long edge bound
    assert report["height_px"] <= 63
    assert Image.open(out).format == "JPEG"


def test_convert_rotates_in_right_angles(sample_image, tmp_path):
    out = tmp_path / "rotated.png"
    report = images.convert(str(sample_image), str(out), rotate_deg=90)
    assert (report["width_px"], report["height_px"]) == (200, 320)
    with pytest.raises(ValueError, match="multiple of 90"):
        images.convert(str(sample_image), str(tmp_path / "x.png"), rotate_deg=45)


def test_convert_refuses_landing_on_the_input(sample_image):
    # The charter at the write site: source is never the output.
    with pytest.raises(ValueError, match="refusing to overwrite input"):
        images.convert(str(sample_image), str(sample_image))


def test_crop_box_must_stay_inside(sample_image, tmp_path):
    out = tmp_path / "crop.png"
    report = images.crop(str(sample_image), str(out), 10, 10, 50, 40)
    assert (report["width_px"], report["height_px"]) == (50, 40)
    with pytest.raises(ValueError, match="leaves the"):
        images.crop(str(sample_image), str(tmp_path / "c2.png"), 300, 0, 50, 40)


def test_annotate_draws_marks_into_a_new_file(sample_image, tmp_path):
    out = tmp_path / "marked.png"
    report = images.annotate(
        str(sample_image), str(out), [{"x": 10, "y": 10, "w": 60, "h": 40, "label": "A"}]
    )
    assert report["marks"] == 1
    assert out.is_file()
    with pytest.raises(ValueError, match="marks is empty"):
        images.annotate(str(sample_image), str(tmp_path / "m2.png"), [])
    with pytest.raises(ValueError, match="needs integer"):
        images.annotate(str(sample_image), str(tmp_path / "m3.png"), [{"x": 1}])


def test_ocr_refuses_by_name_without_tesseract(sample_image, monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda _: None)
    with pytest.raises(RuntimeError, match="brew install tesseract"):
        images.ocr_image(str(sample_image))


@pytest.mark.skipif(shutil.which("tesseract") is None, reason="tesseract not installed")
def test_ocr_reads_rendered_text(tmp_path):
    # A live smoke against the real binary: big black text on white.
    from PIL import ImageDraw

    image = Image.new("RGB", (400, 120), "white")
    ImageDraw.Draw(image).text((20, 30), "TORQUE 42", fill="black", font_size=48)
    path = tmp_path / "label.png"
    image.save(path)
    report = images.ocr_image(str(path))
    assert "42" in report["text"]
