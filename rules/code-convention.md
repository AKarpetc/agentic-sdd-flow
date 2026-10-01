# Code Conventions

> [!NOTE]
> Test conventions are listed separately: [test-convention.md](test-convention.md)

## Table of Contents

- [Follow the Service First](#follow-the-service-first)
- [Scope: Minimal Diff](#scope-minimal-diff)
- [General Conventions 💅](#general-conventions-)
- [Git 🛣️](#git-️)
- [API & GRPC](#api--grpc)
- [Result Pattern](#result-pattern)
- [Data Structures & Collections](#data-structures--collections)
- [Configuration](#configuration)
- [Logging](#logging)
- [Code Style](#code-style)
  - [Comments](#comments)

---

## Follow the Service First
🔴 **The service's own established style comes first.** Before writing code, read the neighbouring code in the same project and follow its patterns: constructor style, encoding/BOM and line endings, naming, folder layout, and the caching, DI and helper patterns already in use.
- Reuse what the service already has (its `IMemoryCache.GetOrCreateAsync` pattern, its helpers, its constants) instead of introducing a new abstraction.
- The plugin's defaults below apply where the service has no established pattern of its own.

## Scope: Minimal Diff
🔴 **Change only what the task requires.** No opportunistic refactors, renames, moved constants, reformatting, whitespace/EOF/encoding changes, or style conversions of code the task does not touch.
- Refactoring is separate work: propose it and ask first; do it only after an explicit yes, preferably as its own task and MR.
- In review, unrelated churn in the diff is a finding: ask to revert it.

---

## General Conventions 💅

### Access Modifiers
- Use **most strict** access modifiers as possible: `private`/`internal` instead of `public`.
- Use the `internal` modifier for all services within a single project if possible.
- Use `public` for interfaces and `internal` for their implementations if applicable.

### Constructors
- 🔴 **Match the service's constructor style** for classes resolved from DI.
  - **The project's DI classes mostly use primary constructors** → new classes use primary constructors too.
  - **They mostly use explicit constructors, or there is no established pattern** → explicit constructor + `private readonly _field` (the default):
    `internal class Service { private readonly IFooService _foo; Service(IFooService foo) { _foo = foo; } }`
  - **Never convert existing classes between the two styles** as a side effect of a task.
  - Why the default is explicit: primary-constructor parameters are mutable and lose the `_field` naming.
- **Null Checks**: Do **not** check services for null using `ArgumentNullException` in the constructor.
  - **Bad**: `_unitOfWork = unitOfWork ?? throw new ArgumentNullException(nameof(unitOfWork));`
  - **Good**: `_unitOfWork = unitOfWork;`

### Double Negation
- Avoid **double negation**. Use positive naming (e.g., `Enabled` instead of `!Disabled`).

### Async & CancellationToken
**🔴 CancellationToken is mandatory in every async method.**

- It should be the last parameter in the parameter list.
- **Internal methods**: Do **not** use a default value. Force the caller to pass the token.
  - **Bad**: `public Task ExecuteAsync(CancellationToken cancellationToken = default)`
  - **Good**: `public Task ExecuteAsync(CancellationToken cancellationToken)`
- **Public API / Legacy Code**: `CancellationToken = default` is acceptable to avoid breaking changes or if the call stack is extremely difficult to refactor immediately (but try to avoid if possible).

---

## Git 🛣️

### Commit Messages
🔴 **Every commit message is `<TASK-KEY>: <Description>`** — the Jira key first, a colon, then what changed. Applies to every repository this plugin is installed into.

- **Good**: `PROJ-42: Add the order lookup endpoint`
- **Good**: `PROJ-118: Share the sales channel id and tighten the brand tests (refactor)`
- **Bad**: `refactor(PROJ-118): share the sales channel id` — Conventional-Commits prefixes (`feat(...)`, `fix(...)`, `chore(...)`, `refactor(...)`, `docs(...)`, `feat:`, `chore:` …) are **forbidden**, with or without the key inside the parentheses.
- **Bad**: `Add the order lookup endpoint` — no task key.
- **Change type is optional** and goes **at the end, in parentheses**: `(refactor)`, `(chore)`, `(docs)`, `(test)`, `(fix)`. Never as a prefix.
- **Description**: imperative mood, capitalised, no trailing period — `Add`, `Fix`, `Return`, not `added` / `adds`.
- **Task key** is the Jira issue the branch was created for (`feature/PROJ-118` → `PROJ-118`). Take it from the branch name or ask — never invent one. Only when there is genuinely no ticket (e.g. housekeeping in a repository without a tracker) may the key be omitted; the type still goes at the end in parentheses, never in front.
- Skills and agents that ship their own commit templates (`chore: apply dotnet format` in `de-sloppify`, kit scaffolds, …) **must be rewritten to this format** before committing — see [kit-overrides.md](kit-overrides.md).

---

## API & GRPC

### General API
- **Internal contracts**: Use GRPC.
- **External API**: Use HTTP REST-like approach.
- **Errors**: Use [Problem Details (RFC 7807)](https://tools.ietf.org/html/rfc7807) (`Microsoft.AspNetCore.Mvc.ProblemDetails`).
- **DTOs**: Use `record` for all DTOs in the projects.

### GRPC Guidelines

#### Definitions & Attributes
- Use `[ProtoContract]` and `[ProtoMember]`.
- **Compatibility**: Mark assembly or DTOs with `[CompatibilityLevel(CompatibilityLevel.Level300)]`.
  - This allows `Guid` to be serialized as a string (better cross-platform compatibility).
  - *Note*: Changing compatibility level on existing types can break backward compatibility.

#### Request/Response Pattern
- Always use wrappers for requests and responses. Avoid `void` or empty `Task` returns.
  - **Bad**: `Task<int> GetAsync(...)`
  - **Good**: `Task<GetResponse> GetAsync(GetRequest request, ...)`
- **Naming**: Use `VerbObjectRequest` / `VerbObjectResponse`.
  - Example: `GetPromoWizardStateRequest`, `GetPromoWizardStateResponse`.

#### Collections in Contracts
- **Initialize Collections**: Always initialize collections with a default value.
  - Example: `public int[] Ids { get; init; } = [];`
- **Prohibited Types**:
  - `Dictionary<K, V>`: Not supported in Proto standard. Use a list of key-value pairs or a custom map class (e.g., `Dictionary<int, BarList>`).
  - `IReadOnlyCollection<T>`: Issues with serialization (Wait for protobuf-net v3.2+). Use `T[]` or `IEnumerable<T>`.

---

## Result Pattern

Try to use the **Result pattern** where possible instead of throwing exceptions for logic flow.
Use CSharpFunctionalExtensions for ready implementation

### Layer-by-Layer Guidelines

| Layer           | Validation/Check     | Action Execution                | Returns                    | Throws                                           |
| :-------------- | :------------------- | :------------------------------ | :------------------------- | :----------------------------------------------- |
| **Domain**      | `CanExecute()`       | `Execute()`                     | `Result`                   | **Never** <br> (or only on invariant violations) |
| **Application** | Implicit or Explicit | Use domain logic or app service | `Result<T>`                | **Never** <br> (wrap all errors)                 |
| **API**         | Model validation     | Call application layer          | `IResult` / `ActionResult` | Maybe <br> (caught by middleware)                |

### Implementation Details

#### Domain Layer
- Methods (e.g., `ChangeName`) should return `Result` or `Result<T>`.
- Use `CanExecute` pattern for validation which returns `Result` or valid state.
- **Do not** throw exceptions for failing business rules.

#### Application Layer
- **Always check the result**: `if (result.IsFailure) { return ... }`.
- Return `Result<T>` to the API layer.
- Wrap all logic in `try-catch` blocks (if needed) or let Result handlings flow naturally.

#### API Layer
- Map `Result.Error` to HTTP status codes.
- Example:
  ```csharp
  if (result.IsFailure)
  {
      return result.Error switch
      {
          NotFoundAppError => NotFound(result.Error.Message),
          _ => BadRequest(result.Error.Message)
      };
  }
  return Ok(result.Value);
  ```

---

## Data Structures & Collections

### Usage
- Use **read-only** collection interfaces (`IReadOnlyCollection<T>`, `IReadOnlySet<T>`) for parameters and return types where possible.
- Use `IEnumerable<T>` for lazy evaluation.
- Use `T[]` (Arrays) for GRPC DTOs.

### Nullability
- **Collections**: Do not use nullable collections (e.g., `List<int>?`). Use an empty collection instead.
- **Booleans**: Avoid `bool?`. Use an `enum` (e.g., `State.Success`, `State.Failed`, `State.Ignored`) or a wrapper if "not set" is a valid state distinct from false.

---

## Configuration

### IOptions
- **❌ Do Not Use `IOptions`**: It does not support dynamic updates.
- **✅ Scoped/Transient**: Use `IOptionsSnapshot`.
- **✅ Singleton**: Use `IOptionsMonitor`.

### Feature Flags
- Must be **disabled by default** (`false`).
- Use positive naming: `NewFeatureEnabled` (not `OldFeatureDisabled`).

---

## Logging

- **Template Parameters**: Use `UpperCamelCase`.
  - **Bad**: `_logger.LogError("Error in {storeId}", storeId);`
  - **Good**: `_logger.LogError("Error in {StoreId}", storeId);`
- **Null Checks**: Never check logger for null. `_logger = logger;`.

---

## Code Style

### EditorConfig
🔴 **Mandatory**: Always use the project's `.editorconfig` for every code edit and code generation. No exceptions.

- Every project has an `.editorconfig` at its root (or a parent directory) — **always follow it**.
- Before editing or generating code, locate and respect the nearest `.editorconfig` for the file being modified (indentation, tabs vs. spaces, line endings, end-of-file newline, charset, max line length, naming/style rules, etc.).
- Do not override formatting rules inline (e.g. `#pragma warning disable` for style warnings) unless there is a documented reason.
- Do not introduce changes that violate `.editorconfig` rules even if surrounding legacy code does — match the config, not the drift.
- If multiple `.editorconfig` files exist in the path hierarchy, apply them according to standard `.editorconfig` precedence (closest file wins, unless `root = true` cuts off inheritance).

### Comments
🔴 **No inline comments. XML doc only.** `//` and `/* */` explanatory comments inside a method body are not permitted. If a block of code needs a comment to be understood, that block is a method waiting to be extracted — **extract it, name it for what the comment said, and put the explanation in `///` XML doc on the new method.**

The comment is a signal that the code failed to explain itself. Deleting the comment does not fix that; extracting the code does.

- **Bad** — a comment propping up an unnamed block:
  ```csharp
  public async Task<Result> RenameAsync(string table, CancellationToken cancellationToken)
  {
      // Postgres keeps the old PK constraint name on rename, so free it before CREATE TABLE.
      var pk = await _catalog.GetPrimaryKeyNameAsync(table, cancellationToken);
      await _catalog.DropConstraintAsync(table, pk, cancellationToken);
      ...
  }
  ```
- **Good** — the block becomes a named method and the comment becomes its contract:
  ```csharp
  public async Task<Result> RenameAsync(string table, CancellationToken cancellationToken)
  {
      await ReleasePrimaryKeyNameAsync(table, cancellationToken);
      ...
  }

  /// <summary>
  /// Drops the primary key so its name is free before the new table is created —
  /// Postgres keeps the old constraint name when a table is renamed.
  /// </summary>
  private async Task ReleasePrimaryKeyNameAsync(string table, CancellationToken cancellationToken)
  {
      var pk = await _catalog.GetPrimaryKeyNameAsync(table, cancellationToken);
      await _catalog.DropConstraintAsync(table, pk, cancellationToken);
  }
  ```
- Never narrate what the next statement does, restate the method name, comment out dead code, or leave TODO essays. Dead code is deleted, not commented out — git remembers it.
- 🔴 **Never reference a task, plan, spec or ticket artefact — in a comment or in XML doc.** No `Task 5`, no `R6`, no `per the brief`, no `see 02-implementation-plan.md`, no decision numbers like `D3`. These are meaningless the moment the plan is archived, and they point at files that are usually untracked. State *what is true*, not which task made it true.

#### The only permitted exceptions

Exhaustive — anything not on this list is a violation:

| Allowed | Why |
|---|---|
| `/// ` XML doc on any member | The sanctioned form. See below. |
| `// Arrange` / `// Act` / `// Assert` in tests | Structural section markers required by [test-convention.md § Anatomy of a Test](test-convention.md). They mark structure, they do not explain code. Nothing may be appended to them. |
| A documented `#pragma warning disable` justification | The suppression must state why, or it should not exist. |
| A Jira URL recording a *durable external fact* a reader cannot otherwise discover | e.g. `// note: wip https://tracker.example.com/browse/PROJ-7097` on a permanently disabled test gate. Never a breadcrumb for how the code got written. |
| Generated-file headers | Not hand-authored. |

#### XML doc
- 🔴 **Keep it short — the main idea only.** One or two lines. A `///` block that reads like prose is over budget: cut it to the single sentence a caller actually needs.
- Public API gets `///` where a caller cannot infer the contract — limits, null semantics, thrown status codes.
- Go past two lines only where the contract genuinely requires it (limits, null semantics, status codes), never to narrate the body.
- Private methods extracted purely to replace a comment get `///` too — that extraction is the whole point of the rule.
- Long-form design rationale belongs in `docs/`, not in the source.

### Formatting
- **Line Breaks**: Use line breaks for long lines.
- **Chain Methods**: Place **every** chained method on a new line starting with a dot.
  ```csharp
  var result = items
      .Where(x => x.Active)
      .Select(x => x.Name)
      .ToArray();
  ```
- **Attributes**: Place each attribute on a separate line.
  ```csharp
  [Required]
  [JsonProperty("foo")]
  public string Foo { get; set; }
  ```

### Control Flow
- **Braces**: Use braces `{}` for all `if` statements, even one-liners.
- **Else**: Avoid `else` keyword where possible. Use early returns (Guard Clauses) implementation pattern.
  ```csharp
  // Bad
  if (valid) { ... } else { return error; }
  
  // Good
  if (!valid) { return error; }
  ...
  ```

### Properties
- 🔴 **New properties use `{ get; init; }`, not `{ get; set; }`.** Immutable after construction is the default; object initializers and `System.Text.Json` both work with `init`. Use `set` only where something genuinely mutates the instance after it is built, and say why.
- Do **not** rewrite existing `{ get; set; }` properties on a type you are merely adding to — match the file for what is already there, and apply `init` to what you add.

### Naming
- **Context Prefixes**: Do **not** use context prefixes in property names within a class.
  - **Bad**: `class Product { public int ProductId { get; set; } }`
  - **Good**: `class Product { public int Id { get; set; } }`
- **Async Suffix**: Maintain consistency with the existing style in the file/project.

### Classes & Methods
- **Partial Classes**: Avoid `partial` classes (except for code generation).
- **Expression Bodies**: Encouraged for short methods/properties.

### Invocations
- **Arguments**: Place arguments on separate lines if there is more than one (or if they are long).
- **Named Arguments**: Encouraged for literals or unclear boolean flags.
  - `Foo(bar: 1, isRecursive: true);`

### Syntax Preferences
- **Default Keyword**:
  - Avoid `variable = default` for primitives or classes. Use implicit types or explicit values.
  - Exception: Structs/Generics.
  - **Bad**: `TimeSpan t = new();`
  - **Good**: `TimeSpan t = default;`
- **Ternary Operator**: Encouraged for assignments.
- **Null-Coalescing (`??`)**: Encouraged.
- **Constants**: Use `const` over variables.