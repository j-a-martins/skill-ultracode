#!/usr/bin/env python3
"""Conservatively audit a bounded LaTeX manuscript tree."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable

from _common import (
    DEFAULT_MAX_DEPTH,
    DEFAULT_MAX_ENTRIES,
    DEFAULT_MAX_TOTAL_BYTES,
    ValidationError,
    has_placeholder,
    read_text,
    scan_tree,
    within,
)

INPUT_RE = re.compile(r"\\(?:input|include|subfile)\s*\{([^{}]+)\}")
UNBRACED_INPUT_RE = re.compile(r"\\(?:input|include)\s+([^\s%{}]+)")
IMPORT_RE = re.compile(
    r"\\(?:import|subimport|inputfrom|includefrom|subinputfrom|subincludefrom)"
    r"\s*\{([^{}]+)\}\s*\{([^{}]+)\}"
)
GRAPHICS_RE = re.compile(r"\\includegraphics(?:\[[^\]]*\])?\s*\{([^{}]+)\}")
GRAPHICSPATH_RE = re.compile(r"\\graphicspath\s*\{((?:\s*\{[^{}]+\}\s*)+)\}")
BIB_RE = re.compile(r"\\bibliography\s*\{([^{}]+)\}")
ADDBIB_RE = re.compile(r"\\addbibresource(?:\[[^\]]*\])?\s*\{([^{}]+)\}")
CITE_RE = re.compile(
    r"\\(?:cite|citep|citet|citealp|citealt|citeauthor|citeyear|citeyearpar|"
    r"parencite|textcite|autocite|footcite|smartcite|supercite|fullcite|nocite)"
    r"[a-zA-Z*]*(?:\s*\[[^\]]*\]){0,2}\s*\{([^{}]*)\}"
)
LABEL_RE = re.compile(r"\\label\s*\{([^{}]*)\}")
REF_RE = re.compile(r"\\(?:ref|eqref|autoref|pageref|cref|Cref)\s*\{([^{}]*)\}")
USEPACKAGE_RE = re.compile(r"\\usepackage(?:\[[^\]]*\])?\s*\{([^{}]+)\}", re.I)
INERT_ENVIRONMENTS = ("verbatim", "verbatim*", "Verbatim", "lstlisting")
HIGH_RISK_PACKAGES = {
    "catchfile",
    "gnuplottex",
    "luacode",
    "minted",
    "pythontex",
    "sagetex",
    "shellesc",
}
UNSAFE = {
    "shell escape": re.compile(r"\\(?:immediate\s*)?write\s*18\b|\\ShellEscape\b", re.I),
    "direct Lua execution": re.compile(r"\\(?:directlua|latelua|luaexec)\b|\\begin\{luacode\*?\}", re.I),
    "file output": re.compile(r"\\(?:openout|newwrite)\b|\\write\s*\d+\b", re.I),
    "file input primitive": re.compile(r"\\(?:openin|readline)\b|\\read\s*\d+\b", re.I),
    "pipe input": re.compile(r"\\input\s*\{?\s*\|", re.I),
    "raw PDF or special primitive": re.compile(r"\\(?:pdfcatalog|pdfobj|pdfannot|special|catcode)\b", re.I),
    "constructed dangerous control sequence": re.compile(
        r"\\csname\s*(?:write18|directlua|openin|openout|input|read|write)\s*\\endcsname",
        re.I,
    ),
    "launch action": re.compile(r"\\(?:href|url)\s*\{\s*(?:run|file|javascript):", re.I),
}


def strip_comments(text: str) -> str:
    output: list[str] = []
    for line in text.splitlines():
        cut = len(line)
        for index, char in enumerate(line):
            if char != "%":
                continue
            cursor = index - 1
            backslashes = 0
            while cursor >= 0 and line[cursor] == "\\":
                backslashes += 1
                cursor -= 1
            if backslashes % 2 == 0:
                cut = index
                break
        output.append(line[:cut])
    return "\n".join(output)


def strip_inert_content(text: str) -> str:
    result = text
    for environment in INERT_ENVIRONMENTS:
        result = re.sub(
            rf"\\begin\{{{re.escape(environment)}\}}.*?\\end\{{{re.escape(environment)}\}}",
            "",
            result,
            flags=re.DOTALL,
        )
    return re.sub(r"\\verb\*?(?P<d>[^A-Za-z\s]).*?(?P=d)", "", result)


def split_list(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _raw_path_is_safe(raw: str) -> bool:
    value = raw.strip()
    return (
        bool(value)
        and not any(token in value for token in ("\x00", "|", "\\", "#", "$", "{", "}"))
        and not value.startswith(("~", "/"))
    )


def candidate_paths(base: Path, raw: str, extensions: Iterable[str]) -> list[Path]:
    candidate = base / raw.strip()
    return [candidate] if candidate.suffix else [candidate.with_suffix(ext) for ext in extensions]


def resolve_existing(
    root: Path,
    bases: Iterable[Path],
    raw: str,
    extensions: Iterable[str],
) -> Path | None:
    if not _raw_path_is_safe(raw):
        return None
    for base in bases:
        for candidate in candidate_paths(base, raw, extensions):
            if not within(root, candidate):
                continue
            try:
                info = candidate.lstat()
            except FileNotFoundError:
                continue
            except OSError:
                return None
            if not candidate.is_symlink() and candidate.is_file() and info.st_nlink == 1:
                try:
                    return candidate.resolve(strict=True)
                except (OSError, RuntimeError):
                    return None
            return None
    return None


def _entry_end(text: str, opener_index: int, opener: str, closer: str) -> int | None:
    depth = 1
    quoted = False
    escaped = False
    for index in range(opener_index + 1, len(text)):
        char = text[index]
        if escaped:
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == '"':
            quoted = not quoted
        elif not quoted and char == opener:
            depth += 1
        elif not quoted and char == closer:
            depth -= 1
            if depth == 0:
                return index
    return None


def parse_bibtex_keys(text: str, label: str) -> tuple[list[str], list[str]]:
    """Extract real top-level entry keys; ignore comments, preambles, and strings."""
    keys: list[str] = []
    errors: list[str] = []
    cursor = 0
    while True:
        at = text.find("@", cursor)
        if at < 0:
            break
        match = re.match(r"@\s*([A-Za-z]+)\s*([({])", text[at:])
        if not match:
            cursor = at + 1
            continue
        entry_type = match.group(1).lower()
        opener = match.group(2)
        closer = "}" if opener == "{" else ")"
        opener_index = at + match.end() - 1
        end = _entry_end(text, opener_index, opener, closer)
        if end is None:
            errors.append(f"{label}: unterminated BibTeX entry near offset {at}")
            break
        if entry_type not in {"comment", "preamble", "string"}:
            body = text[opener_index + 1 : end]
            comma = body.find(",")
            if comma < 0:
                errors.append(f"{label}: BibTeX entry near offset {at} has no key separator")
            else:
                key = body[:comma].strip()
                if not key or re.search(r"[\s{}()@]", key):
                    errors.append(f"{label}: invalid BibTeX key {key!r} near offset {at}")
                else:
                    keys.append(key)
        cursor = end + 1
    return keys, errors


def _read_tex_graph(
    root: Path,
    main: Path,
    allow_placeholders: bool,
    errors: list[str],
) -> tuple[list[tuple[Path, str]], list[Path]]:
    pending = [main]
    visited: set[Path] = set()
    combined: list[tuple[Path, str]] = []
    graphic_dirs: list[Path] = [root]
    while pending:
        path = pending.pop()
        if path in visited:
            continue
        visited.add(path)
        try:
            text = strip_inert_content(strip_comments(read_text(path)))
        except ValidationError as exc:
            errors.append(str(exc))
            continue
        combined.append((path, text))
        label = path.relative_to(root)
        if not allow_placeholders and has_placeholder(text):
            errors.append(f"placeholder remains in {label}")
        for name, pattern in UNSAFE.items():
            if pattern.search(text):
                errors.append(f"unsafe LaTeX primitive ({name}) in {label}")
        for package_list in USEPACKAGE_RE.findall(text):
            for package in split_list(package_list):
                if package.lower() in HIGH_RISK_PACKAGES:
                    errors.append(f"high-risk LaTeX package '{package}' in {label}")
        for block in GRAPHICSPATH_RE.findall(text):
            for raw_dir in re.findall(r"\{([^{}]+)\}", block):
                directory = path.parent / raw_dir
                if not _raw_path_is_safe(raw_dir) or not within(root, directory):
                    errors.append(f"unsafe graphicspath '{raw_dir}' in {label}")
                else:
                    graphic_dirs.append(directory)
        for raw in INPUT_RE.findall(text) + UNBRACED_INPUT_RE.findall(text):
            child = resolve_existing(root, (path.parent,), raw, (".tex",))
            if child is None:
                errors.append(f"missing or unsafe input '{raw}' in {label}")
            else:
                pending.append(child)
        for directory, raw in IMPORT_RE.findall(text):
            base = path.parent / directory
            child = None
            if _raw_path_is_safe(directory) and within(root, base):
                child = resolve_existing(root, (base,), raw, (".tex",))
            if child is None:
                errors.append(f"missing or unsafe imported input '{directory}{raw}' in {label}")
            else:
                pending.append(child)
    return combined, graphic_dirs


def _collect_document_data(
    root: Path,
    combined: list[tuple[Path, str]],
    graphic_dirs: list[Path],
    errors: list[str],
) -> tuple[list[str], list[str], list[str], list[Path], list[str]]:
    labels: list[str] = []
    refs: list[str] = []
    citations: list[str] = []
    bib_paths: list[Path] = []
    graphics: list[str] = []
    for path, text in combined:
        relative = path.relative_to(root)
        labels.extend(LABEL_RE.findall(text))
        refs.extend(REF_RE.findall(text))
        for value in CITE_RE.findall(text):
            if not value.strip():
                errors.append(f"empty citation command in {relative}")
            citations.extend(split_list(value))
        for value in BIB_RE.findall(text):
            for item in split_list(value):
                candidate = resolve_existing(root, (path.parent,), item, (".bib",))
                if candidate is None:
                    errors.append(f"missing or unsafe bibliography '{item}' in {relative}")
                else:
                    bib_paths.append(candidate)
        for value in ADDBIB_RE.findall(text):
            candidate = resolve_existing(root, (path.parent,), value, (".bib",))
            if candidate is None:
                errors.append(f"missing or unsafe bibliography '{value}' in {relative}")
            else:
                bib_paths.append(candidate)
        for value in GRAPHICS_RE.findall(text):
            graphics.append(value)
            candidate = resolve_existing(
                root,
                (path.parent, *graphic_dirs),
                value,
                (".pdf", ".png", ".jpg", ".jpeg", ".eps", ".svg"),
            )
            if candidate is None:
                errors.append(f"missing or unsafe graphic '{value}' in {relative}")
    return labels, refs, citations, bib_paths, graphics


def _check_cross_references(labels: list[str], refs: list[str], errors: list[str]) -> None:
    if any(not key.strip() for key in labels):
        errors.append("empty LaTeX label")
    if any(not key.strip() for key in refs):
        errors.append("empty LaTeX reference")
    for key, count in Counter(labels).items():
        if key and count > 1:
            errors.append(f"duplicate LaTeX label: {key}")
    for key in sorted(set(refs) - set(labels)):
        if key:
            errors.append(f"unresolved LaTeX reference: {key}")


def _check_bibliography(
    root: Path,
    bib_paths: list[Path],
    citations: list[str],
    errors: list[str],
) -> int:
    bib_keys: set[str] = set()
    locations: dict[str, list[str]] = defaultdict(list)
    for path in sorted(set(bib_paths)):
        try:
            text = strip_comments(read_text(path))
        except ValidationError as exc:
            errors.append(str(exc))
            continue
        keys, parse_errors = parse_bibtex_keys(text, str(path.relative_to(root)))
        errors.extend(parse_errors)
        for key in keys:
            locations[key].append(str(path.relative_to(root)))
        bib_keys.update(keys)
    for key, paths in sorted(locations.items()):
        if len(paths) > 1:
            errors.append(f"duplicate bibliography key '{key}' across entries: {paths}")
    for key in sorted({item for item in citations if item != "*"} - bib_keys):
        errors.append(f"unresolved citation key: {key}")
    if any(item != "*" for item in citations) and not bib_paths:
        errors.append("citations are present but no bibliography file was resolved")
    return len(bib_keys)


def _check_compiler_log(
    root: Path,
    compiler_log: Path | None,
    errors: list[str],
    warnings: list[str],
) -> None:
    if compiler_log is None:
        return
    path = compiler_log if compiler_log.is_absolute() else root / compiler_log
    if not within(root, path):
        errors.append("compiler log escapes manuscript root")
        return
    try:
        text = read_text(path, max_bytes=20_000_000)
    except ValidationError as exc:
        errors.append(str(exc))
        return
    if re.search(r"LaTeX Warning:.*undefined", text, re.I):
        errors.append("compiler log reports undefined references or citations")
    if re.search(r"^! (?:LaTeX|Package|Class) Error:", text, re.M):
        errors.append("compiler log reports a LaTeX, package, or class error")
    if "Overfull \\hbox" in text or "Overfull \\vbox" in text:
        warnings.append("compiler log reports overfull boxes")


def audit(
    root: Path,
    main: Path,
    *,
    allow_placeholders: bool = False,
    compiler_log: Path | None = None,
    max_entries: int = DEFAULT_MAX_ENTRIES,
    max_depth: int = DEFAULT_MAX_DEPTH,
    max_total_bytes: int = DEFAULT_MAX_TOTAL_BYTES,
) -> dict[str, object]:
    errors: list[str] = []
    warnings: list[str] = []
    try:
        root = root.resolve(strict=True)
        tree = scan_tree(
            root,
            max_entries=max_entries,
            max_depth=max_depth,
            max_total_bytes=max_total_bytes,
        )
    except (OSError, RuntimeError, ValidationError) as exc:
        return {"passed": False, "errors": [str(exc)], "warnings": [], "metrics": {}}

    main_path = main if main.is_absolute() else root / main
    if not within(root, main_path):
        errors.append("main file escapes the manuscript root")
        main_resolved = None
    else:
        main_resolved = resolve_existing(root, (main_path.parent,), main_path.name, (".tex",))
        if main_resolved is None:
            errors.append(f"missing, linked, or unsafe main file: {main_path}")
    if main_resolved is None:
        return {"passed": False, "errors": errors, "warnings": warnings, "metrics": tree}

    combined, graphic_dirs = _read_tex_graph(root, main_resolved, allow_placeholders, errors)
    labels, refs, citations, bib_paths, graphics = _collect_document_data(
        root, combined, graphic_dirs, errors
    )
    _check_cross_references(labels, refs, errors)
    bibliography_keys = _check_bibliography(root, bib_paths, citations, errors)
    _check_compiler_log(root, compiler_log, errors, warnings)
    metrics = {
        "tree_entries": tree["entries"],
        "tree_files": tree["file_count"],
        "tree_bytes": tree["total_bytes"],
        "tree_depth": tree["max_depth"],
        "tex_files": len(combined),
        "labels": len(labels),
        "references": len(refs),
        "citations": len(citations),
        "bibliography_files": len(set(bib_paths)),
        "bibliography_keys": bibliography_keys,
        "graphics": len(graphics),
    }
    return {"passed": not errors, "errors": errors, "warnings": warnings, "metrics": metrics}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--main", type=Path, default=Path("main.tex"))
    parser.add_argument("--compiler-log", type=Path)
    parser.add_argument("--allow-placeholders", action="store_true")
    parser.add_argument("--max-entries", type=int, default=DEFAULT_MAX_ENTRIES)
    parser.add_argument("--max-depth", type=int, default=DEFAULT_MAX_DEPTH)
    parser.add_argument("--max-total-bytes", type=int, default=DEFAULT_MAX_TOTAL_BYTES)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()
    result = audit(
        args.root.expanduser(),
        args.main,
        allow_placeholders=args.allow_placeholders,
        compiler_log=args.compiler_log,
        max_entries=args.max_entries,
        max_depth=args.max_depth,
        max_total_bytes=args.max_total_bytes,
    )
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
