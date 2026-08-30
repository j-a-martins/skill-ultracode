#!/usr/bin/env python3
"""Validate and package the final-audited conduct-cs-research skill deterministically."""

from __future__ import annotations

import ast
import hashlib
import json
import os
import py_compile
import re
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
ZIP_NAME = "conduct-cs-research-final-audited-2026-08-30.zip"
ALLOWED_TOP = {"SKILL.md", "agents", "references", "scripts"}
MODES = {"full-research-lifecycle", "systematic-search", "peer-review", "scientific-prose"}
WORKSPACE_EXPECTED = {
    "full-research-lifecycle": 30,
    "systematic-search": 14,
    "peer-review": 8,
    "scientific-prose": 6,
}
WORKSPACE_BUDGETS = {
    "full-research-lifecycle": 32,
    "systematic-search": 15,
    "peer-review": 9,
    "scientific-prose": 7,
}
REQUIRED_REPORTS = {
    "integration-and-supersession.md",
    "extended-adversarial-review.md",
    "extended-adversarial-review-round-2.md",
    "extended-adversarial-review-round-3.md",
    "overengineering-review.md",
    "overengineering-review-round-2.md",
    "overengineering-review-round-3.md",
}
WINDOWS_DEVICES = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}
LOCAL_MODULES = {"_common", "audit_latex", "audit_project", "audit_prose", "init_project", "score_journals"}
FORBIDDEN_IMPORT_PREFIXES = {
    "ctypes", "ftplib", "http.client", "imaplib", "marshal", "pickle", "poplib", "shelve", "smtplib",
    "socket", "subprocess", "telnetlib", "urllib.request", "webbrowser",
}
FORBIDDEN_CALLS = {
    "eval", "exec", "compile", "__import__", "os.system", "os.popen", "subprocess.run", "subprocess.call",
    "subprocess.Popen", "subprocess.check_call", "subprocess.check_output",
}


class ReleaseError(RuntimeError):
    pass


def _same_snapshot(left: os.stat_result, right: os.stat_result) -> bool:
    return (
        left.st_dev, left.st_ino, left.st_size,
        getattr(left, "st_mtime_ns", int(left.st_mtime * 1_000_000_000)),
        getattr(left, "st_ctime_ns", int(left.st_ctime * 1_000_000_000)),
    ) == (
        right.st_dev, right.st_ino, right.st_size,
        getattr(right, "st_mtime_ns", int(right.st_mtime * 1_000_000_000)),
        getattr(right, "st_ctime_ns", int(right.st_ctime * 1_000_000_000)),
    )


