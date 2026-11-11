from __future__ import annotations

import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "skill-authoring" / "scripts" / "scaffold_skill.py"
sys.path.insert(0, str(ROOT / "skills" / "skill-authoring" / "scripts"))
sys.path.insert(0, str(ROOT / "skills" / "skill-audit" / "scripts"))

import audit_skill
import scaffold_skill


class ScaffoldSkillTest(unittest.TestCase):
    def test_creates_a_valid_skill(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp) / "skills"
            path = scaffold_skill.scaffold(
                "demo-skill",
                "Create demo artifacts for tests. Use when the suite needs a fixture.",
                root,
            )
            self.assertTrue(path.exists())
            report = audit_skill.audit_skill(path.parent)
            self.assertTrue(report.valid, report.findings)
            text = path.read_text(encoding="utf-8")
            self.assertIn("name: demo-skill", text)
            self.assertIn("# Demo Skill", text)

    def test_writes_lf_line_endings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = scaffold_skill.scaffold(
                "demo-skill", "Create demo artifacts for tests. Use when needed.", pathlib.Path(tmp) / "skills"
            )
            self.assertNotIn(b"\r\n", path.read_bytes())

    def test_invalid_name_is_rejected(self) -> None:
        errors = scaffold_skill.validate_inputs("Demo_Skill", "Create demo artifacts. Use when testing.")
        self.assertTrue(any("lowercase" in error for error in errors))

    def test_long_description_is_rejected(self) -> None:
        errors = scaffold_skill.validate_inputs("demo-skill", "x" * 2000)
        self.assertTrue(any("exceeds 1024" in error for error in errors))

    def test_existing_target_requires_force(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp) / "skills"
            scaffold_skill.scaffold("demo-skill", "Create demo artifacts. Use when testing.", root)
            with self.assertRaises(FileExistsError):
                scaffold_skill.scaffold("demo-skill", "Create demo artifacts. Use when testing.", root)
            path = scaffold_skill.scaffold(
                "demo-skill", "Create better artifacts. Use when testing again.", root, force=True
            )
            self.assertIn("better artifacts", path.read_text(encoding="utf-8"))

    def test_dry_run_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp) / "skills"
            path = scaffold_skill.scaffold(
                "demo-skill", "Create demo artifacts. Use when testing.", root, dry_run=True
            )
            self.assertFalse(path.exists())
            self.assertFalse(root.exists())

    def test_cli_rejects_invalid_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            proc = subprocess.run(
                [sys.executable, str(SCRIPT), "Bad_Name", "--description", "Create demo artifacts. Use when needed.",
                 "--root", tmp],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(proc.returncode, 1)
            self.assertIn("lowercase", proc.stderr)

    def test_minimal_template_is_valid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = scaffold_skill.scaffold(
                "demo-skill", "Create demo artifacts. Use when testing.", pathlib.Path(tmp) / "skills", minimal=True
            )
            report = audit_skill.audit_skill(path.parent)
            self.assertTrue(report.valid, report.findings)
            self.assertNotIn("## Error Handling", path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
