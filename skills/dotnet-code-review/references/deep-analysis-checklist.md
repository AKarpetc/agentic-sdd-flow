# Deep Analysis Checklist

The **second pass** of a review, walked at Step 6 after the convention sweep (Step 5.5) is finished.
[rule-compliance-checklist.md](rule-compliance-checklist.md) asks *does this file obey the rules*; this
file asks *does this change behave correctly once it is deployed, against real data, next to the code it
did not touch*. Those are different questions and they are answered by different reading: §A–C are
read per file, D1–D7 are read across files, across releases, and against the store.

🔴 **Do not re-raise a surface finding here.** Naming, async idiom, null safety, contract style,
`.editorconfig`, mechanical simplification and pattern-matchable security are already reported by Step
5.5. This pass is spent entirely on what only emerges from multi-file and multi-release reasoning. If a
careful deep pass finds nothing beyond the convention pass, **report nothing** — a manufactured marginal
finding is worse than an empty section.

## Severity floors

| Finding | Floor |
|---|---|
| Migration that will fail on replay, or drops/renames shipped with code still reading the old shape | Critical |
| Cache key that crosses a tenant, store, user or permission boundary; secrets in a shared cache | Critical |
| Stale read after a successful write with no stated consistency contract | Critical |
| Wire-breaking contract change (removed/renamed field, retagged `[ProtoMember]`, changed enum value) | Critical |
| Unbounded fan-out or unbounded query on a path that can see production volume | Critical |
| Authorization gap, IDOR, auth bypass, injection reached through an indirect path | Critical |
| Asymmetric or unguarded `Down`; lock-heavy DDL; unbatched backfill | Important |
| Missing TTL or size bound; incomplete aggregate invalidation; fallback with no timeout | Important |
| A signature or behaviour change whose callers outside the diff were not checked | Important |

## D1. Migrations & persistent-state changes

Applies to **any** change to persistent state — EF Core, raw SQL, FluentMigrator, OpenSearch/Elasticsearch
mappings and aliases, Mongo, cache schemas.

**The premise:** every runner keeps a ledger of what it applied (`__EFMigrationsHistory`, a version
document, a migrations collection). **The store can hold the object while the ledger does not know about
it** — someone applied it by hand because the migration would have timed out, a restore or environment
refresh carried it over, or a previous run died halfway. Review for that state, always.

The five rules — **idempotent, reversible, non-blocking, bounded, compatible**:

1. **Idempotency.** Every create and drop is guarded; fluent APIs mostly have no `IfNotExists`, so raw SQL
   is required. Postgres `CREATE INDEX CONCURRENTLY IF NOT EXISTS` / `ADD COLUMN IF NOT EXISTS` /
   `DROP … IF EXISTS`; SQL Server `IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = …)`; OpenSearch —
   read the mapping or alias before `PUT`, creating an existing index is an error.
2. **One non-transactional statement per migration.** Anything outside the transaction
   (`suppressTransaction: true`, `Npgsql:CreatedConcurrently`, every index/mapping API) commits on its own,
   so N such statements give N partial-failure states. Split them, or guard every one.
3. **Conflict-safe inserts** — `ON CONFLICT DO NOTHING`, `WHERE NOT EXISTS`, upsert by document id.
4. **No relative writes.** `SET counter = counter + 1`, appending to a column, an insert with no natural
   key: a replay corrupts data silently instead of failing loudly.
5. **`Down` symmetry.** Every `Up` operation has its inverse with matching names; `Down` may run after a
   partially applied `Up`, so guard it identically. A `Down` re-adding a `NOT NULL` column with no default
   fails on a non-empty table. **Irreversible** changes (drop column/table, narrow a type, delete rows)
   are not undone by a `Down` that recreates the shape — the change needs a stated forward-only decision
   or expand → migrate → contract.
