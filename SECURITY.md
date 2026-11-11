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
