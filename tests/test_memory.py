from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "reflex" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import reflex_memory
import saboteur_check

RULE = (
    "- **WHEN** checking authentication API responses, **DO** require an authenticated boolean "
    "because null values hide failures; **VERIFY** by rejecting a null authenticated field in the response."
)
FIXTURE = ROOT / "examples" / "learning" / "auth-response.json"
CHECKER = ROOT / "examples" / "learning" / "check_auth_response.py"


class MemoryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = pathlib.Path(self.temp.name) / ".reflex"
        self.memory = reflex_memory.Memory(self.directory)

    def cli(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(SCRIPTS / "reflex_engine.py"), "memory", "--store", str(self.directory), *args],
            capture_output=True, text=True, check=False,
        )

    def ready(self, topic: str = "auth-response") -> None:
        self.memory.observe(topic, "correction-1", "correction", "Use a boolean rather than a nullable auth field")
        proc = self.cli(
            "resolve", "--topic", topic, "--event-id", "resolution-1", "--summary", "Corrected response passes property check",
            "--verify-command", sys.executable, str(CHECKER), str(FIXTURE),
        )
        self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)

    def propose(self) -> dict:
        self.ready()
        return self.memory.propose(
            "auth-response", RULE, ["authentication", "api"], "TOOL_OR_API_HALLUCINATION",
            "auth-skill", "Nullable authentication values hid API failures",
        )["entry"]

    def verify(self, entry: dict) -> dict:
        return self.memory.verify(
            entry["id"], [sys.executable, str(CHECKER), "{target}"], FIXTURE,
            "json-null-key", "authenticated", 20,
        )

    def test_three_failures_then_real_resolution_enable_proposal(self) -> None:
        for index in range(3):
            result = self.memory.observe("auth-response", f"failure-{index}", "failure", "Wrong API response field")
            self.assertFalse(result["proposal_ready"])
        proc = self.cli(
            "resolve", "--topic", "auth-response", "--event-id", "resolution-1", "--summary", "API response check succeeds",
            "--verify-command", sys.executable, str(CHECKER), str(FIXTURE),
        )
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertTrue(json.loads(proc.stdout)["proposal_ready"])

    def test_resolution_before_failure_does_not_enable_proposal(self) -> None:
        proc = self.cli(
            "resolve", "--topic", "auth-response", "--event-id", "resolution-1", "--summary", "Check passed before correction",
            "--verify-command", sys.executable, str(CHECKER), str(FIXTURE),
        )
        self.assertEqual(proc.returncode, 0, proc.stdout)
        result = self.memory.observe("auth-response", "correction-1", "correction", "Found a later regression")
        self.assertFalse(result["proposal_ready"])

    def test_replayed_observation_does_not_increase_count(self) -> None:
        self.memory.observe("auth-response", "failure-1", "failure", "Wrong API method")
        result = self.memory.observe("auth-response", "failure-1", "failure", "Wrong API method")
        self.assertFalse(result["recorded"])
        self.assertEqual(result["failure_count"], 1)

    def test_conflicting_replay_is_rejected(self) -> None:
        self.memory.observe("auth-response", "failure-1", "failure", "Wrong API method")
        with self.assertRaises(ValueError):
            self.memory.observe("other-topic", "failure-1", "failure", "Wrong API method")

    def test_proposal_requires_resolved_learning_signal(self) -> None:
        with self.assertRaisesRegex(ValueError, "three failures"):
            self.memory.propose("auth-response", RULE, ["api"], "OTHER", "auth-skill", "Wrong API method")

    def test_failed_resolution_is_recorded_but_not_trusted(self) -> None:
        self.memory.observe("auth-response", "correction-1", "correction", "Wrong API method")
        proc = self.cli(
            "resolve", "--topic", "auth-response", "--event-id", "resolution-1", "--summary", "Resolution test failed",
            "--verify-command", sys.executable, "-c", "import sys; sys.exit(2)",
        )
        self.assertEqual(proc.returncode, 1)
        self.assertFalse(self.memory.signals("auth-response")["proposal_ready"])

    def test_proposal_is_provisional_and_duplicate_topic_is_not_appended(self) -> None:
        entry = self.propose()
        self.assertEqual(entry["status"], "provisional")
        repeated = self.memory.propose("auth-response", RULE, ["api"], "OTHER", "auth-skill", "Same root cause")
        self.assertFalse(repeated["created"])
        self.assertEqual(len(self.memory.read(self.memory.ledger)), 1)

    def test_lint_failure_does_not_write_ledger(self) -> None:
        self.ready()
        with self.assertRaises(ValueError):
            self.memory.propose("auth-response", "invalid rule", ["api"], "OTHER", "auth-skill", "Wrong method")
        self.assertFalse(self.memory.ledger.exists())

    def test_verified_state_requires_live_structured_mutation_test(self) -> None:
        entry = self.propose()
        result = self.verify(entry)
        self.assertTrue(result["valid"], result)
        self.assertEqual(self.memory.get(entry["id"])["status"], "verified")
        self.assertTrue(result["entry"]["verification"][-1]["passed"])

    def test_failed_reverification_demotes_to_provisional(self) -> None:
        entry = self.propose()
        self.verify(entry)
        result = self.memory.verify(
            entry["id"], [sys.executable, "-c", "pass", "{target}"], FIXTURE, "empty-file", None, 20,
        )
        self.assertFalse(result["valid"])
        self.assertEqual(self.memory.get(entry["id"])["status"], "provisional")

    def test_traceback_and_exit_two_do_not_promote_rule(self) -> None:
        entry = self.propose()
        result = self.memory.verify(
            entry["id"], [sys.executable, str(CHECKER), "{target}"], FIXTURE, "truncate-json", None, 20,
        )
        self.assertFalse(result["valid"])
        self.assertEqual(result["entry"]["status"], "provisional")

    def test_retrieval_excludes_provisional_by_default(self) -> None:
        self.propose()
        self.assertEqual(self.memory.retrieve("authentication")["rules"], [])
        self.assertEqual(len(self.memory.retrieve("authentication", review=True)["rules"]), 1)

    def test_retrieval_matches_relevant_rules_only_and_limits_context(self) -> None:
        entry = self.propose()
        self.verify(entry)
        result = self.memory.retrieve("authentication", max_chars=600)
        self.assertEqual(len(result["rules"]), 1)
        self.assertLessEqual(result["chars"], 600)
        self.assertNotIn("verification", result["rules"][0])
        self.assertEqual(self.memory.retrieve("gardening soil")["rules"], [])

    def test_empty_query_does_not_load_all_rules(self) -> None:
        self.propose()
        self.assertEqual(self.memory.retrieve("")["rules"], [])

    def test_retrieval_budget_skips_complete_rule_instead_of_truncating(self) -> None:
        entry = self.propose()
        self.verify(entry)
        result = self.memory.retrieve("authentication", max_chars=256)
        self.assertEqual(result["rules"], [])
        self.assertLessEqual(result["chars"], 256)

    def test_read_only_retrieval_does_not_execute_any_command(self) -> None:
        entry = self.propose()
        self.verify(entry)
        with mock.patch("subprocess.run", side_effect=AssertionError("Retrieval executed a command")):
            self.assertEqual(len(self.memory.retrieve("authentication")["rules"]), 1)

    def test_invalid_retrieval_budget_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.memory.retrieve("authentication", limit=0)

    def test_retrieval_ranks_tag_matches_above_body_matches_and_respects_limit(self) -> None:
        first = self.propose()
        self.verify(first)
        self.memory.observe("different-api", "other-correction", "correction", "Different API lesson")
        self.memory.observe(
            "different-api", "other-resolution", "resolution", "Example property test passed",
            {"passed": True, "exit_code": 0},
        )
        second = self.memory.propose(
            "different-api", RULE, ["authentication"], "OTHER", "auth-skill", "Different contract failure",
        )["entry"]
        self.verify(second)
        result = self.memory.retrieve("api", limit=1)
        self.assertEqual(len(result["rules"]), 1)
        self.assertEqual(result["rules"][0]["id"], first["id"])

    def test_deprecated_rule_cannot_be_retrieved_or_reverified(self) -> None:
        entry = self.propose()
        self.verify(entry)
        self.memory.deprecate(entry["id"], "The API response contract changed")
        self.assertEqual(self.memory.retrieve("authentication", review=True)["rules"], [])
        with self.assertRaisesRegex(ValueError, "Deprecated"):
            self.verify(entry)

    def test_recurrences_produce_escalation_signal_not_auto_code_changes(self) -> None:
        entry = self.propose()
        self.verify(entry)
        for index in range(3):
            self.memory.observe("auth-response", f"recurrence-{index}", "failure", "Same API mistake recurred")
        report = self.memory.inspect(entry["id"])
        self.assertEqual(report["recurrences_since_last_successful_verification_or_proposal"], 3)
        self.assertTrue(report["escalation_suggested"])

    def test_schema_is_enforced_on_disk_reads(self) -> None:
        self.propose()
        rows = self.memory.read(self.memory.ledger)
        rows[0]["status"] = "invented"
        self.memory.ledger.write_text(json.dumps(rows[0]) + "\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "unsupported value"):
            self.memory.retrieve("authentication")

    def test_schema_does_not_allow_verified_without_evidence(self) -> None:
        entry = self.propose()
        entry["status"] = "verified"
        with self.assertRaisesRegex(ValueError, "latest recorded verification"):
            reflex_memory.validate_entry(entry)

    def test_secret_is_rejected_before_persistence(self) -> None:
        secret = "ghp_" + "a" * 36
        with self.assertRaisesRegex(ValueError, "credential"):
            self.memory.observe("auth-response", "failure-1", "failure", secret)
        self.assertFalse(self.memory.events.exists())

    def test_corrupt_ledger_is_not_silently_overwritten(self) -> None:
        self.ready()
        self.memory.ledger.write_text("broken JSON\n", encoding="utf-8")
        before = self.memory.ledger.read_bytes()
        with self.assertRaises(ValueError):
            self.memory.propose("auth-response", RULE, ["api"], "OTHER", "auth-skill", "Wrong API method")
        self.assertEqual(before, self.memory.ledger.read_bytes())

    def test_concurrent_writer_is_rejected_without_deleting_lock(self) -> None:
        with self.memory.lock():
            with self.assertRaisesRegex(ValueError, "locked"):
                self.memory.observe("auth-response", "failure-1", "failure", "Wrong API method")
            self.assertTrue((self.directory / ".write.lock").exists())

    def test_failed_atomic_write_preserves_existing_ledger(self) -> None:
        entry = self.propose()
        before = self.memory.ledger.read_bytes()
        with mock.patch("reflex_memory._atomic_write", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                self.memory.deprecate(entry["id"], "Invalid rule")
        self.assertEqual(before, self.memory.ledger.read_bytes())

    def test_memory_survives_process_restart(self) -> None:
        entry = self.propose()
        self.verify(entry)
        proc = self.cli("retrieve", "--query", "authentication")
        self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
        self.assertEqual(json.loads(proc.stdout)["rules"][0]["id"], entry["id"])

    def test_structured_verifier_rejects_noop_null_mutation(self) -> None:
        target = pathlib.Path(self.temp.name) / "null.json"
        target.write_text('{"authenticated": null}', encoding="utf-8")
        report = saboteur_check.verify_saboteur(
            [sys.executable, str(CHECKER), "{target}"], target, "json-null-key",
            json_key="authenticated", require_verdict=True,
        )
        self.assertFalse(report["valid"])
        self.assertIn("already null", report["errors"][0])


if __name__ == "__main__":
    unittest.main()
