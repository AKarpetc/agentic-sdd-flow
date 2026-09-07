# Benchmark 2026-09-07 — 0.2.8 against bare superpowers

All cells: Opus 5 (`--model claude-opus-5`, both arms), the `evals/benchmark` fixture, hidden HTTP
acceptance, one session per cell. Raw outcomes under `results/bench-2026-09-07-0.2.8`,
`results/bench-context-probe`, `results/bench-conflict`, `results/bench-T7`.

Two things changed mid-run and are marked per row: the **routing fix** (an empty test project stopped
being a reason to escalate, and `quick` became the superpowers flow itself), and the **mix route**
(superpowers writes, `dotnet-sdd mode: 'review'` gates). Rows from before a fix are kept, because the
difference between them *is* the measurement.

## 1. Every valid run

| task | class | arm | route | wall | cost | acceptance | planted bug | tests | endpoint test | Δ violations | agents |
|---|---|---|---|---|---|---|---|---|---|---|---|
| T5 | simple | superpowers | – | 3.8 min | $2.23 | 5/5 | ✅ | 5 | ✅ | +0 | 0 |
| T5 | simple | plugin (before fix) | `light` | 16.1 min | $7.38 | 5/5 | ✅ | 5 | ✅ | +0 | 5 |
| T5 | simple | **plugin (after)** | `quick` | **2.7 min** | **$2.24** | 5/5 | ✅ | 4 | ✅ | +0 | 0 |
| T1 | medium | superpowers | – | 3.9 min | $2.41 | 4/4 | ✅ | 7 | ✅ | +0 | 0 |
| T1 | medium | plugin (before fix) | `light` | 21.7 min | $9.32 | 4/4 | ✅ | 7 | ❌ | +0 | 9 |
| T1 | medium | **plugin (after)** | `quick` | **4.5 min** | **$3.23** | 4/4 | ✅ | 7 | ✅ | +0 | 0 |
| T6 | complex | superpowers | – | 7.4 min | $4.30 | 10/10 | ✅ | 34 | ✅ | +0 | 0 |
| T6 | complex | plugin (before) | `standard` | 73.4 min | $31.51 | 10/10 | ✅ | 36 | ✅ | +0 | 26 |
| T6 | complex | **plugin (after)** | `mix` | **24.4 min** | **$13.31** | 10/10 | ✅ | 29 | ✅ | +0 | 10 |
| T4 | vague | superpowers | – | 52.0 min | $21.22 | 8/8 | ✅ | 44 | **❌** | −4 | 17 |
| T4 | vague | plugin | `standard` | 90 min (killed at the cap) | ≈$40 (not recorded) | 8/8 | ✅ | 25 | ✅ | −4 | 36 |
| T8 | conflict (truth = brief) | superpowers | – | 7.8 min | $3.67 | 4/4 | ✅ | 10 | ✅ | −3 | 0 |
| T8 | conflict (truth = brief) | plugin | `mix` | 12.1 min | $7.07 | 4/4 | ✅ | 10 | ✅ | −4 | 2 |
| T9 | conflict (truth = code) | superpowers | – | 6.9 min | $4.01 | **1/4** | ❌ | 9 | ✅ | −3 | 0 |
| T9 | conflict (truth = code) | **plugin** | `mix` | 18.1 min | $8.53 | **4/4** | ✅ | 13 | ✅ | −4 | 5 |

| T7 | vague | superpowers | – | 5.1 min | $3.01 | 6/6 | ✅ | 24 | ✅ | +0 | 0 |
| T7 | vague | plugin | `mix` | 15.8 min | $9.22 | 6/6 | ✅ | 18 | ✅ | +0 | 4 |

Complete: 14 cells, 7 tasks × 2 arms. Three cells were voided by an account session limit at 15:00Z and
re-run afterwards; `results/void-session-limit/` keeps the killed sessions as evidence.

### The comparison, as it stands after the routing fix

