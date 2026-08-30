#!/usr/bin/env python3
"""Offline regression tests for the integrated conduct-cs-research skill."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))

import _common
import audit_latex
import audit_project
import audit_prose
import init_project
import score_journals


class ProjectTests(unittest.TestCase):
    MODE_COUNTS = {
        "full-research-lifecycle": 25,
        "systematic-search": 12,
        "peer-review": 7,
        "scientific-prose": 6,
    }

    @staticmethod
    def write_json(path: Path, value: object) -> None:
        path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")

    @classmethod
    def set_state(cls, target: Path, stage: str, gates: list[str], actions: list[dict[str, object]] | None = None) -> None:
        state = json.loads((target / "state.json").read_text(encoding="utf-8"))
        state["stage"] = stage
        state["completed_gates"] = gates
        if actions is not None:
            state["external_actions"] = actions
        cls.write_json(target / "state.json", state)

    def test_all_modes_are_proportionate_and_pass_at_intake(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for mode, expected_count in self.MODE_COUNTS.items():
                target = root / mode
                result = init_project.create_project(target, "Example", mode)
                self.assertEqual(result["files_created"], expected_count)
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

    def test_full_protocol_gate_is_enforced(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "project"
            init_project.create_project(target, "Example", "full-research-lifecycle")
            self.set_state(target, "protocol", [])
            self.assertFalse(audit_project.audit(target)["passed"])
            (target / "governance/charter.md").write_text("# Charter\n\nDefined objective and governance.\n", encoding="utf-8")
            (target / "protocol/protocol.md").write_text("# Protocol\n\nProspective methods and analysis are defined.\n", encoding="utf-8")
            self.set_state(target, "protocol", ["question", "protocol"])
            self.assertTrue(audit_project.audit(target)["passed"])

    def test_full_execution_requires_run(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "project"
            init_project.create_project(target, "Example", "full-research-lifecycle")
            (target / "governance/charter.md").write_text("complete", encoding="utf-8")
            (target / "protocol/protocol.md").write_text("complete", encoding="utf-8")
            self.set_state(target, "execution", ["question", "protocol", "pilot", "execution"])
            result = audit_project.audit(target)
            self.assertFalse(result["passed"])
            self.assertTrue(any("run record" in item for item in result["errors"]))

    def test_unknown_claim_source_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "project"
            init_project.create_project(target, "Example", "full-research-lifecycle")
            with (target / "claims/claims.csv").open("a", encoding="utf-8") as handle:
                handle.write("C0001,Claim,S9999,,active,,intro\n")
            result = audit_project.audit(target)
            self.assertFalse(result["passed"])
            self.assertTrue(any("unknown source_id" in item for item in result["errors"]))

    def test_retracted_source_cannot_silently_support_active_claim(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "project"
            init_project.create_project(target, "Example", "full-research-lifecycle")
            with (target / "evidence/sources.csv").open("a", encoding="utf-8") as handle:
                handle.write("S0001,Paper,A,2024,V,10.1/x,https://example.org,retracted,full-text,Retraction notice\n")
            with (target / "claims/claims.csv").open("a", encoding="utf-8") as handle:
                handle.write("C0001,The method improves accuracy,S0001,,active,,intro\n")
            result = audit_project.audit(target)
            self.assertFalse(result["passed"])
            self.assertTrue(any("retracted" in item for item in result["errors"]))

    def test_retraction_fact_can_reference_retracted_record(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "project"
            init_project.create_project(target, "Example", "full-research-lifecycle")
            with (target / "evidence/sources.csv").open("a", encoding="utf-8") as handle:
                handle.write("S0001,Paper,A,2024,V,10.1/x,https://example.org,retracted,full-text,Retraction notice\n")
            with (target / "claims/claims.csv").open("a", encoding="utf-8") as handle:
                handle.write("C0001,The source was retracted,S0001,,active,Retraction fact,related work\n")
            self.assertTrue(audit_project.audit(target)["passed"])

    def test_only_active_claims_require_manuscript_markers(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "project"
            init_project.create_project(target, "Example", "full-research-lifecycle")
            (target / "governance/charter.md").write_text("complete", encoding="utf-8")
            (target / "protocol/protocol.md").write_text("complete", encoding="utf-8")
            with (target / "study/runs.csv").open("a", encoding="utf-8") as handle:
                handle.write("E0001,experiment,2026-01-01,2026-01-01,abc,data,env,params,raw,complete,\n")
            with (target / "study/results.csv").open("a", encoding="utf-8") as handle:
                handle.write("R0001,E0001,analysis.py,1.0,0.1,stable,complete,\n")
            with (target / "claims/claims.csv").open("a", encoding="utf-8") as handle:
                handle.write("C0001,Supported claim,,R0001,active,,Introduction\n")
                handle.write("C0002,Withdrawn claim,,,withdrawn,,\n")
            (target / "manuscript/main.tex").write_text("\\documentclass{article}\n\\begin{document}\n% claim:C0001\nSupported claim.\n\\end{document}\n", encoding="utf-8")
            self.set_state(target, "manuscript", ["question", "protocol", "pilot", "execution", "analysis", "manuscript"])
            self.assertTrue(audit_project.audit(target)["passed"])

    def test_performed_external_action_requires_exact_payload(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "project"
            init_project.create_project(target, "Example", "peer-review")
            action = {"action": "submit", "status": "performed", "destination": "journal", "authorized_at": "2026-01-01", "performed_at": "2026-01-01", "outcome": "submitted"}
            self.set_state(target, "intake", [], [action])
            self.assertFalse(audit_project.audit(target)["passed"])

    def test_valid_external_action_payload_passes_and_mutation_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "project"
            init_project.create_project(target, "Example", "peer-review")
            payload_path = target / "governance/charter.md"
            digest = hashlib.sha256(payload_path.read_bytes()).hexdigest()
            action = {
                "action": "submit",
                "status": "performed",
                "destination": "journal portal",
                "authorized_at": "2026-01-01T00:00:00Z",
                "performed_at": "2026-01-01T00:01:00Z",
                "outcome": "submitted",
                "payload": [{"path": "governance/charter.md", "sha256": digest}],
            }
            self.set_state(target, "intake", [], [action])
            self.assertTrue(audit_project.audit(target)["passed"])
            payload_path.write_text("mutated", encoding="utf-8")
            self.assertFalse(audit_project.audit(target)["passed"])

    def test_systematic_protocol_gate_is_mode_specific(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "project"
            init_project.create_project(target, "Example", "systematic-search")
            self.set_state(target, "protocol", [])
            self.assertFalse(audit_project.audit(target)["passed"])
            (target / "governance/charter.md").write_text("complete", encoding="utf-8")
            (target / "protocol/search-protocol.md").write_text("complete search protocol", encoding="utf-8")
            self.set_state(target, "protocol", ["protocol"])
            self.assertTrue(audit_project.audit(target)["passed"])

    def test_peer_review_final_rejects_open_major_finding(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "project"
            init_project.create_project(target, "Example", "peer-review")
            (target / "governance/charter.md").write_text("complete", encoding="utf-8")
            (target / "review/review.md").write_text("complete review", encoding="utf-8")
            findings = target / "review/findings.csv"
            findings.write_text(findings.read_text(encoding="utf-8") + "F0001,major,Methods,Missing control,Section 3,Invalid inference,Add control,open\n", encoding="utf-8")
            self.set_state(target, "final", ["review", "final"])
            self.assertFalse(audit_project.audit(target)["passed"])
            findings.write_text(findings.read_text(encoding="utf-8").replace(",open\n", ",addressed\n"), encoding="utf-8")
            self.assertTrue(audit_project.audit(target)["passed"])

    def test_prose_final_rejects_incomplete_revision(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "project"
            init_project.create_project(target, "Example", "scientific-prose")
            (target / "governance/charter.md").write_text("complete", encoding="utf-8")
            (target / "manuscript/protected-spans.txt").write_text("None", encoding="utf-8")
            (target / "manuscript/residual-concerns.md").write_text("None", encoding="utf-8")
            log = target / "manuscript/revision-log.csv"
            log.write_text(log.read_text(encoding="utf-8") + "V0001,a.txt,b.txt,line edit,numbers,clarity,None,open\n", encoding="utf-8")
            self.set_state(target, "final", ["revision", "final"])
            self.assertFalse(audit_project.audit(target)["passed"])
            log.write_text(log.read_text(encoding="utf-8").replace(",open\n", ",complete\n"), encoding="utf-8")
            self.assertTrue(audit_project.audit(target)["passed"])

    @unittest.skipIf(not hasattr(os, "symlink"), "symlinks unavailable")
    def test_workspace_symlink_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "project"
            init_project.create_project(target, "Example", "peer-review")
            external = Path(temporary) / "external.txt"
            external.write_text("x", encoding="utf-8")
            os.symlink(external, target / "linked.txt")
            self.assertFalse(audit_project.audit(target)["passed"])

    @unittest.skipIf(not hasattr(os, "link"), "hardlinks unavailable")
    def test_workspace_hardlink_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "project"
            init_project.create_project(target, "Example", "peer-review")
            external = Path(temporary) / "external.txt"
            external.write_text("x", encoding="utf-8")
            os.link(external, target / "hard.txt")
            self.assertFalse(audit_project.audit(target)["passed"])


class CommonParserTests(unittest.TestCase):
    def test_duplicate_json_key_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "x.json"
            path.write_text('{"a": 1, "a": 2}', encoding="utf-8")
            with self.assertRaises(_common.ValidationError):
                _common.load_json(path)

    def test_nonfinite_json_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "x.json"
            path.write_text('{"a": NaN}', encoding="utf-8")
            with self.assertRaises(_common.ValidationError):
                _common.load_json(path)

    def test_extra_csv_field_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "x.csv"
            path.write_text("a,b\n1,2,3\n", encoding="utf-8")
            with self.assertRaises(_common.ValidationError):
                _common.read_csv(path)

    def test_duplicate_csv_header_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "x.csv"
            path.write_text("a,a\n1,2\n", encoding="utf-8")
            with self.assertRaises(_common.ValidationError):
                _common.read_csv(path)


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

    def test_optional_argument_citation_is_resolved(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "m"
            self.make_tree(root, r"\documentclass{article}\begin{document}\parencite[see][p.~3]{key}\bibliography{refs}\end{document}")
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

    def test_direct_lua_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "m"
            self.make_tree(root, r"\documentclass{article}\begin{document}\directlua{os.execute('whoami')}\end{document}")
            self.assertFalse(audit_latex.audit(root, Path("main.tex"))["passed"])

    def test_unsafe_command_in_comment_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "m"
            self.make_tree(root, "% \\write18{whoami}\n\\documentclass{article}\\begin{document}Safe\\end{document}")
            self.assertTrue(audit_latex.audit(root, Path("main.tex"))["passed"])

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

    def test_percentage_before_punctuation_is_stable(self) -> None:
        self.assertTrue(self.run_audit("Accuracy was 83.0% .", "Accuracy was 83.0%.")["passed"])

    def test_leading_decimal_change_fails(self) -> None:
        self.assertFalse(self.run_audit("p < .05", "p < .01")["passed"])

    def test_unicode_minus_change_fails(self) -> None:
        self.assertFalse(self.run_audit("The estimate was −1.2.", "The estimate was 1.2.")["passed"])

    def test_comparison_operator_change_fails(self) -> None:
        self.assertFalse(self.run_audit("p < .05", "p > .05")["passed"])

    def test_number_change_fails(self) -> None:
        self.assertFalse(self.run_audit("n=20", "n=21")["passed"])

    def test_citation_key_change_fails(self) -> None:
        self.assertFalse(self.run_audit(r"Evidence \cite{a}", r"Evidence \cite{b}")["passed"])

    def test_citation_optional_scope_change_fails(self) -> None:
        self.assertFalse(self.run_audit(r"Evidence \parencite[p.~3]{a}", r"Evidence \parencite[p.~30]{a}")["passed"])

    def test_math_change_fails(self) -> None:
        self.assertFalse(self.run_audit("$x=1$", "$x=2$")["passed"])

    def test_code_change_fails(self) -> None:
        self.assertFalse(self.run_audit("Use `alpha=1`.", "Use `alpha=2`.")["passed"])

    def test_doi_sentence_punctuation_is_normalized(self) -> None:
        self.assertTrue(self.run_audit("See doi:10.1000/example.", "See doi:10.1000/example;")["passed"])

    def test_url_sentence_punctuation_is_normalized(self) -> None:
        self.assertTrue(self.run_audit("See https://example.org/a.", "See https://example.org/a;")["passed"])

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
    FIELDS = ["journal", *score_journals.FIT_FIELDS, "provider", "metric_year", "category", "quartile", "verification_url", "verified_date", "notes"]

    def write_rows(self, root: Path, rows: list[dict[str, str]]) -> Path:
        path = root / "journals.csv"
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=self.FIELDS)
            writer.writeheader()
            writer.writerows(rows)
        return path

    def valid_row(self, *, journal: str = "Example Journal", fit: str = "5") -> dict[str, str]:
        today = date.today()
        return {
            "journal": journal,
            "scope_fit": fit,
            "methods_fit": fit,
            "audience_fit": fit,
            "article_fit": fit,
            "open_science_fit": fit,
            "provider": "JCR",
            "metric_year": str(today.year - 1),
            "category": "Computer Science, Artificial Intelligence",
            "quartile": "Q1",
            "verification_url": "https://jcr.clarivate.com/example",
            "verified_date": today.isoformat(),
            "notes": "",
        }

    def test_valid_q1_record_uses_provider_domain(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            result = score_journals.score(self.write_rows(Path(temporary), [self.valid_row()]))
            self.assertTrue(result["journals"][0]["q1_verified"], result)

    def test_missing_category_is_not_verified(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            row = self.valid_row()
            row["category"] = ""
            result = score_journals.score(self.write_rows(Path(temporary), [row]))
            self.assertFalse(result["journals"][0]["q1_verified"])

    def test_stale_verification_is_not_verified(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            row = self.valid_row()
            row["verified_date"] = (date.today() - timedelta(days=500)).isoformat()
            result = score_journals.score(self.write_rows(Path(temporary), [row]), max_verification_age=400)
            self.assertFalse(result["journals"][0]["q1_verified"])

    def test_untrusted_domain_is_not_verified_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            row = self.valid_row()
            row["verification_url"] = "https://example.com/q1"
            result = score_journals.score(self.write_rows(Path(temporary), [row]))
            self.assertFalse(result["journals"][0]["q1_verified"])

    def test_provider_domain_mismatch_is_not_verified(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            row = self.valid_row()
            row["verification_url"] = "https://www.scimagojr.com/example"
            result = score_journals.score(self.write_rows(Path(temporary), [row]))
            self.assertFalse(result["journals"][0]["q1_verified"])

    def test_fit_ranking_is_independent_of_q1(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            high = self.valid_row(journal="High Fit", fit="5")
            high["quartile"] = "Q2"
            low = self.valid_row(journal="Low Fit Q1", fit="1")
            result = score_journals.score(self.write_rows(Path(temporary), [low, high]))
            self.assertEqual(result["journals"][0]["journal"], "High Fit")
            self.assertFalse(result["journals"][0]["q1_verified"])

    def test_verified_q1_filter_is_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            high = self.valid_row(journal="High Fit", fit="5")
            high["quartile"] = "Q2"
            low = self.valid_row(journal="Low Fit Q1", fit="1")
            result = score_journals.score(self.write_rows(Path(temporary), [high, low]), verified_q1_only=True)
            self.assertEqual([item["journal"] for item in result["journals"]], ["Low Fit Q1"])

    def test_future_metric_year_is_not_verified(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            row = self.valid_row()
            row["metric_year"] = str(date.today().year + 1)
            result = score_journals.score(self.write_rows(Path(temporary), [row]))
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
        allowed = set(sys.stdlib_module_names) | {
            "_common",
            "audit_latex",
            "audit_project",
            "audit_prose",
            "init_project",
            "score_journals",
        }
        import_pattern = re.compile(r"^(?:from|import)\s+([A-Za-z_][A-Za-z0-9_]*)", re.MULTILINE)
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
