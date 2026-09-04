# Rule Compliance Checklist

The authoritative enumeration of what a .NET review **must** check, derived verbatim from:

- [code-convention.md](../../../rules/code-convention.md)
- [single-type-per-file.md](../../../rules/single-type-per-file.md)
- [test-convention.md](../../../rules/test-convention.md) *(tests only)*

🔴 **The rule files are the source of truth, not this checklist.** Read all three at review time (Step 0). If a rule file has changed and this checklist disagrees, the rule file wins and this file is stale — flag it to the user.

🔴 **Every violation is reported.** There is no "too minor to mention" for these three files. A formatting rule breach goes in *Convention Violations*, not into silence. Only a rule that genuinely does not apply to the diff is skipped.

## Precedence note

`common.md` contradicts `code-convention.md` in two places. `code-convention.md` wins (per [kit-overrides.md](../../../rules/kit-overrides.md)):

| Topic | common.md says | 🔴 Apply this |
|---|---|---|
| Primary constructors | "use them for DI" | **Banned** for DI-resolved classes |
| Configuration | "use `IOptions<T>`" | **Never `IOptions<T>`** — `IOptionsSnapshot`/`IOptionsMonitor` |

## Severity floors

Assign at least this severity; escalate when the blast radius is larger.

| Band | Rules | Section |
|---|---|---|
| **Critical** | Missing/ignored `CancellationToken`, `.Result`/`.Wait()`, `async void`, `IOptions<T>`, `DateTime.Now`, exceptions used for business flow, feature flag defaulting to `true`, `Arg.Do`, FluentAssertions v8+, Moq in a new test | 🚨 Critical |
| **Convention** | Primary ctor on a DI class, >1 top-level type per file, filename ≠ type name, `{ get; set; }` on a new property, missing `Result<T>`, `Dictionary<K,V>`/`IReadOnlyCollection<T>` in a gRPC contract, uninitialized contract collection, comment referencing a task/plan artefact, multi-line comment, test naming/AAA/`BeEquivalentTo` breaches | 🔴 Convention Violations |
| **Nit** | Chained-method line breaks, attribute-per-line, brace/`else` style, named-argument suggestions, `const` over variable, expression bodies | 💡 Minor Tweaks |

---

## A. code-convention.md — production code

### A1. Access modifiers & structure
- [ ] Most restrictive modifier possible — `internal` for services within one project, `public` only where genuinely crossing an assembly boundary.
- [ ] `public` interface + `internal` implementation where applicable.
- [ ] No `partial` classes except for code generation.
- [ ] Expression bodies used for short methods/properties.

### A2. Constructors
- [ ] 🔴 **No primary constructors on DI-resolved classes.** Explicit ctor + `private readonly _field`. Records/DTOs may use positional parameters.
- [ ] No `ArgumentNullException` null-guards on injected services — `_unitOfWork = unitOfWork;` plain.
- [ ] Logger never null-checked.

### A3. Async & CancellationToken
- [ ] 🔴 **Every async method takes a `CancellationToken`**, as the **last** parameter.
- [ ] Internal methods: **no default value** (`CancellationToken cancellationToken`, not `= default`). Public API/legacy may default.
- [ ] The token is actually **passed through** to every downstream async call — accepting and dropping it is a finding.
- [ ] No `.Result`, `.Wait()`, `.GetAwaiter().GetResult()`, no `async void`.

### A4. Result pattern
- [ ] Domain methods return `Result`/`Result<T>`; **never throw** for a failing business rule (invariant violations only).
- [ ] `CanExecute()` validation pattern where a check precedes an action.
- [ ] Application layer returns `Result<T>` and **always checks** `if (result.IsFailure)` before using the value.
- [ ] API layer maps `result.Error` to status codes via a `switch` (`NotFoundAppError => NotFound(...)`).
- [ ] `CSharpFunctionalExtensions` used, not a bespoke Result type.
- [ ] No `try-catch` as business flow control.

