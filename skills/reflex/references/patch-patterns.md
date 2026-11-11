# Reflex Rule and Patch Patterns

Use this guide when distilling a lesson and editing a target skill.

## TAV Formula

```markdown
- **WHEN** <specific context>, **DO** <imperative action> because <one-clause reason>; **VERIFY** by <command, assertion, or observable check>.
```

## Weak vs Strong Rules

| Weak | Strong |
| --- | --- |
| "Be careful with captions on vertical video." | `- **WHEN** rendering 9:16 vertical video, **PLACE** captions inside y=15%-72% and x=8%-82% because platform UI overlays cover the lower and right edges; **VERIFY** by overlaying the safe-zone grid on three sampled frames.` |
| "Check that the PDF looks right." | `- **WHEN** exporting a PDF table, **COMPARE** every page's text bounding boxes against page margins because overflow can be invisible in source HTML; **VERIFY** by parsing the PDF and failing any page where any text box exceeds the printable area.` |
| "Wait for the page to load." | `- **WHEN** screenshotting a canvas or web page, **AWAIT** fonts.ready and a render-ready flag before capture because async assets create blank frames; **VERIFY** by asserting sampled-frame pixel variance is above zero.` |
| "Use the right units." | `- **WHEN** preparing a financial model, **CONFIRM** currency, period, and revenue model before generating sheets because units and cadence change every formula; **VERIFY** by labeling every assumption as user-confirmed or source-backed.` |

## Patching Protocol

1. Read the current target skill before editing.
2. Put the rule in the existing learned-rules, guardrails, or workflow section that matches the trigger.
3. If an older rule covers the same topic, replace it in place. If it partly covers the topic, merge them.
4. Run `scripts/reflex_engine.py lint` on the final bullet.
5. For executable checks, run `scripts/saboteur_check.py` against valid and broken samples.
6. Run `scripts/reflex_engine.py audit` on the final `SKILL.md`.
7. Prefer a dry run or backup before modifying an existing skill.

## Choosing the Section

| Rule type | Section |
| --- | --- |
| Input validation, missing facts | `Inputs` or `Error Handling` |
| Step ordering or tool usage | `Workflow` |
| Output threshold, format, or proof | `Quality Checks` |
| Repeated correction with no other home | `Learned Reflexes` |

Do not create a new section for a single rule when an existing section fits.

## Consolidation Trigger

When a skill has about 10 learned rules, refactor:

- Combine rules with the same trigger into one multi-part rule.
- Move long examples to `references/`.
- Delete superseded rules.
- Keep only rules that prevent a concrete failure.

## Negative Test Design

A verifier that cannot fail is not a verifier. Pair every executable check with a broken sample:

1. Produce a correct artifact.
2. Produce a deliberately broken artifact with the same shape.
3. Run the identical check on both.
4. Require exit `0` on the correct artifact and non-zero on the broken one.

If both pass, or both fail, the check is measuring the wrong property.
