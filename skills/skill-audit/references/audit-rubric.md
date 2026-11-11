# Skill Audit Rubric

Use this reference when a finding needs justification or when auditing a skill by hand.

## Specification Constraints

Source: [Agent Skills specification](https://agentskills.io/specification).

| Field | Required | Constraint |
| --- | --- | --- |
| `name` | Yes | 1-64 characters, lowercase `a-z`, digits, single hyphens, no leading or trailing hyphen, matches the parent directory |
| `description` | Yes | 1-1024 characters, states what the skill does and when to use it |
| `license` | No | License name or a reference to a bundled license file |
| `compatibility` | No | 1-500 characters, only when the skill has environment requirements |
| `metadata` | No | Map of string keys to string values |
| `allowed-tools` | No | Space-separated string, experimental and client-dependent |

A skill directory contains `SKILL.md` plus optional `scripts/`, `references/`, and `assets/` directories. Keep file references one level deep and prefer relative paths.

## Deterministic Checks

### Errors

| Code | Meaning | Typical fix |
| --- | --- | --- |
| `structure.skill_md` | `SKILL.md` missing | Add the file at the skill root |
| `frontmatter.parse` | Missing, unterminated, or invalid YAML | Repair the `---` block |
| `frontmatter.name` | Missing, invalid format, too long, or does not match the directory | Rename the directory and the field together |
| `frontmatter.description` | Missing, empty, or over 1024 characters | Rewrite the description |
| `frontmatter.compatibility` | Empty or over 500 characters | Shorten it or remove the field |
| `frontmatter.metadata` | Not a mapping | Use `key: value` pairs |
| `frontmatter.allowed_tools` | Not a string | Use a space-separated string |
| `content.empty` | No instruction body | Add the workflow |
| `content.length` | Over 1000 lines | Move detail into `references/` |
| `reference.missing` | Relative link target absent | Fix the path or remove the link |
| `reference.absolute` | Root-absolute path | Use a path relative to the skill root |
| `security.secret` | Token, private key, or API secret | Remove it and rotate the credential |
| `security.command` | Remote pipe to shell | Download, inspect, then execute a local file |

### Warnings

| Code | Meaning | Typical fix |
| --- | --- | --- |
| `frontmatter.description` | Short description or no trigger phrase | State the capability and "Use when ..." conditions |
| `content.title` | No H1 | Add a title |
| `content.activation` | No "Use When" section | Add explicit activation and non-activation boundaries |
| `content.length` | 501-1000 lines | Split reference material |
| `content.duplicate_heading` | Repeated heading | Merge the sections |
| `content.placeholder` | TODO, TBD, FIXME, unresolved repository placeholder | Finish the content |
| `reference.bare_missing` | Mentioned path does not exist | Create the file or correct the path |
| `security.command` | Destructive delete, dynamic evaluation, or git hook bypass | Justify, sandbox, or replace |

## Content Review

The script cannot verify these. Read the skill and answer each question.

1. **Trigger precision**: would a different task match this description by mistake? If yes, narrow it with file types, operations, or user phrases.
2. **Actionability**: can an agent execute each step without guessing a path, tool, or output format?
3. **Ordering**: do steps depend on earlier outputs? Are dependencies stated?
4. **Failure handling**: does each risky step define what to do when it fails?
5. **Honesty**: are tool names, flags, and APIs real for the target agent? Are unrun tests labelled as not run?
6. **Progressive disclosure**: is the core workflow in `SKILL.md`, with long tables, schemas, and examples in `references/`?
7. **Reusability**: does the skill solve one identifiable capability instead of collecting generic advice?

## Security Review

Read every bundled script before running it. Confirm:

- No credentials, private keys, or customer data are embedded.
- Network access is explicit and limited to documented endpoints.
- File writes stay inside the project or a temporary directory.
- Deletions are scoped and reversible.
- Subprocess commands do not interpolate untrusted input into a shell.
- Install instructions do not pipe remote content directly into an interpreter.

Report a suspected leaked credential immediately. Do not reproduce the secret in the report; state the file and line, and recommend rotation.

## Report Template

```markdown
## Audit: <skill-name>

| Severity | Location | Problem | Fix |
| --- | --- | --- | --- |
| error | SKILL.md | Name does not match directory | Rename directory to `pdf-tools` |
| warning | references/api.md | Linked from SKILL.md but missing | Add the file or remove the link |

Checks run: structure, frontmatter, references, security.
Checks not run: live installation, agent activation test.

Verdict: FAIL (1 error, 1 warning)
```
