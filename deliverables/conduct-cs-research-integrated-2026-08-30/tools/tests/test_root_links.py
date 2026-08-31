#!/usr/bin/env python3
"""Security regression tests for linked audit roots."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

DELIVERABLE = Path(__file__).resolve().parents[2]
SKILL = Path(os.environ.get("SKILL_UNDER_TEST", DELIVERABLE / "conduct-cs-research")).resolve()
sys.path.insert(0, str(SKILL / "scripts"))

import audit_latex
import audit_project
import init_project


@unittest.skipUnless(hasattr(os, "symlink"), "symlink unavailable")
class LinkedRootTests(unittest.TestCase):
    def test_project_root_symlink_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            parent = Path(td)
            real = parent / "real"
            init_project.create_project(real, "linked", "peer-review")
            link = parent / "link"
            link.symlink_to(real, target_is_directory=True)
            result = audit_project.audit(link)
            self.assertFalse(result["passed"])
            self.assertTrue(any("linked" in item.lower() for item in result["errors"]))

    def test_latex_root_symlink_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            parent = Path(td)
            real = parent / "real"
            real.mkdir()
            (real / "main.tex").write_text("\\documentclass{article}\n", encoding="utf-8")
            link = parent / "link"
            link.symlink_to(real, target_is_directory=True)
            result = audit_latex.audit(link, Path("main.tex"))
            self.assertFalse(result["passed"])
            self.assertTrue(any("linked" in item.lower() for item in result["errors"]))


if __name__ == "__main__":
    unittest.main()
