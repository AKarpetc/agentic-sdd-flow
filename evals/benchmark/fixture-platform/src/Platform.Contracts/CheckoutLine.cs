namespace Platform.Contracts;

/// <summary>One basket line: how much of a single SKU is being bought.</summary>
public sealed record CheckoutLine(string Sku, int Quantity);
