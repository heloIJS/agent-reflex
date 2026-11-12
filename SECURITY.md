# Security Policy

## Supported Versions

Security fixes apply to the latest version on the default branch.

## Report a Vulnerability

Do not post unpatched vulnerabilities, credentials, or exploit details in a public issue. Use GitHub's private vulnerability reporting for this repository. Include affected paths, impact, and a minimal reproduction without real secrets.

If private reporting is unavailable, contact the repository owner through the verified GitHub profile. Do not send tokens or personal data.

## Security Scope

This repository contains agent instructions and local validation scripts. Review each skill before installation. Skills can influence agent behavior, and installed skills inherit the permissions of the host agent.

The repository's scanner is a best-effort pattern check. It does not replace secret scanning, code review, sandboxing, or least-privilege credentials. False negatives are possible.

Contributors must not add credentials, private keys, customer data, hidden network access, destructive commands without clear safeguards, or untrusted remote script execution.

## Active Memory

`.reflex/` contains local learning state and is ignored by Git. Save sanitized structural summaries, never transcripts or production secrets. Pattern checks are incomplete. The engine stores verifier hashes and outcomes instead of command output, and retrieval never executes stored instructions.

Explicitly supplied resolution and mutation verifiers run with the host's permissions, not in a sandbox. Inspect them before execution. Local schema validation does not prevent someone with filesystem access from tampering with evidence. A verified status means a scoped check passed, not that a lesson is safe or universally correct. Deprecate incorrect rules rather than relying on repeated retrieval to fix them.
