#!/usr/bin/env python3
"""Audit a compact conduct-cs-research project for structural and provenance defects."""

from __future__ import annotations

import argparse
import json
import re
import stat
import sys
from pathlib import Path
from typing import Any

from _common import (
    ID_PATTERNS,
    ValidationError,
    has_placeholder,
    load_json,
    nonempty_without_placeholder,
    read_csv,
    read_text,
    require_headers,
    split_ids,
)

STAGES = [
    "intake",
    "question",
    "protocol",
    "pilot",
    "execution",
    "analysis",
    "manuscript",
    "internal-review",
    "journal-selection",
    "submission-ready",
    "revision",
    "accepted",
    "archived",
]
MODES = {
    "full-research-lifecycle",
    "systematic-search",
    "peer-review",
    "scientific-prose",
}
CORE_FILES = [
    "project.json",
    "state.json",
    "governance/charter.md",
    "protocol/protocol.md",
    "protocol/amendments.md",
    "evidence/sources.csv",
    "study/runs.csv",
    "study/results.csv",
    "study/deviations.md",
    "claims/claims.csv",
    "manuscript/main.tex",
    "manuscript/references.bib",
    "publication/journals.csv",
    "publication/selected-journal.json",
    "publication/submission-checklist.md",
]
MODE_FILES = {
    "systematic-search": [
        "evidence/search-log.csv",
        "evidence/screening.csv",
        "evidence/extraction.csv",
        "evidence/search-protocol.md",
    ],
    "peer-review": ["review/review.md", "review/response-matrix.csv"],
    "scientific-prose": ["manuscript/revision-log.csv", "manuscript/protected-spans.txt"],
}
CSV_REQUIREMENTS = {
    "evidence/sources.csv": ["source_id", "title", "status", "evidence_level"],
    "study/runs.csv": ["run_id", "kind", "code_version", "data_version", "raw_output", "status"],
    "study/results.csv": ["result_id", "run_ids", "analysis_code", "estimate", "uncertainty", "status"],
    "claims/claims.csv": ["claim_id", "text", "source_ids", "result_ids", "status", "limitations"],
    "publication/journals.csv": ["journal", "provider", "metric_year", "category", "quartile", "verification_url", "verified_date"],
    "evidence/search-log.csv": ["search_id", "source", "interface", "query", "executed_at", "result_count"],
    "evidence/screening.csv": ["record_id", "stage", "decision", "exclusion_reason"],
    "evidence/extraction.csv": ["record_id", "method", "outcomes", "limitations", "evidence_access"],
    "review/response-matrix.csv": ["comment_id", "comment", "assessment", "action", "status"],
    "manuscript/revision-log.csv": ["revision_id", "source_path", "revised_path", "scope", "status"],
}


def _stage_at_least(stage: str, required: str) -> bool:
    return STAGES.index(stage) >= STAGES.index(required)


def _gate_done(state: dict[str, Any], gate: str) -> bool:
    gates = state.get("completed_gates", [])
    return isinstance(gates, list) and gate in gates


def _check_tree(root: Path, errors: list[str]) -> None:
    for path in root.rglob("*"):
        try:
            info = path.lstat()
        except OSError as exc:
            errors.append(f"cannot inspect {path}: {exc}")
            continue
        if stat.S_ISLNK(info.st_mode):
            errors.append(f"linked path is not allowed in governed workspace: {path.relative_to(root)}")
        elif path.is_file() and info.st_nlink != 1:
            errors.append(f"hard-linked file is not allowed: {path.relative_to(root)}")


def _load_csv(root: Path, relative: str, errors: list[str]) -> tuple[list[str], list[dict[str, str]]]:
    path = root / relative
    try:
        headers, rows = read_csv(path)
    except ValidationError as exc:
        errors.append(str(exc))
        return [], []
    errors.extend(require_headers(path, headers, CSV_REQUIREMENTS.get(relative, [])))
    return headers, rows


