"""Archives: listing is bounded, extraction is contained by construction."""

import tarfile
import zipfile

import pytest

from root_ext_docs import archives


def test_list_names_entries_and_sizes(sample_zip):
    report = archives.list_archive(str(sample_zip))
    names = {e["name"] for e in report["entries"]}
    assert names == {"readme.txt", "cad/bracket.step"}
    assert report["entry_count"] == 2
    assert report["truncated"] is False


def test_extract_lands_in_derived_subdir(sample_zip):
    report = archives.extract(str(sample_zip))
    assert report["count"] == 2
    for written in report["written"]:
        assert "/derived/vendor_drop/" in written
    assert report["written"][0].endswith("bracket.step")


def test_extract_picks_members(sample_zip, tmp_path):
    out = tmp_path / "picked"
    report = archives.extract(str(sample_zip), str(out), members=["readme.txt"])
    assert report["count"] == 1
    with pytest.raises(ValueError, match="not in the archive"):
        archives.extract(str(sample_zip), members=["ghost.txt"])


def test_zip_slip_is_refused_by_name(tmp_path):
    evil = tmp_path / "evil.zip"
    with zipfile.ZipFile(evil, "w") as archive:
        archive.writestr("../escape.txt", "nope")
    with pytest.raises(ValueError, match="zip-slip"):
        archives.extract(str(evil))
    # And nothing escaped.
    assert not (tmp_path.parent / "escape.txt").exists()


def test_tar_round_trips_and_links_are_skipped(tmp_path):
    src = tmp_path / "payload.txt"
    src.write_text("data")
    tar_path = tmp_path / "drop.tar.gz"
    with tarfile.open(tar_path, "w:gz") as archive:
        archive.add(src, arcname="payload.txt")
        link = tarfile.TarInfo("evil_link")
        link.type = tarfile.SYMTYPE
        link.linkname = "/etc/passwd"
        archive.addfile(link)
    listing = archives.list_archive(str(tar_path))
    kinds = {e["name"]: e["kind"] for e in listing["entries"]}
    assert kinds["evil_link"] == "link"
    report = archives.extract(str(tar_path))
    assert report["count"] == 1  # the link was skipped, the file landed
    assert report["written"][0].endswith("payload.txt")


def test_not_an_archive_is_a_named_error(tmp_path):
    fake = tmp_path / "fake.zip"
    fake.write_bytes(b"junk")
    with pytest.raises(ValueError, match="not a readable archive"):
        archives.list_archive(str(fake))
