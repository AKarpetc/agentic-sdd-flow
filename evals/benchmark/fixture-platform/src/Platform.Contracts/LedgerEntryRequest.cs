namespace Platform.Contracts;

/// <summary>Posts one statement line against a customer for an order.</summary>
public sealed record LedgerEntryRequest(long CustomerId, long OrderId, decimal Amount, string Kind);
