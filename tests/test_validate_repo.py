from __future__ import annotations

import pathlib
import shutil
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import validate_repo

IGNORE = shutil.ignore_patterns(".git", "__pycache__", "*.pyc", ".venv", "node_modules")


def error_codes(root: pathlib.Path) -> set[str]:
    return {finding.code for finding in validate_repo.validate(root) if finding.severity == "error"}


class RepositoryValidationTest(unittest.TestCase):
    def test_current_repository_passes(self) -> None:
        findings = validate_repo.validate(ROOT)
        errors = [finding for finding in findings if finding.severity == "error"]
        self.assertFalse(errors, "\n".join(f"{item.file}: {item.message}" for item in errors))

    def _copy(self, tmp: str) -> pathlib.Path:
        target = pathlib.Path(tmp) / "agent-reflex"
        shutil.copytree(ROOT, target, ignore=IGNORE)
        return target

    def test_uppercase_skill_name_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._copy(tmp)
            path = root / "skills" / "skill-audit" / "SKILL.md"
            path.write_text(path.read_text(encoding="utf-8").replace("name: skill-audit", "name: Skill-Audit"),
                            encoding="utf-8")
            self.assertIn("frontmatter.name", error_codes(root))

    def test_duplicate_skill_name_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._copy(tmp)
            source = root / "skills" / "reflex"
            copy = root / "skills" / "reflex-copy"
            shutil.copytree(source, copy)
            path = copy / "SKILL.md"
            path.write_text(path.read_text(encoding="utf-8").replace("name: reflex", "name: reflex"),
                            encoding="utf-8")
            self.assertIn("repo.duplicate_name", error_codes(root))

    def test_broken_readme_link_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._copy(tmp)
            readme = root / "README.md"
            readme.write_text(readme.read_text(encoding="utf-8") + "\n[Missing](docs/missing.md)\n",
                              encoding="utf-8")
            self.assertIn("repo.broken_link", error_codes(root))

    def test_placeholder_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._copy(tmp)
            readme = root / "README.md"
            marker = "TO" + "DO"
            readme.write_text(readme.read_text(encoding="utf-8") + f"\n- {marker} finish docs\n", encoding="utf-8")
            self.assertIn("repo.placeholder", error_codes(root))

    def test_missing_required_file_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._copy(tmp)
            (root / "SECURITY.md").unlink()
            self.assertIn("repo.required_file", error_codes(root))

    def test_oversized_skill_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._copy(tmp)
            path = root / "skills" / "reflex" / "SKILL.md"
            path.write_text(path.read_text(encoding="utf-8") + ("\nExtra line.\n" * 600), encoding="utf-8")
            self.assertIn("repo.skill_length", error_codes(root))

    def test_unpinned_workflow_action_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._copy(tmp)
            workflow = root / ".github" / "workflows" / "validate.yml"
            text = workflow.read_text(encoding="utf-8")
            text = text.replace("uses: actions/checkout@", "uses: actions/checkout@v4 # was @")
            workflow.write_text(text, encoding="utf-8")
            self.assertIn("ci.unpinned_action", error_codes(root))

    def test_missing_workflow_permissions_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._copy(tmp)
            workflow = root / ".github" / "workflows" / "validate.yml"
            text = workflow.read_text(encoding="utf-8").replace("permissions:\n", "")
            workflow.write_text(text, encoding="utf-8")
            self.assertIn("ci.permissions", error_codes(root))

    def test_invalid_workflow_yaml_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._copy(tmp)
            workflow = root / ".github" / "workflows" / "validate.yml"
            workflow.write_text("name: [invalid\non: push\njobs: {}\n", encoding="utf-8")
            self.assertIn("ci.yaml_syntax", error_codes(root))

    def test_readme_missing_install_command_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._copy(tmp)
            readme = root / "README.md"
            readme.write_text(
                readme.read_text(encoding="utf-8").replace(
                    f"npx skills add {validate_repo.REPO_SLUG}", "npx skills add"
                ),
                encoding="utf-8",
            )
            self.assertIn("readme.command", error_codes(root))


if __name__ == "__main__":
    unittest.main()
