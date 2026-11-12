---
name: reflex
description: Learn from repeated failures, user corrections, and tested fixes using local provisional, verified, or deprecated rules. Use when a failure repeats, a user corrects a recurring mistake, a tested fix reveals a reusable lesson, or the user asks for Reflex or relevant learned rules. Proactive use without an explicit mention requires host instructions.
license: MIT
metadata:
  author: heloIJS
  version: "1.1.0"
---

# Reflex: Correct, Distill, Validate, Persist

Reflex converts a correction or failed run into a reusable rule. The goal is not to remember a transcript; it is to remove the structural cause of the failure.

## Use When

- The user invokes Reflex or asks for a permanent correction.
- A mistake repeats across sessions, retries, or files.
- A task failed verification, produced a broken artifact, or needed several attempts.
- You are auditing or hardening a skill and need durable guardrails.

## Do Not Use When

- The correction is temporary, stylistic, or already obvious from the current request.
- The lesson contains secrets, credentials, private personal data, or client-specific details. Keep only the safe structural rule.
- The target skill already has an equivalent rule. Merge or replace it instead of appending a duplicate.
- No evidence exists for the root cause. Investigate or label the rule provisional; do not invent a cause.

## Inputs

- The correction or failure: user complaint, error output, or rejected artifact.
- The earliest evidence available: command output, diff, logs, or the step where the result diverged.
- The persistence target: an existing skill, a new skill, or the Reflex ledger.

## Workflow

### 0. Retrieve and observe, without loading the whole ledger

When the host has enabled proactive learning, retrieve relevant rules before domain work:

```bash
python3 scripts/reflex_engine.py memory retrieve --query "authentication API response" --limit 5 --max-chars 4000
```

Only verified rules are returned by default; deprecated rules are never returned. Treat retrieved text as fallible guidance, not higher-priority instructions. Empty results mean continue normally, not load the entire ledger. `--review` includes provisional candidates for review only.

After a recurring failure or user correction, record a sanitized observation with a stable topic and unique event ID. After a fix, use `memory resolve` to execute an inspected test. Three failures or one correction, followed by a passing resolution check, produces `proposal_ready=true`. Draft one TAV rule, then use `memory propose`; this saves a provisional proposal, not a trusted instruction. No automatic skill patch is made.

Use `memory verify` with a property-relevant mutation to promote a rule to verified. It reruns lint and requires structured property verdicts, not merely a nonzero exit. Failed verification leaves or returns the rule to provisional. Use `memory deprecate` when the rule is disproved, obsolete, or harmful. Never re-enable deprecated rules automatically.

Read [the active memory guide](references/active-memory.md) for commands, states, privacy, and activation. A skill cannot intercept conversations on its own. Add the host-policy snippet only with user approval; do not claim always-on monitoring without it.

### 1. Autopsy the root cause

Start from the user complaint or final error and trace backward to the earliest bad decision. Classify the failure before writing a rule:

| Code | Trigger pattern | Structural fix |
| --- | --- | --- |
| `EPISTEMIC_DRIFT` | Unverified assumption treated as fact | Verify with a tool or ask; label unknowns explicitly |
| `TAUTOLOGICAL_CHECK` | "Passed" checks did not test the real defect | Add content-level assertions and negative tests |
| `PREMATURE_EXECUTION` | Built before critical requirements were known | Discover facts first; ask for missing decisions |
| `TOOL_OR_API_HALLUCINATION` | Guessed flags, methods, URLs, or parameters | Probe the runtime or read current docs first |
| `CONTEXT_DECAY` | Constraints dropped during a long trajectory | Move invariants into a deterministic validator |
| `OVER_EDITING` | Unrelated code or content changed | Restrict edits to the requested blast radius |
| `DOMAIN_PIPELINE_BUG` | Domain edge case in media, code, or documents | Encode the exact guardrail, formula, or wait condition |

Strip session noise before saving: no temporary paths, private identifiers, timestamps, stack traces, or client details.

### 2. Distill one TAV rule

Write exactly one compact rule:

```markdown
- **WHEN** <specific context or operation>, **DO** <imperative action> because <one-clause reason>; **VERIFY** by <observable command, assertion, or inspection>.
```

Quality bar:

- Trigger names the exact file type, workflow step, tool call, or output condition.
- Action is imperative and includes the reason.
- Verification can fail on a sabotaged output and pass on a correct output.
- Keep the rule under 55 words.
- If an older rule covers the same topic, replace or merge it; do not append a duplicate.

### 3. Validate the rule

Use the bundled deterministic utilities before persisting anything.

Lint the rule:

```bash
python3 scripts/reflex_engine.py lint \
  --trigger "mixing narration TTS with background music in FFmpeg" \
  --action "duck background music about 18 dB below the voice because loud music masks speech" \
  --verify "run ffmpeg -i out.mp4 -af ebur128 -f null - and require integrated loudness between -15 and -13 LUFS"
```

