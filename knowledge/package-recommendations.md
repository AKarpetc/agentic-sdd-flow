# Vetted NuGet Package Recommendations

> Last updated: 2026-07-22 -- .NET 10 / C# 14 (versions verified against NuGet.org)

Curated packages that dotnet-claude-kit recommends by default. Every entry includes rationale and guidance on when NOT to use it.

## CRITICAL: Always Use Latest Stable Versions

**Never rely on version numbers from training data or memory.** They are likely outdated. When adding a package:

1. **Preferred:** Run `dotnet add package <name>` without `--version` — NuGet resolves the latest stable automatically
2. **If specifying version:** Verify against NuGet.org or `dotnet package search <name>` first
3. **Microsoft packages for .NET 10:** Always use 10.x (e.g., `Microsoft.EntityFrameworkCore` 10.x, not 9.x)
4. **Third-party packages:** Use the latest stable release that targets .NET 10 / netstandard2.0+

The version ranges below (e.g., "13.x") indicate the **minimum recommended major version**, not the exact version to use. Always default to the latest stable release within that major.

---

## Web Framework

### ASP.NET Core (built-in)

- **Package:** `Microsoft.NET.Sdk.Web` (SDK, no extra NuGet needed)
- **Rationale:** First-party, minimal API and controller support, built-in OpenAPI via `AddOpenApi()`, endpoint filters, route groups, and native AOT compatibility. No third-party web framework competes in the .NET ecosystem.
- **When NOT to use:** If you are building a pure library, worker service, or console app that has no HTTP surface. Use `Microsoft.NET.Sdk` or `Microsoft.NET.Sdk.Worker` instead.

---

## Mediator / In-Process Messaging

### Mediator (Recommended Default)

- **Package:** `Mediator.Abstractions` + `Mediator.SourceGenerator` (3.x)
- **License:** MIT (free, no commercial restrictions)
- **Rationale:** Source-generated mediator with a near-identical API to MediatR (`IRequest<T>`, `IRequestHandler<T,R>`, `IPipelineBehavior<T,R>`, `ISender`). No reflection, Native AOT compatible, and significantly faster than MediatR in benchmarks. Registration: `services.AddMediator()`. 5M+ NuGet downloads, actively maintained.
- **When NOT to use:** If your application has fewer than 5 features and the indirection adds complexity without benefit. If you need message durability or distributed messaging — use Wolverine instead. If you want the absolute simplest approach, use raw handler classes injected directly.

### Wolverine

