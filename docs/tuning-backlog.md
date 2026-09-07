# Tuning backlog — what to change next, and how to know it worked

Written after the [2026-09-07 measurement](benchmark-2026-09-07-results.md) of 0.2.8. Every item names the
evidence that motivates it, the change, and the number that decides whether it worked. Ordered by expected
value ÷ effort. Nothing here is speculative: each one has a measurement behind it or a measurement in front
of it.

## Ready to run — the harness supports these today

```
# repetition: routing is a model's judgement, and one run per cell is a sample, not a distribution
python3 evals/benchmark/run.py --task T1 --task T6 --repeat 3 --out results/bench-<date>-repeat --workers 1 --model claude-opus-5

# exercise a route the gate now avoids (the context-pack machinery lives only in the plan-driven ones)
python3 evals/benchmark/run.py --task T6 --arm plugin --force-tier standard --out results/bench-<date>-standard --workers 1 --model claude-opus-5

# the paraphrase conflict: does BM25 recall reach the decisive ADR when it shares no vocabulary with the brief
python3 evals/benchmark/run.py --task T10 --out results/bench-<date>-paraphrase --workers 1 --model claude-opus-5

# deep, for the first time: five services, a shared contract, a migration over existing rows
python3 evals/benchmark/run.py --task T11 --out results/bench-<date>-deep --workers 1 --model claude-opus-5

# and the cheap version of the same question first — does the gate even say `deep`? (~$1, minutes)
python3 evals/routing/run.py --case deep-sizing-platform --model claude-opus-5
```

## 1. Repetition, before anything else (P0)

**Evidence.** Every conclusion in the results document rests on one session per cell. The gate picked
`quick` for T1 and `mix` for T6, T7, T8, T9 — consistently, but five samples of a judgement is not a
distribution, and the two mis-routes we did see (T5 → `light`, T1 → `light`) were both fixed by editing a
single sentence of the rubric.

**Change.** None yet — measure first: `--repeat 3` on T1 (quick), T6 (mix) and T8 (conflict).

**Decides it.** The route column: three identical routes per task means the gate is stable; a split means
the rubric is ambiguous at that size and needs a sharper question, not a better model.

## 2. The plan-driven routes still cost what they cost (P0)

**Evidence.** T4 took `standard` correctly (the brief leaves the architecture open) and hit the 90-minute
cap with 36 agents; `plan-reviewer` ran twice for 12.3 minutes before the workflow started. T6 under
`standard` was 26 agents and $31.51 for what `mix` did with 10 agents and $13.31.

**Change.**
- The skill's step 3s already says one plan review; make the **second pass scoped** (verdict the prior
  findings, review only what changed) instead of a full re-read, the way the code re-review works.
- Consider dropping the per-task review at round 0 entirely when the task's tests are green and its diff is
  under ~50 lines — the whole-branch final review sees it anyway.

**Decides it.** `--force-tier standard` on T6, against the recorded $31.51 / 73.4 min / 26 agents. Target:
under $20 and under 40 minutes with the same 10/10 and the same defects found.

## 3. The context-sharing machinery is unexercised (P1)

**Evidence.** The pack, the PreToolUse gate, the journal and `dependsOn` inheritance are built, tested and
enforced — and on every measured run the gate chose a route with no Analyze phase, so no pack was ever
produced. The journal did work: the two reviewers on T6 wrote their lines.

**Change.** None until measured. Run `--force-tier standard` on T6 (item 2) and read
`.superpowers/sdd/packgate.log`:

| what the log shows | what it means | what to do |
|---|---|---|
| no log at all | no agent tried to re-derive | the instruction alone is enough; the hook is a safety net |
| many `redirected` | agents keep trying; the hook is doing the work | keep the hook, and consider dropping the instruction to save prompt |
| many `second-ask-allowed` | the pack is not answering well | fix the pack's contents, not the gate |
| many `unanswered` | the Analyze agent is writing `unknown` too often | give it more budget or a narrower brief |

**Decides it.** Agent tool counts against the recorded 26-agent run (≈11 per agent on the `mix` run,
unknown for `standard` post-change), and the pack-gate log above.

## 4. Does FTS5 recall suffice, or are embeddings warranted (P1)

