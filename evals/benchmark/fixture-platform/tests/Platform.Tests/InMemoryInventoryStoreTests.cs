using FluentAssertions;
using Inventory.Api.Storage;

namespace Platform.Tests;

public sealed class InMemoryInventoryStoreTests
{
    [Fact]
    public async Task ReserveAsync_TakesTheQuantityOffTheShelf()
    {
        var store = new InMemoryInventoryStore();

        var reservation = await store.ReserveAsync("SKU-1", 4, CancellationToken.None);

        reservation.Should().NotBeNull();
        (await store.QuantityAsync("SKU-1", CancellationToken.None)).Should().Be(6);
    }

    [Fact]
    public async Task ReserveAsync_RefusesMoreThanIsOnHand()
    {
        var store = new InMemoryInventoryStore();

        var reservation = await store.ReserveAsync("SKU-2", 4, CancellationToken.None);

        reservation.Should().BeNull();
    }

    [Fact]
    public async Task ReleaseAsync_MarksTheReservationReleased()
    {
        var store = new InMemoryInventoryStore();
        var reservation = await store.ReserveAsync("SKU-1", 2, CancellationToken.None);

        var released = await store.ReleaseAsync(reservation!.Id, CancellationToken.None);

        released.Should().BeTrue();
        (await store.FindReservationAsync(reservation.Id, CancellationToken.None))!.Released.Should().BeTrue();
    }
}
