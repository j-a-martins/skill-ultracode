#!/usr/bin/env python3
"""Create a mode-proportionate, create-only academic-research workspace."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import stat
import sys
import tempfile
from pathlib import Path

from _common import utc_now, write_json_new, write_text_new

MODES = (
    "full-research-lifecycle",
    "systematic-search",
    "peer-review",
    "scientific-prose",
)

COMMON_TEXT = {
    "governance/charter.md": "# Research charter\n\nTODO: objective, deliverable, audience, governance, constraints, confidentiality, authorship, ethics, and AI-use policy.\n",
}

FULL_TEXT = {
    "protocol/protocol.md": "# Protocol\n\nStatus: prospective | retrospective\n\nTODO: questions, design, inputs, outcomes, analysis, stopping criteria, robustness, and reporting route.\n",
    "protocol/amendments.md": "# Protocol amendments\n\nRecord date, trigger, decision, affected artifacts, and whether the change preceded observation of the affected results.\n",
    "study/pilot-decision.json": "{}\n",
    "evidence/sources.csv": "source_id,title,authors,year,venue,doi,url,status,evidence_level,record_path,record_sha256,verified_at,notes\n",
    "evidence/search-protocol.md": "# Search protocol\n\nTODO: search mode, questions, sources, translated queries, eligibility, screening, extraction, appraisal, synthesis, stopping, and update plan.\n",
    "evidence/search-log.csv": "search_id,source,interface,query,executed_at,filters,result_count,export_path,export_sha256,notes\n",
    "evidence/screening.csv": "record_id,source_ids,title,stage,decision,exclusion_reason,reviewer,notes\n",
    "evidence/extraction.csv": "record_id,source_ids,study_family,context,method,data,comparators,outcomes,limitations,evidence_access,notes\n",
    "evidence/synthesis.md": "# Evidence synthesis\n\nTODO: synthesize included evidence, heterogeneity, contradictions, appraisal, limitations, and last-search date.\n",
    "study/runs.csv": "run_id,kind,phase,started_at,ended_at,code_version,code_path,code_sha256,data_version,data_path,data_sha256,environment,environment_path,environment_sha256,parameters,raw_output,raw_output_sha256,status,notes\n",
    "study/results.csv": "result_id,run_ids,analysis_code,analysis_code_sha256,input_paths,input_sha256s,estimate,uncertainty,robustness,status,notes\n",
    "study/deviations.md": "# Deviations and failures\n\nRecord protocol deviations, failed runs, exclusions, and consequences.\n",
    "claims/claims.csv": "claim_id,text,claim_type,source_ids,result_ids,status,limitations,manuscript_locations\n",
    "manuscript/main.tex": r"""\documentclass{article}
