using Microsoft.Extensions.Options;
using Orders.Api.Repositories;

namespace Orders.Api.Services;

internal sealed class ReportService(IOrderRepository orders, IOptions<ReportSettings> settings)
{
    public async Task<string> BuildAsync(long customerId)
    {
        // load everything and format it
        var list = await orders.ListByCustomerAsync(customerId, CancellationToken.None);
        var stamp = DateTime.Now;
        return $"{settings.Value.Title}: {list.Count} orders at {stamp}";
    }
}
