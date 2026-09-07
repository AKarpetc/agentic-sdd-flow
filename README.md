# agentic-sdd-flow

Spec-driven agentic development flow for .NET as a Claude Code plugin: opinionated conventions,
Roslyn-first specialist agents, a deterministic implement → test → review → verify → fix
workflow, and one entry-point skill.

## Install and connect

### 1. Prerequisites (once per machine)

| Need | Check | Install |
|---|---|---|
| Claude Code, current release | `claude --version` | `claude update` |
| .NET SDK on PATH | `dotnet --version` | https://dot.net — the version your solutions target |
| Python 3.9+ | `python3 --version` | ships with macOS/Xcode tools; `apt install python3` on Linux |
| CWM.RoslynNavigator ≥ 0.8.0 | `dotnet tool list --global` | installed on first use by `roslyn-query.py`; or `dotnet tool install --global CWM.RoslynNavigator` — keep `~/.dotnet/tools` on PATH |
| superpowers plugin (brainstorming, writing-plans, SDD scripts) | `claude plugin list` | `claude plugin install superpowers@claude-plugins-official` |
| Git identity | `git config user.name` | the workflows commit on your behalf |

Optional: `node` (only for `node --check` in the test-suite), `uvx`/`npx` for the database MCP servers,
the `spec-coding` MCP server at user scope for the `spec-coding` skill.

### 2. Install the plugin

Personal (user scope, every repository):
```
claude plugin marketplace add AKarpetc/agentic-sdd-flow
claude plugin install agentic-sdd-flow@agentic-sdd-flow
```

Team-wide: commit this to the repository's `.claude/settings.json` and every developer gets the
marketplace registered; each of them still runs the `install` line once, then restarts Claude Code.
```json
{
  "extraKnownMarketplaces": { "agentic-sdd-flow": { "source": { "source": "github", "repo": "AKarpetc/agentic-sdd-flow" } } },
  "enabledPlugins": ["agentic-sdd-flow@agentic-sdd-flow"]
}
```

**Restart Claude Code after installing or updating.** Skills register live, but agents, workflows
and hooks are read at session start.

### 3. Verify

```
claude plugin list | grep -A3 agentic-sdd-flow          # Status: enabled, the version you expect
roslyn-query.py <project-or-solution> --status           # a JSON status line, loadSeconds > 0
```
In a new session the injected context must show one `<rules-contract enforcement="mandatory">` block
(plus one `<overlay-contract>` inside it when the repository has an overlay). Ask the session to write a
`.cs` file with a primary constructor on a DI class: the hook must reject it with `[no-primary-ctor]`.
The `Agent` tool's list must contain `agentic-sdd-flow:tests-writer`; a bare `tests-writer` means a
project-level `.claude/agents/` still shadows the plugin — remove it.

### 4. Connect a repository

Add the two consumer files (copy from `examples/overlay/`):

- `.claude/agentic-sdd-flow.json` — `projects` (name → solution path, what `roslyn-query.py <name>`
  resolves), `plansDir`, `adrDir`, `docsPaths`, `checks`, `handoffs`, `overlayContract`.
- `.claude/rules/OVERLAY-CONTRACT.md` — facts about your systems; injected right after the plugin
  contract and never allowed to relax it.

Delete anything the plugin now provides: project-level copies of the rules, the agents with the same
names, the `roslyn-navigator.sh` script and the local rule hooks. Keep only company-specific skills
(the ones your `handoffs` point at).

### 5. Wire the two things a plugin cannot ship

