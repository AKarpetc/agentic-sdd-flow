namespace Platform.Contracts;

/// <summary>What a completed checkout produced: the order it created and the stock it holds.</summary>
public sealed record CheckoutResult(long OrderId, decimal Subtotal, decimal Total, IReadOnlyList<string> ReservationIds);
