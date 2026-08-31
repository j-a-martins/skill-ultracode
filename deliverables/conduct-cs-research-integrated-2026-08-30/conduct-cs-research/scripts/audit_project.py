#!/usr/bin/env python3
"""Audit a governed research workspace for integrity and readiness defects."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from _common import (
    DEFAULT_MAX_DEPTH,
    DEFAULT_MAX_ENTRIES,
    DEFAULT_MAX_TOTAL_BYTES,
    ValidationError,
    load_json,
    scan_tree,
)
from _project_model import (
    COMMON_FILES,
    CSV_REQUIREMENTS,
    REQUIRED_FILES_BY_MODE,
    SCHEMA_VERSION,
    STAGES_BY_MODE,
)
from _project_records import (
    check_claims,
    check_external_actions,
    check_responses,
    check_results,
    check_review,
    check_revisions,
    check_runs,
    check_search,
    check_sources,
    load_table,
    timestamp,
    validate_gate_sequence,
)
from _project_stages import audit_full, audit_peer_mode, audit_prose_mode, audit_search_mode


def _load_project(root: Path, errors: list[str]) -> tuple[dict[str, Any], dict[str, Any]]:
    for relative in COMMON_FILES:
        if not (root / relative).is_file():
            errors.append(f"missing required file: {relative}")
    try:
        project = load_json(root / "project.json")
        state = load_json(root / "state.json")
    except ValidationError as exc:
        errors.append(str(exc))
        return {}, {}
    if not isinstance(project, dict) or not isinstance(state, dict):
        errors.append("project.json and state.json must contain JSON objects")
        return {}, {}
    if project.get("schema_version") != SCHEMA_VERSION or state.get(
        "schema_version"
    ) != SCHEMA_VERSION:
        errors.append(f"project and state schema_version must be {SCHEMA_VERSION}")
    if not isinstance(project.get("name"), str) or not project["name"].strip():
        errors.append("project.name must be nonempty")
    timestamp(str(project.get("created_at", "")), errors, "project.created_at")
    timestamp(str(state.get("updated_at", "")), errors, "state.updated_at")
    return project, state


def _validate_mode_state(
    project: dict[str, Any], state: dict[str, Any], errors: list[str]
) -> tuple[str | None, str | None]:
    mode = project.get("mode")
    if mode not in STAGES_BY_MODE:
        errors.append(f"invalid project mode: {mode!r}")
        return None, None
    stage = state.get("stage")
    if stage not in STAGES_BY_MODE[mode]:
        errors.append(f"invalid stage {stage!r} for mode {mode}")
        return mode, None
    validate_gate_sequence(mode, stage, state.get("completed_gates"), errors)
    return mode, stage


def _load_tables(
    root: Path, mode: str, errors: list[str]
) -> dict[str, list[dict[str, str]]]:
    for relative in REQUIRED_FILES_BY_MODE[mode]:
        if not (root / relative).is_file():
            errors.append(f"missing required file for {mode}: {relative}")
    tables: dict[str, list[dict[str, str]]] = {}
    for relative in CSV_REQUIREMENTS:
        if (root / relative).exists():
            tables[relative] = load_table(root, relative, errors)
    return tables


def _validate_records(
    root: Path,
    state: dict[str, Any],
    tables: dict[str, list[dict[str, str]]],
    errors: list[str],
    warnings: list[str],
) -> dict[str, Any]:
    source_ids, sources = check_sources(
        root, tables.get("evidence/sources.csv", []), errors, warnings
    )
    search_sets = check_search(root, tables, source_ids, errors, warnings)
    run_ids, runs = check_runs(root, tables.get("study/runs.csv", []), errors)
    result_ids, results = check_results(
        root, tables.get("study/results.csv", []), run_ids, runs, errors
    )
    claims = check_claims(
        sources,
        tables.get("claims/claims.csv", []),
        result_ids,
        results,
        errors,
    )
    findings = tables.get("review/findings.csv", [])
    unresolved_findings = check_review(root, findings, errors)
    responses = tables.get("review/response-matrix.csv", [])
    unresolved_responses = check_responses(responses, errors)
    revisions = tables.get("manuscript/revision-log.csv", [])
    check_revisions(root, revisions, errors, warnings)
    check_external_actions(root, state, errors, warnings)
    return {
        "sources": sources,
        "search_sets": search_sets,
        "runs": runs,
        "results": results,
        "claims": claims,
        "findings": findings,
        "unresolved_findings": unresolved_findings,
        "unresolved_responses": unresolved_responses,
        "revisions": revisions,
    }


def _validate_stage(
    root: Path,
    mode: str,
    stage: str,
    tables: dict[str, list[dict[str, str]]],
    records: dict[str, Any],
    errors: list[str],
    warnings: list[str],
    limits: tuple[int, int, int],
) -> None:
    if mode == "full-research-lifecycle":
        audit_full(
            root,
            stage,
            tables,
            records["runs"],
            records["results"],
            records["claims"],
            records["unresolved_findings"],
            records["unresolved_responses"],
            errors,
            warnings,
            limits,
        )
    elif mode == "systematic-search":
        audit_search_mode(
            root,
            stage,
            tables,
            records["search_sets"],
            records["claims"],
            errors,
        )
    elif mode == "peer-review":
        audit_peer_mode(
            root,
            stage,
            records["findings"],
            records["unresolved_findings"],
            errors,
        )
    else:
        audit_prose_mode(root, stage, records["revisions"], errors)


def audit(
    root: Path,
    *,
    max_entries: int = DEFAULT_MAX_ENTRIES,
    max_depth: int = DEFAULT_MAX_DEPTH,
    max_total_bytes: int = DEFAULT_MAX_TOTAL_BYTES,
) -> dict[str, Any]:
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

    project, state = _load_project(root, errors)
    if not project or not state:
        return {"passed": False, "errors": errors, "warnings": warnings, "metrics": tree}
    mode, stage = _validate_mode_state(project, state, errors)
    if mode is None or stage is None:
        return {"passed": False, "errors": errors, "warnings": warnings, "metrics": tree}
    tables = _load_tables(root, mode, errors)
    records = _validate_records(root, state, tables, errors, warnings)
    limits = (max_entries, max_depth, max_total_bytes)
    _validate_stage(root, mode, stage, tables, records, errors, warnings, limits)
    metrics = {
        "mode": mode,
        "stage": stage,
        "sources": len(records["sources"]),
        "runs": len(records["runs"]),
        "results": len(records["results"]),
        "claims": len(tables.get("claims/claims.csv", [])),
        "findings": len(records["findings"]),
        "revisions": len(records["revisions"]),
        "tree_entries": tree["entries"],
        "tree_files": tree["file_count"],
        "tree_bytes": tree["total_bytes"],
        "tree_depth": tree["max_depth"],
    }
    return {"passed": not errors, "errors": errors, "warnings": warnings, "metrics": metrics}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path)
    parser.add_argument("--max-entries", type=int, default=DEFAULT_MAX_ENTRIES)
    parser.add_argument("--max-depth", type=int, default=DEFAULT_MAX_DEPTH)
    parser.add_argument("--max-total-bytes", type=int, default=DEFAULT_MAX_TOTAL_BYTES)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()
    result = audit(
        args.project.expanduser(),
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
