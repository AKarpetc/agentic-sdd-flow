namespace Platform.Contracts;

/// <summary>Creates an order for a customer at an already priced total.</summary>
public sealed record CreateOrderRequest(long CustomerId, decimal Total);
