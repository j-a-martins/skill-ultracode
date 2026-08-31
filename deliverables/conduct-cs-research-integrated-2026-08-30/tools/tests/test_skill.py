#!/usr/bin/env python3
"""External offline regression suite for conduct-cs-research."""

from __future__ import annotations

import ast
import csv
import hashlib
import json
import os
import sys
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path

DELIVERABLE = Path(__file__).resolve().parents[2]
SKILL = Path(os.environ.get("SKILL_UNDER_TEST", DELIVERABLE / "conduct-cs-research")).resolve()
SCRIPTS = SKILL / "scripts"
sys.path.insert(0, str(SCRIPTS))

import _common
import _project_model
import audit_latex
import audit_project
import audit_prose
import init_project
import score_journals


class Helpers:
    @staticmethod
    def digest(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    @staticmethod
    def write_json(path: Path, value: object) -> None:
        path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    @staticmethod
    def append(path: Path, values: dict[str, object]) -> None:
        with path.open("r", encoding="utf-8", newline="") as handle:
            headers = next(csv.reader(handle))
        with path.open("a", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=headers)
            writer.writerow({key: values.get(key, "") for key in headers})

    @classmethod
    def state(cls, root: Path, stage: str, actions: list[object] | None = None) -> None:
        data = json.loads((root / "state.json").read_text(encoding="utf-8"))
        mode = json.loads((root / "project.json").read_text(encoding="utf-8"))["mode"]
        data["stage"] = stage
        data["completed_gates"] = _project_model.expected_gates(mode, stage)
        data["updated_at"] = _common.utc_now()
        if actions is not None:
            data["external_actions"] = actions
        cls.write_json(root / "state.json", data)

    @classmethod
    def full_manuscript(cls, root: Path, *, claim_status: str = "active") -> None:
        init_project.create_project(root, "Example", "full-research-lifecycle")
        (root / "governance/charter.md").write_text(
            "# Charter\n\nObjective, governance, ethics, authorship, and confidentiality are defined.\n",
            encoding="utf-8",
        )
        (root / "protocol/protocol.md").write_text(
            "# Protocol\n\nProspective design, analysis, stopping, and reporting are defined.\n",
            encoding="utf-8",
        )
        pilot = root / "study/pilot-output.txt"
        pilot.write_text("feasibility passed\n", encoding="utf-8")
        cls.write_json(
            root / "study/pilot-decision.json",
            {
                "decision": "go",
                "decided_at": _common.utc_now(),
                "protocol_effect": "No amendment required",
                "evidence": [{"path": "study/pilot-output.txt", "sha256": cls.digest(pilot)}],
            },
        )
        files = {
            "code_path": root / "study/code.py",
            "data_path": root / "study/data.txt",
            "environment_path": root / "study/environment.txt",
            "raw_output": root / "study/raw.json",
            "analysis_code": root / "study/analysis.py",
        }
        contents = {
            "code_path": "print('run')\n",
            "data_path": "fixed snapshot\n",
            "environment_path": "python=3.13\n",
            "raw_output": '{"metric": 1.0}\n',
            "analysis_code": "print('analyse')\n",
        }
        for key, path in files.items():
            path.write_text(contents[key], encoding="utf-8")
        cls.append(
            root / "study/runs.csv",
            {
                "run_id": "E0001",
                "kind": "experiment",
                "phase": "definitive",
                "started_at": "2026-08-30T10:00:00+00:00",
                "ended_at": "2026-08-30T10:01:00+00:00",
                "code_version": "commit-abc",
                "code_path": "study/code.py",
                "code_sha256": cls.digest(files["code_path"]),
                "data_version": "snapshot-1",
                "data_path": "study/data.txt",
                "data_sha256": cls.digest(files["data_path"]),
                "environment": "Python 3.13",
                "environment_path": "study/environment.txt",
                "environment_sha256": cls.digest(files["environment_path"]),
                "parameters": "seed=1",
                "raw_output": "study/raw.json",
                "raw_output_sha256": cls.digest(files["raw_output"]),
                "status": "complete",
            },
        )
        cls.append(
            root / "study/results.csv",
            {
                "result_id": "R0001",
                "run_ids": "E0001",
                "analysis_code": "study/analysis.py",
                "analysis_code_sha256": cls.digest(files["analysis_code"]),
                "input_paths": "study/raw.json",
                "input_sha256s": cls.digest(files["raw_output"]),
                "estimate": "1.0",
                "uncertainty": "95% CI [0.8, 1.2]",
                "robustness": "stable under sensitivity analysis",
                "status": "confirmed",
            },
        )
        cls.append(
            root / "claims/claims.csv",
            {
                "claim_id": "C0001",
                "text": "The measured result was 1.0.",
                "claim_type": "empirical",
                "result_ids": "R0001",
                "status": claim_status,
                "limitations": "Single test context",
                "manuscript_locations": "Results",
            },
        )
        (root / "manuscript/main.tex").write_text(
            "\\documentclass{article}\n\\begin{document}\n% claim:C0001\nThe measured result was 1.0.\n\\end{document}\n",
            encoding="utf-8",
        )
        cls.state(root, "manuscript")

    @classmethod
    def add_review(cls, root: Path, *, severity: str = "minor", status: str = "addressed") -> None:
        (root / "review/review.md").write_text(
            "# Review\n\nThe evidence was inspected.\n", encoding="utf-8"
        )
        cls.write_json(
            root / "review/summary.json",
            {
                "scope": "complete manuscript",
                "recommendation": "revise",
                "confidence": "medium",
                "limitations": "single internal review",
            },
        )
        cls.append(
            root / "review/findings.csv",
            {
                "finding_id": "F0001",
                "severity": severity,
                "confidence": "high",
                "location": "Discussion",
                "finding": "Clarify the limitation.",
                "evidence": "manuscript/main.tex",
                "consequence": "Readers may overgeneralize.",
                "action": "Add scope limitation.",
                "status": status,
            },
        )

    @classmethod
    def add_journals(cls, root: Path, *, two_categories: bool = False) -> str:
        evidence = root / "publication/q1-evidence.txt"
        evidence.write_text("Example Journal; JCR; Q1; 2025\n", encoding="utf-8")
        categories = ["Computer Science, Artificial Intelligence"]
        if two_categories:
            categories.append("Computer Science, Information Systems")
        for category in categories:
            cls.append(
                root / "publication/journals.csv",
                {
                    "journal": "Example Journal",
                    "issn": "1234-5679",
                    "scope_fit": "5",
                    "methods_fit": "5",
                    "audience_fit": "4",
                    "article_fit": "5",
                    "open_science_fit": "4",
                    "provider": "JCR",
                    "metric_name": "Journal Impact Factor quartile",
                    "metric_year": str(date.today().year - 1),
                    "category": category,
                    "quartile": "Q1",
                    "rank": "10",
                    "denominator": "100",
                    "verification_url": "https://jcr.clarivate.com/jcr-jp/journal-profile?journal=example",
                    "evidence_path": "q1-evidence.txt",
                    "evidence_sha256": cls.digest(evidence),
                    "verified_date": date.today().isoformat(),
                    "human_verified_by": "Researcher",
                    "human_verified_at": _common.utc_now(),
                },
            )
        return cls.digest(evidence)

    @classmethod
    def submission_ready(cls, root: Path, *, claim_status: str = "active") -> None:
        cls.full_manuscript(root, claim_status=claim_status)
        cls.add_review(root)
        digest = cls.add_journals(root, two_categories=True)
        cls.write_json(
            root / "publication/selected-journal.json",
            {
                "journal": "Example Journal",
                "issn": "1234-5679",
                "fit_rationale": "Strong fit",
                "selected_at": _common.utc_now(),
                "q1_claim": "verified",
                "provider": "JCR",
                "metric_year": str(date.today().year - 1),
                "category": "Computer Science, Artificial Intelligence",
                "evidence_sha256": digest,
            },
        )
        (root / "publication/submission-checklist.md").write_text(
            "# Checklist\n\nCurrent instructions, disclosures, payload, destination, and authorization checked.\n",
            encoding="utf-8",
        )
        cls.state(root, "submission-ready")

    @classmethod
    def systematic_synthesis(cls, root: Path) -> None:
        init_project.create_project(root, "Review", "systematic-search")
        (root / "governance/charter.md").write_text("# Charter\n\nScope and governance fixed.\n", encoding="utf-8")
        (root / "protocol/search-protocol.md").write_text("# Protocol\n\nQueries and criteria frozen prospectively.\n", encoding="utf-8")
        record = root / "evidence/source-record.txt"
        export = root / "evidence/export.json"
        record.write_text("canonical metadata\n", encoding="utf-8")
        export.write_text("[]\n", encoding="utf-8")
        cls.append(
            root / "evidence/sources.csv",
            {
                "source_id": "S0001",
                "title": "Paper",
                "status": "verified",
                "evidence_level": "full-text",
                "record_path": "evidence/source-record.txt",
                "record_sha256": cls.digest(record),
                "verified_at": _common.utc_now(),
            },
        )
        cls.append(
            root / "evidence/search-log.csv",
            {
                "search_id": "Q0001",
                "source": "DBLP",
                "interface": "API",
                "query": "test query",
                "executed_at": _common.utc_now(),
                "result_count": "1",
                "export_path": "evidence/export.json",
                "export_sha256": cls.digest(export),
            },
        )
        cls.append(root / "evidence/deduplication.csv", {"cluster_id": "K0001", "canonical_source_id": "S0001", "member_source_ids": "S0001", "method": "identifier", "resolver": "human"})
        cls.append(root / "evidence/screening.csv", {"record_id": "rec1", "source_ids": "S0001", "stage": "title-abstract", "decision": "include"})
        cls.append(root / "evidence/screening.csv", {"record_id": "rec1", "source_ids": "S0001", "stage": "full-text", "decision": "include"})
        cls.append(root / "evidence/extraction.csv", {"record_id": "rec1", "source_ids": "S0001", "method": "experiment", "outcomes": "result", "limitations": "single study", "evidence_access": "full-text-reviewed"})
        cls.write_json(root / "evidence/flow.json", {"identified": 1, "deduplicated": 1, "screened": 1, "full_text_assessed": 1, "included": 1})
        (root / "evidence/synthesis.md").write_text("# Synthesis\n\nOne included study with limited generality.\n", encoding="utf-8")
        cls.append(root / "claims/claims.csv", {"claim_id": "C0001", "text": "One study reported the result.", "claim_type": "synthesis", "source_ids": "S0001", "status": "active", "limitations": "Single study"})
        cls.state(root, "synthesis")


class InitializationTests(unittest.TestCase):
    def test_all_modes_initialize(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            for mode in init_project.MODES:
                target = Path(td) / mode
                result = init_project.create_project(target, mode, mode)
                self.assertEqual(result["files_created"], len(result["files"]))
                self.assertEqual(json.loads((target / "project.json").read_text())["mode"], mode)

    def test_existing_target_is_never_replaced(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "project"
            target.mkdir()
            sentinel = target / "sentinel"
            sentinel.write_text("keep", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                init_project.create_project(target, "x", "peer-review")
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep")

    def test_concurrent_initializers_have_one_winner(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "race"
            barrier = threading.Barrier(8)
            def attempt(index: int) -> str:
                barrier.wait()
                try:
                    init_project.create_project(target, f"p{index}", "peer-review")
                    return "ok"
                except FileExistsError:
                    return "exists"
            with ThreadPoolExecutor(max_workers=8) as pool:
                results = list(pool.map(attempt, range(8)))
            self.assertEqual(results.count("ok"), 1)
            self.assertEqual(results.count("exists"), 7)


class ParserAndTreeTests(unittest.TestCase):
    def test_duplicate_json_key_fails(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "x.json"
            path.write_text('{"a":1,"a":2}', encoding="utf-8")
            with self.assertRaises(_common.ValidationError):
                _common.load_json(path)

    def test_blank_csv_record_fails(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "x.csv"
            path.write_text("a,b\n,\n", encoding="utf-8")
            with self.assertRaises(_common.ValidationError):
                _common.read_csv(path)

    def test_tree_entry_limit_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for index in range(3):
                (root / f"f{index}").write_text("x", encoding="utf-8")
            with self.assertRaises(_common.ValidationError):
                _common.scan_tree(root, max_entries=2)

    def test_tree_depth_limit_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            deep = root / "a" / "b" / "c"
            deep.mkdir(parents=True)
            (deep / "x").write_text("x", encoding="utf-8")
            with self.assertRaises(_common.ValidationError):
                _common.scan_tree(root, max_depth=2)

    @unittest.skipUnless(hasattr(os, "symlink"), "symlink unavailable")
    def test_tree_rejects_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            target = root / "real"
            target.write_text("x", encoding="utf-8")
            (root / "link").symlink_to(target)
            with self.assertRaises(_common.ValidationError):
                _common.scan_tree(root)


class LifecycleTests(unittest.TestCase):
    def test_full_manuscript_passes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "p"
            Helpers.full_manuscript(root)
            self.assertTrue(audit_project.audit(root)["passed"])

    def test_gate_sequence_must_be_exact(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "p"
            Helpers.full_manuscript(root)
            state = json.loads((root / "state.json").read_text())
            state["completed_gates"] = list(reversed(state["completed_gates"]))
            Helpers.write_json(root / "state.json", state)
            self.assertFalse(audit_project.audit(root)["passed"])

    def test_complete_run_requires_code_binding(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "p"
            Helpers.full_manuscript(root)
            rows = list(csv.DictReader((root / "study/runs.csv").open()))
            rows[0]["code_path"] = ""
            rows[0]["code_sha256"] = ""
            with (root / "study/runs.csv").open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=rows[0])
                writer.writeheader(); writer.writerows(rows)
            self.assertFalse(audit_project.audit(root)["passed"])

    def test_active_result_requires_complete_run(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "p"
            Helpers.full_manuscript(root)
            text = (root / "study/runs.csv").read_text(encoding="utf-8").replace(",complete,", ",running,")
            (root / "study/runs.csv").write_text(text, encoding="utf-8")
            self.assertFalse(audit_project.audit(root)["passed"])

    def test_pilot_stop_blocks_execution(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "p"
            Helpers.full_manuscript(root)
            decision = json.loads((root / "study/pilot-decision.json").read_text())
            decision["decision"] = "stop"
            Helpers.write_json(root / "study/pilot-decision.json", decision)
            self.assertFalse(audit_project.audit(root)["passed"])

    def test_pilot_revise_requires_bound_amendment(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "p"
            Helpers.full_manuscript(root)
            decision = json.loads((root / "study/pilot-decision.json").read_text())
            decision["decision"] = "revise"
            Helpers.write_json(root / "study/pilot-decision.json", decision)
            self.assertFalse(audit_project.audit(root)["passed"])

    def test_pilot_revise_with_bound_amendment_passes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "p"
            Helpers.full_manuscript(root)
            amendment = root / "protocol/amendments.md"
            amendment.write_text("# Amendment\n\nChanged the instrumentation before definitive execution.\n", encoding="utf-8")
            decision = json.loads((root / "study/pilot-decision.json").read_text())
            decision.update({"decision": "revise", "amendment_path": "protocol/amendments.md", "amendment_sha256": Helpers.digest(amendment)})
            Helpers.write_json(root / "study/pilot-decision.json", decision)
            self.assertTrue(audit_project.audit(root)["passed"])

    def test_needs_review_claim_blocks_submission(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "p"
            Helpers.submission_ready(root, claim_status="needs-review")
            result = audit_project.audit(root)
            self.assertFalse(result["passed"])
            self.assertTrue(any("needs-review" in item for item in result["errors"]))

    def test_unresolved_major_finding_blocks_submission(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "p"
            Helpers.submission_ready(root)
            rows = list(csv.DictReader((root / "review/findings.csv").open()))
            rows[0]["severity"] = "major"; rows[0]["status"] = "disputed"
            with (root / "review/findings.csv").open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=rows[0]); writer.writeheader(); writer.writerows(rows)
            self.assertFalse(audit_project.audit(root)["passed"])

    def test_open_response_blocks_acceptance(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "p"
            Helpers.submission_ready(root)
            Helpers.append(root / "review/response-matrix.csv", {"comment_id": "R1", "comment": "fix", "assessment": "agree", "rationale": "needed", "action": "revise", "status": "open"})
            evidence = root / "publication/decision-letter.txt"; evidence.write_text("accepted", encoding="utf-8")
            Helpers.write_json(root / "publication/decision.json", {"status": "accepted", "venue": "Example Journal", "decided_at": _common.utc_now(), "evidence_path": "publication/decision-letter.txt", "evidence_sha256": Helpers.digest(evidence)})
            Helpers.state(root, "accepted")
            self.assertFalse(audit_project.audit(root)["passed"])


class SearchTests(unittest.TestCase):
    def test_systematic_synthesis_passes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "p"
            Helpers.systematic_synthesis(root)
            self.assertTrue(audit_project.audit(root)["passed"])

    def test_flow_count_must_match_screening_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "p"
            Helpers.systematic_synthesis(root)
            flow = json.loads((root / "evidence/flow.json").read_text()); flow["screened"] = 2
            Helpers.write_json(root / "evidence/flow.json", flow)
            self.assertFalse(audit_project.audit(root)["passed"])

    def test_flow_count_must_match_full_text_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "p"
            Helpers.systematic_synthesis(root)
            flow = json.loads((root / "evidence/flow.json").read_text()); flow["full_text_assessed"] = 0
            Helpers.write_json(root / "evidence/flow.json", flow)
            self.assertFalse(audit_project.audit(root)["passed"])

    def test_included_set_must_equal_extraction_set(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "p"
            Helpers.systematic_synthesis(root)
            (root / "evidence/extraction.csv").write_text((root / "evidence/extraction.csv").read_text().splitlines()[0] + "\n", encoding="utf-8")
            self.assertFalse(audit_project.audit(root)["passed"])

    def test_deduplication_rejects_duplicate_member(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "p"
            Helpers.systematic_synthesis(root)
            text = (root / "evidence/deduplication.csv").read_text().replace("S0001,identifier", "S0001;S0001,identifier")
            (root / "evidence/deduplication.csv").write_text(text, encoding="utf-8")
            self.assertFalse(audit_project.audit(root)["passed"])

    def test_source_cannot_belong_to_two_clusters(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "p"
            Helpers.systematic_synthesis(root)
            Helpers.append(root / "evidence/deduplication.csv", {"cluster_id": "K0002", "canonical_source_id": "S0001", "member_source_ids": "S0001", "method": "title", "resolver": "human"})
            self.assertFalse(audit_project.audit(root)["passed"])


class JournalTests(unittest.TestCase):
    def _score(self, issn: str, *, categories: int = 1) -> dict[str, object]:
        td = tempfile.TemporaryDirectory(); self.addCleanup(td.cleanup)
        root = Path(td.name); csv_path = root / "journals.csv"; evidence = root / "e.txt"
        evidence.write_text("record", encoding="utf-8")
        csv_path.write_text("journal,issn,scope_fit,methods_fit,audience_fit,article_fit,open_science_fit,provider,metric_name,metric_year,category,quartile,rank,denominator,verification_url,evidence_path,evidence_sha256,verified_date,human_verified_by,human_verified_at,notes\n", encoding="utf-8")
        for index in range(categories):
            Helpers.append(csv_path, {"journal": "Example", "issn": issn, "scope_fit": "5", "methods_fit": "5", "audience_fit": "4", "article_fit": "5", "open_science_fit": "4", "provider": "JCR", "metric_name": "JIF quartile", "metric_year": str(date.today().year - 1), "category": f"Category {index}", "quartile": "Q1", "rank": "1", "denominator": "10", "verification_url": "https://jcr.clarivate.com/jcr-jp/journal-profile?journal=example", "evidence_path": "e.txt", "evidence_sha256": Helpers.digest(evidence), "verified_date": date.today().isoformat(), "human_verified_by": "Researcher", "human_verified_at": _common.utc_now()})
        return score_journals.score(csv_path)

    def test_missing_issn_cannot_verify_q1(self) -> None:
        result = self._score("")
        self.assertTrue(result["passed"])
        self.assertFalse(result["journals"][0]["q1_verified"])

    def test_bad_issn_checksum_cannot_verify_q1(self) -> None:
        result = self._score("1234-567X")
        self.assertFalse(result["journals"][0]["q1_verified"])

    def test_valid_issn_can_verify_q1(self) -> None:
        result = self._score("1234-5679")
        self.assertTrue(result["journals"][0]["q1_verified"])

    def test_multiple_category_records_are_supported(self) -> None:
        result = self._score("1234-5679", categories=2)
        self.assertTrue(result["passed"])
        self.assertEqual(len(result["journals"]), 2)

    def test_exact_category_selection_passes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "p"; Helpers.submission_ready(root)
            self.assertTrue(audit_project.audit(root)["passed"])

    def test_wrong_category_selection_fails(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "p"; Helpers.submission_ready(root)
            selected = json.loads((root / "publication/selected-journal.json").read_text())
            selected["category"] = "Wrong category"; Helpers.write_json(root / "publication/selected-journal.json", selected)
            self.assertFalse(audit_project.audit(root)["passed"])


class LaTeXAndProseTests(unittest.TestCase):
    def test_simple_latex_passes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); (root / "main.tex").write_text("\\documentclass{article}\n\\begin{document}x\\end{document}\n", encoding="utf-8")
            self.assertTrue(audit_latex.audit(root, Path("main.tex"))["passed"])

    def test_direct_lua_fails(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); (root / "main.tex").write_text("\\directlua{os.execute('x')}", encoding="utf-8")
            self.assertFalse(audit_latex.audit(root, Path("main.tex"))["passed"])

    def test_latex_entry_limit_fails(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); (root / "main.tex").write_text("x", encoding="utf-8"); (root / "extra").write_text("x", encoding="utf-8")
            self.assertFalse(audit_latex.audit(root, Path("main.tex"), max_entries=1)["passed"])

    def test_bibtex_comment_does_not_create_key(self) -> None:
        keys, errors = audit_latex.parse_bibtex_keys("@comment{ @article{fake, title={x}} }\n@article{real,title={y}}", "x")
        self.assertEqual(keys, ["real"]); self.assertFalse(errors)

    def test_duplicate_bib_key_fails(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); (root / "main.tex").write_text("\\bibliography{a,b}", encoding="utf-8")
            (root / "a.bib").write_text("@article{k,title={a}}", encoding="utf-8")
            (root / "b.bib").write_text("@article{k,title={b}}", encoding="utf-8")
            self.assertFalse(audit_latex.audit(root, Path("main.tex"))["passed"])

    def test_prose_number_change_fails(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); a = root / "a.txt"; b = root / "b.txt"
            a.write_text("Accuracy was 91.2%.", encoding="utf-8"); b.write_text("Accuracy was 92.1%.", encoding="utf-8")
            self.assertFalse(audit_prose.audit(a, b, strict=True)["passed"])

    def test_prose_direction_reversal_fails(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); a = root / "a.txt"; b = root / "b.txt"
            a.write_text("The method increased accuracy.", encoding="utf-8"); b.write_text("The method decreased accuracy.", encoding="utf-8")
            self.assertFalse(audit_prose.audit(a, b, strict=True)["passed"])


class ProvenanceAndActionTests(unittest.TestCase):
    def test_retracted_source_cannot_be_sole_support(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "p"; init_project.create_project(root, "x", "systematic-search")
            record = root / "evidence/r.txt"; record.write_text("retraction notice", encoding="utf-8")
            Helpers.append(root / "evidence/sources.csv", {"source_id": "S0001", "title": "Retracted", "status": "retracted", "evidence_level": "full-text", "record_path": "evidence/r.txt", "record_sha256": Helpers.digest(record), "verified_at": _common.utc_now(), "notes": "Retracted"})
            Helpers.append(root / "claims/claims.csv", {"claim_id": "C0001", "text": "Ordinary claim", "claim_type": "background", "source_ids": "S0001", "status": "active", "limitations": "None"})
            result = audit_project.audit(root)
            self.assertFalse(result["passed"])
            self.assertTrue(any("sole support" in item for item in result["errors"]))

    def test_payload_tamper_invalidates_authorization(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "p"; init_project.create_project(root, "x", "peer-review")
            payload = root / "review/review.md"; payload.write_text("draft", encoding="utf-8")
            now = _common.parse_timestamp(_common.utc_now())
            action = {"action_id": "A0001", "action": "email", "destination": "editor@example.test", "payload": [{"path": "review/review.md", "sha256": Helpers.digest(payload)}], "status": "authorized", "authorized_at": now.isoformat(), "expires_at": (now + timedelta(hours=1)).isoformat(), "authorized_by": "Author", "authorization_statement": "Send these exact bytes"}
            Helpers.state(root, "intake", [action]); payload.write_text("changed", encoding="utf-8")
            self.assertFalse(audit_project.audit(root)["passed"])


class ArchitectureTests(unittest.TestCase):
    def test_skill_is_token_bounded(self) -> None:
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        words = len(__import__("re").findall(r"\b[\w-]+\b", text))
        self.assertLessEqual(len(text.encode("utf-8")), 8000)
        self.assertLessEqual(words, 800)
        self.assertLessEqual(len(text.splitlines()), 120)

    def test_no_development_tests_ship(self) -> None:
        names = {path.relative_to(SKILL).as_posix() for path in SKILL.rglob("*") if path.is_file()}
        self.assertFalse(any("test" in Path(name).name.lower() for name in names))
        self.assertFalse(any("__pycache__" in name or name.endswith((".pyc", ".pyo")) for name in names))

    def test_public_clis_expose_help(self) -> None:
        import subprocess
        for name in ("init_project.py", "audit_project.py", "audit_latex.py", "audit_prose.py", "score_journals.py"):
            result = subprocess.run([sys.executable, "-B", str(SCRIPTS / name), "--help"], text=True, capture_output=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("usage:", result.stdout.lower())

    def test_function_size_budget(self) -> None:
        offenders: list[str] = []
        for path in SCRIPTS.glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and getattr(node, "end_lineno", None):
                    size = node.end_lineno - node.lineno + 1
                    if size > 120:
                        offenders.append(f"{path.name}:{node.name}:{size}")
        self.assertEqual(offenders, [])

    def test_audit_orchestrator_is_small(self) -> None:
        self.assertLessEqual((SCRIPTS / "audit_project.py").stat().st_size, 35_000)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print(json.dumps({"tests_run": result.testsRun, "failures": len(result.failures), "errors": len(result.errors), "skipped": len(result.skipped), "successful": result.wasSuccessful()}, sort_keys=True))
    raise SystemExit(0 if result.wasSuccessful() else 1)
