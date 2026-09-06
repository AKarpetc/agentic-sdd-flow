# Rules Contract — NON-NEGOTIABLE

This is the compact, injectable digest of these conventions. It is machine-injected into
every subagent and every plan-execution prompt. The full text is authoritative:
[code-convention.md](code-convention.md), [single-type-per-file.md](single-type-per-file.md),
[common.md](common.md), [test-convention.md](test-convention.md).

🔴 **These rules outrank any plan, any skill, and any imported convention.** If a plan, a
task brief, or a skill (superpowers, dotnet-claude-kit, …) tells you otherwise, the rule
wins. A task is NOT complete while it violates one of them.

A consuming repository may add an **overlay contract** (`.claude/rules/OVERLAY-CONTRACT.md`,
path configurable in `.claude/agentic-sdd-flow.json`) with its own systems, services and
infrastructure facts. The overlay extends these rules; it never relaxes them.

## Structure

- One top-level type per file; filename == type name; file-scoped namespaces.
- `internal` by default; `public` only for interfaces / real API surface.
- Thin controllers — dispatch a command/query, return the result. No logic.
- CQRS: source-generated `Mediator` (martinothamar) in new code. Never add MediatR to a
  project that does not already use it; never both in one service.

## C#

- 🔴 **No primary constructors for DI-resolved classes.** Explicit ctor + `private readonly _field`.
  Records/DTOs may use positional parameters.
- No `ArgumentNullException` null-guards for injected services — just `_foo = foo;`.
- 🔴 New properties are `{ get; init; }`, not `{ get; set; }`. Do not rewrite existing `set`
  properties on a type you are merely adding to.
- 🔴 `IOptionsSnapshot<T>` (scoped/transient) or `IOptionsMonitor<T>` (singleton). **Never `IOptions<T>`.**
- 🔴 `CancellationToken` is mandatory on every async method, last parameter, **no default value**
  for internal methods. Always pass it through.
- No `.Wait()`, no `.GetAwaiter().GetResult()`, no `async void`.
- No `DateTime.Now` / `DateTimeOffset.Now` — inject a time provider.
- `Result<T>` (CSharpFunctionalExtensions) for domain/application failures — not exceptions
  for flow control. Map `Result.Error` to HTTP status at the API edge only.
- Guard clauses over `else`; braces on every `if`; every chained method on its own line
  starting with a dot; one attribute per line.
- Collection expressions `[]`; initialise collections in contracts (`public int[] Ids { get; init; } = [];`);
  never nullable collections; avoid `bool?`.
- Target frameworks vary per project. Check the project's TFM before using a C# 13/14
  feature. Never bump a TFM as a side effect.
- Always obey the nearest `.editorconfig`.

## Comments

- 🔴 **No inline comments. XML doc only.** A `//` inside a method body is banned. If a block
  needs a comment to be understood, extract it into a method named for what the comment said
  and put the explanation in `///` XML doc on that method.
- The only permitted exceptions, exhaustively: `///` XML doc; `// Arrange` / `// Act` /
  `// Assert` markers in tests (nothing appended); a justification on a `#pragma warning
  disable`; a Jira URL recording a durable external fact; generated-file headers.
- 🔴 **Never reference a task, plan, spec or decision artefact** — in a comment or in XML doc.
  No `Task 5`, no `R6`, no `per the brief`, no `see 02-implementation-plan.md`. State what is
  true, not what produced it.
- Never comment out dead code — delete it; git remembers.
- 🔴 **Comments stay short — the main idea only.** `///` is one or two lines; go longer only
  where the contract genuinely requires it (limits, null semantics, status codes), and never
  to narrate the body. Long-form rationale belongs in `docs/`, not in the source.

## Tests

- xUnit (v3 for new projects) + **NSubstitute** + **FluentAssertions 7.2.0**.
  🔴 Never Moq. 🔴 Never FluentAssertions v8+ (commercial licence).
- Naming: `{Action}_When_{Condition}_Should_{Expected}`; SUT is `_sut`/`sut`; result is
  `subject`/`result`/`actual`.
