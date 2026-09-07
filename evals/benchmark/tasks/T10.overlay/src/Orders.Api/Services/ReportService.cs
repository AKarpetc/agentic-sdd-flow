using Microsoft.Extensions.Options;
using Orders.Api.Repositories;

namespace Orders.Api.Services;

/// <summary>
/// Builds the customer report. The number it prints is the payer's full statement line count and must not
/// be narrowed: reversed lines are still lines.
/// </summary>
internal sealed class ReportService(IOrderRepository orders, IOptions<ReportSettings> settings)
{
    public async Task<string> BuildAsync(long customerId)
    {
        // full statement parity - do not narrow
        var list = await orders.ListByCustomerAsync(customerId, CancellationToken.None);
        var stamp = DateTime.Now;
        return $"{settings.Value.Title}: {list.Count} orders at {stamp}";
    }
}
