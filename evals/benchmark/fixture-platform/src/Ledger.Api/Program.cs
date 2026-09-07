using Ledger.Api.Configuration;
using Ledger.Api.Domain;
using Ledger.Api.Storage;
using Platform.Contracts;

var builder = WebApplication.CreateBuilder(args);
builder.Services.AddProblemDetails();
builder.Services.Configure<LedgerSettings>(builder.Configuration.GetSection("Ledger"));
builder.Services.AddSingleton<ILedgerStore, LedgerStore>();

var app = builder.Build();

await app.Services.GetRequiredService<ILedgerStore>().MigrateAsync(CancellationToken.None);

app.MapGet("/", () => "ledger-api");

app.MapGet("/api/ledger/{customerId:long}", async (long customerId, ILedgerStore store, CancellationToken cancellationToken) =>
{
    var entries = await store.ListByCustomerAsync(customerId, cancellationToken);
    return Results.Ok(entries.Select(View).ToList());
});

app.MapPost("/api/ledger/entries", async (LedgerEntryRequest request, ILedgerStore store, CancellationToken cancellationToken) =>
{
    if (string.IsNullOrWhiteSpace(request.Kind))
    {
        return Results.Problem(title: "Invalid entry", detail: "kind is required.", statusCode: StatusCodes.Status400BadRequest);
    }

    var entry = await store.AddAsync(request.CustomerId, request.OrderId, request.Amount, request.Kind, cancellationToken);
    return Results.Created($"/api/ledger/{entry.CustomerId}", View(entry));
});

app.Run();

static LedgerEntryView View(LedgerEntry entry) => new(entry.Id, entry.CustomerId, entry.OrderId, entry.Amount, entry.Kind);

