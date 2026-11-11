#!/usr/bin/env python3
"""Scaffold a spec-compliant Agent Skill directory.

Creates <root>/<name>/SKILL.md with valid frontmatter and a workflow skeleton.
Refuses to overwrite an existing skill unless --force is passed.

Exit codes:
    0  skill created (or printed with --dry-run)
    1  invalid input or existing target without --force
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Optional, Sequence

NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
NAME_MAX = 64
DESCRIPTION_MAX = 1024

BODY_TEMPLATE = """# {title}

## Use When

- State the concrete request, file type, or operation that should activate this skill.
- Add a second trigger only when it needs a different workflow.

## Do Not Use When

- State the nearest task that belongs to another skill or to no skill.
- State any destructive or out-of-scope case.

## Inputs

- Required: the information the agent must have before starting.
- Optional: the information that changes the output when present.

## Workflow

1. Inspect the available inputs and state any assumption that affects the result.
2. Perform the first deterministic action.
3. Perform the next action and record its output.
4. Validate the result against an observable check.

## Outputs

- Primary artifact: path, format, and completion criteria.
- Report: what changed, what was verified, and what was not run.

## Error Handling

- Missing input: ask for the smallest missing decision, then stop.
- Failed check: report the exact command and error, fix the cause, and rerun.
- Unsupported environment: state the requirement instead of simulating success.

## Quality Checks

- Every command and path in this skill exists in the target environment.
- The result was inspected, not only assumed.
- Tests that could not run are reported as not run.
"""

MINIMAL_TEMPLATE = """# {title}

## Use When

- State the concrete request that should activate this skill.

## Workflow

1. Describe the first deterministic action.
2. Describe the final action and its verification.

## Outputs

- State the artifact and how completion is confirmed.
"""


def validate_inputs(name: str, description: str) -> list[str]:
    errors: list[str] = []
    if not name:
        errors.append("Skill name is required.")
    elif len(name) > NAME_MAX:
        errors.append(f"Skill name exceeds {NAME_MAX} characters.")
    elif not NAME_RE.match(name):
        errors.append(
            "Skill name must use lowercase letters, digits, and single hyphens, "
            "and must not start or end with a hyphen."
        )

    description = re.sub(r"\s+", " ", description).strip()
    if not description:
        errors.append("Description is required.")
    elif len(description) > DESCRIPTION_MAX:
        errors.append(f"Description exceeds {DESCRIPTION_MAX} characters.")
    return errors


def render_body(name: str, minimal: bool) -> str:
    title = " ".join(part.capitalize() for part in name.split("-"))
    template = MINIMAL_TEMPLATE if minimal else BODY_TEMPLATE
    return template.format(title=title)


def scaffold(
    name: str,
    description: str,
    root: Path,
    force: bool = False,
    minimal: bool = False,
    dry_run: bool = False,
) -> Path:
    description = re.sub(r"\s+", " ", description).strip()
    target = root / name
    skill_md = target / "SKILL.md"

    if target.exists() and not force:
        raise FileExistsError(f"Target already exists: {target}. Pass --force to overwrite SKILL.md.")
    if target.exists() and not target.is_dir():
        raise FileExistsError(f"Target exists and is not a directory: {target}")

    content = (
        "---\n"
        f"name: {name}\n"
        f"description: {description}\n"
        "---\n\n"
        f"{render_body(name, minimal)}"
    )

    if dry_run:
        return skill_md

    target.mkdir(parents=True, exist_ok=True)
    skill_md.write_text(content, encoding="utf-8", newline="\n")
    return skill_md


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Create a new Agent Skill directory with a compliant SKILL.md.",
        epilog='Example: python3 scaffold_skill.py pdf-tools --description "Extract text from PDFs. Use when the user mentions PDFs or forms."',
    )
    parser.add_argument("name", help="Skill name in lowercase kebab-case")
    parser.add_argument("--description", required=True, help="What the skill does and when to use it")
    parser.add_argument("--root", default="skills", help="Directory that holds skills (default: skills)")
    parser.add_argument("--minimal", action="store_true", help="Write a short skeleton instead of the full one")
    parser.add_argument("--force", action="store_true", help="Overwrite SKILL.md in an existing directory")
    parser.add_argument("--dry-run", action="store_true", help="Validate and print the target path without writing")
    args = parser.parse_args(argv)

    errors = validate_inputs(args.name, args.description)
    if errors:
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        return 1

    try:
        skill_md = scaffold(
            args.name,
            args.description,
            Path(args.root),
            force=args.force,
            minimal=args.minimal,
            dry_run=args.dry_run,
        )
    except (FileExistsError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    verb = "Would create" if args.dry_run else "Created"
    print(f"{verb} {skill_md}")
    if not args.dry_run:
        print("Next: complete the body, then validate the skill with an Agent Skills auditor.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
