#!/usr/bin/env python3
"""saboteur_check.py - prove that a verification command catches the defect it claims to catch.

A genuine verifier must:
  1. PASS against a known-good target (exit code 0)
  2. FAIL against a sabotaged target (non-zero exit code)

Commands may contain `{target}`; it is replaced with a shell-quoted path.
When `{target}` is absent, the target is appended to the command.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
from dataclasses import dataclass
from typing import Dict, Optional


@dataclass(frozen=True)
class RunResult:
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool


def quote_target(target: str) -> str:
    """Quote a path for the host shell used by subprocess with shell=True."""
    if os.name == "nt":
        return '"' + target.replace('"', '""') + '"'
    return shlex.quote(target)


def render_command(template: str, target: Optional[str]) -> str:
    if target is not None and "{target}" in template:
        return template.replace("{target}", quote_target(target))
    if target is not None:
        return f"{template} {quote_target(target)}"
    return template


def run_cmd(cmd: str, timeout: int = 20, env: Optional[Dict[str, str]] = None) -> RunResult:
    full_env = os.environ.copy()
    if env:
        full_env.update(env)
    try:
        proc = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=full_env,
        )
        return RunResult(proc.returncode, proc.stdout.strip(), proc.stderr.strip(), False)
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        return RunResult(
            -1,
            stdout.strip() if isinstance(stdout, str) else "",
            stderr.strip() if isinstance(stderr, str) else "Command timed out",
            True,
        )


def output_matches(result: RunResult, expected: Optional[str], forbidden: Optional[str]) -> tuple[bool, list[str]]:
    errors: list[str] = []
    haystack = f"{result.stdout}\n{result.stderr}"
    if expected is not None and expected not in haystack:
        errors.append(f"Expected output text not found: {expected!r}")
    if forbidden is not None and forbidden in haystack:
        errors.append(f"Forbidden output text found: {forbidden!r}")
    return not errors, errors


def verify_saboteur(
    pass_cmd: str,
    fail_cmd: str,
    pass_target: Optional[str] = None,
    fail_target: Optional[str] = None,
    timeout: int = 20,
    expect_text: Optional[str] = None,
    forbid_text: Optional[str] = None,
) -> Dict[str, object]:
    good_cmd = render_command(pass_cmd, pass_target)
    bad_cmd = render_command(fail_cmd, fail_target)

    good = run_cmd(good_cmd, timeout)
    bad = run_cmd(bad_cmd, timeout)

    errors: list[str] = []
    if good.timed_out:
        errors.append("Baseline verification timed out.")
    if bad.timed_out:
        errors.append("Sabotaged verification timed out.")
    if good.exit_code != 0:
        errors.append(f"Baseline verification failed with exit code {good.exit_code}.")
    if bad.exit_code == 0:
        errors.append("Tautology detected: sabotaged input passed verification.")

    text_ok, text_errors = output_matches(good, expect_text, forbid_text)
    if not text_ok:
        errors.extend([f"Baseline: {error}" for error in text_errors])

    verdict = "GENUINE_VERIFIER" if not errors else "INVALID_VERIFIER"
    return {
        "valid": not errors,
        "verdict": verdict,
        "commands": {"pass": good_cmd, "fail": bad_cmd},
        "baseline": good.__dict__,
        "sabotaged": bad.__dict__,
        "errors": errors,
    }


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Test whether a verification check catches sabotaged inputs.")
    parser.add_argument("--pass-cmd", required=True, help="Verifier command for the valid case; may contain {target}")
    parser.add_argument("--fail-cmd", required=True, help="Verifier command for the broken case; may contain {target}")
    parser.add_argument("--pass-target", help="Known-good file or directory; replaces {target}")
    parser.add_argument("--fail-target", help="Broken file or directory; replaces {target}")
    parser.add_argument("--timeout", type=int, default=20, help="Timeout in seconds for each command")
    parser.add_argument("--expect-text", help="Optional text required in baseline command output")
    parser.add_argument("--forbid-text", help="Optional text forbidden in baseline command output")
    args = parser.parse_args(argv)

    result = verify_saboteur(
        args.pass_cmd,
        args.fail_cmd,
        pass_target=args.pass_target,
        fail_target=args.fail_target,
        timeout=args.timeout,
        expect_text=args.expect_text,
        forbid_text=args.forbid_text,
    )
    print(json.dumps(result, indent=2))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    sys.exit(main())
