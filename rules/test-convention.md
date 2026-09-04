---
trigger: always_on
---


# Test Conventions

These conventions apply to all unit and integration tests across the solution. The goal is to write clear, maintainable tests that validate behavior through outcomes rather than implementation details.

## Frameworks & Tools

- **Test Framework**: [`xUnit`](https://xunit.net/) (Preferred).
  - **Use `xUnit v3`** (Core Framework `v3.2.2+`) for all new test projects. Targets `.NET 8.0+` / `.NET Framework 4.7.2+`.
  - `xUnit v2` (`2.9.3`) is in maintenance mode — acceptable for existing projects already on it, but do not start new ones on v2.
  - `nUnit` is allowed **only** in legacy code (legacy code only). Use `xUnit` for all new tests.
- **Mocking**: [`NSubstitute`](https://github.com/nsubstitute/NSubstitute) (latest stable).
- **Assertions**: [`FluentAssertions` **v7.x only**](https://github.com/fluentassertions/fluentassertions).
  - 🔴 **Do NOT upgrade to v8+** — v8 changed to a commercial Xceed license. **v7.2.0 is the last free MIT-licensed version** and is what every project must pin to.
  - In `.csproj`: `<PackageReference Include="FluentAssertions" Version="7.2.0" />` (do not float with `*` or `>=8.x`).

## Naming & Organization

### Naming Patterns
- **Test Project**: `[ProjectUnderTest].Tests.(Unit|Integration)`
- **Test File**: `{SystemUnderTest}Tests.cs` (e.g., `CartSynchronizerTests.cs`)
- **Test Method**: `{TestAction}_When_{Condition(s)}_Should_{ExpectedBehavior}`
  - Example: `Add_WhenItemExists_ShouldUpdateQuantity`

### Variable Naming
- **System Under Test**: `_sut` (field) or `sut` (local).
- **Result**: `subject`, `result`, `actual`.
- **Inputs**: Use descriptive names like `query`, `parameters`, `expected`.

### Visibility
- Use `[assembly: InternalsVisibleTo(...)]` for assemblies that need to be tested, rather than making internal members public.

## Test Types & Parameterization (xUnit)

### `[Fact]` vs `[Theory]`
- **`[Fact]`** — single, parameter-less test case.
- **`[Theory]`** — parameterized test. Always pair with one of: `[InlineData(...)]`, `[MemberData(nameof(Source))]`, or `[ClassData(typeof(Source))]`.
- **Prefer `[Theory]` over copy-pasted `[Fact]`s** when the test logic is identical and only inputs/expectations change.

```csharp
[Theory]
[InlineData(1, 2, 3)]
[InlineData(-1, 1, 0)]
[InlineData(0, 0, 0)]
public void Add_ShouldReturnSum(int a, int b, int expected)
{
    var result = _sut.Add(a, b);
    result.Should().Be(expected);
}
```

- Use **`[MemberData]`** when inputs are non-constant (e.g., complex objects, records). The source must be `public static IEnumerable<object[]>` (xUnit v2) or `public static TheoryData<...>` (preferred — strongly typed, works in v2 and v3).

```csharp
public static TheoryData<CartDto, decimal> CartTotals => new()
{
    { new CartDto { /* ... */ }, 10m },
    { new CartDto { /* ... */ }, 0m },
};

[Theory]
[MemberData(nameof(CartTotals))]
public void Total_ShouldMatch(CartDto cart, decimal expected) { /* ... */ }
```

### Async Tests
- Test methods must be `async Task` — **never `async void`** (xUnit cannot observe completion of `void`).
- Honor cancellation: in **xUnit v3** use `TestContext.Current.CancellationToken` and pass it through to the SUT instead of `CancellationToken.None`.

### Test Lifecycle / Fixtures
- **Per-test setup**: use the test class **constructor**; per-test teardown: implement `IDisposable` / `IAsyncDisposable`.
- **Async setup/teardown**: implement `IAsyncLifetime` (`InitializeAsync` / `DisposeAsync`). Do not run `.Result` / `.Wait()` in the constructor.
- **Shared context across tests in one class**: implement `IClassFixture<TFixture>` — fixture is created once per test class.
- **Shared context across multiple classes**: define `[CollectionDefinition]` + `ICollectionFixture<TFixture>` and tag classes with `[Collection("name")]`.
- Avoid `[Trait]` for selection logic when categorizing — use it for filtering only (e.g., `[Trait("Category", "Integration")]`).

### Skipping & Output
- **Skip** with a reason: `[Fact(Skip = "Flaky on CI — see #1234")]`. Never silently `return;` from a test.
- **Capture diagnostic output** via `ITestOutputHelper` injected into the constructor — **do not** use `Console.WriteLine` (it is not captured by xUnit runners).

```csharp
public sealed class FooTests
{
    private readonly ITestOutputHelper _output;
    public FooTests(ITestOutputHelper output) => _output = output;
}
```

## Anatomy of a Test (AAA)

Divide tests into 3 distinct blocks separated by comments:

1.  **Arrange**: Setup mocks, create entities, initialize dependencies.
2.  **Act**: Call the method under test.
    - **Rule**: The `Act` section should ideally be a **single line**.
3.  **Assert**: Verify the result.

> [!IMPORTANT]
> These three markers are the **only** inline comments permitted in a test. [code-convention.md § Comments](code-convention.md#comments) bans `//` explanatory comments everywhere and carves out exactly `// Arrange`, `// Act`, `// Assert` as structural markers. Write them bare — never append an explanation (`// Arrange — the cache is warm here`). If a test needs explaining, extract a well-named helper and document it with `///`.

```csharp
[Fact]
public void Add_ShouldAlwaysReturnSum()
{
    // Arrange
    var calculator = new Calculator();
    int a = 2;
    int b = 3;

    // Act
    var result = calculator.Add(a, b);

    // Assert
    result.Should().Be(5);
}
```

## Mocking & Stubbing Guidelines

### Core Principle: Subject-Focused
- **Assert the subject** (result of the SUT), not the internals of collaborators.
- **Do not** verify the exact internal sequence of calls unless the behavior depends on it.

### Argument Matching (`Arg.*`) policy
1.  **`Arg.Is<T>(predicate)`**: **Preferred**. Use this to constrain inputs during setup.
    - Example: `_client.Get(Arg.Is<Params>(p => p.Id == 1)).Returns(expected);`
2.  **`Arg.Any<T>()`**: Use when the specific argument value is irrelevant or for `DidNotReceive` checks.
3.  **`Arg.Do`**: **Avoid**. Do not use `Arg.Do` to capture parameters for later assertion.
    - *Why?* It leaks implementation details into the test and makes the test harder to read. constraint the input in the setup instead.

### Examples

**Good (Constrain inputs):**
```csharp
var expected = new CartDto { Total = 3 };
_client.GetCart(Arg.Is<CartParams>(p => p.StoreId == storeId), token)
       .Returns(expected);

var subject = await _sut.Handle(query, token);

subject.Should().BeEquivalentTo(expected);
```

**Bad (Parameter Capture):**
```csharp
CartParams? captured = null;
_client.GetCart(Arg.Do<CartParams>(x => captured = x), token) // ⛔ Avoid this
       .Returns(expected);

await _sut.Handle(query, token);

captured!.StoreId.Should().Be(storeId); // ⛔ Asserting implementation detail
```

### Configuring Returns

- **Static value** — for sync **and** async methods, just call `.Returns(value)`. NSubstitute auto-wraps in `Task` / `ValueTask` for async return types — do **not** write `.Returns(Task.FromResult(value))`.
- **Dynamic value (callback)** — `.Returns(call => ...)` when the result depends on the input.
- **Sequential values** — `.Returns(first, second, third)` for successive calls.
- **Throwing** — `.Throws(new SomeException())` or `.ThrowsAsync<T>()` for async; do not stub a return *and* an exception on the same call.
- **`ReturnsForAnyArgs` / `ThrowsForAnyArgs`** — short-circuits argument matching. Use sparingly, only when the args are truly irrelevant.
- **Properties** — set directly (`sub.Mode = "HEX";`) or via `sub.Mode.Returns("HEX")`. Do not mix the two styles in one test.
- **Events** — raise via `sub.SomeEvent += Raise.Event<EventHandler>(this, args);`.

```csharp
// Async — no Task.FromResult wrapper needed
_repo.GetByIdAsync(Arg.Is<int>(x => x == 1), token).Returns(entity);

// Sequential
_clock.UtcNow.Returns(t1, t2, t3);

// Throwing
_repo.SaveAsync(Arg.Any<Order>(), token).ThrowsAsync<DbUpdateException>();
```

### Verification

- **`Received()`** — at least one matching call. **`Received(n)`** — exactly `n` calls. **`DidNotReceive()`** — zero calls.
- Pass the **same `Arg.Is<T>(...)` constraints** in `Received()` that you used (or would have used) in setup — this is what makes verification meaningful.
- Use **`ReceivedWithAnyArgs()`** only when the method overload itself is what's being verified, not the arguments.
- **`ClearReceivedCalls()`** — reset the call log between phases of a single test (rare; usually a sign the test is doing too much).
- **`Received.InOrder(() => { ... })`** — verify ordering across substitutes only when ordering is part of the contract under test.

```csharp
await _sut.Handle(command, token);

await _publisher.Received(1).PublishAsync(
    Arg.Is<OrderPlaced>(e => e.OrderId == command.OrderId),
    token);
_repo.DidNotReceive().Delete(Arg.Any<Order>());
```

## Assertions

### Object Comparison
- **Do not** assert specific fields individually.
- **Use `BeEquivalentTo`** for object comparisons. This ensures that if new fields are added, tests will automatically validate them (or fail if they don't match), keeping tests robust.

**Correct:**
```csharp
cart.Should().BeEquivalentTo(new CartAggregate(storeId, ...), 
    opts => opts
        .Excluding(z => z.Created)
        .Excluding(z => z.Updated));
```

**Wrong:**
```csharp
cart.Id.Should().Be(123);
cart.StoreId.Should().Be(456);
// Misses any other properties!
```

### No Discard Assignments
- **Do**: Assign the result of an async call to a local variable (e.g., `subject`) and assert it.
- **Don't**: Use discard assignments (e.g., `_ = await ...`).

```csharp
// correct
var subject = await _sut.Handle(query, token);
subject.Should().NotBeNull();
```

### `BeEquivalentTo` Configuration (FluentAssertions v7)
Prefer the strongly-typed options API rather than asserting fields one-by-one:

- **`Excluding(x => x.Created)`** — skip volatile / unrelated fields.
- **`ExcludingMissingMembers()`** — compare only members that exist on both sides (useful for DTO ↔ Entity).
- **`WithStrictOrdering()`** / **`WithoutStrictOrdering()`** — enforce or relax sequence order on collections.
- **`ComparingByMembers<T>()`** — force structural comparison for a type that overrides `Equals` undesirably.
- **`RespectingRuntimeTypes()`** — compare by the actual runtime type, not the declared type (polymorphism).
- **`Using<DateTime>(ctx => ctx.Subject.Should().BeCloseTo(ctx.Expectation, 1.Seconds())).WhenTypeIs<DateTime>()`** — custom comparison rule per type.

### Collection Assertions
Prefer FluentAssertions' specialized collection matchers over manual loops:

```csharp
items.Should().HaveCount(3);
items.Should().ContainSingle(x => x.IsActive);
items.Should().AllSatisfy(x => x.Total.Should().BePositive());
items.Should().OnlyContain(x => x.StoreId == storeId);
items.Should().BeInAscendingOrder(x => x.CreatedAt);
items.Should().BeEquivalentTo(expected, opts => opts.WithStrictOrdering());
```

### Exception Assertions
- **Sync**: `act.Should().Throw<TException>().WithMessage("*partial*").And.SomeProperty.Should()...`
- **Async**: **must `await`** the assertion — `await act.Should().ThrowAsync<TException>();`
- **No throw**: `act.Should().NotThrow();` / `await act.Should().NotThrowAsync();`

```csharp
var act = async () => await _sut.Handle(invalidCommand, token);

await act.Should()
    .ThrowAsync<ValidationException>()
    .WithMessage("*StoreId*");
```

### Type & Pattern Assertions
- **`BeOfType<T>()`** + **`.Which`** — drill into a typed result without casting.
- **`BeAssignableTo<T>()`** — accept any subtype.
- **`Match<T>(predicate)`** — when a one-off predicate is clearer than chaining matchers.

```csharp
result.Should().BeOfType<NotFoundAppError>()
    .Which.Message.Should().Contain(storeId.ToString());
```

### Assertion Scopes (group failures)
Wrap multiple assertions in an **`AssertionScope`** so all failures are reported in a single run instead of stopping at the first one. Use this when independent properties must all hold:

```csharp
using var _ = new AssertionScope();
order.Status.Should().Be(OrderStatus.Paid);
order.Total.Should().Be(100m);
order.Lines.Should().HaveCount(2);
```

### Result Pattern Assertions (`CSharpFunctionalExtensions`)
Since the codebase returns `Result<T>` from application logic, assert the discriminator first, then drill in:

```csharp
// Success
subject.IsSuccess.Should().BeTrue();
subject.Value.Should().BeEquivalentTo(expected);

// Failure — assert the error type and message
subject.IsFailure.Should().BeTrue();
subject.Error.Should().BeOfType<NotFoundAppError>()
    .Which.Message.Should().Contain("not found");
```

Do **not** call `.Value` on a `Result<T>` you have not first asserted as successful — it throws and produces a noisy stack trace instead of a clear assertion failure.

## Coding Style for Tests

- **Implicit Typing**: Prefer `var` when the type is obvious from the right-hand side.
  - `var subject = await ...`
  - `var expected = new Dto { ... }`
- **Value Objects**: Try to use Value Objects instead of primitives/references where possible to make mocking and assertions easier.
