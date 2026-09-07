namespace Platform.Contracts;

/// <summary>A promotion that applied to a quote and the amount it took off.</summary>
public sealed record QuoteDiscount(string Code, decimal Amount);
