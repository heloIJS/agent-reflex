# Agent Skills Specification Reference

Condensed from the official specification at [agentskills.io/specification](https://agentskills.io/specification). Verify against the live specification when implementing a new client.

## Directory Layout

```text
skill-name/
├── SKILL.md          # Required: frontmatter plus instructions
├── scripts/          # Optional: executable helpers
├── references/       # Optional: on-demand documentation
└── assets/           # Optional: templates and static data
```

A skill is a directory containing at least `SKILL.md`. Extra directories are conventions, not requirements.

## Frontmatter Fields

| Field | Required | Constraint |
| --- | --- | --- |
| `name` | Yes | 1-64 characters; lowercase `a-z`, digits, single hyphens; no leading or trailing hyphen; must match the parent directory |
| `description` | Yes | 1-1024 characters; states what the skill does and when to invoke it |
| `license` | No | License name or a reference to a bundled license |
| `compatibility` | No | 1-500 characters; only for real environment requirements |
| `metadata` | No | Mapping of string keys to string values |
| `allowed-tools` | No | Space-separated tool list; experimental and client-dependent |

Minimal file:

```markdown
---
name: pdf-processing
description: Extract text and tables from PDFs and fill forms. Use when the user mentions PDFs, forms, or document extraction.
---

# PDF Processing
```

## Body Content

The body has no required structure. Recommended sections:

- Step-by-step workflow.
- Input and output definitions.
- Examples.
- Edge cases and failure handling.

The agent loads the entire `SKILL.md` when the skill activates, so keep the core procedure compact and move detail to references.

## Progressive Disclosure

| Layer | Loaded | Target size |
| --- | --- | --- |
| Metadata (`name`, `description`) | At startup, for every skill | About 100 tokens |
| `SKILL.md` body | When the skill activates | Under 5,000 tokens, under 500 lines |
| `references/`, `scripts/`, `assets/` | On demand | As small and focused as practical |

Keep file references one level deep from `SKILL.md`. Avoid chains where one reference points to another reference.

## Discovery

The Vercel Labs `skills` CLI searches standard container directories, including:

- The repository root, when it contains `SKILL.md`.
- `skills/`, `skills/.curated/`, `skills/.experimental/`, and `skills/.system/`.
- Agent-specific locations such as `.claude/skills/`, `.codex/skills/`, and `.agents/skills/`.

It walks each container up to three levels, covering `skills/<name>/SKILL.md` and one or two category levels. A `SKILL.md` found at a shallower level shadows nested skills. Use `--full-depth` to search outside those containers.

Alternate locations can be declared in a root `skills.sh.json`:

```json
{
  "$schema": "https://skills.sh/schemas/skills.sh.schema.json",
  "paths": ["./tools/skills"]
}
```

## Validation

The reference validator is `skills-ref` from the [agentskills repository](https://github.com/agentskills/agentskills/tree/main/skills-ref):

```bash
skills-ref validate ./my-skill
```

This repository ships a dependency-free equivalent at `scripts/audit_skill.py` in the skill-audit skill. It covers the specification constraints plus reference and security checks.

## Compatibility Notes

- `allowed-tools` is experimental. Do not rely on it for permissions.
- Installation paths differ per agent. The `skills` CLI resolves them; a skill should not hardcode one agent's directory.
- A skill can only use tools the host agent provides. State environment requirements in `compatibility` instead of assuming access.
