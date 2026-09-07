# Benchmark of agentic-sdd-flow 0.2.7 against bare superpowers — findings and proposal

Measured 2026-09-06/07 on the harness in `evals/benchmark/` (same four feature tasks on the same fixture
solution, one headless session per task and arm, scored by external HTTP checks, coverage and blind
reviews). Raw numbers: [results/bench-2026-09-06/report.md](../results/bench-2026-09-06/report.md) and
[results/bench-2026-09-07-T4/report.md](../results/bench-2026-09-07-T4/report.md); the quality work:
[results/bench-2026-09-06/quality-analysis.md](../results/bench-2026-09-06/quality-analysis.md) and the blind
reviews under `results/bench-2026-09-06/reviews/`.

## 1. Headline numbers

| task | arm | acceptance | own tests | line / branch coverage | wall | cost |
|---|---|---|---|---|---|---|
| T1 order total | superpowers | 4/4 | 5 | 41 % / 0 % | 11 min | $8.33 |
| T1 | plugin | 4/4 | 18 | 72 % / 0 % | 34 min | $31.95 |
| T2 cancel + outbox | superpowers | 8/8 | 13 | 34 % / 57 % | 22 min | $11.69 |
| T2 | plugin | 8/8 | 34 | 84 % / 93 % | 51 min | $46.91 |
| T3 paged listing | superpowers | 8/8 | 19 | 48 % / 38 % | 18 min | $12.12 |
| T3 | plugin | 8/8 | 34 | 71 % / 50 % | 42 min | $39.72 |
| T4 promotions (loose brief, Opus) | superpowers | 8/8 | 63 | – | 70 min | $22.39 |
| T4 | plugin | 0/8, no code | 0 | – | 90 min (timeout) | ≈2 M workflow tokens |

T1–T3 ran on Fable, T4 on Opus (the CLI's default that day; both arms the same), so T4 is comparable only
with itself. Every planted bug was fixed at the root by both arms in T1–T3; the plugin's Debug phase never
ran in a surviving session (the briefs pointed at the bugs). Δ convention violations was 0 for both arms in
T1–T3 (nothing tempted the gate) and −4 for the baseline in T4 (it cleaned `ReportService` on its own).

## 2. What the tests say

- **The baseline never tests the endpoint.** `Program.cs` coverage is 0 % in all three of its T1–T3 trees
  and the T4 tree has no HTTP test either; in the pseudo-mutation check "endpoint mapping broken" fails zero
  baseline tests in every task. The plugin's `tests-writer` adds `WebApplicationFactory` tests every time:
  routes, status codes, ProblemDetails bodies, JSON shape, the seeded acceptance sequence.
- **About 60 % of the plugin's tests are real protection, about 40 % are volume.** The blind auditors
  counted 11/18, 23/34 and 20/34 protective tests; the rest test C# record equality, DI registrations,
  untouched members, duplicate happy paths or framework binding. Per test, both arms look alike (1–2
  assertions, 13–18 lines) — the plugin's are not emptier, there are simply more of them.
- **Assertion quality is one notch higher in the plugin's suites** (`BeEquivalentTo` with typed expected
  objects, full-record checks where the baseline matches two fields, real cancellation tokens) and every
  plugin test follows the test contract (AAA, `_When_…_Should_`, `_sut`); 0 % of the baseline's do — in T4
  0 of 63.
- Auditor scorecards (0–5, baseline vs plugin): coverage 2–3 vs 5, regression-catching 3 vs 4–5, assertion
  quality 3 vs 4, economy 4–5 vs 3, conventions 2–3 vs 4–5. All three "keep which suite" verdicts: the plugin's.

## 3. What the production code says

- Blind code reviews chose the plugin's change in 3/3 tasks, but the margin lives in the tests. T2's
  production code is "nearly line-for-line identical"; T1 differs by a typed DTO; T3 by validation inside
  the service, `Result<T>` and `internal` — at the price of a NuGet dependency for one method.
- **Both arms ship the same real defects**: a check-then-act race on concurrent cancels (T2), an `int`
  overflow in paging arithmetic (T3), the rule text duplicated in a 409 title. The plugin's final review
  *found* them and filed them as `minor`; `dotnet-sdd` defers minors, so nothing fixed them.
- On the loose T4 brief the baseline reached convention-native production code without the plugin
  (`TimeProvider`, `IOptionsSnapshot`, promotions in configuration, open/closed rule types, all four
  `ReportService` violations gone) and would still be sent back by a contract review: no HTTP tests, a
  config typo in `Kind` silently disables a promotion, `IValidateOptions` implemented but bypassed, ~25 files
  where ~15 would do.
- The plugin arm on T4 spent minutes 3–72 in `architecture-design` (17 agents, three lens proposals, five
  judge passes, threat model, design review, 48 000 words of artefacts) and was in the second design pass
  when the 90-minute budget ended. A one-service change with no data store and no contract change took
  the panel route.

## 4. Where the plugin's time and money go

