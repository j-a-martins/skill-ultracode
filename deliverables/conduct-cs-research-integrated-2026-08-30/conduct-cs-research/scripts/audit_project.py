#!/usr/bin/env python3
"""Audit a mode-proportionate research workspace for integrity and readiness defects."""

from __future__ import annotations

import argparse
import json
import re
import stat
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import audit_latex
import audit_prose
import score_journals
from _common import (
    ID_PATTERNS,
    ValidationError,
    has_placeholder,
    load_json,
    nonempty_without_placeholder,
    parse_timestamp,
    read_csv,
    read_text,
    require_headers,
    split_ids,
    verify_path_hash,
)

STAGES_BY_MODE = {
    "full-research-lifecycle": [
        "intake", "question", "protocol", "pilot", "execution", "analysis", "manuscript",
        "internal-review", "journal-selection", "submission-ready", "revision", "accepted", "archived",
    ],
    "systematic-search": ["intake", "protocol", "search", "screening", "extraction", "synthesis", "internal-review", "archived"],
    "peer-review": ["intake", "review", "final", "archived"],
    "scientific-prose": ["intake", "revision", "final", "archived"],
}
GATE_ORDER = {
    "full-research-lifecycle": ["question", "protocol", "pilot", "execution", "analysis", "manuscript", "internal-review", "journal-selection", "submission-package", "revision", "accepted", "archived"],
    "systematic-search": ["protocol", "search", "screening", "extraction", "synthesis", "internal-review", "archived"],
    "peer-review": ["review", "final", "archived"],
    "scientific-prose": ["revision", "final", "archived"],
}
STAGE_GATE = {
    "full-research-lifecycle": {
        "question": "question", "protocol": "protocol", "pilot": "pilot", "execution": "execution",
        "analysis": "analysis", "manuscript": "manuscript", "internal-review": "internal-review",
        "journal-selection": "journal-selection", "submission-ready": "submission-package",
        "revision": "revision", "accepted": "accepted", "archived": "archived",
    },
    "systematic-search": {stage: stage for stage in STAGES_BY_MODE["systematic-search"] if stage != "intake"},
    "peer-review": {stage: stage for stage in STAGES_BY_MODE["peer-review"] if stage != "intake"},
    "scientific-prose": {stage: stage for stage in STAGES_BY_MODE["scientific-prose"] if stage != "intake"},
}

COMMON_FILES = ["project.json", "state.json", "governance/charter.md"]
REQUIRED_FILES_BY_MODE = {
    "full-research-lifecycle": [
        "protocol/protocol.md", "protocol/amendments.md", "study/pilot-decision.json",
        "evidence/sources.csv", "evidence/search-protocol.md", "evidence/search-log.csv",
        "evidence/screening.csv", "evidence/extraction.csv", "evidence/synthesis.md",
        "study/runs.csv", "study/results.csv", "study/deviations.md", "claims/claims.csv",
        "manuscript/main.tex", "manuscript/references.bib", "manuscript/revision-log.csv",
        "manuscript/protected-spans.txt", "review/review.md", "review/summary.json",
        "review/findings.csv", "review/response-matrix.csv", "publication/journals.csv",
        "publication/selected-journal.json", "publication/submission-checklist.md",
        "publication/decision.json", "publication/release-manifest.csv", "publication/correction-plan.md",
    ],
    "systematic-search": [
        "protocol/search-protocol.md", "protocol/amendments.md", "evidence/sources.csv",
        "evidence/search-log.csv", "evidence/deduplication.csv", "evidence/screening.csv",
        "evidence/extraction.csv", "evidence/flow.json", "evidence/synthesis.md",
        "evidence/search-audit.md", "claims/claims.csv",
    ],
    "peer-review": ["evidence/sources.csv", "review/review.md", "review/summary.json", "review/findings.csv", "review/response-matrix.csv"],
    "scientific-prose": ["manuscript/revision-log.csv", "manuscript/protected-spans.txt", "manuscript/residual-concerns.md"],
}
CSV_REQUIREMENTS = {
    "evidence/sources.csv": ["source_id", "title", "status", "evidence_level", "record_path", "record_sha256", "verified_at"],
    "evidence/search-log.csv": ["search_id", "source", "interface", "query", "executed_at", "result_count", "export_path", "export_sha256"],
    "evidence/deduplication.csv": ["cluster_id", "canonical_source_id", "member_source_ids", "method", "resolver"],
    "evidence/screening.csv": ["record_id", "source_ids", "stage", "decision", "exclusion_reason"],
    "evidence/extraction.csv": ["record_id", "source_ids", "method", "outcomes", "limitations", "evidence_access"],
    "study/runs.csv": ["run_id", "kind", "phase", "started_at", "ended_at", "code_version", "code_path", "code_sha256", "data_version", "data_path", "data_sha256", "environment", "environment_path", "environment_sha256", "parameters", "raw_output", "raw_output_sha256", "status"],
    "study/results.csv": ["result_id", "run_ids", "analysis_code", "analysis_code_sha256", "input_paths", "input_sha256s", "estimate", "uncertainty", "robustness", "status"],
    "claims/claims.csv": ["claim_id", "text", "claim_type", "source_ids", "result_ids", "status", "limitations"],
    "manuscript/revision-log.csv": ["revision_id", "source_path", "source_sha256", "revised_path", "revised_sha256", "scope", "protected_content", "material_changes", "residual_concerns", "audit_status", "status"],
    "review/findings.csv": ["finding_id", "severity", "confidence", "location", "finding", "evidence", "consequence", "action", "status"],
    "review/response-matrix.csv": ["comment_id", "comment", "assessment", "rationale", "action", "manuscript_change", "evidence", "residual_limitation", "status"],
    "publication/journals.csv": ["journal", "provider", "metric_name", "metric_year", "category", "quartile", "verification_url", "evidence_path", "evidence_sha256", "verified_date", "human_verified_by", "human_verified_at"],
    "publication/release-manifest.csv": ["artifact", "path", "sha256", "license", "archived_at"],
}

