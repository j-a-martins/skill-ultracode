#!/usr/bin/env python3
"""Conservatively audit a bounded LaTeX manuscript tree."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import _latex_impl
from _common import (
    DEFAULT_MAX_DEPTH,
    DEFAULT_MAX_ENTRIES,
    DEFAULT_MAX_TOTAL_BYTES,
    ValidationError,
    scan_tree,
)

parse_bibtex_keys = _latex_impl.parse_bibtex_keys


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
    """Reject an unsafe root before delegating to the detailed parser."""
    requested = root.expanduser()
    try:
        scan_tree(
            requested,
            max_entries=max_entries,
            max_depth=max_depth,
            max_total_bytes=max_total_bytes,
        )
        resolved = requested.resolve(strict=True)
    except (OSError, RuntimeError, ValidationError) as exc:
        return {"passed": False, "errors": [str(exc)], "warnings": [], "metrics": {}}
    return _latex_impl.audit(
        resolved,
        main,
        allow_placeholders=allow_placeholders,
        compiler_log=compiler_log,
        max_entries=max_entries,
        max_depth=max_depth,
        max_total_bytes=max_total_bytes,
    )


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
        args.root,
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
