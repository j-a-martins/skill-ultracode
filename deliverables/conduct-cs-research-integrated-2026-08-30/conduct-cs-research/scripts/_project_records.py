#!/usr/bin/env python3
"""Record-level validators for governed research workspaces."""

from __future__ import annotations

import re
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
from _project_model import (
    ACTIVE_RESULT_STATUSES,
    CONFIDENCE_LEVELS,
    CSV_REQUIREMENTS,
    EVIDENCE_LEVELS,
    FINDING_SEVERITIES,
    FINDING_STATUSES,
    GATE_ORDER,
    INACTIVE_CLAIM_STATUSES,
    MANUSCRIPT_CLAIM_STATUSES,
    RESPONSE_STATUSES,
    RESULT_STATUSES,
    SOURCE_INELIGIBLE,
    SOURCE_STATUSES,
    UNRESOLVED_FINDING_STATUSES,
    UNRESOLVED_RESPONSE_STATUSES,
    expected_gates,
)

RECORD_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
CLUSTER_ID_RE = re.compile(r"^K\d{4}$")


def required(row: dict[str, Any], fields: tuple[str, ...], errors: list[str], prefix: str) -> None:
    for field in fields:
        if not str(row.get(field, "")).strip():
            errors.append(f"{prefix}: missing {field}")


def timestamp(value: str, errors: list[str], prefix: str) -> datetime | None:
    try:
        return parse_timestamp(value, field=prefix)
    except ValidationError as exc:
        errors.append(str(exc))
        return None


def path_hash(
    root: Path,
    row: dict[str, str],
    path_field: str,
    hash_field: str,
    errors: list[str],
    prefix: str,
    *,
    required_pair: bool = False,
    allow_not_applicable: bool = False,
) -> Path | None:
    raw_path = row.get(path_field, "").strip()
    raw_hash = row.get(hash_field, "").strip().lower()
    if allow_not_applicable and raw_path.lower() == "not-applicable":
        if raw_hash:
            errors.append(f"{prefix}: not-applicable {path_field} must not carry a hash")
        return None
    if not raw_path and not raw_hash:
        if required_pair:
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


