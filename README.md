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
blocked. Full rules: `rules/`.

Check ids you can tune per repository: `single-type-per-file`, `filename-parity`, `no-primary-ctor`, `no-ioptions`, `no-sync-over-async`, `no-async-void`, `no-datetime-now`, `no-moq`,
`no-null-guard`, `no-arg-do`, `no-task-fromresult-stub`, `prefer-init`, `fluentassertions-v7`, `no-artefact-comments`, `no-inline-comments`, `xmldoc-brevity`, `fluentassertions`.

## Company overlay

Everything specific to your systems lives in your repository, not in the plugin:

- `.claude/rules/OVERLAY-CONTRACT.md` — injected after the plugin contract.
- `.claude/agentic-sdd-flow.json` — `taskKeyPattern`, `plansDir`, `adrDir`, `docsPaths`,
  `projects` (name → solution), `checks` (`block|advisory|off` per id), `handoffs` (key → your
  skill or agent), `overlayContract`.

Hand-off keys the plugin's agents use (map the ones you have; unmapped keys are reported in plain words):

| Key | Meaning |
|---|---|
| `review-environment` | raise / redeploy a review environment for a branch |
| `alerts` | alert rules and their routing |
| `dashboards` | metrics dashboards and panels |
| `observability` | tracing / metrics instrumentation beyond dashboards and alerts |
| `db-schema` | schema changes owned outside EF Core (SSDT, DBA-managed scripts) |
| `service-tests` | a per-service test skill layered on top of `tests-writer` |
| `ci-pipeline` | pipeline definitions owned by a platform team |
| `secrets` | provisioning a secret in the secret manager |

See `examples/overlay/`.

## Roslyn

`roslyn-query.py <project-or-solution> <tool> '<json>'` (on PATH from `bin/`) runs one warm
navigator per solution. `bind-roslyn.sh <target>` pins the fallback MCP server
(`${CLAUDE_PLUGIN_DATA}/roslyn-solution`).

## Databases (read-only MCP)

Two optional MCP servers give the SQL agents live schema and plan access. Both are configured to fail closed when their environment variables are unset, and every other tool keeps working either way; the SQL Server server has been observed doing so, the Postgres server has not been exercised. Point them at a development database, never production.

| Server | Set | Access |
|---|---|---|
| `postgres-mcp` ([crystaldba/postgres-mcp](https://github.com/crystaldba/postgres-mcp), MIT) | `ASF_POSTGRES_URI=postgresql://user:pass@host:5432/db` | `--access-mode=restricted`: read-only SQL, `explain_query` (with hypothetical indexes when `hypopg` is installed), index and health analysis |
| `mssql-mcp` ([@connorbritain/mssql-mcp-reader](https://github.com/ConnorBritain/mssql-mcp-reader), MIT, pinned to reader `0.6.1` over core `0.7.0`) | `ASF_MSSQL_SERVER`, `ASF_MSSQL_DATABASE`, `ASF_MSSQL_USER`, `ASF_MSSQL_PASSWORD`; optional `ASF_MSSQL_PORT` (default `1433`), `ASF_MSSQL_TRUST_CERT` (`true` for a self-signed dev certificate) | reader tier — the 14 read-only tools are the only ones registered, so no write or DDL tool is exposed; the one remaining execution path, `run_script`, runs only files under `SCRIPTS_PATH`, which is left unset |

Tools: `list_schemas`, `list_objects`, `get_object_details`, `execute_sql`, `explain_query`, `analyze_query_indexes`, `analyze_workload_indexes`, `analyze_db_health`, `get_top_queries` on Postgres; `list_tables`, `describe_table`, `read_data`, `explain_query`, `search_schema`, `profile_table`, `inspect_relationships`, `inspect_dependencies`, `list_databases`, `test_connection` and four config/script helpers on SQL Server.

For `explain_query` quality on Postgres enable `pg_stat_statements` and `hypopg` on that database.

Notes on the pins:

- `postgres-mcp` declares `mcp[cli]>=1.5.0` with no upper bound and breaks on the `mcp` 2.x rename of `FastMCP`, so the launch line adds `--with "mcp<2"`.
- The SQL Server server is the **reader-tier** package rather than the full `@connorbritain/mssql-mcp-server` plus `READONLY=true`. In the shared core, `READONLY=true` still registers and advertises every write and DDL tool and rejects them at call time; the reader package never registers them. `READONLY=true` is kept as a second layer. `SQL_AUTH_MODE` is forced to `sql` because the package defaults to interactive Azure AD, which opens a browser.
- Never install the unscoped npm package `mssql-mcp-server` — that name belongs to an unrelated author. The scoped `@connorbritain/*` packages are the right ones, and the repository has no root `package.json`, so `npx github:ConnorBritain/mssql-mcp-server#<sha>` cannot work.
- Both npm packages are pinned, because the code that runs lives in the core and the reader depends on it as a floating `^0.7.0`. An explicit `--package=<name>@<version>` overrides that range at install time, so the launch line names reader and core separately.
- The SQL Server server writes an audit log to `logs/audit.jsonl` under the working directory. Set `AUDIT_LOGGING=false` or `AUDIT_LOG_PATH` to move or silence it.

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
- DB MCP servers: postgres-mcp resolves via `uvx` only with `--with "mcp<2"` (its own `mcp>=1.5.0` range pulls the incompatible 2.x SDK); mssql-mcp runs the reader-tier `@connorbritain/mssql-mcp-reader@0.6.1` pinned over `@connorbritain/mssql-mcp-core@0.7.0`, both named explicitly so the reader's floating `^0.7.0` on the core cannot drift. The audit read the published `@connorbritain/mssql-mcp-core@0.7.0` tarball — where all the behaviour lives — plus the reader 0.6.1 tarball; `ConnorBritain/mssql-mcp-server` commit `b41251d5c447e00ebbdeb7be62a2f78f206afbdd` is the provenance of the shim and docs only, and carries no root `package.json`. Neither tarball has install scripts, and the only non-database network paths (Vault, Azure Key Vault, HTTP/syslog/CloudWatch audit sinks) are unreachable unless `ENVIRONMENTS_CONFIG_PATH` configures them. Live checks against a development database are pending — no `ASF_*` variables on the authoring machine; the SQL Server server was confirmed to launch and exit cleanly with a missing-configuration error when they are unset.