### A5. API & gRPC contracts
- [ ] Internal contracts gRPC; external HTTP REST-like.
- [ ] Errors as `ProblemDetails` (RFC 7807).
- [ ] All DTOs are `record`.
- [ ] `[ProtoContract]` / `[ProtoMember]` present; `[CompatibilityLevel(CompatibilityLevel.Level300)]` on assembly or DTO.
- [ ] Request/response **wrappers** — no bare `Task<int>`/`void`; named `VerbObjectRequest` / `VerbObjectResponse`.
- [ ] Contract collections initialized: `public int[] Ids { get; init; } = [];`
- [ ] 🔴 No `Dictionary<K,V>` and no `IReadOnlyCollection<T>` in a proto contract — use `T[]` or `IEnumerable<T>`.

### A6. Collections & nullability
- [ ] Read-only interfaces (`IReadOnlyCollection<T>`, `IReadOnlySet<T>`) for ordinary params/returns; `IEnumerable<T>` for lazy; `T[]` for gRPC DTOs.
- [ ] No nullable collections (`List<int>?`) — empty collection instead.
- [ ] No `bool?` — use an enum or wrapper when "not set" is meaningful.
- [ ] No double negation; positive naming (`Enabled`, not `!Disabled`).

### A7. Configuration
- [ ] 🔴 **No `IOptions<T>`.** `IOptionsSnapshot<T>` for scoped/transient, `IOptionsMonitor<T>` for singleton.
- [ ] Feature flags **default to `false`** and are positively named (`NewFeatureEnabled`).
- [ ] No hardcoded configuration strings.

### A8. Logging
- [ ] Message-template placeholders in `UpperCamelCase` — `{StoreId}`, not `{storeId}`.

### A9. Comments — XML doc only
- [ ] 🔴 **No inline `//` or `/* */` comments in a method body.** Every one is a violation; the fix is **extract the commented block into a method named for what the comment said, and move the explanation to `///` XML doc on it** — not simply deleting the comment. Write the finding as the extraction, showing the new method signature and its doc.
- [ ] Permitted exceptions, exhaustive — anything else is a violation:
  - `///` XML doc on any member
  - `// Arrange` / `// Act` / `// Assert` markers in tests (required by `test-convention.md`); nothing may be appended to them
  - a documented `#pragma warning disable` justification
  - a Jira URL recording a durable external fact a reader cannot otherwise discover (e.g. on a permanently disabled test gate)
  - generated-file headers
- [ ] No narration of the next statement, no restating the method name, no TODO essays.
- [ ] 🔴 **No commented-out code** — deleted, not commented out.
- [ ] 🔴 **No reference to a task, plan, spec, ticket or decision artefact**, in a comment *or* in XML doc — no `Task 5`, `R6`, `D3`, `per the brief`, `see 02-implementation-plan.md`.
- [ ] XML doc stays on the **contract and the *why*** (limits, null semantics, status codes); it may exceed one line, but it is not a walkthrough of the body. Long-form rationale belongs in `docs/`.

### A10. Formatting & style
- [ ] 🔴 The nearest `.editorconfig` is obeyed (indentation, line endings, charset, final newline, naming). Closest file wins unless `root = true` cuts inheritance.
- [ ] No `#pragma warning disable` for style warnings without a documented reason.
- [ ] Every chained method on its own line, starting with the dot.
- [ ] Each attribute on its own line.
- [ ] Long lines broken.
- [ ] Braces on **all** `if` statements, including one-liners.
- [ ] `else` avoided — guard clauses / early returns.
- [ ] Arguments on separate lines when more than one, or when long.
- [ ] Named arguments for literals and unclear boolean flags.

### A11. Properties & naming
- [ ] 🔴 **New properties use `{ get; init; }`**, not `{ get; set; }`. `set` only where the instance genuinely mutates after construction, with a stated reason.
- [ ] Existing `{ get; set; }` properties on a type being extended are **not** rewritten — match the file, apply `init` to what is added.
- [ ] No context prefixes — `Product.Id`, not `Product.ProductId`.
- [ ] `Async` suffix consistent with the surrounding file/project.

