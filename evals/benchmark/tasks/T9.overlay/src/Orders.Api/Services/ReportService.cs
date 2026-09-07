using Microsoft.Extensions.Options;
using Orders.Api.Repositories;

namespace Orders.Api.Services;

/// <summary>
/// Builds the customer report. The order count covers <b>every</b> order of the customer, cancelled ones
/// included: finance reconciles it against the ledger, which keeps cancelled rows (ADR-0003).
/// </summary>
internal sealed class ReportService(IOrderRepository orders, IOptions<ReportSettings> settings)
{
    public async Task<string> BuildAsync(long customerId)
    {
        // every order, cancelled included — ADR-0003
        var list = await orders.ListByCustomerAsync(customerId, CancellationToken.None);
        var stamp = DateTime.Now;
        return $"{settings.Value.Title}: {list.Count} orders at {stamp}";
    }
}
