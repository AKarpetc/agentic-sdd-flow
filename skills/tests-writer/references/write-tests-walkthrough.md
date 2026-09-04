---
name: write-tests
description: Step-by-step workflow for adding tests to cover changes in a project. Use after implementing a feature or when asked to cover existing code with tests.
---
# Write Tests Workflow

## Steps

1. **Identify what changed**
   - Run `git log --oneline -5` to find the last commit(s)
   - Run `git show <hash> --stat` to see affected files
   - Run `git show <hash> -- "*.cs"` to read the diff

2. **Understand the change**
   - Read each changed source file in full
   - Identify: new classes, new methods, changed signatures, new enum values, new mappings

3. **Locate existing tests**
   - Find the relevant test project(s) (`tests/` directory)
   - Read existing test files for the affected code to understand patterns in use

4. **Plan test cases**
   For each changed unit, define:
   - Happy path(s)
   - Edge cases / boundary values
   - Error / null cases where applicable

5. **Write tests**
   Follow [test-convention.md](../../../rules/test-convention.md) and the [tests-writer skill](../SKILL.md):
   - Use **NSubstitute** for mocking (never Moq)
   - Use **xUnit** (`[Fact]`, `[Theory]`, `[InlineData]`)
   - Use **FluentAssertions** (`BeEquivalentTo`, `Should().Be(...)`)
   - Structure with `// Arrange`, `// Act` (single line), `// Assert`
   - Name: `{TestAction}_When_{Condition}_Should_{ExpectedBehavior}`

6. **Build & run**
   ```bash
   dotnet build <test-project>.csproj
   dotnet test <test-project>.csproj --filter "<TestClassName>"
   ```

7. **Verify all green** — fix any compilation errors or failures before finishing
