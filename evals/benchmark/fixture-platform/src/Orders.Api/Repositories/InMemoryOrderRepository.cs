using System.Collections.Concurrent;
using Orders.Api.Domain;

namespace Orders.Api.Repositories;

/// <summary>Process-local order store seeded with the demo data set; the single source of orders on the platform.</summary>
internal sealed class InMemoryOrderRepository : IOrderRepository
{
    private readonly ConcurrentDictionary<long, Order> _orders = new(Seed().ToDictionary(order => order.Id));
    private long _lastId = 1000;

    public Task<Order?> FindAsync(long id, CancellationToken cancellationToken)
    {
        _orders.TryGetValue(id, out var order);
        return Task.FromResult(order);
    }

    public Task<IReadOnlyList<Order>> ListByCustomerAsync(long customerId, CancellationToken cancellationToken)
    {
        IReadOnlyList<Order> result = _orders.Values
            .Where(order => order.CustomerId == customerId)
            .OrderBy(order => order.Id)
            .ToList();
        return Task.FromResult(result);
    }

    public Task<Order> AddAsync(long customerId, decimal total, CancellationToken cancellationToken)
    {
        var order = new Order(Interlocked.Increment(ref _lastId), customerId, total, OrderStatus.Placed);
        _orders[order.Id] = order;
        return Task.FromResult(order);
    }

    private static IEnumerable<Order> Seed()
    {
        yield return new Order(101, 1, 10.00m, OrderStatus.Placed);
        yield return new Order(102, 1, 20.50m, OrderStatus.Paid);
        yield return new Order(103, 1, 5.00m, OrderStatus.Cancelled);
        yield return new Order(104, 1, 7.25m, OrderStatus.Shipped);
        yield return new Order(201, 2, 100.00m, OrderStatus.Placed);
        yield return new Order(202, 2, 1.00m, OrderStatus.Cancelled);
        yield return new Order(301, 3, 3.00m, OrderStatus.Cancelled);
    }
}
