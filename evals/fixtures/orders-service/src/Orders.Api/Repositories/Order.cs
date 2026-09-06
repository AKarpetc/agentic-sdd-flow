namespace Orders.Api.Repositories;

public sealed record Order(long Id, long CustomerId, decimal Total, OrderStatus Status);
