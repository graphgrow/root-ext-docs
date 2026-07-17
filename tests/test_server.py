"""Server wiring: every tool present, annotations honest per the
classification contract (read = readOnly + closed-world; derived-write
= NOT-readOnly + closed-world, the write class; no network tools exist
in this pack at all — OCR is the local tesseract binary)."""

import asyncio

from root_ext_docs.server import mcp

READ_TOOLS = {
    "pdf_info",
    "pdf_extract_text",
    "ocr_pdf",
    "docx_extract",
    "pptx_extract",
    "ocr_image",
    "archive_list",
}
WRITE_TOOLS = {
    "pdf_pages_to_images",
    "image_convert",
    "image_crop",
    "image_annotate",
    "archive_extract",
}


def list_tools():
    return asyncio.run(mcp.list_tools())


def test_all_tools_registered():
    names = {tool.name for tool in list_tools()}
    assert names == READ_TOOLS | WRITE_TOOLS


def test_read_tools_declare_read_only_closed_world():
    for tool in list_tools():
        if tool.name in READ_TOOLS:
            assert tool.annotations is not None, tool.name
            assert tool.annotations.readOnlyHint is True, tool.name
            assert tool.annotations.openWorldHint is False, tool.name


def test_write_tools_declare_closed_world_write():
    # readOnlyHint False + openWorldHint False → the classifier's
    # write class: gated like any write, never mistaken for read.
    for tool in list_tools():
        if tool.name in WRITE_TOOLS:
            assert tool.annotations is not None, tool.name
            assert tool.annotations.readOnlyHint is False, tool.name
            assert tool.annotations.openWorldHint is False, tool.name
            assert tool.annotations.destructiveHint is False, tool.name


def test_no_tool_claims_the_open_world():
    # This pack never reaches the network — no tool may say otherwise.
    for tool in list_tools():
        assert tool.annotations.openWorldHint is False, tool.name


def test_descriptions_teach():
    # Descriptions are prompt surface — every tool says what it does and
    # names its limits; none may be empty.
    for tool in list_tools():
        assert tool.description and len(tool.description) > 40, tool.name


def test_no_inplace_mutation_tools_exist():
    # The charter, as a test: extract and derive — nothing in the
    # registry overwrites, deletes, moves, or edits a user's file.
    names = {tool.name for tool in list_tools()}
    for forbidden in ("overwrite", "delete", "remove", "move", "rename", "save_as", "edit"):
        assert not any(forbidden in name for name in names), forbidden


def test_ocr_tools_name_their_dependency():
    # OCR spawns the system tesseract binary — the descriptions must
    # say so and promise the named refusal.
    for tool in list_tools():
        if tool.name.startswith("ocr"):
            assert "tesseract" in tool.description, tool.name
            assert "refuses by name" in tool.description, tool.name