def id_set(
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


def load_table(root: Path, relative: str, errors: list[str]) -> list[dict[str, str]]:
    path = root / relative
    try:
        headers, rows = read_csv(path)
    except ValidationError as exc:
        errors.append(str(exc))
        return []
    errors.extend(require_headers(path, headers, CSV_REQUIREMENTS.get(relative, [])))
    return rows


def validate_gate_sequence(mode: str, stage: str, gates: Any, errors: list[str]) -> None:
    if not isinstance(gates, list) or any(not isinstance(item, str) for item in gates):
        errors.append("state.completed_gates must be a list of strings")
        return
    expected = expected_gates(mode, stage)
    if gates != expected:
        errors.append(f"stage {stage} requires completed_gates {expected}; got {gates}")
    unknown = sorted(set(gates) - set(GATE_ORDER[mode]))
    if unknown:
        errors.append(f"state.completed_gates contains unknown gates: {unknown}")


def check_external_actions(
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
        required(action, ("action", "destination"), errors, prefix)
        if status == "cancelled":
            required(action, ("outcome",), errors, prefix)
            continue
        _check_action_payload(root, action.get("payload"), errors, prefix)
        authorized = expires = None
        if status in {"authorized", "performed", "failed"}:
            required(
                action,
                ("authorized_at", "expires_at", "authorized_by", "authorization_statement"),
                errors,
                prefix,
            )
            authorized = timestamp(str(action.get("authorized_at", "")), errors, f"{prefix}.authorized_at")
            expires = timestamp(str(action.get("expires_at", "")), errors, f"{prefix}.expires_at")
            if authorized and expires:
                if expires <= authorized:
                    errors.append(f"{prefix}: expires_at must follow authorized_at")
                if (expires - authorized).total_seconds() > 48 * 3600:
                    errors.append(f"{prefix}: authorization window exceeds 48 hours")
                if status == "authorized" and expires < now:
                    errors.append(f"{prefix}: authorization has expired")
        if status in {"performed", "failed"}:
            required(action, ("performed_at", "outcome"), errors, prefix)
            performed = timestamp(str(action.get("performed_at", "")), errors, f"{prefix}.performed_at")
            if performed and authorized and performed < authorized:
                errors.append(f"{prefix}: performed_at precedes authorization")
            if performed and expires and performed > expires:
                errors.append(f"{prefix}: action occurred after authorization expiry")
        if status == "prepared":
            warnings.append(f"{prefix}: prepared is not authorization to transmit")


def _check_action_payload(root: Path, payload: Any, errors: list[str], prefix: str) -> None:
    if not isinstance(payload, list) or not payload:
        errors.append(f"{prefix} lacks an exact payload list")
        return
    seen_paths: set[str] = set()
    for index, item in enumerate(payload):
        item_prefix = f"{prefix}.payload[{index}]"
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


def check_sources(
    root: Path,
    rows: list[dict[str, str]],
    errors: list[str],
    warnings: list[str],
) -> tuple[set[str], dict[str, dict[str, str]]]:
    source_ids = id_set(rows, "source_id", "evidence/sources.csv", errors)
    by_id = {row.get("source_id", ""): row for row in rows if row.get("source_id")}
    for index, row in enumerate(rows, start=2):
        prefix = f"evidence/sources.csv:{index}"
        required(row, ("title", "status", "evidence_level"), errors, prefix)
        status = row.get("status", "").lower()
        level = row.get("evidence_level", "").lower()
        if status not in SOURCE_STATUSES:
            errors.append(f"{prefix}: invalid status '{status}'")
        if level not in EVIDENCE_LEVELS:
            errors.append(f"{prefix}: invalid evidence_level '{level}'")
        record_required = status in {"verified", "corrected", "retracted"}
        path_hash(
            root,
            row,
            "record_path",
            "record_sha256",
            errors,
            prefix,
            required_pair=record_required,
        )
        verified_at = row.get("verified_at", "").strip()
        if record_required or verified_at:
            timestamp(verified_at, errors, f"{prefix}.verified_at")
        if status == "retracted" and "retract" not in row.get("notes", "").lower():
            warnings.append(f"{prefix}: retracted source lacks an explanatory note")
    return source_ids, by_id


def _check_search_log(
    root: Path,
    rows: list[dict[str, str]],
    errors: list[str],
    warnings: list[str],
) -> None:
    id_set(rows, "search_id", "evidence/search-log.csv", errors)
    for index, row in enumerate(rows, start=2):
        prefix = f"evidence/search-log.csv:{index}"
        required(row, ("source", "interface", "query", "executed_at", "result_count"), errors, prefix)
        timestamp(row.get("executed_at", ""), errors, f"{prefix}.executed_at")
        try:
            if int(row.get("result_count", "")) < 0:
                raise ValueError
        except ValueError:
            errors.append(f"{prefix}: result_count must be a nonnegative integer")
        export = path_hash(root, row, "export_path", "export_sha256", errors, prefix)
        if export is None and not (row.get("export_path") or row.get("export_sha256")):
            warnings.append(f"{prefix}: no hash-bound export; document the reproducible alternative")


def _check_screening(
    rows: list[dict[str, str]], source_ids: set[str], errors: list[str]
) -> dict[str, set[str]]:
    pairs: set[tuple[str, str]] = set()
    decisions: dict[tuple[str, str], str] = {}
    screened: set[str] = set()
    full_text: set[str] = set()
    included: set[str] = set()
    for index, row in enumerate(rows, start=2):
        prefix = f"evidence/screening.csv:{index}"
        record_id = row.get("record_id", "").strip()
        stage = row.get("stage", "").lower()
        decision = row.get("decision", "").lower()
        required(row, ("record_id", "source_ids", "stage", "decision"), errors, prefix)
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
            screened.add(record_id)
        if stage == "full-text" and record_id:
            full_text.add(record_id)
            if decisions.get((record_id, "title-abstract")) != "include":
                errors.append(f"{prefix}: full-text assessment lacks a title-abstract include decision")
            if decision == "include":
                included.add(record_id)
    return {"screened_ids": screened, "full_text_ids": full_text, "included_full_text": included}


def _check_extraction(
    rows: list[dict[str, str]],
    source_ids: set[str],
    included: set[str],
    errors: list[str],
) -> set[str]:
    extraction_ids = id_set(
        rows,
        "record_id",
        "evidence/extraction.csv",
        errors,
        pattern=RECORD_ID_RE,
    )
    access = {
        "metadata-only",
        "abstract-reviewed",
        "full-text-reviewed",
        "data-code-artifact-reviewed",
    }
    for index, row in enumerate(rows, start=2):
        prefix = f"evidence/extraction.csv:{index}"
        required(row, ("source_ids", "method", "outcomes", "limitations", "evidence_access"), errors, prefix)
        if row.get("record_id", "") not in included:
            errors.append(f"{prefix}: extraction lacks an included full-text record")
        for value in split_ids(row.get("source_ids", "")):
            if value not in source_ids:
                errors.append(f"{prefix}: unknown source_id '{value}'")
        if row.get("evidence_access", "").lower() not in access:
            errors.append(f"{prefix}: invalid evidence_access")
    return extraction_ids


def _check_deduplication(
    rows: list[dict[str, str]], source_ids: set[str], errors: list[str]
) -> None:
    id_set(rows, "cluster_id", "evidence/deduplication.csv", errors, pattern=CLUSTER_ID_RE)
    membership: dict[str, str] = {}
    for index, row in enumerate(rows, start=2):
        prefix = f"evidence/deduplication.csv:{index}"
        required(row, ("canonical_source_id", "member_source_ids", "method", "resolver"), errors, prefix)
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
                errors.append(f"{prefix}: source_id '{value}' belongs to clusters {prior} and {cluster}")
            membership[value] = cluster


def check_search(
    root: Path,
    tables: dict[str, list[dict[str, str]]],
    source_ids: set[str],
    errors: list[str],
    warnings: list[str],
) -> dict[str, set[str]]:
    _check_search_log(root, tables.get("evidence/search-log.csv", []), errors, warnings)
    screening = _check_screening(tables.get("evidence/screening.csv", []), source_ids, errors)
    screening["extraction_ids"] = _check_extraction(
        tables.get("evidence/extraction.csv", []),
        source_ids,
        screening["included_full_text"],
        errors,
    )
    _check_deduplication(tables.get("evidence/deduplication.csv", []), source_ids, errors)
    return screening


def check_runs(
    root: Path, rows: list[dict[str, str]], errors: list[str]
) -> tuple[set[str], dict[str, dict[str, str]]]:
    run_ids = id_set(rows, "run_id", "study/runs.csv", errors)
    by_id = {row.get("run_id", ""): row for row in rows if row.get("run_id")}
    for index, row in enumerate(rows, start=2):
        prefix = f"study/runs.csv:{index}"
        required(
            row,
            ("kind", "phase", "started_at", "code_version", "data_version", "environment", "parameters", "status"),
            errors,
            prefix,
        )
        phase = row.get("phase", "").lower()
        status = row.get("status", "").lower()
        if phase not in {"pilot", "exploratory", "definitive", "replication"}:
            errors.append(f"{prefix}: invalid phase '{phase}'")
        if status not in {"planned", "running", "complete", "failed", "cancelled"}:
            errors.append(f"{prefix}: invalid status '{status}'")
        started = timestamp(row.get("started_at", ""), errors, f"{prefix}.started_at")
        ended_raw = row.get("ended_at", "").strip()
        ended = timestamp(ended_raw, errors, f"{prefix}.ended_at") if ended_raw else None
        if status in {"complete", "failed", "cancelled"} and not ended_raw:
            errors.append(f"{prefix}: terminal run lacks ended_at")
        if started and ended and ended < started:
            errors.append(f"{prefix}: ended_at precedes started_at")
        for path_field, hash_field in (
            ("code_path", "code_sha256"),
            ("data_path", "data_sha256"),
            ("environment_path", "environment_sha256"),
        ):
            path_hash(
                root,
                row,
                path_field,
                hash_field,
                errors,
                prefix,
                required_pair=status == "complete",
                allow_not_applicable=True,
            )
        path_hash(
            root,
            row,
            "raw_output",
            "raw_output_sha256",
            errors,
            prefix,
            required_pair=status == "complete",
        )
    return run_ids, by_id


def check_results(
    root: Path,
    rows: list[dict[str, str]],
    run_ids: set[str],
    runs: dict[str, dict[str, str]],
    errors: list[str],
) -> tuple[set[str], dict[str, dict[str, str]]]:
    result_ids = id_set(rows, "result_id", "study/results.csv", errors)
    by_id = {row.get("result_id", ""): row for row in rows if row.get("result_id")}
    for index, row in enumerate(rows, start=2):
        prefix = f"study/results.csv:{index}"
        required(row, ("run_ids", "analysis_code", "estimate", "uncertainty", "robustness", "status"), errors, prefix)
        status = row.get("status", "").lower()
        if status not in RESULT_STATUSES:
            errors.append(f"{prefix}: invalid status '{status}'")
        active = status in ACTIVE_RESULT_STATUSES
        for value in split_ids(row.get("run_ids", "")):
            if value not in run_ids:
                errors.append(f"{prefix}: unknown run_id '{value}'")
            elif active and runs[value].get("status", "").lower() != "complete":
                errors.append(f"{prefix}: active result depends on non-complete run '{value}'")
        path_hash(
            root,
            row,
            "analysis_code",
            "analysis_code_sha256",
            errors,
            prefix,
            required_pair=active,
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
                verify_path_hash(root, raw_path, raw_hash.lower(), label=f"{prefix} input[{item_index}]")
            except ValidationError as exc:
                errors.append(str(exc))
    return result_ids, by_id


def check_claims(
    sources: dict[str, dict[str, str]],
    rows: list[dict[str, str]],
    result_ids: set[str],
    results: dict[str, dict[str, str]],
    errors: list[str],
) -> dict[str, set[str]]:
    id_set(rows, "claim_id", "claims/claims.csv", errors)
    manuscript: set[str] = set()
    needs_review: set[str] = set()
    types = {"background", "empirical", "formal", "methodological", "synthesis", "interpretation", "limitation", "retraction"}
    statuses = {"draft", *MANUSCRIPT_CLAIM_STATUSES, *INACTIVE_CLAIM_STATUSES}
    for index, row in enumerate(rows, start=2):
        prefix = f"claims/claims.csv:{index}"
        claim_id = row.get("claim_id", "")
        status = row.get("status", "").lower()
        claim_type = row.get("claim_type", "").lower()
        if status not in statuses:
            errors.append(f"{prefix}: invalid status '{status}'")
        if claim_type not in types:
            errors.append(f"{prefix}: invalid claim_type '{claim_type}'")
        active = status in MANUSCRIPT_CLAIM_STATUSES
        if active:
            manuscript.add(claim_id)
            required(row, ("text", "limitations"), errors, prefix)
            if has_placeholder(row.get("text", "")):
                errors.append(f"{prefix}: active claim contains a placeholder")
        if status == "needs-review":
            needs_review.add(claim_id)
        linked_sources = split_ids(row.get("source_ids", ""))
        linked_results = split_ids(row.get("result_ids", ""))
        if active and not (linked_sources or linked_results):
            errors.append(f"{prefix}: active claim has no evidence link")
        retracted: list[str] = []
        eligible = False
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
                eligible = True
        for value in linked_results:
            result = results.get(value)
            if value not in result_ids or result is None:
                errors.append(f"{prefix}: unknown result_id '{value}'")
            elif active and result.get("status", "").lower() not in ACTIVE_RESULT_STATUSES:
                errors.append(f"{prefix}: active claim depends on inactive result '{value}'")
        if active and retracted and claim_type != "retraction":
            if not eligible and not linked_results:
                errors.append(f"{prefix}: retracted source is the sole support for an active claim")
            if "retract" not in row.get("limitations", "").lower():
                errors.append(f"{prefix}: retracted evidence is not disclosed in limitations")
    return {"manuscript": manuscript, "needs_review": needs_review}


def check_review(root: Path, rows: list[dict[str, str]], errors: list[str]) -> set[str]:
    id_set(rows, "finding_id", "review/findings.csv", errors)
    unresolved: set[str] = set()
    for index, row in enumerate(rows, start=2):
        prefix = f"review/findings.csv:{index}"
        required(
            row,
            ("severity", "confidence", "location", "finding", "evidence", "consequence", "action", "status"),
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
    _check_review_summary(root, errors)
    return unresolved


def _check_review_summary(root: Path, errors: list[str]) -> None:
    path = root / "review/summary.json"
    if not path.exists():
        return
    try:
        summary = load_json(path)
    except ValidationError as exc:
        errors.append(str(exc))
        return
    if not isinstance(summary, dict):
        errors.append("review/summary.json must contain an object")
        return
    if not summary:
        return
    for field in ("scope", "recommendation", "confidence", "limitations"):
        if not isinstance(summary.get(field), str) or not summary[field].strip():
            errors.append(f"review/summary.json lacks nonempty {field}")
    if str(summary.get("confidence", "")).lower() not in CONFIDENCE_LEVELS:
        errors.append("review/summary.json has invalid confidence")


def check_responses(rows: list[dict[str, str]], errors: list[str]) -> set[str]:
    seen: set[str] = set()
    unresolved: set[str] = set()
    for index, row in enumerate(rows, start=2):
        prefix = f"review/response-matrix.csv:{index}"
        required(row, ("comment_id", "comment", "assessment", "rationale", "action", "status"), errors, prefix)
        comment_id = row.get("comment_id", "")
        if comment_id in seen:
            errors.append(f"{prefix}: duplicate comment_id '{comment_id}'")
        seen.add(comment_id)
        if row.get("assessment", "").lower() not in {"agree", "partly-agree", "disagree", "needs-clarification"}:
            errors.append(f"{prefix}: invalid assessment")
        status = row.get("status", "").lower()
        if status not in RESPONSE_STATUSES:
            errors.append(f"{prefix}: invalid status")
        if status in {"implemented", "verified"}:
            required(row, ("manuscript_change", "evidence"), errors, prefix)
        if status in UNRESOLVED_RESPONSE_STATUSES:
            unresolved.add(comment_id)
    return unresolved


def check_revisions(
    root: Path,
    rows: list[dict[str, str]],
    errors: list[str],
    warnings: list[str],
) -> None:
    id_set(rows, "revision_id", "manuscript/revision-log.csv", errors)
    for index, row in enumerate(rows, start=2):
        prefix = f"manuscript/revision-log.csv:{index}"
        required(
            row,
            ("source_path", "source_sha256", "revised_path", "revised_sha256", "scope", "protected_content", "material_changes", "residual_concerns", "audit_status", "status"),
            errors,
            prefix,
        )
        source = path_hash(root, row, "source_path", "source_sha256", errors, prefix, required_pair=True)
        revised = path_hash(root, row, "revised_path", "revised_sha256", errors, prefix, required_pair=True)
        if source and revised and source == revised:
            errors.append(f"{prefix}: source_path and revised_path must differ")
        status = row.get("status", "").lower()
        audit_status = row.get("audit_status", "").lower()
        if status not in {"open", "complete", "accepted", "resolved", "superseded"}:
            errors.append(f"{prefix}: invalid status")
        if audit_status not in {"pass", "manual-accepted", "fail"}:
            errors.append(f"{prefix}: invalid audit_status")
        if source and revised:
            _reconcile_prose_audit(row, audit_status, source, revised, errors, warnings, prefix)


def _reconcile_prose_audit(
    row: dict[str, str],
    audit_status: str,
    source: Path,
    revised: Path,
    errors: list[str],
    warnings: list[str],
    prefix: str,
) -> None:
    result = audit_prose.audit(source, revised, strict=True)
    if result["passed"] and audit_status == "fail":
        errors.append(f"{prefix}: audit_status says fail but deterministic audit passes")
    if result["passed"] or audit_status == "manual-accepted":
        if not result["passed"]:
            if row.get("material_changes", "").strip().lower() in {"", "none"}:
                errors.append(f"{prefix}: manual acceptance requires material_changes rationale")
            if row.get("residual_concerns", "").strip().lower() in {"", "none"}:
                errors.append(f"{prefix}: manual acceptance requires residual concerns")
            warnings.append(f"{prefix}: deterministic drift findings were manually accepted")
        return
    errors.append(f"{prefix}: strict semantic drift audit failed: {result['errors']}")


def check_flow(root: Path, sets: dict[str, set[str]], errors: list[str]) -> None:
    try:
        flow = load_json(root / "evidence/flow.json")
    except ValidationError as exc:
        errors.append(str(exc))
        return
    fields = ("identified", "deduplicated", "screened", "full_text_assessed", "included")
    if not isinstance(flow, dict) or any(not isinstance(flow.get(field), int) or flow[field] < 0 for field in fields):
        errors.append("evidence/flow.json requires five nonnegative integer counts")
        return
    if not flow["identified"] >= flow["deduplicated"] >= flow["screened"]:
        errors.append("identified, deduplicated, and screened counts are inconsistent")
    expected = {
        "screened": len(sets["screened_ids"]),
        "full_text_assessed": len(sets["full_text_ids"]),
        "included": len(sets["included_full_text"]),
    }
    for field, value in expected.items():
        if flow[field] != value:
            errors.append(f"evidence/flow.json {field}={flow[field]} but ledger requires {value}")
    if sets["included_full_text"] != sets["extraction_ids"]:
        missing = sorted(sets["included_full_text"] - sets["extraction_ids"])
        extra = sorted(sets["extraction_ids"] - sets["included_full_text"])
        errors.append(f"included/extraction record sets differ: missing={missing}, extra={extra}")


def check_pilot(root: Path, errors: list[str]) -> str | None:
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
    timestamp(str(decision.get("decided_at", "")), errors, "pilot.decided_at")
    if not isinstance(decision.get("protocol_effect"), str) or not decision.get("protocol_effect", "").strip():
        errors.append("study/pilot-decision.json protocol_effect is empty")
    _check_evidence_list(root, decision.get("evidence"), errors, "pilot evidence")
    if value == "revise":
        amendment_path = str(decision.get("amendment_path", ""))
        amendment_hash = str(decision.get("amendment_sha256", "")).lower()
        if amendment_path != "protocol/amendments.md":
            errors.append("pilot revise decision must bind protocol/amendments.md")
        try:
            verify_path_hash(root, amendment_path, amendment_hash, label="pilot amendment")
        except ValidationError as exc:
            errors.append(str(exc))
        if not nonempty_without_placeholder(root / "protocol/amendments.md"):
            errors.append("pilot revise decision requires a completed protocol amendment")
    return value


def _check_evidence_list(root: Path, evidence: Any, errors: list[str], label: str) -> None:
    if not isinstance(evidence, list) or not evidence:
        errors.append(f"{label} must be a nonempty list")
        return
    for index, item in enumerate(evidence):
        if not isinstance(item, dict):
            errors.append(f"{label}[{index}] must be an object")
            continue
        try:
            verify_path_hash(
                root,
                str(item.get("path", "")),
                str(item.get("sha256", "")).lower(),
                label=f"{label}[{index}]",
            )
        except ValidationError as exc:
            errors.append(str(exc))


def check_publication_decision(root: Path, errors: list[str]) -> None:
    try:
        decision = load_json(root / "publication/decision.json")
    except ValidationError as exc:
        errors.append(str(exc))
        return
    if not isinstance(decision, dict):
        errors.append("publication/decision.json must contain an object")
        return
    required(decision, ("status", "venue", "decided_at", "evidence_path", "evidence_sha256"), errors, "publication/decision.json")
    if str(decision.get("status", "")).lower() != "accepted":
        errors.append("accepted stage requires publication decision status accepted")
    timestamp(str(decision.get("decided_at", "")), errors, "publication.decision.decided_at")
    try:
        verify_path_hash(
            root,
            str(decision.get("evidence_path", "")),
            str(decision.get("evidence_sha256", "")).lower(),
            label="publication decision evidence",
        )
    except ValidationError as exc:
        errors.append(str(exc))


def check_release_manifest(root: Path, rows: list[dict[str, str]], errors: list[str]) -> None:
    seen: set[str] = set()
    for index, row in enumerate(rows, start=2):
        prefix = f"publication/release-manifest.csv:{index}"
        required(row, ("artifact", "path", "sha256", "license", "archived_at"), errors, prefix)
        artifact = row.get("artifact", "")
        if artifact in seen:
            errors.append(f"{prefix}: duplicate artifact '{artifact}'")
        seen.add(artifact)
        try:
            verify_path_hash(root, row.get("path", ""), row.get("sha256", "").lower(), label=prefix)
        except ValidationError as exc:
            errors.append(str(exc))
        timestamp(row.get("archived_at", ""), errors, f"{prefix}.archived_at")


def check_journal_selection(root: Path, errors: list[str], warnings: list[str]) -> None:
    result = score_journals.score(root / "publication/journals.csv")
    errors.extend(f"journal record: {item}" for item in result["errors"])
    warnings.extend(f"journal record: {item}" for item in result["warnings"])
    try:
        selected = load_json(root / "publication/selected-journal.json")
    except ValidationError as exc:
        errors.append(str(exc))
        return
    fields = ("journal", "issn", "fit_rationale", "selected_at", "q1_claim")
    if not isinstance(selected, dict) or any(not str(selected.get(field, "")).strip() for field in fields):
        errors.append("selected journal requires journal, ISSN, rationale, time, and q1_claim")
        return
    timestamp(str(selected["selected_at"]), errors, "selected-journal.selected_at")
    matches = [
        item for item in result["journals"]
        if str(item["journal"]).casefold() == str(selected["journal"]).casefold()
        and str(item["issn"]).upper() == str(selected["issn"]).upper()
    ]
    if not matches:
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
    exact = [item for item in matches if all(str(item.get(field, "")) == str(selected.get(field, "")) for field in exact_fields)]
    if len(exact) != 1 or not exact[0]["q1_verified"]:
        errors.append("verified Q1 selection lacks one matching verified observation")


def review_complete(root: Path, findings: list[dict[str, str]], errors: list[str], label: str) -> None:
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


def check_manuscript(
    root: Path,
    claim_ids: set[str],
    errors: list[str],
    warnings: list[str],
    limits: tuple[int, int, int],
) -> None:
    if not claim_ids:
        errors.append("manuscript stage requires an active or needs-review claim")
    try:
        text = read_text(root / "manuscript/main.tex")
    except ValidationError as exc:
        errors.append(str(exc))
        return
    if has_placeholder(text):
        errors.append("manuscript/main.tex contains unresolved placeholders")
    for claim_id in claim_ids:
        if f"claim:{claim_id}" not in text:
            errors.append(f"manuscript/main.tex lacks marker for claim {claim_id}")
    result = audit_latex.audit(
        root / "manuscript",
        Path("main.tex"),
        max_entries=limits[0],
        max_depth=limits[1],
        max_total_bytes=limits[2],
    )
    errors.extend(f"LaTeX audit: {item}" for item in result["errors"])
    warnings.extend(f"LaTeX audit: {item}" for item in result["warnings"])
