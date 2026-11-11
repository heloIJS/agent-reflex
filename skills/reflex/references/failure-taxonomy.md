# AI Agent Failure Taxonomy

Use this reference during the Reflex autopsy. Classify the earliest structural cause, not the final symptom.

## 1. Epistemic Drift

- Pattern: An unverified assumption is treated as a fact, and later steps depend on it.
- Fix: Verify with a tool when possible. Otherwise label the fact as unknown and ask before acting.
- Reflex shape: `WHEN an external fact changes output, DO retrieve it with the relevant tool or ask the user because stale assumptions corrupt downstream work; VERIFY by citing the retrieved source or explicit user confirmation.`

## 2. Tautological Verification

- Pattern: The output is broken, but the agent reports success because the check only tested a proxy.
- Fix: Add a content-level assertion and a negative test. A verifier is valid only if a sabotaged output fails.
- Reflex shape: `WHEN a generated artifact is validated, DO assert the property that caused the failure and run a sabotaged control because file existence is not correctness; VERIFY by failing the build when the control passes.`

## 3. Premature Execution

- Pattern: A complete deliverable is built before critical requirements are known.
- Fix: Separate facts from user decisions. Inspect available context first, then ask concise questions when a decision changes the deliverable.
- Reflex shape: `WHEN requirements omit a decision that changes the deliverable, DO inspect available context and ask up to three decisive questions before generating because silent defaults create rework; VERIFY by recording each assumption as user-confirmed or evidence-backed.`

## 4. Tool or API Hallucination

- Pattern: The agent invents flags, methods, URLs, schemas, or return values.
- Fix: Probe runtime help, inspect installed packages, or read current documentation before calling unfamiliar APIs.
- Reflex shape: `WHEN using an unfamiliar command or library call, DO inspect --help, version output, or current docs before invoking it because guessed APIs fail at runtime; VERIFY by confirming the exact flag or method exists in the retrieved source.`

## 5. Context Decay

- Pattern: Early constraints are followed, then silently dropped during a long trajectory.
- Fix: Move stable invariants into deterministic validators, templates, or item-level checklists.
- Reflex shape: `WHEN processing batches longer than three items, DO re-run a deterministic validator over every output because constraints decay under context pressure; VERIFY by counting validated items and rejecting any failed item.`

## 6. Over-Editing

- Pattern: A small requested change expands into unrelated rewrites.
- Fix: Read the exact target region first, edit only the relevant lines, then diff untouched regions.
- Reflex shape: `WHEN fixing a localized defect, DO edit only the lines tied to the root cause because unrelated rewrites raise regression risk; VERIFY by diffing unchanged sections and confirming they are identical.`

## 7. Domain Pipeline Bug

- Pattern: A known technical edge case in media, browser, code, or document pipelines breaks the output.
- Fix: Encode the exact threshold, timing condition, compiler flag, or formula in the domain skill.
- Reflex shape: `WHEN <specific pipeline stage>, DO <exact technical guardrail> because <mechanism>; VERIFY by <numeric or rendered-content assertion>.`

## Triage Questions

1. What did the user actually see?
2. What was the first incorrect decision or output?
3. Was a fact verified by a tool, inferred, or guessed?
4. Did the verification command fail on a deliberately broken sample?
5. What future trigger should activate the rule?
6. Can the rule be written without session-specific names or paths?

## Classification Notes

- Classify by the earliest cause that is still fixable, not by the loudest symptom.
- A failure can have two causes. Fix the one that recurs; record the other as a follow-up.
- "The model was careless" is not a category. Find the missing check, ambiguous instruction, or wrong assumption.