\usepackage{graphicx}
\usepackage{hyperref}
\title{TODO: Title}
\author{TODO: Authors}
\begin{document}
\maketitle
\begin{abstract}
TODO: Abstract.
\end{abstract}
\section{Introduction}
% claim:C0001
TODO: Introduction.
\section{Methods}
TODO: Methods.
\section{Results}
TODO: Results.
\section{Discussion}
TODO: Discussion and limitations.
\bibliographystyle{plain}
\bibliography{references}
\end{document}
""",
    "manuscript/references.bib": "% Add verified bibliography records.\n",
    "manuscript/revision-log.csv": "revision_id,source_path,source_sha256,revised_path,revised_sha256,scope,protected_content,material_changes,residual_concerns,audit_status,status\n",
    "manuscript/protected-spans.txt": "TODO: record citations, equations, numbers, identifiers, quotations, and other protected spans, or state that none exist.\n",
    "review/review.md": "# Internal review\n\nTODO: reconstruction, strengths, design-limiting findings, major findings, minor findings, recommendation, confidence, and review limitations. If no material finding exists, state `No material findings` rather than inventing one.\n",
    "review/summary.json": "{}\n",
    "review/findings.csv": "finding_id,severity,confidence,location,finding,evidence,consequence,action,status\n",
    "review/response-matrix.csv": "comment_id,comment,assessment,rationale,action,manuscript_change,evidence,residual_limitation,status\n",
    "publication/journals.csv": "journal,issn,scope_fit,methods_fit,audience_fit,article_fit,open_science_fit,provider,metric_name,metric_year,category,quartile,rank,denominator,verification_url,evidence_path,evidence_sha256,verified_date,human_verified_by,human_verified_at,notes\n",
    "publication/selected-journal.json": "{}\n",
    "publication/submission-checklist.md": "# Submission checklist\n\nTODO: current venue instructions, exact payload, disclosures, author approval, destination, and action-specific authorization.\n",
    "publication/decision.json": "{}\n",
    "publication/release-manifest.csv": "artifact,path,sha256,public_url,license,archived_at,notes\n",
    "publication/correction-plan.md": "# Correction and retraction response plan\n\nTODO: monitoring owner, contact route, correction criteria, artifact update policy, and escalation process.\n",
}

SYSTEMATIC_TEXT = {
    "protocol/search-protocol.md": FULL_TEXT["evidence/search-protocol.md"],
    "protocol/amendments.md": FULL_TEXT["protocol/amendments.md"],
    "evidence/sources.csv": FULL_TEXT["evidence/sources.csv"],
    "evidence/search-log.csv": FULL_TEXT["evidence/search-log.csv"],
    "evidence/deduplication.csv": "cluster_id,canonical_source_id,member_source_ids,method,resolver,notes\n",
    "evidence/screening.csv": FULL_TEXT["evidence/screening.csv"],
    "evidence/extraction.csv": FULL_TEXT["evidence/extraction.csv"],
    "evidence/flow.json": "{}\n",
    "evidence/synthesis.md": FULL_TEXT["evidence/synthesis.md"],
    "evidence/search-audit.md": "# Search audit\n\nTODO: assess protocol adherence, coverage, sentinel retrieval, provider failures, deduplication, screening, extraction, appraisal, synthesis, and limitations.\n",
    "claims/claims.csv": FULL_TEXT["claims/claims.csv"],
}

PEER_TEXT = {
    "evidence/sources.csv": FULL_TEXT["evidence/sources.csv"],
    "review/review.md": "# Peer review\n\nTODO: reconstruct the manuscript, identify strengths and evidence-backed findings, state recommendation and confidence, and audit the review itself. If no material finding exists, state `No material findings` rather than inventing one.\n",
    "review/summary.json": "{}\n",
    "review/findings.csv": FULL_TEXT["review/findings.csv"],
    "review/response-matrix.csv": FULL_TEXT["review/response-matrix.csv"],
}

PROSE_TEXT = {
    "manuscript/revision-log.csv": FULL_TEXT["manuscript/revision-log.csv"],
    "manuscript/protected-spans.txt": FULL_TEXT["manuscript/protected-spans.txt"],
    "manuscript/residual-concerns.md": "# Residual concerns\n\nTODO: record unresolved scientific ambiguity, missing evidence, possible source errors, or state `None`.\n",
}

MODE_TEXT = {
    "full-research-lifecycle": FULL_TEXT,
    "systematic-search": SYSTEMATIC_TEXT,
    "peer-review": PEER_TEXT,
    "scientific-prose": PROSE_TEXT,
}


def project_files(mode: str) -> dict[str, str]:
    files = dict(COMMON_TEXT)
    files.update(MODE_TEXT[mode])
    return files


def _safe_cleanup(staging: Path, identity: tuple[int, int]) -> None:
    try:
        info = staging.lstat()
    except FileNotFoundError:
        return
    if stat.S_ISDIR(info.st_mode) and not stat.S_ISLNK(info.st_mode) and (info.st_dev, info.st_ino) == identity:
        shutil.rmtree(staging)


def create_project(target: Path, name: str, mode: str) -> dict[str, object]:
    if not name.strip() or any(char in name for char in "\\/\x00"):
        raise ValueError("project name must be non-empty and contain no path separators")
    if mode not in MODES:
        raise ValueError(f"unsupported mode: {mode}")

    requested = target.expanduser()
    requested.parent.mkdir(parents=True, exist_ok=True)
    parent = requested.parent.resolve(strict=True)
    target = parent / requested.name
    if target.exists() or target.is_symlink():
        raise FileExistsError(f"target already exists: {target}")

    staging = Path(tempfile.mkdtemp(prefix=".conduct-cs-research-", dir=parent))
    info = staging.lstat()
    identity = (info.st_dev, info.st_ino)
    try:
        for relative, content in project_files(mode).items():
            path = staging / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            write_text_new(path, content)

        now = utc_now()
        write_json_new(
            staging / "project.json",
            {
                "schema_version": 3,
                "name": name.strip(),
                "mode": mode,
                "created_at": now,
                "study_family": None,
                "target_venue": None,
            },
        )
        write_json_new(
            staging / "state.json",
            {
                "schema_version": 3,
                "stage": "intake",
                "completed_gates": [],
                "external_actions": [],
                "updated_at": now,
            },
        )
        if target.exists() or target.is_symlink():
            raise FileExistsError(f"target appeared during initialization: {target}")
        os.rename(staging, target)
        files = sorted(str(path.relative_to(target)) for path in target.rglob("*") if path.is_file())
        return {"project": str(target), "mode": mode, "files_created": len(files), "files": files}
    except Exception:
        _safe_cleanup(staging, identity)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--name", required=True)
    parser.add_argument("--mode", choices=MODES, default="full-research-lifecycle")
    args = parser.parse_args()
    try:
        result = create_project(args.output, args.name, args.mode)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
