# agentic-sdd-flow

Spec-driven agentic development flow for .NET as a Claude Code plugin.

Work in progress — see `docs` in the consuming repository until the README is complete.

## Runtime notes

- Local-path marketplace install: OK (`claude plugin marketplace add <path>` + `claude plugin install agentic-sdd-flow@agentic-sdd-flow`).
- Local-path install is a versioned copy under `~/.claude/plugins/cache/agentic-sdd-flow/agentic-sdd-flow/<version>/` — run `claude plugin update agentic-sdd-flow` after every change (restart required to apply).
