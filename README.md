# agentic-sdd-flow

Spec-driven agentic development flow for .NET as a Claude Code plugin: opinionated conventions,
Roslyn-first specialist agents, a deterministic implement → test → review → verify → fix
workflow, and one entry-point skill.

## Install

```
/plugin marketplace add AKarpetc/agentic-sdd-flow
/plugin install agentic-sdd-flow@agentic-sdd-flow
```

Team-wide, in the repository's `.claude/settings.json`:
```json
{
  "extraKnownMarketplaces": { "agentic-sdd-flow": { "source": { "source": "github", "repo": "AKarpetc/agentic-sdd-flow" } } },
  "enabledPlugins": ["agentic-sdd-flow@agentic-sdd-flow"]
}
```

Requirements: .NET SDK, `CWM.RoslynNavigator` ≥ 0.8.0 (installed on first use), the
[superpowers](https://github.com/obra/superpowers) plugin (brainstorming, writing-plans and the
SDD helper scripts), Python 3.

## Use

```
/agentic-sdd-flow:dotnet-feature PROJ-123 add a paged brands endpoint to the orders service
```
Design (approval gate) → plan → `dotnet-sdd` workflow → branch, never pushed.

Direct pieces: `/agentic-sdd-flow:dotnet-code-review`, the `tests-writer` agent,
`Workflow({ name: 'agentic-sdd-flow:dotnet-sdd', args: { project, projectDir, plan, taskKey } })`.

## What the plugin enforces

`rules/RULES-CONTRACT.md` is injected into every session, subagent and plan-driven prompt; a
PostToolUse hook rejects newly introduced violations in `.cs`/`.csproj` files. Full rules:
`rules/`. Check ids you can tune per repository: `single-type-per-file`, `filename-parity`,
`no-primary-ctor`, `no-ioptions`, `no-sync-over-async`, `no-async-void`, `no-datetime-now`,
`no-moq`, `no-null-guard`, `no-arg-do`, `no-task-fromresult-stub`, `prefer-init`,
`fluentassertions-v7`, `no-artefact-comments`, `no-inline-comments`, `xmldoc-brevity`,
`fluentassertions`.

## Company overlay

Everything specific to your systems lives in your repository, not in the plugin:

- `.claude/rules/OVERLAY-CONTRACT.md` — injected after the plugin contract.
- `.claude/agentic-sdd-flow.json` — `taskKeyPattern`, `plansDir`, `adrDir`, `docsPaths`,
  `projects` (name → solution), `checks` (`block|advisory|off` per id), `handoffs` (key → your
  skill), `overlayContract`.

See `examples/overlay/`.

## Roslyn

`roslyn-query.py <project-or-solution> <tool> '<json>'` (on PATH from `bin/`) runs one warm
navigator per solution. `bind-roslyn.sh <target>` pins the fallback MCP server
(`${CLAUDE_PLUGIN_DATA}/roslyn-solution`).

## Runtime notes

- Local-path marketplace install: OK (`claude plugin marketplace add <path>` + `claude plugin install agentic-sdd-flow@agentic-sdd-flow`).
- Local-path install is a versioned copy under `~/.claude/plugins/cache/agentic-sdd-flow/agentic-sdd-flow/<version>/` — run `claude plugin update agentic-sdd-flow` after every change (restart required to apply).
- SubagentStart hook reaches workflow agents: yes for named `agentType` agents; the default workflow agent reported no contract — the `dotnet-sdd` workflow therefore also asks every agent to read `rules/RULES-CONTRACT.md` first.
- Plugin agents resolve in `agent({agentType})` as their bare name (`tests-writer`); the `agentic-sdd-flow:` prefix is not accepted. A project's own `.claude/agents/<name>.md` shadows the plugin agent of the same name.
- Plugin workflows and agents register at session start — after installing or updating the plugin, restart Claude Code before using `/agentic-sdd-flow:*` workflows.
- `bin/` was not on PATH for workflow agents in the session that installed the plugin; the injected Roslyn note therefore carries the absolute `bin/roslyn-query.py` path as well.
