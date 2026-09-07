using Checkout.Api.Clients;
using Checkout.Api.Services;
using FluentAssertions;
using NSubstitute;
using Platform.Contracts;

namespace Platform.Tests;

public sealed class CheckoutServiceTests
{
    private readonly IInventoryClient _inventory = Substitute.For<IInventoryClient>();
    private readonly IPricingClient _pricing = Substitute.For<IPricingClient>();
    private readonly IOrdersClient _orders = Substitute.For<IOrdersClient>();

    [Fact]
    public async Task CheckoutAsync_ReturnsTheOrderItCreated()
    {
        _orders.FindCustomerAsync(1, Arg.Any<CancellationToken>()).Returns(new CustomerView(1, "USD"));
        _inventory.ReserveAsync("SKU-1", 2, Arg.Any<CancellationToken>())
            .Returns(new ReservationAttempt(new ReservationResult("R1", "SKU-1", 2), 200));
        _pricing.QuoteAsync(Arg.Any<IReadOnlyList<QuoteLine>>(), Arg.Any<CancellationToken>())
            .Returns(new QuoteResult(20.00m, [new QuoteDiscount("PCT10", 2.00m)], 18.00m));
        _orders.CreateAsync(1, 18.00m, Arg.Any<CancellationToken>()).Returns(new OrderView(1001, 1, 18.00m, "Placed"));

        var outcome = await Service().CheckoutAsync(Request(), CancellationToken.None);

        outcome.Failure.Should().BeNull();
        outcome.Result.Should().BeEquivalentTo(new CheckoutResult(1001, 20.00m, 18.00m, ["R1"]));
    }

    [Fact]
    public async Task CheckoutAsync_ReleasesWhatItHeld_WhenALaterLineIsShort()
    {
        _orders.FindCustomerAsync(1, Arg.Any<CancellationToken>()).Returns(new CustomerView(1, "USD"));
        _inventory.ReserveAsync("SKU-1", 2, Arg.Any<CancellationToken>())
            .Returns(new ReservationAttempt(new ReservationResult("R1", "SKU-1", 2), 200));
        _inventory.ReserveAsync("SKU-2", 9, Arg.Any<CancellationToken>())
            .Returns(new ReservationAttempt(null, 409));

        var request = new CheckoutRequest(1, "req-1", [new CheckoutLine("SKU-1", 2), new CheckoutLine("SKU-2", 9)]);
        var outcome = await Service().CheckoutAsync(request, CancellationToken.None);

        outcome.Failure!.StatusCode.Should().Be(409);
        await _inventory.Received(1).ReleaseAsync("R1", Arg.Any<CancellationToken>());
    }

    private static CheckoutRequest Request()
    {
        return new CheckoutRequest(1, "req-1", [new CheckoutLine("SKU-1", 2)]);
    }

    private CheckoutService Service()
    {
        return new CheckoutService(_inventory, _pricing, _orders);
    }
}
