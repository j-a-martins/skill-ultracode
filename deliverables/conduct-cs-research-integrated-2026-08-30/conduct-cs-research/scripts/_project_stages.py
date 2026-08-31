#!/usr/bin/env python3
"""Stage-level readiness checks for governed research workspaces."""

from __future__ import annotations

from pathlib import Path

from _common import nonempty_without_placeholder
from _project_model import ACTIVE_RESULT_STATUSES, is_shipping_stage, stage_at_least
from _project_records import (
    check_flow,
    check_journal_selection,
    check_manuscript,
    check_pilot,
    check_publication_decision,
    check_release_manifest,
    review_complete,
)


def check_ship_readiness(
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
            f"{stage} has unresolved design-limiting or major findings: "
            f"{sorted(unresolved_findings)}"
        )
    if unresolved_responses:
        errors.append(
            f"{stage} has open or planned response items: {sorted(unresolved_responses)}"
        )


def audit_full(
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
    mode = "full-research-lifecycle"
    if stage_at_least(mode, stage, "question") and not nonempty_without_placeholder(
        root / "governance/charter.md"
    ):
        errors.append("question stage requires a completed governance charter")
    if stage_at_least(mode, stage, "protocol") and not nonempty_without_placeholder(
        root / "protocol/protocol.md"
    ):
        errors.append("protocol stage requires a completed protocol")

    pilot = check_pilot(root, errors) if stage_at_least(mode, stage, "pilot") else None
    if pilot == "stop" and stage_at_least(mode, stage, "execution"):
        errors.append("project advanced beyond a pilot stop decision")
    if stage_at_least(mode, stage, "execution"):
        completed = [
            row
            for row in runs.values()
            if row.get("phase", "").lower() in {"definitive", "replication"}
            and row.get("status", "").lower() == "complete"
        ]
        if not completed:
            errors.append("execution stage requires a complete definitive or replication run")
    if stage_at_least(mode, stage, "analysis") and not any(
        row.get("status", "").lower() in ACTIVE_RESULT_STATUSES
        for row in results.values()
    ):
        errors.append("analysis stage requires an active, reported, or confirmed result")
    if stage_at_least(mode, stage, "manuscript"):
        check_manuscript(root, claims["manuscript"], errors, warnings, limits)
    if stage_at_least(mode, stage, "internal-review"):
        review_complete(root, tables.get("review/findings.csv", []), errors, "internal review")
    if stage_at_least(mode, stage, "journal-selection"):
        check_journal_selection(root, errors, warnings)
    if stage_at_least(mode, stage, "submission-ready") and not nonempty_without_placeholder(
        root / "publication/submission-checklist.md"
    ):
        errors.append("submission-ready stage requires a completed submission checklist")
    if stage_at_least(mode, stage, "revision") and not tables.get(
        "review/response-matrix.csv"
    ):
        errors.append("revision stage requires response-matrix records")
    if stage_at_least(mode, stage, "accepted"):
        check_publication_decision(root, errors)
    if stage_at_least(mode, stage, "archived"):
        release_rows = tables.get("publication/release-manifest.csv", [])
        if not release_rows:
            errors.append("archived stage requires release-manifest records")
        else:
            check_release_manifest(root, release_rows, errors)
        if not nonempty_without_placeholder(root / "publication/correction-plan.md"):
            errors.append("archived stage requires a completed correction plan")
    check_ship_readiness(
        stage,
        claims["needs_review"],
        unresolved_findings,
        unresolved_responses,
        errors,
    )


def audit_search_mode(
    root: Path,
    stage: str,
    tables: dict[str, list[dict[str, str]]],
    search_sets: dict[str, set[str]],
    claims: dict[str, set[str]],
    errors: list[str],
) -> None:
    mode = "systematic-search"
    if stage_at_least(mode, stage, "protocol"):
        if not nonempty_without_placeholder(root / "governance/charter.md"):
            errors.append("protocol stage requires a completed governance charter")
        if not nonempty_without_placeholder(root / "protocol/search-protocol.md"):
            errors.append("protocol stage requires a completed search protocol")
    for required_stage, table in (
        ("search", "evidence/search-log.csv"),
        ("screening", "evidence/screening.csv"),
        ("extraction", "evidence/extraction.csv"),
    ):
        if stage_at_least(mode, stage, required_stage) and not tables.get(table):
            errors.append(f"{required_stage} stage requires {table} records")
    if stage_at_least(mode, stage, "synthesis"):
        if not nonempty_without_placeholder(root / "evidence/synthesis.md"):
            errors.append("synthesis stage requires a completed evidence synthesis")
        if not claims["manuscript"]:
            errors.append("synthesis stage requires an evidence-linked active claim")
        check_flow(root, search_sets, errors)
    if stage_at_least(mode, stage, "internal-review"):
        if not nonempty_without_placeholder(root / "evidence/search-audit.md"):
            errors.append("internal-review stage requires a completed search audit")
        if claims["needs_review"]:
            errors.append(
                "internal-review search stage has claims still marked needs-review: "
                f"{sorted(claims['needs_review'])}"
            )


def audit_peer_mode(
    root: Path,
    stage: str,
    findings: list[dict[str, str]],
    unresolved: set[str],
    errors: list[str],
) -> None:
    mode = "peer-review"
    if stage_at_least(mode, stage, "review"):
        if not nonempty_without_placeholder(root / "governance/charter.md"):
            errors.append("review stage requires a completed governance charter")
        review_complete(root, findings, errors, "review stage")
    if stage_at_least(mode, stage, "final") and unresolved:
        errors.append(
            f"final peer-review stage has unresolved major findings: {sorted(unresolved)}"
        )


def audit_prose_mode(
    root: Path,
    stage: str,
    revisions: list[dict[str, str]],
    errors: list[str],
) -> None:
    mode = "scientific-prose"
    if stage_at_least(mode, stage, "revision"):
        if not nonempty_without_placeholder(root / "governance/charter.md"):
            errors.append("revision stage requires a completed governance charter")
        if not revisions:
            errors.append("revision stage requires revision-log records")
        if not nonempty_without_placeholder(root / "manuscript/protected-spans.txt"):
            errors.append("revision stage requires a completed protected-spans record")
    if stage_at_least(mode, stage, "final"):
        incomplete = [
            row
            for row in revisions
            if row.get("status", "").lower() not in {"complete", "accepted", "resolved"}
        ]
        if incomplete:
            errors.append("final prose stage has incomplete revision-log records")
        if not nonempty_without_placeholder(root / "manuscript/residual-concerns.md"):
            errors.append("final prose stage requires resolved residual-concerns.md")
