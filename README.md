# agentic-sdd-flow

Spec-driven agentic development flow for .NET as a Claude Code plugin.

Work in progress — see `docs` in the consuming repository until the README is complete.

## Runtime notes

- Local-path marketplace install: OK (`claude plugin marketplace add <path>` + `claude plugin install agentic-sdd-flow@agentic-sdd-flow`).
- Local-path install is a versioned copy under `~/.claude/plugins/cache/agentic-sdd-flow/agentic-sdd-flow/<version>/` — run `claude plugin update agentic-sdd-flow` after every change (restart required to apply).
- SubagentStart hook reaches workflow agents: yes for named `agentType` agents; the default workflow agent reported no contract — the `dotnet-sdd` workflow therefore also asks every agent to read `rules/RULES-CONTRACT.md` first.
- Plugin agents resolve in `agent({agentType})` as their bare name (`tests-writer`); the `agentic-sdd-flow:` prefix is not accepted. A project's own `.claude/agents/<name>.md` shadows the plugin agent of the same name.
- Plugin workflows and agents register at session start — after installing or updating the plugin, restart Claude Code before using `/agentic-sdd-flow:*` workflows.
- `bin/` was not on PATH for workflow agents in the session that installed the plugin; the injected Roslyn note therefore carries the absolute `bin/roslyn-query.py` path as well.