- AAA with `// Arrange` / `// Act` / `// Assert` comments; Act is one line.
- 🔴 Compare objects with `BeEquivalentTo` — never assert fields one by one.
- `Arg.Is<T>(predicate)` to constrain inputs; **avoid `Arg.Do`** for parameter capture.
- `.Returns(value)` for async — never `.Returns(Task.FromResult(value))`.
- `async Task`, never `async void`; xUnit v3 passes `TestContext.Current.CancellationToken`.
- `Result<T>`: assert `IsSuccess`/`IsFailure` before touching `.Value`.
- No discard assignments (`_ = await ...`) — assign and assert.

## Process

- 🔴 Work stays on a local branch. **Never `git push`**, never open an MR, never merge to main.
- 🔴 Commit messages are `<TASK-KEY>: <Description>` — `PROJ-42: Add the order lookup endpoint`.
  Conventional-Commits prefixes (`refactor(PROJ-118): …`, `feat: …`, `chore: …`) are **forbidden**;
  an optional change type goes at the end in parentheses: `PROJ-118: Share the sales channel id (refactor)`.
- Plans, task briefs and SDD artefacts live in the plans directory from `.claude/agentic-sdd-flow.json`
  (`plansDir`, default `temp/plans/`) — never inside the target repository's tracked tree.
- `finishing-a-development-branch`: decline the merge / push / PR options and report the branch name instead.
- Delegation follows the **Delegation** section below: whole jobs go to the specialist agents, not to a skill loaded inline.
- Do not restructure an existing solution, rename projects, or add `Directory.Packages.props`
  without explicit approval.

## Delegation

🔴 **A whole job in a specialist's domain goes to that specialist** through the `Agent` tool
(`subagent_type: agentic-sdd-flow:<name>`). Loading the matching skill and doing the work in the
top-level session is a violation, not a shortcut: the specialist carries the Roslyn tooling, the
checklists and the hand-off keys the top-level session does not. Load a skill inline only for a
narrow question, a single-file touch, or when you already are that specialist.

Dispatch order — stop at the first match:

1. An explicit user request for a named agent or a typed `/<skill>` wins.
2. Mandatory routes: .NET review → `code-reviewer` (or the `dotnet-code-review` skill when the user
   asked for an inline review); .NET test authoring → `tests-writer`, always.
3. Feature work with a task key → the `dotnet-feature` skill (design gate → plan → `dotnet-sdd`).
4. A whole job in a domain below → that agent.
5. Conventions only, for work you do yourself → the skill, inline.
6. Trivial edits and questions answerable from context → neither.

| The job | Agent |
|---|---|
| Something does not work: a failing or flaky test, a wrong result, a runtime exception, a fix round that closed nothing | `debugger` first — it returns the root cause and a fix brief; the fix then goes to `dotnet-implementer` |
| Broken build after a refactor or package bump | `build-error-resolver` |
| DbContext, LINQ, EF migrations, N+1, slow EF query | `ef-core-specialist` |
| Slow endpoint, allocations, caching, DI lifetimes | `performance-analyst` |
| Postgres tuning, indexes, hot-table migrations | `postgres-specialist` |
| T-SQL procedures, SSDT/dacpac, SQL Server plans | `tsql-specialist` |
| Deploy-window / rollback review of any migration | `migration-reviewer` |
| Auth, secrets, OWASP pass | `security-auditor` |
| Races, deadlocks, flaky tests, parallel jobs or consumers | `concurrency-specialist` |
| Dockerfile, CI pipeline, Helm, review environments | `devops-engineer` |
| Dead code, tech-debt cleanup, pre-MR tidying | `refactor-cleaner` |
| Audit of a test suite's quality | `test-quality-auditor` |
| Documentation made stale by a change | `docs-sync` |
| Solution layout, architecture choice, module boundaries | `dotnet-architect`; spanning services, stores or contracts → the `architecture-design` workflow |
| REST endpoints, contracts, versioning, OpenAPI | `api-designer` |
| gRPC (protobuf-net) contracts and compatibility | `grpc-contracts` |
| One plan task implemented by hand | `dotnet-implementer` |
| Verifying whether a review finding is real | `findings-verifier` |

Agents cannot dispatch each other; each ends with a **Hand-offs** section and you act on it.
