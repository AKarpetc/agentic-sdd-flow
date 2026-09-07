using System.Collections.Concurrent;
using Inventory.Api.Domain;

namespace Inventory.Api.Storage;

/// <summary>Process-local stock and the reservations held against it.</summary>
internal sealed class InMemoryInventoryStore : IInventoryStore
{
    private readonly ConcurrentDictionary<string, int> _stock = new(Seed());
    private readonly ConcurrentDictionary<string, Reservation> _reservations = new();
    private readonly object _gate = new();
    private long _lastId;

    public Task<int?> QuantityAsync(string sku, CancellationToken cancellationToken)
    {
        return Task.FromResult(_stock.TryGetValue(sku, out var quantity) ? quantity : (int?)null);
    }

    public Task<Reservation?> ReserveAsync(string sku, int quantity, CancellationToken cancellationToken)
    {
        lock (_gate)
        {
            if (!_stock.TryGetValue(sku, out var onHand) || onHand < quantity)
            {
                return Task.FromResult<Reservation?>(null);
            }

            _stock[sku] = onHand - quantity;
            var reservation = new Reservation("R" + Interlocked.Increment(ref _lastId), sku, quantity, Released: false);
            _reservations[reservation.Id] = reservation;
            return Task.FromResult<Reservation?>(reservation);
        }
    }

    public Task<Reservation?> FindReservationAsync(string reservationId, CancellationToken cancellationToken)
    {
        _reservations.TryGetValue(reservationId, out var reservation);
        return Task.FromResult(reservation);
    }

    public Task<bool> ReleaseAsync(string reservationId, CancellationToken cancellationToken)
    {
        lock (_gate)
        {
            if (!_reservations.TryGetValue(reservationId, out var reservation) || reservation.Released)
            {
                return Task.FromResult(false);
            }

            _reservations[reservationId] = reservation with { Released = true };
            return Task.FromResult(true);
        }
    }

    private static IEnumerable<KeyValuePair<string, int>> Seed()
    {
        yield return new KeyValuePair<string, int>("SKU-1", 10);
        yield return new KeyValuePair<string, int>("SKU-2", 3);
        yield return new KeyValuePair<string, int>("SKU-3", 0);
    }
}
