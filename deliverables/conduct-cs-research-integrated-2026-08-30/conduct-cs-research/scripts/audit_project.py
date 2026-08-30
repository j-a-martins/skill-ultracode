#!/usr/bin/env python3
"""Audit a mode-proportionate research workspace for integrity and readiness defects."""

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
    sha256_file,
    split_ids,
    within,
)

STAGES_BY_MODE = {
    "full-research-lifecycle": [
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
    ],
    "systematic-search": [
        "intake",
        "protocol",
        "search",
        "screening",
        "extraction",
        "synthesis",
        "internal-review",
        "archived",
    ],
    "peer-review": ["intake", "review", "final", "archived"],
    "scientific-prose": ["intake", "revision", "final", "archived"],
}

COMMON_FILES = ["project.json", "state.json", "governance/charter.md"]
REQUIRED_FILES_BY_MODE = {
    "full-research-lifecycle": [
        "protocol/protocol.md",
        "protocol/amendments.md",
        "evidence/sources.csv",
        "evidence/search-protocol.md",
        "evidence/search-log.csv",
        "evidence/screening.csv",
        "evidence/extraction.csv",
        "evidence/synthesis.md",
        "study/runs.csv",
        "study/results.csv",
        "study/deviations.md",
        "claims/claims.csv",
        "manuscript/main.tex",
        "manuscript/references.bib",
        "manuscript/revision-log.csv",
        "manuscript/protected-spans.txt",
        "review/review.md",
        "review/findings.csv",
        "review/response-matrix.csv",
        "publication/journals.csv",
        "publication/selected-journal.json",
        "publication/submission-checklist.md",
    ],
    "systematic-search": [
        "protocol/search-protocol.md",
        "protocol/amendments.md",
        "evidence/sources.csv",
        "evidence/search-log.csv",
        "evidence/screening.csv",
        "evidence/extraction.csv",
        "evidence/synthesis.md",
        "evidence/search-audit.md",
        "claims/claims.csv",
    ],
    "peer-review": [
        "evidence/sources.csv",
        "review/review.md",
        "review/findings.csv",
        "review/response-matrix.csv",
    ],
    "scientific-prose": [
        "manuscript/revision-log.csv",
        "manuscript/protected-spans.txt",
        "manuscript/residual-concerns.md",
    ],
}

CSV_REQUIREMENTS = {
    "evidence/sources.csv": ["source_id", "title", "status", "evidence_level"],
    "evidence/search-log.csv": ["search_id", "source", "interface", "query", "executed_at", "result_count"],
    "evidence/screening.csv": ["record_id", "stage", "decision", "exclusion_reason"],
    "evidence/extraction.csv": ["record_id", "method", "outcomes", "limitations", "evidence_access"],
    "study/runs.csv": ["run_id", "kind", "code_version", "data_version", "raw_output", "status"],
    "study/results.csv": ["result_id", "run_ids", "analysis_code", "estimate", "uncertainty", "status"],
    "claims/claims.csv": ["claim_id", "text", "source_ids", "result_ids", "status", "limitations"],
    "manuscript/revision-log.csv": ["revision_id", "source_path", "revised_path", "scope", "status"],
    "review/findings.csv": ["finding_id", "severity", "location", "finding", "evidence", "consequence", "action", "status"],
    "review/response-matrix.csv": ["comment_id", "comment", "assessment", "action", "status"],
    "publication/journals.csv": ["journal", "provider", "metric_year", "category", "quartile", "verification_url", "verified_date"],
}

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
ACTIVE_EXCLUDED = {"withdrawn", "rejected", "superseded"}


def _stage_at_least(mode: str, stage: str, required: str) -> bool:
    order = STAGES_BY_MODE[mode]
    return order.index(stage) >= order.index(required)


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