6. **Non-blocking.** Lock-heavy: changing a column type, `SET NOT NULL`, adding a column with a volatile
   default, an offline index build, validating a new FK or check constraint (use `NOT VALID` +
   `VALIDATE CONSTRAINT`). Set `lock_timeout` / `statement_timeout` on long DDL so it fails fast instead
   of queueing behind an open transaction and blocking every query on the table. An OpenSearch mapping
   change forcing a reindex is a full rebuild — behind an alias swap, never in place on a live index.
7. **Bounded.** Batch any `UPDATE`/`DELETE`/reindex over a large set; one statement is one long
   transaction, table bloat and replica lag. Prefer a restartable, observable job over a backfill embedded
   in the migration.
8. **Compatible.** Never drop or rename in the same release as the code change — add → backfill → switch →
   drop later. `RenameColumn`/`RenameTable` are **never** backward compatible. A new `NOT NULL` column
   without a default breaks old code that inserts without it.
9. **Startup migrations** run on every replica and every rollout: they must tolerate concurrent and
   repeated execution and finish inside the readiness-probe budget. One killed by the probe is exactly
   the partial-application case in rule 1.
10. **A cross-cutting migration copied into every service is one flaw × N outages, arriving at once.**
    Judge the pattern, not just this repository.

**Analyzer overlap.** Where a migration analyzer already enforces online/concurrent index operations, do
not re-raise its findings — but note the trap: its fix makes the statement **non-transactional**, so
satisfying the analyzer *increases* the need for rule 1. A suppression attribute is a claim; check it holds.

**Read the siblings.** Sibling migrations and the model snapshot are in scope — that is how a duplicate
object, a timestamp-ordering conflict and snapshot drift are caught; none is visible in the diff alone. Do
not flag scaffolding boilerplate (`#nullable disable`, `<inheritdoc />`, `.Designer.cs`, generated names).

**What it looks like when it goes wrong:** services crash-looping at once because the objects had been
created by hand on the large databases (the migration would have timed out) and the ledger rows were never
written — `42P07: relation "IX_…" already exists`, `Column name '…' is specified more than once`. Recovery
is a choice between dropping the objects and re-running (times out) and hand-inserting ledger rows
(asserts something nobody verified). One existence check removes the situation.

## D2. Caching

Use when code reads, writes, invalidates or configures a cache — in-process, distributed (Redis), HTTP/CDN,
ORM/query, application-level. A cache is a performance optimization, not the source of truth. Review the
full data lifecycle and its failure modes, not the cache API call.

Report only when the implementation can return **stale, incorrect or unauthorized** data, expose sensitive
data, or cause or worsen an outage. A TTL that differs from local habit is not a finding when the
consistency contract is explicit and safe.

- **Consistency contract.** Are stale reads allowed, for how long, and which change invalidates the value?
  An unstated contract on a write path is the finding.
- **Keys are access boundaries.** The key must include every input that changes the result — tenant,
  store, user, permissions, locale, currency, requested fields, filters, sorting, pagination, feature
  state, schema version. A missing one is a cross-tenant or cross-user read.
- **Invalidate after commit**, never before — invalidating before commit can repopulate stale data. Include
  **aggregate and derived** keys: updating an entity key does not refresh a list, count or permission result.
- **Negative entries** are a separate decision: a cached `null` needs a short TTL so it does not hide
  newly created data longer than the product allows.
- **Do not cache mutable instances** callers can change — serialize, copy, or return an immutable value.
- **Bounded freshness and storage** — TTL, entry/size limit, eviction policy. Cache indefinitely only when
  the value is immutable and versioned. Add bounded jitter when many entries are created together.
- **Cache failure must stay optional** — a miss, timeout, unavailable cache or deserialization error must
  not become an outage or a data leak. Bound the fallback: during a cache outage, unlimited retries
  exhaust the authoritative store.
- **Stampede control** — coalesce concurrent misses, bound recomputation with timeouts and concurrency
  limits, give distributed refresh locks a finite lease and handle lock loss. Use stale-while-revalidate
  only where stale is safe, with a maximum stale period.
