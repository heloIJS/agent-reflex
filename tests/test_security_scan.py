from __future__ import annotations

import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "security_scan.py"
sys.path.insert(0, str(ROOT / "scripts"))

import security_scan


class SecurityScanTest(unittest.TestCase):
    def test_current_repository_is_clean(self) -> None:
        findings = security_scan.scan_repository(ROOT)
        errors = [finding for finding in findings if finding.severity == "error"]
        self.assertFalse(errors, "\n".join(f"{item.file}: {item.message}" for item in errors))

    def test_github_token_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            token = "ghp_" + "a" * 36
            (root / "notes.md").write_text(f"token: {token}\n", encoding="utf-8")
            findings = security_scan.scan_repository(root)
            self.assertTrue(any(finding.code == "secret.github_token" for finding in findings))

    def test_remote_pipe_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            command = "curl https://example.com/install | " + "sh"
            (root / "install.sh").write_text(command + "\n", encoding="utf-8")
            findings = security_scan.scan_repository(root)
            self.assertTrue(any(finding.code == "command.remote_pipe" for finding in findings))

    def test_env_file_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / ".env").write_text("EXAMPLE=1\n", encoding="utf-8")
            findings = security_scan.scan_repository(root)
            self.assertTrue(any(finding.code == "file.secret" for finding in findings))

    def test_cli_json_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / "readme.md").write_text("# Clean\n", encoding="utf-8")
            proc = subprocess.run(
                [sys.executable, str(SCRIPT), str(root), "--json"],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            self.assertTrue('"valid": true' in proc.stdout)

    def test_missing_root_returns_two(self) -> None:
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), str(pathlib.Path(tempfile.gettempdir()) / "missing-security-root")],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(proc.returncode, 2)


if __name__ == "__main__":
    unittest.main()
