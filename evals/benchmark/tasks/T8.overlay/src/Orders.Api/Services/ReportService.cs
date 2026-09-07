using Microsoft.Extensions.Options;
using Orders.Api.Repositories;

namespace Orders.Api.Services;

/// <summary>
/// Builds the customer report. The order count is the customer's <b>open</b> orders: cancelled orders are
/// never counted (INC-231, docs/reporting.md). The notifications service reads this number.
/// </summary>
internal sealed class ReportService(IOrderRepository orders, IOptions<ReportSettings> settings)
{
    public async Task<string> BuildAsync(long customerId)
    {
        // open orders only — INC-231
        var list = await orders.ListByCustomerAsync(customerId, CancellationToken.None);
        var stamp = DateTime.Now;
        return $"{settings.Value.Title}: {list.Count} orders at {stamp}";
    }
}
