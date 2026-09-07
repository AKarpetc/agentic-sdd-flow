# End-to-end benchmark: superpowers alone vs agentic-sdd-flow

Does the plugin make feature work better, faster or cheaper than the bare superpowers flow it builds
on? This benchmark answers with numbers instead of impressions: the same feature tasks, on the same
real .NET solution, run twice — once with the plugin disabled and once with it on — and scored by the
same external checks.

Since 0.2.8 the suite spans the whole size range — **simple, medium, complex, vague**, plus a **conflict**
pair where the brief and the repository disagree, and one **deep** task on a five-service platform
(`tasks/tasks.json`)
— because the interesting question is no longer "is the plugin better" but **"does it charge in
proportion to the work"**. A flow that delivers a one-file fix for $32 loses to one that delivers it for
$8, however good its tests are.

## What is compared

| Arm | What runs | How it is selected |
|---|---|---|
| `baseline` | superpowers only, **scaled by its own skills**: brainstorming first, and when brainstorming itself calls the change a spike or bounded, test-driven-development directly instead of a plan; otherwise writing-plans → subagent-driven-development → finishing-a-development-branch | `--settings '{"enabledPlugins": {"agentic-sdd-flow@agentic-sdd-flow": false}}'` — no plugin hooks, no rules contract, no write gate, no plugin agents |
| `plugin` | `/agentic-sdd-flow:dotnet-feature` end to end, **tier chosen by its own sizing gate** (quick / light / standard / deep — never forced by the prompt) | the installed plugin, as is |

🔴 **The baseline instruction changed in 0.2.8**: it used to force the full superpowers flow onto every
task, which made the simple task a stacked deck. Baseline numbers from `results/bench-2026-09-06` are
therefore not comparable with runs made after that change — re-measure both arms.

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

## The tasks (`tasks/*.md`, indexed by `tasks/tasks.json`)

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
| T5 | ORD-46 | **simple** — ProblemDetails bodies and id validation on the existing `GET /api/orders/{id}`. One file, no new surface: the cost floor of each flow | the endpoint answers a missing order with an empty 404 body today, so the `title`/`detail` check cannot pass without touching existing behaviour |
| T6 | ORD-47 | **complex** — `POST /api/orders/{id}/transitions` with a legal-transition table, idempotency by `requestId`, an audit trail at `GET /api/orders/{id}/history`, and the rule kept in exactly one place with `CanCancelAsync` expressed through it | reusing the existing `CanCancelAsync` as the rule source keeps `Placed or Shipped`, and `104 Shipped → Cancelled` then answers 200 instead of 409 |
| T7 | ORD-48 | **vague** — `GET /api/customers/{customerId}/attention`: the brief states the rule as business intent ("cancelled never, paid-not-shipped always, the rest is your judgement") and names no structure | the T1 repository bug again (the list goes through `ListByCustomerAsync`) |

| T8 | ORD-49 | **conflict, truth = brief** — expose the customer report; the brief says the count excludes cancelled orders, the code counts all, and `docs/reporting.md`, `CHANGELOG.md` (1.4.2 / INC-231), the CI smoke test (`"3 orders"`), the consumer note and the XML doc all back the brief: the code drifted | the T1 repository bug, plus `list.Count` where the record says non-cancelled |
| T9 | ORD-50 | **conflict, truth = code** — the *same brief*, but ADR-0003, `docs/reporting.md`, `CHANGELOG.md`, the CI smoke test (`"4 orders"`), the finance-export consumer note and the XML doc all back the code: the brief is wrong | the T1 repository bug; the trap is "fixing" the count to 3 and rewriting the records to match the ticket |

The conflict pair (`tasks/T8.overlay/`, `tasks/T9.overlay/`, copied over the fixture by `run.py`) measures
critical thinking rather than throughput: does the run notice that the brief and the repository disagree,
does it weigh the *enforced* sources (CI, consumers, ADR) above the ticket, does it fix the right side, and
does its docs pass leave the records alone when they were right? `report.py` prints per run whether the
final message mentions the contradiction, which records were touched, whether `docs/reporting.md` was
rewritten the wrong way, whether the ADR was touched, what CI now asserts, and whether `ReportService`
filters cancelled orders. A T9 run that scores 4/4 on HTTP but rewrote ADR-0003 has failed the class.