ACTIVE_CLAIM_STATUSES = {"active", "needs-review"}
INACTIVE_CLAIM_STATUSES = {"withdrawn", "rejected", "superseded"}
RESULT_STATUSES = {"draft", "active", "reported", "confirmed", "failed", "withdrawn", "superseded"}
ACTIVE_RESULT_STATUSES = {"active", "reported", "confirmed"}
SOURCE_STATUSES = {"candidate", "included", "verified", "corrected", "excluded", "unresolved", "withdrawn", "retracted"}
SOURCE_INELIGIBLE = {"candidate", "excluded", "unresolved", "withdrawn"}
EVIDENCE_LEVELS = {"metadata", "abstract", "full-text", "data", "code", "artifact"}
FINDING_SEVERITIES = {"design-limiting", "major", "minor", "editorial", "strength"}
FINDING_STATUSES = {"open", "addressed", "partly-addressed", "disputed", "accepted-limitation", "not-applicable"}
CONFIDENCE_LEVELS = {"high", "medium", "low", "not-assessable"}


def _stage_at_least(mode: str, stage: str, required: str) -> bool:
    order = STAGES_BY_MODE[mode]
    return order.index(stage) >= order.index(required)


def _check_tree(root: Path, errors: list[str]) -> None:
    for path in root.rglob("*"):
        try:
            info = path.lstat()
        except OSError as exc:
            errors.append(f"cannot inspect {path}: {exc}")
            continue
        if stat.S_ISLNK(info.st_mode):
            errors.append(f"linked path is not allowed in governed workspace: {path.relative_to(root)}")
        elif stat.S_ISDIR(info.st_mode):
            continue
        elif stat.S_ISREG(info.st_mode):
            if info.st_nlink != 1:
                errors.append(f"hard-linked file is not allowed: {path.relative_to(root)}")
        else:
            errors.append(f"special file is not allowed: {path.relative_to(root)}")


def _load_csv(root: Path, relative: str, errors: list[str]) -> tuple[list[str], list[dict[str, str]]]:
    path = root / relative
    try:
        headers, rows = read_csv(path)
    except ValidationError as exc:
        errors.append(str(exc))
        return [], []
    errors.extend(require_headers(path, headers, CSV_REQUIREMENTS.get(relative, [])))
    return headers, rows


def _ids(rows: list[dict[str, str]], field: str, errors: list[str], relative: str, *, pattern: re.Pattern[str] | None = None) -> set[str]:
    pattern = pattern or ID_PATTERNS.get(field)
    found: set[str] = set()
    for index, row in enumerate(rows, start=2):
        value = row.get(field, "").strip()
        if not value:
            errors.append(f"{relative}:{index}: missing {field}")
            continue
        if pattern and not pattern.fullmatch(value):
            errors.append(f"{relative}:{index}: invalid {field} '{value}'")
        if value in found:
            errors.append(f"{relative}:{index}: duplicate {field} '{value}'")
        found.add(value)
    return found


def _required(row: dict[str, str], fields: tuple[str, ...], errors: list[str], prefix: str) -> None:
    for field in fields:
        if not row.get(field, "").strip():
            errors.append(f"{prefix}: missing {field}")


def _timestamp(value: str, errors: list[str], prefix: str) -> datetime | None:
    try:
        return parse_timestamp(value, field=prefix)
    except ValidationError as exc:
        errors.append(str(exc))
        return None


def _path_hash_pair(root: Path, row: dict[str, str], path_field: str, hash_field: str, errors: list[str], prefix: str, *, required: bool = False) -> Path | None:
    raw_path = row.get(path_field, "").strip()
    raw_hash = row.get(hash_field, "").strip().lower()
    if not raw_path and not raw_hash:
        if required:
            errors.append(f"{prefix}: {path_field} and {hash_field} are required")
        return None
    if not raw_path or not raw_hash:
        errors.append(f"{prefix}: {path_field} and {hash_field} must be supplied together")
        return None
    try:
        return verify_path_hash(root, raw_path, raw_hash, label=f"{prefix} {path_field}")
    except ValidationError as exc:
        errors.append(str(exc))
        return None


def _semicolon_list(value: str) -> list[str]:
    return [item.strip() for item in value.split(";") if item.strip()]


def _validate_gate_sequence(mode: str, stage: str, gates: Any, errors: list[str]) -> list[str]:
    if not isinstance(gates, list) or any(not isinstance(item, str) for item in gates):
        errors.append("state.completed_gates must be a list of strings")
        return []
    if len(gates) != len(set(gates)):
        errors.append("state.completed_gates contains duplicates")
    allowed = GATE_ORDER[mode]
    unknown = sorted(set(gates) - set(allowed))
    if unknown:
        errors.append(f"state.completed_gates contains unknown gates: {unknown}")
    stage_gate = STAGE_GATE[mode].get(stage)
    expected: list[str] = []
    if stage_gate:
        expected = allowed[: allowed.index(stage_gate) + 1]
    missing = [gate for gate in expected if gate not in gates]
    if missing:
        errors.append(f"stage {stage} lacks predecessor gate(s): {missing}")
    future = [gate for gate in gates if gate not in expected]
    if future:
        errors.append(f"stage {stage} records future gate(s): {future}")
    return gates


