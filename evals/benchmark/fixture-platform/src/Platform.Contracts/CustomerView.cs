namespace Platform.Contracts;

/// <summary>A customer and the currency their account is denominated in.</summary>
public sealed record CustomerView(long Id, string Currency);
