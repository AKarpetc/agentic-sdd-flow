namespace Platform.Contracts;

/// <summary>How much of a SKU is on hand right now.</summary>
public sealed record StockView(string Sku, int Quantity);
