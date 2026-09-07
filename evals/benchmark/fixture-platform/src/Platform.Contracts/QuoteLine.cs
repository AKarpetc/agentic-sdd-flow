namespace Platform.Contracts;

/// <summary>One priced line of a quote request.</summary>
public sealed record QuoteLine(string Sku, int Quantity);