- **Cancellation in cache factories.** A factory delegate that populates a missing entry
  (`GetOrAdd`/`GetOrCreateAsync`) must **not** take the request `CancellationToken` — a client disconnect
  then aborts population mid-flight and poisons the entry for every other caller waiting on it. Pass the
  application-lifetime shutdown token instead.
- **Serialization versioning.** A deployment changing a DTO or format must read old entries safely, use a
  new key namespace, or invalidate the old one before reading it. Prefix keys by service and environment.
- **Authorization is not replaced by a shared cache** — recheck access before returning unless every caller
  the key represents may receive the same value. Do not log cached values or sensitive key parts.
- **Observability** — hit/miss rate, load latency, errors, timeouts, evictions, key cardinality, refresh
  activity; monitor invalidation consumers, retries and dead letters. An unnoticed invalidation backlog
  produces stale data indefinitely.

## D3. Contract & backward compatibility

A change is breaking if an existing consumer would fail to deserialize, compile, or behave correctly
without changing its own code. The list is common patterns, not exhaustive:

- **Renamed or removed fields** in request/response DTOs, protobuf messages or REST models.
- **Changed field types** (`int` → `string`, `DateTime` → `DateTimeOffset`, `T` → `T?`).
- **Removed or renamed endpoints** — HTTP routes, gRPC methods; **changed HTTP method or route template**.
- **Changed `[ProtoMember]` tag numbers** — protobuf-net serializes by tag, so changing or reusing one
  breaks every existing consumer even when the field name is untouched.
- **Changed namespace of a protobuf/gRPC contract** — it is a wire-level identifier.
- **Removed required fields, or new required fields without defaults.**
- **Changed enum member names or values** — wire-breaking for protobuf, name-breaking for JSON.

State the **old and the new** state, and whether a migration path exists (keeping the old field as
deprecated alongside the new one). For a contract published as a package, the blast radius is the
consumers, not this solution — say which consumers were checked and which could not be.

## D4. Performance

Reason about runtime behaviour, not code shape:

- **N+1 patterns** — ORM calls inside loops, lazy-loading triggers, missing `.Include()`, per-item queries
  where a batch exists.
- **Unbounded queries** — missing pagination, `ToList()` on a large table, missing `Take()`/`Skip()`, a
  read whose size is driven by data volume rather than by a parameter.
- **`IEnumerable` re-enumeration** — the same deferred query iterated more than once, especially over a
  database source.
- **Hot-path allocations** — boxing, LINQ in tight loops, closure captures, string concatenation in loops.
- **Missing projections** — loading full entities where a few fields are needed.
- **Algorithmic complexity** — O(n²) or worse where O(n) or O(n log n) is available.
- **Unbounded fan-out.** `Task.WhenAll` over a collection whose size is caller- or data-controlled starts
  every task at once — thread-pool starvation, connection-pool exhaustion, an overwhelmed downstream. Use
  `Parallel.ForEachAsync` with a bounded `MaxDegreeOfParallelism`. `Task.WhenAll` is fine for a small fixed
  set of distinct calls; there, prefer starting each task and awaiting them individually so each exception
  surfaces at its own await. Note that `await Task.WhenAll(…)` rethrows only the **first** exception while
  every task still runs — code that must observe every failure has to read `.Exception.InnerExceptions`.

## D5. Deep security

Go beyond pattern matching — reason about data flow and authorization. Apply these to **publicly reachable
entry points**: HTTP/REST controllers, GraphQL, WebSocket handlers, and anything reachable from the
internet. Where a transport is documented as private-network-only, say so rather than assuming either way.

- **Authorization gaps** — a missing `[Authorize]`, broken access-control logic, a privilege-escalation path.
- **IDOR** — an endpoint takes an id but never verifies the caller owns the resource.
- **Injection via indirect paths** — trace user input through every layer to the query, not just the
  obvious call site.