def stable_read_bytes(path: Path, *, max_bytes: int = 100_000_000) -> bytes:
    try:
        before = path.lstat()
    except OSError as exc:
        raise ReleaseError(f"cannot inspect {path}: {exc}") from exc
    if not stat.S_ISREG(before.st_mode) or stat.S_ISLNK(before.st_mode) or before.st_nlink != 1:
        raise ReleaseError(f"not a single-link regular file: {path}")
    if before.st_size > max_bytes:
        raise ReleaseError(f"file exceeds {max_bytes} bytes: {path}")
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise ReleaseError(f"cannot open {path}: {exc}") from exc
    try:
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1 or (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
            raise ReleaseError(f"file identity changed while opening: {path}")
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(descriptor, min(1024 * 1024, max_bytes - total + 1))
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                raise ReleaseError(f"file grew beyond {max_bytes} bytes: {path}")
            chunks.append(chunk)
        after = os.fstat(descriptor)
        if not _same_snapshot(opened, after):
            raise ReleaseError(f"file changed during read: {path}")
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def stable_read_text(path: Path, *, max_bytes: int = 100_000_000) -> str:
    try:
        return stable_read_bytes(path, max_bytes=max_bytes).decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ReleaseError(f"file is not UTF-8: {path}") from exc


def sha256_file(path: Path) -> str:
    return hashlib.sha256(stable_read_bytes(path, max_bytes=1_000_000_000)).hexdigest()


def is_bytecode(path: Path) -> bool:
    return "__pycache__" in path.parts or path.suffix in {".pyc", ".pyo"}


def regular_files(root: Path) -> list[Path]:
    try:
        root_info = root.lstat()
    except OSError as exc:
        raise ReleaseError(f"cannot inspect release source root {root}: {exc}") from exc
    if not stat.S_ISDIR(root_info.st_mode) or stat.S_ISLNK(root_info.st_mode):
        raise ReleaseError(f"release source root is not a regular directory: {root}")
    result: list[Path] = []
    for path in sorted(root.rglob("*")):
        try:
            info = path.lstat()
        except OSError as exc:
            raise ReleaseError(f"cannot inspect {path}: {exc}") from exc
        relative = path.relative_to(root)
        if stat.S_ISLNK(info.st_mode):
            raise ReleaseError(f"linked path in release source: {relative}")
        if stat.S_ISDIR(info.st_mode):
            continue
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ReleaseError(f"special or hard-linked file in release source: {relative}")
        if is_bytecode(relative):
            raise ReleaseError(f"compiled Python artifact is forbidden: {relative}")
        result.append(path)
    return result


def _remove_regular_tree(path: Path, boundary: Path) -> None:
    if path.resolve().parent != boundary.resolve() and path != boundary:
        try:
            path.resolve().relative_to(boundary.resolve())
        except ValueError as exc:
            raise ReleaseError(f"refusing to clean path outside release boundary: {path}") from exc
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode):
        raise ReleaseError(f"refusing to clean linked path: {path}")
    if stat.S_ISREG(info.st_mode):
        if info.st_nlink != 1:
            raise ReleaseError(f"refusing to clean hard-linked file: {path}")
        path.unlink()
    elif stat.S_ISDIR(info.st_mode):
        for child in path.iterdir():
            _remove_regular_tree(child, boundary)
        if path != boundary:
            path.rmdir()
    else:
        raise ReleaseError(f"refusing to clean special file: {path}")


def reset_release() -> None:
    if RELEASE.exists() or RELEASE.is_symlink():
        info = RELEASE.lstat()
        if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode):
            raise ReleaseError(f"release output path is linked or not a directory: {RELEASE}")
        for child in RELEASE.iterdir():
            _remove_regular_tree(child, RELEASE)
    else:
        RELEASE.mkdir(parents=True, exist_ok=False)


def parse_frontmatter(text: str) -> dict[str, str]:
    match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not match:
        raise ReleaseError("SKILL.md has invalid YAML frontmatter delimiters")
    values: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if not line.strip():
            continue
        key, separator, value = line.partition(":")
        if not separator:
            raise ReleaseError(f"unsupported frontmatter line: {line}")
        key = key.strip()
        if key in values:
            raise ReleaseError(f"duplicate frontmatter key: {key}")
        values[key] = value.strip()
    return values