### A12. Syntax preferences
- [ ] No `= default` for primitives or classes (structs/generics excepted).
- [ ] Ternary for assignments; `??` encouraged.
- [ ] `const` over a variable where the value is constant.

---

## B. single-type-per-file.md

- [ ] 🔴 Exactly **one top-level type** per `.cs` file — class, interface, record, or enum.
- [ ] 🔴 Filename matches the type name **exactly** (`ISettingsRepository` → `ISettingsRepository.cs`).
- [ ] No grouping files — no `Models.cs`, no `Interfaces.cs`, no `Enums.cs`.
- [ ] File-scoped namespaces (`namespace MyProject.Data;`).

When a diff adds a grouped file, the finding is "split into N files", listing each type and its required filename.

---

## C. test-convention.md — test code only

### C1. Frameworks (hard gates)
- [ ] xUnit. **v3 (Core ≥ 3.2.2) for any new test project**; v2 acceptable only in a project already on it; NUnit only where legacy code already uses it.
- [ ] NSubstitute for mocking. 🔴 **Moq in a new test is a Critical finding.** (Existing legacy tests already on Moq are grandfathered — do not flag untouched code.)
- [ ] 🔴 **FluentAssertions pinned to `7.2.0`** — `<PackageReference Include="FluentAssertions" Version="7.2.0" />`. Any `8.x`, floating `*`, or `>=8` is Critical (commercial license). Bare `Assert.*` is a violation too.

### C2. Naming & organization
- [ ] Project: `[ProjectUnderTest].Tests.(Unit|Integration)`.
- [ ] File: `{SystemUnderTest}Tests.cs`.
- [ ] Method: `{Action}_When_{Condition}_Should_{ExpectedBehavior}`.
- [ ] SUT named `_sut` / `sut`; result named `subject` / `result` / `actual`; inputs descriptively named.
- [ ] `[assembly: InternalsVisibleTo(...)]` used rather than widening members to `public` for testability.

### C3. Test types & lifecycle
- [ ] `[Theory]` instead of copy-pasted `[Fact]`s that differ only in data.
- [ ] `[Theory]` always paired with `[InlineData]` / `[MemberData]` / `[ClassData]`.
- [ ] `TheoryData<...>` preferred over `IEnumerable<object[]>` for `[MemberData]`.
- [ ] 🔴 `async Task`, **never `async void`**.
- [ ] xUnit v3: `TestContext.Current.CancellationToken` threaded into the SUT — not `CancellationToken.None`.
- [ ] Setup in the constructor; teardown via `IDisposable`/`IAsyncDisposable`; async setup via `IAsyncLifetime`. No `.Result`/`.Wait()` in a constructor.
- [ ] Shared context via `IClassFixture<T>` / `[CollectionDefinition]` + `ICollectionFixture<T>`.
- [ ] Skips use `[Fact(Skip = "reason")]` — **never** a silent `return;`.
- [ ] Diagnostics via `ITestOutputHelper`, never `Console.WriteLine`.

### C4. AAA structure
- [ ] Three blocks separated by `// Arrange`, `// Act`, `// Assert` comments.
- [ ] **Act is a single line.**

### C5. Mocking
- [ ] Assertions target the **subject**, not collaborator internals; no verifying internal call sequence unless ordering is the contract.
- [ ] `Arg.Is<T>(predicate)` preferred for constraining setup inputs.
- [ ] `Arg.Any<T>()` only when the value is genuinely irrelevant, or for `DidNotReceive`.
- [ ] 🔴 **`Arg.Do` is banned** for capturing parameters to assert later — constrain the input in setup instead.
- [ ] Async stubs use `.Returns(value)` — **no `Task.FromResult` wrapper**.
- [ ] Sequential returns `.Returns(a, b, c)`; throwing via `.Throws`/`.ThrowsAsync<T>`; never a return *and* a throw on the same call.
- [ ] `ReturnsForAnyArgs`/`ThrowsForAnyArgs` used sparingly.
- [ ] Property stubbing style not mixed (`sub.Mode = "HEX"` vs `sub.Mode.Returns("HEX")`).
- [ ] `Received(n)` / `DidNotReceive()` carry the **same `Arg.Is<T>` constraints** as the setup.
- [ ] `ClearReceivedCalls()` treated as a smell (test doing too much).

