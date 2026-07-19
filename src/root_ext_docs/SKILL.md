---
name: doc-eng
description: >
  Operating instructions for document work with this pack — inventory a
  PDF before reading it so text, scans and drawings each go to the right
  tool, list an archive before extracting it, and verify numbers OCR gave
  you. Use when reading PDFs, DOCX or PPTX files, running OCR, converting
  or cropping images, or handling zip and tar archives.
paths:
  - "*.pdf"
  - "*.docx"
  - "*.pptx"
  - "*.zip"
  - "*.tar"
  - "*.tgz"
  - "*.tar.gz"
license: MIT
---

# Document engineering — operating notes

**Extract and derive, never mutate sources.** Nothing overwrites,
deletes or edits a user's file. Write tools refuse an output path that
collides with an input and default to `derived/` beside the source, where
the workspace's viewers pick the artifacts up.

## Call `pdf_info` first — it routes everything else

A PDF is not one kind of thing. `pdf_info` tells you, per page, which
pages carry a text layer and which are scans or drawings. That single
fact decides the next tool:

- **text layer** → `pdf_extract_text`
- **scan** → `ocr_pdf`
- **drawing** → `pdf_pages_to_images`, then `fs.read` the PNG and look

Skipping this is the classic failure: `pdf_extract_text` on a scanned
page returns nothing useful, and it is easy to misread that emptiness as
"the document says nothing about X" rather than "I used the wrong tool".

## Read in slices

`pdf_extract_text` takes 1-based page ranges — `"3"`, `"1-5"`,
`"2,4,9-11"` — and caps at **50 pages per call**. A 400-page standard is
meant to be read in slices, not one blind gulp. Use `pdf_info`'s page
count and sizes to choose the slice.

Other per-call caps worth planning around: render 20 pages, OCR 10 pages,
archive list 1000 entries, archive extract 500 entries / 500 MB.

## OCR misreads numbers

Both `ocr_pdf` and `ocr_image` say this and they mean it. Digits,
decimal points and units are exactly where OCR fails, and exactly what
gets quoted into a report.

When a value matters, verify it against the page: render it with
`pdf_pages_to_images`, `image_crop` to the region, and look. Do not
present an OCR'd figure as measured fact without that check.

Both tools need the local `tesseract` binary and refuse by name without
it. Nothing here reaches the network — if tesseract is not installed,
the honest answer is to say so and suggest `brew install tesseract`.

## Zoom in before you squint

For a dense drawing or a table in a scan, the chain is:

`pdf_pages_to_images` → `image_crop` to the region → `ocr_image`, or just
`fs.read` the crop and look at it.

Cropping first raises OCR accuracy and makes looking actually useful.
`image_annotate` is the other direction: draw labelled rectangles to
point at a region when words alone are ambiguous for the user.

## List an archive before extracting it

`archive_list` shows entries, kinds and the total uncompressed size.
Check that total before extracting — that is what the tool is for.

`archive_extract` refuses absolute paths, `..` members and links by name.
Note the posture: **one bad member refuses the whole archive**, not just
that entry. That is deliberate, and it is not a bug to route around. A
zip bomb is an error, not an outage.

## Structure is worth keeping

`docx_extract` returns the document in order with headings as markdown
levels and tables as markdown tables, so you can cite the table under its
section instead of fishing in text soup. `pptx_extract` gives you slides
with their speaker notes, quoted and marked as notes — the notes often
carry the actual argument.

Both are bounded, and truncation is marked. If you see a truncation
marker, narrow the request rather than reasoning from the visible half.

## Handing text to another pack

The drone pack's `report_extract` takes photogrammetry report **text**,
not a path. This pack is how you get it: `pdf_info` to see whether the
report is text or scan, then `pdf_extract_text` or `ocr_pdf`, then pass
the result across.
