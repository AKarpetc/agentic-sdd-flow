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

## What each tier costs

Measured on the 0.2.7 benchmark fixture (four tasks, one session each) and projected for the tiers
introduced in 0.2.8. Use it to sanity-check a routing decision, not as a promise.

| Tier | Agents dispatched | Typical wall | Typical cost |
|---|---|---|---|
| `quick` | 2–3 (implementer, tests-writer, one scoped review) | 5–10 min | ≈ $3–6 |
| `light` | 2 per task + 1–2 whole-branch | 12–20 min | ≈ $8–14 |
| `standard` | 5–7 per task + final | 30–45 min | ≈ $18–25 |
| `deep` | + 9 (compact) or + 17 (full) before a line of code | + 20–60 min | + $15–40 |

A `standard` run on a `quick`-sized change is the expensive mistake the gate exists to prevent: the
0.2.7 measurement paid $31.95 and 34 minutes for a change the baseline delivered for $8.33 in 11.
