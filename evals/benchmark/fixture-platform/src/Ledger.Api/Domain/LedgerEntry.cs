namespace Ledger.Api.Domain;

/// <summary>One statement line: what a customer was charged for an order.</summary>
internal sealed record LedgerEntry(long Id, long CustomerId, long OrderId, decimal Amount, string Kind);
