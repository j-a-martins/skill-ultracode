#!/usr/bin/env python3
"""Perform a conservative static audit of a LaTeX manuscript tree."""

from __future__ import annotations

import argparse
import json
import re
import stat
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable

from _common import ValidationError, has_placeholder, read_text, within

INPUT_RE = re.compile(r"\\(?:input|include|subfile)\s*\{([^{}]+)\}")
UNBRACED_INPUT_RE = re.compile(r"\\(?:input|include)\s+([^\s%{}]+)")
IMPORT_RE = re.compile(r"\\(?:import|subimport|inputfrom|includefrom|subinputfrom|subincludefrom)\s*\{([^{}]+)\}\s*\{([^{}]+)\}")
GRAPHICS_RE = re.compile(r"\\includegraphics(?:\[[^\]]*\])?\s*\{([^{}]+)\}")
GRAPHICSPATH_RE = re.compile(r"\\graphicspath\s*\{((?:\s*\{[^{}]+\}\s*)+)\}")
BIB_RE = re.compile(r"\\bibliography\s*\{([^{}]+)\}")
ADDBIB_RE = re.compile(r"\\addbibresource(?:\[[^\]]*\])?\s*\{([^{}]+)\}")
CITE_RE = re.compile(
    r"\\(?:cite|citep|citet|citealp|citealt|citeauthor|citeyear|citeyearpar|parencite|textcite|autocite|footcite|smartcite|supercite|fullcite|nocite)[a-zA-Z*]*(?:\s*\[[^\]]*\]){0,2}\s*\{([^{}]*)\}"
)
LABEL_RE = re.compile(r"\\label\s*\{([^{}]*)\}")
REF_RE = re.compile(r"\\(?:ref|eqref|autoref|pageref|cref|Cref)\s*\{([^{}]*)\}")
USEPACKAGE_RE = re.compile(r"\\usepackage(?:\[[^\]]*\])?\s*\{([^{}]+)\}", re.IGNORECASE)
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
    "shell escape": re.compile(r"\\(?:immediate\s*)?write\s*18\b|\\ShellEscape\b", re.IGNORECASE),
    "direct Lua execution": re.compile(r"\\(?:directlua|latelua|luaexec)\b|\\begin\{luacode\*?\}", re.IGNORECASE),
    "file output": re.compile(r"\\(?:openout|newwrite)\b|\\write\s*\d+\b", re.IGNORECASE),
    "file input primitive": re.compile(r"\\(?:openin|readline)\b|\\read\s*\d+\b", re.IGNORECASE),
    "pipe input": re.compile(r"\\input\s*\{?\s*\|", re.IGNORECASE),
    "raw PDF or special primitive": re.compile(r"\\(?:pdfcatalog|pdfobj|pdfannot|special|catcode)\b", re.IGNORECASE),
    "constructed dangerous control sequence": re.compile(r"\\csname\s*(?:write18|directlua|openin|openout|input|read|write)\s*\\endcsname", re.IGNORECASE),
    "launch action": re.compile(r"\\(?:href|url)\s*\{\s*(?:run|file|javascript):", re.IGNORECASE),
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


def strip_inert_content(text: str) -> str:
    result = text
    for environment in INERT_ENVIRONMENTS:
        result = re.sub(
            rf"\\begin\{{{re.escape(environment)}\}}.*?\\end\{{{re.escape(environment)}\}}",
            "",
            result,
            flags=re.DOTALL,
        )
    # Remove simple \verb and \verb* spans without interpreting their contents.
    result = re.sub(r"\\verb\*?(?P<d>[^A-Za-z\s]).*?(?P=d)", "", result)
    return result