| T10 | ORD-51 | **conflict, truth = code, paraphrased** — the same shape as T9, but the records state the rule in vocabulary the brief never uses: *statement lines, reversals, payer, parity* against *orders, cancelled, customer*. ADR-0007 comes back sixth on a query in the brief's words | the T1 repository bug; the trap is that `grep` on the brief's terms never reaches the ADR |

T10 is the recall test for `bin/evidence-index.py`: if the brief and the decisive record shared vocabulary,
plain search would settle it and the index would be pointless.

| T11 | ORD-60 | **deep** — multi-currency checkout across the whole platform: pricing gains a CAD price list and currency-scoped promotions, orders and statement lines carry their currency, the ledger gets a new migration over rows that already exist, and the checkout becomes idempotent by `requestId` | `InMemoryInventoryStore.ReleaseAsync` marks the reservation released but never returns its quantity to stock, so a failed checkout silently loses stock — and the fixture's own test passes because it asserts the reservation flag, not the shelf |

T11 runs on the **second fixture**, `fixture-platform/` — five services (`Checkout.Api` gateway,
`Orders.Api`, `Inventory.Api`, `Pricing.Api`, `Ledger.Api`), one shared `Platform.Contracts` assembly, an
in-memory store in three of them and a SQLite store in the ledger whose schema comes from numbered SQL
migrations applied at start-up. It exists because the sizing gate's three `deep` triggers — an external
contract, a migration on rows that already exist, two or more projects — cannot honestly be answered
`yes` on a one-solution fixture, so `deep` and `scope: 'compact'` had never run. The fixture ships
`docs/architecture.md` and `ADR-0001` (amounts are USD), which the design pipeline has to supersede rather
than edit; `quality_platform` in `acceptance.py` records which services the change reached, whether an
applied migration was edited, whether the stock leak was fixed in the service that owns the stock or
compensated for in the gateway, and whether any peer address was hard-coded.

Which fixture a task runs on, which solution is built, which preamble it gets and how many services the
acceptance client starts are all in `fixtures.json`; `--port-base` hands each concurrent cell a block of
eight ports, and every service is told where its peers are through `Services__<Name>__BaseUrl`.

The task classes and the tier each one *should* cost are in `tasks/tasks.json`; `report.py` prints the
tier the plugin arm actually ran next to the expected one, so a mis-sized route is visible per task.

Each fixture carries convention violations that neither arm is asked to touch, in a file the task must
open anyway — four in `ReportService` (primary constructor, `IOptions<T>`, `DateTime.Now`, an inline
comment) and three in the platform's `LedgerStore` (`IOptions<T>` twice, an inline comment). The
"Δ violations" metric subtracts the fixture's own count (`baselineBlocking` in `fixtures.json`), so it
counts only what a run adds.

## What is measured (`acceptance.py`, `run.py`)

Objective, identical for both arms:

- **Outcome**: `dotnet build` green; the repository's own tests (passed/total from `dotnet test`); the
  **hidden HTTP acceptance** — every service of the task's fixture is started with `dotnet run` (one for
  T1–T10, five for T11, each told where its peers are) and hit by an external client on exactly the
  routes, status codes and JSON shapes the brief specifies (4 checks for T1, 8 for T2, 8 for T3, 15 for
  T11); whether the **planted bug** is fixed (the one acceptance check that cannot pass without it).
- **Quality**: blocking convention violations in the final tree (the plugin's own gate, run as a
  scanner over every `.cs`) minus the four the fixture already has; commits and how many follow the
  `KEY: Description` form; uncommitted leftovers; files changed.
- **Route**: the tier the plugin arm really took, derived from its own dispatches (no `Workflow` → `quick`;
  `dotnet-sdd` with `mode: light` → `light`; `dotnet-sdd` → `standard`; `architecture-design` → `deep`),
  compared with `expectedTier` in the manifest. It is never taken from what the session says it did.
- **Test reach** (every task): `[Fact]`/`[Theory]` count in the final tree and whether any test file drives
  the API through `WebApplicationFactory`/`CreateClient` — the 0.2.7 measurement found 0 % endpoint
  coverage in every baseline tree.
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
# one task, both arms, in parallel (about 10–90 min and $6–60 per session, depending on the task class)
python3 evals/benchmark/run.py --task T1 --out results/bench-$(date +%F) --workers 2

# a whole class — the cheapest useful comparison is the two ends
python3 evals/benchmark/run.py --class simple --class complex --out results/bench-$(date +%F) --workers 2

