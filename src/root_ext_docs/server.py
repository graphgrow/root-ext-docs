"""root-ext-docs — the document-engineering MCP tool server.

Serves over MCP stdio for any host; in ROOT Workspace it connects
through Settings → Connected tools and every call rides the runtime's
governance (the client classifies tools from the annotations below,
fail-safe, and gates accordingly).

Annotation contract (matches the classifier in the ROOT client):
- Read tools: ``readOnlyHint=True, openWorldHint=False`` — they read
  documents and compute, nothing else. OCR runs the local tesseract
  binary and refuses by name when it is absent; nothing reaches the
  network.
- Derived-write tools: ``readOnlyHint=False, openWorldHint=False,
  destructiveHint=False`` — the closed-world write class, gated like
  any write. They create derived artifacts; the charter forbids them
  from landing on an input.

Charter, binding for this package: **extract and derive, never mutate
sources.** No tool overwrites, deletes, moves, or edits a user's file
in place; write tools refuse output paths that collide with inputs and
default to ``derived/`` beside the source — where the workspace's own
viewers (and the model's image-read path) pick the artifacts up.

Heavy imports stay inside call bodies: the server announces its tools
without paying pdfium/Pillow import costs, so the connect-form doctor
stays fast.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

mcp = FastMCP("doc-eng")

_READ = ToolAnnotations(readOnlyHint=True, openWorldHint=False)
_DERIVED_WRITE = ToolAnnotations(
    readOnlyHint=False, openWorldHint=False, destructiveHint=False, idempotentHint=True
)


# ── pdf ──────────────────────────────────────────────────────────────


@mcp.tool(annotations=_READ)
def pdf_info(path: str) -> dict:
    """Inventory a PDF before reading it: page count, per-page size
    (mm), and — the part that matters — which pages carry a text layer
    and which are scans/drawings. Use it to decide between
    pdf_extract_text (text layer), ocr_pdf (scans), and
    pdf_pages_to_images (look at drawings). Reads the file on this
    machine; nothing leaves it."""
    from . import pdfdoc

    return pdfdoc.info(path)


@mcp.tool(annotations=_READ)
def pdf_extract_text(path: str, pages: str = "1-20") -> dict:
    """Extract the text layer of a page range (1-based: "3", "1-5",
    "2,4,9-11"; up to 50 pages per call). Page-ranged so a 400-page
    standard is read in slices instead of one blind gulp. Returns
    nothing useful for scanned pages — pdf_info names those, ocr_pdf
    reads them. Bounded; truncation is marked."""
    from . import pdfdoc

    return pdfdoc.extract_text(path, pages)


@mcp.tool(annotations=_DERIVED_WRITE)
def pdf_pages_to_images(
    path: str,
    pages: str = "1-5",
    out_dir: str | None = None,
    dpi: int = 150,
    image_format: str = "png",
) -> dict:
    """Render PDF pages to PNG/JPEG files (up to 20 pages per call,
    dpi 30–400) in out_dir — default `derived/` beside the source,
    never on top of it (charter). The rendered pages are ordinary
    images: open them in the workspace, or read them with fs.read to
    LOOK at a drawing-heavy page the text extractor can't serve."""
    from . import pdfdoc

    return pdfdoc.pages_to_images(path, pages, out_dir, dpi, image_format)


@mcp.tool(annotations=_READ)
def ocr_pdf(path: str, pages: str = "1-5", dpi: int = 200, lang: str = "eng") -> dict:
    """OCR scanned PDF pages (up to 10 per call): renders each page and
    runs the LOCAL tesseract binary — needs tesseract installed
    (`brew install tesseract`) and refuses by name without it; nothing
    reaches the network. Use pdf_info first to find which pages need
    OCR. OCR misreads numbers — verify critical values against the
    rendered page."""
    from . import pdfdoc

    return pdfdoc.ocr(path, pages, dpi, lang)


# ── office documents ─────────────────────────────────────────────────


@mcp.tool(annotations=_READ)
def docx_extract(path: str) -> dict:
    """Extract a DOCX in document order with structure kept: headings
    as markdown levels, paragraphs, and tables as markdown tables — so
    you can cite the table under a section instead of fishing in text
    soup. Bounded; truncation is marked."""
    from . import office

    return office.docx_extract(path)


@mcp.tool(annotations=_READ)
def pptx_extract(path: str) -> dict:
    """Extract a PPTX slide by slide: title, body text, tables, and
    speaker notes (quoted, marked as notes). Bounded; truncation is
    marked."""
    from . import office

    return office.pptx_extract(path)


# ── images ───────────────────────────────────────────────────────────


@mcp.tool(annotations=_READ)
def ocr_image(path: str, lang: str = "eng") -> dict:
    """OCR one image (png/jpg/gif/webp/bmp/tiff) with the LOCAL
    tesseract binary — needs tesseract installed and refuses by name
    without it; nothing reaches the network. OCR misreads numbers —
    verify critical values by looking at the image itself."""
    from . import images

    return images.ocr_image(path, lang)


@mcp.tool(annotations=_DERIVED_WRITE)
def image_convert(
    path: str,
    out_path: str,
    max_dim: int | None = None,
    rotate_deg: int = 0,
    quality: int = 90,
) -> dict:
    """Convert/resize/rotate an image into a NEW file — format by
    out_path suffix (png/jpg/webp/gif/bmp/tiff), optional max_dim
    bound on the long edge, rotation in 90° steps. Refuses an out_path
    that collides with the input (charter)."""
    from . import images

    return images.convert(path, out_path, max_dim, rotate_deg, quality)


@mcp.tool(annotations=_DERIVED_WRITE)
def image_crop(path: str, out_path: str, x: int, y: int, width: int, height: int) -> dict:
    """Crop a pixel box (x, y, width, height from the top-left) into a
    NEW file — e.g. isolate one view of a drawing before OCR or a
    close look. Refuses a box that leaves the image and an out_path
    that collides with the input (charter)."""
    from . import images

    return images.crop(path, out_path, x, y, width, height)


@mcp.tool(annotations=_DERIVED_WRITE)
def image_annotate(path: str, out_path: str, marks: list[dict]) -> dict:
    """Draw labelled rectangles on a copy of an image (up to 50 marks,
    each {x, y, w, h, label?}) — point at regions of a drawing or
    screenshot when words alone are ambiguous. Writes a NEW file;
    refuses an out_path that collides with the input (charter)."""
    from . import images

    return images.annotate(path, out_path, marks)


# ── archives ─────────────────────────────────────────────────────────


@mcp.tool(annotations=_READ)
def archive_list(path: str) -> dict:
    """List a zip/tar archive's entries (name, size, kind) plus the
    total uncompressed size — look before extracting. Bounded at 1000
    entries; truncation is marked."""
    from . import archives

    return archives.list_archive(path)


@mcp.tool(annotations=_DERIVED_WRITE)
def archive_extract(
    path: str, out_dir: str | None = None, members: list[str] | None = None
) -> dict:
    """Extract an archive (or just `members`) into out_dir — default
    `derived/<name>/` beside it, and NEVER anywhere else: absolute
    paths, `..` members, and links are refused by name (zip-slip),
    entry count and total size are capped so a zip bomb is an error,
    not an outage."""
    from . import archives

    return archives.extract(path, out_dir, members)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