def split_list(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _check_tree(root: Path, errors: list[str]) -> None:
    for path in root.rglob("*"):
        try:
            info = path.lstat()
        except OSError as exc:
            errors.append(f"cannot inspect manuscript path {path}: {exc}")
            continue
        if stat.S_ISLNK(info.st_mode):
            errors.append(f"linked path is not allowed in manuscript tree: {path.relative_to(root)}")
        elif stat.S_ISDIR(info.st_mode):
            continue
        elif stat.S_ISREG(info.st_mode):
            if info.st_nlink != 1:
                errors.append(f"hard-linked manuscript file is not allowed: {path.relative_to(root)}")
        else:
            errors.append(f"special file is not allowed in manuscript tree: {path.relative_to(root)}")


def _raw_path_is_safe(raw: str) -> bool:
    value = raw.strip()
    return bool(value) and not any(token in value for token in ("\x00", "|", "\\", "#", "$", "{", "}")) and not value.startswith(("~", "/"))


def candidate_paths(base: Path, raw: str, extensions: Iterable[str]) -> list[Path]:
    candidate = base / raw.strip()
    if candidate.suffix:
        return [candidate]
    return [candidate.with_suffix(extension) for extension in extensions]


def resolve_existing(root: Path, bases: Iterable[Path], raw: str, extensions: Iterable[str]) -> Path | None:
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
            if stat.S_ISREG(info.st_mode) and info.st_nlink == 1:
                try:
                    return candidate.resolve(strict=True)
                except (OSError, RuntimeError):
                    return None
            return None
    return None


def _find_entry_end(text: str, opener_index: int, opener: str, closer: str) -> int | None:
    depth = 1
    quote = False
    escaped = False
    for index in range(opener_index + 1, len(text)):
        char = text[index]
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == '"':
            quote = not quote
            continue
        if quote:
            continue
        if char == opener:
            depth += 1
        elif char == closer:
            depth -= 1
            if depth == 0:
                return index
    return None


def parse_bibtex_keys(text: str, label: str) -> tuple[list[str], list[str]]:
    """Extract real top-level entry keys while ignoring comments, strings, and embedded @ text."""
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
        end = _find_entry_end(text, opener_index, opener, closer)
        if end is None:
            errors.append(f"{label}: unterminated BibTeX entry near offset {at}")
            break
        if entry_type not in {"comment", "preamble", "string"}:
            body_start = opener_index + 1
            body = text[body_start:end]
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


def audit(root: Path, main: Path, *, allow_placeholders: bool = False, compiler_log: Path | None = None) -> dict[str, object]:
    errors: list[str] = []
    warnings: list[str] = []
    try:
        root = root.resolve(strict=True)
    except (OSError, RuntimeError):
        return {"passed": False, "errors": ["manuscript root cannot be resolved safely"], "warnings": [], "metrics": {}}
    if not root.is_dir() or root.is_symlink():
        return {"passed": False, "errors": ["manuscript root is not a regular directory"], "warnings": [], "metrics": {}}
    _check_tree(root, errors)

    main_path = main if main.is_absolute() else root / main
    if not within(root, main_path):
        return {"passed": False, "errors": ["main file escapes the manuscript root"], "warnings": [], "metrics": {}}
    main_resolved = resolve_existing(root, (main_path.parent,), main_path.name, (".tex",))
    if main_resolved is None:
        return {"passed": False, "errors": [f"missing, linked, or unsafe main file: {main_path}"], "warnings": [], "metrics": {}}

    pending = [main_resolved]
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
        if not allow_placeholders and has_placeholder(text):
            errors.append(f"placeholder remains in {path.relative_to(root)}")
        for label, pattern in UNSAFE.items():
            if pattern.search(text):
                errors.append(f"unsafe LaTeX primitive ({label}) in {path.relative_to(root)}")
        for package_list in USEPACKAGE_RE.findall(text):
            for package in split_list(package_list):
                if package.lower() in HIGH_RISK_PACKAGES:
                    errors.append(f"high-risk LaTeX package '{package}' in {path.relative_to(root)}")
        for block in GRAPHICSPATH_RE.findall(text):
            for raw_dir in re.findall(r"\{([^{}]+)\}", block):
                if not _raw_path_is_safe(raw_dir):
                    errors.append(f"unsafe graphicspath '{raw_dir}' in {path.relative_to(root)}")
                    continue
                directory = path.parent / raw_dir
                if not within(root, directory):
                    errors.append(f"graphicspath escapes root: '{raw_dir}' in {path.relative_to(root)}")
                else:
                    graphic_dirs.append(directory)

        for raw in INPUT_RE.findall(text) + UNBRACED_INPUT_RE.findall(text):
            child = resolve_existing(root, (path.parent,), raw, (".tex",))
            if child is None:
                errors.append(f"missing or unsafe input '{raw}' in {path.relative_to(root)}")
            else:
                pending.append(child)
        for directory, raw in IMPORT_RE.findall(text):
            if not _raw_path_is_safe(directory):
                errors.append(f"unsafe import directory '{directory}' in {path.relative_to(root)}")
                continue
            base = path.parent / directory
            if not within(root, base):
                errors.append(f"import directory escapes root: '{directory}' in {path.relative_to(root)}")
                continue
            child = resolve_existing(root, (base,), raw, (".tex",))
            if child is None:
                errors.append(f"missing or unsafe imported input '{directory}{raw}' in {path.relative_to(root)}")
            else:
                pending.append(child)

    labels: list[str] = []
    refs: list[str] = []
    citations: list[str] = []
    bib_paths: list[Path] = []
    graphics: list[str] = []
    for path, text in combined:
        labels.extend(LABEL_RE.findall(text))
        refs.extend(REF_RE.findall(text))
        for value in CITE_RE.findall(text):
            if not value.strip():
                errors.append(f"empty citation command in {path.relative_to(root)}")
            citations.extend(split_list(value))
        for value in BIB_RE.findall(text):
            for item in split_list(value):
                candidate = resolve_existing(root, (path.parent,), item, (".bib",))
                if candidate is None:
                    errors.append(f"missing or unsafe bibliography '{item}' in {path.relative_to(root)}")
                else:
                    bib_paths.append(candidate)
        for value in ADDBIB_RE.findall(text):
            candidate = resolve_existing(root, (path.parent,), value, (".bib",))
            if candidate is None:
                errors.append(f"missing or unsafe bibliography '{value}' in {path.relative_to(root)}")
            else:
                bib_paths.append(candidate)
        for value in GRAPHICS_RE.findall(text):
            graphics.append(value)
            candidate = resolve_existing(root, (path.parent, *graphic_dirs), value, (".pdf", ".png", ".jpg", ".jpeg", ".eps", ".svg"))
            if candidate is None:
                errors.append(f"missing or unsafe graphic '{value}' in {path.relative_to(root)}")

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

    bib_keys: set[str] = set()
    key_locations: dict[str, list[str]] = defaultdict(list)
    for path in sorted(set(bib_paths)):
        try:
            bib_text = strip_comments(read_text(path))
        except ValidationError as exc:
            errors.append(str(exc))
            continue
        keys, parse_errors = parse_bibtex_keys(bib_text, str(path.relative_to(root)))
        errors.extend(parse_errors)
        for key in keys:
            key_locations[key].append(str(path.relative_to(root)))
        bib_keys.update(keys)
    for key, locations in sorted(key_locations.items()):
        if len(locations) > 1:
            errors.append(f"duplicate bibliography key '{key}' across entries: {locations}")
    for key in sorted({item for item in citations if item != "*"} - bib_keys):
        errors.append(f"unresolved citation key: {key}")
    if any(item != "*" for item in citations) and not bib_paths:
        errors.append("citations are present but no bibliography file was resolved")

    if compiler_log is not None:
        log_path = compiler_log if compiler_log.is_absolute() else root / compiler_log
        if not within(root, log_path):
            errors.append("compiler log escapes manuscript root")
        else:
            try:
                log = read_text(log_path, max_bytes=20_000_000)
            except ValidationError as exc:
                errors.append(str(exc))
            else:
                if re.search(r"LaTeX Warning:.*undefined", log, re.IGNORECASE):
                    errors.append("compiler log reports undefined references or citations")
                if re.search(r"^! (?:LaTeX|Package|Class) Error:", log, re.MULTILINE):
                    errors.append("compiler log reports a LaTeX, package, or class error")
                if "Overfull \\hbox" in log or "Overfull \\vbox" in log:
                    warnings.append("compiler log reports overfull boxes")

    metrics = {
        "tex_files": len(visited),
        "labels": len(labels),
        "references": len(refs),
        "citations": len(citations),
        "bibliography_files": len(set(bib_paths)),
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
