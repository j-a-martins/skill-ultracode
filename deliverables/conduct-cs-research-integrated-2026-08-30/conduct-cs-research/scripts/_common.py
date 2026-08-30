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
from pathlib import Path
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
}


class ValidationError(ValueError):
    """Raised for malformed local research records."""


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


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
    ) == (
        right.st_dev,
        right.st_ino,
        right.st_size,
        getattr(right, "st_mtime_ns", int(right.st_mtime * 1_000_000_000)),
    )


def _open_regular(path: Path, *, max_bytes: int) -> tuple[int, os.stat_result]:
    try:
        before = path.lstat()
    except FileNotFoundError as exc:
        raise ValidationError(f"missing file: {path}") from exc
    if stat.S_ISLNK(before.st_mode):
        raise ValidationError(f"linked file is not allowed: {path}")
    _validate_stat(before, path, max_bytes)

    flags = os.O_RDONLY
    flags |= getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
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


def sha256_file(path: Path, *, max_bytes: int = 1_000_000_000) -> str:
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


def write_json_new(path: Path, value: Any) -> None:
    text = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def read_csv(path: Path, *, max_bytes: int = 5_000_000) -> tuple[list[str], list[dict[str, str]]]:
    text = read_text(path, max_bytes=max_bytes)
    if not text:
        raise ValidationError(f"empty CSV: {path}")
    try:
        reader = csv.DictReader(io.StringIO(text, newline=""), strict=True)
        headers = reader.fieldnames or []
        if not headers or any(not header for header in headers):
            raise ValidationError(f"invalid CSV header: {path}")
        if len(headers) != len(set(headers)):
            raise ValidationError(f"duplicate CSV header: {path}")
        rows = []
        for index, row in enumerate(reader, start=2):
            if None in row:
                raise ValidationError(f"extra CSV field at {path}:{index}")
            rows.append({key: (value or "").strip() for key, value in row.items()})
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


def nonempty_without_placeholder(path: Path) -> bool:
    try:
        text = read_text(path)
    except ValidationError:
        return False
    return bool(text.strip()) and not has_placeholder(text)
