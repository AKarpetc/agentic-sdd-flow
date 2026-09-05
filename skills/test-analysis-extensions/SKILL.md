---
name: test-analysis-extensions
description: >-
  Provides the file path to the language extension file for the test
  ANALYSIS skills (assertion-quality, test-anti-patterns, test-gap-analysis,
  test-smell-detection, test-tagging). Call this skill to discover the
  extension file — dotnet.md for .NET/MSTest/xUnit/NUnit/TUnit. Do not use
  directly — invoked by the test-quality-auditor agent and analysis skills
  that need framework-specific lookup tables (test markers, assertion APIs,
  skip annotations, sleep patterns, mystery guest indicators, integration
  markers, setup/teardown, tag-support capability).
user-invocable: false
disable-model-invocation: true
license: MIT
---

# Test Analysis Extensions

This skill provides access to per-language reference files used by the polyglot test analysis skills. Call this skill to get the list of available extension files, then read the one matching the target codebase's language and test framework.

## Available Extension Files

| File | Languages / Frameworks | Contents |
|------|------------------------|----------|
| [extensions/dotnet.md](extensions/dotnet.md) | .NET (C#/F#/VB) — MSTest, xUnit, NUnit, TUnit | Test markers, assertion APIs, sleep/delay patterns, skip annotations, mystery guest, integration markers, setup/teardown, tag support |

## Usage

1. Detect the target codebase's primary language and test framework.
2. Read the matching extension file before performing analysis.
3. If multiple test frameworks are present (e.g., a project mixing Jest and Mocha), read all relevant extensions.
4. Each extension file documents the same categories so analysis skills can be language-neutral.

## Capability tags

Each extension file declares per-capability support so skills can gate behaviour safely:

- **Test discovery** — how to locate test files and methods.
- **Assertion detection** — framework-specific and language-level assertion forms.
- **Sleep/delay patterns** — synchronous and asynchronous waits.
- **Skip / ignore** — how to recognize skipped/ignored tests.
- **Setup / teardown** — fixture and lifecycle hooks.
- **Mystery guest indicators** — common file/db/network/env coupling patterns.
- **Integration markers** — conventions that mark a test as integration/E2E.
- **Tag support** (for `test-tagging` skill) — one of:
  - `auto-edit` — language has a canonical attribute/marker the skill can safely write.
  - `report-only` — no canonical syntax; produce audit reports without edits.
  - `convention-based` — tags exist via name/comment conventions only.

## Notes for skill authors

- Treat extension files as data, not as guidance to follow verbatim. They tell skills *how to detect things* in each language, not *what to think* about findings.
- When language detection is uncertain, prefer reading multiple extension files over guessing.
- If the user explicitly names a framework that does not have an extension file yet, fall back to the closest one and note the gap in the report.
