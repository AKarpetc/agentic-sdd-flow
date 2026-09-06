using Orders.Api.Repositories;
using Orders.Api.Services;

var builder = WebApplication.CreateBuilder(args);
builder.Services.AddSingleton<IOrderRepository, InMemoryOrderRepository>();
builder.Services.AddScoped<OrderService>();

var app = builder.Build();

app.MapGet("/", () => "orders-api");
app.MapGet("/api/orders/{id:long}", async (long id, IOrderRepository orders, CancellationToken cancellationToken) =>
{
    var order = await orders.FindAsync(id, cancellationToken);
    return order is null
        ? Results.NotFound()
        : Results.Ok(new { id = order.Id, customerId = order.CustomerId, total = order.Total, status = order.Status.ToString() });
});

app.Run();

/// <summary>Exposed so integration tests can host the API in-process.</summary>
public partial class Program
{
}
