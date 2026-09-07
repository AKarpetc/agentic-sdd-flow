namespace Platform.Contracts;

/// <summary>The priced basket: subtotal, the discounts that applied in order, and what is owed.</summary>
public sealed record QuoteResult(decimal Subtotal, IReadOnlyList<QuoteDiscount> Discounts, decimal Total);