| phase of `dotnet-sdd` | share of wall clock | share of tokens | note |
|---|---|---|---|
| Analyze helpers (`git rev-parse` ×4 per task) | 5–10 % | **35 %** | 40–50 k tokens each, on Fable, for a SHA |
| Tests (`tests-writer`) | 18–20 % | 18–20 % | 2–4 min per task, cold `dotnet build/test` each time |
| Review (`code-reviewer`) | 23–25 % | 23–25 % | 7–12 findings per final review, all deferred |
| Plan review, twice (skill + workflow) | ≈ 3–4 min | 3 % | same plan reviewed twice |
| Implement | 9–10 % | 9–10 % | |
| Final review | 6–9 % | 6–9 % | |

Plus: test-only and verification-only plan tasks get the full implement → tests → review cycle (T2: 5 tasks,
34 tests for an 8-check feature), and every agent runs on the session's model while superpowers' SDD hands
Haiku/Sonnet to its subagents.

## 5. Verdict

The plugin's extra cost buys something real: endpoint and contract tests that the baseline never writes,
higher branch coverage, contract-compliant tests and a review that finds real defects. It does not buy
better production code — that is marginal — and the defects the review finds are not fixed. Roughly half of
the spend is overhead (Analyze helpers, double plan review, test padding, full-effort review of green
tasks) and, on a loose brief, the design gate can consume the whole budget. So: keep the plugin for the
tests, the gate and the review; cut the overhead; make the review's findings reach the code; size the
architectural route.

## 6. Proposal for 0.2.8

### 6.1 Defects found by the review must be fixed

Today: findings get `severity` from the report section they land in; a race or an overflow filed under
"Refactoring Suggestions" becomes `minor` unless it breaks a stated requirement, and `dotnet-sdd` defers
every `minor`. Change:

1. **Rubric floor** in `skills/dotnet-code-review` (severity mapping + checklist): any finding that describes
   a reproducible failure in changed code (data race, lost update, overflow, wrong money rounding, swallowed
   exception, resource leak, null dereference) is at least `important` whatever its section.
2. **`kind: defect | convention | style`** on every finding (workflow schema + reviewer output). Blocking is
   decided by `kind = defect` or by severity, so a defect cannot be hidden by a low severity; `convention`
   and `style` minors stay deferred as now.
3. **Verifier may raise severity**: `findings-verifier` returns `severityAdjustment` when it reproduces the
   failure.
4. **Minor defects ride with serious fixes, never get their own loop:**
   - they do not count for approval, stall or the round cap;
   - when a fix round runs anyway, minor defects from the same files are appended to the implementer's list
     and the scoped re-review answers "addressed?" for them in the same call, at no extra round;
   - when nothing serious remains, accumulated minor defects are fixed once in the final fix wave together
     with the final review's blocking findings; if the final review is clean, one fix wave with only them
     runs, followed by a scoped `effort: low` "addressed?" check instead of a full re-review, and whatever
     is still open is parked as `unstable` in the report — no further loop.
   Expected cost: one cheap check per task (≈1–2 min, ≈$1); on T1–T3 it would have closed both real bugs.

### 6.2 Cut the overhead without touching the quality drivers

| change | where | expected saving per task |
|---|---|---|
| Analyze helpers on Haiku with a minimal prompt, or one helper instead of four | `dotnet-sdd.js` `sha()` / task-base agents | ≈30 % of tokens, ≈$10 |
| one plan review: `skipPlanReview: true` when the skill's reviewer approved | `dotnet-feature` → workflow args | ≈2 min, ≈$2 |
| test-only / verification-only plan tasks → `tests-writer` alone | Analyze / task loop | 1–2 agent cycles on plans like T2 |
| `tests-writer` brief: no tests for untouched members, records, DI wiring or framework behaviour | `testsPrompt` | ≈30 % of the Tests phase, the padding the auditors listed |
| per-task review at `effort: low` when tests are green and the diff is small; full final review kept | review round 0 | ≈30 % of the Review phase |
| build once per task and let agents reuse the output | implementer / tests / review prompts | part of the 8–12 s per tool call |

Target: ≈$18–22 per task instead of $32–47 at the same coverage and with defects closed.

### 6.3 Size the architectural route

The design gate must not send a single-service change with no new data store and no contract change to
`architecture-design`; that route is for changes spanning services, stores or contracts. When it does run,
cap the panel (one judge pass, threat model only when a trust boundary changes) and keep the second pass
(ADRs + spec) inside the same budget.

### 6.4 Defects from the run itself

`Workflow` args arrive as a JSON string (parse them in both workflow scripts — the patch a benchmark session
left uncommitted in `workflows/` does exactly this); `resumeFromRunId` after editing a plan replays the
cached rejection (fresh run, or plan hash in the prompt); the implementer creates `feature/<KEY>` even when
told to commit on `main`; a workflow must never write outside `projectDir`.

### 6.6 What was actually built

0.2.8 implements §6.1–6.4 and adds the tier gate the proposal implies:
[0.2.8-tiered-flow.md](0.2.8-tiered-flow.md).

### 6.5 How to verify

Re-run `evals/benchmark` on 0.2.8 for T1–T4 with the same runner (prompt on stdin, `--workers 1` if sessions
may still `pkill` each other's `dotnet`), then compare against this document: cost and wall per task,
acceptance, coverage, the two known defects closed, and T4 delivered inside the budget.
