#!/usr/bin/env python3
"""Run one verifier against an original fixture and a controlled mutation.

The verifier command is an argv list, never a shell string. Both runs use
temporary copies of the same existing input. No mutation touches the source.

Exit codes:
    0  baseline passed and selected mutation was rejected
    1  verifier, mutation, or fixture check failed
    2  invalid command-line usage
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

MUTATIONS = ("empty-file", "truncate-json", "invalid-json", "json-null-key")
TARGET_TOKEN = "{target}"


@dataclass(frozen=True)
class RunResult:
    exit_code: Optional[int]
    stdout: str
    stderr: str
    timed_out: bool
    launch_error: str = ""

    def as_dict(self) -> Dict[str, Any]:
        return {
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "timed_out": self.timed_out,
            "launch_error": self.launch_error,
        }


def mutate_file(path: Path, mutation: str, json_key: Optional[str] = None) -> None:
    """Apply one explicit mutation to a temporary copy of a regular file."""
    if not path.is_file() or path.is_symlink():
        raise ValueError("Mutation target must be a regular file, not a symlink.")

    if mutation == "empty-file":
        path.write_bytes(b"")
        return

    if mutation == "invalid-json":
        path.write_text('{"__reflex_mutation__":', encoding="utf-8")
        return

    try:
        raw = path.read_text(encoding="utf-8")
        value = json.loads(raw)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Mutation '{mutation}' requires a readable JSON fixture: {exc}") from exc

    if mutation == "truncate-json":
        for end in range(len(raw) - 1, -1, -1):
            candidate = raw[:end].rstrip()
            try:
                json.loads(candidate)
            except json.JSONDecodeError:
                path.write_text(candidate, encoding="utf-8")
                return
        raise ValueError("Could not truncate this JSON fixture into invalid JSON.")

    if mutation == "json-null-key":
        if not isinstance(value, dict):
            raise ValueError("Mutation 'json-null-key' requires a top-level JSON object.")
        if not json_key:
            raise ValueError("Mutation 'json-null-key' requires --json-key.")
        if json_key not in value:
            raise ValueError(f"JSON key not found in fixture: {json_key}")
        value[json_key] = None
        path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return

    raise ValueError(f"Unsupported mutation: {mutation}")


def _command_for(command: Sequence[str], target: Path) -> List[str]:
    rendered = [arg.replace(TARGET_TOKEN, str(target)) for arg in command]
    if not any(TARGET_TOKEN in arg for arg in command):
        raise ValueError(f"Verifier command must include {TARGET_TOKEN} as an argument.")
    return rendered


def _run(command: Sequence[str], timeout: int) -> RunResult:
    try:
        result = subprocess.run(
            list(command),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return RunResult(result.returncode, result.stdout.strip(), result.stderr.strip(), False)
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        return RunResult(
            None,
            stdout.strip() if isinstance(stdout, str) else "",
            stderr.strip() if isinstance(stderr, str) else "",
            True,
        )
    except OSError as exc:
        return RunResult(None, "", "", False, str(exc))


def verify_saboteur(
    verify_command: Sequence[str],
    target: Path,
    mutation: str,
    *,
    json_key: Optional[str] = None,
    timeout: int = 20,
) -> Dict[str, Any]:
    """Pass only when the same verifier accepts baseline and rejects mutation."""
    errors: List[str] = []
    if mutation not in MUTATIONS:
        return {"valid": False, "verdict": "INVALID_TEST", "errors": [f"Unsupported mutation: {mutation}"]}
    if not target.is_file() or target.is_symlink():
        return {
            "valid": False,
            "verdict": "INVALID_TEST",
            "errors": [f"Target must be an existing regular file: {target}"],
        }
    if timeout < 1:
        return {"valid": False, "verdict": "INVALID_TEST", "errors": ["Timeout must be at least one second."]}

    try:
        original_bytes = target.read_bytes()
        with tempfile.TemporaryDirectory(prefix="reflex-saboteur-") as temp_dir:
            root = Path(temp_dir)
            baseline_target = root / "baseline" / target.name
            mutated_target = root / "mutated" / target.name
            baseline_target.parent.mkdir()
            mutated_target.parent.mkdir()
            shutil.copyfile(target, baseline_target)
            shutil.copyfile(target, mutated_target)
            mutate_file(mutated_target, mutation, json_key)

            baseline_command = _command_for(verify_command, baseline_target)
            mutated_command = _command_for(verify_command, mutated_target)
            baseline = _run(baseline_command, timeout)
            mutated = _run(mutated_command, timeout)

            if baseline.timed_out:
                errors.append("Baseline verifier timed out.")
            elif baseline.launch_error:
                errors.append(f"Could not launch baseline verifier: {baseline.launch_error}")
            elif baseline.exit_code != 0:
                errors.append(f"Baseline fixture failed verification with exit code {baseline.exit_code}.")

            if mutated.timed_out:
                errors.append("Mutated verifier timed out.")
            elif mutated.launch_error:
                errors.append(f"Could not launch mutated verifier: {mutated.launch_error}")
            elif mutated.exit_code == 0:
                errors.append("Verifier accepted the mutated fixture.")

            source_unchanged = target.read_bytes() == original_bytes
            if not source_unchanged:
                errors.append("Verifier modified the original fixture.")

            return {
                "valid": not errors,
                "verdict": "MUTATION_CAUGHT" if not errors else "INVALID_TEST",
                "mutation": mutation,
                "source_unchanged": source_unchanged,
                "baseline": {"command": baseline_command, **baseline.as_dict()},
                "mutated": {"command": mutated_command, **mutated.as_dict()},
                "errors": errors,
            }
    except (OSError, ValueError) as exc:
        return {"valid": False, "verdict": "INVALID_TEST", "errors": [str(exc)]}


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run one verifier on an original fixture and a controlled content mutation.",
        epilog=(
            "Example: python saboteur_check.py --target report.json --mutation truncate-json "
            "--verify-command python check_report.py {target}"
        ),
    )
    parser.add_argument("--target", required=True, type=Path, help="Existing fixture file; source is never modified")
    parser.add_argument("--mutation", required=True, choices=MUTATIONS, help="Controlled content mutation")
    parser.add_argument("--json-key", help="Existing object key for json-null-key mutation")
    parser.add_argument("--timeout", type=int, default=20, help="Timeout in seconds for each verifier run")
    parser.add_argument(
        "--verify-command",
        required=True,
        nargs=argparse.REMAINDER,
        help=f"Verifier argv; include {TARGET_TOKEN}. No shell is used.",
    )
    args = parser.parse_args(argv)

    command = list(args.verify_command)
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        parser.error("--verify-command needs executable arguments after it")

    result = verify_saboteur(
        command,
        args.target,
        args.mutation,
        json_key=args.json_key,
        timeout=args.timeout,
    )
    print(json.dumps(result, indent=2))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    sys.exit(main())
