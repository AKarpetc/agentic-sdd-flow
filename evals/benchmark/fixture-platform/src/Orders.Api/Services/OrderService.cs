using Orders.Api.Domain;
using Orders.Api.Repositories;

namespace Orders.Api.Services;

/// <summary>Reads and creates orders on behalf of the endpoints.</summary>
internal sealed class OrderService
{
    private readonly IOrderRepository _orders;
    private readonly ICustomerRepository _customers;

    public OrderService(IOrderRepository orders, ICustomerRepository customers)
    {
        _orders = orders;
        _customers = customers;
    }

    public Task<Order?> FindAsync(long id, CancellationToken cancellationToken)
    {
        return _orders.FindAsync(id, cancellationToken);
    }

    public Task<IReadOnlyList<Order>> ListByCustomerAsync(long customerId, CancellationToken cancellationToken)
    {
        return _orders.ListByCustomerAsync(customerId, cancellationToken);
    }

    public Task<Customer?> FindCustomerAsync(long customerId, CancellationToken cancellationToken)
    {
        return _customers.FindAsync(customerId, cancellationToken);
    }

    public async Task<Order?> PlaceAsync(long customerId, decimal total, CancellationToken cancellationToken)
    {
        var customer = await _customers.FindAsync(customerId, cancellationToken);
        return customer is null ? null : await _orders.AddAsync(customerId, total, cancellationToken);
    }
}
