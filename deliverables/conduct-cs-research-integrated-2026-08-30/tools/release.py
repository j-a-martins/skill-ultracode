#!/usr/bin/env python3
"""Validate, test, and reproducibly package the conduct-cs-research skill."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import unicodedata
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "conduct-cs-research"
EVALS = ROOT / "evals"
REPORTS = ROOT / "reports"
TEST_FILE = ROOT / "tools/tests/test_skill.py"
RELEASE = ROOT / "release"
ARCHIVE_NAME = "conduct-cs-research-software-engineered-2026-08-31.zip"
ZIP_EPOCH = (2020, 1, 1, 0, 0, 0)
OPENAI_COMMIT = "49f948faa9258a0c61caceaf225e179651397431"
QUICK_VALIDATE_BLOB = "0547b4041a5f58fa19892079a114a1df98286406"
SKILL_CREATOR_BLOB = "72bc0b97e7a6476254a9d5c424c9971748402ec3"
PUBLIC_SCRIPTS = {
    "scripts/init_project.py",
    "scripts/audit_project.py",
    "scripts/audit_latex.py",
    "scripts/audit_prose.py",
    "scripts/score_journals.py",
}
EXPECTED_REPORTS = {
    "integration-and-supersession.md",
    "software-engineering-remediation.md",
    "extended-adversarial-review-round-4.md",
    "overengineering-review-round-4.md",
}
WINDOWS_DEVICES = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}
BAN_IMPORTS = {
    "socket",
    "http.client",
    "urllib.request",
    "ftplib",
    "smtplib",
    "telnetlib",
    "subprocess",
    "multiprocessing",
    "sqlite3",
    "pickle",
    "shelve",
    "marshal",
    "ctypes",
    "importlib",
}
BAN_CALLS = {"eval", "exec", "__import__", "os.system", "os.popen", "os.fork"}


class Gate:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.metrics: dict[str, Any] = {}
        self.checks: list[dict[str, Any]] = []

    def check(self, name: str, condition: bool, detail: str = "") -> None:
        self.checks.append({"name": name, "pass": bool(condition), "detail": detail})
        if not condition:
            self.errors.append(f"{name}: {detail or 'failed'}")


def git_blob_sha(data: bytes) -> str:
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=strict_object)


def word_count(text: str) -> int:
    return len(re.findall(r"\b[\w-]+\b", text, re.UNICODE))


def collect_files(root: Path) -> list[Path]:
    files: list[Path] = []
    stack = [root]
    while stack:
        directory = stack.pop()
        for entry in sorted(os.scandir(directory), key=lambda item: item.name):
            path = Path(entry.path)
            info = entry.stat(follow_symlinks=False)
            if stat.S_ISLNK(info.st_mode):
                raise ValueError(f"linked path in installable tree: {path}")
            if stat.S_ISDIR(info.st_mode):
                stack.append(path)
            elif stat.S_ISREG(info.st_mode) and info.st_nlink == 1:
                files.append(path)
            elif stat.S_ISREG(info.st_mode):
                raise ValueError(f"hard-linked file in installable tree: {path}")
            else:
                raise ValueError(f"special file in installable tree: {path}")
    return sorted(files, key=lambda path: path.relative_to(root).as_posix())


def parse_frontmatter(text: str) -> dict[str, str]:
    match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not match:
        raise ValueError("SKILL.md lacks YAML frontmatter")
    result: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if not line.strip():
            continue
        if ":" not in line:
            raise ValueError(f"invalid frontmatter line: {line}")
        key, value = line.split(":", 1)
        if key.strip() in result:
            raise ValueError(f"duplicate frontmatter key: {key.strip()}")
        result[key.strip()] = value.strip()
    return result


def validate_skill_tree(gate: Gate) -> list[Path]:
    try:
        files = collect_files(SKILL)
    except Exception as exc:
        gate.errors.append(str(exc))
        return []
    relative = {path.relative_to(SKILL).as_posix() for path in files}
    top = {name.split("/", 1)[0] for name in relative}
    gate.check("skill/top-level-layout", top <= {"SKILL.md", "agents", "references", "scripts"}, str(sorted(top)))
    gate.check("skill/required-files", {"SKILL.md", "agents/openai.yaml"} <= relative)
    nested = sorted(name for name in relative if name != "SKILL.md" and name.endswith("/SKILL.md"))
    gate.check("skill/no-nested-skills", not nested, str(nested))
    forbidden = sorted(
        name
        for name in relative
        if "__pycache__" in name
        or name.endswith((".pyc", ".pyo"))
        or "test" in Path(name).name.casefold()
        or Path(name).name in {"README.md", "CHANGELOG.md", "INSTALLATION_GUIDE.md", "QUICK_REFERENCE.md"}
    )
    gate.check("skill/no-development-or-auxiliary-files", not forbidden, str(forbidden))
    gate.metrics["skill_files"] = len(files)
    gate.metrics["skill_bytes"] = sum(path.stat().st_size for path in files)
    return files


def validate_frontmatter_and_ui(gate: Gate) -> None:
    text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    try:
        frontmatter = parse_frontmatter(text)
    except ValueError as exc:
        gate.errors.append(str(exc))
        return
    gate.check("metadata/keys", set(frontmatter) == {"name", "description"}, str(sorted(frontmatter)))
    gate.check("metadata/name", frontmatter.get("name") == "conduct-cs-research")
    description = frontmatter.get("description", "")
    gate.check("metadata/description", 1 <= len(description) <= 1024 and "<" not in description and ">" not in description)
    gate.check("metadata/description-words", word_count(description) <= 100, str(word_count(description)))
    ui = (SKILL / "agents/openai.yaml").read_text(encoding="utf-8")
    values = dict(re.findall(r'^\s{2}([a-z_]+):\s+"([^"]*)"\s*$', ui, re.MULTILINE))
    gate.check("ui/display-name", bool(values.get("display_name")))
    short = values.get("short_description", "")
    gate.check("ui/short-description", 25 <= len(short) <= 64, str(len(short)))
    prompt = values.get("default_prompt", "")
    gate.check("ui/default-prompt", "$conduct-cs-research" in prompt)


def validate_progressive_disclosure(gate: Gate) -> None:
    skill_text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    linked = set(re.findall(r"\[[^\]]+\]\(((?:references|scripts)/[^)#]+)\)", skill_text))
    missing = sorted(name for name in linked if not (SKILL / name).is_file())
    gate.check("disclosure/no-broken-direct-links", not missing, str(missing))
    references = sorted(path.relative_to(SKILL).as_posix() for path in (SKILL / "references").glob("*.md"))
    gate.check("disclosure/all-references-direct", set(references) <= linked, str(sorted(set(references) - linked)))
    gate.check("disclosure/public-scripts-direct", PUBLIC_SCRIPTS <= linked, str(sorted(PUBLIC_SCRIPTS - linked)))
    nested = list((SKILL / "references").glob("*/*.md"))
    gate.check("disclosure/one-level-references", not nested, str(nested))
    no_contents = []
    for name in references:
        text = (SKILL / name).read_text(encoding="utf-8")
        if len(text.splitlines()) > 100 and "## Contents" not in text:
            no_contents.append(name)
    gate.check("disclosure/long-reference-contents", not no_contents, str(no_contents))


def validate_token_budgets(gate: Gate) -> None:
    skill_text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    skill_words = word_count(skill_text)
    skill_bytes = len(skill_text.encode("utf-8"))
    skill_lines = len(skill_text.splitlines())
    gate.check("tokens/skill-words", skill_words <= 800, str(skill_words))
    gate.check("tokens/skill-bytes", skill_bytes <= 8000, str(skill_bytes))
    gate.check("tokens/skill-lines", skill_lines <= 120, str(skill_lines))
    route_limits = {
        "systematic-search.md": 2600,
        "peer-review.md": 2600,
        "scientific-prose.md": 2600,
        "study-design.md": 3000,
        "experiments-and-reproducibility.md": 3000,
        "manuscript-and-latex.md": 3000,
        "journal-selection.md": 2600,
        "integrity-ethics-and-policy.md": 3000,
    }
    route_words: dict[str, int] = {}
    for name, limit in route_limits.items():
        combined = skill_words + word_count((SKILL / "references" / name).read_text(encoding="utf-8"))
        route_words[name] = combined
        gate.check(f"tokens/route/{name}", combined <= limit, f"{combined}>{limit}")
    workflow = word_count((SKILL / "references/workflow.md").read_text(encoding="utf-8"))
    largest_stage = max(route_words.values(), default=skill_words) - skill_words
    full_context = skill_words + workflow + largest_stage
    gate.check("tokens/full-active-stage", full_context <= 4000, str(full_context))
    total_reference_words = sum(word_count(path.read_text(encoding="utf-8")) for path in (SKILL / "references").glob("*.md"))
    gate.check("tokens/total-references", total_reference_words <= 13000, str(total_reference_words))
    gate.metrics.update({"skill_words": skill_words, "skill_bytes": skill_bytes, "skill_lines": skill_lines, "full_active_stage_words": full_context, "reference_words": total_reference_words, "route_words": route_words})


def import_name(node: ast.AST) -> Iterable[str]:
    if isinstance(node, ast.Import):
        yield from (alias.name for alias in node.names)
    elif isinstance(node, ast.ImportFrom) and node.module:
        yield node.module


def dotted_call(node: ast.Call) -> str:
    current: ast.AST = node.func
    parts: list[str] = []
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        parts.append(current.id)
    return ".".join(reversed(parts))


def branch_count(node: ast.AST) -> int:
    branch_types = (ast.If, ast.For, ast.AsyncFor, ast.While, ast.Try, ast.BoolOp, ast.IfExp, ast.Match, ast.comprehension)
    return sum(isinstance(child, branch_types) for child in ast.walk(node))


def validate_runtime_code(gate: Gate) -> None:
    scripts = sorted((SKILL / "scripts").glob("*.py"))
    local = {path.stem for path in scripts}
    stdlib = set(getattr(sys, "stdlib_module_names", ()))
    policy_errors: list[str] = []
    size_errors: list[str] = []
    branch_errors: list[str] = []
    imports_seen: set[str] = set()
    for path in scripts:
        text = path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(text, filename=str(path))
            compile(text, str(path), "exec")
        except SyntaxError as exc:
            policy_errors.append(f"{path.name}: syntax error: {exc}")
            continue
        for node in ast.walk(tree):
            for module in import_name(node):
                imports_seen.add(module)
                if module in BAN_IMPORTS or any(module.startswith(name + ".") for name in BAN_IMPORTS):
                    policy_errors.append(f"{path.name}: banned import {module}")
                root = module.split(".", 1)[0]
                if root not in stdlib and root not in local:
                    policy_errors.append(f"{path.name}: non-stdlib import {module}")
            if isinstance(node, ast.Call):
                call = dotted_call(node)
                if call in BAN_CALLS or call.startswith(("os.spawn", "os.exec")):
                    policy_errors.append(f"{path.name}: banned call {call}")
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.end_lineno:
                lines = node.end_lineno - node.lineno + 1
                branches = branch_count(node)
                if lines > 120:
                    size_errors.append(f"{path.name}:{node.name}:{lines}")
                if branches > 25:
                    branch_errors.append(f"{path.name}:{node.name}:{branches}")
    gate.check("code/stdlib-and-side-effect-policy", not policy_errors, str(policy_errors))
    gate.check("code/function-size", not size_errors, str(size_errors))
    gate.check("code/function-branching", not branch_errors, str(branch_errors))
    gate.check("code/audit-orchestrator-size", (SKILL / "scripts/audit_project.py").stat().st_size <= 35000, str((SKILL / "scripts/audit_project.py").stat().st_size))
    gate.metrics.update({"runtime_scripts": len(scripts), "runtime_imports": sorted(imports_seen)})


def run_tests(skill: Path, hash_seed: str) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="conduct-cs-research-pycache-") as cache:
        env = os.environ.copy()
        env.update({"SKILL_UNDER_TEST": str(skill), "PYTHONDONTWRITEBYTECODE": "1", "PYTHONPYCACHEPREFIX": cache, "PYTHONHASHSEED": hash_seed})
        completed = subprocess.run([sys.executable, "-B", str(TEST_FILE)], cwd=ROOT, env=env, text=True, capture_output=True, timeout=180)
    if completed.returncode != 0:
        raise RuntimeError(f"tests failed for hash seed {hash_seed}:\n{completed.stdout}\n{completed.stderr}")
    for line in reversed(completed.stdout.splitlines()):
        try:
            result = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(result, dict) and "tests_run" in result:
            return result
    raise RuntimeError("test runner did not emit its JSON summary")


def validate_evaluations(gate: Gate) -> None:
    ids: set[str] = set()
    count = critical = 0
    errors: list[str] = []
    for path in sorted(EVALS.glob("*.jsonl")):
        for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if not raw.strip():
                continue
            try:
                item = json.loads(raw, object_pairs_hook=strict_object)
            except Exception as exc:
                errors.append(f"{path.name}:{line_no}: {exc}")
                continue
            required = {"id", "mode", "severity", "prompt", "expected", "forbidden"}
            if not isinstance(item, dict) or not required <= set(item):
                errors.append(f"{path.name}:{line_no}: invalid case shape")
                continue
            case_id = str(item["id"])
            if case_id in ids:
                errors.append(f"duplicate evaluation id: {case_id}")
            ids.add(case_id)
            if item["mode"] not in {None, "full-research-lifecycle", "systematic-search", "peer-review", "scientific-prose"}:
                errors.append(f"{case_id}: invalid mode")
            if item["severity"] not in {"critical", "major", "minor"}:
                errors.append(f"{case_id}: invalid severity")
            if not isinstance(item["prompt"], str) or not item["prompt"].strip():
                errors.append(f"{case_id}: empty prompt")
            if not isinstance(item["expected"], list) or not item["expected"]:
                errors.append(f"{case_id}: expected must be nonempty list")
            if not isinstance(item["forbidden"], list):
                errors.append(f"{case_id}: forbidden must be a list")
            count += 1
            critical += item["severity"] == "critical"
    try:
        schema = load_json(EVALS / "rubric.schema.json")
        if not isinstance(schema, dict) or "$schema" not in schema:
            errors.append("rubric.schema.json lacks a JSON Schema declaration")
    except Exception as exc:
        errors.append(f"rubric.schema.json: {exc}")
    gate.check("evaluations/structure", not errors, str(errors))
    gate.check("evaluations/count", count >= 80, str(count))
    gate.check("evaluations/critical-count", critical >= 30, str(critical))
    gate.metrics.update({"evaluation_cases": count, "critical_evaluation_cases": critical})


def validate_reports(gate: Gate) -> None:
    missing = sorted(name for name in EXPECTED_REPORTS if not (REPORTS / name).is_file())
    empty = sorted(name for name in EXPECTED_REPORTS if (REPORTS / name).is_file() and (REPORTS / name).stat().st_size < 500)
    gate.check("reports/required", not missing, str(missing))
    gate.check("reports/substantive", not empty, str(empty))


def verify_official_sources(gate: Gate, validator: Path, spec: Path, provenance: Path) -> None:
    try:
        record = load_json(provenance)
    except Exception as exc:
        gate.errors.append(f"validator provenance: {exc}")
        return
    gate.check("official/commit", record.get("commit") == OPENAI_COMMIT, str(record.get("commit")))
    gate.check("official/validator-blob", git_blob_sha(validator.read_bytes()) == QUICK_VALIDATE_BLOB, git_blob_sha(validator.read_bytes()))
    gate.check("official/spec-blob", git_blob_sha(spec.read_bytes()) == SKILL_CREATOR_BLOB, git_blob_sha(spec.read_bytes()))
    completed = subprocess.run([sys.executable, str(validator), str(SKILL)], text=True, capture_output=True, timeout=60)
    gate.check("official/quick-validate", completed.returncode == 0, (completed.stdout + completed.stderr).strip())
    gate.metrics["official_validator_output"] = (completed.stdout + completed.stderr).strip()


def portable_member(name: str) -> str | None:
    if not name or "\\" in name or unicodedata.normalize("NFC", name) != name:
        return "invalid separator, empty name, or non-NFC name"
    pure = PurePosixPath(name)
    if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
        return "absolute or traversal path"
    for part in pure.parts:
        trimmed = part.rstrip(" .")
        if trimmed != part:
            return "component has trailing dot or space"
        stem = trimmed.split(".", 1)[0].upper()
        if stem in WINDOWS_DEVICES or ":" in part:
            return "Windows-incompatible component"
    return None


def build_zip(destination: Path, files: list[Path]) -> None:
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            relative = path.relative_to(SKILL).as_posix()
            name = f"conduct-cs-research/{relative}"
            info = zipfile.ZipInfo(name, ZIP_EPOCH)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            mode = 0o755 if path.suffix == ".py" else 0o644
            info.external_attr = (stat.S_IFREG | mode) << 16
            archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def validate_zip(path: Path, expected_files: list[Path]) -> list[str]:
    errors: list[str] = []
    names: set[str] = set()
    aliases: set[str] = set()
    expected = {f"conduct-cs-research/{item.relative_to(SKILL).as_posix()}" for item in expected_files}
    with zipfile.ZipFile(path) as archive:
        if archive.testzip() is not None:
            errors.append("archive CRC failure")
        for info in archive.infolist():
            reason = portable_member(info.filename)
            if reason:
                errors.append(f"{info.filename}: {reason}")
            alias = unicodedata.normalize("NFC", info.filename).casefold()
            if info.filename in names or alias in aliases:
                errors.append(f"duplicate or portable alias: {info.filename}")
            names.add(info.filename)
            aliases.add(alias)
            mode = (info.external_attr >> 16) & 0xFFFF
            if info.flag_bits & 0x1:
                errors.append(f"encrypted member: {info.filename}")
            if not stat.S_ISREG(mode):
                errors.append(f"non-regular member: {info.filename}")
            if info.file_size > 20_000_000:
                errors.append(f"oversized member: {info.filename}")
            if info.compress_size and info.file_size / info.compress_size > 200:
                errors.append(f"excessive compression ratio: {info.filename}")
        if names != expected:
            errors.append(f"archive file set differs: missing={sorted(expected - names)}, extra={sorted(names - expected)}")
    return errors


def extract_and_compare(archive_path: Path, expected_files: list[Path], output: Path) -> Path:
    skill_out = output / "conduct-cs-research"
    with zipfile.ZipFile(archive_path) as archive:
        for info in archive.infolist():
            if portable_member(info.filename):
                raise RuntimeError(f"unsafe archive member: {info.filename}")
            target = output.joinpath(*PurePosixPath(info.filename).parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(info))
    expected = {item.relative_to(SKILL).as_posix(): item.read_bytes() for item in expected_files}
    actual = {item.relative_to(skill_out).as_posix(): item.read_bytes() for item in collect_files(skill_out)}
    if actual != expected:
        raise RuntimeError("clean extraction differs byte-for-byte from source")
    return skill_out


def clean_release_directory() -> None:
    if RELEASE.exists():
        if RELEASE.is_symlink() or not RELEASE.is_dir():
            raise RuntimeError(f"unsafe release output path: {RELEASE}")
        shutil.rmtree(RELEASE)
    RELEASE.mkdir()


def write_release(gate: Gate, archive_bytes: bytes, files: list[Path], test_results: dict[str, Any]) -> None:
    clean_release_directory()
    archive = RELEASE / ARCHIVE_NAME
    archive.write_bytes(archive_bytes)
    digest = hashlib.sha256(archive_bytes).hexdigest()
    (RELEASE / f"{ARCHIVE_NAME}.sha256").write_text(f"{digest}  {ARCHIVE_NAME}\n", encoding="utf-8")
    gate.metrics.update({"archive_name": ARCHIVE_NAME, "archive_sha256": digest, "archive_bytes": len(archive_bytes), "archive_members": len(files), "tests": test_results})
    record = {"passed": not gate.errors, "errors": gate.errors, "warnings": gate.warnings, "metrics": gate.metrics, "checks": gate.checks}
    (RELEASE / "validation.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = ["PASS" if not gate.errors else "FAIL", f"Errors: {len(gate.errors)}", f"Warnings: {len(gate.warnings)}", f"Archive: {ARCHIVE_NAME}", f"SHA-256: {digest}", f"Tests: {test_results.get('tests_run', 0)}"]
    (RELEASE / "validation.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    manifest = {item.relative_to(SKILL).as_posix(): {"sha256": sha256(item), "bytes": item.stat().st_size} for item in files}
    (RELEASE / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (RELEASE / "release-ready.txt").write_text(f"PASS\n{ARCHIVE_NAME}\n{digest}\n", encoding="utf-8")
    for name in sorted(EXPECTED_REPORTS):
        shutil.copyfile(REPORTS / name, RELEASE / name)
    for path in sorted(EVALS.iterdir()):
        if path.is_file():
            shutil.copyfile(path, RELEASE / path.name)


def validate_source(gate: Gate) -> list[Path]:
    files = validate_skill_tree(gate)
    if not files:
        return files
    validate_frontmatter_and_ui(gate)
    validate_progressive_disclosure(gate)
    validate_token_budgets(gate)
    validate_runtime_code(gate)
    validate_evaluations(gate)
    validate_reports(gate)
    return files


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--official-validator", type=Path)
    parser.add_argument("--skill-creator-spec", type=Path)
    parser.add_argument("--provenance", type=Path, default=ROOT / "tools/vendor/openai-skill-creator/provenance.json")
    args = parser.parse_args()
    gate = Gate()
    files = validate_source(gate)
    if gate.errors:
        print(json.dumps({"passed": False, "errors": gate.errors, "warnings": gate.warnings, "metrics": gate.metrics}, indent=2))
        return 1
    try:
        tests_zero = run_tests(SKILL, "0")
        tests_random = run_tests(SKILL, "123456789")
    except Exception as exc:
        gate.errors.append(str(exc))
        print(json.dumps({"passed": False, "errors": gate.errors}, indent=2))
        return 1
    gate.check("tests/source-two-hash-seeds", tests_zero["successful"] and tests_random["successful"])
    gate.metrics["source_tests_seed_0"] = tests_zero
    gate.metrics["source_tests_seed_random"] = tests_random
    if args.check_only:
        print(json.dumps({"passed": not gate.errors, "errors": gate.errors, "warnings": gate.warnings, "metrics": gate.metrics, "checks": gate.checks}, indent=2, sort_keys=True))
        return 0 if not gate.errors else 1
    if not args.official_validator or not args.skill_creator_spec:
        gate.errors.append("packaging requires the pinned official validator and skill-creator specification")
        print(json.dumps({"passed": False, "errors": gate.errors}, indent=2))
        return 1
    verify_official_sources(gate, args.official_validator, args.skill_creator_spec, args.provenance)
    if gate.errors:
        print(json.dumps({"passed": False, "errors": gate.errors}, indent=2))
        return 1
    try:
        with tempfile.TemporaryDirectory(prefix="conduct-cs-research-release-") as td:
            temp = Path(td)
            first = temp / "first.zip"
            second = temp / "second.zip"
            build_zip(first, files)
            build_zip(second, files)
            gate.check("archive/deterministic-dual-build", first.read_bytes() == second.read_bytes())
            archive_errors = validate_zip(first, files)
            gate.check("archive/structure", not archive_errors, str(archive_errors))
            extracted = extract_and_compare(first, files, temp / "extract")
            clean_tests = run_tests(extracted, "0")
            gate.check("tests/clean-extraction", clean_tests["successful"])
            gate.metrics["clean_extraction_tests"] = clean_tests
            if gate.errors:
                raise RuntimeError("release gate failed before emission")
            write_release(gate, first.read_bytes(), files, clean_tests)
    except Exception as exc:
        gate.errors.append(str(exc))
        print(json.dumps({"passed": False, "errors": gate.errors, "warnings": gate.warnings, "metrics": gate.metrics}, indent=2))
        return 1
    print(json.dumps({"passed": True, "errors": [], "warnings": gate.warnings, "metrics": gate.metrics}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
