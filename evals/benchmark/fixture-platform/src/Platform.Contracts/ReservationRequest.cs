namespace Platform.Contracts;

/// <summary>Asks inventory to hold a quantity of one SKU.</summary>
public sealed record ReservationRequest(string Sku, int Quantity);
