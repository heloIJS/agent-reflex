from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "reflex" / "scripts"))

import reflex_engine
import saboteur_check

VALID_RULE = (
    "- **WHEN** rendering 9:16 vertical video, **DO** place captions inside the safe zone "
    "because platform UI covers captions; **VERIFY** by sampling three frames with a safe-zone grid."
)


def run_engine(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ROOT / "skills" / "reflex" / "scripts" / "reflex_engine.py"), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def make_skill(tmp: str, name: str = "demo") -> pathlib.Path:
    skill_dir = pathlib.Path(tmp) / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    path = skill_dir / "SKILL.md"
    path.write_text(
        "---\n"
        f"name: {name}\n"
        "description: Demo skill used to test the reflex engine. Use when testing the engine.\n"
        "---\n\n"
        "# Demo\n\n"
        "## Use When\n\n"
        "- A test triggers it.\n",
        encoding="utf-8",
    )
    return path


class ReflexEngineTest(unittest.TestCase):
    def test_valid_rule_lints(self) -> None:
        ok, errors, rule = reflex_engine.lint_rule_text(VALID_RULE)
        self.assertTrue(ok, errors)
        self.assertTrue(rule.startswith("- **WHEN**"))

    def test_vague_rule_fails(self) -> None:
        ok, errors, _ = reflex_engine.lint_rule_text(
            "- **WHEN** making a report, **DO** be careful because quality matters; "
            "**VERIFY** by checking that everything looks ok."
        )
        self.assertFalse(ok)
        self.assertTrue(any("Vague" in error or "observational" in error for error in errors))

    def test_secret_in_rule_fails(self) -> None:
        fake_key = "sk-" + "a" * 24
        ok, errors, _ = reflex_engine.lint_rule_text(
            f"- **WHEN** calling the API, **DO** use key {fake_key} because tests; "
            "**VERIFY** by checking the response."
        )
        self.assertFalse(ok)
        self.assertTrue(any("secret" in error.lower() for error in errors))

    def test_cli_lint_accepts_structured_parts(self) -> None:
        proc = run_engine(
            "lint",
            "--trigger", "mixing TTS with background music",
            "--action", "duck music 18 dB because loud music masks speech",
            "--verify", "run ffmpeg -i out.mp4 -af ebur128 -f null - and require -14 LUFS plus or minus 1",
        )
        self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
        self.assertTrue(json.loads(proc.stdout)["valid"])

    def test_cli_lint_rejects_missing_parts(self) -> None:
        proc = run_engine("lint", "--trigger", "only a trigger")
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("Missing required arguments", proc.stdout)

    def test_patch_dry_run_does_not_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = make_skill(tmp)
            before = target.read_text(encoding="utf-8")
            proc = run_engine("patch", str(target), "--rule", VALID_RULE, "--dry-run", "--no-backup")
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            self.assertEqual(before, target.read_text(encoding="utf-8"))
            self.assertIn("diff", json.loads(proc.stdout)["result"])

    def test_patch_appends_and_audits(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = make_skill(tmp)
            proc = run_engine("patch", str(target), "--rule", VALID_RULE, "--no-backup")
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            text = target.read_text(encoding="utf-8")
            self.assertIn("## Learned Reflexes", text)
            self.assertEqual(text.count("**WHEN** rendering 9:16 vertical video"), 1)

    def test_patch_writes_backup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = make_skill(tmp)
            proc = run_engine("patch", str(target), "--rule", VALID_RULE)
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            self.assertTrue(target.with_suffix(".md.bak").exists())

    def test_patch_replaces_existing_rule(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = make_skill(tmp)
            first = (
                "- **WHEN** exporting PDF reports, **DO** check text bounds because overflow breaks layout; "
                "**VERIFY** by parsing every page for margins."
            )
            second = (
                "- **WHEN** exporting PDF reports, **DO** measure all text boxes because overflow hides "
                "in source HTML; **VERIFY** by failing any page whose box exceeds the margin box."
            )
            self.assertEqual(run_engine("patch", str(target), "--rule", first, "--no-backup").returncode, 0)
            proc = run_engine(
                "patch", str(target), "--rule", second, "--replace-match", "exporting PDF reports", "--no-backup"
            )
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            text = target.read_text(encoding="utf-8")
            self.assertIn("measure all text boxes", text)
            self.assertNotIn("check text bounds", text)

    def test_audit_accepts_crlf(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = make_skill(tmp)
            content = target.read_text(encoding="utf-8").replace("\n", "\r\n")
            target.write_bytes(content.encode("utf-8"))
            ok, messages, _ = reflex_engine.audit_skill_md(target)
            self.assertTrue(ok, messages)

    def test_audit_reads_multiline_folded_description(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = make_skill(tmp)
            text = target.read_text(encoding="utf-8")
            text = text.replace(
                "description: Demo skill used to test the reflex engine. Use when testing the engine.",
                "description: >\n  Demo skill used to test the reflex engine.\n  Use when testing the engine.",
            )
            target.write_text(text, encoding="utf-8")
            ok, messages, _ = reflex_engine.audit_skill_md(target)
            self.assertTrue(ok, messages)

    def test_audit_reads_multiline_literal_description(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = make_skill(tmp)
            text = target.read_text(encoding="utf-8")
            text = text.replace(
                "description: Demo skill used to test the reflex engine. Use when testing the engine.",
                "description: |\n  Demo skill used to test the reflex engine.\n  Use when testing the engine.",
            )
            target.write_text(text, encoding="utf-8")
            ok, messages, _ = reflex_engine.audit_skill_md(target)
            self.assertTrue(ok, messages)

    def test_patch_audits_candidate_before_writing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = make_skill(tmp)
            original = target.read_text(encoding="utf-8")
            target.write_text(original + ("\nExtra content.\n" * 490), encoding="utf-8")
            before = target.read_text(encoding="utf-8")
            proc = run_engine("patch", str(target), "--rule", VALID_RULE)
            self.assertNotEqual(proc.returncode, 0)
            self.assertEqual(before, target.read_text(encoding="utf-8"))
            self.assertFalse(target.with_suffix(".md.bak").exists())

    def test_replace_match_miss_stays_inside_target_section(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = make_skill(tmp)
            original = target.read_text(encoding="utf-8")
            target.write_text(
                original + "\n## Learned Reflexes\n\n- Existing rule.\n\n## Gotchas\n\nKeep this section after learned rules.\n",
                encoding="utf-8",
            )
            proc = run_engine(
                "patch", str(target), "--rule", VALID_RULE,
                "--replace-match", "no matching rule", "--no-backup",
            )
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            text = target.read_text(encoding="utf-8")
            rule_pos = text.index("**WHEN** rendering 9:16")
            gotchas_pos = text.index("## Gotchas")
            self.assertLess(rule_pos, gotchas_pos)

    def test_patch_rejects_rule_accumulation_over_limit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = make_skill(tmp)
            lines = [
                f"- **WHEN** processing input case {index}, **DO** preserve valid output because corruption harms results; "
                "**VERIFY** by checking the output checksum after processing."
                for index in range(1, reflex_engine.LEARNED_RULE_LIMIT + 1)
            ]
            text = target.read_text(encoding="utf-8")
            text += "\n## Learned Reflexes\n\n" + "\n".join(lines) + "\n"
            target.write_text(text, encoding="utf-8")
            before = target.read_text(encoding="utf-8")
            proc = run_engine("patch", str(target), "--rule", VALID_RULE, "--no-backup")
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("Consolidate overlapping rules", proc.stdout)
            self.assertEqual(before, target.read_text(encoding="utf-8"))

    def test_audit_rejects_name_directory_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = make_skill(tmp, "demo")
            target.write_text(
                target.read_text(encoding="utf-8").replace("name: demo", "name: other"),
                encoding="utf-8",
            )
            ok, messages, _ = reflex_engine.audit_skill_md(target)
            self.assertFalse(ok)
            self.assertTrue(any("match its directory" in message for message in messages))

    def test_duplicate_learned_rule_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = make_skill(tmp)
            text = target.read_text(encoding="utf-8") + f"\n{VALID_RULE}\n{VALID_RULE}\n"
            target.write_text(text, encoding="utf-8")
            ok, messages, _ = reflex_engine.audit_skill_md(target)
            self.assertFalse(ok)
            self.assertTrue(any("Duplicate" in message for message in messages))


class SaboteurCheckTest(unittest.TestCase):
    def _checker(self, tmp: str, script: str) -> pathlib.Path:
        path = pathlib.Path(tmp) / "check.py"
        path.write_text(
            "import sys\n" + script + "\n",
            encoding="utf-8",
        )
        return path

    def test_same_verifier_rejects_empty_file_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = pathlib.Path(tmp) / "report.txt"
            target.write_text("valid report", encoding="utf-8")
            checker = self._checker(
                tmp,
                "import pathlib\nsys.exit(0 if pathlib.Path(sys.argv[1]).stat().st_size > 0 else 1)",
            )
            result = saboteur_check.verify_saboteur(
                [sys.executable, str(checker), "{target}"], target, "empty-file"
            )
            self.assertTrue(result["valid"], result["errors"])
            self.assertEqual(result["verdict"], "MUTATION_CAUGHT")
            self.assertTrue(result["source_unchanged"])

    def test_verifier_that_ignores_mutation_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = pathlib.Path(tmp) / "report.txt"
            target.write_text("valid report", encoding="utf-8")
            result = saboteur_check.verify_saboteur(
                [sys.executable, "-c", "pass", "{target}"], target, "empty-file"
            )
        self.assertFalse(result["valid"])
        self.assertTrue(any("accepted the mutated" in error for error in result["errors"]))

    def test_command_failure_on_baseline_is_not_a_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = pathlib.Path(tmp) / "report.txt"
            target.write_text("valid report", encoding="utf-8")
            result = saboteur_check.verify_saboteur(
                [str(pathlib.Path(tmp) / "missing-command.exe"), "{target}"], target, "empty-file"
            )
        self.assertFalse(result["valid"])
        self.assertTrue(any("Could not launch baseline" in error for error in result["errors"]))

    def test_truncate_json_mutation_is_caught(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = pathlib.Path(tmp) / "report.json"
            target.write_text('{"ok": true, "count": 3}\n', encoding="utf-8")
            checker = self._checker(
                tmp,
                "import json, pathlib\n"
                "try: json.loads(pathlib.Path(sys.argv[1]).read_text()); sys.exit(0)\n"
                "except (ValueError, OSError): sys.exit(1)",
            )
            result = saboteur_check.verify_saboteur(
                [sys.executable, str(checker), "{target}"], target, "truncate-json"
            )
            self.assertTrue(result["valid"], result["errors"])
            self.assertEqual(json.loads(target.read_text(encoding="utf-8")), {"ok": True, "count": 3})

    def test_json_null_mutation_rejects_missing_required_value(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = pathlib.Path(tmp) / "report.json"
            target.write_text('{"status": "ready"}\n', encoding="utf-8")
            checker = self._checker(
                tmp,
                "import json, pathlib\n"
                "data = json.loads(pathlib.Path(sys.argv[1]).read_text())\n"
                "sys.exit(0 if data.get('status') else 1)",
            )
            result = saboteur_check.verify_saboteur(
                [sys.executable, str(checker), "{target}"], target, "json-null-key", json_key="status"
            )
            self.assertTrue(result["valid"], result["errors"])

    def test_mutation_rejects_wrong_fixture_type(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = pathlib.Path(tmp) / "report.txt"
            target.write_text("not JSON", encoding="utf-8")
            result = saboteur_check.verify_saboteur(
                [sys.executable, "-c", "pass", "{target}"], target, "truncate-json"
            )
            self.assertFalse(result["valid"])
            self.assertEqual(result["verdict"], "INVALID_TEST")

    def test_cli_accepts_verifier_argv_without_shell(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = pathlib.Path(tmp) / "report.txt"
            target.write_text("valid", encoding="utf-8")
            checker = self._checker(
                tmp,
                "import pathlib\nsys.exit(0 if pathlib.Path(sys.argv[1]).stat().st_size else 1)",
            )
            script = ROOT / "skills" / "reflex" / "scripts" / "saboteur_check.py"
            proc = subprocess.run(
                [sys.executable, str(script), "--target", str(target), "--mutation", "empty-file",
                 "--verify-command", sys.executable, str(checker), "{target}"],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            self.assertEqual(json.loads(proc.stdout)["verdict"], "MUTATION_CAUGHT")


if __name__ == "__main__":
    unittest.main()
