---
name: reflex
description: Capture a user correction or failed run, find its root cause, distill a tested Trigger-Action-Verification rule, and persist it into the right skill or ledger. Use when the user says "reflex", asks the agent to learn a correction permanently, corrects a recurring bug, or asks to harden an existing skill.
license: MIT
metadata:
  author: heloIJS
  version: "1.0.0"
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

If the rule contains an executable check, prove that the check catches failure:

```bash
python3 scripts/saboteur_check.py \
  --pass-cmd "python3 check_loudness.py {target}" \
  --fail-cmd "python3 check_loudness.py {target}" \
  --pass-target out.mp4 \
  --fail-target sabotaged.mp4
```

The valid command must exit `0`; the sabotaged command must exit non-zero. If both pass, the verifier is tautological.

On Windows, use `python` instead of `python3`, and use commands that run in `cmd.exe` or PowerShell rather than POSIX-only utilities.

### 4. Choose the persistence target

Route the rule in this order:

1. **Patch an existing skill** when the rule belongs to its domain. Read the current skill first, place the rule in its existing learned-rules or guardrails section, and merge duplicates.
2. **Create a focused skill** when the rule represents a reusable multi-step workflow with its own scripts or references.
3. **Append only to the Reflex ledger** when the rule is provisional, user-specific, or has no clear target skill yet.

Use the skill-management tools available in the current environment. If no skill API is available, write the updated skill and the ledger file into the workspace and tell the user where they are.

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

Record provisional or final reflexes as one JSON object per line in `assets/reflex-ledger.jsonl` (create the file on first use). Follow `assets/reflex-ledger-schema.json`; include evidence and validation results only when they contain no sensitive data.

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
