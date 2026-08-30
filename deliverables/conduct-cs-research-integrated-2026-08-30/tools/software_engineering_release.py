#!/usr/bin/env python3
"""Run the token-efficiency and software-engineering release gate."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import release

release.ZIP_NAME = "conduct-cs-research-software-engineered-2026-08-30.zip"
release.REQUIRED_REPORTS.update(
    {
        "software-engineering-review.md",
        "token-efficiency-and-skill-creator-compliance.md",
        "software-engineering-adversarial-overengineering-review.md",
    }
)

TEST_SOURCE = release.ROOT / "tests" / "self_test.py"
OPENAI_SKILL_CREATOR_COMMIT = "49f948faa9258a0c61caceaf225e179651397431"
OPENAI_SKILL_CREATOR_SKILL_BLOB = "72bc0b97e7a6476254a9d5c424c9971748402ec3"
PUBLIC_SCRIPTS = (
    "audit_latex.py",
    "audit_project.py",
    "audit_prose.py",
    "init_project.py",
    "score_journals.py",
)
MODE_REFERENCE = {
    "systematic-search": "systematic-search.md",
    "peer-review": "peer-review.md",
    "scientific-prose": "scientific-prose.md",
}


def run_external_self_test(skill: Path, *, seed: str) -> dict[str, Any]:
    runtime_test = skill / "scripts" / "self_test.py"
    if runtime_test.exists() or runtime_test.is_symlink():
        return {
            "returncode": 1,
            "summary": {},
            "stdout": "",
            "stderr": "development-only self_test.py is present in the runtime skill",
            "bytecode": [],
            "seed": seed,
            "passed": False,
        }
    try:
        payload = release.stable_read_bytes(TEST_SOURCE, max_bytes=2_000_000)
    except release.ReleaseError as exc:
        return {
            "returncode": 1,
            "summary": {},
            "stdout": "",
            "stderr": str(exc),
            "bytecode": [],
            "seed": seed,
            "passed": False,
        }

    cleanup_error = ""
    process: subprocess.CompletedProcess[str] | None = None
    bytecode: list[str] = []
    try:
        with runtime_test.open("xb") as handle:
            handle.write(payload)
        runtime_test.chmod(0o755)
        environment = os.environ.copy()
        environment.update({"PYTHONDONTWRITEBYTECODE": "1", "PYTHONHASHSEED": seed})
        process = subprocess.run(
            [sys.executable, "-B", "scripts/self_test.py"],
            cwd=skill,
            text=True,
            capture_output=True,
            timeout=240,
            env=environment,
        )
        bytecode = [
            str(path.relative_to(skill))
            for path in skill.rglob("*")
            if path.is_file() and release.is_bytecode(path.relative_to(skill))
        ]
    finally:
        try:
            runtime_test.unlink(missing_ok=True)
        except OSError as exc:
            cleanup_error = str(exc)

    if process is None:
        return {
            "returncode": 1,
            "summary": {},
            "stdout": "",
            "stderr": cleanup_error or "test process did not start",
            "bytecode": bytecode,
            "seed": seed,
            "passed": False,
        }
    stdout_lines = [line for line in process.stdout.splitlines() if line.strip()]
    summary: dict[str, Any] = {}
    if stdout_lines:
        try:
            summary = json.loads(stdout_lines[-1])
        except json.JSONDecodeError:
            summary = {}
    return {
        "returncode": process.returncode,
        "summary": summary,
        "stdout": process.stdout,
        "stderr": process.stderr + (f"\ncleanup: {cleanup_error}" if cleanup_error else ""),
        "bytecode": bytecode,
        "seed": seed,
        "passed": process.returncode == 0 and bool(summary.get("successful")) and not bytecode and not cleanup_error,
    }


release.run_self_test = run_external_self_test

# Load the prior final-audit extension after patching the test runner and release name.
import final_release  # noqa: E402,F401

ORIGINAL_VALIDATE_SOURCE = release.validate_source
ORIGINAL_VALIDATE_SUPPORTING = release.validate_supporting_artifacts


def word_count(text: str) -> int:
    return len(re.findall(r"\b[\w-]+\b", text))


def body_text(skill_text: str) -> str:
    match = re.match(r"^---\n.*?\n---\n", skill_text, re.DOTALL)
    return skill_text[match.end():] if match else skill_text


def normalized_paragraphs(text: str) -> set[str]:
    result: set[str] = set()
    for raw in re.split(r"\n\s*\n", text):
        paragraph = re.sub(r"\s+", " ", raw.strip().lower())
        if word_count(paragraph) >= 35 and not paragraph.startswith("|"):
            result.add(paragraph)
    return result


def snapshot(skill: Path) -> dict[str, str]:
    return {
        path.relative_to(skill).as_posix(): release.sha256_file(path)
        for path in release.regular_files(skill)
    }


def validate_cli_contract(skill: Path) -> list[str]:
    errors: list[str] = []
    before = snapshot(skill)
    environment = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONHASHSEED": "424242"}
    for name in PUBLIC_SCRIPTS:
        process = subprocess.run(
            [sys.executable, "-B", str(skill / "scripts" / name), "--help"],
            cwd=skill,
            text=True,
            capture_output=True,
            timeout=30,
            env=environment,
        )
        if process.returncode != 0:
            errors.append(f"{name} --help failed: {process.stderr[-1000:]}")
        if "usage:" not in process.stdout.lower():
            errors.append(f"{name} --help did not expose a CLI usage contract")
    after = snapshot(skill)
    if before != after:
        errors.append("CLI help execution changed the installable skill tree")
    return errors


def validate_source() -> tuple[list[str], list[str], dict[str, Any]]:
    errors, warnings, metrics = ORIGINAL_VALIDATE_SOURCE()
    skill = release.SKILL
    skill_text = release.stable_read_text(skill / "SKILL.md")
    body = body_text(skill_text)
    frontmatter = release.parse_frontmatter(skill_text)
    description = frontmatter.get("description", "")

    metrics.update(
        {
            "skill_creator_benchmark_commit": OPENAI_SKILL_CREATOR_COMMIT,
            "skill_creator_skill_blob": OPENAI_SKILL_CREATOR_SKILL_BLOB,
            "runtime_test_files": int((skill / "scripts" / "self_test.py").exists()),
            "description_words": word_count(description),
        }
    )
    if len(skill_text.splitlines()) > 120:
        errors.append(f"token-efficient SKILL.md line budget exceeded: {len(skill_text.splitlines())}>120")
    if word_count(skill_text) > 950:
        errors.append(f"token-efficient SKILL.md word budget exceeded: {word_count(skill_text)}>950")
    if word_count(description) > 80:
        errors.append(f"trigger description is too verbose: {word_count(description)}>80 words")
    if (skill / "scripts" / "self_test.py").exists():
        errors.append("development-only self_test.py must not ship in the runtime skill")
    runtime_scripts = sorted(path.name for path in (skill / "scripts").glob("*.py"))
    metrics["runtime_scripts"] = runtime_scripts
    if len(runtime_scripts) != 6:
        errors.append(f"runtime script count must remain 6 after test separation: {len(runtime_scripts)}")
    if metrics.get("source_files", 0) > 17:
        errors.append(f"installable source-file budget exceeded: {metrics.get('source_files')}>17")

    required_phrases = (
        "Do not preload every reference",
        "full-research-lifecycle",
        "systematic-search",
        "peer-review",
        "scientific-prose",
        "bounded stage task",
    )
    for phrase in required_phrases:
        if phrase not in skill_text:
            errors.append(f"routing contract lacks required phrase: {phrase}")

    reference_words: dict[str, int] = {}
    skill_paragraphs = normalized_paragraphs(body)
    for path in sorted((skill / "references").glob("*.md")):
        text = release.stable_read_text(path)
        reference_words[path.name] = word_count(text)
        duplicate = skill_paragraphs & normalized_paragraphs(text)
        if duplicate:
            errors.append(f"SKILL.md duplicates long paragraph content from {path.name}")
    metrics["reference_words"] = reference_words
    metrics["total_reference_words"] = sum(reference_words.values())
    if metrics["total_reference_words"] > 13_000:
        errors.append(f"reference corpus exceeds progressive-disclosure budget: {metrics['total_reference_words']}>13000 words")

    skill_words = word_count(skill_text)
    bounded_context: dict[str, int] = {}
    for mode, name in MODE_REFERENCE.items():
        combined = skill_words + reference_words.get(name, 0)
        bounded_context[mode] = combined
        if combined > 2_600:
            errors.append(f"{mode} initial context exceeds 2600-word budget: {combined}")
    other_reference_words = [count for name, count in reference_words.items() if name != "workflow.md"]
    full_stage = skill_words + reference_words.get("workflow.md", 0) + max(other_reference_words, default=0)
    metrics["bounded_initial_context_words"] = bounded_context
    metrics["full_stage_context_words"] = full_stage
    if full_stage > 4_000:
        errors.append(f"full-lifecycle active-stage context exceeds 4000-word budget: {full_stage}")

    yaml_text = release.stable_read_text(skill / "agents" / "openai.yaml")
    interface_keys = set(re.findall(r"^\s{2}([a-z_]+):", yaml_text, re.MULTILINE))
    if interface_keys != {"display_name", "short_description", "default_prompt"}:
        errors.append(f"agents/openai.yaml interface keys are not minimal: {sorted(interface_keys)}")
    prompt_match = re.search(r'^\s*default_prompt:\s*"([^"]+)"\s*$', yaml_text, re.MULTILINE)
    if prompt_match and len(prompt_match.group(1)) > 180:
        errors.append(f"default_prompt exceeds 180 characters: {len(prompt_match.group(1))}")

    errors.extend(validate_cli_contract(skill))
    return errors, warnings, metrics


def validate_supporting_artifacts() -> tuple[list[str], list[str], dict[str, Any]]:
    errors, warnings, metrics = ORIGINAL_VALIDATE_SUPPORTING()
    seen: set[str] = set()
    for shard in sorted(release.EVALS.glob("*.jsonl")):
        for line in release.stable_read_text(shard).splitlines():
            if line.strip():
                item = release.load_strict_json(line)
                if isinstance(item, dict) and isinstance(item.get("id"), str):
                    seen.add(item["id"])
    required = {
        "se-bounded-search-no-full-preload",
        "se-bounded-prose-one-reference",
        "se-peer-review-one-reference",
        "se-full-lifecycle-workflow-first",
        "se-generic-code-negative-control",
        "se-resist-load-every-reference",
        "se-no-runtime-self-test",
        "se-standalone-journal-task",
    }
    missing = sorted(required - seen)
    if missing:
        errors.append(f"software-engineering evaluation cases are missing: {missing}")
    metrics["software_engineering_eval_cases"] = len(seen & required)
    return errors, warnings, metrics


release.validate_source = validate_source
release.validate_supporting_artifacts = validate_supporting_artifacts

if __name__ == "__main__":
    raise SystemExit(release.main())
