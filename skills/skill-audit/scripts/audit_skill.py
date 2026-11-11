#!/usr/bin/env python3
"""Deterministic validator for Agent Skills.

Audits one or more skill directories against the Agent Skills specification and
a set of content, reference, and security checks. Standard library only: PyYAML
is used when installed, with a built-in YAML subset parser as fallback.

Exit codes:
    0  no errors (warnings allowed unless --strict is used)
    1  errors found, or warnings found with --strict
    2  invalid command-line usage or unreadable path
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import unquote

NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
NAME_MAX = 64
DESCRIPTION_MAX = 1024
COMPATIBILITY_MAX = 500
SKILL_LINE_WARNING = 500
SKILL_LINE_ERROR = 1000
TEXT_SUFFIXES = {".md", ".py", ".sh", ".bash", ".js", ".ts", ".json", ".yaml", ".yml", ".txt"}
SKIP_PARTS = {".git", "__pycache__", "node_modules", ".venv", "venv", ".pytest_cache", ".mypy_cache"}

TRIGGER_RE = re.compile(
    r"\b(use (this )?(skill )?when|use for|use when|invoke (this skill )?when|"
    r"trigger(ed)? when|when the user|when you|when a user)\b",
    re.IGNORECASE,
)

PLACEHOLDER_PATTERNS = [
    (r"\bTODO\s*[:\]]", "TODO marker"),
    (r"\bTBD\s*[:\]]", "TBD marker"),
    (r"\bFIXME\s*[:\]]", "FIXME marker"),
    (r"\bOWNER/REPO\b", "unresolved repository placeholder"),
    (r"<owner>/<repo>", "unresolved repository placeholder"),
    (r"\[CUSTOM_[A-Z_]+\]", "unresolved custom placeholder"),
    (r"\blorem ipsum\b", "lorem ipsum filler"),
]

SECRET_PATTERNS = [
    (r"-----BEGIN [A-Z ]*PRIVATE KEY-----", "private key material"),
    (r"\bgh[pousr]_[A-Za-z0-9]{36,}\b", "GitHub token"),
    (r"\bgithub_pat_[A-Za-z0-9_]{50,}\b", "GitHub fine-grained token"),
    (r"\bAKIA[0-9A-Z]{16}\b", "AWS access key"),
    (r"\bsk-[A-Za-z0-9_-]{20,}\b", "API secret key"),
    (r"\bxox[baprs]-[0-9A-Za-z-]{10,}\b", "Slack token"),
]

DANGEROUS_PATTERNS = [
    (r"\b(curl|wget)\b[^\n|]*\|\s*(bash|sh|zsh)\b", "error", "remote script piped to a shell"),
    (r"\brm\s+-rf\s+(/|~|\$HOME)\b", "warning", "recursive delete of a home or root path"),
    (r"\beval\s*\(", "warning", "dynamic code evaluation"),
    (r"--no" + r"-verify\b", "warning", "git hook bypass"),
]

MARKDOWN_LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)\s]+)(?:\s+[\"'][^\"']*[\"'])?\)")
FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
INLINE_CODE_RE = re.compile(r"`[^`\n]+`")
BARE_PATH_RE = re.compile(r"(?<![\w./-])((?:references|scripts|assets)/[A-Za-z0-9_./-]+)")


@dataclass
class Finding:
    severity: str
    code: str
    message: str
    file: str = ""
    line: int = 0

    def as_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
        }
        if self.file:
            data["file"] = self.file
        if self.line:
            data["line"] = self.line
        return data


@dataclass
class SkillReport:
    path: str
    name: str = ""
    findings: List[Finding] = field(default_factory=list)

    @property
    def errors(self) -> List[Finding]:
        return [f for f in self.findings if f.severity == "error"]

    @property
    def warnings(self) -> List[Finding]:
        return [f for f in self.findings if f.severity == "warning"]

    @property
    def valid(self) -> bool:
        return not self.errors

    def as_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "name": self.name,
            "valid": self.valid,
            "errors": [f.as_dict() for f in self.errors],
            "warnings": [f.as_dict() for f in self.warnings],
        }


def _read(path: Path) -> str:
    text = path.read_text(encoding="utf-8", errors="replace")
    return text.replace("\r\n", "\n").replace("\r", "\n").lstrip("\ufeff")


def _strip_comment(value: str) -> str:
    in_single = in_double = False
    for index, char in enumerate(value):
        if char == "'" and not in_double:
            in_single = not in_single
        elif char == '"' and not in_single:
            in_double = not in_double
        elif char == "#" and not in_single and not in_double:
            if index == 0 or value[index - 1].isspace():
                return value[:index].rstrip()
    return value.rstrip()


def _scalar(raw: str) -> str:
    value = _strip_comment(raw).strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
        inner = value[1:-1]
        if value[0] == "'":
            return inner.replace("''", "'")
        return inner.replace('\\"', '"').replace("\\n", "\n")
    return value


def parse_yaml_subset(text: str) -> Tuple[Dict[str, Any], List[str]]:
    """Parse the flat and one-level-nested YAML used by SKILL.md frontmatter."""
    data: Dict[str, Any] = {}
    errors: List[str] = []
    lines = text.split("\n")
    index = 0

    while index < len(lines):
        line = lines[index]
        if not line.strip() or line.lstrip().startswith("#"):
            index += 1
            continue
        if line.startswith((" ", "\t")):
            errors.append(f"line {index + 1}: unexpected indentation")
            index += 1
            continue

        match = re.match(r"^([A-Za-z0-9_.-]+):(.*)$", line)
        if not match:
            errors.append(f"line {index + 1}: expected 'key: value'")
            index += 1
            continue

        key, rest = match.group(1), match.group(2).strip()
        if rest in {"|", ">", "|-", ">-", "|+", ">+"}:
            block: List[str] = []
            index += 1
            while index < len(lines) and (
                not lines[index].strip() or lines[index].startswith((" ", "\t"))
            ):
                if lines[index].strip():
                    block.append(lines[index].strip())
                index += 1
            data[key] = "\n".join(block) if rest.startswith("|") else " ".join(block)
            continue

        if rest == "":
            nested: Dict[str, str] = {}
            index += 1
            while index < len(lines):
                child = lines[index]
                if not child.strip():
                    index += 1
                    continue
                if not child.startswith((" ", "\t")):
                    break
                child_match = re.match(r"^\s+([A-Za-z0-9_.-]+):(.*)$", child)
                if not child_match:
                    errors.append(f"line {index + 1}: cannot parse nested mapping entry")
                    index += 1
                    continue
                nested[child_match.group(1)] = _scalar(child_match.group(2))
                index += 1
            data[key] = nested
            continue

        data[key] = _scalar(rest)
        index += 1

    return data, errors


def split_frontmatter(text: str) -> Tuple[Optional[str], str]:
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return None, text
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            return "\n".join(lines[1:index]), "\n".join(lines[index + 1:])
    return None, text


def parse_frontmatter(text: str) -> Tuple[Optional[Dict[str, Any]], str, List[str]]:
    raw, body = split_frontmatter(text)
    if raw is None:
        return None, body, ["missing or unterminated YAML frontmatter"]

    try:
        import yaml  # type: ignore
    except ImportError:
        data, errors = parse_yaml_subset(raw)
        return data, body, errors

    try:
        loaded = yaml.safe_load(raw)
    except Exception as exc:  # PyYAML raises several parser subclasses.
        return None, body, [f"invalid YAML frontmatter: {exc}"]
    if loaded is None:
        return {}, body, []
    if not isinstance(loaded, dict):
        return None, body, ["frontmatter must be a YAML mapping"]
    return loaded, body, []


def _line_of(text: str, needle: str) -> int:
    for number, line in enumerate(text.split("\n"), start=1):
        if needle in line:
            return number
    return 0


def _relative(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _iter_text_files(skill_dir: Path) -> Iterable[Path]:
    for path in sorted(skill_dir.rglob("*")):
        if not path.is_file():
            continue
        if any(part in SKIP_PARTS for part in path.parts):
            continue
        if path.suffix.lower() in TEXT_SUFFIXES:
            yield path


def _check_references(skill_dir: Path, markdown: Path, text: str, report: SkillReport) -> None:
    clean = FENCE_RE.sub("", text)
    clean = INLINE_CODE_RE.sub("", clean)
    relative_markdown = _relative(markdown, skill_dir)

    for match in MARKDOWN_LINK_RE.finditer(clean):
        target = unquote(match.group(1).split("#", 1)[0].strip())
        if not target or target.startswith(("http://", "https://", "mailto:", "#")):
            continue
        if target.startswith("/"):
            report.findings.append(
                Finding("error", "reference.absolute", f"Use a relative link instead of '{target}'",
                        relative_markdown, _line_of(text, match.group(0)))
            )
            continue
        if not (skill_dir / target).exists():
            report.findings.append(
                Finding("error", "reference.missing", f"Linked file does not exist: {target}",
                        relative_markdown, _line_of(text, match.group(0)))
            )

    bare_checked: set[str] = set()
    for match in BARE_PATH_RE.finditer(clean):
        target = match.group(1).rstrip(".,);:")
        if target in bare_checked or not Path(target).suffix:
            continue
        bare_checked.add(target)
        if not (skill_dir / target).exists():
            report.findings.append(
                Finding("warning", "reference.bare_missing",
                        f"Path mentioned but not found: {target}",
                        relative_markdown, _line_of(text, match.group(0)))
            )


def _scan_text(skill_dir: Path, path: Path, report: SkillReport) -> None:
    text = _read(path)
    relative = _relative(path, skill_dir)
    lines = text.split("\n")

    for number, line in enumerate(lines, start=1):
        for pattern, label in SECRET_PATTERNS:
            if re.search(pattern, line):
                report.findings.append(
                    Finding("error", "security.secret", f"Possible {label} in skill content",
                            relative, number)
                )
        for pattern, severity, label in DANGEROUS_PATTERNS:
            if re.search(pattern, line, flags=re.IGNORECASE):
                report.findings.append(
                    Finding(severity, "security.command", f"Suspicious command: {label}", relative, number)
                )
        for pattern, label in PLACEHOLDER_PATTERNS:
            if re.search(r'^\s*\(?r["\']', line):
                break
            if re.search(pattern, line, flags=re.IGNORECASE):
                report.findings.append(
                    Finding("warning", "content.placeholder", f"Unfinished {label}", relative, number)
                )


def audit_skill(target: Path) -> SkillReport:
    """Audit a skill directory or a SKILL.md path."""
    target = target.resolve()
    skill_dir = target if target.is_dir() else target.parent
    skill_md = skill_dir / "SKILL.md" if target.is_dir() else target
    report = SkillReport(path=_relative(skill_dir, Path.cwd()) or skill_dir.name)
    report.name = skill_dir.name

    if not skill_md.is_file():
        report.findings.append(Finding("error", "structure.skill_md", "SKILL.md is missing", "SKILL.md"))
        return report

    text = _read(skill_md)
    frontmatter, body, parse_errors = parse_frontmatter(text)
    for error in parse_errors:
        report.findings.append(Finding("error", "frontmatter.parse", error, "SKILL.md"))

    if frontmatter is None:
        frontmatter = {}

    raw_name = frontmatter.get("name")
    name = raw_name.strip() if isinstance(raw_name, str) else ""
    if isinstance(raw_name, str) and name:
        report.name = name

    if not name:
        report.findings.append(Finding("error", "frontmatter.name", "Required field 'name' is missing or empty", "SKILL.md"))
    else:
        if len(name) > NAME_MAX:
            report.findings.append(Finding("error", "frontmatter.name", f"Name exceeds {NAME_MAX} characters", "SKILL.md"))
        if not NAME_RE.match(name):
            report.findings.append(
                Finding("error", "frontmatter.name",
                        "Name must be lowercase letters, digits, and single hyphens, and must not start or end with a hyphen",
                        "SKILL.md")
            )
        if name != skill_dir.name:
            report.findings.append(
                Finding("error", "frontmatter.name",
                        f"Name '{name}' must match the parent directory name '{skill_dir.name}'", "SKILL.md")
            )

    description = frontmatter.get("description")
    if not isinstance(description, str) or not description.strip():
        report.findings.append(
            Finding("error", "frontmatter.description", "Required field 'description' is missing or empty", "SKILL.md")
        )
    else:
        description = re.sub(r"\s+", " ", description).strip()
        if len(description) > DESCRIPTION_MAX:
            report.findings.append(
                Finding("error", "frontmatter.description",
                        f"Description exceeds {DESCRIPTION_MAX} characters ({len(description)})", "SKILL.md")
            )
        if len(description) < 40:
            report.findings.append(
                Finding("warning", "frontmatter.description",
                        "Description is short; state both the capability and the trigger conditions", "SKILL.md")
            )
        if not TRIGGER_RE.search(description):
            report.findings.append(
                Finding("warning", "frontmatter.description",
                        "Description does not say when to use the skill; add explicit trigger conditions", "SKILL.md")
            )

    compatibility = frontmatter.get("compatibility")
    if compatibility is not None:
        if not isinstance(compatibility, str) or not compatibility.strip():
            report.findings.append(
                Finding("error", "frontmatter.compatibility", "Field 'compatibility' must be a non-empty string", "SKILL.md")
            )
        elif len(compatibility) > COMPATIBILITY_MAX:
            report.findings.append(
                Finding("error", "frontmatter.compatibility",
                        f"'compatibility' exceeds {COMPATIBILITY_MAX} characters", "SKILL.md")
            )

    license_value = frontmatter.get("license")
    if license_value is not None and (not isinstance(license_value, str) or not license_value.strip()):
        report.findings.append(
            Finding("error", "frontmatter.license", "Field 'license' must be a non-empty string when present", "SKILL.md")
        )

    metadata = frontmatter.get("metadata")
    if metadata is not None:
        if not isinstance(metadata, dict):
            report.findings.append(Finding("error", "frontmatter.metadata", "Field 'metadata' must be a mapping", "SKILL.md"))
        else:
            for key, value in metadata.items():
                if not isinstance(value, str):
                    report.findings.append(
                        Finding("warning", "frontmatter.metadata",
                                f"Metadata value for '{key}' is not a string; quote it to stay spec-compliant", "SKILL.md")
                    )

    allowed_tools = frontmatter.get("allowed-tools")
    if allowed_tools is not None and not isinstance(allowed_tools, str):
        report.findings.append(
            Finding("error", "frontmatter.allowed_tools", "'allowed-tools' must be a space-separated string", "SKILL.md")
        )

    if not body.strip():
        report.findings.append(Finding("error", "content.empty", "SKILL.md has no instruction body", "SKILL.md"))
    else:
        if not re.search(r"^#\s+\S", body, flags=re.MULTILINE):
            report.findings.append(Finding("warning", "content.title", "Add a top-level H1 title to the body", "SKILL.md"))
        if "## Use When" not in body and "## When to Use" not in body:
            report.findings.append(
                Finding("warning", "content.activation",
                        "Add a 'Use When' section so the skill is not triggered too broadly", "SKILL.md")
            )
        line_count = len(text.split("\n"))
        if line_count > SKILL_LINE_ERROR:
            report.findings.append(
                Finding("error", "content.length",
                        f"SKILL.md has {line_count} lines; split detail into references/ (hard limit {SKILL_LINE_ERROR})",
                        "SKILL.md")
            )
        elif line_count > SKILL_LINE_WARNING:
            report.findings.append(
                Finding("warning", "content.length",
                        f"SKILL.md has {line_count} lines; aim for at most {SKILL_LINE_WARNING}", "SKILL.md")
            )
        headings: Dict[str, int] = {}
        for line in body.split("\n"):
            if line.startswith("#"):
                headings[line.strip().lower()] = headings.get(line.strip().lower(), 0) + 1
        duplicates = [heading for heading, count in headings.items() if count > 1]
        if duplicates:
            report.findings.append(
                Finding("warning", "content.duplicate_heading",
                        f"Duplicate heading: {duplicates[0]}", "SKILL.md")
            )
        _check_references(skill_dir, skill_md, body, report)

    for path in _iter_text_files(skill_dir):
        _scan_text(skill_dir, path, report)

    return report


def _print_text(reports: Sequence[SkillReport]) -> None:
    total_errors = total_warnings = 0
    for report in reports:
        total_errors += len(report.errors)
        total_warnings += len(report.warnings)
        status = "PASS" if report.valid else "FAIL"
        print(f"{status}  {report.path}  (name: {report.name})")
        for finding in report.errors + report.warnings:
            location = finding.file or "SKILL.md"
            if finding.line:
                location += f":{finding.line}"
            print(f"  {finding.severity.upper():7} {location}  {finding.code}  {finding.message}")
    print(f"\n{len(reports)} skill(s), {total_errors} error(s), {total_warnings} warning(s)")


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate Agent Skills against the Agent Skills specification.",
        epilog="Example: python3 audit_skill.py skills/reflex skills/skill-audit",
    )
    parser.add_argument("paths", nargs="+", help="Skill directories or SKILL.md files")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero when warnings are present")
    parser.add_argument("--quiet", action="store_true", help="Suppress per-finding text output and print only the summary")
    args = parser.parse_args(argv)

    reports: List[SkillReport] = []
    for raw_path in args.paths:
        path = Path(raw_path)
        if not path.exists():
            print(f"error: path not found: {raw_path}", file=sys.stderr)
            return 2
        reports.append(audit_skill(path))

    if args.json:
        payload = {
            "valid": not any(not report.valid for report in reports),
            "skills": [report.as_dict() for report in reports],
        }
        print(json.dumps(payload, indent=2))
    elif args.quiet:
        errors = sum(len(report.errors) for report in reports)
        warnings = sum(len(report.warnings) for report in reports)
        valid = all(report.valid for report in reports)
        print(f"{'PASS' if valid else 'FAIL'}: {len(reports)} skill(s), {errors} error(s), {warnings} warning(s)")
    else:
        _print_text(reports)

    has_errors = any(not report.valid for report in reports)
    has_warnings = any(report.warnings for report in reports)
    return 1 if has_errors or (args.strict and has_warnings) else 0


if __name__ == "__main__":
    sys.exit(main())
