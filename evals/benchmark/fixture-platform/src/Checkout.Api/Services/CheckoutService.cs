using Checkout.Api.Clients;
using Platform.Contracts;

namespace Checkout.Api.Services;

/// <summary>Runs one checkout across inventory, pricing and orders, releasing what it holds when a step fails.</summary>
internal sealed class CheckoutService
{
    private readonly IInventoryClient _inventory;
    private readonly IPricingClient _pricing;
    private readonly IOrdersClient _orders;

    public CheckoutService(IInventoryClient inventory, IPricingClient pricing, IOrdersClient orders)
    {
        _inventory = inventory;
        _pricing = pricing;
        _orders = orders;
    }

    public async Task<CheckoutOutcome> CheckoutAsync(CheckoutRequest request, CancellationToken cancellationToken)
    {
        if (request.Lines.Count == 0)
        {
            return Failed(new CheckoutFailure(StatusCodes.Status400BadRequest, "Empty basket", "lines must contain at least one line."));
        }

        var customer = await _orders.FindCustomerAsync(request.CustomerId, cancellationToken);
        if (customer is null)
        {
            return Failed(new CheckoutFailure(StatusCodes.Status404NotFound, "Customer not found", $"No customer with id {request.CustomerId}."));
        }

        var held = new List<string>();
        foreach (var line in request.Lines)
        {
            var attempt = await _inventory.ReserveAsync(line.Sku, line.Quantity, cancellationToken);
            if (attempt.Reservation is null)
            {
                await ReleaseAsync(held, cancellationToken);
                return Failed(ReservationFailure(line, attempt.StatusCode));
            }

            held.Add(attempt.Reservation.ReservationId);
        }

        var quote = await _pricing.QuoteAsync(request.Lines.Select(line => new QuoteLine(line.Sku, line.Quantity)).ToList(), cancellationToken);
        if (quote is null)
        {
            await ReleaseAsync(held, cancellationToken);
            return Failed(new CheckoutFailure(StatusCodes.Status400BadRequest, "Basket cannot be priced", "Pricing refused the basket."));
        }

        var order = await _orders.CreateAsync(request.CustomerId, quote.Total, cancellationToken);
        if (order is null)
        {
            await ReleaseAsync(held, cancellationToken);
            return Failed(new CheckoutFailure(StatusCodes.Status502BadGateway, "Order not created", "Orders refused the checkout."));
        }

        return new CheckoutOutcome(new CheckoutResult(order.Id, quote.Subtotal, quote.Total, held), null);
    }

    private static CheckoutFailure ReservationFailure(CheckoutLine line, int statusCode)
    {
        return statusCode == StatusCodes.Status404NotFound
            ? new CheckoutFailure(StatusCodes.Status400BadRequest, "Unknown sku", $"No stock record for sku {line.Sku}.")
            : new CheckoutFailure(StatusCodes.Status409Conflict, "Insufficient stock", $"Not enough stock of {line.Sku} to reserve {line.Quantity}.");
    }

    private static CheckoutOutcome Failed(CheckoutFailure failure)
    {
        return new CheckoutOutcome(null, failure);
    }

    private async Task ReleaseAsync(IReadOnlyList<string> reservationIds, CancellationToken cancellationToken)
    {
        foreach (var reservationId in reservationIds)
        {
            await _inventory.ReleaseAsync(reservationId, cancellationToken);
        }
    }
}