def run_self_test(skill: Path, *, seed: str) -> dict[str, Any]:
    environment = os.environ.copy()
    environment.update({"PYTHONDONTWRITEBYTECODE": "1", "PYTHONHASHSEED": seed})
    process = subprocess.run(
        [sys.executable, "-B", "scripts/self_test.py"], cwd=skill, text=True, capture_output=True,
        timeout=240, env=environment,
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
        "returncode": process.returncode, "summary": summary, "stdout": process.stdout, "stderr": process.stderr,
        "bytecode": bytecode, "seed": seed,
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


def _dotted_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _dotted_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return None


def inspect_capabilities(skill: Path) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    allowed = set(sys.stdlib_module_names) | LOCAL_MODULES
    metrics: dict[str, Any] = {"functions": 0, "largest_function_lines": 0}
    for path in sorted((skill / "scripts").glob("*.py")):
        try:
            text = stable_read_text(path)
            tree = ast.parse(text, filename=str(path))
        except (SyntaxError, ReleaseError) as exc:
            errors.append(f"cannot parse {path.name}: {exc}")
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                metrics["functions"] += 1
                if node.end_lineno:
                    metrics["largest_function_lines"] = max(metrics["largest_function_lines"], node.end_lineno - node.lineno + 1)
            if isinstance(node, ast.Import):
                imported = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported = [node.module]
            else:
                imported = []
            for module_name in imported:
                top = module_name.split(".", 1)[0]
                if top not in allowed:
                    errors.append(f"third-party import {module_name} in {path.name}")
                if any(module_name == prefix or module_name.startswith(prefix + ".") for prefix in FORBIDDEN_IMPORT_PREFIXES):
                    errors.append(f"forbidden network, process, or unsafe serialization import {module_name} in {path.name}")
            if isinstance(node, ast.Call):
                called = _dotted_name(node.func)
                if called in FORBIDDEN_CALLS or (called and called.startswith("subprocess.")):
                    errors.append(f"forbidden dynamic or process execution call {called} in {path.name}")
    if metrics["largest_function_lines"] > 320:
        errors.append(f"a script function exceeds the overengineering/readability bound: {metrics['largest_function_lines']} lines")
    return errors, metrics


def strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_strict_json(text: str) -> Any:
    return json.loads(
        text, object_pairs_hook=strict_object,
        parse_constant=lambda value: (_ for _ in ()).throw(ValueError(f"non-finite JSON value: {value}")),
    )


def validate_supporting_artifacts() -> tuple[list[str], list[str], dict[str, Any]]:
    errors: list[str] = []
    warnings: list[str] = []
    metrics: dict[str, Any] = {}
    for name in sorted(REQUIRED_REPORTS):
        path = REPORTS / name
        try:
            text = stable_read_text(path)
        except ReleaseError as exc:
            errors.append(str(exc))
            continue
        if not text.strip():
            errors.append(f"empty required report: {name}")
    metrics["reports"] = len([path for path in REPORTS.glob("*.md") if path.is_file()])

    protocol = EVALS / "evaluation.md"
    schema = EVALS / "rubric.schema.json"
    dataset = EVALS / "evals.jsonl"
    for path in (protocol, schema, dataset):
        try:
            if not stable_read_text(path).strip():
                errors.append(f"empty evaluation artifact: {path.name}")
        except ReleaseError as exc:
            errors.append(str(exc))
    try:
        parsed_schema = load_strict_json(stable_read_text(schema))
        if not isinstance(parsed_schema, dict) or parsed_schema.get("type") != "object":
            errors.append("evaluation rubric schema must describe a JSON object")
    except Exception as exc:
        errors.append(f"invalid rubric.schema.json: {exc}")

    cases: list[dict[str, Any]] = []
    seen: set[str] = set()
    try:
        lines = stable_read_text(dataset).splitlines()
    except ReleaseError:
        lines = []
    for line_number, line in enumerate(lines, start=1):
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
    if len(cases) < 70:
        errors.append(f"evaluation dataset is too small for the final integrated surface: {len(cases)} cases")
    if metrics["critical_eval_cases"] < 35:
        errors.append(f"evaluation dataset lacks critical-case depth: {metrics['critical_eval_cases']}<35")
    return errors, warnings, metrics


def validate_source() -> tuple[list[str], list[str], dict[str, Any]]:
    errors: list[str] = []
    warnings: list[str] = []
    metrics: dict[str, Any] = {}
    if not SKILL.is_dir():
        return [f"missing skill directory: {SKILL}"], warnings, metrics
    try:
        initial_files = regular_files(SKILL)
    except ReleaseError as exc:
        return [str(exc)], warnings, metrics
    initial_names = [path.relative_to(SKILL).as_posix() for path in initial_files]
    top = {path.relative_to(SKILL).parts[0] for path in initial_files}
    unexpected = sorted(top - ALLOWED_TOP)
    if unexpected:
        errors.append(f"unexpected skill top-level entries: {unexpected}")
    for required in ("SKILL.md", "agents/openai.yaml"):
        if not (SKILL / required).is_file():
            errors.append(f"missing required skill file: {required}")

    try:
        skill_text = stable_read_text(SKILL / "SKILL.md")
    except ReleaseError as exc:
        errors.append(str(exc))
        skill_text = ""
    lines = skill_text.splitlines()
    metrics["skill_lines"] = len(lines)
    metrics["skill_words"] = len(re.findall(r"\b\w+\b", skill_text))
    if len(lines) > 500:
        errors.append(f"SKILL.md exceeds 500 lines: {len(lines)}")
    try:
        frontmatter = parse_frontmatter(skill_text)
    except ReleaseError as exc:
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
    metrics["reference_lines"] = sum(len(stable_read_text(path).splitlines()) for path in references)
    metrics["script_lines"] = sum(len(stable_read_text(path).splitlines()) for path in scripts)
    if len(references) > 10:
        errors.append(f"too many reference files for progressive disclosure: {len(references)}")
    if len(scripts) > 7:
        errors.append(f"too many scripts after overengineering review: {len(scripts)}")
    for path in references:
        text = stable_read_text(path)
        if f"references/{path.name}" not in skill_text:
            errors.append(f"reference is not directly linked from SKILL.md: {path.name}")
        if len(text.splitlines()) > 100 and not re.search(r"^## Contents\s*$", text, re.MULTILINE):
            errors.append(f"long reference lacks a Contents section: {path.name}")
        if len(text.splitlines()) > 350:
            warnings.append(f"long reference file: {path.name}")
    for path in scripts:
        if path.name.startswith("_") or path.name == "self_test.py":
            continue
        if f"scripts/{path.name}" not in skill_text:
            errors.append(f"script is not documented in SKILL.md: {path.name}")

    yaml_text = stable_read_text(SKILL / "agents/openai.yaml") if (SKILL / "agents/openai.yaml").is_file() else ""
    short_match = re.search(r'^\s*short_description:\s*"([^"]+)"\s*$', yaml_text, re.MULTILINE)
    prompt_match = re.search(r'^\s*default_prompt:\s*"([^"]+)"\s*$', yaml_text, re.MULTILINE)
    if not short_match or not (25 <= len(short_match.group(1)) <= 64):
        errors.append("agents/openai.yaml has an invalid short_description")
    if not prompt_match or "$conduct-cs-research" not in prompt_match.group(1):
        errors.append("agents/openai.yaml default_prompt must name $conduct-cs-research")

    capability_errors, capability_metrics = inspect_capabilities(SKILL)
    errors.extend(capability_errors)
    metrics.update(capability_metrics)
    errors.extend(f"compile: {item}" for item in compile_scripts(SKILL))
    tests_zero = run_self_test(SKILL, seed="0")
    tests_random = run_self_test(SKILL, seed="314159")
    metrics["source_tests"] = tests_zero["summary"]
    metrics["source_tests_alt_hash_seed"] = tests_random["summary"]
    for test in (tests_zero, tests_random):
        if not test["passed"]:
            errors.append(f"source-tree self tests failed or emitted bytecode with PYTHONHASHSEED={test['seed']}")
            if test["bytecode"]:
                errors.append(f"source tests emitted bytecode: {test['bytecode']}")
            if test["stderr"]:
                warnings.append(test["stderr"][-8000:])

    try:
        final_files = regular_files(SKILL)
    except ReleaseError as exc:
        errors.append(str(exc))
        final_files = []
    final_names = [path.relative_to(SKILL).as_posix() for path in final_files]
    if initial_names != final_names:
        errors.append("source-tree file set changed during validation")

    workspace_counts: dict[str, int] = {}
    for mode, budget in WORKSPACE_BUDGETS.items():
        with tempfile.TemporaryDirectory(prefix="conduct audit Δ ") as temporary:
            project = Path(temporary) / "Project With Space"
            process = subprocess.run(
                [sys.executable, "-B", str(SKILL / "scripts/init_project.py"), str(project), "--name", "Release Audit", "--mode", mode],
                text=True, capture_output=True, timeout=60,
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONHASHSEED": "271828"},
            )
            if process.returncode != 0:
                errors.append(f"{mode} workspace initialization failed: {process.stderr[-2000:]}")
                continue
            count = sum(1 for path in project.rglob("*") if path.is_file())
            workspace_counts[mode] = count
            if count != WORKSPACE_EXPECTED[mode]:
                errors.append(f"{mode} workspace file set changed unexpectedly: {count}!={WORKSPACE_EXPECTED[mode]}")
            if count > budget:
                errors.append(f"{mode} workspace exceeds overengineering budget: {count}>{budget}")
            audit = subprocess.run(
                [sys.executable, "-B", str(SKILL / "scripts/audit_project.py"), str(project), "--json"],
                text=True, capture_output=True, timeout=60,
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONHASHSEED": "271828"},
            )
            if audit.returncode != 0:
                errors.append(f"fresh {mode} workspace audit failed: {audit.stdout[-3000:]} {audit.stderr[-2000:]}")
    metrics["workspace_files"] = workspace_counts
    metrics["source_files"] = len(final_files)
    metrics["source_bytes"] = sum(len(stable_read_bytes(path)) for path in final_files)
    return errors, warnings, metrics


def portable_member_name(name: str, seen: set[str]) -> list[str]:
    errors: list[str] = []
    if not name or "\x00" in name or "\\" in name:
        return [f"invalid archive name: {name!r}"]
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
        if part.split(".", 1)[0].upper() in WINDOWS_DEVICES:
            errors.append(f"reserved Windows archive component: {part!r}")
    return errors


def make_archive(zip_path: Path) -> None:
    with zipfile.ZipFile(zip_path, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=9, strict_timestamps=True) as archive:
        for path in regular_files(SKILL):
            relative = path.relative_to(SKILL).as_posix()
            info = zipfile.ZipInfo(f"conduct-cs-research/{relative}", date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            permission = 0o755 if path.parent.name == "scripts" and path.suffix == ".py" else 0o644
            info.external_attr = (stat.S_IFREG | permission) << 16
            archive.writestr(info, stable_read_bytes(path), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


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
        if len(infos) > 200 or metrics["archive_uncompressed_bytes"] > 15_000_000:
            errors.append("archive exceeds member or expansion budget")
        for info in infos:
            errors.extend(portable_member_name(info.filename, seen))
            mode = (info.external_attr >> 16) & 0o170000
            if mode != stat.S_IFREG:
                errors.append(f"archive contains a link, directory entry, or special file: {info.filename}")
            if info.flag_bits & 0x1:
                errors.append(f"archive contains encrypted member: {info.filename}")
            if info.compress_size and info.file_size / info.compress_size > 200:
                errors.append(f"archive member has suspicious compression ratio: {info.filename}")
            if info.date_time != (1980, 1, 1, 0, 0, 0):
                errors.append(f"archive timestamp is not deterministic: {info.filename}")
        corrupt = archive.testzip()
        if corrupt:
            errors.append(f"archive CRC check failed for {corrupt}")

        with tempfile.TemporaryDirectory(prefix="clean extraction Δ ") as temporary:
            destination = Path(temporary).resolve() / "Path With Space"
            destination.mkdir()
            for info in infos:
                target = destination / PurePosixPath(info.filename)
                try:
                    target.resolve().relative_to(destination)
                except (OSError, RuntimeError, ValueError):
                    errors.append(f"extraction path escapes destination: {info.filename}")
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                try:
                    with target.open("xb") as handle:
                        handle.write(archive.read(info))
                except FileExistsError:
                    errors.append(f"archive extraction collision: {info.filename}")
            extracted = destination / "conduct-cs-research"
            try:
                source_map = {path.relative_to(SKILL).as_posix(): stable_read_bytes(path) for path in regular_files(SKILL)}
                extracted_map = {path.relative_to(extracted).as_posix(): stable_read_bytes(path) for path in regular_files(extracted)}
            except ReleaseError as exc:
                errors.append(str(exc))
                source_map = {}; extracted_map = {}
            if source_map.keys() != extracted_map.keys():
                errors.append("clean extraction file set differs from source")
            else:
                for name in source_map:
                    if source_map[name] != extracted_map[name]:
                        errors.append(f"clean extraction byte mismatch: {name}")
            errors.extend(f"clean-extraction compile: {item}" for item in compile_scripts(extracted))
            extracted_test = run_self_test(extracted, seed="161803")
            if not extracted_test["passed"]:
                errors.append("clean-extraction self tests failed or emitted bytecode")
                if extracted_test["stderr"]:
                    errors.append(extracted_test["stderr"][-8000:])
            try:
                post_test_names = {path.relative_to(extracted).as_posix() for path in regular_files(extracted)}
            except ReleaseError as exc:
                errors.append(str(exc)); post_test_names = set()
            if post_test_names != set(extracted_map):
                errors.append("clean-extraction file set changed during tests")
    return errors, metrics, extracted_test


def validate_archive_name_guards() -> list[str]:
    malicious = [
        "../escape", "/absolute", "conduct-cs-research\\evil", "conduct-cs-research/../evil",
        "conduct-cs-research/CON.txt", "conduct-cs-research/file. ", "other-root/SKILL.md",
    ]
    errors: list[str] = []
    for name in malicious:
        if not portable_member_name(name, set()):
            errors.append(f"archive-name guard failed to reject {name!r}")
    collision_seen: set[str] = set()
    portable_member_name("conduct-cs-research/A.txt", collision_seen)
    if not portable_member_name("conduct-cs-research/a.txt", collision_seen):
        errors.append("archive-name guard failed to reject case-fold collision")
    return errors


def copy_supporting_artifacts() -> None:
    for source in sorted(REPORTS.glob("*")) + sorted(EVALS.glob("*")):
        if not source.exists():
            continue
        info = source.lstat()
        if not stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode) or info.st_nlink != 1:
            raise ReleaseError(f"supporting artifact is not a single-link regular file: {source}")
        destination = RELEASE / source.name
        with destination.open("xb") as handle:
            handle.write(stable_read_bytes(source))


def write_release_text(name: str, text: str) -> None:
    with (RELEASE / name).open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def main() -> int:
    started = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    try:
        reset_release()
    except ReleaseError as exc:
        print(json.dumps({"passed": False, "errors": [str(exc)]}, indent=2))
        return 1

    source_errors, source_warnings, metrics = validate_source()
    support_errors, support_warnings, support_metrics = validate_supporting_artifacts()
    metrics.update(support_metrics)
    errors = source_errors + support_errors + validate_archive_name_guards()
    warnings = source_warnings + support_warnings
    zip_path = RELEASE / ZIP_NAME
    archive_metrics: dict[str, Any] = {}
    extracted_test: dict[str, Any] = {}

    if not errors:
        make_archive(zip_path)
        with tempfile.TemporaryDirectory() as temporary:
            second = Path(temporary) / ZIP_NAME
            make_archive(second)
            first_bytes = stable_read_bytes(zip_path)
            second_bytes = stable_read_bytes(second)
            metrics["deterministic_rebuild_sha256"] = hashlib.sha256(second_bytes).hexdigest()
            if first_bytes != second_bytes:
                errors.append("two independent archive builds are not byte-identical")
            mutated = bytearray(first_bytes)
            if mutated:
                mutated[len(mutated) // 3] ^= 0x01
                metrics["mutation_changes_digest"] = hashlib.sha256(mutated).hexdigest() != hashlib.sha256(first_bytes).hexdigest()
                if not metrics["mutation_changes_digest"]:
                    errors.append("archive mutation did not change the release digest")
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
        "schema_version": 3,
        "started_at": started,
        "finished_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "passed": not errors,
        "errors": errors,
        "warnings": warnings,
        "metrics": metrics,
        "assurance_boundary": {
            "source_archives_byte_inspected": False,
            "source_integration_claim": "capability-level semantic supersession only",
            "reason": "The original conversation attachments were not exposed as readable bytes to this build environment. No claim of line-by-line equivalence, source-code reuse, or license verification is made.",
            "scientific_validity_proven": False,
            "semantic_equivalence_proven": False,
            "search_completeness_proven": False,
            "remote_q1_evidence_or_human_identity_authenticated": False,
            "journal_acceptance_or_q1_publication_guaranteed": False,
        },
    }
    write_release_text("validation.json", json.dumps(validation, indent=2, sort_keys=True) + "\n")
    text_lines = [
        f"Release validation: {'PASS' if validation['passed'] else 'FAIL'}",
        f"Errors: {len(errors)}", f"Warnings: {len(warnings)}",
        f"Source tests: {metrics.get('source_tests', {})}",
        f"Alternate-hash-seed tests: {metrics.get('source_tests_alt_hash_seed', {})}",
        f"Clean-extraction tests: {metrics.get('clean_extraction_tests', {})}",
        f"Skill lines: {metrics.get('skill_lines')}", f"Reference files: {metrics.get('reference_files')}",
        f"Script files: {metrics.get('script_files')}", f"Workspace files by mode: {metrics.get('workspace_files')}",
        f"Evaluation cases: {metrics.get('eval_cases')}", f"Critical evaluation cases: {metrics.get('critical_eval_cases')}",
        f"Archive members: {metrics.get('archive_members')}", f"ZIP SHA-256: {metrics.get('zip_sha256', 'not built')}",
        f"Deterministic rebuild SHA-256: {metrics.get('deterministic_rebuild_sha256', 'not built')}",
        "Original source-archive byte comparison: NOT PERFORMED; supersession is capability-level only.",
    ]
    if errors:
        text_lines.append("\nErrors:"); text_lines.extend(f"- {item}" for item in errors)
    if warnings:
        text_lines.append("\nWarnings:"); text_lines.extend(f"- {item}" for item in warnings if item)
    write_release_text("validation.txt", "\n".join(text_lines) + "\n")

    if zip_path.exists() and not errors:
        digest = sha256_file(zip_path)
        write_release_text(f"{ZIP_NAME}.sha256", f"{digest}  {ZIP_NAME}\n")
    manifest = {
        "release": ZIP_NAME, "passed": validation["passed"], "zip_sha256": metrics.get("zip_sha256"),
        "skill_source_files": metrics.get("source_files"), "source_tests": metrics.get("source_tests"),
        "source_tests_alt_hash_seed": metrics.get("source_tests_alt_hash_seed"),
        "clean_extraction_tests": metrics.get("clean_extraction_tests"), "workspace_files": metrics.get("workspace_files"),
        "eval_cases": metrics.get("eval_cases"),
        "reports": sorted(path.name for path in REPORTS.glob("*") if path.is_file()),
        "evals": sorted(path.name for path in EVALS.glob("*") if path.is_file()),
        "source_integration_claim": "capability-level semantic supersession only",
    }
    write_release_text("manifest.json", json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    copy_supporting_artifacts()
    write_release_text("release-ready.txt", "READY\n" if validation["passed"] else "NOT READY\n")
    print(json.dumps(validation, indent=2, sort_keys=True))
    return 0 if validation["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
