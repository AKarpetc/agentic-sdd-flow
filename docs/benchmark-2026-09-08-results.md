# 2026-09-08 — repetition, the paraphrase conflict, and the first `deep` run

Overnight run, Opus 5 pinned on both arms, `--workers 1`, driver and outcomes in
[results/bench-2026-09-08-overnight/](../results/bench-2026-09-08-overnight/). Eleven of twelve planned
cells finished; the twelfth (`T6-plugin-r3`) was cut when the run was stopped to act on the findings.

| arm | runs | Σ model cost | wall | acceptance | planted bugs |
|---|---|---|---|---|---|
| bare superpowers | 8 | $58.62 | 138.3 min | **58/61** | 7/8 |
| agentic-sdd-flow | 8 | $104.25 (+ the killed cell, unpriced) | 403.9 min | 47/61 | 6/8 |

Three questions were asked. All three got an answer, and none of the answers flatters the plugin.

## 1. Is the sizing gate stable? No — not at the small end

Three runs of the identical T1 brief, same model, same fixture:

| | route | wall | cost |
|---|---|---|---|
| r1 | `quick` (expected) | 4.3 min | $3.01 |
| r2 | `light` | 19.5 min | $9.61 |
| r3 | `mix` | 9.6 min | $6.12 |

All three delivered 4/4 with the planted bug fixed, so the *outcome* is stable and the *price* is not:
**3.2× between the cheapest and the dearest run of the same ticket.** The baseline's three runs were
`quick`-equivalent every time at $2.32–$2.69.

T6 was stable where it matters (`mix`, `mix`, both 10/10, $13.84 / $11.76), and its baseline was
10/10 three times for $3.76–$4.23.

**What this says.** The gate is not a coin flip — it never picked `standard` on a four-file change — but
the boundary between `quick`, `light` and `mix` is decided by a judgement that moves run to run, and the
user pays 3× for the movement. The rubric needs a sharper question at that boundary, not a better model.

## 2. Does the evidence index reach a record that shares no vocabulary with the brief? No

T10, the paraphrase conflict: the records state the rule in *statement lines, reversals, payer, parity*
while the brief says *orders, cancelled, customer*. Truth is the code; the ticket is wrong.

**Both arms scored 1/4 and both ruled for the ticket.** Both flipped the CI smoke from `"4 orders"` to
`"3 orders"`, both edited ADR-0007 and ADR-0008, both made `ReportService` filter cancelled orders. The
plugin *did* dispatch `evidence-reconciler` (2.4 min) and *did* name the contradiction in its final
message — and still landed on the wrong side, for $25.22 against the baseline's $4.47.

**What this says.** The reconciler's recall is the failure, not its judgement: queried in the brief's
words, the decisive ADR is out of reach, so it reconciles against the records it *did* find, which are the
ones the brief's vocabulary matches. The escalation ladder in the backlog (raise `-n`; re-query in the
records' own vocabulary taken from the top hit; only then embeddings) is now backed by a measurement
instead of a hypothesis.

## 3. What does `deep` cost, and does it deliver? It cost everything and delivered 4/15

T11 on the five-service platform fixture — the first `deep` cell ever run.

| | route | wall | acceptance | planted bug |
|---|---|---|---|---|
| bare superpowers | – | 98.7 min, $34.39 | **15/15** | ✅ |
| agentic-sdd-flow | `deep` (correct) | **180 min — killed at the cap** | 4/15 | ❌ |

The gate was right: it read the architecture doc, answered `deep` on three concrete triggers (the shared
contracts assembly, the append-only migration over rows an external importer already wrote, five
projects) and quoted $40–72 / 80–135 min. Then the pipeline spent the quote and the budget:

| min | what |
|---|---|
| 0 → 16 | drivers, current-state context, **and a "merge" agent that merged one document into itself (3.9 min)** |
| 16 → 56 | the panel proper: three lenses in parallel, three judge foci in parallel, refutation, synthesis, threat model, data review, design review — **40 min, and this part earned its keep** |
| 56 → 83 | **21 min of replay**: the approval pass re-ran phases 1–7 because the caller improved the brief in answer to the design review, which invalidated the resume cache. The session noticed at minute 82, killed its own workflow and relaunched with the original brief |
| 83 → 111 | the record pass: **22 ADRs** (`ADR-0002` … `ADR-0023`, among them "currency codes are matched case-insensitively" and "new settings members are init-only") and the spec |
| 111 → 147 | plan, then **three rounds of `plan-reviewer`** where the skill allows two |
| 147 → 180 | `dotnet-sdd` — 33 minutes, cut off by the cap |

