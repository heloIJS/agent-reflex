#!/usr/bin/env python3
"""reflex_engine.py - deterministic linter, auditor, and skill patcher for Reflex.

Commands:
  lint   Validate a Trigger -> Action -> Verification (TAV) reflex rule.
  audit  Validate a SKILL.md against structural and quality rules.
  patch  Insert or replace a reflex rule in a target SKILL.md.

All commands emit JSON. A non-zero exit code means validation failed.
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import pathlib
import re
import shutil
import sys
import tempfile
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

RULE_WORD_LIMIT = 55
SKILL_LINE_LIMIT = 500
SKILL_WORD_GUIDANCE = 9000
DESCRIPTION_LIMIT = 1024
DESCRIPTION_MIN = 20
LEARNED_RULE_LIMIT = 10

VAGUE_PATTERNS = [
    r"\bbe careful\b",
    r"\btry to\b",
    r"\bmake sure\b",
    r"\bdon't forget\b",
    r"\bremember to\b",
    r"\bas needed\b",
    r"\bif appropriate\b",
    r"\bcheck that everything\b",
]

WEAK_VERIFY_PATTERNS = [
    r"\blooks? (ok|good|right|correct)\b",
    r"\bseems? (ok|good|right|correct)\b",
    r"\bmanually inspect\b",
    r"\bcheck visually\b$",
]

SESSION_PATH_PATTERNS = [
    r"/working_dir/[^\s)]+",
    r"/mnt/agents/[^\s)]+",
    r"\binput_file_\d+\b",
    r"\bwatermarked_img_[^\s)]+",
    r"/tmp/[^\s)]+",
]

SECRET_PATTERNS = [
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
    r"\b[A-Za-z0-9_-]{24}\.[A-Za-z0-9_-]{6}\.[A-Za-z0-9_-]{27}\b",
    r"\bsk-[A-Za-z0-9_-]{20,}\b",
    r"\bAKIA[0-9A-Z]{16}\b",
    r"\bgh[pousr]_[A-Za-z0-9]{36,}\b",
]


@dataclass(frozen=True)
class RuleParts:
    trigger: str
    action: str
    verify: str


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip()).rstrip(".")


def _read_text(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")


def format_rule(parts: RuleParts) -> str:
    return (
        f"- **WHEN** {parts.trigger}, **DO** {parts.action}; "
        f"**VERIFY** by {parts.verify}."
    )


def parse_tav_rule(rule_text: str) -> RuleParts:
    """Parse a one-line TAV rule: `- **WHEN** ..., **DO** ...; **VERIFY** by ...`."""
    text = rule_text.strip()
    if not text.startswith("- "):
        raise ValueError("Rule must be a Markdown bullet starting with '- '.")
    text = text[2:].strip()

    match = re.match(
        r"^\*\*WHEN\*\*\s*(.*?),\s*\*\*DO\*\*\s*(.*?);\s*\*\*VERIFY\*\*\s*by\s*(.*)\.?$",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        raise ValueError("Rule must match: **WHEN** ..., **DO** ...; **VERIFY** by ...")
    return RuleParts(_clean(match.group(1)), _clean(match.group(2)), _clean(match.group(3)))


def lint_rule_parts(parts: RuleParts) -> Tuple[bool, List[str], str]:
    errors: List[str] = []
    rule = format_rule(parts)
    words = len(rule.split())

    if len(parts.trigger.split()) < 3:
        errors.append("Trigger is too short; name the context, operation, or file condition.")
    if len(parts.action.split()) < 4:
        errors.append("Action is too short; use an imperative command and include one reason.")
    if len(parts.verify.split()) < 3:
        errors.append("Verification is too short; use a command, assertion, or observable check.")

    if words > RULE_WORD_LIMIT:
        errors.append(f"Rule has {words} words; limit is {RULE_WORD_LIMIT}.")

    combined = " ".join([parts.trigger, parts.action, parts.verify])
    for pattern in VAGUE_PATTERNS:
        if re.search(pattern, combined, flags=re.IGNORECASE):
            errors.append(f"Vague phrase detected: /{pattern}/. Replace it with a concrete instruction.")
    for pattern in SESSION_PATH_PATTERNS:
        if re.search(pattern, combined):
            errors.append(f"Session-specific path detected: {pattern}. Generalize the rule.")
    for pattern in SECRET_PATTERNS:
        if re.search(pattern, combined):
            errors.append("Possible secret or credential detected. Remove it before saving.")
    for pattern in WEAK_VERIFY_PATTERNS:
        if re.search(pattern, parts.verify, flags=re.IGNORECASE):
            errors.append("Verification is observational only. Add a command, threshold, assertion, or negative test.")

    if re.search(r"\b(nothing|none|no check|skip verification)\b", parts.verify, flags=re.IGNORECASE):
        errors.append("Verification must not be empty or skipped.")

    return not errors, errors, rule


def lint_rule_text(rule_text: str) -> Tuple[bool, List[str], str]:
    try:
        parts = parse_tav_rule(rule_text)
    except ValueError as exc:
        return False, [str(exc)], rule_text.strip()
    return lint_rule_parts(parts)


def _frontmatter(text: str) -> Optional[str]:
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---\n", 4)
    return None if end == -1 else text[4:end]


def _field(frontmatter: str, name: str) -> Optional[str]:
    lines = frontmatter.split("\n")
    for index, line in enumerate(lines):
        match = re.match(rf"^{re.escape(name)}:\s*(.*?)\s*$", line)
        if not match:
            continue

        value = match.group(1).strip()
        if value in {"|", ">", "|-", ">-", "|+", ">+"}:
            block: List[str] = []
            for child in lines[index + 1:]:
                if child.strip() and not child.startswith((" ", "\t")):
                    break
                if child.strip():
                    block.append(child.strip())
                elif block:
                    block.append("")
            result = "\n".join(block).rstrip()
            return " ".join(result.split()) if value.startswith(">") else result

        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
            if line.lstrip().startswith(name + ": \""):
                value = value.replace("\\\"", "\"").replace("\\n", "\n")
            elif line.lstrip().startswith(name + ": '"):
                value = value.replace("''", "'")
        return value or None
    return None


def audit_skill_md(path: pathlib.Path, content: Optional[str] = None) -> Tuple[bool, List[str], Dict[str, object]]:
    """Audit a SKILL.md. Returns (ok, messages, stats); warnings are prefixed."""
    errors: List[str] = []
    warnings: List[str] = []
    if content is None and not path.exists():
        return False, [f"File not found: {path}"], {}

    text = content if content is not None else _read_text(path)
    lines = text.split("\n")
    fm = _frontmatter(text)

    if len(lines) > SKILL_LINE_LIMIT:
        errors.append(f"SKILL.md has {len(lines)} lines; keep it at or below {SKILL_LINE_LIMIT}.")
    if len(text.split()) > SKILL_WORD_GUIDANCE:
        warnings.append(f"SKILL.md is long ({len(text.split())} words); consider moving detail to references/.")

    if fm is None:
        errors.append("Missing or malformed YAML frontmatter.")
    else:
        name = _field(fm, "name")
        description = _field(fm, "description")
        if not name:
            errors.append("Frontmatter missing required 'name' field.")
        else:
            if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name) or len(name) > 64:
                errors.append("Skill name must be lowercase kebab-case and at most 64 characters.")
            elif name != path.parent.name:
                errors.append(f"Skill name '{name}' must match its directory '{path.parent.name}'.")
        if not description:
            errors.append("Frontmatter missing required 'description' field.")
        elif not (DESCRIPTION_MIN <= len(description) <= DESCRIPTION_LIMIT):
            errors.append(f"Description must be {DESCRIPTION_MIN}-{DESCRIPTION_LIMIT} characters.")
        elif not re.search(r"\b(use when|use for|use this|when the user|invoke when)\b", description, re.IGNORECASE):
            warnings.append("Description does not state when to use the skill.")

    if not re.search(r"^#\s+", text, flags=re.MULTILINE):
        errors.append("SKILL.md needs a top-level H1 title.")
    if "## When to Use" not in text and "## Use When" not in text:
        warnings.append("Add an explicit activation section so the skill is not triggered too broadly.")

    learned = [line for line in lines if line.lstrip().startswith("- **WHEN**")]
    seen: Dict[str, int] = {}
    for line in learned:
        normalized = re.sub(r"\s+", " ", line.lower())
        seen[normalized] = seen.get(normalized, 0) + 1
    if any(count > 1 for count in seen.values()):
        errors.append("Duplicate learned reflex bullets detected.")

    if re.search(r"\b(input_file_\d+|/tmp/|/working_dir/)\b", text):
        warnings.append("Possible session-specific path found in skill content.")

    stats = {
        "file": str(path),
        "lines": len(lines),
        "words": len(text.split()),
        "learned_rules": len(learned),
        "valid": not errors,
    }
    return not errors, errors + [f"WARNING: {warning}" for warning in warnings], stats


def _find_section_bounds(content: str, section: str) -> Tuple[int, int]:
    match = re.search(rf"^##\s+{re.escape(section)}\s*$", content, flags=re.MULTILINE)
    if not match:
        return -1, -1
    following = re.search(r"^##\s+", content[match.end():], flags=re.MULTILINE)
    end = match.end() + following.start() if following else len(content)
    return match.start(), end


def _insert_rule(content: str, section: str, rule: str, replace_match: str = "") -> Tuple[str, str]:
    heading = f"## {section}"
    if replace_match:
        start, end = _find_section_bounds(content, section)
        section_content = content[start:end] if start >= 0 else ""
        pattern = re.compile(
            rf"^(?P<indent>[ \t]*)- .*{re.escape(replace_match)}.*$",
            flags=re.MULTILINE,
        )
        match = pattern.search(section_content)
        if match:
            indent = match.group("indent")
            replaced = pattern.sub(indent + rule, section_content, count=1)
            return content[:start] + replaced + content[end:], "replaced"

    if heading not in content:
        return content.rstrip() + f"\n\n{heading}\n\n{rule}\n", "created_section"

    start, end = _find_section_bounds(content, section)
    section_text = content[start:end]
    if rule in section_text:
        return content, "already_present"

    insertion = end
    while insertion > start and content[insertion - 1].isspace():
        insertion -= 1
    prefix = content[:insertion].rstrip()
    suffix = content[insertion:].lstrip("\n")
    if suffix:
        updated = f"{prefix}\n{rule}\n\n{suffix}"
    else:
        updated = f"{prefix}\n{rule}\n"
    return updated, "appended"


def _atomic_write(path: pathlib.Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def patch_skill_md(
    path: pathlib.Path,
    trigger: str,
    action: str,
    verify: str,
    section: str = "Learned Reflexes",
    replace_match: str = "",
    dry_run: bool = False,
    backup: bool = True,
) -> Tuple[bool, List[str], Dict[str, object]]:
    ok, errors, rule = lint_rule_parts(RuleParts(trigger, action, verify))
    result: Dict[str, object] = {"rule": rule, "dry_run": dry_run}
    if not ok:
        result["errors"] = errors
        return False, errors, result
    if not path.exists():
        errors = [f"Target file does not exist: {path}"]
        result["errors"] = errors
        return False, errors, result

    before = _read_text(path)
    after, action_taken = _insert_rule(before, section, rule, replace_match)
    result["action"] = action_taken

    if action_taken == "already_present":
        result["audit"] = audit_skill_md(path, content=before)[2]
        result["audit_messages"] = []
        return True, [], result

    section_start, section_end = _find_section_bounds(after, section)
    if section_start >= 0:
        learned = [
            line for line in after[section_start:section_end].splitlines()
            if line.lstrip().startswith("- **WHEN**")
        ]
        if len(learned) > LEARNED_RULE_LIMIT:
            errors = [
                f"Section '## {section}' has {len(learned)} rules; limit is {LEARNED_RULE_LIMIT}. "
                "Consolidate overlapping rules before adding another."
            ]
            result["errors"] = errors
            return False, errors, result

    audit_ok, audit_messages, stats = audit_skill_md(path, content=after)
    result["audit"] = stats
    result["audit_messages"] = audit_messages
    if not audit_ok:
        result["errors"] = audit_messages
        return False, audit_messages, result

    if dry_run:
        result["diff"] = "\n".join(
            difflib.unified_diff(before.split("\n"), after.split("\n"), fromfile="before", tofile="after", lineterm="")
        )
        return True, audit_messages, result

    if after != before:
        if backup:
            shutil.copy2(path, path.with_suffix(path.suffix + ".bak"))
        _atomic_write(path, after)

    return True, audit_messages, result


def _add_common_lint_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--trigger", help="WHEN condition")
    parser.add_argument("--action", help="DO imperative action and one-clause reason")
    parser.add_argument("--verify", help="VERIFY observable command, assertion, or inspection")
    parser.add_argument("--rule", help="Full one-line TAV Markdown bullet")


def _parts_from_args(args: argparse.Namespace) -> RuleParts:
    if getattr(args, "rule", None):
        return parse_tav_rule(args.rule)
    missing = [name for name in ("trigger", "action", "verify") if not getattr(args, name)]
    if missing:
        raise ValueError(f"Missing required arguments: {', '.join('--' + name for name in missing)}")
    return RuleParts(_clean(args.trigger), _clean(args.action), _clean(args.verify))


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Reflex deterministic rule linter, auditor, and skill patcher.")
    parser.add_argument("--version", action="version", version="reflex-engine 1.0.0")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_lint = sub.add_parser("lint", help="Lint a TAV reflex rule.")
    _add_common_lint_args(p_lint)

    p_audit = sub.add_parser("audit", help="Audit a SKILL.md file.")
    p_audit.add_argument("path", type=pathlib.Path)

    p_patch = sub.add_parser("patch", help="Patch a target SKILL.md with a validated reflex rule.")
    p_patch.add_argument("path", type=pathlib.Path)
    _add_common_lint_args(p_patch)
    p_patch.add_argument("--section", default="Learned Reflexes", help="Section heading without '##'")
    p_patch.add_argument("--replace-match", default="", help="Substring of an old rule to replace in place")
    p_patch.add_argument("--dry-run", action="store_true", help="Print the diff without modifying the file")
    p_patch.add_argument("--no-backup", action="store_true", help="Do not create a .bak file before writing")

    args = parser.parse_args(argv)

    if args.cmd == "lint":
        try:
            parts = _parts_from_args(args)
        except ValueError as exc:
            print(json.dumps({"valid": False, "errors": [str(exc)]}, indent=2))
            return 1
        ok, errors, rule = lint_rule_parts(parts)
        print(json.dumps({"valid": ok, "formatted_rule": rule, "errors": errors}, indent=2))
        return 0 if ok else 1

    if args.cmd == "audit":
        ok, messages, stats = audit_skill_md(args.path)
        print(json.dumps({"valid": ok, "stats": stats, "messages": messages}, indent=2))
        return 0 if ok else 1

    if args.cmd == "patch":
        try:
            parts = _parts_from_args(args)
        except ValueError as exc:
            print(json.dumps({"valid": False, "errors": [str(exc)]}, indent=2))
            return 1
        ok, messages, result = patch_skill_md(
            args.path,
            parts.trigger,
            parts.action,
            parts.verify,
            section=args.section,
            replace_match=args.replace_match,
            dry_run=args.dry_run,
            backup=not args.no_backup,
        )
        print(json.dumps({"valid": ok, "result": result}, indent=2))
        return 0 if ok else 1

    return 1


if __name__ == "__main__":
    sys.exit(main())
