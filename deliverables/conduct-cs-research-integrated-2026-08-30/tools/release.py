#!/usr/bin/env python3
"""Validate and package the integrated conduct-cs-research skill deterministically."""

from __future__ import annotations

import ast
import hashlib
import json
import os
import py_compile
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import unicodedata
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "conduct-cs-research"
REPORTS = ROOT / "reports"
EVALS = ROOT / "evals"
RELEASE = ROOT / "release"
ZIP_NAME = "conduct-cs-research-integrated-2026-08-30.zip"
ALLOWED_TOP = {"SKILL.md", "agents", "references", "scripts"}
MODES = {"full-research-lifecycle", "systematic-search", "peer-review", "scientific-prose"}
WORKSPACE_BUDGETS = {
    "full-research-lifecycle": 25,
    "systematic-search": 12,
    "peer-review": 7,
    "scientific-prose": 6,
}
REQUIRED_REPORTS = {
    "integration-and-supersession.md",
    "extended-adversarial-review.md",
    "extended-adversarial-review-round-2.md",
    "overengineering-review.md",
    "overengineering-review-round-2.md",
}
WINDOWS_DEVICES = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}
LOCAL_MODULES = {"_common", "audit_latex", "audit_project", "audit_prose", "init_project", "score_journals"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_bytecode(path: Path) -> bool:
    return "__pycache__" in path.parts or path.suffix in {".pyc", ".pyo"}


def regular_files(root: Path) -> list[Path]:
    result: list[Path] = []
    for path in sorted(root.rglob("*")):
        info = path.lstat()
        if stat.S_ISLNK(info.st_mode):
            raise RuntimeError(f"linked path in release source: {path.relative_to(root)}")
        if path.is_file():
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise RuntimeError(f"non-regular or hard-linked file: {path.relative_to(root)}")
            if is_bytecode(path.relative_to(root)):
                raise RuntimeError(f"compiled Python artifact is forbidden: {path.relative_to(root)}")
            result.append(path)
    return result


def parse_frontmatter(text: str) -> dict[str, str]:
    match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not match:
        raise RuntimeError("SKILL.md has invalid YAML frontmatter delimiters")
    values: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if not line.strip():
            continue
        key, separator, value = line.partition(":")
        if not separator:
            raise RuntimeError(f"unsupported frontmatter line: {line}")
        key = key.strip()
        if key in values:
            raise RuntimeError(f"duplicate frontmatter key: {key}")
        values[key] = value.strip()
    return values


def run_self_test(skill: Path) -> dict[str, Any]:
    environment = os.environ.copy()
    environment.update({"PYTHONDONTWRITEBYTECODE": "1", "PYTHONHASHSEED": "0"})
    process = subprocess.run(
        [sys.executable, "-B", "scripts/self_test.py"],
        cwd=skill,
        text=True,
        capture_output=True,
        timeout=180,
        env=environment,
    )
    stdout_lines = [line for line in process.stdout.splitlines() if line.strip()]
    summary: dict[str, Any] = {}
    if stdout_lines:
        try:
            summary = json.loads(stdout_lines[-1])
        except json.JSONDecodeError:
            summary = {}
    bytecode = [str(path.relative_to(skill)) for path in skill.rglob("*") if path.is_file() and is_bytecode(path.relative_to(skill))]
    return {
        "returncode": process.returncode,
        "summary": summary,
        "stdout": process.stdout,
        "stderr": process.stderr,
        "bytecode": bytecode,
        "passed": process.returncode == 0 and bool(summary.get("successful")) and not bytecode,
    }


def compile_scripts(skill: Path) -> list[str]:
    errors: list[str] = []
    with tempfile.TemporaryDirectory() as temporary:
        destination = Path(temporary)
        for index, path in enumerate(sorted((skill / "scripts").glob("*.py"))):
            try:
                py_compile.compile(str(path), cfile=str(destination / f"{index}.pyc"), doraise=True)
            except py_compile.PyCompileError as exc:
                errors.append(str(exc))
    return errors


def inspect_imports(skill: Path) -> list[str]:
    errors: list[str] = []
    allowed = set(sys.stdlib_module_names) | LOCAL_MODULES
    for path in sorted((skill / "scripts").glob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as exc:
            errors.append(f"cannot parse imports in {path.name}: {exc}")
            continue
        for node in ast.walk(tree):
            module: str | None = None
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module = alias.name.split(".", 1)[0]
                    if module not in allowed:
                        errors.append(f"third-party import {module} in {path.name}")
            elif isinstance(node, ast.ImportFrom) and node.module:
                module = node.module.split(".", 1)[0]
                if module not in allowed:
                    errors.append(f"third-party import {module} in {path.name}")
    return errors


def strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_strict_json(text: str) -> Any:
    return json.loads(
        text,
        object_pairs_hook=strict_object,
        parse_constant=lambda value: (_ for _ in ()).throw(ValueError(f"non-finite JSON value: {value}")),
    )


def validate_supporting_artifacts() -> tuple[list[str], list[str], dict[str, Any]]:
    errors: list[str] = []
    warnings: list[str] = []
    metrics: dict[str, Any] = {}
    for name in sorted(REQUIRED_REPORTS):
        path = REPORTS / name
        if not path.is_file() or not path.read_text(encoding="utf-8").strip():
            errors.append(f"missing or empty required report: {name}")
    metrics["reports"] = len([path for path in REPORTS.glob("*.md") if path.is_file()])

    protocol = EVALS / "evaluation.md"
    schema = EVALS / "rubric.schema.json"
    dataset = EVALS / "evals.jsonl"
    for path in (protocol, schema, dataset):
        if not path.is_file() or not path.read_text(encoding="utf-8").strip():
            errors.append(f"missing or empty evaluation artifact: {path.name}")
    try:
        parsed_schema = load_strict_json(schema.read_text(encoding="utf-8"))
        if not isinstance(parsed_schema, dict) or parsed_schema.get("type") != "object":
            errors.append("evaluation rubric schema must describe a JSON object")
    except Exception as exc:
        errors.append(f"invalid rubric.schema.json: {exc}")

    cases: list[dict[str, Any]] = []
    seen: set[str] = set()
    if dataset.is_file():
        for line_number, line in enumerate(dataset.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            try:
                item = load_strict_json(line)
            except Exception as exc:
                errors.append(f"evals.jsonl:{line_number}: {exc}")
                continue
            if not isinstance(item, dict):
                errors.append(f"evals.jsonl:{line_number}: case must be an object")
                continue
            case_id = item.get("id")
            if not isinstance(case_id, str) or not re.fullmatch(r"[a-z0-9-]+", case_id):
                errors.append(f"evals.jsonl:{line_number}: invalid id")
            elif case_id in seen:
                errors.append(f"evals.jsonl:{line_number}: duplicate id {case_id}")
            else:
                seen.add(case_id)
            if item.get("mode") not in MODES | {None}:
                errors.append(f"evals.jsonl:{line_number}: invalid mode")
            if item.get("severity") not in {"critical", "major", "minor"}:
                errors.append(f"evals.jsonl:{line_number}: invalid severity")
            if not isinstance(item.get("prompt"), str) or not item["prompt"].strip():
                errors.append(f"evals.jsonl:{line_number}: prompt is empty")
            for field in ("expected", "forbidden"):
                value = item.get(field)
                if not isinstance(value, list) or not value or any(not isinstance(entry, str) or not entry.strip() for entry in value):
                    errors.append(f"evals.jsonl:{line_number}: {field} must be a nonempty string list")
            cases.append(item)
    metrics["eval_cases"] = len(cases)
    metrics["critical_eval_cases"] = sum(1 for item in cases if item.get("severity") == "critical")
    if len(cases) < 50:
        errors.append(f"evaluation dataset is too small for the integrated surface: {len(cases)} cases")
    if metrics["critical_eval_cases"] < 20:
        warnings.append("evaluation dataset has fewer than 20 critical cases")
    return errors, warnings, metrics


def validate_source() -> tuple[list[str], list[str], dict[str, Any]]:
    errors: list[str] = []
    warnings: list[str] = []
    metrics: dict[str, Any] = {}
    if not SKILL.is_dir():
        return [f"missing skill directory: {SKILL}"], warnings, metrics

    try:
        initial_files = regular_files(SKILL)
    except RuntimeError as exc:
        return [str(exc)], warnings, metrics
    initial_names = [path.relative_to(SKILL).as_posix() for path in initial_files]
    top = {path.relative_to(SKILL).parts[0] for path in initial_files}
    unexpected = sorted(top - ALLOWED_TOP)
    if unexpected:
        errors.append(f"unexpected skill top-level entries: {unexpected}")
    for required in ("SKILL.md", "agents/openai.yaml"):
        if not (SKILL / required).is_file():
            errors.append(f"missing required skill file: {required}")

    skill_text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    lines = skill_text.splitlines()
    metrics["skill_lines"] = len(lines)
    metrics["skill_words"] = len(re.findall(r"\b\w+\b", skill_text))
    if len(lines) > 500:
        errors.append(f"SKILL.md exceeds 500 lines: {len(lines)}")
    try:
        frontmatter = parse_frontmatter(skill_text)
    except RuntimeError as exc:
        errors.append(str(exc))
        frontmatter = {}
    if set(frontmatter) != {"name", "description"}:
        errors.append(f"frontmatter keys must be exactly name and description: {sorted(frontmatter)}")
    if frontmatter.get("name") != "conduct-cs-research":
        errors.append("frontmatter name must be conduct-cs-research")
    description = frontmatter.get("description", "")
    if not description or len(description) > 1024 or "<" in description or ">" in description:
        errors.append("frontmatter description is missing or invalid")
    for phrase in ("systematic", "peer review", "scientific-prose", "q1"):
        if phrase not in description.lower():
            errors.append(f"frontmatter description does not cover integrated trigger: {phrase}")

    references = sorted((SKILL / "references").glob("*.md"))
    scripts = sorted((SKILL / "scripts").glob("*.py"))
    metrics["reference_files"] = len(references)
    metrics["script_files"] = len(scripts)
    metrics["reference_lines"] = sum(len(path.read_text(encoding="utf-8").splitlines()) for path in references)
    metrics["script_lines"] = sum(len(path.read_text(encoding="utf-8").splitlines()) for path in scripts)
    if len(references) > 10:
        errors.append(f"too many reference files for progressive disclosure: {len(references)}")
    if len(scripts) > 7:
        errors.append(f"too many scripts after overengineering review: {len(scripts)}")
    for path in references:
        if f"references/{path.name}" not in skill_text:
            errors.append(f"reference is not directly linked from SKILL.md: {path.name}")
        if len(path.read_text(encoding="utf-8").splitlines()) > 350:
            warnings.append(f"long reference file: {path.name}")
    for path in scripts:
        if path.name.startswith("_") or path.name == "self_test.py":
            continue
        if f"scripts/{path.name}" not in skill_text:
            errors.append(f"script is not documented in SKILL.md: {path.name}")

    yaml_text = (SKILL / "agents/openai.yaml").read_text(encoding="utf-8") if (SKILL / "agents/openai.yaml").is_file() else ""
    short_match = re.search(r'^\s*short_description:\s*"([^"]+)"\s*$', yaml_text, re.MULTILINE)
    prompt_match = re.search(r'^\s*default_prompt:\s*"([^"]+)"\s*$', yaml_text, re.MULTILINE)
    if not short_match or not (25 <= len(short_match.group(1)) <= 64):
        errors.append("agents/openai.yaml has an invalid short_description")
    if not prompt_match or "$conduct-cs-research" not in prompt_match.group(1):
        errors.append("agents/openai.yaml default_prompt must name $conduct-cs-research")

    errors.extend(inspect_imports(SKILL))
    errors.extend(f"compile: {item}" for item in compile_scripts(SKILL))
    tests = run_self_test(SKILL)
    metrics["source_tests"] = tests["summary"]
    if not tests["passed"]:
        errors.append("source-tree self tests failed or emitted bytecode")
        if tests["bytecode"]:
            errors.append(f"source tests emitted bytecode: {tests['bytecode']}")
        if tests["stderr"]:
            warnings.append(tests["stderr"][-4000:])

    try:
        final_files = regular_files(SKILL)
    except RuntimeError as exc:
        errors.append(str(exc))
        final_files = []
    final_names = [path.relative_to(SKILL).as_posix() for path in final_files]
    if initial_names != final_names:
        errors.append("source-tree file set changed during validation")

    workspace_counts: dict[str, int] = {}
    for mode, budget in WORKSPACE_BUDGETS.items():
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            process = subprocess.run(
                [sys.executable, "-B", str(SKILL / "scripts/init_project.py"), str(project), "--name", "Release Audit", "--mode", mode],
                text=True,
                capture_output=True,
                timeout=60,
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            )
            if process.returncode != 0:
                errors.append(f"{mode} workspace initialization failed: {process.stderr[-1000:]}")
                continue
            count = sum(1 for path in project.rglob("*") if path.is_file())
            workspace_counts[mode] = count
            if count > budget:
                errors.append(f"{mode} workspace exceeds overengineering budget: {count}>{budget}")
            audit = subprocess.run(
                [sys.executable, "-B", str(SKILL / "scripts/audit_project.py"), str(project), "--json"],
                text=True,
                capture_output=True,
                timeout=60,
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            )
            if audit.returncode != 0:
                errors.append(f"fresh {mode} workspace audit failed: {audit.stdout[-1500:]} {audit.stderr[-1000:]}")
    metrics["workspace_files"] = workspace_counts
    metrics["source_files"] = len(final_files)
    metrics["source_bytes"] = sum(path.stat().st_size for path in final_files)
    return errors, warnings, metrics


def portable_member_name(name: str, seen: set[str]) -> list[str]:
    errors: list[str] = []
    if not name or "\x00" in name or "\\" in name:
        errors.append(f"invalid archive name: {name!r}")
        return errors
    if len(name.encode("utf-8")) > 240:
        errors.append(f"archive path is too long for portable installation: {name}")
    if name != unicodedata.normalize("NFC", name):
        errors.append(f"archive name is not NFC-normalized: {name}")
    pure = PurePosixPath(name)
    if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
        errors.append(f"unsafe archive path: {name}")
    if not pure.parts or pure.parts[0] != "conduct-cs-research":
        errors.append(f"archive member lacks required top-level folder: {name}")
    folded = unicodedata.normalize("NFC", name).casefold()
    if folded in seen:
        errors.append(f"case or Unicode-colliding archive member: {name}")
    seen.add(folded)
    for part in pure.parts:
        if part.endswith((".", " ")) or ":" in part:
            errors.append(f"nonportable archive component: {part!r}")
        stem = part.split(".", 1)[0].upper()
        if stem in WINDOWS_DEVICES:
            errors.append(f"reserved Windows archive component: {part!r}")
    return errors


def make_archive(zip_path: Path) -> None:
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9, strict_timestamps=True) as archive:
        for path in regular_files(SKILL):
            relative = path.relative_to(SKILL).as_posix()
            info = zipfile.ZipInfo(f"conduct-cs-research/{relative}", date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            permission = 0o755 if path.parent.name == "scripts" and path.suffix == ".py" else 0o644
            info.external_attr = (stat.S_IFREG | permission) << 16
            archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def validate_archive(zip_path: Path, expected_members: int) -> tuple[list[str], dict[str, Any], dict[str, Any]]:
    errors: list[str] = []
    metrics: dict[str, Any] = {}
    extracted_test: dict[str, Any] = {}
    seen: set[str] = set()
    with zipfile.ZipFile(zip_path) as archive:
        infos = archive.infolist()
        metrics["archive_members"] = len(infos)
        metrics["archive_uncompressed_bytes"] = sum(item.file_size for item in infos)
        metrics["archive_compressed_bytes"] = sum(item.compress_size for item in infos)
        if len(infos) != expected_members:
            errors.append(f"archive member count differs from validated source: {len(infos)} != {expected_members}")
        if len(infos) > 200:
            errors.append("archive has too many members")
        if metrics["archive_uncompressed_bytes"] > 10_000_000:
            errors.append("archive is unexpectedly large")
        for info in infos:
            errors.extend(portable_member_name(info.filename, seen))
            mode = (info.external_attr >> 16) & 0o170000
            if mode not in {stat.S_IFREG, stat.S_IFDIR}:
                errors.append(f"archive contains a link or special file: {info.filename}")
            if info.flag_bits & 0x1:
                errors.append(f"archive contains encrypted member: {info.filename}")
            if info.compress_size and info.file_size / info.compress_size > 200:
                errors.append(f"archive member has suspicious compression ratio: {info.filename}")
            if info.date_time != (1980, 1, 1, 0, 0, 0):
                errors.append(f"archive timestamp is not deterministic: {info.filename}")
        corrupt = archive.testzip()
        if corrupt:
            errors.append(f"archive CRC check failed for {corrupt}")

        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary).resolve()
            for info in infos:
                target = destination / PurePosixPath(info.filename)
                try:
                    target.resolve().relative_to(destination)
                except (OSError, RuntimeError, ValueError):
                    errors.append(f"extraction path escapes destination: {info.filename}")
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.read(info))
            extracted = destination / "conduct-cs-research"
            try:
                source_map = {path.relative_to(SKILL).as_posix(): path.read_bytes() for path in regular_files(SKILL)}
                extracted_map = {path.relative_to(extracted).as_posix(): path.read_bytes() for path in regular_files(extracted)}
            except RuntimeError as exc:
                errors.append(str(exc))
                source_map = {}
                extracted_map = {}
            if source_map.keys() != extracted_map.keys():
                errors.append("clean extraction file set differs from source")
            else:
                for name in source_map:
                    if source_map[name] != extracted_map[name]:
                        errors.append(f"clean extraction byte mismatch: {name}")
            errors.extend(f"clean-extraction compile: {item}" for item in compile_scripts(extracted))
            extracted_test = run_self_test(extracted)
            if not extracted_test["passed"]:
                errors.append("clean-extraction self tests failed or emitted bytecode")
            try:
                post_test_files = regular_files(extracted)
            except RuntimeError as exc:
                errors.append(str(exc))
                post_test_files = []
            if set(path.relative_to(extracted).as_posix() for path in post_test_files) != set(extracted_map):
                errors.append("clean-extraction file set changed during tests")
    return errors, metrics, extracted_test


def copy_supporting_artifacts() -> None:
    for source in sorted(REPORTS.glob("*")) + sorted(EVALS.glob("*")):
        if source.is_file():
            shutil.copy2(source, RELEASE / source.name)


def main() -> int:
    started = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    RELEASE.mkdir(parents=True, exist_ok=True)
    for child in RELEASE.iterdir():
        if child.is_file() or child.is_symlink():
            child.unlink()
        elif child.is_dir():
            shutil.rmtree(child)

    source_errors, source_warnings, metrics = validate_source()
    support_errors, support_warnings, support_metrics = validate_supporting_artifacts()
    metrics.update(support_metrics)
    errors = source_errors + support_errors
    warnings = source_warnings + support_warnings
    zip_path = RELEASE / ZIP_NAME
    archive_metrics: dict[str, Any] = {}
    extracted_test: dict[str, Any] = {}

    if not errors:
        make_archive(zip_path)
        with tempfile.TemporaryDirectory() as temporary:
            second = Path(temporary) / ZIP_NAME
            make_archive(second)
            metrics["deterministic_rebuild_sha256"] = sha256_file(second)
            if zip_path.read_bytes() != second.read_bytes():
                errors.append("two independent archive builds are not byte-identical")
        archive_errors, archive_metrics, extracted_test = validate_archive(zip_path, int(metrics["source_files"]))
        errors.extend(archive_errors)
    metrics.update(archive_metrics)
    metrics["clean_extraction_tests"] = extracted_test.get("summary", {})

    if errors and zip_path.exists():
        zip_path.unlink()
    if zip_path.exists():
        metrics["zip_bytes"] = zip_path.stat().st_size
        metrics["zip_sha256"] = sha256_file(zip_path)

    validation = {
        "schema_version": 2,
        "started_at": started,
        "finished_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "passed": not errors,
        "errors": errors,
        "warnings": warnings,
        "metrics": metrics,
        "assurance_boundary": {
            "source_archives_byte_inspected": False,
            "reason": "The conversation attachment runtime was unavailable; integration was performed at the capability and trigger-contract level using the supplied skill identities, prior context, and public analogues.",
            "scientific_validity_proven": False,
            "semantic_equivalence_proven": False,
            "search_completeness_proven": False,
            "journal_acceptance_or_q1_guaranteed": False,
        },
    }
    (RELEASE / "validation.json").write_text(json.dumps(validation, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    text_lines = [
        f"Release validation: {'PASS' if validation['passed'] else 'FAIL'}",
        f"Errors: {len(errors)}",
        f"Warnings: {len(warnings)}",
        f"Source tests: {metrics.get('source_tests', {})}",
        f"Clean-extraction tests: {metrics.get('clean_extraction_tests', {})}",
        f"Skill lines: {metrics.get('skill_lines')}",
        f"Reference files: {metrics.get('reference_files')}",
        f"Script files: {metrics.get('script_files')}",
        f"Workspace files by mode: {metrics.get('workspace_files')}",
        f"Evaluation cases: {metrics.get('eval_cases')}",
        f"Archive members: {metrics.get('archive_members')}",
        f"ZIP SHA-256: {metrics.get('zip_sha256', 'not built')}",
        f"Deterministic rebuild SHA-256: {metrics.get('deterministic_rebuild_sha256', 'not built')}",
        "Source archive byte-level comparison: NOT PERFORMED (attachment runtime unavailable)",
    ]
    if errors:
        text_lines.append("\nErrors:")
        text_lines.extend(f"- {item}" for item in errors)
    if warnings:
        text_lines.append("\nWarnings:")
        text_lines.extend(f"- {item}" for item in warnings if item)
    (RELEASE / "validation.txt").write_text("\n".join(text_lines) + "\n", encoding="utf-8")

    if zip_path.exists() and not errors:
        digest = sha256_file(zip_path)
        (RELEASE / f"{ZIP_NAME}.sha256").write_text(f"{digest}  {ZIP_NAME}\n", encoding="utf-8")
    manifest = {
        "release": ZIP_NAME,
        "passed": validation["passed"],
        "zip_sha256": metrics.get("zip_sha256"),
        "skill_source_files": metrics.get("source_files"),
        "source_tests": metrics.get("source_tests"),
        "clean_extraction_tests": metrics.get("clean_extraction_tests"),
        "workspace_files": metrics.get("workspace_files"),
        "eval_cases": metrics.get("eval_cases"),
        "reports": sorted(path.name for path in REPORTS.glob("*") if path.is_file()),
        "evals": sorted(path.name for path in EVALS.glob("*") if path.is_file()),
    }
    (RELEASE / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    copy_supporting_artifacts()
    (RELEASE / "release-ready.txt").write_text("READY\n" if validation["passed"] else "NOT READY\n", encoding="utf-8")
    print(json.dumps(validation, indent=2, sort_keys=True))
    return 0 if validation["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
