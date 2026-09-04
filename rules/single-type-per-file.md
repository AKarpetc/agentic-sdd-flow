---
trigger: always_on
---

# Rule: Single Type Per File

## Definition
To ensure maintainability, clean Git history, and alignment with C# best practices, every top-level type must have its own physical file.

## Constraints
* **Type Isolation:** Each `class`, `interface`, `record`, and `enum` MUST be defined in its own separate `.cs` file.
* **Filename Parity:** The filename must match the name of the type exactly (e.g., `ISettingsRepository` → `ISettingsRepository.cs`).
* **No Grouping:** Do not group multiple interfaces or DTOs into a single "Models.cs" or "Interfaces.cs" file.
* **File-Scoped Namespaces:** Use file-scoped namespaces (e.g., `namespace MyProject.Data;`) to keep the files clean and reduce nesting levels.

## Agent Instructions
1. **Validation:** Before finalizing a code generation task, check if the output contains more than one type definition.
2. **Action:** If multiple types are detected, split the response into separate code blocks, each clearly labeled with its respective filename.
3. **Refactoring:** If existing code is provided with multiple types in one block, the default action is to propose a refactor that splits them into individual files.

## Example
**Incorrect:**
```csharp
// Services.cs
public interface IAuthService { ... }
public interface ITokenService { ... }