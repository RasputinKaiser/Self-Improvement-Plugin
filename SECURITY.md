# Security Policy

## Supported versions

This project is in active development. Security fixes target the current `main` branch unless a release branch is created later.

## Reporting a vulnerability

Do not open a public issue for a security problem.

Instead, report the issue privately through GitHub's private vulnerability reporting flow if it is enabled for this repository. If that is not available, contact the maintainer through the GitHub profile.

Please include:

- what the issue is
- how it can be reproduced
- what local files, scripts, or hooks are involved
- whether the issue can expose local files, tokens, transcripts, browser data, or private repo content

## Scope

Relevant issues include:

- unsafe subprocess execution
- hook behavior that can run commands without clear user intent
- local file exposure
- Memory Fabric record exposure
- transcript or prompt leakage
- unsafe generated patch behavior
- dependency or script behavior that can affect the local machine

## Out of scope

Please do not report:

- issues caused by publishing your own secrets
- problems in unrelated Claude Code, Codex, or third-party plugins
- missing features
- theoretical issues without a plausible path to impact

## Local data warning

This plugin can read and write local harness state. Treat local harness state, Memory Fabric records, transcripts, screenshots, and logs as private unless you have reviewed and sanitized them.
