# root-ext-docs

Document-engineering MCP tool server for ROOT Workspace (and any MCP
host). Twelve tools across four surfaces:

- **PDF** — `pdf_info` (which pages are text, which are scans),
  `pdf_extract_text` (page-ranged), `pdf_pages_to_images` (render to
  `derived/` — where the workspace viewer and the model's image-read
  path pick them up), `ocr_pdf` (local tesseract).
- **Office** — `docx_extract`, `pptx_extract`: structure-keeping
  markdown (headings, tables, slide notes).
- **Images** — `ocr_image`, `image_convert`, `image_crop`,
  `image_annotate` (labelled rectangles for pointing at drawings).
- **Archives** — `archive_list`, `archive_extract` (zip-slip refused
  by name, size/entry caps).

**Charter, binding and tested: extract and derive, never mutate
sources.** No tool overwrites, deletes, or edits a user's file in
place; write tools refuse output paths that collide with inputs and
default to `derived/` beside the source.

OCR needs the system `tesseract` binary (`brew install tesseract`) and
refuses by name without it. Nothing in this pack reaches the network.

## Develop

```sh
uv venv && uv pip install -e ".[dev]"
.venv/bin/pytest
```

## Package (signed .rootx, ADR-0018)

```sh
uv build
.venv/bin/python tools/build_pack.py   # --unsigned for a test build
```
