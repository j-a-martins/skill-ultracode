#!/usr/bin/env python3
"""Shared workspace schemas and lifecycle rules."""

from __future__ import annotations

SCHEMA_VERSION = 3
MODES = (
    "full-research-lifecycle",
    "systematic-search",
    "peer-review",
    "scientific-prose",
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

GATE_ORDER = {
    "full-research-lifecycle": [
        "question",
        "protocol",
        "pilot",
        "execution",
        "analysis",
        "manuscript",
        "internal-review",
        "journal-selection",
        "submission-package",
        "revision",
        "accepted",
        "archived",
    ],
    "systematic-search": [
        "protocol",
        "search",
        "screening",
        "extraction",
        "synthesis",
        "internal-review",
        "archived",
    ],
    "peer-review": ["review", "final", "archived"],
    "scientific-prose": ["revision", "final", "archived"],
}

STAGE_GATE = {
    "full-research-lifecycle": {
        "question": "question",
        "protocol": "protocol",
        "pilot": "pilot",
        "execution": "execution",
        "analysis": "analysis",
        "manuscript": "manuscript",
        "internal-review": "internal-review",
        "journal-selection": "journal-selection",
        "submission-ready": "submission-package",
        "revision": "revision",
        "accepted": "accepted",
        "archived": "archived",
    },
    "systematic-search": {
        stage: stage for stage in STAGES_BY_MODE["systematic-search"] if stage != "intake"
    },
    "peer-review": {
        stage: stage for stage in STAGES_BY_MODE["peer-review"] if stage != "intake"
    },
    "scientific-prose": {
        stage: stage for stage in STAGES_BY_MODE["scientific-prose"] if stage != "intake"
    },
}

COMMON_FILES = ["project.json", "state.json", "governance/charter.md"]
REQUIRED_FILES_BY_MODE = {
    "full-research-lifecycle": [
        "protocol/protocol.md",
        "protocol/amendments.md",
        "study/pilot-decision.json",
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
        "review/summary.json",
        "review/findings.csv",
        "review/response-matrix.csv",
        "publication/journals.csv",
        "publication/selected-journal.json",
        "publication/submission-checklist.md",
        "publication/decision.json",
        "publication/release-manifest.csv",
        "publication/correction-plan.md",
    ],
    "systematic-search": [
        "protocol/search-protocol.md",
        "protocol/amendments.md",
        "evidence/sources.csv",
        "evidence/search-log.csv",
        "evidence/deduplication.csv",
        "evidence/screening.csv",
        "evidence/extraction.csv",
        "evidence/flow.json",
        "evidence/synthesis.md",
        "evidence/search-audit.md",
        "claims/claims.csv",
    ],
    "peer-review": [
        "evidence/sources.csv",
        "review/review.md",
        "review/summary.json",
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
    "evidence/sources.csv": [
        "source_id",
        "title",
        "status",
        "evidence_level",
        "record_path",
        "record_sha256",
        "verified_at",
    ],
    "evidence/search-log.csv": [
        "search_id",
        "source",
        "interface",
        "query",
        "executed_at",
        "result_count",
        "export_path",
        "export_sha256",
    ],
    "evidence/deduplication.csv": [
        "cluster_id",
        "canonical_source_id",
        "member_source_ids",
        "method",
        "resolver",
    ],
    "evidence/screening.csv": [
        "record_id",
        "source_ids",
        "stage",
        "decision",
        "exclusion_reason",
    ],
    "evidence/extraction.csv": [
        "record_id",
        "source_ids",
        "method",
        "outcomes",
        "limitations",
        "evidence_access",
    ],
    "study/runs.csv": [
        "run_id",
        "kind",
        "phase",
        "started_at",
        "ended_at",
        "code_version",
        "code_path",
        "code_sha256",
        "data_version",
        "data_path",
        "data_sha256",
        "environment",
        "environment_path",
        "environment_sha256",
        "parameters",
        "raw_output",
        "raw_output_sha256",
        "status",
    ],
    "study/results.csv": [
        "result_id",
        "run_ids",
        "analysis_code",
        "analysis_code_sha256",
        "input_paths",
        "input_sha256s",
        "estimate",
        "uncertainty",
        "robustness",
        "status",
    ],
    "claims/claims.csv": [
        "claim_id",
        "text",
        "claim_type",
        "source_ids",
        "result_ids",
        "status",
        "limitations",
    ],
    "manuscript/revision-log.csv": [
        "revision_id",
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
    ],
    "review/findings.csv": [
        "finding_id",
        "severity",
        "confidence",
        "location",
        "finding",
        "evidence",
        "consequence",
        "action",
        "status",
    ],
    "review/response-matrix.csv": [
        "comment_id",
        "comment",
        "assessment",
        "rationale",
        "action",
        "manuscript_change",
        "evidence",
        "residual_limitation",
        "status",
    ],
    "publication/journals.csv": [
        "journal",
        "issn",
        "scope_fit",
        "methods_fit",
        "audience_fit",
        "article_fit",
        "open_science_fit",
        "provider",
        "metric_name",
        "metric_year",
        "category",
        "quartile",
        "verification_url",
        "evidence_path",
        "evidence_sha256",
        "verified_date",
        "human_verified_by",
        "human_verified_at",
    ],
    "publication/release-manifest.csv": [
        "artifact",
        "path",
        "sha256",
        "license",
        "archived_at",
    ],
}

MANUSCRIPT_CLAIM_STATUSES = {"active", "needs-review"}
INACTIVE_CLAIM_STATUSES = {"withdrawn", "rejected", "superseded"}
RESULT_STATUSES = {
    "draft",
    "active",
    "reported",
    "confirmed",
    "failed",
    "withdrawn",
    "superseded",
}
ACTIVE_RESULT_STATUSES = {"active", "reported", "confirmed"}
SOURCE_STATUSES = {
    "candidate",
    "included",
    "verified",
    "corrected",
    "excluded",
    "unresolved",
    "withdrawn",
    "retracted",
}
CLAIM_ELIGIBLE_SOURCE_STATUSES = {"verified", "corrected"}
SOURCE_INELIGIBLE = {"candidate", "included", "excluded", "unresolved", "withdrawn"}
EVIDENCE_LEVELS = {"metadata", "abstract", "full-text", "data", "code", "artifact"}
FINDING_SEVERITIES = {"design-limiting", "major", "minor", "editorial", "strength"}
FINDING_STATUSES = {
    "open",
    "addressed",
    "partly-addressed",
    "disputed",
    "accepted-limitation",
    "not-applicable",
}
UNRESOLVED_FINDING_STATUSES = {"open", "partly-addressed", "disputed"}
CONFIDENCE_LEVELS = {"high", "medium", "low", "not-assessable"}
RESPONSE_STATUSES = {
    "open",
    "planned",
    "implemented",
    "verified",
    "not-adopted",
    "accepted-limitation",
}
UNRESOLVED_RESPONSE_STATUSES = {"open", "planned"}
SHIPPING_STAGES = {"submission-ready", "accepted", "archived"}


def stage_at_least(mode: str, stage: str, required: str) -> bool:
    order = STAGES_BY_MODE[mode]
    return order.index(stage) >= order.index(required)


def expected_gates(mode: str, stage: str) -> list[str]:
    gate = STAGE_GATE[mode].get(stage)
    if gate is None:
        return []
    order = GATE_ORDER[mode]
    return order[: order.index(gate) + 1]


def is_shipping_stage(mode: str, stage: str) -> bool:
    return mode == "full-research-lifecycle" and stage in SHIPPING_STAGES