Roslyn fallback MCP server (the primary path is `roslyn-query.py` over Bash; the MCP server serves the
solution pinned by `bin/bind-roslyn.sh` and its tool names match the agents' allowlists):
```
claude mcp add -s user cwm-roslyn-navigator -e DOTNET_ROOT=/usr/local/share/dotnet -- <plugin checkout>/bin/roslyn-navigator.sh
# DOTNET_ROOT is the directory that holds the dotnet executable (`dirname "$(realpath "$(which dotnet)")"`)
```
Agent pulse in the status line (see *Agent pulse* below), in `~/.claude/settings.json`:
```json
{ "statusLine": { "type": "command", "command": "<plugin checkout>/bin/agent-pulse.sh", "refreshInterval": 5 } }
```
`<plugin checkout>` is a git clone of this repository, not the version-numbered cache under
`~/.claude/plugins/cache/` — the clone path survives updates. Database access for the SQL agents
needs `ASF_POSTGRES_URI` or `ASF_MSSQL_*` in the shell (see *Databases*).

### 6. Update

Every runtime change ships as a new version: bump `version` in `.claude-plugin/plugin.json` **and**
`.claude-plugin/marketplace.json`, push, then on each machine
```
claude plugin update agentic-sdd-flow@agentic-sdd-flow   # "already at the latest version" means the version was not bumped
```
and restart. `claude plugin uninstall` + `install` is the fallback when the cache looks stale.

### Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| No `<rules-contract>` block at session start | plugin not enabled for this scope, or the session predates the install | `claude plugin list`; restart |
| Agents missing from the `Agent` tool, or bare names present | started before the install; a project `.claude/agents/` shadows the plugin | restart; delete the project copies |
| `cwm-roslyn-navigator` fails with ENOENT | the user-scope MCP entry still points at a deleted script | re-add it as in step 5 |
| `roslyn-query.py` returns an empty graph | wrong solution resolved (mis-bind), not clean code | pass the explicit `.sln` path; check `projects` in the config |
| `plugin update` says "already at the latest version" after a push | the version was not bumped | bump both manifests and push again |
| The write gate blocks a legacy file you only touched | it compares with `HEAD`; a genuinely new violation was introduced | fix it, or tune the check id in `checks` |

## Use

```
/agentic-sdd-flow:dotnet-feature PROJ-123 add a paged brands endpoint to the orders service
```
Design (approval gate) → plan → `dotnet-sdd` workflow → branch, never pushed.

### The change is sized, and the route is proposed with its price

The entry skill answers five questions from the brief ([the rubric](skills/dotnet-feature/references/sizing.md)),
then **proposes three routes with what each costs and recommends one** — it does not silently pick. A
headless run takes the recommendation and says so; `--tier` or one word from the user overrides it.

| Route | What runs | Measured (Opus 5, benchmark fixture) |
|---|---|---|
| **A `superpowers`** | brainstorming → test-driven-development in the session, **no plugin agent**; the rules still hold through the hooks | $2.23 / 3.8 min on the simple task, $4.30 / 7.4 min on the complex one |
| **B `mix`** | A, then `dotnet-sdd` in `mode: 'review'`: one whole-branch review, every finding through the verifier, one fix wave | + $4–7 |
| **C `agentic`** | `light` (plan → implement/tests per task + one branch review), `standard` (+ per-task review, verified fix loop), `deep` (`architecture-design` first) | $9.32 / 22 min (`light`), $31.51 / 73 min (`standard`) |

Recommend A for one or two files, B for a change inside one service that another service reads, C where a
mistake reaches another team: a store, a migration, an external contract, two or more projects. On the
measured tasks A and C delivered the same acceptance and the same defect closures — the plugin's value on
that fixture was the review, not the code, which is exactly what B buys.

When a brief says one thing and the repository another — the code, a test, a CI assertion, an ADR, a doc,
a comment, a consumer note — nobody picks a side: the implementer stops with the contradiction,
`evidence-reconciler` weighs every source (executed > decided > descriptive > intent) and returns `brief`,
`code` or `undecided` with an evidence table; `code` or `undecided` returns `status: 'contradiction'` and
the user rules. Its recall comes from `bin/evidence-index.py` — BM25 over the repository's *records* (docs,
ADRs, consumer notes, changelogs, CI files, and the XML docs and comments of `.cs`) through stdlib SQLite
FTS5, no server, no model, nothing leaving the machine — because the source that settles a contradiction is
usually worded differently from the ticket. Hits are leads the agent must open and read; see
[docs/vector-store-evaluation.md](docs/vector-store-evaluation.md) for why this and not Chroma or Pinecone,
and what would change that.