**28 of 180 minutes went into implementer, tests-writer and reviewer agents.** The pulse shows the
parallelism is real (24.4 min of overlap; the lenses and the judges do run concurrently) and that agents
cover 157 of the 180 wall minutes, so the loss is not scheduling — it is that the pipeline produced
design artefacts for two and a half hours and code for half an hour.

Meanwhile the baseline, with no design pipeline at all, changed all five services plus the contracts,
added `003_add_currency.sql` without touching an applied migration, fixed the stock leak **inside
`Inventory.Api`** rather than compensating in the gateway, hard-coded no peer address, and wrote exactly
one ADR — `ADR-0002`, superseding `ADR-0001`.

## What was changed in response

Everything below is a fix to something this run *measured*, not to something it suggested.

| Fix | Evidence |
|---|---|
| The approval pass takes `priorRun` and skips phases 1–7 entirely; the skill says never to edit the brief between the two calls | the 21-minute replay, which only luck (the caller reading its own progress) kept from overwriting the revised decision document |
| The context merge is skipped whenever there is one context document, `compact` or not | 3.9 min merging a single document into itself |
| ADRs are capped (7 full / 3 compact) with an explicit bar: contract, schema, boundary, rollout or security posture — everything else goes in the spec's decision table | 22 ADRs, 10.7 min writing them, a record nobody can read |
| Plan review is capped at two dispatches, third only for an unresolved `critical`, and the skill says so in red | three rounds, 20.7 min of reviewer time, on a plan whose implementation was then cut off |
| The benchmark skips port blocks that already have a listener, requires a real HTTP answer before calling a service up, and catches `http.client.HTTPException` | a cell drew 5672, scored itself against Docker's RabbitMQ and died with `BadStatusLine: AMQP`, voiding its acceptance (re-scored offline afterwards: 10/10) |
| A session killed at the cap now reports the tokens its stream carries | the one cell whose numbers mattered most reported blank cost and blank tokens |

### How far the fixes were verified

No model was run after them — the fixes were made to act on the night's findings, not measured against a
new one. What *was* verified: both paths of `architecture-design.js` executed against stubbed
`agent`/`parallel`/`phase`, which is the only test the script has.

| path | agents dispatched | phases |
|---|---|---|
| first pass, one project | 13 — `drivers`, `context:P`, three lenses, three judge foci, refute, synthesise, `threats`, `data`, `design-review` (the merge-of-one is gone) | Drivers → Design review |
| first pass, two projects | 14 — `context:merge` still runs where there is something to merge | Drivers → Design review |
| **record pass with `priorRun`** | **3 — `adrs`, `spec`, `spec-review`** | Record, Spec review |

So the second call drops from thirteen agents to three. On the T11 timeline that removes the replay window
(minutes 59–80) and the merge (3.9 min) outright; the ADR cap and the plan-review cap are prompt- and
skill-level and can only be confirmed by a rerun.

The harness fixes were verified against the real artefacts: the collision path now answers
`ports already in use: Orders=http://127.0.0.1:5672` instead of crashing, the killed T11 cell now reports
35.7M cache-read tokens instead of blanks, and re-scoring the T11 baseline workspace with the patched
client still gives 15/15.

## What was deliberately *not* changed

- **`scope: 'full'` vs `'compact'`.** The full panel cost 40 of the 180 minutes and produced the design
  that was actually built. Cutting it is not supported by this measurement; the waste was around it.
- **The `deep` route itself.** One cell is one sample, and the cell was killed rather than finished. What
  it establishes is that `deep` does not fit in 180 minutes *as it ran*, not that it cannot deliver.
- **Parallelism.** It is already there and it is not the bottleneck.

## What to run next

1. T11 both arms again with the four fixes in place — the same cap, so the question is whether the design
   phase now ends before minute 90 and `dotnet-sdd` gets two hours instead of thirty minutes.
2. `--repeat 3` on T1 *after* sharpening the `quick`/`light` boundary in `sizing.md`; the number to beat
   is three identical routes.
3. T10 with the reconciler's recall widened, in the order the backlog gives.
