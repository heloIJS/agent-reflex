---
name: skill-authoring
description: Create or revise a reusable Agent Skill that complies with the Agent Skills specification. Use when the user asks to write a new skill, generate a SKILL.md, turn a workflow into a reusable skill, scaffold a skill directory, or fix a skill's frontmatter and description.
license: MIT
metadata:
  author: heloIJS
  version: "1.0.0"
---

# Skill Authoring

Turn a repeatable workflow into one focused, testable skill. A good skill is not a knowledge dump: it is a bounded procedure with a clear trigger, deterministic steps, a defined output, and honest failure handling.

## Use When

- The user asks for a new skill or a `SKILL.md`.
- An existing workflow should become reusable across sessions or projects.
- A skill description is too vague, so the skill never activates or activates too often.
- A skill needs references, scripts, or assets split out of an oversized body.

## Do Not Use When

- The task is only to review or lint an existing skill; use an auditor.
- The content is a one-off answer with no reusable procedure.
- The workflow depends on tools or data the target agent cannot access.

## Workflow

### 1. Decide whether a skill is the right unit

A skill is justified when all three are true:

1. The task is repeatable with recognizable trigger conditions.
2. The procedure has more than one step or a non-obvious ordering.
3. The agent needs domain rules, checks, or scripts it would not infer.

If the request is a single fact or a generic style preference, answer directly instead.

### 2. Gather the minimum facts

Collect these before writing:

- **Trigger**: the exact user phrases, file types, and operations that should activate the skill.
- **Inputs**: required and optional information, plus what to do when each is missing.
- **Steps**: the deterministic sequence, including tools and commands.
- **Output**: the artifact, format, location, and completion criteria.
- **Failure cases**: invalid input, missing dependency, partial result, and recovery.
- **Verification**: an observable check that can fail on a broken output.

If a missing decision changes the deliverable, ask up to three targeted questions. Do not interview the user about details you can inspect in the workspace.

### 3. Choose the name

Use lowercase kebab-case: `pdf-form-filler`, not `PDF_FormFiller`. The directory name must match the `name` field exactly. Prefer a capability noun phrase over a vague category: `release-notes` beats `docs-helper`.

### 4. Write the frontmatter

```yaml
---
name: example-skill
description: Do a specific task with a specific method. Use when the user asks for X, mentions Y, or works with Z files.
---
```

Rules:

- `name`: 1-64 characters, lowercase letters, digits, single hyphens, matches the directory.
- `description`: 1-1024 characters; state the capability first, then the triggers. Include the words a user would actually type.
- Add `license`, `compatibility`, `metadata`, or `allowed-tools` only when true and useful.
- Do not put secrets, internal URLs, or client names in `metadata`.

### 5. Scaffold the directory

Run the bundled script from this skill directory:

```bash
python3 scripts/scaffold_skill.py pdf-form-filler \
  --description "Fill and flatten PDF forms with field mapping. Use when the user mentions PDF forms, AcroForm, or form fields."
```

Use `--root skills` to place it in a catalog, `--minimal` for a short skeleton, and `--force` only when replacing a known file. The script refuses to overwrite without `--force`.

### 6. Write the instruction body

Use this order, omitting sections that do not apply:

1. **H1 title** and one-sentence purpose.
2. **Use When**: concrete triggers, not a restatement of the description.
3. **Do Not Use When**: the nearest look-alike tasks and destructive cases.
4. **Inputs**: required, optional, and defaults.
5. **Workflow**: numbered imperative steps, one action per step.
6. **Outputs**: exact artifact and completion criteria.
7. **Error Handling**: condition, action, and stop rule per failure.
8. **Quality Checks**: observable checks the agent must run.
9. **References**: relative links to supporting material.

Write instructions to the agent, not about the skill. Keep one term per concept. Never invent a tool, flag, or API; if availability is unknown, say so and require a runtime check.

### 7. Apply progressive disclosure

- Keep `SKILL.md` under 500 lines and about 5,000 tokens.
- Move long tables, schemas, examples, and domain notes to `references/`.
- Put executable helpers in `scripts/` and static templates in `assets/`.
- Keep references one level deep from the skill root.
- Link each resource from `SKILL.md` so the agent knows when to load it.

### 8. Validate the structure

Run an Agent Skills validator when one is available in the workspace. If this repository is present, run:

```bash
python3 skills/skill-audit/scripts/audit_skill.py skills/pdf-form-filler
```

Fix every error. Review every warning; accept a warning only with a stated reason. If no validator is available, check the frontmatter and file references manually against [the specification reference](references/spec-reference.md).

### 9. Test the skill

Test at least these cases, using a scratch directory:

| Case | Input | Expected result |
| --- | --- | --- |
| Normal | Complete, valid request | Full workflow completes; output criteria met |
| Ambiguous | Two plausible interpretations | Agent asks one decisive question or states a reversible assumption |
| Missing info | No required input | Agent asks for the specific missing item and stops |
| Invalid | Wrong file type, malformed input | Agent reports the problem without producing a false success |
| Edge | Empty, huge, or unusual input | Documented behavior, no crash or silent truncation |
| Recovery | A step fails midway | Agent reports what succeeded, repairs, and reruns the failed check |

Run every test that the environment supports. Never report an unrun test as passed; write "not run" and the reason.

### 10. Report

Return:

1. Skill name and directory.
2. Files created or changed.
3. Validation result with the exact command.
4. Tests run, passed, failed, and not run.
5. The install command for the published repository, if known.

## Error Handling

- **Name conflicts with an existing directory**: inspect the existing skill first; merge or choose a new name instead of overwriting.
- **Description exceeds 1024 characters**: move detail into `resources` and keep the triggers in the description.
- **Validator unavailable**: perform the manual checklist and state that automated validation was not run.
- **Scaffold refuses to write**: the target exists. Read it, then use `--force` only if replacement is intended.
- **A step needs a tool the agent lacks**: document a fallback or mark the skill incompatible; never simulate the result.

## Quality Checks

- Directory name equals the frontmatter `name`.
- Description contains both capability and trigger phrases.
- The body has an H1 and an explicit activation section.
- Every relative link and mentioned resource exists.
- No unfinished marker, unresolved repository placeholder, secret, or fake test result.
- `SKILL.md` is under 500 lines; long material is in `references/`.

## References

- [Specification reference](references/spec-reference.md): fields, constraints, discovery paths, and progressive disclosure.
- [Description patterns](references/description-patterns.md): trigger formulas, good and bad examples, and keyword selection.
