# Changelog

## 1.1.0 - 2026-11-13

- Add opt-in proactive learning signals with replay-safe event IDs and topic-based proposal gates.
- Add active local JSONL memory with schema validation, exclusive write locks, and atomic per-file persistence.
- Add bounded lexical retrieval of relevant verified rules, excluding deprecated lessons.
- Add provisional, verified, and deprecated states with executed mutation checks, failed-check demotion, and explicit deprecation.
- Require structured property verdicts for learning verification; runtime errors and exit 2 no longer count as evidence.
- Track observed recurrences and suggest review/escalation without automatically changing skills or global instructions.
- Document host-policy activation and limitations; remove the historical example ledger rather than trusting fabricated verification flags.

## 1.0.2 — 2026-11-12

- Add the Agent Reflex banner to the repository README.
- Replace free-form saboteur failure commands with controlled fixture mutations and one argv verifier.
- Add empty-file and JSON mutations, baseline checks, launch-error reporting, and source-preservation checks.
- Add tests proving broken verifier commands and mutation-ignoring checks do not pass.

## 1.0.1 — 2026-11-12

- Parse folded and literal YAML block descriptions in Reflex audits.
- Audit candidate skill content before writing; invalid patches leave the original file unchanged.
- Scope replacement matching to the requested section and keep fallback insertions inside that section.
- Reject reflex additions beyond 10 rules until maintainers consolidate the section.
- Add regression tests for multiline YAML, failed patch rollback, replacement placement, and compaction limits.

## 1.0.0 — 2026-11-12

- Published the Reflex, Skill Authoring, and Skill Audit skills.
- Added a dependency-free Agent Skills auditor and scaffold utility.
- Added deterministic repository checks and a lightweight credential/risky-command scan.
- Added tests for valid, ambiguous, missing, invalid, edge, and recovery behavior.
- Added least-privilege validation and security workflows with SHA-pinned actions.
- Documented Vercel Labs Skills CLI discovery and installation.
