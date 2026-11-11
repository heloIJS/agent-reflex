# agent-reflex

**Turn agent mistakes into durable, testable skills.**

`agent-reflex` is a small collection of reusable Agent Skills and standard-library Python utilities. It helps coding agents learn from corrections, create well-scoped skills, and audit skill packages before sharing them.

## Features

- **Reflex**: trace failures to root causes, write Trigger-Action-Verification rules, and persist them safely.
- **Skill Authoring**: scaffold and write skills with explicit triggers, workflows, outputs, and failure handling.
- **Skill Audit**: check skill metadata, references, content signals, and suspicious commands.
- **No runtime dependencies**: bundled Python tools use the standard library.
- **Honest validation**: scripts distinguish errors from warnings and test checks against invalid cases.

## Available skills

| Skill | Purpose | Source |
| --- | --- | --- |
| `reflex` | Capture corrections and persist validated, reusable failure-prevention rules. | [SKILL.md](skills/reflex/SKILL.md) |
| `skill-authoring` | Create or revise focused Agent Skills that comply with the specification. | [SKILL.md](skills/skill-authoring/SKILL.md) |
| `skill-audit` | Audit skill structure, metadata, references, and security risks. | [SKILL.md](skills/skill-audit/SKILL.md) |

## Installation

Install all skills interactively:

```bash
npx skills add heloIJS/agent-reflex
```

### Discover available skills

```bash
npx skills add heloIJS/agent-reflex --list
```

### Install a specific skill

```bash
npx skills add heloIJS/agent-reflex --skill reflex
npx skills add heloIJS/agent-reflex --skill skill-authoring
npx skills add heloIJS/agent-reflex --skill skill-audit
```

### Update installed skills

```bash
npx skills update
```

The CLI installs into the selected agent's supported location. Paths differ by agent; use `npx skills add --help` for current options. Node.js 22.20 or later is required by the current Skills CLI.

The installed CLI version should be checked before using optional commands. In tested `skills` 1.8.1, `skills check` is not listed or supported; use `npx skills update` to refresh installed skills.

## Usage

Invoke the skill by asking for its capability:

```text
Reflex: find why the generated report failed validation and save a reusable rule.
Create a skill for checking database migration safety.
Audit skills/payment-export before release; do not change files.
```

Run the standalone repository checks without installing any skill:

```bash
python scripts/validate_repo.py
python -m unittest discover -s tests -v
python scripts/security_scan.py
```

## Supported agents

Skills use the open Agent Skills `SKILL.md` format and can be installed by clients supported by the Vercel Labs Skills CLI. The CLI supports OpenCode, Claude Code, Codex, Cursor, and many other clients; the active supported-agent list and installation paths are maintained in the [CLI documentation](https://github.com/vercel-labs/skills/blob/main/docs/agents.md).

This repository does not claim that every client implements every optional field or loads supporting resources identically. Skills avoid `allowed-tools`, which remains experimental.

## Repository structure

```text
agent-reflex/
├── .github/              # Pull request template, issue forms, CI workflows
├── skills/
│   ├── reflex/            # TAV rule workflow and utilities
│   ├── skill-authoring/   # Authoring workflow and scaffold script
│   └── skill-audit/       # Audit workflow and validation script
├── scripts/              # Repository validator and security scanner
├── tests/                # Unit, negative, edge, and recovery tests
├── CONTRIBUTING.md
├── SECURITY.md
└── README.md
```

The source of truth is `skills/<name>/`. The Skills CLI may create agent-specific installed copies; those are generated artifacts and are not committed.

## Creating custom skills

Use the authoring skill or scaffold script:

```bash
python skills/skill-authoring/scripts/scaffold_skill.py my-skill \
  --description "Do a repeatable task. Use when the user asks for this task or supplies these files."
```

Complete the generated instructions and add references or scripts only when they support a real workflow. Read [CONTRIBUTING.md](CONTRIBUTING.md) and the [skill-authoring guide](skills/skill-authoring/SKILL.md) before opening a pull request.

## Quality and validation

The validation workflow runs on pushes and pull requests. It checks required files, unique metadata, skill references, README commands, placeholders, workflow YAML syntax, SHA-pinned actions, security-sensitive files, and the test suite. It also asks the Skills CLI to discover repository skills.

Run locally:

```bash
python scripts/validate_repo.py
python -m unittest discover -s tests -v
python scripts/security_scan.py
npx --yes skills@latest add . --list
```

Use the standalone skill auditor for a focused report:

```bash
python skills/skill-audit/scripts/audit_skill.py skills/reflex --json
```

Warnings are visible and may indicate trigger or content risks. `--strict` makes skill-audit warnings fail. The checks do not prove an agent will invoke a skill correctly; test representative requests in the target agent too.

## Contributing

Issues and pull requests are welcome. Keep each skill focused, add tests for new behavior, and never commit secrets or generated install artifacts. See [CONTRIBUTING.md](CONTRIBUTING.md).

## Security

Review skill instructions and scripts before installing them. Report vulnerabilities through GitHub's private vulnerability reporting. See [SECURITY.md](SECURITY.md).

## License

The repository is licensed under [MIT](LICENSE).