### C6. Assertions
- [ ] 🔴 **`BeEquivalentTo` for object comparison** — field-by-field assertion of a returned object is a violation, because new fields silently escape coverage.
- [ ] `BeEquivalentTo` options used instead of hand-rolled comparisons: `Excluding`, `ExcludingMissingMembers`, `WithStrictOrdering`, `ComparingByMembers<T>`, `RespectingRuntimeTypes`, `Using<T>(...).WhenTypeIs<T>()`.
- [ ] Collection matchers (`ContainSingle`, `AllSatisfy`, `OnlyContain`, `BeInAscendingOrder`) instead of manual loops.
- [ ] 🔴 No discard assignments — `var subject = await _sut.Handle(...)`, never `_ = await ...`.
- [ ] Async exception assertions **awaited**: `await act.Should().ThrowAsync<T>()`.
- [ ] `BeOfType<T>().Which` instead of casting.
- [ ] `AssertionScope` used when several independent properties must all hold.
- [ ] `Result<T>`: assert `IsSuccess`/`IsFailure` **first**; never touch `.Value` before proving success; assert `Error` by type and message on failure.
- [ ] `var` where the right-hand side makes the type obvious.

---

## Grep sweep (fallback / cross-check)

Run over **changed files only**. Hits are candidates, not verdicts — confirm in context.

```bash
# production code
rg -n 'IOptions<'                                    # A7  → IOptionsSnapshot/IOptionsMonitor
rg -n 'DateTime\.(Now|UtcNow)'                       # no ambient clock
rg -n '\.Result\b|\.Wait\(\)|GetAwaiter\(\)\.GetResult' # A3
rg -n 'async void'                                   # A3
rg -n 'CancellationToken cancellationToken = default' # A3 (internal methods)
rg -n 'Task(<[^>]+>)? \w+\([^)]*\)' -g '*.cs'        # then check each async method has a token
rg -n '^\s*(internal|public|sealed).*class \w+\('    # A2 primary ctor
rg -n 'throw new ArgumentNullException'              # A2
rg -n '\{ get; set; \}'                              # A11 on NEW properties
rg -n 'new HttpClient\(|catch\s*\(\s*Exception'      # resilience
rg -n '\{[a-z]\w*\}'                                 # A8 lowercase log placeholder
# A9 — inline comments. The leading `[^:/]` excludes `///` XML doc and `http://` URLs
# without needing PCRE2; the second filter drops the legal AAA markers. Verified to
# report only real violations on a mixed sample.
rg -n '(^|[^:/])//[^/]' -g '*.cs' | rg -v '// (Arrange|Act|Assert)$'
rg -n '/\*'                                          # A9 block comment
rg -n '^\s*//\s*(var|if|return|await|public|private|foreach|//)' # A9 commented-out code
rg -n 'Task\d|R\d\b|per the brief|see \d\d-|Task \d' # A9 artefact references
rg -n 'namespace \w[\w.]* *\{'                       # B file-scoped namespace
rg -n '^\s*(public|internal).*(class|record|interface|enum) ' -c  # B >1 type per file

# tests
rg -n 'using Moq|Mock<'                              # C1
rg -n 'FluentAssertions.*Version="(8|\*|>=)'         # C1
rg -n 'Arg\.Do'                                      # C5
rg -n 'Returns\(Task\.FromResult'                    # C5
rg -n 'CancellationToken\.None'                      # C3
rg -n '_ = await'                                    # C6
rg -n 'Console\.WriteLine'                           # C3
rg -n 'async void'                                   # C3
rg -n 'Assert\.'                                     # C1 bare xUnit assert
```

Counting types per file: `rg -c '^\s*(public|internal|private|sealed|abstract|static).*\b(class|record|interface|enum|struct)\b' <file>` — any count > 1 needs a manual look (nested types are legal, top-level duplicates are not).
