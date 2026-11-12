#!/usr/bin/env python3
"""Local, opt-in learning memory. Never executes commands read from memory."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Optional, Sequence

from reflex_engine import SECRET_PATTERNS, _atomic_write, lint_rule_text, parse_tav_rule
from saboteur_check import MUTATIONS, _run, verify_saboteur

SCHEMA = Path(__file__).resolve().parents[1] / "assets" / "reflex-ledger-schema.json"
SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
STOPWORDS = set("a an and are as at be by do for from in is it of on or the this to use when with yang dan di untuk saat".split())
SECRET_CHECKS = SECRET_PATTERNS + [r"\bgithub_pat_[A-Za-z0-9_]{50,}\b", r"\bxox[baprs]-[0-9A-Za-z-]{10,}\b"]


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_text(value: str, label: str, limit: int = 1024) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f"{label} must be non-empty text of at most {limit} characters.")
    if any(re.search(pattern, value) for pattern in SECRET_CHECKS):
        raise ValueError(f"Possible credential in {label}; remove sensitive data before recording.")
    if any(ord(char) < 32 for char in value):
        raise ValueError(f"{label} cannot contain control characters.")
    return value.strip()


def slug(value: str) -> str:
    if not SLUG.fullmatch(value) or len(value) > 64:
        raise ValueError("Topic and event ID must be lowercase kebab-case, at most 64 characters.")
    return value


def validate_schema(value: Any, schema: dict, location: str = "entry") -> None:
    """Validate the JSON Schema keywords used by our bundled ledger schema."""
    types = {"object": dict, "array": list, "string": str, "integer": int, "boolean": bool}
    expected = schema.get("type")
    if expected and (not isinstance(value, types[expected]) or (expected == "integer" and isinstance(value, bool))):
        raise ValueError(f"{location}: expected {expected}.")
    if "enum" in schema and value not in schema["enum"]:
        raise ValueError(f"{location}: unsupported value.")
    if isinstance(value, dict):
        missing = set(schema.get("required", [])) - value.keys()
        if missing:
            raise ValueError(f"{location}: missing {', '.join(sorted(missing))}.")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False and set(value) - properties.keys():
            raise ValueError(f"{location}: unknown fields.")
        for key, item in value.items():
            if key in properties:
                validate_schema(item, properties[key], f"{location}.{key}")
    elif isinstance(value, list):
        if len(value) > schema.get("maxItems", math.inf):
            raise ValueError(f"{location}: too many items.")
        for index, item in enumerate(value):
            validate_schema(item, schema.get("items", {}), f"{location}[{index}]")
    elif isinstance(value, str):
        if len(value) < schema.get("minLength", 0) or len(value) > schema.get("maxLength", math.inf):
            raise ValueError(f"{location}: text length out of bounds.")
        if "pattern" in schema and not re.search(schema["pattern"], value):
            raise ValueError(f"{location}: text format is invalid.")
    elif expected == "integer" and value < schema.get("minimum", -math.inf):
        raise ValueError(f"{location}: value below minimum.")


def validate_entry(entry: dict) -> None:
    validate_schema(entry, json.loads(SCHEMA.read_text(encoding="utf-8")))
    for key in ("trigger", "action", "verify", "target", "root_cause"):
        safe_text(entry[key], key)
    for tag in entry["tags"]:
        slug(tag)
    ok, errors, _ = lint_rule_text(rule_text(entry))
    if not ok:
        raise ValueError("Invalid memory rule: " + "; ".join(errors))
    if entry["status"] == "verified" and (not entry["verification"] or not entry["verification"][-1]["passed"]):
        raise ValueError("Verified rule requires the latest recorded verification to pass.")
    if entry["status"] == "verified" and not entry["verification"][-1]["fixture_hash"]:
        raise ValueError("Verified rule requires a fixture fingerprint.")
    if entry["status"] == "deprecated" and not entry["deprecation_reason"].strip():
        raise ValueError("Deprecated rule requires a reason.")


def rule_text(entry: dict) -> str:
    return f"- **WHEN** {entry['trigger']}, **DO** {entry['action']}; **VERIFY** by {entry['verify']}."


class Memory:
    def __init__(self, directory: Path):
        self.directory = directory
        self.ledger = directory / "reflex-ledger.jsonl"
        self.events = directory / "events.jsonl"

    @contextmanager
    def lock(self) -> Iterator[None]:
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.directory / ".write.lock"
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as exc:
            raise ValueError("Memory is locked. Retry; remove a stale lock only after confirming no writer is running.") from exc
        try:
            os.close(fd)
            yield
        finally:
            path.unlink()

    def read(self, path: Path) -> list[dict]:
        if not path.exists():
            return []
        entries = []
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
                if not isinstance(entry, dict):
                    raise ValueError("Row must be an object.")
                if path == self.ledger:
                    validate_entry(entry)
                else:
                    if set(entry) != {"id", "topic", "kind", "summary", "created", "evidence"}:
                        raise ValueError("Invalid observation fields.")
                    slug(entry["id"])
                    slug(entry["topic"])
                    safe_text(entry["summary"], "summary", 300)
                    if entry["kind"] not in {"failure", "correction", "resolution"}:
                        raise ValueError("Unsupported observation kind.")
                    if not isinstance(entry["evidence"], dict):
                        raise ValueError("Observation evidence must be an object.")
                    if entry["kind"] == "resolution" and (
                        entry["evidence"].get("passed") is not True or entry["evidence"].get("exit_code") != 0
                    ):
                        raise ValueError("Resolution lacks a successful check.")
                if any(item["id"] == entry["id"] for item in entries):
                    raise ValueError("Duplicate row ID.")
                entries.append(entry)
            except (ValueError, KeyError, TypeError) as exc:
                raise ValueError(f"Invalid memory row {path.name}:{number}: {exc}") from exc
        return entries

    def save(self, path: Path, entries: list[dict]) -> None:
        if path == self.ledger:
            for entry in entries:
                validate_entry(entry)
        _atomic_write(path, "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in entries))

    def observe(self, topic: str, event_id: str, kind: str, summary: str, evidence: Optional[dict] = None) -> dict:
        slug(topic)
        slug(event_id)
        safe_text(summary, "summary", 300)
        if kind not in {"failure", "correction", "resolution"}:
            raise ValueError("Unsupported observation kind.")
        with self.lock():
            events = self.read(self.events)
            previous = next((event for event in events if event["id"] == event_id), None)
            if previous:
                if (previous["topic"], previous["kind"], previous["summary"]) != (topic, kind, summary):
                    raise ValueError("Event ID already belongs to a different observation.")
                return {"recorded": False, "event": previous, **self.signals(topic, events)}
            event = {"id": event_id, "topic": topic, "kind": kind, "summary": summary,
                     "created": now(), "evidence": evidence or {}}
            self.save(self.events, events + [event])
            return {"recorded": True, "event": event, **self.signals(topic, events + [event])}

    def signals(self, topic: str, events: Optional[list[dict]] = None) -> dict:
        rows = [event for event in (events if events is not None else self.read(self.events)) if event["topic"] == topic]
        failures = sum(row["kind"] == "failure" for row in rows)
        corrections = sum(row["kind"] == "correction" for row in rows)
        problem_positions = [i for i, row in enumerate(rows) if row["kind"] in {"failure", "correction"}]
        resolved = bool(problem_positions) and any(
            row["kind"] == "resolution" and row["evidence"].get("exit_code") == 0
            and row["evidence"].get("passed") is True
            for row in rows[problem_positions[-1] + 1:]
        )
        return {"failure_count": failures, "correction_count": corrections,
                "proposal_ready": (failures >= 3 or corrections > 0) and resolved}

    def propose(self, topic: str, rule: str, tags: list[str], category: str, target: str, root_cause: str) -> dict:
        slug(topic)
        safe_text(rule, "rule", 2048)
        parts = parse_tav_rule(rule)
        with self.lock():
            signals = self.signals(topic)
            if not signals["proposal_ready"]:
                raise ValueError("Need three failures or a user correction, followed by a successfully executed resolution check.")
            entries = self.read(self.ledger)
            existing = next((entry for entry in entries if entry["topic"] == topic and entry["status"] != "deprecated"), None)
            if existing:
                return {"created": False, "entry": existing, "message": "Existing topic; review it instead of duplicating."}
            digest = hashlib.sha256((topic + rule).encode()).hexdigest()[:16]
            entry = {
                "id": "rfx-" + digest, "topic": topic, "status": "provisional", "category": category,
                "root_cause": root_cause, "trigger": parts.trigger, "action": parts.action, "verify": parts.verify,
                "target": target, "tags": sorted(set(tags)), "created": now(), "updated": now(),
                "failure_count": signals["failure_count"], "correction_count": signals["correction_count"],
                "verification": [], "deprecation_reason": "",
            }
            if any(row["id"] == entry["id"] for row in entries):
                raise ValueError("This exact rule was deprecated. Revise it before proposing again.")
            self.save(self.ledger, entries + [entry])
            return {"created": True, "entry": entry}

    def get(self, rule_id: str) -> dict:
        entries = self.read(self.ledger)
        entry = next((row for row in entries if row["id"] == rule_id), None)
        if entry is None:
            raise ValueError(f"Rule not found: {rule_id}")
        return entry

    def inspect(self, rule_id: str) -> dict:
        entry = self.get(rule_id)
        successful_checks = [item["created"] for item in entry["verification"] if item["passed"]]
        since = successful_checks[-1] if successful_checks else entry["created"]
        recurrences = sum(
            event["topic"] == entry["topic"] and event["kind"] in {"failure", "correction"}
            and event["created"] > since for event in self.read(self.events)
        )
        return {"entry": entry, "signals": self.signals(entry["topic"]),
                "recurrences_since_last_successful_verification_or_proposal": recurrences,
                "escalation_suggested": recurrences >= 3}

    def verify(self, rule_id: str, command: Sequence[str], fixture: Path, mutation: str,
               json_key: Optional[str], timeout: int) -> dict:
        if not command or not 1 <= timeout <= 300:
            raise ValueError("Verification requires argv and timeout between 1 and 300 seconds.")
        entry = self.get(rule_id)
        if entry["status"] == "deprecated":
            raise ValueError("Deprecated rules cannot be verified; propose a corrected rule.")
        digest = hashlib.sha256(json.dumps(entry, sort_keys=True).encode()).hexdigest()
        fixture_hash = hashlib.sha256(fixture.read_bytes()).hexdigest() if fixture.is_file() else ""
        report = verify_saboteur(command, fixture, mutation, json_key=json_key,
                                 timeout=timeout, require_verdict=True)
        evidence = {
            "passed": report["valid"], "mutation": mutation, "created": now(),
            "command_hash": hashlib.sha256(json.dumps(list(command)).encode()).hexdigest(),
            "fixture_hash": fixture_hash,
        }
        with self.lock():
            entries = self.read(self.ledger)
            current = next(row for row in entries if row["id"] == rule_id)
            if hashlib.sha256(json.dumps(current, sort_keys=True).encode()).hexdigest() != digest:
                raise ValueError("Rule changed during verification; retry against its current revision.")
            current["verification"] = (current["verification"] + [evidence])[-10:]
            current["status"] = "verified" if report["valid"] else "provisional"
            current["updated"] = now()
            self.save(self.ledger, entries)
        # Do not persist command output: verifiers may print private information.
        return {"valid": report["valid"], "entry": current, "errors": report["errors"],
                "note": "Verified only for this fixture, property verdict, and mutation; not a universal correctness proof."}

    def deprecate(self, rule_id: str, reason: str) -> dict:
        safe_text(reason, "deprecation reason", 300)
        with self.lock():
            entries = self.read(self.ledger)
            entry = next((row for row in entries if row["id"] == rule_id), None)
            if not entry:
                raise ValueError(f"Rule not found: {rule_id}")
            entry["status"] = "deprecated"
            entry["deprecation_reason"] = reason
            entry["updated"] = now()
            self.save(self.ledger, entries)
        return entry

    def retrieve(self, query: str, limit: int = 5, max_chars: int = 4000, review: bool = False) -> dict:
        if not 1 <= limit <= 20 or not 256 <= max_chars <= 16000:
            raise ValueError("Limit must be 1-20 and max-chars must be 256-16000.")
        terms = tokens(query)
        if not terms:
            return {"rules": [], "chars": 2, "budget_unit": "characters"}
        entries = self.read(self.ledger)
        ranked = []
        for entry in entries:
            if entry["status"] == "deprecated" or (not review and entry["status"] != "verified"):
                continue
            weights = ((entry["tags"], 5), ([entry["topic"], entry["trigger"]], 3),
                       ([entry["target"], entry["action"], entry["verify"]], 1))
            score = sum(len(terms & tokens(" ".join(values))) * weight for values, weight in weights)
            if score:
                ranked.append((score, entry))
        ranked.sort(key=lambda item: (-item[0], item[1]["id"]))
        selected = []
        for score, entry in ranked:
            item = {"id": entry["id"], "status": entry["status"], "rule": rule_text(entry), "score": score}
            if len(json.dumps(selected + [item], ensure_ascii=False)) <= max_chars:
                selected.append(item)
            if len(selected) == limit:
                break
        return {"rules": selected, "chars": len(json.dumps(selected, ensure_ascii=False)), "budget_unit": "characters"}


def tokens(text: str) -> set[str]:
    return {term for term in re.findall(r"[^\W_]+", text.casefold()) if len(term) > 1 and term not in STOPWORDS}


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", type=Path, default=Path(".reflex"), help="Local memory directory (default: .reflex)")
    sub = parser.add_subparsers(dest="command", required=True)
    observe = sub.add_parser("observe", help="Record a sanitized failure or correction signal")
    resolve = sub.add_parser("resolve", help="Execute an inspected resolution check and record its outcome")
    for command in (observe, resolve):
        command.add_argument("--topic", required=True)
        command.add_argument("--event-id", required=True, help="Stable unique ID for replay-safe recording")
        command.add_argument("--summary", required=True)
    observe.add_argument("--kind", choices=("failure", "correction"), required=True)
    resolve.add_argument("--timeout", type=int, default=20)
    resolve.add_argument("--verify-command", nargs=argparse.REMAINDER, required=True)
    propose = sub.add_parser("propose", help="Create a provisional TAV rule after resolved learning signals")
    propose.add_argument("--topic", required=True)
    propose.add_argument("--rule", required=True)
    propose.add_argument("--tags", nargs="+", required=True)
    propose.add_argument("--category", required=True)
    propose.add_argument("--target", required=True)
    propose.add_argument("--root-cause", required=True)
    verify = sub.add_parser("verify", help="Lint and execute structured content mutation verification")
    verify.add_argument("id")
    verify.add_argument("--fixture", type=Path, required=True)
    verify.add_argument("--mutation", choices=MUTATIONS, required=True)
    verify.add_argument("--json-key")
    verify.add_argument("--timeout", type=int, default=20)
    verify.add_argument("--verify-command", nargs=argparse.REMAINDER, required=True)
    deprecate = sub.add_parser("deprecate", help="Disable a rule without deleting history")
    deprecate.add_argument("id")
    deprecate.add_argument("--reason", required=True)
    inspect = sub.add_parser("inspect", help="Show one rule, current signals, and recurrence counts")
    inspect.add_argument("id")
    retrieve = sub.add_parser("retrieve", help="Return bounded, relevant verified rules")
    retrieve.add_argument("--query", required=True)
    retrieve.add_argument("--limit", type=int, default=5)
    retrieve.add_argument("--max-chars", type=int, default=4000)
    retrieve.add_argument("--review", action="store_true", help="Include provisional rules for review, not as trusted instructions")
    args = parser.parse_args(argv)
    memory = Memory(args.store)
    try:
        if args.command == "observe":
            result = memory.observe(args.topic, args.event_id, args.kind, args.summary)
        elif args.command == "resolve":
            slug(args.topic)
            slug(args.event_id)
            safe_text(args.summary, "summary", 300)
            if not args.verify_command or not 1 <= args.timeout <= 300:
                raise ValueError("Resolution requires a verifier argv and timeout between 1 and 300 seconds.")
            run = _run(args.verify_command, args.timeout)
            passed = run.exit_code == 0 and not run.timed_out and not run.launch_error
            evidence = {"exit_code": run.exit_code, "passed": passed,
                        "command_hash": hashlib.sha256(json.dumps(args.verify_command).encode()).hexdigest()}
            result = memory.observe(args.topic, args.event_id, "resolution" if passed else "failure", args.summary, evidence)
            result["valid"] = passed
        elif args.command == "propose":
            result = memory.propose(args.topic, args.rule, args.tags, args.category, args.target, args.root_cause)
        elif args.command == "verify":
            result = memory.verify(args.id, args.verify_command, args.fixture, args.mutation, args.json_key, args.timeout)
        elif args.command == "deprecate":
            result = memory.deprecate(args.id, args.reason)
        elif args.command == "inspect":
            result = memory.inspect(args.id)
        else:
            result = memory.retrieve(args.query, args.limit, args.max_chars, args.review)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 1 if result.get("valid") is False else 0
    except (OSError, ValueError, KeyError, TypeError, StopIteration) as exc:
        print(json.dumps({"valid": False, "errors": [str(exc)]}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
