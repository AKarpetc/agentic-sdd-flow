using Pricing.Api.Configuration;
using Pricing.Api.Services;
using Platform.Contracts;

var builder = WebApplication.CreateBuilder(args);
builder.Services.AddProblemDetails();
builder.Services.Configure<PricingSettings>(builder.Configuration.GetSection("Pricing"));
builder.Services.AddScoped<PricingService>();

var app = builder.Build();

app.MapGet("/", () => "pricing-api");

app.MapPost("/api/pricing/quote", (QuoteRequest request, PricingService pricing) =>
{
    if (request.Lines.Count == 0)
    {
        return Results.Problem(title: "Empty basket", detail: "lines must contain at least one line.", statusCode: StatusCodes.Status400BadRequest);
    }

    var outcome = pricing.Quote(request);
    return outcome.Quote is null
        ? Results.Problem(title: "Unknown sku", detail: $"No price for sku {outcome.UnknownSku}.", statusCode: StatusCodes.Status400BadRequest)
        : Results.Ok(outcome.Quote);
});

app.Run();

