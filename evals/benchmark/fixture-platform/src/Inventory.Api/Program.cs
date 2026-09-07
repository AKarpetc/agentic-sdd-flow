using Inventory.Api.Storage;
using Platform.Contracts;

var builder = WebApplication.CreateBuilder(args);
builder.Services.AddProblemDetails();
builder.Services.AddSingleton<IInventoryStore, InMemoryInventoryStore>();

var app = builder.Build();

app.MapGet("/", () => "inventory-api");

app.MapGet("/api/stock/{sku}", async (string sku, IInventoryStore store, CancellationToken cancellationToken) =>
{
    var quantity = await store.QuantityAsync(sku, cancellationToken);
    return quantity is null
        ? Results.Problem(title: "Unknown sku", detail: $"No stock record for sku {sku}.", statusCode: StatusCodes.Status404NotFound)
        : Results.Ok(new StockView(sku, quantity.Value));
});

app.MapPost("/api/reservations", async (ReservationRequest request, IInventoryStore store, CancellationToken cancellationToken) =>
{
    if (request.Quantity <= 0)
    {
        return Results.Problem(title: "Invalid quantity", detail: "quantity must be greater than zero.", statusCode: StatusCodes.Status400BadRequest);
    }

    if (await store.QuantityAsync(request.Sku, cancellationToken) is null)
    {
        return Results.Problem(title: "Unknown sku", detail: $"No stock record for sku {request.Sku}.", statusCode: StatusCodes.Status404NotFound);
    }

    var reservation = await store.ReserveAsync(request.Sku, request.Quantity, cancellationToken);
    return reservation is null
        ? Results.Problem(title: "Insufficient stock", detail: $"Not enough stock of {request.Sku} to reserve {request.Quantity}.", statusCode: StatusCodes.Status409Conflict)
        : Results.Ok(new ReservationResult(reservation.Id, reservation.Sku, reservation.Quantity));
});

app.MapDelete("/api/reservations/{reservationId}", async (string reservationId, IInventoryStore store, CancellationToken cancellationToken) =>
{
    var reservation = await store.FindReservationAsync(reservationId, cancellationToken);
    if (reservation is null)
    {
        return Results.Problem(title: "Unknown reservation", detail: $"No reservation with id {reservationId}.", statusCode: StatusCodes.Status404NotFound);
    }

    await store.ReleaseAsync(reservationId, cancellationToken);
    return Results.NoContent();
});

app.Run();