A review finding that describes a reproducible failure is a `defect`, and a `defect` is never below
`important` however soft the section it was written in; the verifier may raise a severity it can
reproduce, and a minor defect rides along with the next fix round instead of being deferred for ever.

Direct pieces: `/agentic-sdd-flow:dotnet-code-review`, the `tests-writer` agent,
`Workflow({ name: 'agentic-sdd-flow:dotnet-sdd', args: { project, projectDir, plan, taskKey, mode } })`.
On the architectural path the entry point can run `architecture-design` first (drivers → current C4 → three lens proposals → judge panel → threat model → data review; ADRs + spec after you approve). Every design artifact carries its diagrams as Mermaid fences (`skills/architecture-design/references/sketch-conventions.md`), so a sketch is reviewable text in the merge request and importable into FigJam later. Direct call: `Workflow({ name: 'agentic-sdd-flow:architecture-design', args: { brief, projects, workDir, adrDir, specsDir, slug } })`.

Every stage has its own reviewer, and the author never reviews its own work: `design-reviewer`
verdicts the decision table after the judge panel (Design review) and the written spec after the
ADRs (Spec review, one fix pass by the spec author, scoped re-review); `plan-reviewer` gates the plan
inside `dotnet-sdd` before the first implementer run (Plan review — a critical or important finding
returns `status: plan_rejected` with the findings as open questions, the author fixes the plan and
reruns with `resumeFromRunId`); `code-reviewer` reviews every task and the whole branch, with
`findings-verifier` filtering noise before the fix loop. All three return the same verdict shape:
`approved`, severity-ranked `findings` with stable ids, and a scoped re-review on the next round.

When something does not work, the `debugger` agent runs before anyone changes code: it reproduces
the symptom, tests one hypothesis at a time with Roslyn, writes a regression test and a diagnosis
file, and returns a fix brief that `dotnet-implementer` executes. The `dotnet-sdd` workflow dispatches
it on its own in two places — when `tests-writer` cannot get the tests green (Debug → Fix → Tests
once more) and when a review fix round closes nothing (Debug before the next Fix).

Plugin agents and workflows register at session start: restart Claude Code after installing or
updating the plugin.

## Agents

Workflow agents: `dotnet-implementer`, `findings-verifier`, `code-reviewer`, `plan-reviewer`, `design-reviewer`, `tests-writer`, `debugger`, `evidence-reconciler`, `design-simplicity`, `design-scalability`, `design-boundaries`, `design-judge`.
Specialists: `dotnet-architect`, `api-designer`, `grpc-contracts`, `ef-core-specialist`, `postgres-specialist`, `tsql-specialist`, `migration-reviewer`, `security-auditor`, `performance-analyst`, `concurrency-specialist`, `devops-engineer`, `build-error-resolver`, `refactor-cleaner`, `test-quality-auditor`, `docs-sync`.
All resolve as `agentic-sdd-flow:<name>` and none can dispatch other agents. Specialists end with a Hand-offs section using the keys listed under *Company overlay*; workflow agents return JSON instead.

## What the plugin enforces

`rules/RULES-CONTRACT.md` is injected into every session, subagent and plan-driven prompt; a
PostToolUse hook rejects newly introduced violations in `.cs`/`.csproj` files. Its **Delegation**
section is the dispatch policy: a whole job in a specialist's domain goes to that agent through the
`Agent` tool, and loading the matching skill inline instead counts as a violation. The write gate
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

## Agent pulse (status line)

