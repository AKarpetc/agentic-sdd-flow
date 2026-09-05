# Common Infrastructure

> Copy-paste implementations for infrastructure types that skills reference. Add these to your `Shared` or `Common` project and register them in `Program.cs`.

## Result Pattern

Use `Result` / `Result<T>` from **CSharpFunctionalExtensions** (`Result.Success(value)`, `Result.Failure<T>(error)`, `IsSuccess`/`IsFailure`, `Value`, `Error`) — the conventions and the test rules key on that API. Do not hand-roll a Result type; add the package if a project lacks it and the brief allows a new package, otherwise report the gap.

## Result to ProblemDetails Extension

```csharp
// ResultExtensions.cs
public static class ResultExtensions
{
    public static IResult ToProblemDetails(this Result result, int statusCode = 400)
    {
        return TypedResults.Problem(
            title: "One or more errors occurred",
            detail: result.Error,
            statusCode: statusCode);
    }
}
```

`result.Error` is a `string` for a plain `Result`/`Result<T>`; a domain type that wraps a typed error (e.g. `Result<T, TError>` or a custom `AppError`) maps the same way — pass its message to `detail` and, where the caller needs to branch on error kind, switch on the error's type before calling `TypedResults.Problem`.

## Validation Endpoint Filter

Generic FluentValidation filter for minimal API endpoints.

```csharp
// ValidationFilter.cs
public sealed class ValidationFilter<TRequest> : IEndpointFilter
{
    public async ValueTask<object?> InvokeAsync(
        EndpointFilterInvocationContext context,
        EndpointFilterDelegate next)
    {
        var validator = context.HttpContext.RequestServices.GetService<IValidator<TRequest>>();
        if (validator is null)
            return await next(context);

        var request = context.Arguments.OfType<TRequest>().FirstOrDefault();
        if (request is null)
            return await next(context);

        var validationResult = await validator.ValidateAsync(request);
        if (!validationResult.IsValid)
        {
            return TypedResults.ValidationProblem(validationResult.ToDictionary());
        }

        return await next(context);
    }
}

// Usage on an endpoint
group.MapPost("/", CreateOrder)
    .AddEndpointFilter<ValidationFilter<CreateOrderRequest>>();
```

## Global Exception Handler

Modern `IExceptionHandler` implementation (preferred over inline `UseExceptionHandler` lambda).

```csharp
// GlobalExceptionHandler.cs
public sealed class GlobalExceptionHandler(
    ILogger<GlobalExceptionHandler> logger,
    IHostEnvironment env) : IExceptionHandler
{
    public async ValueTask<bool> TryHandleAsync(
        HttpContext context,
        Exception exception,
        CancellationToken ct)
    {
        logger.LogError(exception, "Unhandled exception for {Method} {Path}",
            context.Request.Method, context.Request.Path);

        var problem = new ProblemDetails
        {
            Title = "An unexpected error occurred",
            Status = StatusCodes.Status500InternalServerError,
            Type = "https://tools.ietf.org/html/rfc9110#section-15.6.1"
        };

        if (env.IsDevelopment())
        {
            problem.Detail = exception.Message;
        }

        context.Response.StatusCode = problem.Status.Value;
        await context.Response.WriteAsJsonAsync(problem, ct);
        return true;
    }
}
```

## IEndpointGroup + Auto-Discovery

```csharp
// IEndpointGroup.cs
public interface IEndpointGroup
{
    void Map(IEndpointRouteBuilder app);
}

// EndpointExtensions.cs
public static class EndpointExtensions
{
    public static IEndpointRouteBuilder MapEndpoints(
        this IEndpointRouteBuilder app,
        params Assembly[] assemblies)
    {
        var targetAssemblies = assemblies.Length > 0
            ? assemblies
            : [Assembly.GetCallingAssembly()];

        var endpointGroups = targetAssemblies
            .SelectMany(a => a.GetTypes())
            .Where(t => t is { IsAbstract: false, IsInterface: false }
                && typeof(IEndpointGroup).IsAssignableFrom(t));

        foreach (var type in endpointGroups)
        {
            var group = (IEndpointGroup)Activator.CreateInstance(type)!;
            group.Map(app);
        }

        return app;
    }
}

// Program.cs — one-time registration
app.MapEndpoints();

// Per-feature endpoint group — auto-discovered
public sealed class OrderEndpoints : IEndpointGroup
{
    public void Map(IEndpointRouteBuilder app)
    {
        var group = app.MapGroup("/api/orders").WithTags("Orders");
        group.MapGet("/", ListOrders);
        group.MapPost("/", CreateOrder).AddEndpointFilter<ValidationFilter<CreateOrderRequest>>();
    }
}
```

## Pagination

```csharp
// PaginationQuery.cs
public sealed record PaginationQuery(int Page = 1, int PageSize = 20)
{
    public int Skip => (Page - 1) * PageSize;
}

// PagedList.cs
public sealed record PagedList<T>(
    List<T> Items,
    int TotalCount,
    int Page,
    int PageSize)
{
    public int TotalPages => (int)Math.Ceiling(TotalCount / (double)PageSize);
    public bool HasPrevious => Page > 1;
    public bool HasNext => Page < TotalPages;

    public static async Task<PagedList<T>> CreateAsync(
        IQueryable<T> query, PaginationQuery pagination, CancellationToken ct)
    {
        var totalCount = await query.CountAsync(ct);
        var items = await query
            .Skip(pagination.Skip)
            .Take(pagination.PageSize)
            .ToListAsync(ct);

        return new PagedList<T>(items, totalCount, pagination.Page, pagination.PageSize);
    }
}
```

## Quick Setup Checklist

Register everything in `Program.cs`:

```csharp
// Services
builder.Services.AddProblemDetails();
builder.Services.AddExceptionHandler<GlobalExceptionHandler>();
builder.Services.AddValidatorsFromAssemblyContaining<Program>();

// Middleware (order matters)
app.UseExceptionHandler();
app.UseHttpsRedirection();

// Endpoints
app.MapEndpoints();
```

Required NuGet packages:

```bash
dotnet add package FluentValidation.DependencyInjectionExtensions
```