**Evidence.** T10 exists for exactly this: the records state the rule in vocabulary the brief never uses
(statement lines, reversals, payer, parity — against orders, cancelled, customer). Queried in the brief's
words, the decisive ADR-0007 comes back **sixth** at 1.88, below `smoke-report.sh` and the changelog. It is
found, but it would fall out of a top-5 cutoff.

**Change.** Run T10 both arms. If the plugin rules `code` (4/4, ADR untouched, CI guard intact), the index
is sufficient and the vector question is closed for now. If it rules `brief`, try in order:
1. raise the reconciler's `-n` from 10 to 20 (free);
2. make it query a third time in the *records'* vocabulary, taken from the top hit's own words (free);
3. only then the embedding backend from [vector-store-evaluation.md](vector-store-evaluation.md) §4.

**Decides it.** T10's acceptance and `adrTouched` / `ciSmokeExpects` quality signals.

## 5. `deep` has never run — the fixture now exists (P1, was P2)

**Evidence.** No cell exercised the design pipeline: the single-solution fixture has no data store and no
external contract, so nothing in it can honestly demand one. `scope: 'compact'` is therefore untested too.

**Change (built, unmeasured).** `evals/benchmark/fixture-platform/` — five services (`Checkout.Api`
gateway, `Orders.Api`, `Inventory.Api`, `Pricing.Api`, `Ledger.Api`), a shared `Platform.Contracts`
assembly, and a SQLite ledger whose schema comes from numbered migrations applied at start-up over rows
that already exist. **T11 / ORD-60** (multi-currency checkout) answers `yes` to all three of the gate's
`deep` triggers at once — an external contract, a migration on existing rows, more than two projects —
and trips over a cross-service defect: releasing a reservation never returns its quantity to stock, and
the fixture's own test passes because it asserts the reservation flag rather than the shelf. Fifteen
hidden HTTP checks; the caps for that cell (3 h, 250 turns) come from the manifest, because the design
pipeline plus five services does not fit in 90 minutes.

**Decides it.** In order of price:
1. `evals/routing/run.py --case deep-sizing-platform` — does the gate say `deep` at all (~$1);
2. `run.py --task T11` both arms — acceptance, the `route` column against `expectedTier: deep`, and the
   `Reach:` line `report.py` prints: services touched, applied migrations edited (must be none), whether
   the stock leak was fixed in `Inventory.Api` or compensated for in the gateway, hard-coded peer URLs,
   whether ADR-0001 was superseded or overwritten;
3. only then `--repeat`, and only if the first run is not decisive on its own.

Expect the plugin arm to cost several times the T6 `standard` run and the baseline to be the interesting
half: a five-service change with no design record is exactly where the two flows should diverge.

## 6. Smaller, cheap, evidence-backed (P2)

| Item | Evidence | Change |
|---|---|---|
| `tests-writer` skipped the endpoint on T1's `light` run | 3 passes, service layer only, no `WebApplicationFactory` — the `quick` route wrote one | make the final review file a missing entry-point test as `important`, so the gate catches it rather than the brief asking nicely |
| T4's plugin session died at the cap with the work done | 8/8 acceptance, but killed before it could report | the benchmark's 90-minute cap is the harness's, not the plugin's; raise it to 120 for `standard`/`deep` cells or the number is about the cap |
| T8's plugin run "extended" three records | `docs/reporting.md`, `CHANGELOG.md`, `.gitlab-ci.yml` touched on a `truth: brief` task | read the diffs and decide whether extending a record is acceptable on a `brief` verdict; today `quality_conflict` only flags rewriting one *the wrong way* |
| Cost is unrecorded when a session is killed | T4 plugin shows `$0.00` | sum `modelUsage` from the last `result` event in the stream, or fall back to the pulse's agent count × the run's mean |

## 7. What not to do

- **Do not "make the agents faster".** 97.6 % of a `standard` run's wall clock is model inference at a rate
  indistinguishable from the single-session baseline's. The volume is the cost; the rate is not the problem.
- **Do not add an LLM router.** The workflow script already routes deterministically and for free.
- **Do not import chat-shaped context sharing.** Re-injecting a transcript into fresh agents is quadratic
  in exactly the tokens that are the bottleneck.
- **Do not tune on one run.** Item 1 exists because two of today's conclusions would have been different
  with a different sample.