A long subagent run looks frozen: the parent session is blocked on the `Agent` call and cannot post
anything until it returns, and no hook fires on a timer. What can move is the status line, so the
plugin keeps an **agent pulse** for it. `PreToolUse`, `SubagentStart` and `SubagentStop` hooks record
every subagent's type, start time, tool count and last action (`Bash dotnet test`, `Edit
OrderServiceTests.cs`, `find_symbol OrderService`) in `~/.agentic-sdd-flow/pulse/<session>.json`;
`bin/agent-pulse.sh` renders it:

```
⟳ tests-writer 2m10s · Bash Run the tests (14)  |  ⟳ code-reviewer 0m40s · Read OrderService.cs (6)
```

A plugin cannot ship a `statusLine`, so wire it once in `~/.claude/settings.json` (the checkout
path survives plugin updates; `refreshInterval` keeps it ticking while the session waits):

```json
{
  "statusLine": { "type": "command", "command": "<plugin checkout>/bin/agent-pulse.sh", "refreshInterval": 5 }
}
```

Finished agents stay visible as `✓ tests-writer 2m30s` for two minutes. The hook never blocks and
never writes to the model's context; a broken pulse costs nothing but the line.

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
- A repository that never uses them can leave the `ASF_*` variables unset (the servers fail closed) or remove the two entries from its own `.mcp.json` override.

## Tests

```
python3 -m unittest discover -s tests -v
shellcheck -x -P SCRIPTDIR bin/*.sh
```

Standard-library `unittest` only (Python ≥ 3.9). `tests/` covers the write gate rule by rule and
end-to-end through stdin (including the committed-baseline diff and `checks` re-tiering), the
three injection modes and the navigator version note, the config loader, the Roslyn resolver /
pin / launcher scripts against a fixture repository, and a structural lint: manifests, hooks,
MCP entries, agent and skill frontmatter, navigator tool names, hand-off keys, README check ids,
relative links and the workflow scripts. `.github/workflows/tests.yml` runs the same on push.

Work distribution is pinned twice. Statically, `tests/test_manifest.py` asserts which agent each
workflow phase dispatches to (implementer never reviews, reviewer never implements, fan-out phases
run in parallel). Behaviourally, `evals/routing/` runs nine headless `claude -p` sessions inside a
copy of `evals/fixtures/orders-service` and checks the top-level dispatch: review → the
`dotnet-code-review` skill or `code-reviewer`, tests → `tests-writer`, a ticket → `dotnet-feature`,
a broken build → `build-error-resolver`, a slow query → the EF Core specialist, a cross-service
design → `architecture-design`, a migration → `migration-reviewer`, a Python edit → no plugin agent
at all, and a primary-constructor write → rejected by the gate. Each session costs about a dollar
and the fixture never needs the .NET SDK.

```
python3 evals/routing/run.py [--case NAME] [--workers 3] [--out DIR]
```

The end-to-end benchmark against bare superpowers lives in `evals/benchmark/`; the 0.2.7 measurement, the quality analysis and the proposal for 0.2.8 are summarised in [docs/benchmark-2026-09-findings.md](docs/benchmark-2026-09-findings.md), and what 0.2.8 changed in response — the tier gate, the defect floor, the overhead cuts — in [docs/0.2.8-tiered-flow.md](docs/0.2.8-tiered-flow.md).

`claude plugin eval` is the intended home for these cases once it is enabled for the account; the
runner is a stand-in with the same shape (prompt, expected dispatch, forbidden dispatch).

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
- Plugin-declared MCP servers surface as mcp__plugin_agentic-sdd-flow_<server>__<tool>; the DB agents list both that and the bare spelling. The Roslyn fallback server is listed bare in every agent (its primary path is roslyn-query.py over Bash) — verify the prefixed spelling at the next trial.
- architecture-design trial (2 projects, 3 lenses, 3 judges): first run 15 agents / 73 min → `proposed` (11 drivers, 3 proposals, panel 79/78/78, refutation held, 17 decisions, 11 threats, data review CHANGES_REQUESTED with 10 findings, 8 unanswered drivers); second run with `approvedProposalId` + `resumeFromRunId` replayed 15 cached agents and ran 2 → `recorded` with 17 ADRs and a 521-line spec; the writing-plans intake accepted the spec without edits.
- Agents and workflows register at session start, but on this build the 0.2.0 agents became available mid-session once the consuming repository's shadowing `.claude/agents/` was removed; skills register live after `claude plugin update`.
- Consumer setup verified on a repository with an overlay contract and a 30-project index: overlay injected once, no local hooks, project names resolve through the config, write gate active. A user-scope `cwm-roslyn-navigator` entry must point at this plugin's `bin/roslyn-navigator.sh` once the consumer deletes its own copy of the script.
