#!/usr/bin/env python3
"""Audit a governed research workspace for integrity and readiness defects."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import audit_latex
import audit_prose
import score_journals
from _common import (
    DEFAULT_MAX_DEPTH,
    DEFAULT_MAX_ENTRIES,
    DEFAULT_MAX_TOTAL_BYTES,
    ID_PATTERNS,
    ValidationError,
    has_placeholder,
    load_json,
    nonempty_without_placeholder,
    parse_timestamp,
    read_csv,
    read_text,
    require_headers,
    scan_tree,
    split_ids,
    verify_path_hash,
)
from _project_model import (
    ACTIVE_RESULT_STATUSES,
    COMMON_FILES,
    CONFIDENCE_LEVELS,
    CSV_REQUIREMENTS,
    EVIDENCE_LEVELS,
    FINDING_SEVERITIES,
    FINDING_STATUSES,
    GATE_ORDER,
    INACTIVE_CLAIM_STATUSES,
    MANUSCRIPT_CLAIM_STATUSES,
    REQUIRED_FILES_BY_MODE,
    RESPONSE_STATUSES,
    RESULT_STATUSES,
    SCHEMA_VERSION,
    SHIP_READY_CLAIM_STATUSES,
    SOURCE_INELIGIBLE,
    SOURCE_STATUSES,
    STAGES_BY_MODE,
    UNRESOLVED_FINDING_STATUSES,
    UNRESOLVED_RESPONSE_STATUSES,
    expected_gates,
    is_shipping_stage,
    stage_at_least,
)

RECORD_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
CLUSTER_ID_RE = re.compile(r"^K\d{4}$")


def _required(
    row: dict[str, str],
    fields: tuple[str, ...],
    errors: list[str],
    prefix: str,
) -> None:
    for field in fields:
        if not row.get(field, "").strip():
            errors.append(f"{prefix}: missing {field}")


def _timestamp(value: str, errors: list[str], prefix: str) -> datetime | None:
    try:
        return parse_timestamp(value, field=prefix)
    except ValidationError as exc:
        errors.append(str(exc))
        return None


def _path_hash(
    root: Path,
    row: dict[str, str],
    path_field: str,
    hash_field: str,
    errors: list[str],
    prefix: str,
    *,
    required: bool = False,
    allow_not_applicable: bool = False,
) -> Path | None:
    raw_path = row.get(path_field, "").strip()
    raw_hash = row.get(hash_field, "").strip().lower()
    if allow_not_applicable and raw_path.lower() == "not-applicable":
        if raw_hash:
            errors.append(f"{prefix}: not-applicable {path_field} must not carry a hash")
        return None
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


def _id_set(
    rows: list[dict[str, str]],
    field: str,
    relative: str,
    errors: list[str],
    *,
    pattern: re.Pattern[str] | None = None,
) -> set[str]:
    matcher = pattern or ID_PATTERNS.get(field)
    found: set[str] = set()
    for index, row in enumerate(rows, start=2):
        value = row.get(field, "").strip()
        if not value:
            errors.append(f"{relative}:{index}: missing {field}")
            continue
        if matcher and not matcher.fullmatch(value):
            errors.append(f"{relative}:{index}: invalid {field} '{value}'")
        if value in found:
            errors.append(f"{relative}:{index}: duplicate {field} '{value}'")
        found.add(value)
    return found


def _load_table(
    root: Path,
    relative: str,
    errors: list[str],
) -> list[dict[str, str]]:
    path = root / relative
    try:
        headers, rows = read_csv(path)
    except ValidationError as exc:
        errors.append(str(exc))
        return []
    errors.extend(require_headers(path, headers, CSV_REQUIREMENTS.get(relative, [])))
    return rows


def _validate_gate_sequence(
    mode: str,
    stage: str,
    gates: Any,
    errors: list[str],
) -> None:
    if not isinstance(gates, list) or any(not isinstance(item, str) for item in gates):
        errors.append("state.completed_gates must be a list of strings")
        return
    expected = expected_gates(mode, stage)
    if gates != expected:
        errors.append(
            f"stage {stage} requires exact completed_gates sequence {expected}; got {gates}"
        )
    unknown = sorted(set(gates) - set(GATE_ORDER[mode]))
    if unknown:
        errors.append(f"state.completed_gates contains unknown gates: {unknown}")


def _check_external_actions(
    root: Path,
    state: dict[str, Any],
    errors: list[str],
    warnings: list[str],
) -> None:
    actions = state.get("external_actions", [])
    if not isinstance(actions, list):
        errors.append("state.external_actions must be a list")
        return
    allowed = {"prepared", "authorized", "performed", "failed", "cancelled"}
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
        if status not in allowed:
            errors.append(f"{prefix} has invalid status {status!r}")
            continue
        _required(action, ("action", "destination"), errors, prefix)
        if status == "cancelled":
            _required(action, ("outcome",), errors, prefix)
            continue
        payload = action.get("payload")
        if not isinstance(payload, list) or not payload:
            errors.append(f"{prefix} lacks an exact payload list")
        else:
            seen_paths: set[str] = set()
            for item_index, item in enumerate(payload):
                item_prefix = f"{prefix}.payload[{item_index}]"
                if not isinstance(item, dict):
                    errors.append(f"{item_prefix} must be an object")
                    continue
                raw_path = str(item.get("path", ""))
                if raw_path in seen_paths:
                    errors.append(f"{item_prefix} duplicates payload path {raw_path!r}")
                seen_paths.add(raw_path)
                try:
                    verify_path_hash(
                        root,
                        raw_path,
                        str(item.get("sha256", "")).lower(),
                        label=item_prefix,
                    )
                except ValidationError as exc:
                    errors.append(str(exc))
        authorized = expires = None
        if status in {"authorized", "performed", "failed"}:
            _required(
                action,
                ("authorized_at", "expires_at", "authorized_by", "authorization_statement"),
                errors,
                prefix,
            )
            authorized = _timestamp(
                str(action.get("authorized_at", "")), errors, f"{prefix}.authorized_at"
            )
            expires = _timestamp(
                str(action.get("expires_at", "")), errors, f"{prefix}.expires_at"
            )
            if authorized and expires:
                if expires <= authorized:
                    errors.append(f"{prefix}: expires_at must follow authorized_at")
                if (expires - authorized).total_seconds() > 48 * 3600:
                    errors.append(f"{prefix}: authorization window exceeds 48 hours")
                if status == "authorized" and expires < now:
                    errors.append(f"{prefix}: authorization has expired")
        if status in {"performed", "failed"}:
            _required(action, ("performed_at", "outcome"), errors, prefix)
            performed = _timestamp(
                str(action.get("performed_at", "")), errors, f"{prefix}.performed_at"
            )
            if performed and authorized and performed < authorized:
                errors.append(f"{prefix}: performed_at precedes authorization")
            if performed and expires and performed > expires:
                errors.append(f"{prefix}: action occurred after authorization expiry")
        if status == "prepared":
            warnings.append(f"{prefix}: prepared is not authorization to transmit")


def _check_sources(
    root: Path,
    rows: list[dict[str, str]],
    errors: list[str],
    warnings: list[str],
) -> tuple[set[str], dict[str, dict[str, str]]]:
    source_ids = _id_set(rows, "source_id", "evidence/sources.csv", errors)
    by_id = {row.get("source_id", ""): row for row in rows if row.get("source_id")}
    for index, row in enumerate(rows, start=2):
        prefix = f"evidence/sources.csv:{index}"
        _required(row, ("title", "status", "evidence_level"), errors, prefix)
        status = row.get("status", "").lower()
        level = row.get("evidence_level", "").lower()
        if status not in SOURCE_STATUSES:
            errors.append(f"{prefix}: invalid status '{status}'")
        if level not in EVIDENCE_LEVELS:
            errors.append(f"{prefix}: invalid evidence_level '{level}'")
        record_required = status in {"verified", "corrected", "retracted"}
        _path_hash(
            root,
            row,
            "record_path",
            "record_sha256",
            errors,
            prefix,
            required=record_required,
        )
        verified_at = row.get("verified_at", "").strip()
        if record_required or verified_at:
            _timestamp(verified_at, errors, f"{prefix}.verified_at")
        if status == "retracted" and "retract" not in row.get("notes", "").lower():
            warnings.append(f"{prefix}: retracted source lacks an explanatory note")
    return source_ids, by_id


def _check_search_log(
    root: Path,
    rows: list[dict[str, str]],
    errors: list[str],
    warnings: list[str],
) -> None:
    _id_set(rows, "search_id", "evidence/search-log.csv", errors)
    for index, row in enumerate(rows, start=2):
        prefix = f"evidence/search-log.csv:{index}"
        _required(
            row,
            ("source", "interface", "query", "executed_at", "result_count"),
            errors,
            prefix,
        )
        _timestamp(row.get("executed_at", ""), errors, f"{prefix}.executed_at")
        try:
            if int(row.get("result_count", "")) < 0:
                raise ValueError
        except ValueError:
            errors.append(f"{prefix}: result_count must be a nonnegative integer")
        export = _path_hash(root, row, "export_path", "export_sha256", errors, prefix)
        if export is None and not (row.get("export_path") or row.get("export_sha256")):
            warnings.append(
                f"{prefix}: no hash-bound export; document the reproducible alternative"
            )


def _check_screening(
    rows: list[dict[str, str]],
    source_ids: set[str],
    errors: list[str],
) -> dict[str, set[str]]:
    pairs: set[tuple[str, str]] = set()
    decisions: dict[tuple[str, str], str] = {}
    screened_ids: set[str] = set()
    full_text_ids: set[str] = set()
    included_full_text: set[str] = set()
    for index, row in enumerate(rows, start=2):
        prefix = f"evidence/screening.csv:{index}"
        record_id = row.get("record_id", "").strip()
        stage = row.get("stage", "").lower()
        decision = row.get("decision", "").lower()
        _required(row, ("record_id", "source_ids", "stage", "decision"), errors, prefix)
        if record_id and not RECORD_ID_RE.fullmatch(record_id):
            errors.append(f"{prefix}: invalid record_id '{record_id}'")
        if stage not in {"title-abstract", "full-text"}:
            errors.append(f"{prefix}: invalid screening stage '{stage}'")
        if decision not in {"include", "exclude", "duplicate", "uncertain"}:
            errors.append(f"{prefix}: invalid screening decision '{decision}'")
        key = (record_id, stage)
        if record_id and stage and key in pairs:
            errors.append(f"{prefix}: duplicate screening record/stage pair {key}")
        pairs.add(key)
        decisions[key] = decision
        for value in split_ids(row.get("source_ids", "")):
            if value not in source_ids:
                errors.append(f"{prefix}: unknown source_id '{value}'")
        if decision == "exclude" and not row.get("exclusion_reason", "").strip():
            errors.append(f"{prefix}: excluded record lacks exclusion_reason")
        if record_id:
            screened_ids.add(record_id)
        if stage == "full-text" and record_id:
            full_text_ids.add(record_id)
            if decisions.get((record_id, "title-abstract")) != "include":
                errors.append(
                    f"{prefix}: full-text assessment lacks a title-abstract include decision"
                )
            if decision == "include":
                included_full_text.add(record_id)
    return {
        "screened_ids": screened_ids,
        "full_text_ids": full_text_ids,
        "included_full_text": included_full_text,
    }


def _check_extraction(
    rows: list[dict[str, str]],
    source_ids: set[str],
    included_full_text: set[str],
    errors: list[str],
) -> set[str]:
    extraction_ids = _id_set(
        rows,
        "record_id",
        "evidence/extraction.csv",
        errors,
        pattern=RECORD_ID_RE,
    )
    allowed_access = {
        "metadata-only",
        "abstract-reviewed",
        "full-text-reviewed",
        "data-code-artifact-reviewed",
    }
    for index, row in enumerate(rows, start=2):
        prefix = f"evidence/extraction.csv:{index}"
        _required(
            row,
            ("source_ids", "method", "outcomes", "limitations", "evidence_access"),
            errors,
            prefix,
        )
        if row.get("record_id", "") not in included_full_text:
            errors.append(
                f"{prefix}: extraction lacks a corresponding included full-text record"
            )
        for value in split_ids(row.get("source_ids", "")):
            if value not in source_ids:
                errors.append(f"{prefix}: unknown source_id '{value}'")
        if row.get("evidence_access", "").lower() not in allowed_access:
            errors.append(f"{prefix}: invalid evidence_access")
    return extraction_ids


def _check_deduplication(
    rows: list[dict[str, str]],
    source_ids: set[str],
    errors: list[str],
) -> None:
    _id_set(
        rows,
        "cluster_id",
        "evidence/deduplication.csv",
        errors,
        pattern=CLUSTER_ID_RE,
    )
    membership: dict[str, str] = {}
    for index, row in enumerate(rows, start=2):
        prefix = f"evidence/deduplication.csv:{index}"
        _required(
            row,
            ("canonical_source_id", "member_source_ids", "method", "resolver"),
            errors,
            prefix,
        )
        cluster = row.get("cluster_id", "")
        canonical = row.get("canonical_source_id", "")
        members = split_ids(row.get("member_source_ids", ""))
        if len(members) != len(set(members)):
            errors.append(f"{prefix}: member_source_ids contains duplicates")
        if canonical not in source_ids:
            errors.append(f"{prefix}: unknown canonical_source_id '{canonical}'")
        if canonical and canonical not in members:
            errors.append(f"{prefix}: canonical_source_id is not a cluster member")
        for value in members:
            if value not in source_ids:
                errors.append(f"{prefix}: unknown member source_id '{value}'")
            prior = membership.get(value)
            if prior and prior != cluster:
                errors.append(
                    f"{prefix}: source_id '{value}' belongs to multiple clusters ({prior}, {cluster})"
                )
            membership[value] = cluster


def _check_search(
    root: Path,
    tables: dict[str, list[dict[str, str]]],
    source_ids: set[str],
    errors: list[str],
    warnings: list[str],
) -> dict[str, set[str]]:
    _check_search_log(root, tables.get("evidence/search-log.csv", []), errors, warnings)
    screening = _check_screening(
        tables.get("evidence/screening.csv", []), source_ids, errors
    )
    screening["extraction_ids"] = _check_extraction(
        tables.get("evidence/extraction.csv", []),
        source_ids,
        screening["included_full_text"],
        errors,
    )
    _check_deduplication(
        tables.get("evidence/deduplication.csv", []), source_ids, errors
    )
    return screening


def _check_runs(
    root: Path,
    rows: list[dict[str, str]],
    errors: list[str],
) -> tuple[set[str], dict[str, dict[str, str]]]:
    run_ids = _id_set(rows, "run_id", "study/runs.csv", errors)
    by_id = {row.get("run_id", ""): row for row in rows if row.get("run_id")}
    for index, row in enumerate(rows, start=2):
        prefix = f"study/runs.csv:{index}"
        _required(
            row,
            (
                "kind",
                "phase",
                "started_at",
                "code_version",
                "data_version",
                "environment",
                "parameters",
                "status",
            ),
            errors,
            prefix,
        )
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
        binding_required = status == "complete"
        for path_field, hash_field in (
            ("code_path", "code_sha256"),
            ("data_path", "data_sha256"),
            ("environment_path", "environment_sha256"),
        ):
            _path_hash(
                root,
                row,
                path_field,
                hash_field,
                errors,
                prefix,
                required=binding_required,
                allow_not_applicable=True,
            )
        _path_hash(
            root,
            row,
            "raw_output",
            "raw_output_sha256",
            errors,
            prefix,
            required=binding_required,
        )
    return run_ids, by_id


def _check_results(
    root: Path,
    rows: list[dict[str, str]],
    run_ids: set[str],
    runs: dict[str, dict[str, str]],
    errors: list[str],
) -> tuple[set[str], dict[str, dict[str, str]]]:
    result_ids = _id_set(rows, "result_id", "study/results.csv", errors)
    by_id = {row.get("result_id", ""): row for row in rows if row.get("result_id")}
    for index, row in enumerate(rows, start=2):
        prefix = f"study/results.csv:{index}"
        _required(
            row,
            ("run_ids", "analysis_code", "estimate", "uncertainty", "robustness", "status"),
            errors,
            prefix,
        )
        status = row.get("status", "").lower()
        if status not in RESULT_STATUSES:
            errors.append(f"{prefix}: invalid status '{status}'")
        active = status in ACTIVE_RESULT_STATUSES
        for value in split_ids(row.get("run_ids", "")):
            if value not in run_ids:
                errors.append(f"{prefix}: unknown run_id '{value}'")
            elif active and runs[value].get("status", "").lower() != "complete":
                errors.append(f"{prefix}: active result depends on non-complete run '{value}'")
        _path_hash(
            root,
            row,
            "analysis_code",
            "analysis_code_sha256",
            errors,
            prefix,
            required=active,
            allow_not_applicable=True,
        )
        paths = [item.strip() for item in row.get("input_paths", "").split(";") if item.strip()]
        hashes = [item.strip() for item in row.get("input_sha256s", "").split(";") if item.strip()]
        if len(paths) != len(hashes):
            errors.append(f"{prefix}: input_paths and input_sha256s counts differ")
        if active and not paths:
            errors.append(f"{prefix}: active result lacks hash-bound input artifacts")
        for item_index, (raw_path, raw_hash) in enumerate(zip(paths, hashes)):
            try:
                verify_path_hash(
                    root,
                    raw_path,
                    raw_hash.lower(),
                    label=f"{prefix} input[{item_index}]",
                )
            except ValidationError as exc:
                errors.append(str(exc))
    return result_ids, by_id


def _check_claims(
    sources: dict[str, dict[str, str]],
    rows: list[dict[str, str]],
    result_ids: set[str],
    results: dict[str, dict[str, str]],
    errors: list[str],
) -> dict[str, set[str]]:
    _id_set(rows, "claim_id", "claims/claims.csv", errors)
    manuscript: set[str] = set()
    needs_review: set[str] = set()
    allowed_types = {
        "background",
        "empirical",
        "formal",
        "methodological",
        "synthesis",
        "interpretation",
        "limitation",
        "retraction",
    }
    allowed_status = {"draft", *MANUSCRIPT_CLAIM_STATUSES, *INACTIVE_CLAIM_STATUSES}
    for index, row in enumerate(rows, start=2):
        prefix = f"claims/claims.csv:{index}"
        claim_id = row.get("claim_id", "")
        status = row.get("status", "").lower()
        claim_type = row.get("claim_type", "").lower()
        if status not in allowed_status:
            errors.append(f"{prefix}: invalid status '{status}'")
        if claim_type not in allowed_types:
            errors.append(f"{prefix}: invalid claim_type '{claim_type}'")
        active = status in MANUSCRIPT_CLAIM_STATUSES
        if active:
            manuscript.add(claim_id)
            _required(row, ("text", "limitations"), errors, prefix)
            if has_placeholder(row.get("text", "")):
                errors.append(f"{prefix}: active claim contains a placeholder")
        if status == "needs-review":
            needs_review.add(claim_id)
        linked_sources = split_ids(row.get("source_ids", ""))
        linked_results = split_ids(row.get("result_ids", ""))
        if active and not (linked_sources or linked_results):
            errors.append(f"{prefix}: active claim has no evidence link")
        retracted: list[str] = []
        eligible_nonretracted = False
        for value in linked_sources:
            source = sources.get(value)
            if source is None:
                errors.append(f"{prefix}: unknown source_id '{value}'")
                continue
            source_status = source.get("status", "").lower()
            if active and source_status in SOURCE_INELIGIBLE:
                errors.append(f"{prefix}: active claim depends on ineligible source '{value}'")
            if source_status == "retracted":
                retracted.append(value)
            elif source_status not in SOURCE_INELIGIBLE:
                eligible_nonretracted = True
        for value in linked_results:
            result = results.get(value)
            if value not in result_ids or result is None:
                errors.append(f"{prefix}: unknown result_id '{value}'")
            elif active and result.get("status", "").lower() not in ACTIVE_RESULT_STATUSES:
                errors.append(f"{prefix}: active claim depends on inactive result '{value}'")
        if active and retracted and claim_type != "retraction":
            if not eligible_nonretracted and not linked_results:
                errors.append(
                    f"{prefix}: retracted source is the sole support for an active claim"
                )
            if "retract" not in row.get("limitations", "").lower():
                errors.append(
                    f"{prefix}: retracted evidence is not disclosed in claim limitations"
                )
    return {"manuscript": manuscript, "needs_review": needs_review}


def _check_review(
    root: Path,
    rows: list[dict[str, str]],
    errors: list[str],
) -> set[str]:
    _id_set(rows, "finding_id", "review/findings.csv", errors)
    unresolved: set[str] = set()
    for index, row in enumerate(rows, start=2):
        prefix = f"review/findings.csv:{index}"
        _required(
            row,
            (
                "severity",
                "confidence",
                "location",
                "finding",
                "evidence",
                "consequence",
                "action",
                "status",
            ),
            errors,
            prefix,
        )
        severity = row.get("severity", "").lower()
        confidence = row.get("confidence", "").lower()
        status = row.get("status", "").lower()
        if severity not in FINDING_SEVERITIES:
            errors.append(f"{prefix}: invalid severity '{severity}'")
        if confidence not in CONFIDENCE_LEVELS:
            errors.append(f"{prefix}: invalid confidence '{confidence}'")
        if status not in FINDING_STATUSES:
            errors.append(f"{prefix}: invalid status '{status}'")
        if severity in {"design-limiting", "major"} and status in UNRESOLVED_FINDING_STATUSES:
            unresolved.add(row.get("finding_id", ""))
    summary_path = root / "review/summary.json"
    if summary_path.exists():
        try:
            summary = load_json(summary_path)
        except ValidationError as exc:
            errors.append(str(exc))
        else:
            if not isinstance(summary, dict):
                errors.append("review/summary.json must contain an object")
            elif summary:
                for field in ("scope", "recommendation", "confidence", "limitations"):
                    if not isinstance(summary.get(field), str) or not summary[field].strip():
                        errors.append(f"review/summary.json lacks nonempty {field}")
                if str(summary.get("confidence", "")).lower() not in CONFIDENCE_LEVELS:
                    errors.append("review/summary.json has invalid confidence")
    return unresolved


def _check_responses(rows: list[dict[str, str]], errors: list[str]) -> set[str]:
    seen: set[str] = set()
    unresolved: set[str] = set()
    for index, row in enumerate(rows, start=2):
        prefix = f"review/response-matrix.csv:{index}"
        _required(
            row,
            ("comment_id", "comment", "assessment", "rationale", "action", "status"),
            errors,
            prefix,
        )
        comment_id = row.get("comment_id", "")
        if comment_id in seen:
            errors.append(f"{prefix}: duplicate comment_id '{comment_id}'")
        seen.add(comment_id)
        if row.get("assessment", "").lower() not in {
            "agree",
            "partly-agree",
            "disagree",
            "needs-clarification",
        }:
            errors.append(f"{prefix}: invalid assessment")
        status = row.get("status", "").lower()
        if status not in RESPONSE_STATUSES:
            errors.append(f"{prefix}: invalid status")
        if status in {"implemented", "verified"}:
            _required(row, ("manuscript_change", "evidence"), errors, prefix)
        if status in UNRESOLVED_RESPONSE_STATUSES:
            unresolved.add(comment_id)
    return unresolved


def _check_revisions(
    root: Path,
    rows: list[dict[str, str]],
    errors: list[str],
    warnings: list[str],
) -> None:
    _id_set(rows, "revision_id", "manuscript/revision-log.csv", errors)
    for index, row in enumerate(rows, start=2):
        prefix = f"manuscript/revision-log.csv:{index}"
        _required(
            row,
            (
                "source_path",
                "source_sha256",
                "revised_path",
                "revised_sha256",
                "scope",
                "protected_content",
                "material_changes",
                "residual_concerns",
                "audit_status",
                "status",
            ),
            errors,
            prefix,
        )
        source = _path_hash(
            root,
            row,
            "source_path",
            "source_sha256",
            errors,
            prefix,
            required=True,
        )
        revised = _path_hash(
            root,
            row,
            "revised_path",
            "revised_sha256",
            errors,
            prefix,
            required=True,
        )
        if source and revised and source == revised:
            errors.append(f"{prefix}: source_path and revised_path must differ")
        status = row.get("status", "").lower()
        audit_status = row.get("audit_status", "").lower()
        if status not in {"open", "complete", "accepted", "resolved", "superseded"}:
            errors.append(f"{prefix}: invalid status")
        if audit_status not in {"pass", "manual-accepted", "fail"}:
            errors.append(f"{prefix}: invalid audit_status")
        if not source or not revised:
            continue
        audit = audit_prose.audit(source, revised, strict=True)
        if audit["passed"] and audit_status == "fail":
            errors.append(f"{prefix}: audit_status says fail but deterministic audit passes")
        if not audit["passed"] and audit_status != "manual-accepted":
            errors.append(f"{prefix}: strict semantic drift audit failed: {audit['errors']}")
        if not audit["passed"] and audit_status == "manual-accepted":
            if row.get("material_changes", "").strip().lower() in {"", "none"}:
                errors.append(f"{prefix}: manual acceptance requires material_changes rationale")
            if row.get("residual_concerns", "").strip().lower() in {"", "none"}:
                errors.append(f"{prefix}: manual acceptance requires residual concerns")
            warnings.append(f"{prefix}: deterministic drift findings were manually accepted")


def _check_flow(
    root: Path,
    search_sets: dict[str, set[str]],
    errors: list[str],
) -> None:
    try:
        flow = load_json(root / "evidence/flow.json")
    except ValidationError as exc:
        errors.append(str(exc))
        return
    required = ("identified", "deduplicated", "screened", "full_text_assessed", "included")
    if not isinstance(flow, dict) or any(
        not isinstance(flow.get(field), int) or flow[field] < 0 for field in required
    ):
        errors.append("evidence/flow.json requires five nonnegative integer counts")
        return
    if not flow["identified"] >= flow["deduplicated"] >= flow["screened"]:
        errors.append("identified, deduplicated, and screened counts are inconsistent")
    expected = {
        "screened": len(search_sets["screened_ids"]),
        "full_text_assessed": len(search_sets["full_text_ids"]),
        "included": len(search_sets["included_full_text"]),
    }
    for field, value in expected.items():
        if flow[field] != value:
            errors.append(f"evidence/flow.json {field}={flow[field]} but ledger requires {value}")
    if search_sets["included_full_text"] != search_sets["extraction_ids"]:
        missing = sorted(search_sets["included_full_text"] - search_sets["extraction_ids"])
        extra = sorted(search_sets["extraction_ids"] - search_sets["included_full_text"])
        errors.append(f"included/extraction record sets differ: missing={missing}, extra={extra}")


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
        errors.append("pilot decision must be go, revise, or stop")
    _timestamp(
        str(decision.get("decided_at", "")), errors, "study/pilot-decision.json.decided_at"
    )
    if not isinstance(decision.get("protocol_effect"), str) or not decision.get(
        "protocol_effect", ""
    ).strip():
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
                verify_path_hash(
                    root,
                    str(item.get("path", "")),
                    str(item.get("sha256", "")).lower(),
                    label=f"pilot evidence[{index}]",
                )
            except ValidationError as exc:
                errors.append(str(exc))
    if value == "revise":
        amendment_path = str(decision.get("amendment_path", ""))
        amendment_hash = str(decision.get("amendment_sha256", "")).lower()
        if amendment_path != "protocol/amendments.md":
            errors.append("pilot revise decision must bind protocol/amendments.md")
        try:
            verify_path_hash(
                root,
                amendment_path,
                amendment_hash,
                label="pilot amendment",
            )
        except ValidationError as exc:
            errors.append(str(exc))
        if not nonempty_without_placeholder(root / "protocol/amendments.md"):
            errors.append("pilot revise decision requires a completed protocol amendment")
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
        errors.append("accepted stage requires publication decision status accepted")
    _timestamp(
        str(decision.get("decided_at", "")), errors, "publication/decision.json.decided_at"
    )
    try:
        verify_path_hash(
            root,
            str(decision.get("evidence_path", "")),
            str(decision.get("evidence_sha256", "")).lower(),
            label="publication decision evidence",
        )
    except ValidationError as exc:
        errors.append(str(exc))


def _check_release_manifest(
    root: Path,
    rows: list[dict[str, str]],
    errors: list[str],
) -> None:
    seen: set[str] = set()
    for index, row in enumerate(rows, start=2):
        prefix = f"publication/release-manifest.csv:{index}"
        _required(row, ("artifact", "path", "sha256", "license", "archived_at"), errors, prefix)
        artifact = row.get("artifact", "")
        if artifact in seen:
            errors.append(f"{prefix}: duplicate artifact '{artifact}'")
        seen.add(artifact)
        try:
            verify_path_hash(
                root,
                row.get("path", ""),
                row.get("sha256", "").lower(),
                label=prefix,
            )
        except ValidationError as exc:
            errors.append(str(exc))
        _timestamp(row.get("archived_at", ""), errors, f"{prefix}.archived_at")


def _journal_selection(
    root: Path,
    errors: list[str],
    warnings: list[str],
) -> None:
    result = score_journals.score(root / "publication/journals.csv")
    errors.extend(f"journal record: {item}" for item in result["errors"])
    warnings.extend(f"journal record: {item}" for item in result["warnings"])
    try:
        selected = load_json(root / "publication/selected-journal.json")
    except ValidationError as exc:
        errors.append(str(exc))
        return
    required = {"journal", "issn", "fit_rationale", "selected_at", "q1_claim"}
    if not isinstance(selected, dict) or any(
        not str(selected.get(field, "")).strip() for field in required
    ):
        errors.append("selected journal requires journal, ISSN, rationale, time, and q1_claim")
        return
    _timestamp(str(selected["selected_at"]), errors, "selected-journal.selected_at")
    identity_matches = [
        item
        for item in result["journals"]
        if str(item["journal"]).casefold() == str(selected["journal"]).casefold()
        and str(item["issn"]).upper() == str(selected["issn"]).upper()
    ]
    if not identity_matches:
        errors.append("selected journal and ISSN do not match a candidate identity")
    q1_claim = str(selected["q1_claim"]).lower()
    if q1_claim not in {"verified", "provisional", "not-claimed"}:
        errors.append("selected-journal q1_claim must be verified, provisional, or not-claimed")
        return
    if q1_claim != "verified":
        return
    exact_fields = ("provider", "metric_year", "category", "evidence_sha256")
    if any(not str(selected.get(field, "")).strip() for field in exact_fields):
        errors.append("verified Q1 selection lacks its exact observation tuple")
        return
    exact = [
        item
        for item in identity_matches
        if all(str(item.get(field, "")) == str(selected.get(field, "")) for field in exact_fields)
    ]
    if len(exact) != 1 or not exact[0]["q1_verified"]:
        errors.append("selected journal claims verified Q1 without one matching verified observation")


def _review_complete(
    root: Path,
    findings: list[dict[str, str]],
    errors: list[str],
    label: str,
) -> None:
    if not nonempty_without_placeholder(root / "review/review.md"):
        errors.append(f"{label} requires a completed review/review.md")
        return
    try:
        text = read_text(root / "review/review.md")
    except ValidationError as exc:
        errors.append(str(exc))
        return
    if not findings and "no material findings" not in text.lower():
        errors.append(f"{label} has no findings and does not state No material findings")
    try:
        summary = load_json(root / "review/summary.json")
    except ValidationError as exc:
        errors.append(str(exc))
        return
    if not isinstance(summary, dict) or not summary:
        errors.append(f"{label} requires a completed review/summary.json")


def _check_manuscript(
    root: Path,
    claim_ids: set[str],
    errors: list[str],
    warnings: list[str],
    limits: tuple[int, int, int],
) -> None:
    if not claim_ids:
        errors.append("manuscript stage requires at least one active or needs-review claim")
    try:
        manuscript = read_text(root / "manuscript/main.tex")
    except ValidationError as exc:
        errors.append(str(exc))
        return
    if has_placeholder(manuscript):
        errors.append("manuscript/main.tex contains unresolved placeholders")
    for claim_id in claim_ids:
        if f"claim:{claim_id}" not in manuscript:
            errors.append(f"manuscript/main.tex lacks marker for claim {claim_id}")
    latex = audit_latex.audit(
        root / "manuscript",
        Path("main.tex"),
        max_entries=limits[0],
        max_depth=limits[1],
        max_total_bytes=limits[2],
    )
    errors.extend(f"LaTeX audit: {item}" for item in latex["errors"])
    warnings.extend(f"LaTeX audit: {item}" for item in latex["warnings"])


def _check_ship_readiness(
    stage: str,
    needs_review: set[str],
    unresolved_findings: set[str],
    unresolved_responses: set[str],
    errors: list[str],
) -> None:
    if not is_shipping_stage("full-research-lifecycle", stage):
        return
    if needs_review:
        errors.append(f"{stage} has claims still marked needs-review: {sorted(needs_review)}")
    if unresolved_findings:
        errors.append(
            f"{stage} has unresolved design-limiting or major findings: {sorted(unresolved_findings)}"
        )
    if unresolved_responses:
        errors.append(f"{stage} has open or planned response items: {sorted(unresolved_responses)}")


def _audit_full(
    root: Path,
    stage: str,
    tables: dict[str, list[dict[str, str]]],
    runs: dict[str, dict[str, str]],
    results: dict[str, dict[str, str]],
    claims: dict[str, set[str]],
    unresolved_findings: set[str],
    unresolved_responses: set[str],
    errors: list[str],
    warnings: list[str],
    limits: tuple[int, int, int],
) -> None:
    if stage_at_least("full-research-lifecycle", stage, "question") and not nonempty_without_placeholder(root / "governance/charter.md"):
        errors.append("question stage requires a completed governance charter")
    if stage_at_least("full-research-lifecycle", stage, "protocol") and not nonempty_without_placeholder(root / "protocol/protocol.md"):
        errors.append("protocol stage requires a completed protocol")
    pilot = _check_pilot(root, errors) if stage_at_least("full-research-lifecycle", stage, "pilot") else None
    if pilot == "stop" and stage_at_least("full-research-lifecycle", stage, "execution"):
        errors.append("project advanced beyond a pilot stop decision")
    if stage_at_least("full-research-lifecycle", stage, "execution"):
        complete = [
            row
            for row in runs.values()
            if row.get("phase", "").lower() in {"definitive", "replication"}
            and row.get("status", "").lower() == "complete"
        ]
        if not complete:
            errors.append("execution stage requires a complete definitive or replication run")
    if stage_at_least("full-research-lifecycle", stage, "analysis") and not any(
        row.get("status", "").lower() in ACTIVE_RESULT_STATUSES for row in results.values()
    ):
        errors.append("analysis stage requires an active, reported, or confirmed result")
    if stage_at_least("full-research-lifecycle", stage, "manuscript"):
        _check_manuscript(root, claims["manuscript"], errors, warnings, limits)
    if stage_at_least("full-research-lifecycle", stage, "internal-review"):
        _review_complete(root, tables.get("review/findings.csv", []), errors, "internal review")
    if stage_at_least("full-research-lifecycle", stage, "journal-selection"):
        _journal_selection(root, errors, warnings)
    if stage_at_least("full-research-lifecycle", stage, "submission-ready") and not nonempty_without_placeholder(root / "publication/submission-checklist.md"):
        errors.append("submission-ready stage requires a completed submission checklist")
    if stage_at_least("full-research-lifecycle", stage, "revision") and not tables.get("review/response-matrix.csv"):
        errors.append("revision stage requires response-matrix records")
    if stage_at_least("full-research-lifecycle", stage, "accepted"):
        _check_publication_decision(root, errors)
    if stage_at_least("full-research-lifecycle", stage, "archived"):
        release_rows = tables.get("publication/release-manifest.csv", [])
        if not release_rows:
            errors.append("archived stage requires release-manifest records")
        else:
            _check_release_manifest(root, release_rows, errors)
        if not nonempty_without_placeholder(root / "publication/correction-plan.md"):
            errors.append("archived stage requires a completed correction plan")
    _check_ship_readiness(
        stage,
        claims["needs_review"],
        unresolved_findings,
        unresolved_responses,
        errors,
    )


def _audit_search_mode(
    root: Path,
    stage: str,
    tables: dict[str, list[dict[str, str]]],
    search_sets: dict[str, set[str]],
    claims: dict[str, set[str]],
    errors: list[str],
) -> None:
    if stage_at_least("systematic-search", stage, "protocol"):
        if not nonempty_without_placeholder(root / "governance/charter.md"):
            errors.append("protocol stage requires a completed governance charter")
        if not nonempty_without_placeholder(root / "protocol/search-protocol.md"):
            errors.append("protocol stage requires a completed search protocol")
    for required_stage, table in (
        ("search", "evidence/search-log.csv"),
        ("screening", "evidence/screening.csv"),
        ("extraction", "evidence/extraction.csv"),
    ):
        if stage_at_least("systematic-search", stage, required_stage) and not tables.get(table):
            errors.append(f"{required_stage} stage requires {table} records")
    if stage_at_least("systematic-search", stage, "synthesis"):
        if not nonempty_without_placeholder(root / "evidence/synthesis.md"):
            errors.append("synthesis stage requires a completed evidence synthesis")
        if not claims["manuscript"]:
            errors.append("synthesis stage requires an evidence-linked active claim")
        _check_flow(root, search_sets, errors)
    if stage_at_least("systematic-search", stage, "internal-review") and not nonempty_without_placeholder(root / "evidence/search-audit.md"):
        errors.append("internal-review stage requires a completed search audit")


def _audit_peer_mode(
    root: Path,
    stage: str,
    findings: list[dict[str, str]],
    unresolved: set[str],
    errors: list[str],
) -> None:
    if stage_at_least("peer-review", stage, "review"):
        if not nonempty_without_placeholder(root / "governance/charter.md"):
            errors.append("review stage requires a completed governance charter")
        _review_complete(root, findings, errors, "review stage")
    if stage_at_least("peer-review", stage, "final") and unresolved:
        errors.append(f"final peer-review stage has unresolved major findings: {sorted(unresolved)}")


def _audit_prose_mode(
    root: Path,
    stage: str,
    revisions: list[dict[str, str]],
    errors: list[str],
) -> None:
    if stage_at_least("scientific-prose", stage, "revision"):
        if not nonempty_without_placeholder(root / "governance/charter.md"):
            errors.append("revision stage requires a completed governance charter")
        if not revisions:
            errors.append("revision stage requires revision-log records")
        if not nonempty_without_placeholder(root / "manuscript/protected-spans.txt"):
            errors.append("revision stage requires a completed protected-spans record")
    if stage_at_least("scientific-prose", stage, "final"):
        incomplete = [
            row
            for row in revisions
            if row.get("status", "").lower() not in {"complete", "accepted", "resolved"}
        ]
        if incomplete:
            errors.append("final prose stage has incomplete revision-log records")
        if not nonempty_without_placeholder(root / "manuscript/residual-concerns.md"):
            errors.append("final prose stage requires resolved residual-concerns.md")


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

    for relative in COMMON_FILES:
        if not (root / relative).is_file():
            errors.append(f"missing required file: {relative}")
    try:
        project = load_json(root / "project.json")
        state = load_json(root / "state.json")
    except ValidationError as exc:
        errors.append(str(exc))
        return {"passed": False, "errors": errors, "warnings": warnings, "metrics": tree}
    if not isinstance(project, dict) or not isinstance(state, dict):
        errors.append("project.json and state.json must contain JSON objects")
        return {"passed": False, "errors": errors, "warnings": warnings, "metrics": tree}
    if project.get("schema_version") != SCHEMA_VERSION or state.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"project and state schema_version must be {SCHEMA_VERSION}")
    if not isinstance(project.get("name"), str) or not project["name"].strip():
        errors.append("project.name must be nonempty")
    _timestamp(str(project.get("created_at", "")), errors, "project.created_at")
    _timestamp(str(state.get("updated_at", "")), errors, "state.updated_at")

    mode = project.get("mode")
    if mode not in STAGES_BY_MODE:
        errors.append(f"invalid project mode: {mode!r}")
        return {"passed": False, "errors": errors, "warnings": warnings, "metrics": tree}
    stage = state.get("stage")
    if stage not in STAGES_BY_MODE[mode]:
        errors.append(f"invalid stage {stage!r} for mode {mode}")
        return {"passed": False, "errors": errors, "warnings": warnings, "metrics": tree}
    _validate_gate_sequence(mode, stage, state.get("completed_gates"), errors)
    for relative in REQUIRED_FILES_BY_MODE[mode]:
        if not (root / relative).is_file():
            errors.append(f"missing required file for {mode}: {relative}")

    tables: dict[str, list[dict[str, str]]] = {}
    for relative in CSV_REQUIREMENTS:
        if (root / relative).exists():
            tables[relative] = _load_table(root, relative, errors)
    source_ids, sources = _check_sources(
        root, tables.get("evidence/sources.csv", []), errors, warnings
    )
    search_sets = _check_search(root, tables, source_ids, errors, warnings)
    run_ids, runs = _check_runs(root, tables.get("study/runs.csv", []), errors)
    result_ids, results = _check_results(
        root, tables.get("study/results.csv", []), run_ids, runs, errors
    )
    claims = _check_claims(
        sources,
        tables.get("claims/claims.csv", []),
        result_ids,
        results,
        errors,
    )
    findings = tables.get("review/findings.csv", [])
    unresolved_findings = _check_review(root, findings, errors)
    response_rows = tables.get("review/response-matrix.csv", [])
    unresolved_responses = _check_responses(response_rows, errors)
    revisions = tables.get("manuscript/revision-log.csv", [])
    _check_revisions(root, revisions, errors, warnings)
    _check_external_actions(root, state, errors, warnings)

    limits = (max_entries, max_depth, max_total_bytes)
    if mode == "full-research-lifecycle":
        _audit_full(
            root,
            stage,
            tables,
            runs,
            results,
            claims,
            unresolved_findings,
            unresolved_responses,
            errors,
            warnings,
            limits,
        )
    elif mode == "systematic-search":
        _audit_search_mode(root, stage, tables, search_sets, claims, errors)
    elif mode == "peer-review":
        _audit_peer_mode(root, stage, findings, unresolved_findings, errors)
    else:
        _audit_prose_mode(root, stage, revisions, errors)

    metrics = {
        "mode": mode,
        "stage": stage,
        "sources": len(sources),
        "runs": len(runs),
        "results": len(results),
        "claims": len(tables.get("claims/claims.csv", [])),
        "findings": len(findings),
        "revisions": len(revisions),
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