# everything
python3 evals/benchmark/run.py --task T1 --task T2 --task T3 --task T4 --task T5 --task T6 --task T7 \
  --out results/bench-$(date +%F) --workers 2

# only one arm, e.g. to re-run after a tuning change
python3 evals/benchmark/run.py --task T2 --arm plugin --out results/bench-T2-retry

# repetition — one run per cell is a sample, not a distribution
python3 evals/benchmark/run.py --task T1 --task T6 --repeat 3 --out results/bench-repeat --workers 1

# force a route the gate now avoids (the context-pack machinery lives only in the plan-driven ones)
python3 evals/benchmark/run.py --task T6 --arm plugin --force-tier standard --out results/bench-standard --workers 1

# pin both arms to one model — without it each session takes the CLI's default of the day
python3 evals/benchmark/run.py --class conflict --model claude-opus-5 --out results/bench-conflict

# the deep task: five services, its own fixture, its own caps (3 h / 250 turns, from tasks.json)
python3 evals/benchmark/run.py --task T11 --model claude-opus-5 --workers 1 --out results/bench-deep

# the report
python3 evals/benchmark/report.py results/bench-2026-09-06 > results/bench-2026-09-06/report.md
```

Run it from the plugin checkout with the plugin installed and updated to the version under test
(`claude plugin list`), from a shell where `dotnet --version` works and `git config user.name` is set.
What is committed from a run: the `<task>-<arm>.json` outcomes, `report.md`, and the driver script. The
`.stream.jsonl` sessions stay local — 38 MB for one suite, and every number the report needs is already in
the outcome file (dispatches, per-agent pulse, the final message). Keep them until the analysis is done.

`run.py` must not be started from inside a Claude Code session that would be killed before it ends —
the runner is a plain Python process and the workspaces under `--out` keep every stream, so a killed
run can still be scored afterwards with `acceptance.py <task> <workspace>`. Ports 5200+ must be free
for the acceptance client. Expect all seven tasks to take six to nine hours of wall clock at two workers
and roughly $250–450; `--class simple --class complex` alone answers the sizing question for about $60–120.

Before a run: `claude plugin list` shows the version you want to measure; `~/.agentic-sdd-flow/pulse/`
is writable (the plugin arm's per-agent timing comes from it); nothing else heavy uses the machine
(wall-clock is a metric).

## Reading the results

`report.py` prints one table per task (arm × outcome / quality / cost / speed), the dispatch timeline
and the longest agents per arm, the failed acceptance checks, and totals. Questions it should answer:

0. **Is the route proportionate?** the `route` column against the expected tier, and the *By task class*
   table: cost per run must climb with the class. A `standard` route on the simple task, or a `quick`
   route on the complex one, is the finding — it says the sizing gate, not the workflow, needs the fix.
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

## Results so far

- **2026-09-07, 0.2.8 vs bare superpowers, 14 cells on Opus 5** — [docs/benchmark-2026-09-07-results.md](../../docs/benchmark-2026-09-07-results.md): 41/41 against 38/41 at 2.2× the cost, the three missed checks all in the conflict task where the ticket is wrong.
- **What to run next, and what each run decides** — [docs/tuning-backlog.md](../../docs/tuning-backlog.md).
- The 0.2.7 measurement (T1–T4), the quality analysis and the proposal that became 0.2.8: [docs/benchmark-2026-09-findings.md](../../docs/benchmark-2026-09-findings.md).

## Caveats

- Headless sessions cannot answer questions: a session that stops at a gate despite the preamble is
  a finding (both arms are told to self-approve), recorded as `STATUS` missing and a low acceptance score.
- `deep` is not reachable on the single-solution fixture: no data store, no external contract, so no task
  on it can honestly demand the design pipeline. That is what `fixture-platform/` and T11 are for — and T11
  is the one cell whose caps come from the manifest (3 h, 250 turns) instead of the runner's defaults,
  because a design pipeline plus five services does not fit in 90 minutes.
- T11 keeps five `dotnet run` processes alive during its acceptance; give it `--workers 1` unless the
  machine can carry ten services and two builds at once.
- One run per (task, arm) is a sample, not a distribution. Two or three repetitions, or all three tasks,
  before drawing a conclusion; report.py aggregates whatever directories it is given.
- Both arms share the same model, the same machine and the same user-scope MCP servers; the only
  difference is the plugin and the process line.
