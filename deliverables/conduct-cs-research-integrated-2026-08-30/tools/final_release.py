#!/usr/bin/env python3
"""Run the final release gate with all runtime-evaluation JSONL shards."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import release

ORIGINAL_VALIDATE_SUPPORTING = release.validate_supporting_artifacts


def validate_eval_corpus() -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    cases: list[dict[str, Any]] = []
    seen: set[str] = set()
    shards = sorted(release.EVALS.glob("*.jsonl"))
    if not shards:
        return ["no runtime-evaluation JSONL shards found"], {"eval_shards": 0, "eval_cases": 0, "critical_eval_cases": 0}

    for shard in shards:
        try:
            text = release.stable_read_text(shard)
        except release.ReleaseError as exc:
            errors.append(str(exc))
            continue
        for line_number, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                continue
            try:
                item = release.load_strict_json(line)
            except Exception as exc:
                errors.append(f"{shard.name}:{line_number}: {exc}")
                continue
            if not isinstance(item, dict):
                errors.append(f"{shard.name}:{line_number}: case must be an object")
                continue
            case_id = item.get("id")
            if not isinstance(case_id, str) or not re.fullmatch(r"[a-z0-9-]+", case_id):
                errors.append(f"{shard.name}:{line_number}: invalid id")
            elif case_id in seen:
                errors.append(f"{shard.name}:{line_number}: duplicate id {case_id}")
            else:
                seen.add(case_id)
            if item.get("mode") not in release.MODES | {None}:
                errors.append(f"{shard.name}:{line_number}: invalid mode")
            if item.get("severity") not in {"critical", "major", "minor"}:
                errors.append(f"{shard.name}:{line_number}: invalid severity")
            if not isinstance(item.get("prompt"), str) or not item["prompt"].strip():
                errors.append(f"{shard.name}:{line_number}: prompt is empty")
            for field in ("expected", "forbidden"):
                value = item.get(field)
                if not isinstance(value, list) or not value or any(not isinstance(entry, str) or not entry.strip() for entry in value):
                    errors.append(f"{shard.name}:{line_number}: {field} must be a nonempty string list")
            cases.append(item)

    metrics = {
        "eval_shards": len(shards),
        "eval_cases": len(cases),
        "critical_eval_cases": sum(1 for item in cases if item.get("severity") == "critical"),
    }
    if metrics["eval_cases"] < 80:
        errors.append(f"combined evaluation corpus is too small: {metrics['eval_cases']}<80")
    if metrics["critical_eval_cases"] < 45:
        errors.append(f"combined evaluation corpus lacks critical-case depth: {metrics['critical_eval_cases']}<45")
    required_ids = {
        "final-blank-csv-gate-bypass",
        "final-pilot-stop-bypass",
        "final-bib-comment-key-spoof",
        "final-latex-import-traversal",
        "final-prose-direction-reversal",
        "final-q1-evidence-mutation",
        "final-accepted-without-decision-bytes",
        "final-expired-action-authorization",
    }
    missing = sorted(required_ids - seen)
    if missing:
        errors.append(f"combined evaluation corpus lacks final-audit cases: {missing}")
    return errors, metrics


def validate_supporting_artifacts() -> tuple[list[str], list[str], dict[str, Any]]:
    errors, warnings, metrics = ORIGINAL_VALIDATE_SUPPORTING()
    errors = [
        item
        for item in errors
        if not item.startswith("evaluation dataset is too small")
        and not item.startswith("evaluation dataset lacks critical-case depth")
    ]
    corpus_errors, corpus_metrics = validate_eval_corpus()
    errors.extend(corpus_errors)
    metrics.update(corpus_metrics)
    return errors, warnings, metrics


release.validate_supporting_artifacts = validate_supporting_artifacts

if __name__ == "__main__":
    raise SystemExit(release.main())
