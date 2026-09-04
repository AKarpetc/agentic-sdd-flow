---
trigger: always_on
---

# Engineering Principles: .NET & Clean Architecture

## 1. Structural Integrity
* **One File, One Type**: Every class, interface, record, or enum **must** be in its own file. Combining multiple classes in a single file is strictly prohibited.
* **CQRS with `Mediator`**: Use the Command Query Responsibility Segregation (CQRS) pattern. All application logic must be implemented via mediator handlers — never a custom dispatcher.
  * **New code / new services**: use source-generated [`Mediator`](https://github.com/martinothamar/Mediator) (`Mediator.Abstractions` + `Mediator.SourceGenerator`). Handlers implement `ICommandHandler<,>` / `IQueryHandler<,>` and return `ValueTask`.
  * **Existing MediatR services** (the overlay contract lists them, if any): keep MediatR. Do not migrate without an explicit request, and never register both mediators in the same service.
* **Thin Controllers**: Controllers must only serve as entry points. Their sole responsibility is to dispatch a Command or Query and return the result.

## 2. Logic & Error Handling
* **Result Pattern**: Use a functional `Result<T>` pattern for domain and application logic failures (e.g., `NotFound`, `ValidationError`). 
* **No Flow-Control Exceptions**: Do not use `try-catch` blocks for business logic. Reserve exceptions only for unexpected infrastructure failures (e.g., database connection loss).
* **Explicit Validation**: Use `FluentValidation` integrated into the mediator pipeline via a pipeline behavior (`IPipelineBehavior<,>` in both MediatR and `Mediator`) to ensure requests are valid before hitting handlers.

## 3. C# 12+ Coding Standards
* **Modern Collections**: Use collection expressions `[]` instead of `new List<T>()`, `new T[]`, or `Array.Empty<T>()`.
* **Primary Constructors**: Use primary constructors for Dependency Injection in classes and handlers to eliminate boilerplate field assignments.
* **Implicit Typing**: Use `var` when the type is obvious from the right-hand side of the assignment.
* **Immutability**: Use `record` types for DTOs, Commands, and Queries.

## 4. Persistence & Performance
* **Async First**: All I/O-bound operations must be asynchronous. Always pass and honor `CancellationToken`.
* **EF Core Efficiency**:
    * Use `.AsNoTracking()` for read-only Queries.
    * Use Projections (`.Select()`) to avoid fetching unnecessary columns.
    * Avoid N+1 queries by eager loading or projecting directly to DTOs.
* **Pagination**: All endpoints returning collections must implement pagination (e.g., `PageNumber`, `PageSize`).

## 5. Security & Documentation
* **Identity**: Use JWT-based stateless authentication. Apply `[Authorize]` by default and use `[AllowAnonymous]` only where explicitly required.
* **API Documentation**: Maintain Swagger/OpenAPI documentation. Use XML comments on public-facing API models and controllers.
* **Global Exception Handling**: Use a centralized middleware to catch unhandled exceptions and return a standard `ProblemDetails` response.

## 6. Prohibitions (Zero Tolerance)
* ❌ No `.Result` or `.Wait()` on Tasks (prevents thread pool starvation).
* ❌ No business logic inside Controllers or Entity Framework Configurations.
* ❌ No hardcoded strings for configuration; use `IOptions<T>`.
* ❌ No direct use of `DateTime.Now`; use an `IDateTimeProvider` for testability.