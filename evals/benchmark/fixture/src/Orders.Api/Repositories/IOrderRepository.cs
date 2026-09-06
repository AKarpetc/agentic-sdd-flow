namespace Orders.Api.Repositories;

public interface IOrderRepository
{
    Task<Order?> FindAsync(long id, CancellationToken cancellationToken);

    Task<IReadOnlyList<Order>> ListByCustomerAsync(long customerId, CancellationToken cancellationToken);

    Task SaveAsync(Order order, CancellationToken cancellationToken);
}
