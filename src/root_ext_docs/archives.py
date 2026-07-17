"""Archive capabilities: list and extract, contained by construction.

Vendor deliverables arrive zipped. ``extract`` unpacks into a derived
directory ONLY — every member path is normalized and must stay inside
it (zip-slip refused by name), symlinks and absolute paths are refused,
and total uncompressed size + entry count are capped so a zip bomb is
an error, not an outage.
"""

from __future__ import annotations

import tarfile
import zipfile
from pathlib import Path, PurePosixPath

from . import files

MAX_LIST_ENTRIES = 1_000
MAX_EXTRACT_ENTRIES = 500
MAX_EXTRACT_BYTES = 500_000_000

_TAR_SUFFIXES = (".tar", ".tgz", ".tar.gz", ".tar.bz2", ".tar.xz")


def _is_tar(path: Path) -> bool:
    name = path.name.lower()
    return any(name.endswith(suffix) for suffix in _TAR_SUFFIXES)


def _entries(resolved: Path) -> list[dict]:
    """Uniform entry listing across zip and tar."""
    out: list[dict] = []
    if _is_tar(resolved):
        with tarfile.open(resolved) as archive:
            for member in archive:
                out.append(
                    {
                        "name": member.name,
                        "size": member.size,
                        "kind": "dir" if member.isdir() else (
                            "link" if member.issym() or member.islnk() else "file"
                        ),
                    }
                )
    else:
        with zipfile.ZipFile(resolved) as archive:
            for entry in archive.infolist():
                out.append(
                    {
                        "name": entry.filename,
                        "size": entry.file_size,
                        "kind": "dir" if entry.is_dir() else "file",
                    }
                )
    return out


def list_archive(path: str) -> dict:
    resolved = files.checked_path(path, files.ARCHIVE_SUFFIXES)
    try:
        entries = _entries(resolved)
    except (zipfile.BadZipFile, tarfile.TarError) as exc:
        raise ValueError(f"not a readable archive: {exc}") from exc
    truncated = len(entries) > MAX_LIST_ENTRIES
    total = sum(e["size"] for e in entries)
    return {
        "source": str(resolved),
        "entry_count": len(entries),
        "total_uncompressed_bytes": total,
        "entries": entries[:MAX_LIST_ENTRIES],
        "truncated": truncated,
    }


def _safe_member(name: str) -> PurePosixPath:
    """Normalize one member path; refuse anything that would escape."""
    member = PurePosixPath(name)
    if member.is_absolute() or any(part == ".." for part in member.parts):
        raise ValueError(
            f"archive member {name!r} escapes the extraction directory — "
            "refusing the whole archive (zip-slip)"
        )
    return member


def extract(path: str, out_dir: str | None = None, members: list[str] | None = None) -> dict:
    """Extract into derived/<stem>/ (or out_dir) — never anywhere else."""
    resolved = files.checked_path(path, files.ARCHIVE_SUFFIXES)
    try:
        entries = _entries(resolved)
    except (zipfile.BadZipFile, tarfile.TarError) as exc:
        raise ValueError(f"not a readable archive: {exc}") from exc

    wanted = set(members) if members else None
    picked = [
        e for e in entries
        if e["kind"] == "file" and (wanted is None or e["name"] in wanted)
    ]
    if wanted:
        missing = wanted - {e["name"] for e in picked}
        if missing:
            raise ValueError(f"members not in the archive: {sorted(missing)[:10]}")
    if not picked:
        raise ValueError("nothing to extract (directories and links are skipped)")
    if len(picked) > MAX_EXTRACT_ENTRIES:
        raise ValueError(
            f"{len(picked)} files exceed the {MAX_EXTRACT_ENTRIES}-entry cap — "
            "pass `members` to pick what you need"
        )
    total = sum(e["size"] for e in picked)
    if total > MAX_EXTRACT_BYTES:
        raise ValueError(
            f"{total} uncompressed bytes exceed the {MAX_EXTRACT_BYTES} cap — "
            "pass `members` to pick what you need"
        )
    for entry in picked:
        _safe_member(entry["name"])  # refuse the whole archive up front

    stem = resolved.name.split(".")[0] or "archive"
    base = files.derived_dir(resolved, out_dir) if out_dir else files.derived_dir(
        resolved, None
    ) / stem
    base.mkdir(parents=True, exist_ok=True)
    base = base.resolve()

    names = {e["name"] for e in picked}
    written: list[str] = []
    if _is_tar(resolved):
        with tarfile.open(resolved) as archive:
            for member in archive:
                if member.name not in names or not member.isfile():
                    continue
                target = (base / _safe_member(member.name)).resolve()
                if not target.is_relative_to(base):
                    raise ValueError(f"member {member.name!r} escapes (zip-slip)")
                target.parent.mkdir(parents=True, exist_ok=True)
                source = archive.extractfile(member)
                if source is None:
                    continue
                target.write_bytes(source.read())
                written.append(str(target))
    else:
        with zipfile.ZipFile(resolved) as archive:
            for name in names:
                target = (base / _safe_member(name)).resolve()
                if not target.is_relative_to(base):
                    raise ValueError(f"member {name!r} escapes (zip-slip)")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.read(name))
                written.append(str(target))
    return {
        "source": str(resolved),
        "out_dir": str(base),
        "written": sorted(written),
        "count": len(written),
    }
