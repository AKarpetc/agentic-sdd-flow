# End-to-end benchmark: superpowers alone vs agentic-sdd-flow

Does the plugin make feature work better, faster or cheaper than the bare superpowers flow it builds
on? This benchmark answers with numbers instead of impressions: the same three feature tasks, on
the same real .NET solution, run twice — once with the plugin disabled and once with it on — and
scored by the same external checks.

## What is compared

| Arm | What runs | How it is selected |
|---|---|---|
| `baseline` | superpowers only: brainstorming → writing-plans → subagent-driven-development → finishing-a-development-branch | `--settings '{"enabledPlugins": {"agentic-sdd-flow@agentic-sdd-flow": false}}'` — no plugin hooks, no rules contract, no write gate, no plugin agents |
| `plugin` | `/agentic-sdd-flow:dotnet-feature` end to end: design gate → plan → plan review → dotnet-sdd (implement, tests, debug, review, verify, fix, final review) | the installed plugin, as is |

Both arms get the identical prompt: the same preamble (`tasks/_preamble.md`: non-interactive, approve
the recommended option at every gate, commit on `main`, never push, end with `STATUS/COMMITS/NOTES`),
the same task brief, and one arm-specific "process for this run" line from `tasks/arms.json`.
Sessions are headless `claude -p` with `--permission-mode acceptEdits`, `--max-turns 120` and a
90-minute wall clock. Every event is streamed to disk with an arrival timestamp so stage timing can be
reconstructed for either arm. Three runner details come from the first measurement
(`results/bench-2026-09-06/report.md`): the prompt is passed on **stdin**, not argv — with it in argv every
session's command line contains `Orders.Api`, and a neighbouring session's `pkill -f "Orders.Api"` after a
smoke test SIGTERMs the whole session (exit 143) and aborts its background workflow, which is how four
plugin-arm runs died; `CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=0` lifts the headless 10-minute idle ceiling
on background workflows; and the checker forces `DOTNET_CLI_UI_LANGUAGE=en`, because a localized SDK prints
a test summary the parser cannot read. Sessions of both arms still share one machine, so a `pkill` by
project name in one arm can still hit the other arm's `dotnet` build, test or smoke server — run with
`--workers 1` when that must not happen.

## The tasks (`tasks/T1.md`, `T2.md`, `T3.md`)

Each task is a real feature on `fixture/` (a `dotnet new` solution: `Orders.Api` minimal host with an
in-memory seeded repository, `Orders.Api.Tests` with xUnit + NSubstitute + FluentAssertions 7.2.0;
restores from nuget.org only, no VPN needed). Each task forces every stage — a design decision, a
plan, code, tests, review — and each one trips over a **planted bug** that only a root-cause
investigation resolves, so the debugging stage is exercised as well:

| Task | Key | Feature | Planted bug the criteria expose |
|---|---|---|---|
| T1 | ORD-42 | `GET /api/customers/{id}/orders/total` — non-cancelled sum via the repository, logic in the service layer | `InMemoryOrderRepository.ListByCustomerAsync` filters on `order.Id` instead of `order.CustomerId`: every total is 0 |
| T2 | ORD-43 | `POST /api/orders/{id}/cancel` with 204/409/404 and ProblemDetails, persisted status, in-memory outbox exposed at `GET /api/outbox` | `OrderService.CanCancelAsync` says Placed **or Shipped** — the rule must be Placed or Paid, and the task names this method as the single source of the rule |
| T3 | ORD-44 | `GET /api/customers/{id}/orders?page&size` — 1-based paging through the existing `PageMath.Skip`, validation with ProblemDetails | `PageMath.Skip` returns `page * size` (0-based); plus the T1 repository bug, since the listing goes through the same method |
| T4 | ORD-45 | `GET /api/orders/{id}/pricing` with configured promotions (percentage / fixed / expired), a customer report at `GET /api/customers/{id}/report` through the existing `ReportService` — the brief is deliberately loose on structure and asks for extensibility and a controllable clock | the T1 repository bug again (the report goes through `ListByCustomerAsync`), plus the four convention violations sitting in the file the task must touch (`ReportService`) |

The fixture also carries four convention violations in `ReportService` (primary constructor,
`IOptions<T>`, `DateTime.Now`, an inline comment) that neither arm is asked to touch — the
"Δ violations" metric counts only what a run adds.

## What is measured (`acceptance.py`, `run.py`)

Objective, identical for both arms:

