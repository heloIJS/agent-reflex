# Contributing

Thanks for improving `agent-reflex`. Contributions should add a focused capability or prevent a specific recurring failure.

## Before You Start

1. Search existing issues and skills for duplicates.
2. For a new skill, describe its trigger, inputs, output, and verification before writing it.
3. Keep pull requests focused. Do not reformat unrelated files.
4. Never include secrets, customer data, local environment files, or generated installation artifacts.

## Add or Change a Skill

Every skill belongs in `skills/<skill-name>/SKILL.md`. The directory must match the frontmatter `name`.

Use the authoring script for a new scaffold:

```bash
python skills/skill-authoring/scripts/scaffold_skill.py pdf-processing \
  --description "Extract text and tables from PDFs. Use when the user mentions PDF extraction or document parsing."
```

Then complete the workflow, inputs, outputs, error handling, and quality checks. Move long reference material into `references/`; keep the core `SKILL.md` below 500 lines.

## Validate Locally

Python 3.10+ is sufficient; repository scripts use only the standard library.

```bash
python scripts/validate_repo.py
python -m unittest discover -s tests -v
python scripts/security_scan.py
npx --yes skills@latest add . --list
```

Inspect all script and shell changes. Do not run commands that download and execute remote code in one step.

For active-memory changes, run the tests in `tests/test_memory.py`. Keep `.reflex/` out of Git and use temporary stores in tests. Include proposal gating, failed verification, retrieval budget, deprecation, and corrupted-state recovery cases. Do not claim a host integration was executed unless the target host actually emitted the observations.

## Pull Request Checklist

- [ ] Scope and purpose are clear.
- [ ] Skill metadata and local references validate.
- [ ] New behavior has normal, invalid, and failure-path tests.
- [ ] Security scan reports no credential or unsafe command findings.
- [ ] README and changelog reflect user-facing changes.
- [ ] Any test that could not run is stated with its blocker.

## Skill Quality Bar

- One identifiable, reusable capability per skill.
- Description states what it does and when to invoke it.
- Workflow has ordered actions and observable verification.
- Failure handling says how to recover or when to stop.
- No unsupported agent-tool claims or fabricated compatibility.
- No raw corrections, private identifiers, or secrets in reusable rules.

## Commit Style

Use a short Conventional Commit subject, for example `feat(skill): add pdf extraction workflow` or `fix(audit): reject duplicate skill names`.
