namespace Inventory.Api.Domain;

/// <summary>A hold on stock; a released reservation no longer keeps its quantity off the shelf.</summary>
internal sealed record Reservation(string Id, string Sku, int Quantity, bool Released);