- **Authentication bypass** — branches that skip the check on an error path or a fallback handler.
- **Sensitive data exposure** — PII or secrets in logs, error responses or cache keys; response DTOs broad
  enough to carry internal fields.
- **TOCTOU** — authorization checked, then the resource changes before it is used.
- **Deserialization of untrusted input** — arbitrary or polymorphic, without validation.

## D6. Domain borders & cross-service consistency

- Types leaking across module or service boundaries — internal DTOs in a public API, domain entities in a
  controller response.
- Direct dependencies between bounded contexts that should talk via events or a shared contract.
- Business logic in infrastructure (controllers, repositories) that belongs in domain/application services;
  anemic domain models.
- Patterns that should be consistent and are not — error-handling middleware, logging, the auth pipeline,
  retry/circuit-breaker policy.
- Ad-hoc service-to-service coupling where a shared contract or event already exists.
- Inconsistent transaction boundaries for the same logical operation.

## D7. Multi-file reasoning

Actively look **beyond the diff** for:

- A method-signature change that breaks callers not shown in the diff.
- A new dependency creating a circular reference.
- A removed null-check whose callers rely on the non-null guarantee.
- A configuration or feature-flag change altering runtime behaviour elsewhere.
- A new public API duplicating one that already exists.
- Event handlers or background jobs depending on state the changed code sets — including a job that now
  runs on every replica, or a consumer whose ordering assumption the change breaks.

## Evidence discipline (applies to every D-finding)

1. **Every factual claim must be verifiable** from the diff, the repository, or `git` history. Do **not**
   assert library version histories, API renames across tool versions, or framework behaviour you are
   inferring. If a concern depends on such a fact, verify it with a tool first or drop it. A confident
   false statement costs more than a missed minor issue.
2. **Check the finding against the stated intent** — the ticket, the MR title and description, the commit
   message. Many "warnings" flag exactly the change the task asked for. Raise it only when the change has a
   consequence the author plausibly did not intend.
3. **No confirmations.** "This is correct", "the refactor is equivalent", "no regression" are not findings.
   A D-finding requires the author to change something or decide something.
4. **Anchor to a line that the diff actually changed.** For an issue in an unchanged construct, anchor at
   the nearest changed line in the same file and name the unchanged target in the text. For a cross-file
   issue, anchor at the primary site — where the change introduces it — and list the secondary sites.
5. **Confidence bar.** If you are unsure it is a real defect, do not raise it. Precision over coverage.

## Sweep for the deep pass

Roslyn first — these answer D3, D6 and D7 directly:

```
→ find_references (every changed public symbol)      # D3/D7 callers outside the diff
→ get_public_api (every modified type)               # D3 what actually changed on the surface
→ get_project_graph / detect_circular_dependencies   # D6 direction and cycles
→ get_di_registrations                               # D6/D7 lifetime of state the change relies on
```

Then a grep cross-check — each hit is a *question*, not a finding:

```bash
rg -n 'Task\.WhenAll'                                     # D4 unbounded fan-out
rg -n 'GetOrCreateAsync|GetOrAdd' -A2 | rg -n 'cancellationToken|ct\b'   # D2 factory cancellation
rg -n '\.ToList\(\)|\.ToArray\(\)' -g '*.cs'              # D4 unbounded materialization
rg -n 'CreateIndex|DropColumn|DropTable|RenameColumn|RenameTable|AlterColumn'  # D1
rg -n 'suppressTransaction|CreatedConcurrently|Online'    # D1 non-transactional statements
rg -n 'migrationBuilder\.Sql'                             # D1 guard the raw SQL
rg -n 'ProtoMember\(\s*\d+'                               # D3 tag renumbering (compare against the base ref)
rg -n 'TagWith'                                           # D2/observability — a plain comment, not a tag
```

For D3, the tag and enum checks only mean something against the **base ref**:
`git diff <base>..HEAD -- '*Contracts*' '*.proto'` and read what moved.
