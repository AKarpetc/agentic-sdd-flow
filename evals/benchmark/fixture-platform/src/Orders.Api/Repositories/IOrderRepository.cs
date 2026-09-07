using Orders.Api.Domain;

namespace Orders.Api.Repositories;

internal interface IOrderRepository
{
    Task<Order?> FindAsync(long id, CancellationToken cancellationToken);

    Task<IReadOnlyList<Order>> ListByCustomerAsync(long customerId, CancellationToken cancellationToken);

    Task<Order> AddAsync(long customerId, decimal total, CancellationToken cancellationToken);
}
