#!/usr/bin/env python3
"""Create a compact, create-only research workspace."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from _common import utc_now, write_json_new

MODES = (
    "full-research-lifecycle",
    "systematic-search",
    "peer-review",
    "scientific-prose",
)

CORE_TEXT = {
    "governance/charter.md": "# Research charter\n\nTODO: objective, contribution, study family, governance, constraints, authorship, ethics, confidentiality, and AI-use policy.\n",
    "protocol/protocol.md": "# Protocol\n\nStatus: prospective | retrospective\n\nTODO: research questions, methods, outcomes, analysis, stopping criteria, robustness, and reporting route.\n",
    "protocol/amendments.md": "# Protocol amendments\n\nRecord date, trigger, decision, affected artifacts, and whether the change preceded observation of the affected results.\n",
    "evidence/sources.csv": "source_id,title,authors,year,venue,doi,url,status,evidence_level,notes\n",
    "study/runs.csv": "run_id,kind,started_at,ended_at,code_version,data_version,environment,parameters,raw_output,status,notes\n",
    "study/results.csv": "result_id,run_ids,analysis_code,estimate,uncertainty,robustness,status,notes\n",
    "study/deviations.md": "# Deviations and failures\n\nRecord protocol deviations, failed runs, exclusions, and consequences.\n",
    "claims/claims.csv": "claim_id,text,source_ids,result_ids,status,limitations,manuscript_locations\n",
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
    "publication/journals.csv": "journal,scope_fit,methods_fit,audience_fit,article_fit,open_science_fit,provider,metric_year,category,quartile,verification_url,verified_date,notes\n",
    "publication/selected-journal.json": "{}\n",
    "publication/submission-checklist.md": "# Submission checklist\n\nTODO: current venue instructions, exact payload, disclosures, author approval, destination, and action-specific authorization.\n",
}

MODE_TEXT = {
    "systematic-search": {
        "evidence/search-log.csv": "search_id,source,interface,query,executed_at,filters,result_count,export_path,export_sha256,notes\n",
        "evidence/screening.csv": "record_id,source_ids,title,stage,decision,exclusion_reason,reviewer,notes\n",
        "evidence/extraction.csv": "record_id,study_family,context,method,data,comparators,outcomes,limitations,evidence_access,notes\n",
        "evidence/search-protocol.md": "# Search protocol\n\nTODO: review type, question, sources, translated queries, eligibility, screening, extraction, appraisal, synthesis, stopping, and update plan.\n",
    },
    "peer-review": {
        "review/review.md": "# Review\n\nTODO: manuscript reconstruction, strengths, design-limiting findings, major findings, minor findings, recommendation, and confidence.\n",
        "review/response-matrix.csv": "comment_id,comment,assessment,rationale,action,manuscript_change,evidence,status\n",
    },
    "scientific-prose": {
        "manuscript/revision-log.csv": "revision_id,source_path,revised_path,scope,protected_content,material_changes,residual_concerns,status\n",
        "manuscript/protected-spans.txt": "Record citations, equations, numbers, identifiers, quotations, and other spans that must remain unchanged.\n",
    },
}


def project_files(mode: str) -> dict[str, str]:
    files = dict(CORE_TEXT)
    if mode == "full-research-lifecycle":
        for additions in MODE_TEXT.values():
            files.update(additions)
    else:
        files.update(MODE_TEXT.get(mode, {}))
    return files


def create_project(target: Path, name: str, mode: str) -> dict[str, object]:
    if not name.strip() or any(char in name for char in "\\/\x00"):
        raise ValueError("project name must be non-empty and contain no path separators")
    if target.exists() or target.is_symlink():
        raise FileExistsError(f"target already exists: {target}")

    target.parent.mkdir(parents=True, exist_ok=True)
    created = False
    try:
        target.mkdir(mode=0o755)
        created = True
        for relative, content in project_files(mode).items():
            path = target / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("x", encoding="utf-8", newline="\n") as handle:
                handle.write(content)

        now = utc_now()
        write_json_new(
            target / "project.json",
            {
                "schema_version": 1,
                "name": name.strip(),
                "mode": mode,
                "created_at": now,
                "study_family": None,
                "target_venue": None,
            },
        )
        write_json_new(
            target / "state.json",
            {
                "schema_version": 1,
                "stage": "intake",
                "completed_gates": [],
                "external_actions": [],
                "updated_at": now,
            },
        )
        files = sorted(str(path.relative_to(target)) for path in target.rglob("*") if path.is_file())
        return {"project": str(target), "mode": mode, "files_created": len(files), "files": files}
    except Exception:
        if created:
            shutil.rmtree(target, ignore_errors=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--name", required=True)
    parser.add_argument("--mode", choices=MODES, default="full-research-lifecycle")
    args = parser.parse_args()
    try:
        result = create_project(args.output.expanduser(), args.name, args.mode)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