- **Outcome**: `dotnet build` green; the repository's own tests (passed/total from `dotnet test`); the
  **hidden HTTP acceptance** — the API is started with `dotnet run` and hit by an external client on
  exactly the routes, status codes and JSON shapes the brief specifies (4 checks for T1, 8 for T2, 8
  for T3); whether the **planted bug** is fixed (the one acceptance check that cannot pass without it).
- **Quality**: blocking convention violations in the final tree (the plugin's own gate, run as a
  scanner over every `.cs`) minus the four the fixture already has; commits and how many follow the
  `KEY: Description` form; uncommitted leftovers; files changed.
- **Cost and speed**: wall clock, `total_cost_usd`, input / output / cache tokens, turns, tool calls
  (top-level and inside subagents), number of agents dispatched.
- **Stages**: the minute at which each top-level Skill / Agent / Workflow dispatch happened, and per
  agent its duration and tool count — from the plugin's pulse file for workflow agents, from nested
  stream events for baseline subagents.
- **Self-report**: the `STATUS` line the session ends with, compared with what the checks found.
- **T4 design signals** (`quality` block): a clock abstraction present (`TimeProvider` / `I*Clock`), system-clock
  calls outside it, `IOptions<T>` vs `IOptionsSnapshot`/`IOptionsMonitor`, promotions really in `appsettings`,
  promotion kinds as separate types, and whether `ReportService` kept its primary constructor. These are
  the differences a convention gate and a reviewer are supposed to make; the blind comparative reviews
  in the results directory cover what a grep cannot.

## How to run

```
# one task, both arms, in parallel (about 30–90 min and $20–60 per session)
python3 evals/benchmark/run.py --task T1 --out results/bench-$(date +%F) --workers 2

# everything
python3 evals/benchmark/run.py --task T1 --task T2 --task T3 --out results/bench-$(date +%F) --workers 2

# only one arm, e.g. to re-run after a tuning change
python3 evals/benchmark/run.py --task T2 --arm plugin --out results/bench-T2-retry

# the report
python3 evals/benchmark/report.py results/bench-2026-09-06 > results/bench-2026-09-06/report.md
```

Run it from the plugin checkout with the plugin installed and updated to the version under test
(`claude plugin list`), from a shell where `dotnet --version` works and `git config user.name` is set.
`run.py` must not be started from inside a Claude Code session that would be killed before it ends —
the runner is a plain Python process and the workspaces under `--out` keep every stream, so a killed
run can still be scored afterwards with `acceptance.py <task> <workspace>`. Ports 5200+ must be free
for the acceptance client. Expect the whole suite to take three to five hours of wall clock at two
workers and roughly $150–300.

Before a run: `claude plugin list` shows the version you want to measure; `~/.agentic-sdd-flow/pulse/`
is writable (the plugin arm's per-agent timing comes from it); nothing else heavy uses the machine
(wall-clock is a metric).

## Reading the results

`report.py` prints one table per task (arm × outcome / quality / cost / speed), the dispatch timeline
and the longest agents per arm, the failed acceptance checks, and totals. Questions it should answer:

1. **Does the plugin deliver more of the criteria?** acceptance and planted-bug columns.
2. **At what price?** cost, tokens and wall clock per delivered check (compute cost ÷ passed checks).
3. **Is the code cleaner?** Δ violations and commit hygiene — the baseline has no gate, so anything
   above zero there is what the gate would have caught.
4. **Where does the time go?** the stage table: a plugin arm that spends most of its wall clock in
   review/verify/fix rounds, or a baseline that spends it re-running failing tests, is a tuning target.
5. **Did the debugger earn its place?** whether the planted bug was fixed at the root (the acceptance
   check) and, in the plugin arm, whether the Debug phase ran (pulse shows `debugger`) or the
   implementer found it alone.

Tuning spots to look for: agents with the largest time ÷ tool-calls ratio (waiting on builds), fix
rounds that close nothing, reviewers producing findings the verifier rejects, plan review rejecting
plans for hygiene rather than substance, sessions that hit `--max-turns` before finishing.

## Caveats

- Headless sessions cannot answer questions: a session that stops at a gate despite the preamble is
  a finding (both arms are told to self-approve), recorded as `STATUS` missing and a low acceptance score.
- One run per (task, arm) is a sample, not a distribution. Two or three repetitions, or all three tasks,
  before drawing a conclusion; report.py aggregates whatever directories it is given.
- Both arms share the same model, the same machine and the same user-scope MCP servers; the only
  difference is the plugin and the process line.
