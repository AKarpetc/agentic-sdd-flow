namespace Platform.Contracts;

/// <summary>The basket sent to pricing for a subtotal, its discounts and a total.</summary>
public sealed record QuoteRequest(IReadOnlyList<QuoteLine> Lines);
