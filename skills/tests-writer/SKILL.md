---
name: tests-writer
description: Guidelines for writing maintainable, outcome-focused unit tests across .NET projects. Use this skill whenever writing or reviewing tests.
---
# Tests Writer

Governs structural, syntactic, and architectural conventions for C# unit tests across .NET projects. Validates behavior through outcomes, not implementation details. Follows [test-convention.md](../../rules/test-convention.md).

## Frameworks & Tools

- **Test Framework**: `xUnit`. `nUnit` only where legacy code already uses it.
- **Mocking**: `NSubstitute`. **Never use Moq** in new tests.
  - Exception: a pre-existing legacy test helper that wraps Moq internally — leave it as-is.
- **Assertions**: `FluentAssertions` **7.2.0 only** — never v8+ (commercial licence).

## NSubstitute Quick Reference

```csharp
// Create substitute
var sub = Substitute.For<IFoo>();

// Setup return value — constrain input with Arg.Is (preferred)
sub.Method(Arg.Is<Params>(p => p.Id == 1), Arg.Any<CancellationToken>())
   .Returns(expected);

// Verify call
sub.Received(1).Method(Arg.Is<Params>(p => p.Id == 1), Arg.Any<CancellationToken>());
sub.DidNotReceive().Method(Arg.Any<Params>(), Arg.Any<CancellationToken>());
```

## AAA Structure

```csharp
[Fact]
public async Task Handle_WhenValidRequest_ShouldReturnExpectedResult()
{
    // Arrange
    var query = new GetCartQuery { StoreId = 1 };
    var expected = new CartDto { Total = 3 };

    _client.GetCart(Arg.Is<CartParams>(p => p.StoreId == 1), Arg.Any<CancellationToken>())
           .Returns(expected);

    // Act
    var subject = await _sut.Handle(query, TestContext.Current.CancellationToken);

    // Assert
    subject.Should().BeEquivalentTo(expected);
}
```

## Key Rules

- **Name tests**: `{TestAction}_When_{Condition}_Should_{ExpectedBehavior}`
- **Name SUT**: `_sut` (field) or `sut` (local)
- **Name output**: `subject`, `result`, or `actual`
- **Use `Arg.Is<T>(predicate)`** to constrain inputs in setup — avoid `Arg.Do` for capturing
- **Use `BeEquivalentTo`** for object comparisons instead of asserting fields individually
- **Do not use** discard assignments (`_ = await ...`) — assign to `subject`
- **Single Act line** — the `// Act` block should be one statement
- **Run the tests** — load `${CLAUDE_PLUGIN_ROOT}/skills/run-tests/SKILL.md` for the platform-correct command; the final run is a fresh build, never `--no-build`.

## Review Checklist

- [ ] NSubstitute used (not Moq)?
- [ ] Named `{TestAction}_When_{Condition}_Should_{Behavior}`?
- [ ] Variables named `_sut`, `subject`, `expected`, `query`?
- [ ] `// Arrange`, `// Act` (single line), `// Assert` blocks present?
- [ ] `Arg.Is<T>()` used instead of `Arg.Do` captures?
- [ ] `BeEquivalentTo` used for object comparison?
- [ ] No `_ = await` discards?
