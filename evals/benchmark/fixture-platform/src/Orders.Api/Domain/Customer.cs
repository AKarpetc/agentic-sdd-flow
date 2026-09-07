namespace Orders.Api.Domain;

/// <summary>A customer account; <paramref name="Currency"/> is the currency their statements are kept in.</summary>
internal sealed record Customer(long Id, string Currency);
