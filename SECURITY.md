# Security Policy

Thank you for helping keep Kestrel and its users safe.

## Supported Versions

Kestrel is early-stage software. Only the latest release on `main` receives
security fixes.

| Version | Supported |
| ------- | --------- |
| latest `main` | Yes |
| older tagged releases | No |

## Reporting a Vulnerability

**Please do not report security issues via public GitHub issues, discussions,
or pull requests.**

Instead, use GitHub's private vulnerability reporting:

1. Go to the repository's **Security** tab.
2. Click **Report a vulnerability**.
3. Fill in a detailed description (affected version/commit, reproduction
   steps, impact, and any suggested mitigation).

If private reporting is unavailable, email the maintainer listed on the
GitHub profile at https://github.com/pleasedodisturb.

## What to Include

- Affected component (backend, frontend, container, CI, etc.)
- Affected version or commit SHA
- Step-by-step reproduction
- Impact assessment (data exposure, RCE, privilege escalation, etc.)
- Any proof-of-concept code or logs (redact sensitive data first)

## Response Expectations

- **Acknowledgement**: within 5 business days of receipt.
- **Triage and severity assessment**: within 10 business days.
- **Fix or mitigation**: targeted within 30 days for high/critical, or a
  publicly-communicated timeline if the fix requires longer.
- **Disclosure**: coordinated; we credit reporters who wish to be credited.

## Scope

In scope:

- The Kestrel backend (`src/career_os/`)
- The Kestrel frontend (`frontend/`)
- The published container image and PyPI/npm packages
- GitHub Actions workflows in this repository

Out of scope:

- Self-hosted deployments misconfigured by the operator
- Third-party job boards, AI providers, or integrations Kestrel connects to
- Denial-of-service via resource exhaustion on self-hosted instances
- Social-engineering of maintainers

## Safe Harbor

We will not pursue legal action against researchers who act in good faith,
avoid privacy violations and service degradation, and follow this policy.