| | bare superpowers | plugin 0.2.8 |
|---|---|---|
| acceptance | **38/41** | **41/41** |
| cost, six comparable tasks (T4 excluded: the plugin session was killed at the cap and never reported a cost) | **$19.63** | **$43.60** |
| wall, the same six | 27.1 min | 77.6 min |
| the three missed checks | all in T9 | – |

**2.2× the money and 2.9× the wall clock, for three acceptance checks — all three of them in the one task
where the cheaper flow silently broke a downstream consumer.** That is the whole trade, in one line.

## 2. What the routing fix bought

Same task, same model, same fixture, only the gate changed:

| | before | after | |
|---|---|---|---|
| T5 | `light`, $7.38, 16.1 min | `quick`, **$2.24, 2.7 min** | −70 % cost, −83 % wall |
| T1 | `light`, $9.32, 21.7 min, no endpoint test | `quick`, **$3.23, 4.5 min**, endpoint test | −65 % cost, −79 % wall, better tests |
| T6 | `standard`, $31.51, 73.4 min, 26 agents | `mix`, **$13.31, 24.4 min, 10 agents** | −58 % cost, −67 % wall |

On the simple and medium tasks the plugin now costs what bare superpowers costs (T5: $2.24 vs $2.23;
T1: $3.23 vs $2.41) and delivers the same acceptance. The gap survives only where the plugin does more:
the complex task at 3.1× (was 7.3×) and the vague brief, where both arms are expensive.

Note what the mis-route cost was made of, and what it was *not*: on T1 the expensive `light` run produced
**worse** tests than the cheap `quick` one — three `tests-writer` passes over the service layer and no
endpoint test at all, while the superpowers flow wrote one. More agents did not mean more coverage.

## 3. Where the plugin earns its price

Three findings, in order of strength.

**a. The conflict class — the only place where a flow *broke* something.** T9 gives the same brief as T8,
but the repository's records (ADR-0003, the CI smoke pin `"4 orders"`, the finance-export consumer note,
the changelog, the XML doc) back the **code**, and the brief is wrong.

| | bare superpowers | plugin |
|---|---|---|
| acceptance | **1/4** | **4/4** |
| ADR-0003 | marked *Superseded*, replaced by a self-written ADR-0004 | untouched |
| CI guard `smoke-report` | **flipped from `"4 orders"` to `"3 orders"`** | left at `"4 orders"` |
| `docs/reporting.md` | rewritten to the brief's rule | extended, still states the recorded rule |
| consumer note | rewritten | untouched |
| the real defect behind the complaint | found | found |
| cost / wall | $4.01 / 6.9 min | $8.53 / 18.1 min |

Both arms *noticed* the contradiction — this is not an attention failure. The difference is authority:
bare superpowers ruled for the ticket by itself, and its own notes flag "finance-export ledger
reconciliation as needing coordination" while it proceeds anyway and disables, in the same commit, the one
check that would have caught the break. The plugin dispatched `evidence-reconciler` **before changing
anything** (at minute 1.4 of 18), got `code` at high confidence — "ADR-0003 (finance sign-off required),
the CI smoke literal, and the finance-export consumer all fix N as every order" — implemented the recorded
behaviour, and left every record where it was. No acceptance test catches this difference on its own; only
the rule that a contradiction belongs to its owner does.

On T8, where the records back the brief, **both arms scored 4/4**. That is the honest shape of this class:
it discriminates in one direction only — when the brief is the thing that is wrong. When the ticket is
right, doing what the ticket says needs no judgement.

**b. Endpoint tests on a loose brief.** On T4 the baseline wrote 44 tests and **never started the host**;
the plugin wrote 25 and drove the API over HTTP. This is the 0.2.7 finding reproduced on a different model.
On the specified tasks the difference has gone: the superpowers flow now writes the endpoint test too.

**c. Convention enforcement is free.** Δ violations is 0 or −4 in every arm and every route, because the
write gate is a hook, not an agent — it costs nothing on the `quick` route where no plugin agent runs at all.

## 4. Where it does not

- **The code itself.** Every acceptance check that the plugin passed, the baseline passed too — except the
  conflict case, which is not about code quality. On T6 both closed the transition race (a global gate vs a
  per-order gate); on T4 both produced `TimeProvider`, `IOptionsSnapshot`, promotions in configuration, two
  promotion kinds and a cleaned `ReportService`.