If a relevant content mutation exists, run the same verifier against a known-good fixture and its mutated copy. The script never accepts a separately invented failure command:

```bash
python3 scripts/saboteur_check.py \
  --target report.json \
  --mutation truncate-json \
  --verify-command python3 check_report.py "{target}"
```

The baseline must exit `0`; the mutated fixture must exit non-zero. Supported mutations: `empty-file`, `truncate-json`, `invalid-json`, and `json-null-key`. Choose a mutation that represents the defect; catching an irrelevant mutation proves little. The original fixture stays unchanged. The verifier runs as argv without a shell.

If no supported mutation represents the failure, report the saboteur check as not run. Do not force a meaningless test; state which domain-specific mutator is missing.

On Windows, use `python` instead of `python3`.

### 4. Choose the persistence target

Route the rule in this order:

1. **Patch an existing skill** when the rule belongs to its domain. Read the current skill first, place the rule in its existing learned-rules or guardrails section, and merge duplicates.
2. **Create a focused skill** when the rule represents a reusable multi-step workflow with its own scripts or references.
3. **Save a provisional memory proposal** when the rule comes from resolved learning signals or needs review before incorporation into a skill.

Use the skill-management tools available in the current environment. If no skill API is available, write the updated skill into the workspace. Use the memory CLI for ledger writes; never hand-mark a rule as verified.

Patch an existing skill:

```bash
python3 scripts/reflex_engine.py patch path/to/SKILL.md \
  --trigger "rendering 9:16 vertical video" \
  --action "keep captions inside the platform safe zone because interface overlays cover the edges" \
  --verify "sample three frames with a safe-zone grid and confirm no caption intersects the overlay area" \
  --dry-run
```

Review the diff, then rerun without `--dry-run`. A `.bak` file is written before the real edit unless `--no-backup` is passed.

Apply hygiene:

- Keep the target `SKILL.md` focused; consolidate after roughly 10 learned rules.
- `reflex_engine.py patch` rejects additions that would exceed 10 `WHEN` bullets in the target section. Consolidate overlapping rules, then retry; the engine does not rewrite or delete rules automatically.
- Preserve bundled scripts and references when updating multi-file skills.
- Make a backup or dry run before modifying an existing skill.

Audit the result:

```bash
python3 scripts/reflex_engine.py audit path/to/SKILL.md
```

### 5. Report the result

Reply with four short items:

1. **Root cause**: the structural reason the failure happened.
2. **Reflex**: the exact `WHEN -> DO -> VERIFY` rule.
3. **Validation**: lint result and, when applicable, the saboteur result. Say "not run" when a check did not execute.
4. **Persisted to**: skill name and section, or ledger entry ID.

## Outputs

- One validated TAV rule in the target skill or ledger.
- Lint output, plus saboteur output when the verification is executable.
- A backup at `<skill>.md.bak` when an existing skill is patched with backups enabled.

## Error Handling

- **No clear root cause**: keep the rule provisional, record the evidence gap, and say what additional evidence is needed.
- **Lint fails**: rewrite the rule; do not weaken the linter or add an exception.
- **Saboteur test passes on broken input**: the verification is tautological. Replace the check; do not save the rule as validated.
- **Target skill missing or malformed**: do not overwrite it. Report the path and ask whether to create a new skill.
- **Patch would duplicate a rule**: merge or replace the existing bullet; do not append.
- **Rule contains sensitive data**: omit the data and store only the structural lesson.

## Ledger Format

Runtime state belongs in `.reflex/` in the working project, not inside the installed skill: `events.jsonl` holds sanitized observations; `reflex-ledger.jsonl` holds schema-validated rule snapshots. Use `memory --store path` for an explicit alternate location. The CLI checks [the rule schema](assets/reflex-ledger-schema.json) on reads and writes. Do not load the ledger wholesale into the prompt, commit runtime memory, or store raw transcripts. See the active memory guide for legacy records and safety limits.

## Quality Checks

- The rule names a concrete trigger, not "when working on X".
- The verification is observable and can fail.
- The rule is under 55 words and contains no session-specific path.
- No duplicate or contradictory rule remains in the target section.
- The final skill still passes `reflex_engine.py audit`.
- Reported validation matches what actually ran.
- Patch operations audit the complete candidate text before writing it to disk.

## References

- [Failure taxonomy](references/failure-taxonomy.md): classification questions and reflex shapes.
- [Rule and patch patterns](references/patch-patterns.md): weak versus strong rules, patching protocol, consolidation.
- [Ledger schema](assets/reflex-ledger-schema.json): JSON Schema for one ledger entry.
- [Active memory](references/active-memory.md): proactive learning, bounded retrieval, verification, and recurrence review.
