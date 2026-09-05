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
SDD helper scripts), Python 3; the `spec-coding` skill additionally needs the `spec-coding` MCP
server registered at user scope.

## Use

```
/agentic-sdd-flow:dotnet-feature PROJ-123 add a paged brands endpoint to the orders service
```
Design (approval gate) → plan → `dotnet-sdd` workflow → branch, never pushed.

Direct pieces: `/agentic-sdd-flow:dotnet-code-review`, the `tests-writer` agent,
`Workflow({ name: 'agentic-sdd-flow:dotnet-sdd', args: { project, projectDir, plan, taskKey } })`.

Plugin agents and workflows register at session start: restart Claude Code after installing or
updating the plugin.

## What the plugin enforces

`rules/RULES-CONTRACT.md` is injected into every session, subagent and plan-driven prompt; a
PostToolUse hook rejects newly introduced violations in `.cs`/`.csproj` files. The write gate
compares against the committed version of the file and reports only newly introduced violations,
keyed by rule and message — a second occurrence of a violation the file already contains is not
blocked. Full rules: `rules/`. Check ids you can tune per repository: `single-type-per-file`, `filename-parity`,
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
- Plugin agents resolve in `agent({agentType})` only as `agentic-sdd-flow:<name>`; a bare name resolves to a project's own `.claude/agents/<name>.md` if one exists (shadowing), otherwise it is not found.
- Plugin workflows and agents register at session start — after installing or updating the plugin, restart Claude Code before using `/agentic-sdd-flow:*` workflows.
- `bin/` is on PATH for workflow agents once the plugin was installed before the session started; the injected Roslyn note also carries the absolute `bin/roslyn-query.py` path.
- RoslynCodeLens.Mcp on net8/net9: works — takes the `.sln` as a positional CLI arg (not a `set_active_solution` call), loads and background-compiles an 11-project net8/net9 solution in well under a minute, and `find_uncovered_symbols` returns real per-symbol coverage data (760 symbols, 19 risk hotspots) with no arguments needed once the solution is loaded.
- Fuse on net8/net9: partially works — `fuse mcp serve` answers `tools/list` and `fuse_check` (oracle-grade, sub-second, real compiler diagnostics on a proposed edit) correctly out of the box; `fuse_test` for a symbol with obvious direct test coverage returned "no covering tests" because the workspace was indexed at syntax tier only (no solution auto-selected), and building a semantic index (`fuse index --semantic`) failed with "index database is locked" while its own resident `fuse host` daemon was still up — so exercising `fuse_test`'s test-scoping claim needs more setup than the JSON-RPC probe alone.
- Decision: stay on CWM.RoslynNavigator 0.8.0 + roslyn-query.py — it already covers coverage/diagnostics/DI/endpoint queries this plugin needs without a second daemon or a semantic-indexing step, and neither spike tool clears enough of a bar to justify the added surface.
- Plugin workflow scripts are read once at session start. After editing a workflow, either restart Claude Code or run it via `Workflow({ scriptPath: '<plugin root>/workflows/<name>.js', args })`; `resumeFromRunId` works with either form.
- End-to-end trial on a real net8/net9 solution (2 plan tasks): status done — task 1 needed one verified fix round, task 2 was approved first pass, the final review triggered one fix wave; 22 agents, 6 minors deferred.
- The write gate fired inside a plugin agent: a brief that demanded a primary constructor and an inline comment was rejected by the PostToolUse hook and the implementer rewrote the file to the conventions.
- Resume works across process restarts: `resumeFromRunId` replayed 16 cached agents and re-dispatched only the agent that had not reported.
- A reviewer without the plugin root in context once ran a filesystem-wide `find` and stalled the run; the injected block now names the plugin root and the agents are told never to search for their skills.
