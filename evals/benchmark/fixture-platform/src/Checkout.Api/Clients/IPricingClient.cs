using Platform.Contracts;

namespace Checkout.Api.Clients;

internal interface IPricingClient
{
    Task<QuoteResult?> QuoteAsync(IReadOnlyList<QuoteLine> lines, CancellationToken cancellationToken);
}
