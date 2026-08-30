#!/usr/bin/env python3
"""Perform a conservative static audit of a LaTeX manuscript tree."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Iterable

from _common import ValidationError, has_placeholder, read_text, within

INPUT_RE = re.compile(r"\\(?:input|include)\s*\{([^{}]+)\}")
GRAPHICS_RE = re.compile(r"\\includegraphics(?:\[[^\]]*\])?\s*\{([^{}]+)\}")
BIB_RE = re.compile(r"\\bibliography\s*\{([^{}]+)\}")
ADDBIB_RE = re.compile(r"\\addbibresource(?:\[[^\]]*\])?\s*\{([^{}]+)\}")
CITE_RE = re.compile(r"\\cite[a-zA-Z*]*\s*\{([^{}]+)\}")
LABEL_RE = re.compile(r"\\label\s*\{([^{}]+)\}")
REF_RE = re.compile(r"\\(?:ref|eqref|autoref|pageref|cref|Cref)\s*\{([^{}]+)\}")
BIB_KEY_RE = re.compile(r"@\w+\s*[({]\s*([^,\s]+)\s*,", re.IGNORECASE)
UNSAFE = {
    "shell escape": re.compile(r"\\(?:immediate\s*)?write18\b|\\ShellEscape\b", re.IGNORECASE),
    "file output": re.compile(r"\\(?:openout|write|newwrite)\b", re.IGNORECASE),
    "file input primitive": re.compile(r"\\(?:openin|read|readline)\b", re.IGNORECASE),
    "pipe input": re.compile(r"\\input\s*\{?\s*\|", re.IGNORECASE),
    "system command package": re.compile(r"\\usepackage(?:\[[^\]]*\])?\{(?:shellesc|catchfile)\}", re.IGNORECASE),
}


def strip_comments(text: str) -> str:
    output: list[str] = []
    for line in text.splitlines():
        cut = len(line)
        for index, char in enumerate(line):
            if char != "%":
                continue
            backslashes = 0
            cursor = index - 1
            while cursor >= 0 and line[cursor] == "\\":
                backslashes += 1
                cursor -= 1
            if backslashes % 2 == 0:
                cut = index
                break
        output.append(line[:cut])
    return "\n".join(output)


def split_list(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def safe_candidate(root: Path, current: Path, raw: str, extensions: Iterable[str]) -> Path | None:
    value = raw.strip()
    if not value or "\x00" in value or "|" in value or value.startswith(("~", "/", "\\")):
        return None
    candidate = current.parent / value
    if candidate.suffix:
        candidates = [candidate]
    else:
        candidates = [candidate.with_suffix(ext) for ext in extensions]
    for item in candidates:
        if within(root, item) and item.is_file() and not item.is_symlink():
            return item.resolve()
    return candidates[0]


def audit(root: Path, main: Path, *, allow_placeholders: bool = False, compiler_log: Path | None = None) -> dict[str, object]:
    errors: list[str] = []
    warnings: list[str] = []
    root = root.resolve()
    main_path = main if main.is_absolute() else root / main
    if not within(root, main_path):
        return {"passed": False, "errors": ["main file escapes the manuscript root"], "warnings": [], "metrics": {}}
    if not main_path.is_file() or main_path.is_symlink():
        return {"passed": False, "errors": [f"missing or linked main file: {main_path}"], "warnings": [], "metrics": {}}

    pending = [main_path.resolve()]
    visited: set[Path] = set()
    combined: list[tuple[Path, str]] = []
    while pending:
        path = pending.pop()
        if path in visited:
            continue
        visited.add(path)
        try:
            text = strip_comments(read_text(path))
        except ValidationError as exc:
            errors.append(str(exc))
            continue
        combined.append((path, text))
        if not allow_placeholders and has_placeholder(text):
            errors.append(f"placeholder remains in {path.relative_to(root)}")
        for label, pattern in UNSAFE.items():
            if pattern.search(text):
                errors.append(f"unsafe LaTeX primitive ({label}) in {path.relative_to(root)}")
        for raw in INPUT_RE.findall(text):
            child = safe_candidate(root, path, raw, (".tex",))
            if child is None or not within(root, child):
                errors.append(f"unsafe input path '{raw}' in {path.relative_to(root)}")
            elif not child.is_file() or child.is_symlink():
                errors.append(f"missing or linked input '{raw}' in {path.relative_to(root)}")
            else:
                pending.append(child.resolve())

    labels: list[str] = []
    refs: list[str] = []
    citations: list[str] = []
    bib_paths: list[Path] = []
    graphics: list[str] = []
    for path, text in combined:
        labels.extend(LABEL_RE.findall(text))
        refs.extend(REF_RE.findall(text))
        for value in CITE_RE.findall(text):
            citations.extend(split_list(value))
        for value in BIB_RE.findall(text):
            for item in split_list(value):
                candidate = safe_candidate(root, path, item, (".bib",))
                if candidate is None or not within(root, candidate) or not candidate.is_file() or candidate.is_symlink():
                    errors.append(f"missing or unsafe bibliography '{item}' in {path.relative_to(root)}")
                else:
                    bib_paths.append(candidate.resolve())
        for value in ADDBIB_RE.findall(text):
            candidate = safe_candidate(root, path, value, (".bib",))
            if candidate is None or not within(root, candidate) or not candidate.is_file() or candidate.is_symlink():
                errors.append(f"missing or unsafe bibliography '{value}' in {path.relative_to(root)}")
            else:
                bib_paths.append(candidate.resolve())
        for value in GRAPHICS_RE.findall(text):
            graphics.append(value)
            candidate = safe_candidate(root, path, value, (".pdf", ".png", ".jpg", ".jpeg", ".eps"))
            if candidate is None or not within(root, candidate) or not candidate.is_file() or candidate.is_symlink():
                errors.append(f"missing or unsafe graphic '{value}' in {path.relative_to(root)}")

    duplicate_labels = sorted(key for key, count in Counter(labels).items() if count > 1)
    for key in duplicate_labels:
        errors.append(f"duplicate LaTeX label: {key}")
    for key in sorted(set(refs) - set(labels)):
        errors.append(f"unresolved LaTeX reference: {key}")

    bib_keys: set[str] = set()
    for path in sorted(set(bib_paths)):
        try:
            bib_text = strip_comments(read_text(path))
        except ValidationError as exc:
            errors.append(str(exc))
            continue
        keys = BIB_KEY_RE.findall(bib_text)
        duplicates = [key for key, count in Counter(keys).items() if count > 1]
        for key in duplicates:
            errors.append(f"duplicate bibliography key '{key}' in {path.relative_to(root)}")
        bib_keys.update(keys)
    for key in sorted(set(citations) - bib_keys):
        errors.append(f"unresolved citation key: {key}")
    if citations and not bib_paths:
        errors.append("citations are present but no bibliography file was resolved")

    if compiler_log is not None:
        try:
            log = read_text(compiler_log, max_bytes=20_000_000)
        except ValidationError as exc:
            errors.append(str(exc))
        else:
            if re.search(r"LaTeX Warning:.*undefined", log, re.IGNORECASE):
                errors.append("compiler log reports undefined references or citations")
            if re.search(r"^! LaTeX Error:", log, re.MULTILINE):
                errors.append("compiler log reports a LaTeX error")
            if "Overfull \\hbox" in log:
                warnings.append("compiler log reports overfull boxes")

    metrics = {
        "tex_files": len(visited),
        "labels": len(labels),
        "references": len(refs),
        "citations": len(citations),
        "bibliography_keys": len(bib_keys),
        "graphics": len(graphics),
    }
    return {"passed": not errors, "errors": errors, "warnings": warnings, "metrics": metrics}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--main", type=Path, default=Path("main.tex"))
    parser.add_argument("--compiler-log", type=Path)
    parser.add_argument("--allow-placeholders", action="store_true")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()
    result = audit(args.root.expanduser(), args.main, allow_placeholders=args.allow_placeholders, compiler_log=args.compiler_log)
    if args.as_json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print("PASS" if result["passed"] else "FAIL")
        for item in result["errors"]:
            print(f"ERROR: {item}")
        for item in result["warnings"]:
            print(f"WARNING: {item}")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
