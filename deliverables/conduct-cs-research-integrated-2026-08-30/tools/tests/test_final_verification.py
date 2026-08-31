#!/usr/bin/env python3
"""Regression cases added by the final independent verification pass."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

DELIVERABLE = Path(__file__).resolve().parents[2]
SKILL = Path(os.environ.get("SKILL_UNDER_TEST", DELIVERABLE / "conduct-cs-research")).resolve()
SCRIPTS = SKILL / "scripts"
sys.path.insert(0, str(SCRIPTS))

import _common
import audit_project
import audit_prose
import init_project
from test_core import Helpers


class SearchLedgerRegressionTests(unittest.TestCase):
    def test_screening_rows_are_order_independent(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "p"
            Helpers.systematic_synthesis(root)
            path = root / "evidence/screening.csv"
            with path.open("r", encoding="utf-8", newline="") as handle:
                rows = list(csv.reader(handle))
            path.write_text(
                "\n".join(",".join(row) for row in [rows[0], *reversed(rows[1:])]) + "\n",
                encoding="utf-8",
            )
            self.assertTrue(audit_project.audit(root)["passed"])

    def test_screening_source_identity_cannot_change_between_stages(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "p"
            Helpers.systematic_synthesis(root)
            second = root / "evidence/source-record-2.txt"
            second.write_text("second canonical record\n", encoding="utf-8")
            Helpers.append(
                root / "evidence/sources.csv",
                {
                    "source_id": "S0002",
                    "title": "Second Paper",
                    "status": "verified",
                    "evidence_level": "full-text",
                    "record_path": "evidence/source-record-2.txt",
                    "record_sha256": Helpers.digest(second),
                    "verified_at": _common.utc_now(),
                },
            )
            path = root / "evidence/screening.csv"
            rows = list(csv.DictReader(path.open(encoding="utf-8", newline="")))
            rows[1]["source_ids"] = "S0002"
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
            result = audit_project.audit(root)
            self.assertFalse(result["passed"])
            self.assertTrue(any("changes source_ids" in item for item in result["errors"]))

    def test_included_but_unverified_source_cannot_support_active_claim(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "p"
            Helpers.systematic_synthesis(root)
            path = root / "evidence/sources.csv"
            rows = list(csv.DictReader(path.open(encoding="utf-8", newline="")))
            rows[0].update(
                {
                    "status": "included",
                    "record_path": "",
                    "record_sha256": "",
                    "verified_at": "",
                }
            )
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
            result = audit_project.audit(root)
            self.assertFalse(result["passed"])
            self.assertTrue(any("ineligible source" in item for item in result["errors"]))

    def test_final_search_review_rejects_needs_review_claim(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "p"
            Helpers.systematic_synthesis(root)
            claims_path = root / "claims/claims.csv"
            rows = list(csv.DictReader(claims_path.open(encoding="utf-8", newline="")))
            rows[0]["status"] = "needs-review"
            with claims_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
            (root / "evidence/search-audit.md").write_text(
                "# Search audit\n\nProtocol adherence and limitations were assessed.\n",
                encoding="utf-8",
            )
            Helpers.state(root, "internal-review")
            result = audit_project.audit(root)
            self.assertFalse(result["passed"])
            self.assertTrue(any("needs-review" in item for item in result["errors"]))


class ProseRegressionTests(unittest.TestCase):
    def test_local_direction_swap_fails_with_unchanged_global_counts(self) -> None:
        original = "Method A increased accuracy.\n\nMethod B decreased latency."
        revised = "Method A decreased accuracy.\n\nMethod B increased latency."
        result = audit_prose.audit_text(original, revised, strict=True)
        self.assertFalse(result["passed"])
        self.assertTrue(any("ordered semantic-event" in item for item in result["errors"]))

    def test_declared_protected_span_is_enforced_in_governed_project(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "p"
            init_project.create_project(root, "Prose", "scientific-prose")
            (root / "governance/charter.md").write_text(
                "# Charter\n\nScope, audience, confidentiality, and authorization are fixed.\n",
                encoding="utf-8",
            )
            original = root / "manuscript/original.txt"
            revised = root / "manuscript/revised.txt"
            original.write_text("The Alpha protocol was used.\n", encoding="utf-8")
            revised.write_text("The Beta protocol was used.\n", encoding="utf-8")
            (root / "manuscript/protected-spans.txt").write_text(
                "# Exact literals\nAlpha protocol\n", encoding="utf-8"
            )
            Helpers.append(
                root / "manuscript/revision-log.csv",
                {
                    "revision_id": "V0001",
                    "source_path": "manuscript/original.txt",
                    "source_sha256": Helpers.digest(original),
                    "revised_path": "manuscript/revised.txt",
                    "revised_sha256": Helpers.digest(revised),
                    "scope": "copyedit",
                    "protected_content": "Alpha protocol",
                    "material_changes": "none",
                    "residual_concerns": "none",
                    "audit_status": "pass",
                    "status": "complete",
                },
            )
            Helpers.state(root, "revision")
            result = audit_project.audit(root)
            self.assertFalse(result["passed"])
            self.assertTrue(any("protected span" in item for item in result["errors"]))


class SecurePathRegressionTests(unittest.TestCase):
    @unittest.skipUnless(hasattr(os, "symlink"), "symlink unavailable")
    def test_project_hash_rejects_intermediate_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            real = root / "real"
            real.mkdir()
            payload = real / "payload.txt"
            payload.write_text("secret\n", encoding="utf-8")
            (root / "linked").symlink_to(real, target_is_directory=True)
            with self.assertRaises(_common.ValidationError):
                _common.sha256_project_file(root, "linked/payload.txt")

    def test_project_paths_reject_portability_aliases(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for raw in ("name. ", "NUL.txt", "a:b.txt"):
                with self.subTest(raw=raw):
                    with self.assertRaises(_common.ValidationError):
                        _common.project_path(root, raw, must_exist=False)


if __name__ == "__main__":
    unittest.main()
