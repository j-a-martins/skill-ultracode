#!/usr/bin/env python3
"""Offline regression tests for the integrated conduct-cs-research skill."""

from __future__ import annotations

import csv
import importlib
import json
import os
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))

import audit_latex
import audit_project
import audit_prose
import init_project
import score_journals


class ProjectTests(unittest.TestCase):
    def test_all_modes_initialize_and_audit_at_intake(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for mode in init_project.MODES:
                target = root / mode
                result = init_project.create_project(target, "Example", mode)
                self.assertGreaterEqual(result["files_created"], 15)
                audit = audit_project.audit(target)
                self.assertTrue(audit["passed"], audit)

    def test_create_only_rejects_existing_target(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "project"
            init_project.create_project(target, "Example", "peer-review")
            with self.assertRaises(FileExistsError):
                init_project.create_project(target, "Example", "peer-review")

    def test_invalid_project_name_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(ValueError):
                init_project.create_project(Path(temporary) / "p", "../bad", "peer-review")

    def test_protocol_gate_is_enforced(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "project"
            init_project.create_project(target, "Example", "full-research-lifecycle")
            state = json.loads((target / "state.json").read_text())
            state["stage"] = "protocol"
            (target / "state.json").write_text(json.dumps(state), encoding="utf-8")
            self.assertFalse(audit_project.audit(target)["passed"])
            (target / "governance/charter.md").write_text("# Charter\n\nDefined objective and governance.\n", encoding="utf-8")
            (target / "protocol/protocol.md").write_text("# Protocol\n\nProspective methods and analysis are defined.\n", encoding="utf-8")
            state["completed_gates"] = ["protocol"]
            (target / "state.json").write_text(json.dumps(state), encoding="utf-8")
            self.assertTrue(audit_project.audit(target)["passed"])

    def test_execution_requires_run(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "project"
            init_project.create_project(target, "Example", "peer-review")
            state = json.loads((target / "state.json").read_text())
            state.update({"stage": "execution", "completed_gates": ["protocol", "execution"]})
            (target / "state.json").write_text(json.dumps(state), encoding="utf-8")
            (target / "governance/charter.md").write_text("complete", encoding="utf-8")
            (target / "protocol/protocol.md").write_text("complete", encoding="utf-8")
            result = audit_project.audit(target)
            self.assertFalse(result["passed"])
            self.assertTrue(any("run record" in item for item in result["errors"]))

    def test_unknown_claim_source_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "project"
            init_project.create_project(target, "Example", "peer-review")
            with (target / "claims/claims.csv").open("a", encoding="utf-8") as handle:
                handle.write("C0001,Claim,S9999,,active,,intro\n")
            result = audit_project.audit(target)
            self.assertFalse(result["passed"])
            self.assertTrue(any("unknown source_id" in item for item in result["errors"]))

    def test_performed_external_action_needs_authorization(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "project"
            init_project.create_project(target, "Example", "peer-review")
            state = json.loads((target / "state.json").read_text())
            state["external_actions"] = [{"action": "submit", "status": "performed", "destination": "journal"}]
            (target / "state.json").write_text(json.dumps(state), encoding="utf-8")
            self.assertFalse(audit_project.audit(target)["passed"])

    @unittest.skipIf(not hasattr(os, "symlink"), "symlinks unavailable")
    def test_workspace_symlink_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "project"
            init_project.create_project(target, "Example", "peer-review")
            external = Path(temporary) / "external.txt"
            external.write_text("x", encoding="utf-8")
            os.symlink(external, target / "linked.txt")
            self.assertFalse(audit_project.audit(target)["passed"])


class LatexTests(unittest.TestCase):
    def make_tree(self, root: Path, tex: str, bib: str = "@article{key, title={T}}\n") -> None:
        root.mkdir()
        (root / "main.tex").write_text(tex, encoding="utf-8")
        (root / "refs.bib").write_text(bib, encoding="utf-8")

    def test_valid_latex(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "m"
            self.make_tree(root, r"\documentclass{article}\begin{document}\section{A}\label{sec:a}See \ref{sec:a} and \cite{key}.\bibliography{refs}\end{document}")
            self.assertTrue(audit_latex.audit(root, Path("main.tex"))["passed"])

    def test_missing_citation_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "m"
            self.make_tree(root, r"\documentclass{article}\begin{document}\cite{missing}\bibliography{refs}\end{document}")
            self.assertFalse(audit_latex.audit(root, Path("main.tex"))["passed"])

    def test_unsafe_shell_escape_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "m"
            self.make_tree(root, r"\documentclass{article}\begin{document}\immediate\write18{whoami}\end{document}")
            self.assertFalse(audit_latex.audit(root, Path("main.tex"))["passed"])

    def test_path_escape_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = base / "m"
            self.make_tree(root, r"\documentclass{article}\begin{document}\input{../outside}\end{document}")
            (base / "outside.tex").write_text("secret", encoding="utf-8")
            self.assertFalse(audit_latex.audit(root, Path("main.tex"))["passed"])

    def test_duplicate_label_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "m"
            self.make_tree(root, r"\documentclass{article}\begin{document}\label{x}\label{x}\end{document}")
            self.assertFalse(audit_latex.audit(root, Path("main.tex"))["passed"])

    def test_placeholder_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "m"
            self.make_tree(root, r"\documentclass{article}\begin{document}TODO: text\end{document}")
            self.assertFalse(audit_latex.audit(root, Path("main.tex"))["passed"])


class ProseTests(unittest.TestCase):
    def run_audit(self, original: str, revised: str, strict: bool = False) -> dict[str, object]:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            a = root / "a.txt"
            b = root / "b.txt"
            a.write_text(original, encoding="utf-8")
            b.write_text(revised, encoding="utf-8")
            return audit_prose.audit(a, b, strict=strict)

    def test_identical_protected_content_passes(self) -> None:
        result = self.run_audit("We observed 12.5% in \\cite{a}. $x=1$", "In \\cite{a}, we observed 12.5%. $x=1$")
        self.assertTrue(result["passed"], result)

    def test_number_change_fails(self) -> None:
        self.assertFalse(self.run_audit("n=20", "n=21")["passed"])

    def test_citation_change_fails(self) -> None:
        self.assertFalse(self.run_audit(r"Evidence \cite{a}", r"Evidence \cite{b}")["passed"])

    def test_math_change_fails(self) -> None:
        self.assertFalse(self.run_audit("$x=1$", "$x=2$")["passed"])

    def test_uncertainty_removal_warns(self) -> None:
        result = self.run_audit("The method may improve accuracy.", "The method improves accuracy.")
        self.assertTrue(result["passed"])
        self.assertTrue(result["warnings"])

    def test_uncertainty_removal_fails_strict(self) -> None:
        self.assertFalse(self.run_audit("The method may improve accuracy.", "The method improves accuracy.", strict=True)["passed"])

    def test_causal_strengthening_fails_strict(self) -> None:
        self.assertFalse(self.run_audit("X is associated with Y.", "X causes Y.", strict=True)["passed"])

    def test_negation_change_fails_strict(self) -> None:
        self.assertFalse(self.run_audit("The effect was not significant.", "The effect was significant.", strict=True)["passed"])


class JournalTests(unittest.TestCase):
    def write_csv(self, root: Path, row: dict[str, str]) -> Path:
        path = root / "journals.csv"
        fields = ["journal", *score_journals.FIT_FIELDS, "provider", "metric_year", "category", "quartile", "verification_url", "verified_date", "notes"]
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerow(row)
        return path

    def valid_row(self) -> dict[str, str]:
        today = date.today()
        return {
            "journal": "Example Journal",
            "scope_fit": "5",
            "methods_fit": "4",
            "audience_fit": "4",
            "article_fit": "5",
            "open_science_fit": "3",
            "provider": "JCR",
            "metric_year": str(today.year - 1),
            "category": "Computer Science, Artificial Intelligence",
            "quartile": "Q1",
            "verification_url": "https://clarivate.com/example",
            "verified_date": today.isoformat(),
            "notes": "",
        }

    def test_valid_q1_record(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            result = score_journals.score(self.write_csv(root, self.valid_row()), trusted_domains=["clarivate.com"])
            self.assertTrue(result["journals"][0]["q1_verified"], result)

    def test_missing_category_is_not_verified(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            row = self.valid_row()
            row["category"] = ""
            result = score_journals.score(self.write_csv(root, row))
            self.assertFalse(result["journals"][0]["q1_verified"])

    def test_stale_verification_is_not_verified(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            row = self.valid_row()
            row["verified_date"] = (date.today() - timedelta(days=500)).isoformat()
            result = score_journals.score(self.write_csv(root, row), max_verification_age=400)
            self.assertFalse(result["journals"][0]["q1_verified"])

    def test_untrusted_domain_is_not_verified(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            row = self.valid_row()
            row["verification_url"] = "https://example.com/q1"
            result = score_journals.score(self.write_csv(root, row), trusted_domains=["clarivate.com"])
            self.assertFalse(result["journals"][0]["q1_verified"])

    def test_fit_is_ranked_independently_of_q1(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            row = self.valid_row()
            row["quartile"] = "Q2"
            result = score_journals.score(self.write_csv(root, row))
            self.assertGreater(result["journals"][0]["fit_score"], 4)
            self.assertFalse(result["journals"][0]["q1_verified"])


class SkillStructureTests(unittest.TestCase):
    def test_skill_is_concise_and_links_resources(self) -> None:
        skill = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        self.assertLessEqual(len(skill.splitlines()), 500)
        for path in (SKILL_DIR / "references").glob("*.md"):
            self.assertIn(f"references/{path.name}", skill)
        for path in (SKILL_DIR / "scripts").glob("*.py"):
            if path.name.startswith("_") or path.name == "self_test.py":
                continue
            self.assertIn(f"scripts/{path.name}", skill)

    def test_trigger_description_covers_integrated_modes(self) -> None:
        frontmatter = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8").split("---", 2)[1].lower()
        for phrase in ("systematic", "peer review", "scientific-prose", "q1"):
            self.assertIn(phrase, frontmatter)

    def test_no_third_party_imports(self) -> None:
        allowed = set(sys.stdlib_module_names) | {"_common", "audit_latex", "audit_project", "audit_prose", "init_project", "score_journals"}
        import_pattern = __import__("re").compile(r"^(?:from|import)\s+([A-Za-z_][A-Za-z0-9_]*)", __import__("re").MULTILINE)
        for path in SCRIPT_DIR.glob("*.py"):
            for module in import_pattern.findall(path.read_text(encoding="utf-8")):
                self.assertIn(module, allowed, f"third-party import {module} in {path.name}")


def main() -> int:
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    summary = {
        "tests_run": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "skipped": len(result.skipped),
        "successful": result.wasSuccessful(),
    }
    print(json.dumps(summary, sort_keys=True))
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