def _check_external_actions(root: Path, state: dict[str, Any], errors: list[str], warnings: list[str]) -> None:
    actions = state.get("external_actions", [])
    if not isinstance(actions, list):
        errors.append("state.external_actions must be a list")
        return
    allowed_status = {"prepared", "authorized", "performed", "failed", "cancelled"}
    seen: set[str] = set()
    now = datetime.now(timezone.utc)
    for index, action in enumerate(actions):
        prefix = f"external_actions[{index}]"
        if not isinstance(action, dict):
            errors.append(f"{prefix} must be an object")
            continue
        action_id = str(action.get("action_id", ""))
        if not ID_PATTERNS["action_id"].fullmatch(action_id):
            errors.append(f"{prefix} has invalid action_id")
        elif action_id in seen:
            errors.append(f"{prefix} duplicates action_id {action_id}")
        seen.add(action_id)
        status = action.get("status")
        if status not in allowed_status:
            errors.append(f"{prefix} has invalid status {status!r}")
            continue
        if status == "cancelled":
            _required(action, ("action", "destination", "outcome"), errors, prefix)
            continue
        _required(action, ("action", "destination"), errors, prefix)
        payload = action.get("payload")
        if not isinstance(payload, list) or not payload:
            errors.append(f"{prefix} lacks an exact payload list")
        else:
            for item_index, item in enumerate(payload):
                item_prefix = f"{prefix}.payload[{item_index}]"
                if not isinstance(item, dict):
                    errors.append(f"{item_prefix} must be an object")
                    continue
                try:
                    verify_path_hash(root, str(item.get("path", "")), str(item.get("sha256", "")).lower(), label=item_prefix)
                except ValidationError as exc:
                    errors.append(str(exc))
        if status in {"authorized", "performed", "failed"}:
            _required(action, ("authorized_at", "expires_at", "authorized_by", "authorization_statement"), errors, prefix)
            authorized = _timestamp(str(action.get("authorized_at", "")), errors, f"{prefix}.authorized_at")
            expires = _timestamp(str(action.get("expires_at", "")), errors, f"{prefix}.expires_at")
            if authorized and expires:
                if expires <= authorized:
                    errors.append(f"{prefix}: expires_at must follow authorized_at")
                if (expires - authorized).total_seconds() > 48 * 3600:
                    errors.append(f"{prefix}: authorization window exceeds 48 hours")
                if status == "authorized" and expires < now:
                    errors.append(f"{prefix}: authorization has expired")
        else:
            authorized = expires = None
        if status in {"performed", "failed"}:
            _required(action, ("performed_at", "outcome"), errors, prefix)
            performed = _timestamp(str(action.get("performed_at", "")), errors, f"{prefix}.performed_at")
            if performed and authorized and performed < authorized:
                errors.append(f"{prefix}: performed_at precedes authorization")
            if performed and expires and performed > expires:
                errors.append(f"{prefix}: action occurred after authorization expiry")
        if status == "prepared":
            warnings.append(f"{prefix}: prepared is not authorization to transmit")


def _check_sources(root: Path, rows: list[dict[str, str]], errors: list[str], warnings: list[str]) -> tuple[set[str], dict[str, dict[str, str]]]:
    source_ids = _ids(rows, "source_id", errors, "evidence/sources.csv")
    source_by_id = {row.get("source_id", ""): row for row in rows if row.get("source_id")}
    for index, row in enumerate(rows, start=2):
        prefix = f"evidence/sources.csv:{index}"
        _required(row, ("title", "status", "evidence_level"), errors, prefix)
        status = row.get("status", "").lower()
        if status not in SOURCE_STATUSES:
            errors.append(f"{prefix}: invalid status '{status}'")
        level = row.get("evidence_level", "").lower()
        if level not in EVIDENCE_LEVELS:
            errors.append(f"{prefix}: invalid evidence_level '{level}'")
        record_required = status in {"verified", "corrected", "retracted"}
        _path_hash_pair(root, row, "record_path", "record_sha256", errors, prefix, required=record_required)
        verified_at = row.get("verified_at", "").strip()
        if record_required:
            _timestamp(verified_at, errors, f"{prefix}.verified_at")
        elif verified_at:
            _timestamp(verified_at, errors, f"{prefix}.verified_at")
        if status == "retracted" and "retract" not in row.get("notes", "").lower():
            warnings.append(f"{prefix}: retracted source lacks an explanatory note")
    return source_ids, source_by_id


