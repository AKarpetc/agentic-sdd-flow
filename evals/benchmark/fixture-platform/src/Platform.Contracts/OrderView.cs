namespace Platform.Contracts;

/// <summary>An order as every other service sees it.</summary>
public sealed record OrderView(long Id, long CustomerId, decimal Total, string Status);
