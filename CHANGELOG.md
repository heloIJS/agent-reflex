# Changelog

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