def _check_external_actions(root: Path, state: dict[str, Any], errors: list[str]) -> None:
    actions = state.get("external_actions", [])
    if not isinstance(actions, list):
        errors.append("state.external_actions must be a list")
        return
    allowed_status = {"prepared", "authorized", "performed", "failed", "cancelled"}
    for index, action in enumerate(actions):
        prefix = f"external_actions[{index}]"
        if not isinstance(action, dict):
            errors.append(f"{prefix} must be an object")
            continue
        status = action.get("status")
        if status not in allowed_status:
            errors.append(f"{prefix} has invalid status {status!r}")
            continue
        if status in {"authorized", "performed", "failed"}:
            for field in ("action", "destination", "authorized_at"):
                if not isinstance(action.get(field), str) or not action[field].strip():
                    errors.append(f"{prefix} lacks nonempty {field}")
            payload = action.get("payload")
            if not isinstance(payload, list) or not payload:
                errors.append(f"{prefix} lacks an exact payload list")
            else:
                for item_index, item in enumerate(payload):
                    item_prefix = f"{prefix}.payload[{item_index}]"
                    if not isinstance(item, dict):
                        errors.append(f"{item_prefix} must be an object")
                        continue
                    relative = item.get("path")
                    expected = str(item.get("sha256", "")).lower()
                    if not isinstance(relative, str) or not relative.strip():
                        errors.append(f"{item_prefix} lacks path")
                        continue
                    if not SHA256_RE.fullmatch(expected):
                        errors.append(f"{item_prefix} has invalid sha256")
                        continue
                    candidate = root / relative
                    if not within(root, candidate):
                        errors.append(f"{item_prefix} path escapes project")
                        continue
                    try:
                        actual = sha256_file(candidate)
                    except ValidationError as exc:
                        errors.append(f"{item_prefix}: {exc}")
                        continue
                    if actual != expected:
                        errors.append(f"{item_prefix} payload hash does not match current bytes")
        if status in {"performed", "failed"}:
            for field in ("performed_at", "outcome"):
                if not isinstance(action.get(field), str) or not action[field].strip():
                    errors.append(f"{prefix} lacks nonempty {field}")


def _check_sources_and_claims(
    sources: list[dict[str, str]],
    claims: list[dict[str, str]],
    results: list[dict[str, str]],
    errors: list[str],
    warnings: list[str],
) -> tuple[set[str], set[str], set[str]]:
    source_ids = _ids(sources, "source_id", errors, "evidence/sources.csv")
    result_ids = _ids(results, "result_id", errors, "study/results.csv")
    claim_ids = _ids(claims, "claim_id", errors, "claims/claims.csv")
    source_by_id = {row.get("source_id", ""): row for row in sources if row.get("source_id")}
    allowed_evidence = {"metadata", "abstract", "full-text", "data", "code", "artifact"}
    for index, row in enumerate(sources, start=2):
        level = row.get("evidence_level", "")
        if level and level not in allowed_evidence:
            errors.append(f"evidence/sources.csv:{index}: invalid evidence_level '{level}'")
        if row.get("status", "").lower() == "retracted" and "retract" not in row.get("notes", "").lower():
            warnings.append(f"evidence/sources.csv:{index}: retracted source lacks explanatory note")

    active_claim_ids: set[str] = set()
    for index, row in enumerate(claims, start=2):
        status = row.get("status", "").lower()
        active = status not in ACTIVE_EXCLUDED
        claim_id = row.get("claim_id", "")
        if active and claim_id:
            active_claim_ids.add(claim_id)
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
        retracted = [
            value
            for value in linked_sources
            if source_by_id.get(value, {}).get("status", "").lower() == "retracted"
        ]
        if active and retracted:
            disclosure = (row.get("text", "") + " " + row.get("limitations", "")).lower()
            if "retract" not in disclosure:
                errors.append(f"claims/claims.csv:{index}: active claim uses retracted source without disclosure")
            non_retracted = [value for value in linked_sources if value not in retracted]
            if not non_retracted and not linked_results and "retract" not in row.get("text", "").lower():
                errors.append(f"claims/claims.csv:{index}: retracted source is the sole support for an active non-retraction claim")
    return source_ids, result_ids, active_claim_ids


