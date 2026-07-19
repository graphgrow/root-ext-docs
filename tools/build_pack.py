"""Build the signed .rootx extension pack (ADR-0018, publisher side).

Usage:
    .venv/bin/python tools/build_pack.py [--key /path/to/graphgrow-packs.key]

Reads the freshly built wheel from dist/, writes extension.json, signs
its exact bytes with the publisher's ed25519 key (detached, base64),
and zips the artifacts into dist/doc-eng-<version>.rootx. Without
--key (or if the key file is absent) it builds an UNSIGNED pack that
installs as unverified — useful for testing the badge, never for
distribution.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import pathlib
import sys
import zipfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
DEFAULT_KEY = pathlib.Path(
    "~/Desktop/Professional/graphgrow-pack-signing/graphgrow-packs.key"
).expanduser()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--key", type=pathlib.Path, default=DEFAULT_KEY)
    parser.add_argument("--unsigned", action="store_true")
    args = parser.parse_args()

    wheels = sorted((ROOT / "dist").glob("root_ext_docs-*-py3-none-any.whl"))
    if not wheels:
        print("no wheel in dist/ — run `uv build` first", file=sys.stderr)
        return 1
    wheel = wheels[-1]
    version = wheel.name.split("-")[1]
    sha256 = hashlib.sha256(wheel.read_bytes()).hexdigest()

    manifest = {
        "schema": 1,
        "id": "dev.graphgrow.doc-eng",
        "name": "doc-eng",
        "title": "Document Engineering",
        "version": version,
        "publisher": "graphgrow",
        "description": (
            "PDF page rendering and OCR (local tesseract), page-ranged text "
            "extraction, DOCX/PPTX structure extraction, image transforms and "
            "annotation, and contained archive handling. Extract and derive, "
            "never mutate sources — by charter and by test."
        ),
        "entry": {
            "kind": "python-wheel",
            "wheel": f"wheels/{wheel.name}",
            "sha256": sha256,
            "script": "root-ext-docs",
        },
        # No network anywhere in this pack — OCR is the local tesseract
        # binary, refused by name when absent.
        "needs": {},
        # First-class promotion (ADR-0019): pure-read extraction runs
        # SANDBOXED — except the OCR tools, which spawn the system
        # tesseract subprocess and therefore need user-program; the
        # derived-write tools (they create artifacts) are user-program
        # writes. The client clamps each to stricter(declared, derived).
        # The pack's operating instructions (ADR-0025). Only the POINTER
        # lives in the manifest; the text rides inside the wheel, whose
        # sha256 this manifest pins — so the signature that covers the
        # manifest covers the instructions too, with nothing extra to
        # sign and one copy to keep in sync. Note what is absent: no
        # field here grants a tool or widens a permission. A skill tells
        # the model what to do; it can never change what it is allowed
        # to do.
        "skill": {"body": "root_ext_docs/SKILL.md"},
        "tools": [
            *(
                {"name": name, "side_effect": "read", "posture": "sandboxed"}
                for name in (
                    "pdf_info", "pdf_extract_text",
                    "docx_extract", "pptx_extract", "archive_list",
                )
            ),
            *(
                {"name": name, "side_effect": "read", "posture": "user-program"}
                for name in ("ocr_pdf", "ocr_image")
            ),
            *(
                {"name": name, "side_effect": "write", "posture": "user-program"}
                for name in (
                    "pdf_pages_to_images", "image_convert", "image_crop",
                    "image_annotate", "archive_extract",
                )
            ),
        ],
    }
    manifest_bytes = json.dumps(manifest, indent=2).encode()

    signature_b64 = None
    if not args.unsigned and args.key.is_file():
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

        raw = base64.b64decode(args.key.read_text().strip())
        key = Ed25519PrivateKey.from_private_bytes(raw)
        signature_b64 = base64.b64encode(key.sign(manifest_bytes)).decode()
        print(f"signed as graphgrow with {args.key}")
    else:
        print("building UNSIGNED (installs as unverified)")

    out = ROOT / "dist" / f"doc-eng-{version}.rootx"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as pack:
        pack.writestr("extension.json", manifest_bytes)
        if signature_b64:
            pack.writestr("extension.json.sig", signature_b64 + "\n")
        pack.write(wheel, f"wheels/{wheel.name}")
    print(f"built {out} ({out.stat().st_size:,} bytes; wheel sha256 {sha256[:16]}…)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
