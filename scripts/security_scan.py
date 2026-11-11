#!/usr/bin/env python3
"""Scan the repository for leaked credentials and risky shell instructions.

This is a lightweight, dependency-free guard for pull requests. It does not
replace GitHub secret scanning or a dedicated secret manager.

Exit codes: 0 clean, 1 findings, 2 unreadable root.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

ROOT = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {
    ".md", ".py", ".sh", ".bash", ".ps1", ".js", ".ts", ".json", ".jsonl",
    ".yaml", ".yml", ".txt", ".toml", ".ini", ".cfg", ".example",
}
SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv", ".pytest_cache"}

SECRET_PATTERNS = [
    ("private_key", r"-----BEGIN [A-Z ]*PRIVATE KEY-----", "Private key material"),
    ("github_token", r"\bgh[pousr]_[A-Za-z0-9]{36,}\b", "GitHub token"),
    ("github_pat", r"\bgithub_pat_[A-Za-z0-9_]{50,}\b", "GitHub fine-grained token"),
    ("aws_key", r"\bAKIA[0-9A-Z]{16}\b", "AWS access key ID"),
    ("openai_key", r"\bsk-[A-Za-z0-9_-]{32,}\b", "API secret key"),
    ("slack_token", r"\bxox[baprs]-[0-9A-Za-z-]{10,}\b", "Slack token"),
    (
        "credential_assignment",
        r"(?i)\b(api[_-]?key|client[_-]?secret|password|passwd|access[_-]?token)\b\s*[:=]\s*['\"][^'\"]{16,}['\"]",
        "Hard-coded credential",
    ),
]

DANGEROUS_PATTERNS = [
    ("remote_pipe", "error", r"\b(curl|wget)\b[^\n|]*\|\s*(bash|sh|zsh)\b", "Remote script piped to a shell"),
    ("recursive_delete", "warning", r"\brm\s+-rf\s+(/|~|\$HOME)\b", "Recursive delete of a home or root path"),
    ("force_push", "warning", r"\bgit\s+push\b[^\n]*--force\b", "Force push instruction"),
    ("permissive_mode", "warning", r"\bchmod\s+777\b", "World-writable permissions"),
    ("dynamic_eval", "warning", r"\beval\s*\(", "Dynamic code evaluation"),
]


@dataclass
class Finding:
    severity: str
    code: str
    message: str
    file: str
    line: int


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n").replace("\r", "\n")


def iter_text_files(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix.lower() in TEXT_SUFFIXES:
            yield path


def scan_file(path: Path, root: Path) -> List[Finding]:
    findings: List[Finding] = []
    try:
        text = _read(path)
    except OSError as exc:
        return [Finding("warning", "io.read", f"Cannot read file: {exc}", path.as_posix(), 0)]

    relative = path.relative_to(root).as_posix() if path.is_relative_to(root) else path.as_posix()
    lines = text.split("\n")
    for number, line in enumerate(lines, start=1):
        for code, pattern, label in SECRET_PATTERNS:
            if re.search(pattern, line):
                findings.append(Finding("error", f"secret.{code}", label, relative, number))
        for code, severity, pattern, label in DANGEROUS_PATTERNS:
            if re.search(pattern, line, flags=re.IGNORECASE):
                findings.append(Finding(severity, f"command.{code}", label, relative, number))
    return findings


def scan_repository(root: Path) -> List[Finding]:
    root = root.resolve()
    findings: List[Finding] = []

    for path in root.rglob("*"):
        if not path.is_file() or any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.name in {".env", "id_rsa", "id_ed25519"}:
            findings.append(
                Finding("error", "file.secret", "Secret-bearing file must not be committed",
                        path.relative_to(root).as_posix(), 0)
            )

    for path in iter_text_files(root):
        findings.extend(scan_file(path, root))
    return findings


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Scan for credentials and risky shell instructions.")
    parser.add_argument("root", nargs="?", default=str(ROOT), help="Repository root (default: repository root)")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    args = parser.parse_args(argv)

    root = Path(args.root)
    if not root.is_dir():
        print(f"error: root not found: {root}", file=sys.stderr)
        return 2

    findings = scan_repository(root)
    errors = [item for item in findings if item.severity == "error"]
    warnings = [item for item in findings if item.severity == "warning"]

    if args.json:
        print(json.dumps({
            "valid": not errors,
            "errors": [item.__dict__ for item in errors],
            "warnings": [item.__dict__ for item in warnings],
        }, indent=2))
    else:
        for item in errors + warnings:
            location = f"{item.file}:{item.line}" if item.line else item.file
            print(f"{item.severity.upper():7} {location}  {item.code}  {item.message}")
        print(f"\n{len(errors)} error(s), {len(warnings)} warning(s)")

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
