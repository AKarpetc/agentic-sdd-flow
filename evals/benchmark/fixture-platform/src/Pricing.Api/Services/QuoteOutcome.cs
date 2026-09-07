using Platform.Contracts;

namespace Pricing.Api.Services;

/// <summary>Either a priced basket or the first SKU the price list does not know.</summary>
internal sealed record QuoteOutcome(QuoteResult? Quote, string? UnknownSku);
