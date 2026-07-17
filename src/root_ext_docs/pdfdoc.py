"""PDF capabilities over pypdfium2 (PDFium — the Chromium renderer).

The split that matters to an agent: ``info`` says which pages carry a
text layer and which are scans; ``extract_text`` serves the former;
``pages_to_images`` + ``ocr`` serve the latter. Rendered pages land in
``derived/`` beside the source (charter) — where the workspace viewer
and the model's own image-read path pick them up.
"""

from __future__ import annotations

from pathlib import Path

from . import files, images

# Rendering bounds — a 400-page datasheet render must be asked for in
# slices, and one page must not become a gigapixel bitmap.
MAX_RENDER_PAGES = 20
MAX_OCR_PAGES = 10
MAX_DPI = 400
OCR_DPI_DEFAULT = 200


def _open(path: Path):
    import pypdfium2 as pdfium

    try:
        return pdfium.PdfDocument(str(path))
    except Exception as exc:
        raise ValueError(f"not a readable PDF: {exc}") from exc


def info(path: str) -> dict:
    """Page inventory + which pages have a text layer."""
    resolved = files.checked_path(path, files.PDF_SUFFIXES)
    pdf = _open(resolved)
    try:
        pages = []
        for index in range(len(pdf)):
            page = pdf[index]
            width_pt, height_pt = page.get_size()
            textpage = page.get_textpage()
            char_count = textpage.count_chars()
            pages.append(
                {
                    "page": index + 1,
                    "width_mm": round(width_pt * 25.4 / 72, 1),
                    "height_mm": round(height_pt * 25.4 / 72, 1),
                    "text_chars": char_count,
                    "has_text_layer": char_count > 0,
                }
            )
        scanned = [p["page"] for p in pages if not p["has_text_layer"]]
        return {
            "source": str(resolved),
            "page_count": len(pdf),
            "pages": pages,
            "pages_without_text_layer": scanned,
            "note": (
                "Pages without a text layer are scans or drawings — use "
                "ocr_pdf for their text, or pdf_pages_to_images to look at them."
                if scanned
                else "Every page carries a text layer — extract_text serves them all."
            ),
        }
    finally:
        pdf.close()


def extract_text(path: str, pages: str = "1-20") -> dict:
    """Text-layer extraction for a page range (1-based spec)."""
    resolved = files.checked_path(path, files.PDF_SUFFIXES)
    pdf = _open(resolved)
    try:
        indices = files.parse_pages(pages, len(pdf), max_pages=50)
        chunks = []
        for index in indices:
            textpage = pdf[index].get_textpage()
            chunks.append(f"## Page {index + 1}\n{textpage.get_text_range()}")
        text, truncated = files.budget_text("\n\n".join(chunks))
        return {
            "source": str(resolved),
            "pages": [i + 1 for i in indices],
            "text": text,
            "truncated": truncated,
        }
    finally:
        pdf.close()


def _render_page(pdf, index: int, dpi: int):
    bitmap = pdf[index].render(scale=dpi / 72)
    return bitmap.to_pil()


def pages_to_images(
    path: str,
    pages: str = "1-5",
    out_dir: str | None = None,
    dpi: int = 150,
    image_format: str = "png",
) -> dict:
    """Render pages to image files in derived/ (or out_dir)."""
    resolved = files.checked_path(path, files.PDF_SUFFIXES)
    if not 30 <= dpi <= MAX_DPI:
        raise ValueError(f"dpi must be 30–{MAX_DPI}")
    if image_format not in ("png", "jpeg", "jpg"):
        raise ValueError("image_format must be png or jpeg")
    pdf = _open(resolved)
    try:
        indices = files.parse_pages(pages, len(pdf), MAX_RENDER_PAGES)
        target = files.derived_dir(resolved, out_dir)
        suffix = "jpg" if image_format in ("jpeg", "jpg") else "png"
        written = []
        for index in indices:
            out_path = target / f"{resolved.stem}_p{index + 1}.{suffix}"
            files.refuse_collision(out_path, (resolved,))
            image = _render_page(pdf, index, dpi)
            if suffix == "jpg":
                image = image.convert("RGB")
            image.save(out_path)
            written.append(
                {
                    "page": index + 1,
                    "path": str(out_path),
                    "width_px": image.width,
                    "height_px": image.height,
                }
            )
        return {"source": str(resolved), "dpi": dpi, "written": written}
    finally:
        pdf.close()


def ocr(path: str, pages: str = "1-5", dpi: int = OCR_DPI_DEFAULT, lang: str = "eng") -> dict:
    """OCR scanned pages: render each page, run tesseract, return text.
    Refuses by name when tesseract is not installed."""
    resolved = files.checked_path(path, files.PDF_SUFFIXES)
    if not 30 <= dpi <= MAX_DPI:
        raise ValueError(f"dpi must be 30–{MAX_DPI}")
    images.require_tesseract()
    pdf = _open(resolved)
    try:
        indices = files.parse_pages(pages, len(pdf), MAX_OCR_PAGES)
        chunks = []
        for index in indices:
            rendered = _render_page(pdf, index, dpi)
            chunks.append(
                f"## Page {index + 1}\n{images.tesseract_image(rendered, lang)}"
            )
        text, truncated = files.budget_text("\n\n".join(chunks))
        return {
            "source": str(resolved),
            "pages": [i + 1 for i in indices],
            "dpi": dpi,
            "lang": lang,
            "text": text,
            "truncated": truncated,
        }
    finally:
        pdf.close()
