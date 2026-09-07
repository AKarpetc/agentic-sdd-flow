using Platform.Contracts;

namespace Checkout.Api.Clients;

internal interface IOrdersClient
{
    Task<CustomerView?> FindCustomerAsync(long customerId, CancellationToken cancellationToken);

    Task<OrderView?> CreateAsync(long customerId, decimal total, CancellationToken cancellationToken);
}
