#!/usr/bin/env python3
"""Validate and package the integrated conduct-cs-research skill deterministically."""

from __future__ import annotations

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

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "conduct-cs-research"
REPORTS = ROOT / "reports"
EVALS = ROOT / "evals"
RELEASE = ROOT / "release"
ZIP_NAME = "conduct-cs-research-integrated-2026-08-30.zip"
ALLOWED_TOP = {"SKILL.md", "agents", "references", "scripts"}
WINDOWS_DEVICES = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def regular_files(root: Path) -> list[Path]:
    result: list[Path] = []
    for path in sorted(root.rglob("*")):
        info = path.lstat()
        if stat.S_ISLNK(info.st_mode):
            raise RuntimeError(f"linked path in release source: {path.relative_to(root)}")
        if path.is_file():
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise RuntimeError(f"non-regular or hard-linked file: {path.relative_to(root)}")
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
    process = subprocess.run(
        [sys.executable, "scripts/self_test.py"],
        cwd=skill,
        text=True,
        capture_output=True,
        timeout=180,
    )
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
        "stderr": process.stderr,
        "passed": process.returncode == 0 and bool(summary.get("successful")),
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


def validate_source() -> tuple[list[str], list[str], dict[str, Any]]:
    errors: list[str] = []
    warnings: list[str] = []
    metrics: dict[str, Any] = {}
    if not SKILL.is_dir():
        return [f"missing skill directory: {SKILL}"], warnings, metrics

    files = regular_files(SKILL)
    top = {path.relative_to(SKILL).parts[0] for path in files}
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

    compile_errors = compile_scripts(SKILL)
    errors.extend(f"compile: {item}" for item in compile_errors)
    tests = run_self_test(SKILL)
    metrics["source_tests"] = tests["summary"]
    if not tests["passed"]:
        errors.append("source-tree self tests failed")
        warnings.append(tests["stderr"][-4000:])

    with tempfile.TemporaryDirectory() as temporary:
        project = Path(temporary) / "project"
        process = subprocess.run(
            [sys.executable, str(SKILL / "scripts/init_project.py"), str(project), "--name", "Release Audit", "--mode", "full-research-lifecycle"],
            text=True,
            capture_output=True,
            timeout=60,
        )
        if process.returncode != 0:
            errors.append(f"full workspace initialization failed: {process.stderr[-1000:]}")
        else:
            count = sum(1 for path in project.rglob("*") if path.is_file())
            metrics["full_workspace_files"] = count
            if count > 26:
                errors.append(f"full workspace exceeds overengineering threshold: {count} files")
            audit = subprocess.run(
                [sys.executable, str(SKILL / "scripts/audit_project.py"), str(project), "--json"],
                text=True,
                capture_output=True,
                timeout=60,
            )
            if audit.returncode != 0:
                errors.append(f"fresh workspace audit failed: {audit.stdout[-1500:]} {audit.stderr[-1000:]}")

    for path in files:
        relative = path.relative_to(SKILL).as_posix()
        if "__pycache__" in relative or path.suffix in {".pyc", ".pyo"}:
            errors.append(f"compiled artifact leaked into source: {relative}")
        if path.name.lower() in {"readme.md", "changelog.md", "installation_guide.md", "quick_reference.md"}:
            errors.append(f"extraneous skill documentation: {relative}")
    metrics["source_files"] = len(files)
    metrics["source_bytes"] = sum(path.stat().st_size for path in files)
    return errors, warnings, metrics


