#!/usr/bin/env python3
"""Shared standard-library helpers for the conduct-cs-research skill."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import re
import stat
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

PLACEHOLDER_RE = re.compile(
    r"(?i)(?:\bTODO\b|\bTBD\b|\bFIXME\b|\[fill(?:\s+in)?[^\]]*\]|\[describe[^\]]*\])"
)
ID_PATTERNS = {
    "source_id": re.compile(r"^S\d{4}$"),
    "note_id": re.compile(r"^N\d{4}$"),
    "decision_id": re.compile(r"^D\d{4}$"),
    "run_id": re.compile(r"^E\d{4}$"),
    "result_id": re.compile(r"^R\d{4}$"),
    "claim_id": re.compile(r"^C\d{4}$"),
    "finding_id": re.compile(r"^F\d{4}$"),
    "revision_id": re.compile(r"^V\d{4}$"),
    "search_id": re.compile(r"^Q\d{4}$"),
    "action_id": re.compile(r"^A\d{4}$"),
}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
DEFAULT_MAX_ENTRIES = 10_000
DEFAULT_MAX_DEPTH = 32
DEFAULT_MAX_TOTAL_BYTES = 1_000_000_000


class ValidationError(ValueError):
    """Raised for malformed local research records."""


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def parse_timestamp(value: str, *, field: str = "timestamp") -> datetime:
    """Parse a timezone-aware ISO-8601 timestamp."""
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{field} is empty")
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValidationError(f"{field} is not valid ISO-8601: {value!r}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValidationError(f"{field} must include a timezone: {value!r}")
    return parsed


def _validate_stat(info: os.stat_result, path: Path, max_bytes: int) -> None:
    if not stat.S_ISREG(info.st_mode):
        raise ValidationError(f"not a regular file: {path}")
    if info.st_nlink != 1:
        raise ValidationError(f"hard-linked file is not allowed: {path}")
    if info.st_size > max_bytes:
        raise ValidationError(f"file exceeds {max_bytes} bytes: {path}")


def _same_identity(left: os.stat_result, right: os.stat_result) -> bool:
    return (left.st_dev, left.st_ino) == (right.st_dev, right.st_ino)


def _same_snapshot(left: os.stat_result, right: os.stat_result) -> bool:
    return (
        left.st_dev,
        left.st_ino,
        left.st_size,
        getattr(left, "st_mtime_ns", int(left.st_mtime * 1_000_000_000)),
        getattr(left, "st_ctime_ns", int(left.st_ctime * 1_000_000_000)),
    ) == (
        right.st_dev,
        right.st_ino,
        right.st_size,
        getattr(right, "st_mtime_ns", int(right.st_mtime * 1_000_000_000)),
        getattr(right, "st_ctime_ns", int(right.st_ctime * 1_000_000_000)),
    )


def _open_regular(path: Path, *, max_bytes: int) -> tuple[int, os.stat_result]:
    try:
        before = path.lstat()
    except FileNotFoundError as exc:
        raise ValidationError(f"missing file: {path}") from exc
    except OSError as exc:
        raise ValidationError(f"cannot inspect file {path}: {exc}") from exc
    if stat.S_ISLNK(before.st_mode):
        raise ValidationError(f"linked file is not allowed: {path}")
    _validate_stat(before, path, max_bytes)

    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise ValidationError(f"cannot open regular file {path}: {exc}") from exc
    try:
        opened = os.fstat(descriptor)
        _validate_stat(opened, path, max_bytes)
        if not _same_identity(before, opened):
            raise ValidationError(f"file identity changed while opening: {path}")
        return descriptor, opened
    except Exception:
        os.close(descriptor)
        raise


def ensure_regular_file(path: Path, *, max_bytes: int = 10_000_000) -> os.stat_result:
    descriptor, opened = _open_regular(path, max_bytes=max_bytes)
    os.close(descriptor)
    return opened


def read_bytes(path: Path, *, max_bytes: int = 10_000_000) -> bytes:
    descriptor, before = _open_regular(path, max_bytes=max_bytes)
    try:
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(descriptor, min(1024 * 1024, max_bytes - total + 1))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > max_bytes:
                raise ValidationError(f"file exceeds {max_bytes} bytes while reading: {path}")
        after = os.fstat(descriptor)
        if not _same_snapshot(before, after):
            raise ValidationError(f"file changed while being read: {path}")
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def read_text(path: Path, *, max_bytes: int = 10_000_000) -> str:
    data = read_bytes(path, max_bytes=max_bytes)
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValidationError(f"file is not UTF-8: {path}") from exc


def sha256_file(path: Path, *, max_bytes: int = DEFAULT_MAX_TOTAL_BYTES) -> str:
    descriptor, before = _open_regular(path, max_bytes=max_bytes)
    digest = hashlib.sha256()
    total = 0
    try:
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                raise ValidationError(f"file exceeds {max_bytes} bytes while hashing: {path}")
            digest.update(chunk)
        after = os.fstat(descriptor)
        if not _same_snapshot(before, after):
            raise ValidationError(f"file changed while being hashed: {path}")
        return digest.hexdigest()
    finally:
        os.close(descriptor)


def scan_tree(
    root: Path,
    *,
    max_entries: int = DEFAULT_MAX_ENTRIES,
    max_depth: int = DEFAULT_MAX_DEPTH,
    max_total_bytes: int = DEFAULT_MAX_TOTAL_BYTES,
) -> dict[str, Any]:
    """Inspect a tree without following links and enforce bounded traversal."""
    if max_entries < 1 or max_depth < 1 or max_total_bytes < 1:
        raise ValidationError("tree limits must be positive")
    try:
        root_info = root.lstat()
    except FileNotFoundError as exc:
        raise ValidationError(f"missing directory: {root}") from exc
    except OSError as exc:
        raise ValidationError(f"cannot inspect directory {root}: {exc}") from exc
    if stat.S_ISLNK(root_info.st_mode) or not stat.S_ISDIR(root_info.st_mode):
        raise ValidationError(f"not a regular directory: {root}")

    stack: list[Path] = [root]
    files: list[Path] = []
    entries_seen = 0
    total_bytes = 0
    max_depth_seen = 0
    while stack:
        directory = stack.pop()
        try:
            with os.scandir(directory) as iterator:
                entries = sorted(iterator, key=lambda item: item.name)
        except OSError as exc:
            raise ValidationError(f"cannot scan directory {directory}: {exc}") from exc
        for entry in entries:
            entries_seen += 1
            if entries_seen > max_entries:
                raise ValidationError(f"tree exceeds {max_entries} filesystem entries: {root}")
            path = Path(entry.path)
            depth = len(path.relative_to(root).parts)
            max_depth_seen = max(max_depth_seen, depth)
            if depth > max_depth:
                raise ValidationError(f"tree exceeds maximum relative depth {max_depth}: {path}")
            try:
                info = entry.stat(follow_symlinks=False)
            except OSError as exc:
                raise ValidationError(f"cannot inspect tree entry {path}: {exc}") from exc
            if stat.S_ISLNK(info.st_mode):
                raise ValidationError(f"linked path is not allowed: {path}")
            if stat.S_ISDIR(info.st_mode):
                stack.append(path)
                continue
            if not stat.S_ISREG(info.st_mode):
                raise ValidationError(f"special file is not allowed: {path}")
            if info.st_nlink != 1:
                raise ValidationError(f"hard-linked file is not allowed: {path}")
            total_bytes += info.st_size
            if total_bytes > max_total_bytes:
                raise ValidationError(
                    f"tree exceeds aggregate regular-file budget {max_total_bytes} bytes: {root}"
                )
            files.append(path)
    files.sort(key=lambda item: item.relative_to(root).as_posix())
    return {
        "entries": entries_seen,
        "files": files,
        "file_count": len(files),
        "total_bytes": total_bytes,
        "max_depth": max_depth_seen,
    }


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValidationError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_json(path: Path, *, max_bytes: int = 2_000_000) -> Any:
    text = read_text(path, max_bytes=max_bytes)
    try:
        return json.loads(
            text,
            object_pairs_hook=_strict_object,
            parse_constant=lambda value: (_ for _ in ()).throw(
                ValidationError(f"non-finite JSON value: {value}")
            ),
        )
    except (json.JSONDecodeError, ValidationError) as exc:
        raise ValidationError(f"invalid JSON in {path}: {exc}") from exc


def write_text_new(path: Path, text: str) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def write_json_new(path: Path, value: Any) -> None:
    write_text_new(path, json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n")


def read_csv(path: Path, *, max_bytes: int = 5_000_000) -> tuple[list[str], list[dict[str, str]]]:
    text = read_text(path, max_bytes=max_bytes)
    if not text:
        raise ValidationError(f"empty CSV: {path}")
    if "\x00" in text:
        raise ValidationError(f"NUL byte in CSV: {path}")
    try:
        reader = csv.DictReader(io.StringIO(text, newline=""), strict=True)
        headers = reader.fieldnames or []
        if not headers or any(not header or not header.strip() for header in headers):
            raise ValidationError(f"invalid CSV header: {path}")
        headers = [header.strip() for header in headers]
        if len(headers) != len(set(headers)):
            raise ValidationError(f"duplicate CSV header: {path}")
        rows: list[dict[str, str]] = []
        for index, row in enumerate(reader, start=2):
            if None in row:
                raise ValidationError(f"extra CSV field at {path}:{index}")
            normalized = {key.strip(): (value or "").strip() for key, value in row.items()}
            if not any(normalized.values()):
                raise ValidationError(f"blank CSV record at {path}:{index}")
            rows.append(normalized)
        return headers, rows
    except csv.Error as exc:
        raise ValidationError(f"invalid CSV in {path}: {exc}") from exc


def require_headers(path: Path, headers: list[str], required: Iterable[str]) -> list[str]:
    missing = [name for name in required if name not in headers]
    return [f"{path}: missing CSV column '{name}'" for name in missing]


def split_ids(value: str) -> list[str]:
    return [item.strip() for item in re.split(r"[;,\s]+", value or "") if item.strip()]


def has_placeholder(text: str) -> bool:
    return bool(PLACEHOLDER_RE.search(text))


def within(root: Path, candidate: Path) -> bool:
    try:
        candidate.resolve().relative_to(root.resolve())
        return True
    except (OSError, RuntimeError, ValueError):
        return False


def project_path(
    root: Path,
    raw: str,
    *,
    must_exist: bool = True,
    max_bytes: int = DEFAULT_MAX_TOTAL_BYTES,
) -> Path:
    """Resolve a portable project-relative regular-file path beneath root."""
    if not isinstance(raw, str) or not raw.strip() or "\x00" in raw or "\\" in raw:
        raise ValidationError(f"invalid project-relative path: {raw!r}")
    pure = PurePosixPath(raw.strip())
    if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
        raise ValidationError(f"unsafe project-relative path: {raw!r}")
    candidate = root.joinpath(*pure.parts)
    if not within(root, candidate):
        raise ValidationError(f"project path escapes root: {raw!r}")
    if must_exist:
        ensure_regular_file(candidate, max_bytes=max_bytes)
    return candidate


def verify_path_hash(root: Path, raw_path: str, raw_hash: str, *, label: str) -> Path:
    expected = (raw_hash or "").lower()
    if not SHA256_RE.fullmatch(expected):
        raise ValidationError(f"{label} has invalid sha256")
    candidate = project_path(root, raw_path)
    actual = sha256_file(candidate)
    if actual != expected:
        raise ValidationError(f"{label} hash does not match current bytes")
    return candidate


def nonempty_without_placeholder(path: Path) -> bool:
    try:
        text = read_text(path)
    except ValidationError:
        return False
    return bool(text.strip()) and not has_placeholder(text)
