#!/usr/bin/env python3
"""Offline regression tests for the final-audit conduct-cs-research skill."""

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


class WorkspaceMixin:
    @staticmethod
    def write_json(path: Path, value: object) -> None:
        path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")

    @staticmethod
    def digest(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    @staticmethod
    def append_row(path: Path, values: dict[str, object]) -> None:
        with path.open("r", encoding="utf-8", newline="") as handle:
            headers = next(csv.reader(handle))
        with path.open("a", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=headers)
            writer.writerow({header: values.get(header, "") for header in headers})

    @classmethod
    def set_state(cls, target: Path, stage: str, gates: list[str], actions: list[dict[str, object]] | None = None) -> None:
        state = json.loads((target / "state.json").read_text(encoding="utf-8"))
        state["stage"] = stage
        state["completed_gates"] = gates
        state["updated_at"] = _common.utc_now()
        if actions is not None:
            state["external_actions"] = actions
        cls.write_json(target / "state.json", state)

    @classmethod
    def complete_full_to_manuscript(cls, target: Path) -> None:
        init_project.create_project(target, "Example", "full-research-lifecycle")
        (target / "governance/charter.md").write_text("# Charter\n\nObjective, governance, ethics, authorship, and confidentiality are defined.\n", encoding="utf-8")
        (target / "protocol/protocol.md").write_text("# Protocol\n\nProspective study design, analysis, stopping, and reporting are defined.\n", encoding="utf-8")

        pilot = target / "study/pilot-output.txt"
        pilot.write_text("instrumentation and feasibility passed", encoding="utf-8")
        cls.write_json(
            target / "study/pilot-decision.json",
            {
                "decision": "go",
                "decided_at": _common.utc_now(),
                "protocol_effect": "No amendment required",
                "evidence": [{"path": "study/pilot-output.txt", "sha256": cls.digest(pilot)}],
            },
        )

        code = target / "study/code.py"
        data = target / "study/data.txt"
        environment = target / "study/environment.txt"
        raw = target / "study/raw.json"
        analysis = target / "study/analysis.py"
        code.write_text("print('run')\n", encoding="utf-8")
        data.write_text("fixed data snapshot\n", encoding="utf-8")
        environment.write_text("python=3.12\n", encoding="utf-8")
        raw.write_text('{"metric": 1.0}\n', encoding="utf-8")
        analysis.write_text("print('analyse')\n", encoding="utf-8")
        cls.append_row(
            target / "study/runs.csv",
            {
                "run_id": "E0001", "kind": "experiment", "phase": "definitive",
                "started_at": "2026-08-30T10:00:00+00:00", "ended_at": "2026-08-30T10:01:00+00:00",
                "code_version": "commit-abc", "code_path": "study/code.py", "code_sha256": cls.digest(code),
                "data_version": "snapshot-1", "data_path": "study/data.txt", "data_sha256": cls.digest(data),
                "environment": "Python 3.12", "environment_path": "study/environment.txt", "environment_sha256": cls.digest(environment),
                "parameters": "seed=1", "raw_output": "study/raw.json", "raw_output_sha256": cls.digest(raw),
                "status": "complete", "notes": "",
            },
        )
        cls.append_row(
            target / "study/results.csv",
            {
                "result_id": "R0001", "run_ids": "E0001", "analysis_code": "study/analysis.py",
                "analysis_code_sha256": cls.digest(analysis), "input_paths": "study/raw.json",
                "input_sha256s": cls.digest(raw), "estimate": "1.0", "uncertainty": "95% CI [0.8,1.2]",
                "robustness": "stable under prespecified sensitivity check", "status": "confirmed", "notes": "",
            },
        )
        cls.append_row(
            target / "claims/claims.csv",
            {
                "claim_id": "C0001", "text": "The measured result was 1.0.", "claim_type": "empirical",
                "source_ids": "", "result_ids": "R0001", "status": "active", "limitations": "Single test context",
                "manuscript_locations": "Results",
            },
        )
        (target / "manuscript/main.tex").write_text(
            "\\documentclass{article}\n\\begin{document}\n% claim:C0001\nThe measured result was 1.0.\n\\end{document}\n",
            encoding="utf-8",
        )
        cls.set_state(
            target,
            "manuscript",
            ["question", "protocol", "pilot", "execution", "analysis", "manuscript"],
        )

    @classmethod
    def complete_full_to_archive(cls, target: Path) -> None:
        cls.complete_full_to_manuscript(target)
        (target / "review/review.md").write_text(
            "# Internal review\n\nNo material findings.\n\nRecommendation: ready with editorial changes.\nConfidence: medium.\n",
            encoding="utf-8",
        )
        cls.write_json(
            target / "review/summary.json",
            {"scope": "complete manuscript", "recommendation": "ready with editorial changes", "confidence": "medium", "limitations": "single internal review"},
        )
        cls.append_row(
            target / "review/response-matrix.csv",
            {
                "comment_id": "R1.1", "comment": "Clarify limitation", "assessment": "agree",
                "rationale": "Improves calibration", "action": "Add limitation", "manuscript_change": "Discussion",
                "evidence": "manuscript/main.tex", "residual_limitation": "None", "status": "verified",
            },
        )

        evidence = target / "publication/jcr-evidence.txt"
        evidence.write_text("Example Journal; JCR; Computer Science; Q1; 2025\n", encoding="utf-8")
        today = date.today()
        cls.append_row(
            target / "publication/journals.csv",
            {
                "journal": "Example Journal", "issn": "1234-567X", "scope_fit": "5", "methods_fit": "5",
                "audience_fit": "4", "article_fit": "5", "open_science_fit": "4", "provider": "JCR",
                "metric_name": "Journal Impact Factor quartile", "metric_year": str(today.year - 1),
                "category": "Computer Science, Artificial Intelligence", "quartile": "Q1", "rank": "10",
                "denominator": "100", "verification_url": "https://jcr.clarivate.com/jcr-jp/journal-profile?journal=example",
                "evidence_path": "jcr-evidence.txt", "evidence_sha256": cls.digest(evidence),
                "verified_date": today.isoformat(), "human_verified_by": "Researcher",
                "human_verified_at": _common.utc_now(), "notes": "",
            },
        )
        cls.write_json(
            target / "publication/selected-journal.json",
            {
                "journal": "Example Journal", "fit_rationale": "Strong scope and methods fit", "selected_at": _common.utc_now(),
                "q1_claim": "verified", "provider": "JCR", "metric_year": str(today.year - 1),
                "category": "Computer Science, Artificial Intelligence", "evidence_sha256": cls.digest(evidence),
            },
        )
        (target / "publication/submission-checklist.md").write_text(
            "# Submission checklist\n\nCurrent instructions, exact payload, disclosures, author approval, and destination were checked.\n",
            encoding="utf-8",
        )
        decision_evidence = target / "publication/decision-letter.txt"
        decision_evidence.write_text("Editorial decision: accepted\n", encoding="utf-8")
        cls.write_json(
            target / "publication/decision.json",
            {
                "status": "accepted", "venue": "Example Journal", "decided_at": _common.utc_now(),
                "evidence_path": "publication/decision-letter.txt", "evidence_sha256": cls.digest(decision_evidence),
            },
        )
        cls.append_row(
            target / "publication/release-manifest.csv",
            {
                "artifact": "manuscript", "path": "manuscript/main.tex", "sha256": cls.digest(target / "manuscript/main.tex"),
                "public_url": "https://example.org/archive", "license": "CC-BY-4.0", "archived_at": _common.utc_now(), "notes": "",
            },
        )
        (target / "publication/correction-plan.md").write_text(
            "# Correction plan\n\nThe corresponding author monitors corrections and will update archived artifacts and notify the journal.\n",
            encoding="utf-8",
        )
        cls.set_state(
            target,
            "archived",
            ["question", "protocol", "pilot", "execution", "analysis", "manuscript", "internal-review", "journal-selection", "submission-package", "revision", "accepted", "archived"],
        )


class ProjectTests(WorkspaceMixin, unittest.TestCase):
    MODE_COUNTS = {"full-research-lifecycle": 30, "systematic-search": 14, "peer-review": 8, "scientific-prose": 6}

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

    def test_old_schema_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "project"
            init_project.create_project(target, "Example", "peer-review")
            project = json.loads((target / "project.json").read_text())
            project["schema_version"] = 2
            self.write_json(target / "project.json", project)
            self.assertFalse(audit_project.audit(target)["passed"])

    def test_duplicate_and_future_gates_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "project"
            init_project.create_project(target, "Example", "peer-review")
            self.set_state(target, "intake", ["review", "review"])
            result = audit_project.audit(target)
            self.assertFalse(result["passed"])
            self.assertTrue(any("duplicate" in item or "future" in item for item in result["errors"]))

    def test_full_manuscript_evidence_chain_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "project"
            self.complete_full_to_manuscript(target)
            self.assertTrue(audit_project.audit(target)["passed"], audit_project.audit(target))

    def test_blank_run_record_cannot_satisfy_execution(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "project"
            init_project.create_project(target, "Example", "full-research-lifecycle")
            with (target / "study/runs.csv").open("a", encoding="utf-8") as handle:
                handle.write(",,,,,,,,,,,,,,,,,,\n")
            result = audit_project.audit(target)
            self.assertFalse(result["passed"])
            self.assertTrue(any("blank CSV record" in item for item in result["errors"]))

    def test_pilot_requires_hash_bound_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "project"
            init_project.create_project(target, "Example", "full-research-lifecycle")
            (target / "governance/charter.md").write_text("complete", encoding="utf-8")
            (target / "protocol/protocol.md").write_text("complete", encoding="utf-8")
            self.write_json(target / "study/pilot-decision.json", {"decision": "go", "decided_at": _common.utc_now(), "protocol_effect": "none", "evidence": []})
            self.set_state(target, "pilot", ["question", "protocol", "pilot"])
            self.assertFalse(audit_project.audit(target)["passed"])

    def test_pilot_stop_blocks_execution(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "project"
            self.complete_full_to_manuscript(target)
            decision = json.loads((target / "study/pilot-decision.json").read_text())
            decision["decision"] = "stop"
            self.write_json(target / "study/pilot-decision.json", decision)
            self.assertFalse(audit_project.audit(target)["passed"])

    def test_unknown_or_ineligible_claim_source_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "project"
            init_project.create_project(target, "Example", "full-research-lifecycle")
            self.append_row(target / "claims/claims.csv", {"claim_id": "C0001", "text": "Claim", "claim_type": "background", "source_ids": "S9999", "status": "active", "limitations": "None"})
            self.assertFalse(audit_project.audit(target)["passed"])

            target2 = Path(temporary) / "project2"
            init_project.create_project(target2, "Example", "full-research-lifecycle")
            self.append_row(target2 / "evidence/sources.csv", {"source_id": "S0001", "title": "Paper", "status": "candidate", "evidence_level": "abstract"})
            self.append_row(target2 / "claims/claims.csv", {"claim_id": "C0001", "text": "Claim", "claim_type": "background", "source_ids": "S0001", "status": "active", "limitations": "None"})
            self.assertFalse(audit_project.audit(target2)["passed"])

    def test_invalid_source_status_cannot_bypass_retraction_controls(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "project"
            init_project.create_project(target, "Example", "full-research-lifecycle")
            self.append_row(target / "evidence/sources.csv", {"source_id": "S0001", "title": "Paper", "status": "retractd", "evidence_level": "full-text"})
            self.assertFalse(audit_project.audit(target)["passed"])

    def test_retracted_source_cannot_silently_support_active_claim(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "project"
            init_project.create_project(target, "Example", "full-research-lifecycle")
            record = target / "evidence/retraction.txt"
            record.write_text("Retraction notice", encoding="utf-8")
            self.append_row(target / "evidence/sources.csv", {"source_id": "S0001", "title": "Paper", "status": "retracted", "evidence_level": "full-text", "record_path": "evidence/retraction.txt", "record_sha256": self.digest(record), "verified_at": _common.utc_now(), "notes": "Retraction notice"})
            self.append_row(target / "claims/claims.csv", {"claim_id": "C0001", "text": "The method improves accuracy", "claim_type": "empirical", "source_ids": "S0001", "status": "active", "limitations": "None"})
            self.assertFalse(audit_project.audit(target)["passed"])

    def test_retraction_fact_can_reference_retracted_record(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "project"
            init_project.create_project(target, "Example", "full-research-lifecycle")
            record = target / "evidence/retraction.txt"
            record.write_text("Retraction notice", encoding="utf-8")
            self.append_row(target / "evidence/sources.csv", {"source_id": "S0001", "title": "Paper", "status": "retracted", "evidence_level": "full-text", "record_path": "evidence/retraction.txt", "record_sha256": self.digest(record), "verified_at": _common.utc_now(), "notes": "Retraction notice"})
            self.append_row(target / "claims/claims.csv", {"claim_id": "C0001", "text": "The source was retracted", "claim_type": "retraction", "source_ids": "S0001", "status": "active", "limitations": "Retraction fact"})
            self.assertTrue(audit_project.audit(target)["passed"], audit_project.audit(target))

    def test_archive_requires_hash_bound_decision_and_release(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "project"
            self.complete_full_to_archive(target)
            result = audit_project.audit(target)
            self.assertTrue(result["passed"], result)
            (target / "publication/decision-letter.txt").write_text("mutated", encoding="utf-8")
            self.assertFalse(audit_project.audit(target)["passed"])

    def test_no_material_findings_is_valid_but_empty_review_is_not(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "project"
            init_project.create_project(target, "Example", "peer-review")
            (target / "governance/charter.md").write_text("complete", encoding="utf-8")
            (target / "review/review.md").write_text("No material findings.\n", encoding="utf-8")
            self.write_json(target / "review/summary.json", {"scope": "paper", "recommendation": "minor revision", "confidence": "medium", "limitations": "none"})
            self.set_state(target, "final", ["review", "final"])
            self.assertTrue(audit_project.audit(target)["passed"], audit_project.audit(target))
            (target / "review/review.md").write_text("Generic review.\n", encoding="utf-8")
            self.assertFalse(audit_project.audit(target)["passed"])

    def test_invalid_finding_severity_cannot_close_review(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "project"
            init_project.create_project(target, "Example", "peer-review")
            self.append_row(target / "review/findings.csv", {"finding_id": "F0001", "severity": "majro", "confidence": "high", "location": "Methods", "finding": "Missing control", "evidence": "Section 3", "consequence": "Invalid inference", "action": "Add control", "status": "addressed"})
            self.assertFalse(audit_project.audit(target)["passed"])

    def test_open_major_finding_blocks_final(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "project"
            init_project.create_project(target, "Example", "peer-review")
            (target / "governance/charter.md").write_text("complete", encoding="utf-8")
            (target / "review/review.md").write_text("Major finding documented.\n", encoding="utf-8")
            self.write_json(target / "review/summary.json", {"scope": "paper", "recommendation": "major revision", "confidence": "high", "limitations": "none"})
            self.append_row(target / "review/findings.csv", {"finding_id": "F0001", "severity": "major", "confidence": "high", "location": "Methods", "finding": "Missing control", "evidence": "Section 3", "consequence": "Invalid inference", "action": "Add control", "status": "open"})
            self.set_state(target, "final", ["review", "final"])
            self.assertFalse(audit_project.audit(target)["passed"])

    def test_systematic_search_reconciles_screening_extraction_and_flow(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "project"
            init_project.create_project(target, "Example", "systematic-search")
            (target / "governance/charter.md").write_text("complete charter", encoding="utf-8")
            (target / "protocol/search-protocol.md").write_text("complete protocol", encoding="utf-8")
            source_record = target / "evidence/source.txt"
            export = target / "evidence/export.json"
            source_record.write_text("canonical record", encoding="utf-8")
            export.write_text('[{"id":"S0001"}]\n', encoding="utf-8")
            self.append_row(target / "evidence/sources.csv", {"source_id": "S0001", "title": "Paper", "status": "verified", "evidence_level": "full-text", "record_path": "evidence/source.txt", "record_sha256": self.digest(source_record), "verified_at": _common.utc_now()})
            self.append_row(target / "evidence/search-log.csv", {"search_id": "Q0001", "source": "DBLP", "interface": "API", "query": "test", "executed_at": _common.utc_now(), "result_count": "1", "export_path": "evidence/export.json", "export_sha256": self.digest(export)})
            self.append_row(target / "evidence/screening.csv", {"record_id": "rec-1", "source_ids": "S0001", "title": "Paper", "stage": "full-text", "decision": "include", "reviewer": "Researcher"})
            self.append_row(target / "evidence/extraction.csv", {"record_id": "rec-1", "source_ids": "S0001", "study_family": "experiment", "context": "CS", "method": "method", "data": "data", "comparators": "baseline", "outcomes": "outcome", "limitations": "limitation", "evidence_access": "full-text-reviewed"})
            self.write_json(target / "evidence/flow.json", {"identified": 1, "deduplicated": 1, "screened": 1, "full_text_assessed": 1, "included": 1})
            (target / "evidence/synthesis.md").write_text("Evidence synthesis and limitations.", encoding="utf-8")
            (target / "evidence/search-audit.md").write_text("Search audit passed with stated limitations.", encoding="utf-8")
            self.append_row(target / "claims/claims.csv", {"claim_id": "C0001", "text": "The included paper reports an outcome.", "claim_type": "synthesis", "source_ids": "S0001", "status": "active", "limitations": "One study"})
            self.set_state(target, "internal-review", ["protocol", "search", "screening", "extraction", "synthesis", "internal-review"])
            self.assertTrue(audit_project.audit(target)["passed"], audit_project.audit(target))
            flow = json.loads((target / "evidence/flow.json").read_text())
            flow["included"] = 2
            self.write_json(target / "evidence/flow.json", flow)
            self.assertFalse(audit_project.audit(target)["passed"])

    def test_scientific_prose_final_runs_strict_drift_audit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "project"
            init_project.create_project(target, "Example", "scientific-prose")
            (target / "governance/charter.md").write_text("complete", encoding="utf-8")
            (target / "manuscript/protected-spans.txt").write_text("Numbers and direction terms", encoding="utf-8")
            (target / "manuscript/residual-concerns.md").write_text("None", encoding="utf-8")
            source = target / "manuscript/original.txt"
            revised = target / "manuscript/revised.txt"
            source.write_text("Accuracy increased to 83.0%.", encoding="utf-8")
            revised.write_text("Accuracy rose to 83.0%.", encoding="utf-8")
            self.append_row(target / "manuscript/revision-log.csv", {"revision_id": "V0001", "source_path": "manuscript/original.txt", "source_sha256": self.digest(source), "revised_path": "manuscript/revised.txt", "revised_sha256": self.digest(revised), "scope": "line edit", "protected_content": "numbers and direction", "material_changes": "clarity only", "residual_concerns": "None", "audit_status": "pass", "status": "complete"})
            self.set_state(target, "final", ["revision", "final"])
            self.assertTrue(audit_project.audit(target)["passed"], audit_project.audit(target))
            revised.write_text("Accuracy fell to 83.0%.", encoding="utf-8")
            row_path = target / "manuscript/revision-log.csv"
            text = row_path.read_text(encoding="utf-8").replace(self.digest(source), self.digest(source), 1)
            # Replace only the revised hash in the final occurrence.
            fields = list(csv.DictReader(text.splitlines()))[0]
            fields["revised_sha256"] = self.digest(revised)
            with row_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(fields))
                writer.writeheader(); writer.writerow(fields)
            self.assertFalse(audit_project.audit(target)["passed"])

    def test_external_action_hash_expiry_and_order_are_enforced(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "project"
            init_project.create_project(target, "Example", "peer-review")
            payload = target / "governance/charter.md"
            action = {
                "action_id": "A0001", "action": "submit", "status": "performed", "destination": "journal portal",
                "authorized_at": "2026-08-30T10:00:00+00:00", "expires_at": "2026-08-30T11:00:00+00:00",
                "authorized_by": "Author", "authorization_statement": "Submit exactly these bytes",
                "performed_at": "2026-08-30T10:05:00+00:00", "outcome": "submitted",
                "payload": [{"path": "governance/charter.md", "sha256": self.digest(payload)}],
            }
            self.set_state(target, "intake", [], [action])
            self.assertTrue(audit_project.audit(target)["passed"], audit_project.audit(target))
            action["performed_at"] = "2026-08-30T12:00:00+00:00"
            self.set_state(target, "intake", [], [action])
            self.assertFalse(audit_project.audit(target)["passed"])

    @unittest.skipIf(not hasattr(os, "symlink"), "symlinks unavailable")
    def test_workspace_symlink_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "project"
            init_project.create_project(target, "Example", "peer-review")
            external = Path(temporary) / "external.txt"; external.write_text("x", encoding="utf-8")
            os.symlink(external, target / "linked.txt")
            self.assertFalse(audit_project.audit(target)["passed"])

    @unittest.skipIf(not hasattr(os, "link"), "hardlinks unavailable")
    def test_workspace_hardlink_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "project"
            init_project.create_project(target, "Example", "peer-review")
            external = Path(temporary) / "external.txt"; external.write_text("x", encoding="utf-8")
            os.link(external, target / "hard.txt")
            self.assertFalse(audit_project.audit(target)["passed"])

    @unittest.skipIf(not hasattr(os, "mkfifo"), "FIFO unavailable")
    def test_workspace_special_file_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "project"
            init_project.create_project(target, "Example", "peer-review")
            os.mkfifo(target / "pipe")
            self.assertFalse(audit_project.audit(target)["passed"])


class CommonParserTests(unittest.TestCase):
    def test_duplicate_json_key_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "x.json"; path.write_text('{"a": 1, "a": 2}', encoding="utf-8")
            with self.assertRaises(_common.ValidationError): _common.load_json(path)

    def test_nonfinite_json_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "x.json"; path.write_text('{"a": NaN}', encoding="utf-8")
            with self.assertRaises(_common.ValidationError): _common.load_json(path)

    def test_extra_csv_field_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "x.csv"; path.write_text("a,b\n1,2,3\n", encoding="utf-8")
            with self.assertRaises(_common.ValidationError): _common.read_csv(path)

    def test_duplicate_csv_header_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "x.csv"; path.write_text("a,a\n1,2\n", encoding="utf-8")
            with self.assertRaises(_common.ValidationError): _common.read_csv(path)

    def test_blank_comma_row_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "x.csv"; path.write_text("a,b\n,\n", encoding="utf-8")
            with self.assertRaises(_common.ValidationError): _common.read_csv(path)

    def test_naive_timestamp_is_rejected(self) -> None:
        with self.assertRaises(_common.ValidationError): _common.parse_timestamp("2026-08-30T10:00:00")

    def test_project_path_rejects_backslash_and_parent_escape(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaises(_common.ValidationError): _common.project_path(root, "../x")
            with self.assertRaises(_common.ValidationError): _common.project_path(root, "a\\b")


class LatexTests(unittest.TestCase):
    def make_tree(self, root: Path, tex: str, bib: str = "@article{key, title={T}}\n") -> None:
        root.mkdir(); (root / "main.tex").write_text(tex, encoding="utf-8"); (root / "refs.bib").write_text(bib, encoding="utf-8")

    def test_valid_latex(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "m"
            self.make_tree(root, r"\documentclass{article}\begin{document}\section{A}\label{sec:a}See \ref{sec:a} and \cite{key}.\bibliography{refs}\end{document}")
            self.assertTrue(audit_latex.audit(root, Path("main.tex"))["passed"])

    def test_optional_argument_and_nocite_wildcard(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "m"
            self.make_tree(root, r"\documentclass{article}\begin{document}\parencite[see][p.~3]{key}\nocite{*}\bibliography{refs}\end{document}")
            self.assertTrue(audit_latex.audit(root, Path("main.tex"))["passed"])

    def test_missing_citation_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "m"; self.make_tree(root, r"\documentclass{article}\begin{document}\cite{missing}\bibliography{refs}\end{document}")
            self.assertFalse(audit_latex.audit(root, Path("main.tex"))["passed"])

    def test_comment_entry_cannot_spoof_citation_key(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "m"; self.make_tree(root, r"\documentclass{article}\begin{document}\cite{fake}\bibliography{refs}\end{document}", "@comment{fake, not a real entry}\n")
            self.assertFalse(audit_latex.audit(root, Path("main.tex"))["passed"])

    def test_embedded_at_entry_text_cannot_spoof_key(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "m"; self.make_tree(root, r"\documentclass{article}\begin{document}\cite{fake}\bibliography{refs}\end{document}", '@article{real, title={Text @article{fake, title={X}}}}\n')
            self.assertFalse(audit_latex.audit(root, Path("main.tex"))["passed"])

    def test_duplicate_key_across_bibliographies_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "m"; self.make_tree(root, r"\documentclass{article}\begin{document}\cite{key}\bibliography{refs,more}\end{document}")
            (root / "more.bib").write_text("@book{key, title={B}}\n", encoding="utf-8")
            self.assertFalse(audit_latex.audit(root, Path("main.tex"))["passed"])

    def test_imported_unsafe_command_is_scanned(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "m"; self.make_tree(root, r"\documentclass{article}\begin{document}\import{parts/}{section}\end{document}")
            (root / "parts").mkdir(); (root / "parts/section.tex").write_text(r"\write18{whoami}", encoding="utf-8")
            self.assertFalse(audit_latex.audit(root, Path("main.tex"))["passed"])

    def test_import_path_escape_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary); root = base / "m"; self.make_tree(root, r"\documentclass{article}\begin{document}\import{../}{outside}\end{document}")
            (base / "outside.tex").write_text("secret", encoding="utf-8")
            self.assertFalse(audit_latex.audit(root, Path("main.tex"))["passed"])

    def test_high_risk_package_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "m"; self.make_tree(root, r"\documentclass{article}\usepackage{minted}\begin{document}x\end{document}")
            self.assertFalse(audit_latex.audit(root, Path("main.tex"))["passed"])

    def test_unsafe_shell_escape_and_direct_lua_are_rejected(self) -> None:
        for command in (r"\immediate\write18{whoami}", r"\directlua{os.execute('whoami')}"):
            with self.subTest(command=command), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary) / "m"; self.make_tree(root, rf"\documentclass{{article}}\begin{{document}}{command}\end{{document}}")
                self.assertFalse(audit_latex.audit(root, Path("main.tex"))["passed"])

    def test_unsafe_command_in_comment_and_verbatim_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "m"
            self.make_tree(root, "% \\write18{whoami}\n\\documentclass{article}\\begin{document}\\begin{verbatim}\\write18{x}\\end{verbatim}Safe\\end{document}")
            self.assertTrue(audit_latex.audit(root, Path("main.tex"))["passed"])

    def test_duplicate_and_empty_labels_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "m"; self.make_tree(root, r"\documentclass{article}\begin{document}\label{x}\label{x}\label{}\end{document}")
            self.assertFalse(audit_latex.audit(root, Path("main.tex"))["passed"])

    def test_placeholder_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "m"; self.make_tree(root, r"\documentclass{article}\begin{document}TODO: text\end{document}")
            self.assertFalse(audit_latex.audit(root, Path("main.tex"))["passed"])

    def test_compiler_log_must_remain_under_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary); root = base / "m"; self.make_tree(root, r"\documentclass{article}\begin{document}x\end{document}")
            outside = base / "outside.log"; outside.write_text("clean", encoding="utf-8")
            self.assertFalse(audit_latex.audit(root, Path("main.tex"), compiler_log=outside)["passed"])

    @unittest.skipIf(not hasattr(os, "mkfifo"), "FIFO unavailable")
    def test_special_file_in_manuscript_tree_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "m"; self.make_tree(root, r"\documentclass{article}\begin{document}x\end{document}")
            os.mkfifo(root / "pipe")
            self.assertFalse(audit_latex.audit(root, Path("main.tex"))["passed"])


class ProseTests(unittest.TestCase):
    def run_audit(self, original: str, revised: str, strict: bool = False) -> dict[str, object]:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); a = root / "a.txt"; b = root / "b.txt"
            a.write_text(original, encoding="utf-8"); b.write_text(revised, encoding="utf-8")
            return audit_prose.audit(a, b, strict=strict)

    def test_identical_protected_content_passes(self) -> None:
        self.assertTrue(self.run_audit("We observed 12.5% in \\cite{a}. $x=1$", "In \\cite{a}, we observed 12.5%. $x=1$")["passed"])

    def test_direction_synonym_passes_but_reversal_fails(self) -> None:
        self.assertTrue(self.run_audit("Accuracy increased.", "Accuracy rose.")["passed"])
        self.assertFalse(self.run_audit("Accuracy increased.", "Accuracy decreased.")["passed"])
        self.assertFalse(self.run_audit("The result was higher.", "The result was lower.")["passed"])

    def test_support_to_contradiction_fails(self) -> None:
        self.assertFalse(self.run_audit("The result supports the hypothesis.", "The result contradicts the hypothesis.")["passed"])

    def test_temporal_reversal_fails(self) -> None:
        self.assertFalse(self.run_audit("Measurement occurred before training.", "Measurement occurred after training.")["passed"])

    def test_leading_decimal_unicode_minus_and_operator_changes_fail(self) -> None:
        self.assertFalse(self.run_audit("p < .05", "p < .01")["passed"])
        self.assertFalse(self.run_audit("The estimate was −1.2.", "The estimate was 1.2.")["passed"])
        self.assertFalse(self.run_audit("p < .05", "p > .05")["passed"])

    def test_number_citation_math_code_and_xref_changes_fail(self) -> None:
        cases = [
            ("n=20", "n=21"),
            (r"Evidence \cite{a}", r"Evidence \cite{b}"),
            (r"See \ref{x}.", r"See \label{x}."),
            ("$x=1$", "$x=2$"),
            ("Use `alpha=1`.", "Use `alpha=2`."),
        ]
        for original, revised in cases:
            with self.subTest(original=original): self.assertFalse(self.run_audit(original, revised)["passed"])

    def test_citation_optional_scope_change_fails(self) -> None:
        self.assertFalse(self.run_audit(r"Evidence \parencite[p.~3]{a}", r"Evidence \parencite[p.~30]{a}")["passed"])

    def test_citation_paragraph_move_warns_and_fails_strict(self) -> None:
        original = "Claim A \\cite{x}.\n\nClaim B."
        revised = "Claim A.\n\nClaim B \\cite{x}."
        self.assertTrue(self.run_audit(original, revised)["passed"])
        self.assertTrue(self.run_audit(original, revised)["warnings"])
        self.assertFalse(self.run_audit(original, revised, strict=True)["passed"])

    def test_conditional_scope_change_fails_strict(self) -> None:
        self.assertFalse(self.run_audit("The method works if data are clean.", "The method works when data are clean.", strict=True)["passed"])

    def test_uncertainty_causal_and_negation_strengthening_fail_strict(self) -> None:
        self.assertFalse(self.run_audit("The method may improve accuracy.", "The method improves accuracy.", strict=True)["passed"])
        self.assertFalse(self.run_audit("X is associated with Y.", "X causes Y.", strict=True)["passed"])
        self.assertFalse(self.run_audit("The effect was not significant.", "The effect was significant.", strict=True)["passed"])

    def test_doi_url_sentence_punctuation_is_normalized(self) -> None:
        self.assertTrue(self.run_audit("See doi:10.1000/example.", "See doi:10.1000/example;")["passed"])
        self.assertTrue(self.run_audit("See https://example.org/a.", "See https://example.org/a;")["passed"])


class JournalTests(WorkspaceMixin, unittest.TestCase):
    FIELDS = [
        "journal", "issn", *score_journals.FIT_FIELDS, "provider", "metric_name", "metric_year", "category",
        "quartile", "rank", "denominator", "verification_url", "evidence_path", "evidence_sha256",
        "verified_date", "human_verified_by", "human_verified_at", "notes",
    ]

    def write_rows(self, root: Path, rows: list[dict[str, str]]) -> Path:
        path = root / "journals.csv"
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=self.FIELDS); writer.writeheader(); writer.writerows(rows)
        return path

    def valid_row(self, root: Path, *, journal: str = "Example Journal", fit: str = "5") -> dict[str, str]:
        evidence = root / f"{journal.replace(' ', '-')}.txt"; evidence.write_text(f"{journal}; Q1 evidence\n", encoding="utf-8")
        today = date.today()
        return {
            "journal": journal, "issn": "1234-567X", "scope_fit": fit, "methods_fit": fit, "audience_fit": fit,
            "article_fit": fit, "open_science_fit": fit, "provider": "JCR", "metric_name": "JIF quartile",
            "metric_year": str(today.year - 1), "category": "Computer Science, Artificial Intelligence",
            "quartile": "Q1", "rank": "10", "denominator": "100",
            "verification_url": "https://jcr.clarivate.com/jcr-jp/journal-profile?journal=example",
            "evidence_path": evidence.name, "evidence_sha256": self.digest(evidence), "verified_date": today.isoformat(),
            "human_verified_by": "Researcher", "human_verified_at": _common.utc_now(), "notes": "",
        }

    def test_valid_hash_bound_q1_record(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); result = score_journals.score(self.write_rows(root, [self.valid_row(root)]))
            self.assertTrue(result["journals"][0]["q1_verified"], result)
            self.assertIn("not cryptographically", result["journals"][0]["verification_scope"])

    def test_missing_category_human_or_evidence_is_not_verified(self) -> None:
        for field in ("category", "human_verified_by", "evidence_sha256"):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary); row = self.valid_row(root); row[field] = ""
                result = score_journals.score(self.write_rows(root, [row]))
                self.assertFalse(result["journals"][0]["q1_verified"])

    def test_evidence_mutation_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); row = self.valid_row(root); path = self.write_rows(root, [row])
            (root / row["evidence_path"]).write_text("mutated", encoding="utf-8")
            self.assertFalse(score_journals.score(path)["journals"][0]["q1_verified"])

    def test_untrusted_or_bare_provider_url_is_not_verified(self) -> None:
        for url in ("https://example.com/q1", "https://jcr.clarivate.com/"):
            with self.subTest(url=url), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary); row = self.valid_row(root); row["verification_url"] = url
                self.assertFalse(score_journals.score(self.write_rows(root, [row]))["journals"][0]["q1_verified"])

    def test_provider_domain_mismatch_is_not_verified(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); row = self.valid_row(root); row["verification_url"] = "https://www.scimagojr.com/journalsearch.php?q=x"
            self.assertFalse(score_journals.score(self.write_rows(root, [row]))["journals"][0]["q1_verified"])

    def test_stale_verification_and_metric_are_not_verified(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); row = self.valid_row(root); row["verified_date"] = (date.today() - timedelta(days=500)).isoformat()
            self.assertFalse(score_journals.score(self.write_rows(root, [row]), max_verification_age=400)["journals"][0]["q1_verified"])
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); row = self.valid_row(root); row["metric_year"] = str(date.today().year - 3)
            self.assertFalse(score_journals.score(self.write_rows(root, [row]), max_metric_lag=2)["journals"][0]["q1_verified"])

    def test_duplicate_identity_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); row = self.valid_row(root)
            result = score_journals.score(self.write_rows(root, [row, dict(row)]))
            self.assertFalse(result["passed"])

    def test_fit_ranking_is_independent_of_q1_and_filter_is_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); high = self.valid_row(root, journal="High Fit", fit="5"); high["quartile"] = "Q2"
            low = self.valid_row(root, journal="Low Fit Q1", fit="1")
            path = self.write_rows(root, [low, high]); result = score_journals.score(path)
            self.assertEqual(result["journals"][0]["journal"], "High Fit")
            filtered = score_journals.score(path, verified_q1_only=True)
            self.assertEqual([item["journal"] for item in filtered["journals"]], ["Low Fit Q1"])

    def test_invalid_url_port_does_not_crash(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); row = self.valid_row(root); row["verification_url"] = "https://jcr.clarivate.com:bad/x"
            result = score_journals.score(self.write_rows(root, [row]))
            self.assertFalse(result["journals"][0]["q1_verified"])


class SkillStructureTests(unittest.TestCase):
    def test_skill_is_concise_and_links_resources(self) -> None:
        skill = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        self.assertLessEqual(len(skill.splitlines()), 500)
        for path in (SKILL_DIR / "references").glob("*.md"): self.assertIn(f"references/{path.name}", skill)
        for path in (SKILL_DIR / "scripts").glob("*.py"):
            if path.name.startswith("_") or path.name == "self_test.py": continue
            self.assertIn(f"scripts/{path.name}", skill)

    def test_trigger_description_covers_integrated_modes(self) -> None:
        frontmatter = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8").split("---", 2)[1].lower()
        for phrase in ("systematic", "peer review", "scientific-prose", "q1"): self.assertIn(phrase, frontmatter)

    def test_no_third_party_imports_or_network_clients(self) -> None:
        allowed = set(sys.stdlib_module_names) | {"_common", "audit_latex", "audit_project", "audit_prose", "init_project", "score_journals"}
        import_pattern = re.compile(r"^(?:from|import)\s+([A-Za-z_][A-Za-z0-9_]*)", re.MULTILINE)
        forbidden = re.compile(r"\b(?:urllib\.request|http\.client|socket|ftplib|smtplib|imaplib|poplib|telnetlib|subprocess|os\.system|os\.popen|eval\s*\(|exec\s*\()")
        for path in SCRIPT_DIR.glob("*.py"):
            text = path.read_text(encoding="utf-8")
            for module in import_pattern.findall(text): self.assertIn(module, allowed, f"third-party import {module} in {path.name}")
            if path.name != "self_test.py": self.assertIsNone(forbidden.search(text), f"forbidden capability in {path.name}")


def main() -> int:
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    summary = {"tests_run": result.testsRun, "failures": len(result.failures), "errors": len(result.errors), "skipped": len(result.skipped), "successful": result.wasSuccessful()}
    print(json.dumps(summary, sort_keys=True))
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
