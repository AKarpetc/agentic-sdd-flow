namespace Platform.Contracts;

/// <summary>A statement line as it is stored in the ledger.</summary>
public sealed record LedgerEntryView(long Id, long CustomerId, long OrderId, decimal Amount, string Kind);
