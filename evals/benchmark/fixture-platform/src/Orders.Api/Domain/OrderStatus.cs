namespace Orders.Api.Domain;

internal enum OrderStatus
{
    Placed = 0,
    Paid = 1,
    Shipped = 2,
    Cancelled = 3,
}
