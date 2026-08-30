#!/usr/bin/env python3
"""Shared standard-library helpers for the conduct-cs-research skill."""

from __future__ import annotations

import csv
import hashlib
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
}


class ValidationError(ValueError):
    """Raised for malformed local research records."""


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def ensure_regular_file(path: Path, *, max_bytes: int = 10_000_000) -> os.stat_result:
    try:
        info = path.lstat()
    except FileNotFoundError as exc:
        raise ValidationError(f"missing file: {path}") from exc
    if stat.S_ISLNK(info.st_mode):
        raise ValidationError(f"linked file is not allowed: {path}")
    if not stat.S_ISREG(info.st_mode):
        raise ValidationError(f"not a regular file: {path}")
    if info.st_nlink != 1:
        raise ValidationError(f"hard-linked file is not allowed: {path}")
    if info.st_size > max_bytes:
        raise ValidationError(f"file exceeds {max_bytes} bytes: {path}")
    return info


def read_text(path: Path, *, max_bytes: int = 10_000_000) -> str:
    before = ensure_regular_file(path, max_bytes=max_bytes)
    data = path.read_bytes()
    after = path.lstat()
    if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
    ):
        raise ValidationError(f"file changed while being read: {path}")
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValidationError(f"file is not UTF-8: {path}") from exc


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
    lines = text.splitlines()
    if not lines:
        raise ValidationError(f"empty CSV: {path}")
    try:
        reader = csv.DictReader(lines, strict=True)
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


def sha256_file(path: Path) -> str:
    ensure_regular_file(path, max_bytes=1_000_000_000)
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def has_placeholder(text: str) -> bool:
    return bool(PLACEHOLDER_RE.search(text))


def within(root: Path, candidate: Path) -> bool:
    root_resolved = root.resolve()
    try:
        candidate.resolve().relative_to(root_resolved)
        return True
    except (OSError, ValueError):
        return False


def nonempty_without_placeholder(path: Path) -> bool:
    try:
        text = read_text(path)
    except ValidationError:
        return False
    return bool(text.strip()) and not has_placeholder(text)


def safe_cell(value: str) -> str:
    """Neutralize spreadsheet formulas in generated CSV cells."""
    return "'" + value if value.startswith(("=", "+", "-", "@")) else value
