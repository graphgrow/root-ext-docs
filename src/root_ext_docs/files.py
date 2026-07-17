"""Shared file discipline — the charter, in code.

**Extract and derive, never mutate sources** (the root-ext-cad charter
shape): every write tool refuses an output path that collides with an
input, derived artifacts default to a ``derived/`` directory beside the
source, and everything returned as text is budgeted with truncation
marked — a tool must never let one file flood the prompt.
"""

from __future__ import annotations

from pathlib import Path

# Per-call budget of text handed back to the model.
MAX_TEXT_CHARS = 50_000
# Refuse absurd inputs before parsing.
MAX_SOURCE_BYTES = 200_000_000

PDF_SUFFIXES = (".pdf",)
DOCX_SUFFIXES = (".docx",)
PPTX_SUFFIXES = (".pptx",)
IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tif", ".tiff")
ARCHIVE_SUFFIXES = (".zip", ".tar", ".tgz", ".gz", ".tar.gz", ".tar.bz2", ".tar.xz")


def checked_path(path: str, suffixes: tuple[str, ...]) -> Path:
    resolved = Path(path).expanduser()
    if not resolved.is_file():
        raise FileNotFoundError(f"no file at {resolved}")
    name = resolved.name.lower()
    if not any(name.endswith(suffix) for suffix in suffixes):
        raise ValueError(f"expected one of {suffixes}, got {resolved.suffix!r}")
    if resolved.stat().st_size > MAX_SOURCE_BYTES:
        raise ValueError("file exceeds the 200 MB parse ceiling")
    return resolved


def refuse_collision(out_path: Path, inputs: tuple[Path, ...]) -> None:
    """The charter, at the write site: derived artifacts never land on
    top of an input. Compares resolved paths."""
    resolved_out = out_path.expanduser().resolve()
    for source in inputs:
        if resolved_out == source.expanduser().resolve():
            raise ValueError(
                f"refusing to overwrite input {source} — derived artifacts "
                "go to a distinct output path (charter: extract and derive, "
                "never mutate sources)"
            )


def derived_dir(source: Path, out_dir: str | None) -> Path:
    """Resolve (and create) the output directory: the caller's out_dir,
    or ``derived/`` beside the source — never a path that IS the source's
    own file."""
    target = (
        Path(out_dir).expanduser() if out_dir else source.parent / "derived"
    )
    target.mkdir(parents=True, exist_ok=True)
    return target


def budget_text(text: str) -> tuple[str, bool]:
    """Cap text for one response; truncation is explicit so the model
    knows it saw a slice and can re-query narrower (page ranges)."""
    if len(text) <= MAX_TEXT_CHARS:
        return text, False
    return (
        text[:MAX_TEXT_CHARS] + "\n… (truncated — re-query a narrower page range)",
        True,
    )


def parse_pages(spec: str, page_count: int, max_pages: int) -> list[int]:
    """Parse a 1-based page spec ("3", "1-5", "2,4,9-11") into 0-based
    indices, clamped to the document and capped at max_pages — the cap
    is a refusal with the number in it, never a silent slice."""
    indices: list[int] = []
    for part in spec.replace(" ", "").split(","):
        if not part:
            continue
        if "-" in part:
            start_s, _, end_s = part.partition("-")
            start, end = int(start_s), int(end_s)
            if end < start:
                raise ValueError(f"backwards page range {part!r}")
            indices.extend(range(start - 1, end))
        else:
            indices.append(int(part) - 1)
    indices = sorted({i for i in indices if 0 <= i < page_count})
    if not indices:
        raise ValueError(
            f"page spec {spec!r} selects nothing in a {page_count}-page document"
        )
    if len(indices) > max_pages:
        raise ValueError(
            f"page spec selects {len(indices)} pages — the cap is {max_pages} "
            "per call; ask again with a narrower range"
        )
    return indices