- **Package:** `WolverineFx` (6.x)
- **License:** MIT (free, no commercial restrictions)
- **Rationale:** Combines mediator + messaging in one library. Built-in outbox, saga support, and direct integration with RabbitMQ/Azure Service Bus. Convention-based handlers (no interfaces). Good choice if you want a single library for both in-process and distributed messaging, avoiding the need for a separate MassTransit dependency.
- **v6 note:** Wolverine 6 changed runtime defaults, removed deprecated APIs, and moved namespaces. Migrating from 5.x? Use `RestoreV5Defaults()` at the top of the `UseWolverine` lambda to adopt the 6.x API without the new defaults. See the [migration guide](https://wolverinefx.net/guide/migration).
- **When NOT to use:** If you only need a simple in-process mediator without messaging (use Mediator instead). If your team prefers explicit interfaces over convention-based discovery.

### MediatR (Commercial License)

- **Package:** `MediatR` (14.x)
- **License:** Lucky Penny Software dual license since v13: RPL-1.5 (copyleft, free if you accept reciprocal obligations) or paid commercial. **Most commercial teams need a paid license** (activated via `MEDIATR_LICENSE_KEY` / `LUCKYPENNY_LICENSE_KEY`). Versions ≤12.x remain MIT but are unsupported.
- **Rationale:** The most widely adopted mediator in .NET with the largest community. v14 adds .NET 10 support. Excellent pipeline behavior support. Consider only if your organization already has a MediatR commercial license.
- **When NOT to use:** For new projects — use `Mediator` (source-generated, MIT, faster) or Wolverine instead. The commercial license adds cost without technical advantage over the MIT alternatives.

---

## Validation

### FluentValidation

- **Package:** `FluentValidation` (12.x), `FluentValidation.DependencyInjectionExtensions`
- **Rationale:** Expressive, testable validation rules. Integrates cleanly with Mediator/MediatR pipeline behaviors. Keeps validation logic out of endpoint/controller code. Supports async rules for database-dependent validation.
- **When NOT to use:** For trivial DTOs where `System.ComponentModel.DataAnnotations` or minimal API binding validation is sufficient. If you are using Blazor EditForm with DataAnnotations and do not need server-side revalidation. If you want to minimize dependencies in a small microservice.

---

## ORM / Data Access

### Entity Framework Core

- **Package:** `Microsoft.EntityFrameworkCore` (10.x), provider package (e.g., `Microsoft.EntityFrameworkCore.SqlServer`, `Npgsql.EntityFrameworkCore.PostgreSQL`)
- **Rationale:** First-party ORM with LINQ-to-SQL translation, migrations, change tracking, interceptors, and deep ASP.NET Core integration. Best productivity-to-performance ratio for most applications. See ADR-003.
- **When NOT to use:** For read-heavy reporting dashboards where raw SQL or Dapper gives simpler, faster queries. For bulk insert/update scenarios (use EF Core bulk extensions or raw SQL). If your database is not relational (use the appropriate NoSQL SDK). If you are writing a performance-critical hot path measured in microseconds.

---

## Logging & Observability

### Serilog

- **Package:** `Serilog.AspNetCore`, `Serilog.Sinks.Console`, plus sink packages as needed
- **Rationale:** The gold standard for structured logging in .NET. Rich sink ecosystem (Seq, Elasticsearch, Application Insights, file, console). Enrichers for correlation IDs, machine name, and more. `LogContext` for scoped properties.
- **When NOT to use:** If the built-in `Microsoft.Extensions.Logging` with a simple console/debug provider meets your needs (e.g., small CLI tools). If your organization mandates a specific logging framework.

### OpenTelemetry

- **Package:** `OpenTelemetry.Extensions.Hosting`, `OpenTelemetry.Instrumentation.AspNetCore`, `OpenTelemetry.Instrumentation.Http`, `OpenTelemetry.Exporter.Otlp`
- **Rationale:** Vendor-neutral standard for distributed traces, metrics, and logs. First-class .NET support. Exports to Jaeger, Zipkin, Prometheus, Grafana, Azure Monitor, AWS X-Ray, and more. Essential for microservices and modular monoliths.
- **When NOT to use:** For a single small API where Serilog structured logs are sufficient. If your entire stack is Azure and you prefer Application Insights SDK directly (though OTel can export to App Insights too).

---

## Testing

### xUnit v3

- **Package:** `xunit.v3` (3.x)
- **Rationale:** The default test framework for .NET. v3 brings a new architecture with improved parallel execution, `IAsyncLifetime` improvements, and better diagnostics. Used by the .NET team itself.
- **When NOT to use:** If your team has an existing large NUnit or MSTest suite and migration cost outweighs benefits.

### Assertions (Kit-Wide Stance)

- **Default:** xUnit built-in `Assert` — zero extra dependencies, zero licensing risk.
- **FluentAssertions is commercial from v8.** v8+ requires a paid Xceed license for commercial use; v7 remains Apache 2.0 but is frozen. Do not add FluentAssertions v8+ to a commercial project without procurement approval.
- **If you want fluent syntax (MIT/Apache alternatives):**
  - `Shouldly` (4.x) — clean `value.ShouldBe(expected)` syntax, long-established, BSD-licensed.
  - `AwesomeAssertions` — community fork of FluentAssertions v7 under Apache 2.0. API-compatible with FA, so migration from FA v7 is near zero cost.
- **When NOT to switch:** An existing suite locked on FluentAssertions v7 can stay there indefinitely — v7's license does not expire.

### Testcontainers

- **Package:** `Testcontainers` (4.x), plus module packages (e.g., `Testcontainers.PostgreSql`, `Testcontainers.MsSql`)
- **Rationale:** Spin up real databases, message brokers, and other infrastructure in Docker for integration tests. No more shared test databases or mocking infrastructure. Deterministic, isolated, CI-friendly.
- **When NOT to use:** In CI environments without Docker support. For pure unit tests where an in-memory provider or mock is faster and sufficient. If test execution time is critical and container startup latency (even a few seconds) is unacceptable.

### Verify

- **Package:** `Verify.Xunit` (or `Verify.NUnit`, `Verify.MSTest`)
- **Rationale:** Snapshot testing for complex objects, HTTP responses, and rendered output. Eliminates brittle assertion chains for large response payloads. Git-diffable `.verified.` files make reviewing changes easy.
- **When NOT to use:** For simple equality assertions where `Assert.Equal` is clearer. When the output changes frequently and snapshot maintenance becomes a burden.

### WireMock.Net

- **Package:** `WireMock.Net` (2.x)
- **Rationale:** HTTP mock server for integration tests. Simulate external API responses, latency, and failures. Useful for testing resilience policies and HTTP client behavior without hitting real services.
- **When NOT to use:** When a simple `DelegatingHandler` or `HttpMessageHandler` mock is sufficient. For testing internal service-to-service calls in the same process (use `WebApplicationFactory` instead).

### FakeTimeProvider

- **Package:** `Microsoft.Extensions.TimeProvider.Testing` (10.x)
- **Rationale:** Official test double for `TimeProvider`. Control time in tests: advance, freeze, set specific moments. Essential for testing time-dependent logic (expiration, scheduling, rate limiting).
- **When NOT to use:** When your code does not depend on time. When you are already using `TimeProvider` only in a trivial way that does not require manipulation in tests.

---

## Messaging / Event Bus

### Wolverine (Recommended Default)

- **Package:** `WolverineFx` (6.x), transport packages (e.g., `WolverineFx.RabbitMQ`, `WolverineFx.AzureServiceBus`)
- **License:** MIT (free, no commercial restrictions)
- **Rationale:** Modern message bus with built-in outbox, saga support, and direct integration with RabbitMQ/Azure Service Bus. Also doubles as an in-process mediator, letting you use a single library for both. Transport-agnostic, convention-based handlers, and source-generated dispatch for high performance. If you already use Wolverine as your mediator, this is the natural choice for messaging too.
- **v6 note:** v6 changed defaults, removed APIs, and moved namespaces — use `RestoreV5Defaults()` when upgrading from 5.x without adopting new runtime defaults ([migration guide](https://wolverinefx.net/guide/migration)).
- **When NOT to use:** For very simple queue consumption where the raw Azure SDK or RabbitMQ client is sufficient. If your team is heavily invested in MassTransit patterns (state machines, consumer definitions) and migration cost is not justified.

### MassTransit (Commercial License from v9)

- **Package:** `MassTransit` (9.x, current 9.1.x), transport packages (e.g., `MassTransit.RabbitMQ`, `MassTransit.Azure.ServiceBus.Core`)
- **License:** **v9 is released and requires a commercial license** (tiered pricing, no per-seat limits). v8 remains Apache 2.0 with security patches through end of 2026, after which it is end-of-life.
- **Rationale:** The most mature message bus abstraction for .NET. Transactional outbox, sagas, state machines, retry policies, and dead-letter handling built in. Excellent Aspire integration. Consider if your organization already has a MassTransit license or is on v8 and plans to stay.
- **When NOT to use:** For new projects — use Wolverine instead (MIT, similar capabilities). If you are using Wolverine for both mediator and messaging (avoid two overlapping abstractions). If you only need simple in-process pub/sub.

---

## Caching

### HybridCache (built-in)

- **Package:** `Microsoft.Extensions.Caching.Hybrid` (ships with .NET 10, GA)
- **Rationale:** Unified L1 (in-memory) + L2 (distributed) cache with stampede protection, tag-based invalidation, and automatic serialization. Replaces manual `IDistributedCache` patterns that are error-prone. See ADR-004.
- **When NOT to use:** If you only need simple in-memory caching with `IMemoryCache` and have no distributed cache. If you need fine-grained control over cache behavior that HybridCache does not expose.

### StackExchange.Redis

- **Package:** `StackExchange.Redis` (3.x), `Microsoft.Extensions.Caching.StackExchangeRedis`
- **Rationale:** The standard Redis client for .NET. Backs `IDistributedCache` and HybridCache L2. High performance, connection multiplexing, Lua scripting support.
- **When NOT to use:** If you are not using Redis. If your caching needs are purely in-memory.

---

## API Versioning

### Asp.Versioning

- **Package:** `Asp.Versioning.Http` (for minimal APIs), `Asp.Versioning.Mvc` (for controllers)
- **Rationale:** The official Microsoft-endorsed API versioning library (successor to `Microsoft.AspNetCore.Mvc.Versioning`). Supports URL segment, query string, header, and media type versioning. Integrates with OpenAPI document generation.
- **When NOT to use:** If your API is internal-only with a single consumer and versioning adds unnecessary complexity. If you prefer a manual URL prefix approach (e.g., `/api/v1/`, `/api/v2/`) without library support.

---

## Resilience

### Polly v8

- **Package:** `Microsoft.Extensions.Http.Resilience` (wraps Polly v8), or `Polly.Core` directly
- **Rationale:** The standard resilience library for .NET. v8 introduces resilience pipelines (replacing the older policy API). Built-in strategies: retry, circuit breaker, timeout, rate limiter, hedging. Integrates with `IHttpClientFactory` via `AddStandardResilienceHandler()`.
- **When NOT to use:** For internal service calls within the same process. If your only need is a simple retry that `Polly.Core` could handle without the full HTTP resilience stack. If you are using Wolverine or MassTransit, which have their own built-in retry and circuit breaker mechanisms.

---

## Docker / Containers

### Built-in .NET Container Support

- **Package:** `Microsoft.NET.Build.Containers` (included in .NET SDK 8+)
- **Rationale:** Publish container images directly with `dotnet publish` -- no Dockerfile needed. Produces optimized, non-root images. Supports `PublishProfile=DefaultContainer`, custom base images, and multi-arch builds.
- **When NOT to use:** When you need multi-stage builds with non-.NET build steps (e.g., npm for a SPA frontend). When you need precise Dockerfile control for compliance or security scanning tools that require a Dockerfile. When your CI pipeline already has a mature Dockerfile-based workflow.

---

## Aspire

### Aspire (13.x)

- **Package:** `Aspire.Hosting.AppHost` (the AppHost orchestrator), plus integration packages (e.g., `Aspire.Npgsql.EntityFrameworkCore.PostgreSQL`). ServiceDefaults is a project template that Aspire tooling generates, not a NuGet package.
- **Rationale:** Orchestration, service discovery, health checks, and telemetry for cloud-native apps. Dashboard for local development. Simplifies configuration of databases, caches, and message brokers.
- **Aspire 13 changes:** Rebranded from ".NET Aspire" to polyglot **Aspire** ([aspire.dev](https://aspire.dev)) with first-class Python and JavaScript/TypeScript support alongside .NET. The `aspire` CLI is now the primary interface (purpose-built for AI coding agents: detached mode, structured output, health-check blocking). Single-file AppHosts are supported — no project file needed, package references via `#:package` directives.
- **When NOT to use:** For single-project applications with no external dependencies. If your deployment target does not support container orchestration. If you are deploying to a platform with its own service mesh and discovery (and Aspire adds duplication).

---

## Object Mapping

### Manual Mapping (Recommended Default)

- **Package:** none
- **Rationale:** For DTOs, an explicit `static OrderDto ToDto(this Order order)` extension or record constructor is transparent, refactor-safe, and debuggable. Most projects have too few mappings to justify a library.

### Mapperly

- **Package:** `Riok.Mapperly` (4.x)
- **License:** Apache 2.0 (free, no commercial restrictions)
- **Rationale:** Source-generated mapper — compile-time generated code, no reflection, Native AOT compatible, and you can read the generated mapping in the IDE. The best library choice when mapping volume makes manual mapping tedious.
- **When NOT to use:** When mappings are few and manual code is clearer.

### AutoMapper (Commercial License)

- **Package:** `AutoMapper` (16.x)
- **License:** Lucky Penny Software dual license since v15: RPL-1.5 or paid commercial (`LUCKYPENNY_LICENSE_KEY`). Versions ≤14.x remain MIT but are unsupported.
- **Recommendation:** Do not add to new projects. Use manual mapping or Mapperly. Consider only if your organization already holds a Lucky Penny license.

---

## DI Extras

### Scrutor

- **Package:** `Scrutor` (7.x)
- **Rationale:** Assembly scanning and decoration for `Microsoft.Extensions.DependencyInjection`. Register all implementations of an interface with a single call. Decorator pattern support without manual wrapper classes.
- **When NOT to use:** For small projects with fewer than 10 services where explicit registration is clearer. If you are using a full DI container (Autofac, Lamar) that already has scanning and decoration built in.

---

## HTTP Client Generation

### Refit

- **Package:** `Refit` (13.x), `Refit.HttpClientFactory`
- **Rationale:** Define HTTP clients as interfaces with attributes. Source-generated at compile time (no runtime reflection). Integrates with `IHttpClientFactory` for proper `HttpClient` lifecycle. Reduces boilerplate for typed HTTP clients.
- **When NOT to use:** For a single HTTP call where a manually configured `HttpClient` is simpler. If the external API provides its own official .NET SDK. If you need full control over request/response serialization that Refit's conventions do not support.