- **Speed, ever.** The plugin is slower in every cell. On the routes that survived the fix it is slower by
  a minute; on `standard` it is slower by an hour.
- **The `standard` route on a single-service change.** T4 hit the 90-minute cap with 36 agents; T6 cost
  $31.51 before the mix route existed. `standard` should be reserved for what the sizing rubric says it is
  for — a store, a migration, an external contract, two or more projects.

## 5. The bottleneck, and what actually moved it

Measured on T6 (§3c of [0.2.8-tiered-flow.md](0.2.8-tiered-flow.md)): 71.6 of 73.4 wall minutes were
model inference across 26 serial agent dispatches; Roslyn bound on the first call and `dotnet` ran nine
times. It was never I/O. The lever that moved it was **fewer agents** — 26 → 10 on the same task — not the
context pack, not the hook, not the journal. Those were built and do work (the journal collected the
reviewers' lines), but the routes the gate now picks (`quick`, `mix`) run no Analyze phase, so the pack is
not even produced. That is the honest result: *the sharing machinery matters only for the plan-driven
routes, which are now the exception.*

## 5b. The vague class is two different things

T4 and T7 are both "loose briefs", and they cost an order of magnitude apart:

| | T4 | T7 |
|---|---|---|
| what is left open | the *mechanisms*: extensible promotion kinds, a controllable clock, configuration-driven rules | the *rule*: what "needs attention" means is the reader's judgement |
| baseline | $21.22 / 52 min | $3.01 / 5.1 min |
| plugin | 90 min, killed at the cap | $9.22 / 15.8 min |

So it is not vagueness that is expensive — it is **how many mechanisms have to be invented**. A brief that
leaves a business rule open is cheap; a brief that leaves the architecture open is not. The sizing rubric
already encodes this in question 5, and the T4 route (`standard`) was the correct one for it; what it
could not do is finish inside a 90-minute cap.

## 6. Verdict

**Use the plugin as a gate, not as a factory.** After 0.2.8 the numbers say:

- `quick` (superpowers in-session, no plugin agent) for one or two files — parity with bare superpowers on
  cost and outcome, with the rules gate for free;
- `mix` (superpowers writes, the workflow reviews) for anything inside one service that another service
  reads — 3× the baseline's cost, and it is what caught the transition race and the guard bypass on T6 and
  what handled the conflict correctly on T8;
- `standard` / `deep` only where a mistake reaches another team;
- **always** the reconciler when the brief and the repository disagree, whatever the route — that is the
  one measured case where the cheaper flow did real damage.

### In one paragraph

Before 0.2.8 the plugin cost 3.7–7.3× bare superpowers and bought marginally better tests. After the
routing fix it costs **the same on small work, 2–3× on everything else, and 41/41 against 38/41** — and the
three checks it does not miss are the ones that matter most: the case where the ticket is wrong and the
repository is right. On the code itself the two flows are indistinguishable; every acceptance check the
plugin passed, bare superpowers passed too, except in the conflict case. Buy the plugin for the gate — the
review that finds a race and a guard bypass, the reconciler that refuses to overrule an ADR, the write hook
that costs nothing — and let superpowers write the code.

### What still needs measuring

- **Repetition.** One run per cell is a sample, not a distribution; routing is a model's judgement, and its
  *stability* is untested.
- **`deep`.** Untouched: the fixture is one solution with no store and no external contract, so nothing in
  it can honestly demand the design pipeline.
- **The context-sharing machinery.** Built and enforced (pack, gate, journal, dependency inheritance) but
  barely exercised, because the routes the gate now picks run no Analyze phase. It needs a task that
  legitimately takes `light`/`standard` — or the honest conclusion that the machinery is for a route the
  gate has learned to avoid.
- **The paraphrase conflict**, to decide whether the FTS5 evidence index is enough or embeddings are
  warranted ([vector-store-evaluation.md](vector-store-evaluation.md) §4).
