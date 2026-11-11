# Description Patterns

The `description` field is the only text loaded for every skill at startup. It decides whether the skill activates. Write it for retrieval, not for marketing.

## Formula

```text
<Capability in one sentence>. Use when <user request>, <file type>, or <operation>.
```

Aim for 150-400 characters. Include:

1. The action the skill performs.
2. The objects it operates on: file types, formats, tools, or domains.
3. The phrases a user would actually type.
4. A boundary when a nearby skill could be confused with this one.

## Good Examples

| Skill | Description | Why it works |
| --- | --- | --- |
| `pdf-form-filler` | Fill, flatten, and verify PDF AcroForm fields. Use when the user mentions PDF forms, form fields, or needs a filled PDF. | Names the objects and the exact user nouns. |
| `skill-audit` | Audit an Agent Skill for specification compliance, trigger quality, broken references, and security risks. Use when the user asks to review, validate, lint, or debug a SKILL.md. | Lists capabilities, then the request verbs. |
| `reflex` | Capture a correction, find its root cause, and persist a tested rule. Use when the user says "reflex", asks the agent to learn permanently, or corrects a recurring bug. | Includes the literal invocation phrase. |

## Weak Examples

| Description | Problem | Fix |
| --- | --- | --- |
| `Helps with PDFs.` | No capability, no trigger, too short to retrieve. | Name extraction, form filling, and the user nouns. |
| `A powerful and comprehensive skill for all your document needs.` | Marketing language, no concrete object. | Replace with file types and operations. |
| `Use this when needed.` | Circular; "needed" has no signal. | Name the request, file, or operation that activates it. |
| `Analyze data.` | Too broad; matches every data task. | Narrow to the format, method, and output. |

## Keyword Selection

Choose keywords from four sources:

1. **User nouns**: the words in the request, including misspellings users make.
2. **File types and formats**: `.pdf`, `docx`, `9:16`, `SARIF`.
3. **Tool names**: `ffmpeg`, `pytest`, `Playwright`.
4. **Output artifacts**: report, caption, migration, changelog.

Do not stuff synonyms that do not change activation. A description that matches everything activates on nothing useful.

## Boundary Sentences

Add a short boundary when another skill is close:

```text
Use for runtime secrets handling. Do not use for repository secret scanning, which belongs to the security-review skill.
```

Keep the boundary factual. Do not mention skills that do not exist in the catalog.

## Length Check

- Below 40 characters: almost always too vague.
- 40-150: acceptable for a narrow skill.
- 150-600: typical sweet spot.
- 600-1024: only for a skill with many distinct triggers.
- Over 1024: invalid; move detail into the body.
