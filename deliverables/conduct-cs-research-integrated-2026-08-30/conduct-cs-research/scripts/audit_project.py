#!/usr/bin/env python3
"""Audit a governed research workspace for integrity and readiness defects."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import audit_prose
from _common import (
    DEFAULT_MAX_DEPTH,
    DEFAULT_MAX_ENTRIES,
    DEFAULT_MAX_TOTAL_BYTES,
    SHA256_RE,
    ValidationError,
    load_json,
    read_project_bytes,
    read_text,
    scan_tree,
    split_ids,
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


def _screening_key(row: dict[str, str]) -> tuple[str, int, str]:
    stage_order = {"title-abstract": 0, "full-text": 1}
    stage = row.get("stage", "").strip().lower()
    return (row.get("record_id", "").strip(), stage_order.get(stage, 2), stage)


def _load_tables(
    root: Path, mode: str, errors: list[str]
) -> dict[str, list[dict[str, str]]]:
    for relative in REQUIRED_FILES_BY_MODE[mode]:
        if not (root / relative).is_file():
            errors.append(f"missing required file for {mode}: {relative}")
    tables: dict[str, list[dict[str, str]]] = {}
    for relative in CSV_REQUIREMENTS:
        if (root / relative).exists():
            rows = load_table(root, relative, errors)
            if relative == "evidence/screening.csv":
                rows.sort(key=_screening_key)
            tables[relative] = rows
    return tables


def _check_screening_source_consistency(
    rows: list[dict[str, str]], errors: list[str]
) -> None:
    by_record: dict[str, dict[str, set[str]]] = {}
    for row in rows:
        record_id = row.get("record_id", "").strip()
        stage = row.get("stage", "").strip().lower()
        if not record_id or stage not in {"title-abstract", "full-text"}:
            continue
        by_record.setdefault(record_id, {})[stage] = set(split_ids(row.get("source_ids", "")))
    for record_id, stages in sorted(by_record.items()):
        if {"title-abstract", "full-text"} <= set(stages):
            if stages["title-abstract"] != stages["full-text"]:
                errors.append(
                    f"screening record {record_id!r} changes source_ids between title-abstract and full-text stages"
                )


def _decode_verified_project_text(
    root: Path,
    row: dict[str, str],
    path_field: str,
    hash_field: str,
    prefix: str,
    errors: list[str],
) -> str | None:
    raw_path = row.get(path_field, "").strip()
    expected = row.get(hash_field, "").strip().lower()
    if not raw_path or not SHA256_RE.fullmatch(expected):
        return None
    try:
        data = read_project_bytes(root, raw_path)
    except ValidationError as exc:
        errors.append(f"{prefix}: {exc}")
        return None
    if hashlib.sha256(data).hexdigest() != expected:
        errors.append(f"{prefix}: {path_field} hash does not match audited bytes")
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        errors.append(f"{prefix}: {path_field} is not UTF-8")
        return None


def _check_revision_semantics(
    root: Path,
    revisions: list[dict[str, str]],
    errors: list[str],
    warnings: list[str],
) -> None:
    if not revisions:
        return
    try:
        spans = audit_prose.parse_protected_spans(
            read_text(root / "manuscript/protected-spans.txt")
        )
    except ValidationError as exc:
        errors.append(f"manuscript/protected-spans.txt: {exc}")
        return
    for index, row in enumerate(revisions, start=2):
        prefix = f"manuscript/revision-log.csv:{index}"
        original = _decode_verified_project_text(
            root, row, "source_path", "source_sha256", prefix, errors
        )
        revised = _decode_verified_project_text(
            root, row, "revised_path", "revised_sha256", prefix, errors
        )
        if original is None or revised is None:
            continue
        result = audit_prose.audit_text(
            original,
            revised,
            strict=True,
            protected_spans=spans,
        )
        audit_status = row.get("audit_status", "").strip().lower()
        if result["passed"]:
            if audit_status == "fail":
                errors.append(f"{prefix}: audit_status says fail but protected semantic audit passes")
            continue
        if audit_status != "manual-accepted":
            errors.append(f"{prefix}: protected semantic audit failed: {result['errors']}")
            continue
        material = row.get("material_changes", "").strip().lower()
        concerns = row.get("residual_concerns", "").strip().lower()
        if material in {"", "none"} or concerns in {"", "none"}:
            errors.append(
                f"{prefix}: manual acceptance requires a specific material-change rationale and residual concerns"
            )
        else:
            warnings.append(f"{prefix}: protected semantic drift was manually accepted")


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
    _check_screening_source_consistency(
        tables.get("evidence/screening.csv", []), errors
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
    _check_revision_semantics(root, revisions, errors, warnings)
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
        requested = root.expanduser()
        tree = scan_tree(
            requested,
            max_entries=max_entries,
            max_depth=max_depth,
            max_total_bytes=max_total_bytes,
        )
        root = requested.resolve(strict=True)
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