def audit(root: Path) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    metrics: dict[str, Any] = {}
    if not root.exists() or not root.is_dir() or root.is_symlink():
        return {"passed": False, "errors": [f"project directory is missing or linked: {root}"], "warnings": [], "metrics": {}}

    _check_tree(root, errors)
    for relative in COMMON_FILES:
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
    if mode not in STAGES_BY_MODE:
        errors.append(f"invalid project mode: {mode!r}")
        return {"passed": False, "errors": errors, "warnings": warnings, "metrics": metrics}
    stage = state.get("stage")
    if stage not in STAGES_BY_MODE[mode]:
        errors.append(f"invalid stage {stage!r} for mode {mode}")
    gates = state.get("completed_gates")
    if not isinstance(gates, list) or any(not isinstance(item, str) for item in gates):
        errors.append("state.completed_gates must be a list of strings")
    if errors:
        return {"passed": False, "errors": errors, "warnings": warnings, "metrics": metrics}

    for relative in REQUIRED_FILES_BY_MODE[mode]:
        if not (root / relative).is_file():
            errors.append(f"missing required file for {mode}: {relative}")

    tables: dict[str, list[dict[str, str]]] = {}
    for relative in CSV_REQUIREMENTS:
        if (root / relative).exists():
            _, rows = _load_csv(root, relative, errors)
            tables[relative] = rows

    sources = tables.get("evidence/sources.csv", [])
    runs = tables.get("study/runs.csv", [])
    results = tables.get("study/results.csv", [])
    claims = tables.get("claims/claims.csv", [])
    findings = tables.get("review/findings.csv", [])
    revisions = tables.get("manuscript/revision-log.csv", [])
    run_ids = _ids(runs, "run_id", errors, "study/runs.csv")
    _ids(findings, "finding_id", errors, "review/findings.csv")
    _ids(revisions, "revision_id", errors, "manuscript/revision-log.csv")
    _ids(tables.get("evidence/search-log.csv", []), "search_id", errors, "evidence/search-log.csv")
    _, _, active_claim_ids = _check_sources_and_claims(sources, claims, results, errors, warnings)

    for index, row in enumerate(results, start=2):
        for value in split_ids(row.get("run_ids", "")):
            if value not in run_ids:
                errors.append(f"study/results.csv:{index}: unknown run_id '{value}'")

    _check_external_actions(root, state, errors)

    metrics.update(
        {
            "mode": mode,
            "stage": stage,
            "sources": len(sources),
            "runs": len(runs),
            "results": len(results),
            "claims": len(claims),
            "findings": len(findings),
            "revisions": len(revisions),
            "files": sum(1 for path in root.rglob("*") if path.is_file()),
        }
    )

    if mode == "full-research-lifecycle":
        if _stage_at_least(mode, stage, "question"):
            if not nonempty_without_placeholder(root / "governance/charter.md"):
                errors.append("question stage requires a completed governance/charter.md")
            if not _gate_done(state, "question"):
                errors.append("question stage requires completed_gates to include 'question'")
        if _stage_at_least(mode, stage, "protocol"):
            if not nonempty_without_placeholder(root / "protocol/protocol.md"):
                errors.append("protocol stage requires a completed protocol/protocol.md")
            if not _gate_done(state, "protocol"):
                errors.append("protocol stage requires completed_gates to include 'protocol'")
        if _stage_at_least(mode, stage, "pilot") and not _gate_done(state, "pilot"):
            errors.append("pilot stage requires completed_gates to include 'pilot'")
        if _stage_at_least(mode, stage, "execution"):
            if not runs:
                errors.append("execution stage requires at least one run record")
            if not _gate_done(state, "execution"):
                errors.append("execution stage requires completed_gates to include 'execution'")
        if _stage_at_least(mode, stage, "analysis"):
            if not results:
                errors.append("analysis stage requires at least one result record")
            if not _gate_done(state, "analysis"):
                errors.append("analysis stage requires completed_gates to include 'analysis'")
            if str(project.get("study_family", "")).lower() in {"systematic-review", "scoping-review", "mapping-study"}:
                if not tables.get("evidence/search-log.csv"):
                    errors.append("review study at analysis stage requires search-log records")
        if _stage_at_least(mode, stage, "manuscript"):
            if not active_claim_ids:
                errors.append("manuscript stage requires at least one active claim")
            try:
                manuscript = read_text(root / "manuscript/main.tex")
            except ValidationError as exc:
                errors.append(str(exc))
                manuscript = ""
            if has_placeholder(manuscript):
                errors.append("manuscript stage contains unresolved placeholders in manuscript/main.tex")
            for claim_id in active_claim_ids:
                if f"claim:{claim_id}" not in manuscript:
                    errors.append(f"manuscript/main.tex lacks marker for active claim {claim_id}")
            if not _gate_done(state, "manuscript"):
                errors.append("manuscript stage requires completed_gates to include 'manuscript'")
        if _stage_at_least(mode, stage, "internal-review"):
            if not nonempty_without_placeholder(root / "review/review.md"):
                errors.append("internal-review stage requires a completed review/review.md")
            if not findings:
                errors.append("internal-review stage requires structured finding records")
            if not _gate_done(state, "internal-review"):
                errors.append("internal-review stage requires completed_gates to include 'internal-review'")
        if _stage_at_least(mode, stage, "journal-selection"):
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
        if _stage_at_least(mode, stage, "submission-ready"):
            if not nonempty_without_placeholder(root / "publication/submission-checklist.md"):
                errors.append("submission-ready stage requires a completed submission checklist")
            if not _gate_done(state, "submission-package"):
                errors.append("submission-ready stage requires completed_gates to include 'submission-package'")
        if _stage_at_least(mode, stage, "revision"):
            if not tables.get("review/response-matrix.csv"):
                errors.append("revision stage requires response-matrix records")
            if not _gate_done(state, "revision"):
                errors.append("revision stage requires completed_gates to include 'revision'")
        if _stage_at_least(mode, stage, "accepted") and not _gate_done(state, "accepted"):
            errors.append("accepted stage requires completed_gates to include 'accepted'")
        if _stage_at_least(mode, stage, "archived") and not _gate_done(state, "archived"):
            errors.append("archived stage requires completed_gates to include 'archived'")

    elif mode == "systematic-search":
        if _stage_at_least(mode, stage, "protocol"):
            if not nonempty_without_placeholder(root / "governance/charter.md"):
                errors.append("protocol stage requires a completed governance/charter.md")
            if not nonempty_without_placeholder(root / "protocol/search-protocol.md"):
                errors.append("protocol stage requires a completed search protocol")
            if not _gate_done(state, "protocol"):
                errors.append("protocol stage requires completed_gates to include 'protocol'")
        if _stage_at_least(mode, stage, "search"):
            if not tables.get("evidence/search-log.csv"):
                errors.append("search stage requires search-log records")
            if not _gate_done(state, "search"):
                errors.append("search stage requires completed_gates to include 'search'")
        if _stage_at_least(mode, stage, "screening"):
            if not tables.get("evidence/screening.csv"):
                errors.append("screening stage requires screening records")
            if not _gate_done(state, "screening"):
                errors.append("screening stage requires completed_gates to include 'screening'")
        if _stage_at_least(mode, stage, "extraction"):
            if not tables.get("evidence/extraction.csv"):
                errors.append("extraction stage requires extraction records")
            if not _gate_done(state, "extraction"):
                errors.append("extraction stage requires completed_gates to include 'extraction'")
        if _stage_at_least(mode, stage, "synthesis"):
            if not nonempty_without_placeholder(root / "evidence/synthesis.md"):
                errors.append("synthesis stage requires a completed evidence synthesis")
            if not active_claim_ids:
                errors.append("synthesis stage requires at least one evidence-linked active claim")
            if not _gate_done(state, "synthesis"):
                errors.append("synthesis stage requires completed_gates to include 'synthesis'")
        if _stage_at_least(mode, stage, "internal-review"):
            if not nonempty_without_placeholder(root / "evidence/search-audit.md"):
                errors.append("internal-review stage requires a completed search audit")
            if not _gate_done(state, "internal-review"):
                errors.append("internal-review stage requires completed_gates to include 'internal-review'")
        if _stage_at_least(mode, stage, "archived") and not _gate_done(state, "archived"):
            errors.append("archived stage requires completed_gates to include 'archived'")

    elif mode == "peer-review":
        if _stage_at_least(mode, stage, "review"):
            if not nonempty_without_placeholder(root / "governance/charter.md"):
                errors.append("review stage requires a completed governance/charter.md")
            if not nonempty_without_placeholder(root / "review/review.md"):
                errors.append("review stage requires a completed review/review.md")
            if not findings:
                errors.append("review stage requires structured finding records")
            if not _gate_done(state, "review"):
                errors.append("review stage requires completed_gates to include 'review'")
        if _stage_at_least(mode, stage, "final"):
            unresolved = [
                row for row in findings
                if row.get("severity", "").lower() in {"design-limiting", "major"}
                and row.get("status", "").lower() in {"", "open"}
            ]
            if unresolved:
                errors.append("final peer-review stage has unresolved design-limiting or major findings")
            if not _gate_done(state, "final"):
                errors.append("final stage requires completed_gates to include 'final'")
        if _stage_at_least(mode, stage, "archived") and not _gate_done(state, "archived"):
            errors.append("archived stage requires completed_gates to include 'archived'")

    elif mode == "scientific-prose":
        if _stage_at_least(mode, stage, "revision"):
            if not nonempty_without_placeholder(root / "governance/charter.md"):
                errors.append("revision stage requires a completed governance/charter.md")
            if not revisions:
                errors.append("revision stage requires revision-log records")
            if not nonempty_without_placeholder(root / "manuscript/protected-spans.txt"):
                errors.append("revision stage requires a completed protected-spans record")
            if not _gate_done(state, "revision"):
                errors.append("revision stage requires completed_gates to include 'revision'")
        if _stage_at_least(mode, stage, "final"):
            incomplete = [row for row in revisions if row.get("status", "").lower() not in {"complete", "accepted", "resolved"}]
            if incomplete:
                errors.append("final prose stage has incomplete revision-log records")
            if not nonempty_without_placeholder(root / "manuscript/residual-concerns.md"):
                errors.append("final prose stage requires resolved residual-concerns.md")
            if not _gate_done(state, "final"):
                errors.append("final stage requires completed_gates to include 'final'")
        if _stage_at_least(mode, stage, "archived") and not _gate_done(state, "archived"):
            errors.append("archived stage requires completed_gates to include 'archived'")

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