def portable_member_name(name: str, seen: set[str]) -> list[str]:
    errors: list[str] = []
    if not name or "\x00" in name or "\\" in name:
        errors.append(f"invalid archive name: {name!r}")
        return errors
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
            info.external_attr = permission << 16
            archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def validate_archive(zip_path: Path) -> tuple[list[str], dict[str, Any], dict[str, Any]]:
    errors: list[str] = []
    metrics: dict[str, Any] = {}
    extracted_test: dict[str, Any] = {}
    seen: set[str] = set()
    with zipfile.ZipFile(zip_path) as archive:
        infos = archive.infolist()
        metrics["archive_members"] = len(infos)
        metrics["archive_uncompressed_bytes"] = sum(item.file_size for item in infos)
        metrics["archive_compressed_bytes"] = sum(item.compress_size for item in infos)
        if len(infos) > 200:
            errors.append("archive has too many members")
        if metrics["archive_uncompressed_bytes"] > 10_000_000:
            errors.append("archive is unexpectedly large")
        for info in infos:
            errors.extend(portable_member_name(info.filename, seen))
            mode = (info.external_attr >> 16) & 0o170000
            if mode and mode not in {stat.S_IFREG, stat.S_IFDIR}:
                errors.append(f"archive contains a link or special file: {info.filename}")
            if info.flag_bits & 0x1:
                errors.append(f"archive contains encrypted member: {info.filename}")
            if info.compress_size and info.file_size / info.compress_size > 200:
                errors.append(f"archive member has suspicious compression ratio: {info.filename}")

        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary)
            for info in infos:
                target = destination / PurePosixPath(info.filename)
                if not str(target.resolve()).startswith(str(destination.resolve()) + os.sep):
                    errors.append(f"extraction path escapes destination: {info.filename}")
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.read(info))
            extracted = destination / "conduct-cs-research"
            source_map = {path.relative_to(SKILL).as_posix(): path.read_bytes() for path in regular_files(SKILL)}
            extracted_map = {path.relative_to(extracted).as_posix(): path.read_bytes() for path in regular_files(extracted)}
            if source_map.keys() != extracted_map.keys():
                errors.append("clean extraction file set differs from source")
            else:
                for name in source_map:
                    if source_map[name] != extracted_map[name]:
                        errors.append(f"clean extraction byte mismatch: {name}")
            compile_errors = compile_scripts(extracted)
            errors.extend(f"clean-extraction compile: {item}" for item in compile_errors)
            extracted_test = run_self_test(extracted)
            if not extracted_test["passed"]:
                errors.append("clean-extraction self tests failed")
    return errors, metrics, extracted_test


def copy_supporting_artifacts() -> None:
    for source in sorted(REPORTS.glob("*")) + sorted(EVALS.glob("*")):
        if source.is_file():
            shutil.copy2(source, RELEASE / source.name)


def main() -> int:
    started = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    source_errors, source_warnings, metrics = validate_source()
    RELEASE.mkdir(parents=True, exist_ok=True)
    for child in RELEASE.iterdir():
        if child.is_file() or child.is_symlink():
            child.unlink()
        elif child.is_dir():
            shutil.rmtree(child)

    zip_path = RELEASE / ZIP_NAME
    archive_errors: list[str] = []
    archive_metrics: dict[str, Any] = {}
    extracted_test: dict[str, Any] = {}
    if not source_errors:
        make_archive(zip_path)
        archive_errors, archive_metrics, extracted_test = validate_archive(zip_path)
    errors = source_errors + archive_errors
    warnings = source_warnings
    metrics.update(archive_metrics)
    if zip_path.exists():
        metrics["zip_bytes"] = zip_path.stat().st_size
        metrics["zip_sha256"] = sha256_file(zip_path)
    metrics["clean_extraction_tests"] = extracted_test.get("summary", {})

    validation = {
        "schema_version": 1,
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
        f"Full workspace files: {metrics.get('full_workspace_files')}",
        f"ZIP SHA-256: {metrics.get('zip_sha256', 'not built')}",
        "Source archive byte-level comparison: NOT PERFORMED (attachment runtime unavailable)",
    ]
    if errors:
        text_lines.append("\nErrors:")
        text_lines.extend(f"- {item}" for item in errors)
    if warnings:
        text_lines.append("\nWarnings:")
        text_lines.extend(f"- {item}" for item in warnings if item)
    (RELEASE / "validation.txt").write_text("\n".join(text_lines) + "\n", encoding="utf-8")

    if zip_path.exists():
        digest = sha256_file(zip_path)
        (RELEASE / f"{ZIP_NAME}.sha256").write_text(f"{digest}  {ZIP_NAME}\n", encoding="utf-8")
    manifest = {
        "release": ZIP_NAME,
        "passed": validation["passed"],
        "zip_sha256": metrics.get("zip_sha256"),
        "skill_source_files": metrics.get("source_files"),
        "source_tests": metrics.get("source_tests"),
        "clean_extraction_tests": metrics.get("clean_extraction_tests"),
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
