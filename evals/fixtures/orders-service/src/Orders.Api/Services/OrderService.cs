using Orders.Api.Repositories;

namespace Orders.Api.Services;

/// <summary>Reads orders and computes per-customer totals.</summary>
internal sealed class OrderService
{
    private readonly IOrderRepository _orders;

    public OrderService(IOrderRepository orders)
    {
        _orders = orders;
    }

    public async Task<decimal> TotalForCustomerAsync(long customerId, CancellationToken cancellationToken)
    {
        var orders = await _orders.ListByCustomerAsync(customerId, cancellationToken);
        return orders
            .Where(order => order.Status != OrderStatus.Cancelled)
            .Sum(order => order.Total);
    }

    public async Task<bool> CanCancelAsync(long orderId, CancellationToken cancellationToken)
    {
        var order = await _orders.FindAsync(orderId, cancellationToken);
        return order is not null && order.Status is OrderStatus.Placed or OrderStatus.Paid;
    }
}
