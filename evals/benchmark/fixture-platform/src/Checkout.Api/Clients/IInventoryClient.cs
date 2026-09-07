using Platform.Contracts;

namespace Checkout.Api.Clients;

internal interface IInventoryClient
{
    Task<ReservationAttempt> ReserveAsync(string sku, int quantity, CancellationToken cancellationToken);

    Task ReleaseAsync(string reservationId, CancellationToken cancellationToken);
}