def _check_search(root: Path, tables: dict[str, list[dict[str, str]]], source_ids: set[str], errors: list[str], warnings: list[str]) -> dict[str, set[str]]:
    search_rows = tables.get("evidence/search-log.csv", [])
    _ids(search_rows, "search_id", errors, "evidence/search-log.csv")
    for index, row in enumerate(search_rows, start=2):
        prefix = f"evidence/search-log.csv:{index}"
        _required(row, ("source", "interface", "query", "executed_at", "result_count"), errors, prefix)
        _timestamp(row.get("executed_at", ""), errors, f"{prefix}.executed_at")
        try:
            count = int(row.get("result_count", ""))
            if count < 0:
                raise ValueError
        except ValueError:
            errors.append(f"{prefix}: result_count must be a nonnegative integer")
        export = _path_hash_pair(root, row, "export_path", "export_sha256", errors, prefix)
        if export is None and not (row.get("export_path") or row.get("export_sha256")):
            warnings.append(f"{prefix}: no hash-bound export; explain the reproducible alternative in notes")

    screening = tables.get("evidence/screening.csv", [])
    screening_ids = _ids(screening, "record_id", errors, "evidence/screening.csv", pattern=re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$"))
    included_screening: set[str] = set()
    for index, row in enumerate(screening, start=2):
        prefix = f"evidence/screening.csv:{index}"
        _required(row, ("source_ids", "stage", "decision"), errors, prefix)
        linked = split_ids(row.get("source_ids", ""))
        for value in linked:
            if value not in source_ids:
                errors.append(f"{prefix}: unknown source_id '{value}'")
        stage = row.get("stage", "").lower()
        decision = row.get("decision", "").lower()
        if stage not in {"title-abstract", "full-text"}:
            errors.append(f"{prefix}: invalid screening stage '{stage}'")
        if decision not in {"include", "exclude", "duplicate", "uncertain"}:
            errors.append(f"{prefix}: invalid screening decision '{decision}'")
        if decision == "exclude" and not row.get("exclusion_reason", "").strip():
            errors.append(f"{prefix}: excluded record lacks exclusion_reason")
        if decision == "include" and stage == "full-text":
            included_screening.add(row.get("record_id", ""))

    extraction = tables.get("evidence/extraction.csv", [])
    extraction_ids = _ids(extraction, "record_id", errors, "evidence/extraction.csv", pattern=re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$"))
    for index, row in enumerate(extraction, start=2):
        prefix = f"evidence/extraction.csv:{index}"
        _required(row, ("source_ids", "method", "outcomes", "limitations", "evidence_access"), errors, prefix)
        if row.get("record_id", "") not in included_screening:
            errors.append(f"{prefix}: extraction lacks a corresponding included full-text screening record")
        for value in split_ids(row.get("source_ids", "")):
            if value not in source_ids:
                errors.append(f"{prefix}: unknown source_id '{value}'")
        if row.get("evidence_access", "").lower() not in {"metadata-only", "abstract-reviewed", "full-text-reviewed", "data-code-artifact-reviewed"}:
            errors.append(f"{prefix}: invalid evidence_access")

    dedup = tables.get("evidence/deduplication.csv", [])
    _ids(dedup, "cluster_id", errors, "evidence/deduplication.csv", pattern=re.compile(r"^K\d{4}$"))
    for index, row in enumerate(dedup, start=2):
        prefix = f"evidence/deduplication.csv:{index}"
        _required(row, ("canonical_source_id", "member_source_ids", "method", "resolver"), errors, prefix)
        canonical = row.get("canonical_source_id", "")
        members = split_ids(row.get("member_source_ids", ""))
        if canonical not in source_ids:
            errors.append(f"{prefix}: unknown canonical_source_id '{canonical}'")
        for value in members:
            if value not in source_ids:
                errors.append(f"{prefix}: unknown member source_id '{value}'")
        if canonical and canonical not in members:
            errors.append(f"{prefix}: canonical_source_id must be included in member_source_ids")

    return {"screening_ids": screening_ids, "included_screening": included_screening, "extraction_ids": extraction_ids}


def _check_runs_and_results(root: Path, runs: list[dict[str, str]], results: list[dict[str, str]], errors: list[str]) -> tuple[set[str], dict[str, dict[str, str]], set[str], dict[str, dict[str, str]]]:
    run_ids = _ids(runs, "run_id", errors, "study/runs.csv")
    run_by_id = {row.get("run_id", ""): row for row in runs if row.get("run_id")}
    for index, row in enumerate(runs, start=2):
        prefix = f"study/runs.csv:{index}"
        _required(row, ("kind", "phase", "started_at", "code_version", "data_version", "environment", "parameters", "status"), errors, prefix)
        phase = row.get("phase", "").lower()
        status = row.get("status", "").lower()
        if phase not in {"pilot", "exploratory", "definitive", "replication"}:
            errors.append(f"{prefix}: invalid phase '{phase}'")
        if status not in {"planned", "running", "complete", "failed", "cancelled"}:
            errors.append(f"{prefix}: invalid status '{status}'")
        started = _timestamp(row.get("started_at", ""), errors, f"{prefix}.started_at")
        ended_raw = row.get("ended_at", "").strip()
        ended = _timestamp(ended_raw, errors, f"{prefix}.ended_at") if ended_raw else None
        if status in {"complete", "failed", "cancelled"} and not ended_raw:
            errors.append(f"{prefix}: terminal run lacks ended_at")
        if started and ended and ended < started:
            errors.append(f"{prefix}: ended_at precedes started_at")
        _path_hash_pair(root, row, "code_path", "code_sha256", errors, prefix)
        _path_hash_pair(root, row, "data_path", "data_sha256", errors, prefix)
        _path_hash_pair(root, row, "environment_path", "environment_sha256", errors, prefix)
        _path_hash_pair(root, row, "raw_output", "raw_output_sha256", errors, prefix, required=status == "complete")

    result_ids = _ids(results, "result_id", errors, "study/results.csv")
    result_by_id = {row.get("result_id", ""): row for row in results if row.get("result_id")}
    for index, row in enumerate(results, start=2):
        prefix = f"study/results.csv:{index}"
        _required(row, ("run_ids", "analysis_code", "estimate", "uncertainty", "robustness", "status"), errors, prefix)
        status = row.get("status", "").lower()
        if status not in RESULT_STATUSES:
            errors.append(f"{prefix}: invalid status '{status}'")
        linked = split_ids(row.get("run_ids", ""))
        for value in linked:
            if value not in run_ids:
                errors.append(f"{prefix}: unknown run_id '{value}'")
            elif status in ACTIVE_RESULT_STATUSES and run_by_id[value].get("status", "").lower() != "complete":
                errors.append(f"{prefix}: active result depends on non-complete run '{value}'")
        analysis = row.get("analysis_code", "").strip()
        if analysis.lower() != "not-applicable":
            _path_hash_pair(root, row, "analysis_code", "analysis_code_sha256", errors, prefix, required=True)
        elif row.get("analysis_code_sha256", "").strip():
            errors.append(f"{prefix}: not-applicable analysis_code must not carry a hash")
        paths = _semicolon_list(row.get("input_paths", ""))
        hashes = _semicolon_list(row.get("input_sha256s", ""))
        if len(paths) != len(hashes):
            errors.append(f"{prefix}: input_paths and input_sha256s counts differ")
        for item_index, (raw_path, raw_hash) in enumerate(zip(paths, hashes)):
            try:
                verify_path_hash(root, raw_path, raw_hash.lower(), label=f"{prefix} input[{item_index}]")
            except ValidationError as exc:
                errors.append(str(exc))
    return run_ids, run_by_id, result_ids, result_by_id


def _check_claims(sources: list[dict[str, str]], claims: list[dict[str, str]], result_ids: set[str], result_by_id: dict[str, dict[str, str]], errors: list[str], warnings: list[str]) -> set[str]:
    source_by_id = {row.get("source_id", ""): row for row in sources if row.get("source_id")}
    source_ids = set(source_by_id)
    claim_ids = _ids(claims, "claim_id", errors, "claims/claims.csv")
    active_ids: set[str] = set()
    allowed_types = {"background", "empirical", "formal", "methodological", "synthesis", "interpretation", "limitation", "retraction"}
    allowed_status = {"draft", *ACTIVE_CLAIM_STATUSES, *INACTIVE_CLAIM_STATUSES}
    for index, row in enumerate(claims, start=2):
        prefix = f"claims/claims.csv:{index}"
        status = row.get("status", "").lower()
        if status not in allowed_status:
            errors.append(f"{prefix}: invalid status '{status}'")
        claim_type = row.get("claim_type", "").lower()
        if claim_type not in allowed_types:
            errors.append(f"{prefix}: invalid claim_type '{claim_type}'")
        active = status in ACTIVE_CLAIM_STATUSES
        claim_id = row.get("claim_id", "")
        if active:
            active_ids.add(claim_id)
            _required(row, ("text", "limitations"), errors, prefix)
            if has_placeholder(row.get("text", "")):
                errors.append(f"{prefix}: active claim contains a placeholder")
        linked_sources = split_ids(row.get("source_ids", ""))
        linked_results = split_ids(row.get("result_ids", ""))
        if active and not (linked_sources or linked_results):
            errors.append(f"{prefix}: active claim has no evidence link")
        for value in linked_sources:
            if value not in source_ids:
                errors.append(f"{prefix}: unknown source_id '{value}'")
            elif active and source_by_id[value].get("status", "").lower() in SOURCE_INELIGIBLE:
                errors.append(f"{prefix}: active claim depends on ineligible source '{value}'")
        for value in linked_results:
            if value not in result_ids:
                errors.append(f"{prefix}: unknown result_id '{value}'")
            elif active and result_by_id[value].get("status", "").lower() not in ACTIVE_RESULT_STATUSES:
                errors.append(f"{prefix}: active claim depends on inactive result '{value}'")
        retracted = [value for value in linked_sources if source_by_id.get(value, {}).get("status", "").lower() == "retracted"]
        if active and retracted:
            disclosure = (row.get("text", "") + " " + row.get("limitations", "")).lower()
            if "retract" not in disclosure:
                errors.append(f"{prefix}: active claim uses retracted source without disclosure")
            non_retracted = [value for value in linked_sources if value not in retracted]
            if not non_retracted and not linked_results and claim_type != "retraction":
                errors.append(f"{prefix}: retracted source is the sole support for a non-retraction claim")
        if active and linked_sources and not linked_results:
            levels = {source_by_id[value].get("evidence_level", "").lower() for value in linked_sources if value in source_by_id}
            if levels and levels <= {"metadata", "abstract"}:
                warnings.append(f"{prefix}: claim is supported only by metadata or abstract-level evidence")
    return active_ids


def _check_findings_and_review(root: Path, findings: list[dict[str, str]], errors: list[str]) -> None:
    _ids(findings, "finding_id", errors, "review/findings.csv")
    for index, row in enumerate(findings, start=2):
        prefix = f"review/findings.csv:{index}"
        _required(row, ("severity", "confidence", "location", "finding", "evidence", "consequence", "action", "status"), errors, prefix)
        if row.get("severity", "").lower() not in FINDING_SEVERITIES:
            errors.append(f"{prefix}: invalid severity")
        if row.get("confidence", "").lower() not in CONFIDENCE_LEVELS:
            errors.append(f"{prefix}: invalid confidence")
        if row.get("status", "").lower() not in FINDING_STATUSES:
            errors.append(f"{prefix}: invalid status")

    if (root / "review/summary.json").exists():
        try:
            summary = load_json(root / "review/summary.json")
        except ValidationError as exc:
            errors.append(str(exc))
            return
        if summary:
            if not isinstance(summary, dict):
                errors.append("review/summary.json must contain an object")
            else:
                for field in ("scope", "recommendation", "confidence", "limitations"):
                    if not isinstance(summary.get(field), str) or not summary[field].strip():
                        errors.append(f"review/summary.json lacks nonempty {field}")
                if str(summary.get("confidence", "")).lower() not in CONFIDENCE_LEVELS:
                    errors.append("review/summary.json has invalid confidence")


def _check_response_matrix(rows: list[dict[str, str]], errors: list[str]) -> None:
    seen: set[str] = set()
    for index, row in enumerate(rows, start=2):
        prefix = f"review/response-matrix.csv:{index}"
        _required(row, ("comment_id", "comment", "assessment", "rationale", "action", "status"), errors, prefix)
        comment_id = row.get("comment_id", "")
        if comment_id in seen:
            errors.append(f"{prefix}: duplicate comment_id '{comment_id}'")
        seen.add(comment_id)
        if row.get("assessment", "").lower() not in {"agree", "partly-agree", "disagree", "needs-clarification"}:
            errors.append(f"{prefix}: invalid assessment")
        if row.get("status", "").lower() not in {"open", "planned", "implemented", "verified", "not-adopted", "accepted-limitation"}:
            errors.append(f"{prefix}: invalid status")
        if row.get("status", "").lower() in {"implemented", "verified"}:
            _required(row, ("manuscript_change", "evidence"), errors, prefix)


def _check_revisions(root: Path, revisions: list[dict[str, str]], errors: list[str], warnings: list[str]) -> None:
    _ids(revisions, "revision_id", errors, "manuscript/revision-log.csv")
    for index, row in enumerate(revisions, start=2):
        prefix = f"manuscript/revision-log.csv:{index}"
        _required(row, ("source_path", "source_sha256", "revised_path", "revised_sha256", "scope", "protected_content", "material_changes", "residual_concerns", "audit_status", "status"), errors, prefix)
        source = _path_hash_pair(root, row, "source_path", "source_sha256", errors, prefix, required=True)
        revised = _path_hash_pair(root, row, "revised_path", "revised_sha256", errors, prefix, required=True)
        if source and revised and source == revised:
            errors.append(f"{prefix}: source_path and revised_path must differ")
        status = row.get("status", "").lower()
        if status not in {"open", "complete", "accepted", "resolved", "superseded"}:
            errors.append(f"{prefix}: invalid status")
        audit_status = row.get("audit_status", "").lower()
        if audit_status not in {"pass", "manual-accepted", "fail"}:
            errors.append(f"{prefix}: invalid audit_status")
        if source and revised:
            audit = audit_prose.audit(source, revised, strict=True)
            if audit["passed"]:
                if audit_status == "fail":
                    errors.append(f"{prefix}: audit_status says fail but deterministic audit passes")
            elif audit_status != "manual-accepted":
                errors.append(f"{prefix}: strict semantic drift audit failed: {audit['errors']}")
            else:
                if row.get("material_changes", "").strip().lower() in {"", "none"}:
                    errors.append(f"{prefix}: manual acceptance requires a material_changes rationale")
                if row.get("residual_concerns", "").strip().lower() in {"", "none"}:
                    errors.append(f"{prefix}: manual acceptance requires residual concerns or an explicit resolution rationale")
                warnings.append(f"{prefix}: deterministic drift findings were manually accepted and require human review")


def _check_flow(root: Path, errors: list[str]) -> None:
    try:
        flow = load_json(root / "evidence/flow.json")
    except ValidationError as exc:
        errors.append(str(exc))
        return
    required = ("identified", "deduplicated", "screened", "full_text_assessed", "included")
    if not isinstance(flow, dict) or any(not isinstance(flow.get(field), int) or flow[field] < 0 for field in required):
        errors.append("evidence/flow.json requires nonnegative integer identified, deduplicated, screened, full_text_assessed, and included counts")
        return
    if not (flow["identified"] >= flow["deduplicated"] >= flow["screened"] >= flow["full_text_assessed"] >= flow["included"]):
        errors.append("evidence/flow.json counts are not monotonically reconciled")


def _check_pilot(root: Path, errors: list[str]) -> str | None:
    try:
        decision = load_json(root / "study/pilot-decision.json")
    except ValidationError as exc:
        errors.append(str(exc))
        return None
    if not isinstance(decision, dict):
        errors.append("study/pilot-decision.json must contain an object")
        return None
    for field in ("decision", "decided_at", "protocol_effect", "evidence"):
        if field not in decision:
            errors.append(f"study/pilot-decision.json lacks {field}")
    value = str(decision.get("decision", "")).lower()
    if value not in {"go", "revise", "stop"}:
        errors.append("study/pilot-decision.json decision must be go, revise, or stop")
    _timestamp(str(decision.get("decided_at", "")), errors, "study/pilot-decision.json.decided_at")
    if not isinstance(decision.get("protocol_effect"), str) or not decision.get("protocol_effect", "").strip():
        errors.append("study/pilot-decision.json protocol_effect is empty")
    evidence = decision.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        errors.append("study/pilot-decision.json evidence must be a nonempty list")
    else:
        for index, item in enumerate(evidence):
            if not isinstance(item, dict):
                errors.append(f"pilot evidence[{index}] must be an object")
                continue
            try:
                verify_path_hash(root, str(item.get("path", "")), str(item.get("sha256", "")).lower(), label=f"pilot evidence[{index}]")
            except ValidationError as exc:
                errors.append(str(exc))
    return value


def _check_publication_decision(root: Path, errors: list[str]) -> None:
    try:
        decision = load_json(root / "publication/decision.json")
    except ValidationError as exc:
        errors.append(str(exc))
        return
    if not isinstance(decision, dict):
        errors.append("publication/decision.json must contain an object")
        return
    for field in ("status", "venue", "decided_at", "evidence_path", "evidence_sha256"):
        if not isinstance(decision.get(field), str) or not decision[field].strip():
            errors.append(f"publication/decision.json lacks nonempty {field}")
    if str(decision.get("status", "")).lower() != "accepted":
        errors.append("accepted stage requires publication/decision.json status accepted")
    _timestamp(str(decision.get("decided_at", "")), errors, "publication/decision.json.decided_at")
    try:
        verify_path_hash(root, str(decision.get("evidence_path", "")), str(decision.get("evidence_sha256", "")).lower(), label="publication decision evidence")
    except ValidationError as exc:
        errors.append(str(exc))


def _check_release_manifest(root: Path, rows: list[dict[str, str]], errors: list[str]) -> None:
    seen: set[str] = set()
    for index, row in enumerate(rows, start=2):
        prefix = f"publication/release-manifest.csv:{index}"
        _required(row, ("artifact", "path", "sha256", "license", "archived_at"), errors, prefix)
        artifact = row.get("artifact", "")
        if artifact in seen:
            errors.append(f"{prefix}: duplicate artifact '{artifact}'")
        seen.add(artifact)
        try:
            verify_path_hash(root, row.get("path", ""), row.get("sha256", "").lower(), label=prefix)
        except ValidationError as exc:
            errors.append(str(exc))
        _timestamp(row.get("archived_at", ""), errors, f"{prefix}.archived_at")


def _no_material_findings(review_text: str) -> bool:
    return "no material findings" in review_text.lower()


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
    if project.get("schema_version") != 3 or state.get("schema_version") != 3:
        errors.append("project and state schema_version must be 3; migrate older workspaces before relying on this audit")
    if not isinstance(project.get("name"), str) or not project["name"].strip():
        errors.append("project.name must be nonempty")
    _timestamp(str(project.get("created_at", "")), errors, "project.created_at")
    _timestamp(str(state.get("updated_at", "")), errors, "state.updated_at")

    mode = project.get("mode")
    if mode not in STAGES_BY_MODE:
        errors.append(f"invalid project mode: {mode!r}")
        return {"passed": False, "errors": errors, "warnings": warnings, "metrics": metrics}
    stage = state.get("stage")
    if stage not in STAGES_BY_MODE[mode]:
        errors.append(f"invalid stage {stage!r} for mode {mode}")
        return {"passed": False, "errors": errors, "warnings": warnings, "metrics": metrics}
    _validate_gate_sequence(mode, stage, state.get("completed_gates"), errors)

    for relative in REQUIRED_FILES_BY_MODE[mode]:
        if not (root / relative).is_file():
            errors.append(f"missing required file for {mode}: {relative}")

    tables: dict[str, list[dict[str, str]]] = {}
    for relative in CSV_REQUIREMENTS:
        if (root / relative).exists():
            _, rows = _load_csv(root, relative, errors)
            tables[relative] = rows

    sources = tables.get("evidence/sources.csv", [])
    source_ids, _ = _check_sources(root, sources, errors, warnings)
    search_sets = _check_search(root, tables, source_ids, errors, warnings)
    runs = tables.get("study/runs.csv", [])
    results = tables.get("study/results.csv", [])
    _, run_by_id, result_ids, result_by_id = _check_runs_and_results(root, runs, results, errors)
    claims = tables.get("claims/claims.csv", [])
    active_claim_ids = _check_claims(sources, claims, result_ids, result_by_id, errors, warnings)
    findings = tables.get("review/findings.csv", [])
    _check_findings_and_review(root, findings, errors)
    response_rows = tables.get("review/response-matrix.csv", [])
    _check_response_matrix(response_rows, errors)
    revisions = tables.get("manuscript/revision-log.csv", [])
    _check_revisions(root, revisions, errors, warnings)
    _check_external_actions(root, state, errors, warnings)

    metrics.update({
        "mode": mode, "stage": stage, "sources": len(sources), "runs": len(runs), "results": len(results),
        "claims": len(claims), "findings": len(findings), "revisions": len(revisions),
        "files": sum(1 for path in root.rglob("*") if path.is_file()),
    })

    if mode == "full-research-lifecycle":
        if _stage_at_least(mode, stage, "question") and not nonempty_without_placeholder(root / "governance/charter.md"):
            errors.append("question stage requires a completed governance/charter.md")
        if _stage_at_least(mode, stage, "protocol") and not nonempty_without_placeholder(root / "protocol/protocol.md"):
            errors.append("protocol stage requires a completed protocol/protocol.md")
        pilot_decision: str | None = None
        if _stage_at_least(mode, stage, "pilot"):
            pilot_decision = _check_pilot(root, errors)
        if pilot_decision == "stop" and _stage_at_least(mode, stage, "execution"):
            errors.append("project advanced beyond a pilot stop decision")
        if _stage_at_least(mode, stage, "execution"):
            completed = [row for row in runs if row.get("phase", "").lower() in {"definitive", "replication"} and row.get("status", "").lower() == "complete"]
            if not completed:
                errors.append("execution stage requires at least one complete definitive or replication run")
        if _stage_at_least(mode, stage, "analysis"):
            if not any(row.get("status", "").lower() in ACTIVE_RESULT_STATUSES for row in results):
                errors.append("analysis stage requires at least one active, reported, or confirmed result")
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
            latex = audit_latex.audit(root / "manuscript", Path("main.tex"))
            errors.extend(f"LaTeX audit: {item}" for item in latex["errors"])
            warnings.extend(f"LaTeX audit: {item}" for item in latex["warnings"])
        if _stage_at_least(mode, stage, "internal-review"):
            if not nonempty_without_placeholder(root / "review/review.md"):
                errors.append("internal-review stage requires a completed review/review.md")
            else:
                review_text = read_text(root / "review/review.md")
                if not findings and not _no_material_findings(review_text):
                    errors.append("internal review has no finding records and does not explicitly state No material findings")
            try:
                summary = load_json(root / "review/summary.json")
            except ValidationError:
                summary = {}
            if not summary:
                errors.append("internal-review stage requires a completed review/summary.json")
        if _stage_at_least(mode, stage, "journal-selection"):
            journal_result = score_journals.score(root / "publication/journals.csv")
            errors.extend(f"journal record: {item}" for item in journal_result["errors"])
            warnings.extend(f"journal record: {item}" for item in journal_result["warnings"])
            try:
                selected = load_json(root / "publication/selected-journal.json")
            except ValidationError as exc:
                errors.append(str(exc))
                selected = {}
            needed = {"journal", "fit_rationale", "selected_at", "q1_claim"}
            if not isinstance(selected, dict) or not needed.issubset(selected) or any(not str(selected.get(field, "")).strip() for field in needed):
                errors.append("journal-selection stage requires nonempty journal, fit_rationale, selected_at, and q1_claim")
            else:
                _timestamp(str(selected.get("selected_at", "")), errors, "selected-journal.selected_at")
                matches = [item for item in journal_result["journals"] if str(item["journal"]).casefold() == str(selected["journal"]).casefold()]
                if len(matches) != 1:
                    errors.append("selected journal must match exactly one candidate record")
                q1_claim = str(selected.get("q1_claim", "")).lower()
                if q1_claim not in {"verified", "provisional", "not-claimed"}:
                    errors.append("selected-journal q1_claim must be verified, provisional, or not-claimed")
                elif q1_claim == "verified":
                    if not matches or not matches[0]["q1_verified"]:
                        errors.append("selected journal claims verified Q1 without a complete local evidence record")
                    for field in ("provider", "metric_year", "category", "evidence_sha256"):
                        if not matches or str(selected.get(field, "")) != str(matches[0].get(field, "")):
                            errors.append(f"selected-journal verified Q1 field does not match candidate: {field}")
        if _stage_at_least(mode, stage, "submission-ready") and not nonempty_without_placeholder(root / "publication/submission-checklist.md"):
            errors.append("submission-ready stage requires a completed submission checklist")
        if _stage_at_least(mode, stage, "revision") and not response_rows:
            errors.append("revision stage requires response-matrix records")
        if _stage_at_least(mode, stage, "accepted"):
            _check_publication_decision(root, errors)
        if _stage_at_least(mode, stage, "archived"):
            release_rows = tables.get("publication/release-manifest.csv", [])
            if not release_rows:
                errors.append("archived stage requires release-manifest records")
            else:
                _check_release_manifest(root, release_rows, errors)
            if not nonempty_without_placeholder(root / "publication/correction-plan.md"):
                errors.append("archived stage requires a completed correction plan")

    elif mode == "systematic-search":
        if _stage_at_least(mode, stage, "protocol"):
            if not nonempty_without_placeholder(root / "governance/charter.md"):
                errors.append("protocol stage requires a completed governance/charter.md")
            if not nonempty_without_placeholder(root / "protocol/search-protocol.md"):
                errors.append("protocol stage requires a completed search protocol")
        if _stage_at_least(mode, stage, "search") and not tables.get("evidence/search-log.csv"):
            errors.append("search stage requires search-log records")
        if _stage_at_least(mode, stage, "screening") and not tables.get("evidence/screening.csv"):
            errors.append("screening stage requires screening records")
        if _stage_at_least(mode, stage, "extraction") and not tables.get("evidence/extraction.csv"):
            errors.append("extraction stage requires extraction records")
        if _stage_at_least(mode, stage, "synthesis"):
            if not nonempty_without_placeholder(root / "evidence/synthesis.md"):
                errors.append("synthesis stage requires a completed evidence synthesis")
            if not active_claim_ids:
                errors.append("synthesis stage requires at least one evidence-linked active claim")
            _check_flow(root, errors)
            missing_extractions = search_sets["included_screening"] - search_sets["extraction_ids"]
            if missing_extractions:
                errors.append(f"included records lack extraction rows: {sorted(missing_extractions)}")
        if _stage_at_least(mode, stage, "internal-review") and not nonempty_without_placeholder(root / "evidence/search-audit.md"):
            errors.append("internal-review stage requires a completed search audit")

    elif mode == "peer-review":
        if _stage_at_least(mode, stage, "review"):
            if not nonempty_without_placeholder(root / "governance/charter.md"):
                errors.append("review stage requires a completed governance/charter.md")
            if not nonempty_without_placeholder(root / "review/review.md"):
                errors.append("review stage requires a completed review/review.md")
            else:
                review_text = read_text(root / "review/review.md")
                if not findings and not _no_material_findings(review_text):
                    errors.append("review has no finding records and does not explicitly state No material findings")
            try:
                summary = load_json(root / "review/summary.json")
            except ValidationError:
                summary = {}
            if not summary:
                errors.append("review stage requires a completed review/summary.json")
        if _stage_at_least(mode, stage, "final"):
            unresolved = [row for row in findings if row.get("severity", "").lower() in {"design-limiting", "major"} and row.get("status", "").lower() in {"open", "partly-addressed"}]
            if unresolved:
                errors.append("final peer-review stage has unresolved design-limiting or major findings")

    elif mode == "scientific-prose":
        if _stage_at_least(mode, stage, "revision"):
            if not nonempty_without_placeholder(root / "governance/charter.md"):
                errors.append("revision stage requires a completed governance/charter.md")
            if not revisions:
                errors.append("revision stage requires revision-log records")
            if not nonempty_without_placeholder(root / "manuscript/protected-spans.txt"):
                errors.append("revision stage requires a completed protected-spans record")
        if _stage_at_least(mode, stage, "final"):
            incomplete = [row for row in revisions if row.get("status", "").lower() not in {"complete", "accepted", "resolved"}]
            if incomplete:
                errors.append("final prose stage has incomplete revision-log records")
            if not nonempty_without_placeholder(root / "manuscript/residual-concerns.md"):
                errors.append("final prose stage requires resolved residual-concerns.md")

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
