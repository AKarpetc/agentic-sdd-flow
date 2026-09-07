namespace Orders.Api.Domain;

/// <summary>An order and the money it is worth, in the platform's single currency.</summary>
internal sealed record Order(long Id, long CustomerId, decimal Total, OrderStatus Status);
