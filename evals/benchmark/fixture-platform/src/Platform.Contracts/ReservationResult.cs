namespace Platform.Contracts;

/// <summary>A hold that inventory granted; the id is what releases it again.</summary>
public sealed record ReservationResult(string ReservationId, string Sku, int Quantity);
