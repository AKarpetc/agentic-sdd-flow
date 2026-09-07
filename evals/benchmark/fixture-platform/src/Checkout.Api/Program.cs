using Checkout.Api.Clients;
using Checkout.Api.Services;
using Platform.Contracts;

var builder = WebApplication.CreateBuilder(args);
builder.Services.AddProblemDetails();
builder.Services.AddHttpClient<IInventoryClient, InventoryClient>(client => client.BaseAddress = BaseAddress(builder.Configuration, "Inventory"));
builder.Services.AddHttpClient<IPricingClient, PricingClient>(client => client.BaseAddress = BaseAddress(builder.Configuration, "Pricing"));
builder.Services.AddHttpClient<IOrdersClient, OrdersClient>(client => client.BaseAddress = BaseAddress(builder.Configuration, "Orders"));
builder.Services.AddScoped<CheckoutService>();

var app = builder.Build();

app.MapGet("/", () => "checkout-api");

app.MapPost("/api/checkout", async (CheckoutRequest request, CheckoutService checkout, CancellationToken cancellationToken) =>
{
    var outcome = await checkout.CheckoutAsync(request, cancellationToken);
    return outcome.Failure is null
        ? Results.Ok(outcome.Result)
        : Results.Problem(title: outcome.Failure.Title, detail: outcome.Failure.Detail, statusCode: outcome.Failure.StatusCode);
});

app.Run();

static Uri BaseAddress(IConfiguration configuration, string service)
{
    var url = configuration[$"Services:{service}:BaseUrl"];
    return string.IsNullOrWhiteSpace(url)
        ? throw new InvalidOperationException($"Services:{service}:BaseUrl is not configured.")
        : new Uri(url);
}

