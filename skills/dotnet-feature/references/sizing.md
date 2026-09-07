# Sizing a change — the five questions

The gate must be cheaper than the work it routes. Answer these five from the brief and at most one
repository lookup; when an answer is genuinely unknown, answer it the **cheap** way and let the
escalation rules in the skill move the run up.

| # | Question | Answer that raises the tier |
|---|---|---|
| 1 | **Blast radius** — how many files does the change plausibly touch? | 1–2 → `quick` · ≤ 5 → `light` · more → `standard` |
| 2 | **Surface** — does it add or change an endpoint, a gRPC service, a published event, a NuGet-published contract, or a public API of a shared package? | an external contract → `deep`; a new internal endpoint → at least `light` |
| 3 | **Data** — does it add or change a table, a migration on existing rows, a stored procedure, a cache key others read? | any → at least `standard`; a migration on existing rows or a hot table → `deep` |
| 4 | **Reach** — does it span two or more projects/solutions, or add infrastructure (queue, cache, service, job host)? | any → `deep` |
| 5 | **Specification** — is the *what* already decided (a stated rule, a named method, a fixed shape), or does the brief ask you to choose a structure? | already decided → the tier from 1–4 · "design it so that…", "make it extensible", "the way you would for a service that lives for years" → at least `standard`, and `deep` only when 2, 3 or 4 also say so |

## Deciding

Take the **highest** tier any question produces, then apply the two guards from the skill:

- **One tier up, never two.** A brief that only *smells* big is not evidence. `deep` needs a concrete
  yes on question 2, 3 or 4 — "extensibility" alone is a `standard`, not a design pipeline.
- **The gate is reversible upwards, not downwards.** Cheap first, escalate on evidence.

## Worked examples

| Brief | Answers | Tier |
|---|---|---|
| "`GET /orders/{id}` returns 500 when the order is missing — should be 404" | 1 file, no new surface, no data, one project, specified | `quick` |
| "Add `GET /api/customers/{id}/orders/total`, sum through the repository, logic in the service layer" | ~4 files, new internal endpoint, no data, one project, specified | `light` |
| "Cancel an order: 204/409/404, persist the status, publish to an outbox others can read" | ~8 files, new endpoint + an event surface others consume, state change, one project | `standard` |
| "Add promotions to pricing, configurable by marketing, new kinds addable without touching the calculation" | many files, no external contract, no store, one project, **structure is the ask** | `standard` |
| "Move product search off the Server call onto the ProductSearch gRPC contract and keep the iOS wire format" | two solutions, a contract change, wire compatibility | `deep` |
| "Add an `Archived` flag to orders with a migration and a backfill" | one project but a migration on existing rows | `deep` |

## What each route costs — measured, not projected

Benchmark `evals/benchmark`, 2026-09-07, Opus 5, one session per cell, the same fixture solution and the
same hidden HTTP acceptance for both arms. **Show these numbers in the proposal; mark anything else
`unmeasured`.**

| Task | Class | superpowers (route A) | plugin route, as run | Quality difference |
|---|---|---|---|---|
| T5 | simple, 1 file | **$2.23 / 3.8 min**, 5/5 | `light` $7.38 / 16.1 min, 5/5 | none — same 4 files, same 7 tests, both with an endpoint test |
| T1 | medium, ~4 files | **$2.41 / 3.9 min**, 4/4 | `light` $9.32 / 21.7 min, 4/4 | baseline wrote the endpoint test, the plugin's `tests-writer` did **not** |
| T6 | complex, 16 files, state machine + idempotency + audit | **$4.30 / 7.4 min**, 10/10 | `standard` $31.51 / 73.4 min, 10/10 | parity: both closed the transition race (global gate vs per-order gate), 34 vs 36 tests, both +0 violations |

Ranges to quote for a route that has no measurement at this size:

| Route | Agents dispatched | Typical wall | Typical cost |
|---|---|---|---|
| A `superpowers` | 0 plugin agents (rules held by the hooks) | 4–8 min | ≈ $2–4 |
| B `mix` | 1 reviewer + 1 verifier per finding + at most 1 fix pass | + 8–15 min | + $4–7 |
| C `light` | 2 per plan task + 1–2 whole-branch | 20–25 min | ≈ $8–14 |
| C `standard` | 5–7 per plan task + plan review + final | 60–75 min | ≈ $25–32 |
| C `deep` | + 9 (compact) or + 17 (full) before a line of code | + 20–60 min | + $15–40 |

**Why C is so much slower is not I/O.** On T6 the plugin session spent 71.6 of its 73.4 wall minutes inside
model inference (`duration_api_ms`), across 26 serial agent dispatches; Roslyn bound correctly and `dotnet`
ran nine times. The baseline spent 6.9 of 7.4 minutes the same way, in **one** session with no subagent at
all. So the cost of route C is the cost of re-establishing context 26 times — each agent reads the rules,
the skill and the code again before it can act — not of waiting on tools. Fewer, larger agents is the only
lever that moves it; parallelism would move wall clock but not cost, and is unsafe in one working
directory (two implementers committing to the same branch).

A `standard` run on a `quick`-sized change is the expensive mistake the gate exists to prevent: the
0.2.7 measurement paid $31.95 and 34 minutes for a change the baseline delivered for $8.33 in 11. The
milder version is real too: on T5 the gate chose `light` because the test project was empty, and paid
$7.38 and 16 minutes for the tree the superpowers flow produced for $2.23 in 4 — same files, same tests.
