"""Image capabilities: Pillow transforms + the tesseract OCR seam.

OCR needs the system tesseract binary and **refuses by name** without
it (the zoo.py posture: no silent degradation) — the refusal carries
the install command. Transforms write derived artifacts only; every
write site runs the collision refusal.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from . import files

MAX_DIM = 10_000
OCR_TIMEOUT_S = 60

SAVE_FORMATS = {
    ".png": "PNG",
    ".jpg": "JPEG",
    ".jpeg": "JPEG",
    ".webp": "WEBP",
    ".gif": "GIF",
    ".bmp": "BMP",
    ".tif": "TIFF",
    ".tiff": "TIFF",
}


def _load(path: Path):
    from PIL import Image

    image = Image.open(path)
    image.load()
    return image


def require_tesseract() -> str:
    binary = shutil.which("tesseract")
    if not binary:
        raise RuntimeError(
            "OCR needs the tesseract binary and it is not installed — "
            "`brew install tesseract` (macOS) or `apt install tesseract-ocr` "
            "(Linux), then retry. Refusing by name rather than failing "
            "somewhere vague."
        )
    return binary


def tesseract_image(image, lang: str) -> str:
    """Run tesseract over a PIL image via a temp PNG; returns the text."""
    binary = require_tesseract()
    if not lang.replace("+", "").isalnum():
        raise ValueError(f"suspicious tesseract lang {lang!r}")
    with tempfile.TemporaryDirectory(prefix="root-ext-docs-ocr-") as tmp:
        source = Path(tmp) / "page.png"
        image.save(source)
        run = subprocess.run(
            [binary, str(source), "stdout", "-l", lang],
            capture_output=True,
            text=True,
            timeout=OCR_TIMEOUT_S,
        )
    if run.returncode != 0:
        raise RuntimeError(f"tesseract failed: {run.stderr.strip()[:400]}")
    return run.stdout.strip()


def ocr_image(path: str, lang: str = "eng") -> dict:
    """OCR one image file — text only, nothing written."""
    resolved = files.checked_path(path, files.IMAGE_SUFFIXES)
    require_tesseract()
    text, truncated = files.budget_text(tesseract_image(_load(resolved), lang))
    return {"source": str(resolved), "lang": lang, "text": text, "truncated": truncated}


def _save(image, out_path: Path, quality: int) -> dict:
    save_format = SAVE_FORMATS.get(out_path.suffix.lower())
    if not save_format:
        raise ValueError(
            f"unsupported output suffix {out_path.suffix!r} — one of "
            f"{sorted(SAVE_FORMATS)}"
        )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if save_format == "JPEG" and image.mode not in ("RGB", "L"):
        image = image.convert("RGB")
    image.save(out_path, format=save_format, quality=quality)
    return {
        "path": str(out_path),
        "width_px": image.width,
        "height_px": image.height,
        "bytes": out_path.stat().st_size,
    }


def convert(
    path: str,
    out_path: str,
    max_dim: int | None = None,
    rotate_deg: int = 0,
    quality: int = 90,
) -> dict:
    """Convert / resize / rotate into a NEW file (suffix picks format)."""
    resolved = files.checked_path(path, files.IMAGE_SUFFIXES)
    target = Path(out_path).expanduser()
    files.refuse_collision(target, (resolved,))
    if max_dim is not None and not 16 <= max_dim <= MAX_DIM:
        raise ValueError(f"max_dim must be 16–{MAX_DIM}")
    if rotate_deg % 90 != 0:
        raise ValueError("rotate_deg must be a multiple of 90")
    image = _load(resolved)
    if rotate_deg % 360:
        image = image.rotate(-(rotate_deg % 360), expand=True)
    if max_dim is not None and max(image.size) > max_dim:
        image.thumbnail((max_dim, max_dim))
    report = _save(image, target, quality)
    return {"source": str(resolved), **report}


def crop(path: str, out_path: str, x: int, y: int, width: int, height: int) -> dict:
    """Crop a pixel box into a NEW file."""
    resolved = files.checked_path(path, files.IMAGE_SUFFIXES)
    target = Path(out_path).expanduser()
    files.refuse_collision(target, (resolved,))
    image = _load(resolved)
    if width <= 0 or height <= 0:
        raise ValueError("width and height must be positive")
    if x < 0 or y < 0 or x + width > image.width or y + height > image.height:
        raise ValueError(
            f"box {x},{y} {width}×{height} leaves the {image.width}×{image.height} image"
        )
    report = _save(image.crop((x, y, x + width, y + height)), target, quality=90)
    return {"source": str(resolved), **report}


def annotate(path: str, out_path: str, marks: list[dict]) -> dict:
    """Draw labelled rectangles into a NEW file — for pointing at
    regions of a drawing or screenshot."""
    from PIL import ImageDraw

    resolved = files.checked_path(path, files.IMAGE_SUFFIXES)
    target = Path(out_path).expanduser()
    files.refuse_collision(target, (resolved,))
    if not marks:
        raise ValueError("marks is empty — nothing to annotate")
    if len(marks) > 50:
        raise ValueError("more than 50 marks — annotate in passes")
    image = _load(resolved).convert("RGB")
    draw = ImageDraw.Draw(image)
    stroke = max(2, round(min(image.size) / 400))
    color = (200, 40, 40)
    for index, mark in enumerate(marks):
        try:
            x, y = int(mark["x"]), int(mark["y"])
            w, h = int(mark["w"]), int(mark["h"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"mark #{index + 1} needs integer x, y, w, h") from exc
        draw.rectangle([x, y, x + w, y + h], outline=color, width=stroke)
        label = str(mark.get("label", "")).strip()
        if label:
            draw.text((x + stroke + 2, y + stroke + 2), label, fill=color)
    report = _save(image, target, quality=90)
    return {"source": str(resolved), "marks": len(marks), **report}
