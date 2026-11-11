---
name: skill-audit
description: Audit an Agent Skill for specification compliance, trigger quality, broken references, and security risks. Use when the user asks to review, validate, lint, or debug a SKILL.md, asks why a skill is not discovered or activated, or wants a pre-publish quality report for a skill directory.
license: MIT
metadata:
  author: heloIJS
  version: "1.0.0"
---

# Skill Audit

Audit one skill directory or a whole catalog, then report findings with a severity and a concrete fix. The audit is deterministic: the same input produces the same findings.

## Use When

- The user asks to validate, lint, review, or audit a skill.
- A skill is not discovered, not installed, or not activating when expected.
- A contribution is about to be published and needs a pre-merge quality gate.
- A skill was copied from another repository and may contain broken references.

## Do Not Use When

- The task is to write a new skill from scratch; use `skill-authoring` instead.
- The user only wants a content rewrite with no compliance question.
- The target is a general codebase, not an Agent Skill.

## What the Auditor Checks

| Level | Checks |
| --- | --- |
| Structure | `SKILL.md` exists, frontmatter parses, required fields present, name format, name matches directory, duplicates across a catalog |
| Content | Description states capability and trigger, body has a title and activation section, `SKILL.md` stays under the line budget, headings are unique |
| References | Every relative markdown link resolves, mentioned `references/`, `scripts/`, and `assets/` paths exist |
| Security | Private keys and tokens, remote scripts piped to a shell, destructive deletes, dynamic evaluation, hook bypasses, unfinished placeholders |

The auditor does not judge domain accuracy. Read the skill body for correctness after the deterministic checks pass.

## Workflow

### 1. Locate the targets

Find each skill directory: a folder containing `SKILL.md`. In a catalog, expect `skills/<name>/SKILL.md`.

### 2. Run the deterministic audit

From the skill directory that contains the script:

```bash
python3 scripts/audit_skill.py path/to/skill
```

For several skills or a whole catalog:

```bash
python3 scripts/audit_skill.py skills/reflex skills/skill-audit --json
```

Use `--strict` when warnings should fail the gate. Use `--quiet` for a one-line summary.

### 3. Triage every finding

Read the severity, not the count:

- **error**: blocks spec compliance or hides a security risk. Fix before publishing.
- **warning**: quality risk or missing guidance. Fix when practical; do not suppress it silently.
- **info** in JSON output: context only, no action required.

Do not downgrade an error to make a build pass. Fix the cause or explain why the check is a false positive.

### 4. Review the instruction content

The script cannot judge whether the workflow is correct. Read the skill and verify:

1. The description names both the capability and the exact trigger conditions.
2. The workflow steps are ordered, imperative, and testable.
3. Every command, flag, and path exists in the target environment.
4. Failure cases say what to do, not only what can go wrong.
5. The skill does not claim tools or APIs its target agent does not provide.

### 5. Inspect before executing bundled code

Treat skill scripts as untrusted until inspected. Read the file, check network calls, filesystem writes, and subprocess usage. Run only code that is safe in the current environment. Never pipe a remote script into a shell.

### 6. Fix only what was requested

If the user asked for a review, report findings without editing. If the user asked to fix, patch the smallest region and rerun the audit. Preserve unrelated content.

### 7. Report

Return a compact table, then the verdict:

```markdown
| Severity | Location | Problem | Fix |
| --- | --- | --- | --- |
| error | SKILL.md | Description has no trigger conditions | Add "Use when ..." with concrete keywords |
| warning | scripts/run.py:14 | `eval` on user input | Replace with an explicit parser |

Verdict: FAIL (1 error, 1 warning)
```

State explicitly which checks ran and which did not. If a test could not execute, say so; never report unrun tests as passed.

## Severity Policy

| Verdict | Condition |
| --- | --- |
| PASS | No errors, warnings reviewed |
| PASS WITH WARNINGS | No errors, warnings accepted with a reason |
| FAIL | At least one error, or warnings under `--strict` |

## Error Handling

- **Path missing**: report the path and stop; do not guess a nearby skill.
- **Unreadable or malformed frontmatter**: report the parser message and line, then ask for the raw block if the fix is ambiguous.
- **PyYAML unavailable**: the script falls back to a built-in parser for flat and one-level mappings. Complex YAML needs PyYAML installed; report that limitation instead of claiming a pass.
- **Script refuses to run**: inspect the interpreter and file permissions. Do not rewrite the audit to bypass a failure.
- **Finding looks wrong**: reproduce with the smallest fixture, then update the check and its test together.

## Quality Checks

- Every reported finding includes a file and, when available, a line.
- The verdict matches the exit code: `0` for no errors, `1` for errors.
- The report separates deterministic findings from human content review.
- Any executed bundled script was inspected first.

## References

- [Audit rubric](references/audit-rubric.md): full check list, spec constraints, severity definitions, and report template.