def _ids(rows: list[dict[str, str]], field: str, errors: list[str], relative: str) -> set[str]:
    pattern = ID_PATTERNS.get(field)
    found: set[str] = set()
    for index, row in enumerate(rows, start=2):
        value = row.get(field, "")
        if not value:
            continue
        if pattern and not pattern.fullmatch(value):
            errors.append(f"{relative}:{index}: invalid {field} '{value}'")
        if value in found:
            errors.append(f"{relative}:{index}: duplicate {field} '{value}'")
        found.add(value)
    return found


def audit(root: Path) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    metrics: dict[str, Any] = {}
    if not root.exists() or not root.is_dir() or root.is_symlink():
        return {"passed": False, "errors": [f"project directory is missing or linked: {root}"], "warnings": [], "metrics": {}}

    _check_tree(root, errors)
    for relative in CORE_FILES:
        if not (root / relative).is_file():
            errors.append(f"missing required file: {relative}")

    try:
        project = load_json(root / "project.json")
        state = load_json(root / "state.json")
    except ValidationError as exc:
        errors.append(str(exc))
        return {"passed": False, "errors": errors, "warnings": warnings, "metrics": metrics}
    if not isinstance(project, dict) or not isinstance(state, dict):
        errors.append("project.json and state.json must contain JSON objects")
        return {"passed": False, "errors": errors, "warnings": warnings, "metrics": metrics}

    mode = project.get("mode")
    stage = state.get("stage")
    if mode not in MODES:
        errors.append(f"invalid project mode: {mode!r}")
    if stage not in STAGES:
        errors.append(f"invalid project stage: {stage!r}")
    if errors:
        return {"passed": False, "errors": errors, "warnings": warnings, "metrics": metrics}

    expected_mode_files: list[str] = []
    if mode == "full-research-lifecycle":
        for values in MODE_FILES.values():
            expected_mode_files.extend(values)
    else:
        expected_mode_files.extend(MODE_FILES.get(mode, []))
    for relative in expected_mode_files:
        if not (root / relative).is_file():
            errors.append(f"missing mode-specific file: {relative}")

    tables: dict[str, list[dict[str, str]]] = {}
    for relative in CSV_REQUIREMENTS:
        if (root / relative).exists():
            _, rows = _load_csv(root, relative, errors)
            tables[relative] = rows

    sources = tables.get("evidence/sources.csv", [])
    runs = tables.get("study/runs.csv", [])
    results = tables.get("study/results.csv", [])
    claims = tables.get("claims/claims.csv", [])
    source_ids = _ids(sources, "source_id", errors, "evidence/sources.csv")
    run_ids = _ids(runs, "run_id", errors, "study/runs.csv")
    result_ids = _ids(results, "result_id", errors, "study/results.csv")
    claim_ids = _ids(claims, "claim_id", errors, "claims/claims.csv")

    allowed_evidence = {"metadata", "abstract", "full-text", "data", "code", "artifact"}
    for index, row in enumerate(sources, start=2):
        level = row.get("evidence_level", "")
        if level and level not in allowed_evidence:
            errors.append(f"evidence/sources.csv:{index}: invalid evidence_level '{level}'")
        if row.get("status") == "retracted" and "retract" not in row.get("notes", "").lower():
            warnings.append(f"evidence/sources.csv:{index}: retracted source lacks explanatory note")

    for index, row in enumerate(results, start=2):
        for value in split_ids(row.get("run_ids", "")):
            if value not in run_ids:
                errors.append(f"study/results.csv:{index}: unknown run_id '{value}'")

    for index, row in enumerate(claims, start=2):
        status = row.get("status", "").lower()
        active = status not in {"withdrawn", "rejected", "superseded"}
        linked_sources = split_ids(row.get("source_ids", ""))
        linked_results = split_ids(row.get("result_ids", ""))
        for value in linked_sources:
            if value not in source_ids:
                errors.append(f"claims/claims.csv:{index}: unknown source_id '{value}'")
        for value in linked_results:
            if value not in result_ids:
                errors.append(f"claims/claims.csv:{index}: unknown result_id '{value}'")
        if active and not (linked_sources or linked_results):
            errors.append(f"claims/claims.csv:{index}: active claim has no evidence link")
        if active and has_placeholder(row.get("text", "")):
            errors.append(f"claims/claims.csv:{index}: active claim contains a placeholder")

    metrics.update(
        {
            "mode": mode,
            "stage": stage,
            "sources": len(sources),
            "runs": len(runs),
            "results": len(results),
            "claims": len(claims),
            "files": sum(1 for path in root.rglob("*") if path.is_file()),
        }
    )

    if _stage_at_least(stage, "question") and not nonempty_without_placeholder(root / "governance/charter.md"):
        errors.append("question stage requires a completed governance/charter.md")
    if _stage_at_least(stage, "protocol"):
        if not nonempty_without_placeholder(root / "protocol/protocol.md"):
            errors.append("protocol stage requires a completed protocol/protocol.md")
        if not _gate_done(state, "protocol"):
            errors.append("protocol stage requires completed_gates to include 'protocol'")
    if _stage_at_least(stage, "execution"):
        if not runs:
            errors.append("execution stage requires at least one run record")
        if not _gate_done(state, "execution"):
            errors.append("execution stage requires completed_gates to include 'execution'")
    if _stage_at_least(stage, "analysis"):
        if not results:
            errors.append("analysis stage requires at least one result record")
        if not _gate_done(state, "analysis"):
            errors.append("analysis stage requires completed_gates to include 'analysis'")
        if mode in {"systematic-search", "full-research-lifecycle"}:
            if not tables.get("evidence/search-log.csv"):
                errors.append("analysis stage for a search-capable project requires search-log records")
    if _stage_at_least(stage, "manuscript"):
        if not claims:
            errors.append("manuscript stage requires at least one claim record")
        try:
            manuscript = read_text(root / "manuscript/main.tex")
        except ValidationError as exc:
            errors.append(str(exc))
            manuscript = ""
        if has_placeholder(manuscript):
            errors.append("manuscript stage contains unresolved placeholders in manuscript/main.tex")
        for claim_id in claim_ids:
            if f"claim:{claim_id}" not in manuscript:
                errors.append(f"manuscript/main.tex lacks marker for {claim_id}")
        if not _gate_done(state, "manuscript"):
            errors.append("manuscript stage requires completed_gates to include 'manuscript'")
    if _stage_at_least(stage, "internal-review"):
        if not nonempty_without_placeholder(root / "review/review.md"):
            errors.append("internal-review stage requires a completed review/review.md")
        if not _gate_done(state, "internal-review"):
            errors.append("internal-review stage requires completed_gates to include 'internal-review'")
    if _stage_at_least(stage, "journal-selection"):
        try:
            selected = load_json(root / "publication/selected-journal.json")
        except ValidationError as exc:
            errors.append(str(exc))
            selected = {}
        needed = {"journal", "fit_rationale", "verified_at"}
        if not isinstance(selected, dict) or not needed.issubset(selected):
            errors.append("journal-selection stage requires journal, fit_rationale, and verified_at in selected-journal.json")
        if not _gate_done(state, "journal-selection"):
            errors.append("journal-selection stage requires completed_gates to include 'journal-selection'")
    if _stage_at_least(stage, "submission-ready"):
        if not nonempty_without_placeholder(root / "publication/submission-checklist.md"):
            errors.append("submission-ready stage requires a completed submission checklist")
        if not _gate_done(state, "submission-package"):
            errors.append("submission-ready stage requires completed_gates to include 'submission-package'")

    actions = state.get("external_actions", [])
    if not isinstance(actions, list):
        errors.append("state.external_actions must be a list")
    else:
        for index, action in enumerate(actions):
            if not isinstance(action, dict):
                errors.append(f"external_actions[{index}] must be an object")
                continue
            if action.get("status") == "performed" and not action.get("authorized_at"):
                errors.append(f"external_actions[{index}] is performed without authorized_at")
            if action.get("status") == "performed" and not action.get("destination"):
                errors.append(f"external_actions[{index}] is performed without a destination")

    return {"passed": not errors, "errors": errors, "warnings": warnings, "metrics": metrics}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()
    result = audit(args.project.expanduser())
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
