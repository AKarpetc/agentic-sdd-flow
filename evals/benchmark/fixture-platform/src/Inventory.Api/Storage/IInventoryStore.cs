using Inventory.Api.Domain;

namespace Inventory.Api.Storage;

internal interface IInventoryStore
{
    Task<int?> QuantityAsync(string sku, CancellationToken cancellationToken);

    Task<Reservation?> ReserveAsync(string sku, int quantity, CancellationToken cancellationToken);

    Task<Reservation?> FindReservationAsync(string reservationId, CancellationToken cancellationToken);

    Task<bool> ReleaseAsync(string reservationId, CancellationToken cancellationToken);
}
