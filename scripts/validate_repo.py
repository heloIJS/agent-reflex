#!/usr/bin/env python3
"""Validate the agent-reflex repository.

Checks required files, Agent Skills compliance, unique names, README accuracy,
relative links, unresolved placeholders, workflow hardening, and forbidden files.

Run from any directory:
    python3 scripts/validate_repo.py

Exit code 0 means no errors. Warnings do not fail the build.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Iterable, List, Sequence
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
REPO_SLUG = "heloIJS/agent-reflex"
MAX_SKILL_LINES = 500

sys.path.insert(0, str(ROOT / "skills" / "skill-audit" / "scripts"))
try:
    from audit_skill import Finding, audit_skill  # type: ignore
except ImportError as exc:  # pragma: no cover - defensive
    print(f"error: cannot import the skill auditor: {exc}", file=sys.stderr)
    raise SystemExit(2)

REQUIRED_FILES = [
    "README.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "CHANGELOG.md",
    "LICENSE",
    ".gitignore",
    ".github/workflows/validate.yml",
    ".github/workflows/security.yml",
]

README_SECTIONS = [
    "## Features",
    "## Available skills",
    "## Installation",
    "## Usage",
    "## Supported agents",
    "## Repository structure",
    "## Creating custom skills",
    "## Quality and validation",
    "## Contributing",
    "## Security",
    "## License",
]

PLACEHOLDER_PATTERNS = [
    (r"\bTODO\b", "TODO marker"),
    (r"\bTBD\b", "TBD marker"),
    (r"\bFIXME\b", "FIXME marker"),
    (r"\[owner/repo\]", "owner/repo placeholder"),
    (r"\[CUSTOM_[A-Z_]+\]", "custom placeholder"),
    (r"\blorem ipsum\b", "filler text"),
]

TEXT_SUFFIXES = {".md", ".yml", ".yaml", ".json", ".py", ".txt"}
SKIP_DIRS = {".git", "__pycache__", ".venv", "venv", "node_modules", ".pytest_cache"}
LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)\s]+)(?:\s+[\"'][^\"']*[\"'])?\)")
FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
INLINE_CODE_RE = re.compile(r"`[^`\n]+`")


def finding(severity: str, code: str, message: str, file: str = "", line: int = 0) -> Finding:
    return Finding(severity, code, message, file, line)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n").replace("\r", "\n")


def _iter_files(root: Path, suffixes: Iterable[str]) -> Iterable[Path]:
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix.lower() in suffixes:
            yield path


def discover_skills(root: Path) -> List[Path]:
    skills_root = root / "skills"
    if not skills_root.is_dir():
        return []
    return sorted([path for path in skills_root.iterdir() if path.is_dir() and (path / "SKILL.md").is_file()])


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def check_required_files(root: Path) -> List[Finding]:
    findings: List[Finding] = []
    for name in REQUIRED_FILES:
        if not (root / name).is_file():
            findings.append(finding("error", "repo.required_file", f"Required file is missing: {name}"))
    return findings


def check_skills(root: Path) -> List[Finding]:
    findings: List[Finding] = []
    skills_root = root / "skills"
    if not skills_root.is_dir():
        return [finding("error", "repo.skills_dir", "skills/ directory is missing")]

    for entry in sorted(skills_root.iterdir()):
        if entry.is_dir() and not (entry / "SKILL.md").is_file():
            findings.append(
                finding("error", "repo.stray_dir", "Skill directory has no SKILL.md", _relative(entry, root))
            )

    skills = discover_skills(root)
    if not skills:
        return findings + [finding("error", "repo.no_skills", "No skills found under skills/")]

    names: dict[str, str] = {}
    for skill_dir in skills:
        report = audit_skill(skill_dir)
        relative = _relative(skill_dir, root)
        for item in report.findings:
            findings.append(item)
        line_count = len(_read(skill_dir / "SKILL.md").split("\n"))
        if line_count > MAX_SKILL_LINES:
            findings.append(
                finding("error", "repo.skill_length",
                        f"SKILL.md has {line_count} lines; keep it at or below {MAX_SKILL_LINES}",
                        _relative(skill_dir / "SKILL.md", root))
            )
        if report.name:
            if report.name in names:
                findings.append(
                    finding("error", "repo.duplicate_name",
                            f"Duplicate skill name '{report.name}' in {names[report.name]} and {relative}")
                )
            else:
                names[report.name] = relative

    return findings


def check_readme(root: Path) -> List[Finding]:
    findings: List[Finding] = []
    readme_path = root / "README.md"
    if not readme_path.is_file():
        return findings
    text = _read(readme_path)

    if not re.search(r"^#\s+\S", text, flags=re.MULTILINE):
        findings.append(finding("error", "readme.title", "README needs an H1 title", "README.md"))

    for section in README_SECTIONS:
        if section not in text:
            findings.append(finding("error", "readme.section", f"README is missing section: {section}", "README.md"))

    required_commands = [
        f"npx skills add {REPO_SLUG}",
        f"npx skills add {REPO_SLUG} --list",
        f"npx skills add {REPO_SLUG} --skill",
        "npx skills update",
    ]
    for command in required_commands:
        if command not in text:
            findings.append(
                finding("error", "readme.command", f"README is missing install command: {command}", "README.md")
            )

    for skill_dir in discover_skills(root):
        name = skill_dir.name
        link = f"skills/{name}/SKILL.md"
        if name not in text:
            findings.append(finding("error", "readme.skill_name", f"README does not name skill '{name}'", "README.md"))
        if link not in text:
            findings.append(finding("error", "readme.skill_link", f"README does not link to {link}", "README.md"))

    return findings


def check_links(root: Path) -> List[Finding]:
    findings: List[Finding] = []
    for path in _iter_files(root, {".md"}):
        text = _read(path)
        clean = INLINE_CODE_RE.sub("", FENCE_RE.sub("", text))
        relative_file = _relative(path, root)
        for match in LINK_RE.finditer(clean):
            target = unquote(match.group(1).split("#", 1)[0].strip())
            if not target or target.startswith(("http://", "https://", "mailto:", "tel:", "#")):
                continue
            if target.startswith("/"):
                findings.append(
                    finding("error", "repo.absolute_link", f"Use a relative link instead of '{target}'", relative_file)
                )
                continue
            resolved = (path.parent / target).resolve()
            if not resolved.exists():
                findings.append(finding("error", "repo.broken_link", f"Broken relative link: {target}", relative_file))
    return findings


def _placeholder_files(root: Path) -> Iterable[Path]:
    for name in ("README.md", "CONTRIBUTING.md", "SECURITY.md", "CHANGELOG.md"):
        path = root / name
        if path.is_file():
            yield path
    for pattern in ("examples/**/*.md", "skills/*/SKILL.md", ".github/**/*.md", ".github/**/*.yml"):
        for path in sorted(root.glob(pattern)):
            if path.is_file():
                yield path


def check_placeholders(root: Path) -> List[Finding]:
    findings: List[Finding] = []
    for path in _placeholder_files(root):
        text = _read(path)
        relative_file = _relative(path, root)
        for number, line in enumerate(text.split("\n"), start=1):
            for pattern, label in PLACEHOLDER_PATTERNS:
                if re.search(pattern, line, flags=re.IGNORECASE):
                    findings.append(
                        finding("error", "repo.placeholder", f"Unresolved {label}", relative_file, number)
                    )
    return findings


def check_workflows(root: Path) -> List[Finding]:
    findings: List[Finding] = []
    workflow_dir = root / ".github" / "workflows"
    for path in sorted(workflow_dir.glob("*.y*ml")):
        text = _read(path)
        relative_file = _relative(path, root)
        try:
            import yaml  # type: ignore

            document = yaml.load(text, Loader=yaml.BaseLoader)
            if not isinstance(document, dict):
                findings.append(finding("error", "ci.yaml_structure", "Workflow YAML must be a mapping", relative_file))
            elif not document.get("name") or not isinstance(document.get("jobs"), dict):
                findings.append(
                    finding("error", "ci.yaml_structure", "Workflow needs a name and jobs mapping", relative_file)
                )
            elif "on" not in document:
                findings.append(finding("error", "ci.yaml_structure", "Workflow needs an 'on' trigger", relative_file))
        except ImportError:
            findings.append(
                finding("error", "ci.yaml_validator", "Install PyYAML to validate workflow YAML syntax", relative_file)
            )
        except Exception as exc:
            findings.append(finding("error", "ci.yaml_syntax", f"Invalid workflow YAML: {exc}", relative_file))
        if "permissions:" not in text:
            findings.append(finding("error", "ci.permissions", "Workflow must declare least-privilege permissions", relative_file))
        if "pull_request_target" in text:
            findings.append(finding("error", "ci.pull_request_target", "Do not use pull_request_target", relative_file))
        for number, line in enumerate(text.split("\n"), start=1):
            match = re.search(r"^\s*(?:-\s*)?uses:\s*([^\s#]+)", line)
            if not match:
                continue
            reference = match.group(1)
            if reference.startswith("./"):
                continue
            if "@" not in reference:
                findings.append(finding("error", "ci.unpinned_action", f"Action is not pinned: {reference}", relative_file, number))
                continue
            revision = reference.rsplit("@", 1)[1]
            if not re.fullmatch(r"[0-9a-f]{40}", revision):
                findings.append(
                    finding("error", "ci.unpinned_action",
                            f"Pin the action to a full commit SHA: {reference}", relative_file, number)
                )
    return findings


def check_license_and_ignore(root: Path) -> List[Finding]:
    findings: List[Finding] = []
    license_path = root / "LICENSE"
    if license_path.is_file():
        text = _read(license_path)
        if "MIT License" not in text:
            findings.append(finding("error", "repo.license", "LICENSE does not contain the MIT License text", "LICENSE"))
        if "Copyright (c) 2026 heloIJS" not in text:
            findings.append(finding("error", "repo.license", "LICENSE copyright line is missing or outdated", "LICENSE"))

    ignore_path = root / ".gitignore"
    if ignore_path.is_file():
        text = _read(ignore_path)
        for entry in ("__pycache__/", "*.py[cod]", ".env", "node_modules/", "skills-lock.json"):
            if entry not in text:
                findings.append(finding("error", "repo.gitignore", f".gitignore is missing entry: {entry}", ".gitignore"))
    return findings


def check_forbidden_files(root: Path) -> List[Finding]:
    findings: List[Finding] = []
    forbidden_names = {".env", "skills-lock.json", "credentials.json", "id_rsa", "id_ed25519"}
    forbidden_suffixes = {".pem", ".key", ".pyc"}
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.name in forbidden_names or path.suffix.lower() in forbidden_suffixes:
            findings.append(finding("error", "repo.forbidden_file", "Do not commit secrets or generated artifacts", _relative(path, root)))
    return findings


def validate(root: Path = ROOT) -> List[Finding]:
    root = root.resolve()
    findings: List[Finding] = []
    findings.extend(check_required_files(root))
    findings.extend(check_skills(root))
    findings.extend(check_readme(root))
    findings.extend(check_links(root))
    findings.extend(check_placeholders(root))
    findings.extend(check_workflows(root))
    findings.extend(check_license_and_ignore(root))
    findings.extend(check_forbidden_files(root))
    return findings


def main(argv: Sequence[str] = ()) -> int:
    root = Path(argv[0]) if argv else ROOT
    if not root.is_dir():
        print(f"error: repository root not found: {root}", file=sys.stderr)
        return 2

    findings = validate(root)
    errors = [item for item in findings if item.severity == "error"]
    warnings = [item for item in findings if item.severity == "warning"]

    for item in errors + warnings:
        location = item.file or "-"
        if item.line:
            location += f":{item.line}"
        print(f"{item.severity.upper():7} {location}  {item.code}  {item.message}")

    print(f"\n{len(errors)} error(s), {len(warnings)} warning(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
