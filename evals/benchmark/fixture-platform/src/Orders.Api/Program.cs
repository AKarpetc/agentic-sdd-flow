using Orders.Api.Domain;
using Orders.Api.Repositories;
using Orders.Api.Services;
using Platform.Contracts;

var builder = WebApplication.CreateBuilder(args);
builder.Services.AddProblemDetails();
builder.Services.AddSingleton<IOrderRepository, InMemoryOrderRepository>();
builder.Services.AddSingleton<ICustomerRepository, InMemoryCustomerRepository>();
builder.Services.AddScoped<OrderService>();

var app = builder.Build();

app.MapGet("/", () => "orders-api");

app.MapGet("/api/orders/{id:long}", async (long id, OrderService orders, CancellationToken cancellationToken) =>
{
    var order = await orders.FindAsync(id, cancellationToken);
    return order is null
        ? Results.Problem(title: "Order not found", detail: $"No order with id {id}.", statusCode: StatusCodes.Status404NotFound)
        : Results.Ok(View(order));
});

app.MapPost("/api/orders", async (CreateOrderRequest request, OrderService orders, CancellationToken cancellationToken) =>
{
    var order = await orders.PlaceAsync(request.CustomerId, request.Total, cancellationToken);
    return order is null
        ? Results.Problem(title: "Customer not found", detail: $"No customer with id {request.CustomerId}.", statusCode: StatusCodes.Status404NotFound)
        : Results.Created($"/api/orders/{order.Id}", View(order));
});

app.MapGet("/api/customers/{id:long}", async (long id, OrderService orders, CancellationToken cancellationToken) =>
{
    var customer = await orders.FindCustomerAsync(id, cancellationToken);
    return customer is null
        ? Results.Problem(title: "Customer not found", detail: $"No customer with id {id}.", statusCode: StatusCodes.Status404NotFound)
        : Results.Ok(new CustomerView(customer.Id, customer.Currency));
});

app.MapGet("/api/customers/{id:long}/orders", async (long id, OrderService orders, CancellationToken cancellationToken) =>
{
    var list = await orders.ListByCustomerAsync(id, cancellationToken);
    return Results.Ok(list.Select(View).ToList());
});

app.Run();

static OrderView View(Order order) => new(order.Id, order.CustomerId, order.Total, order.Status.ToString());

