using Orders.Api.Domain;

namespace Orders.Api.Repositories;

internal interface ICustomerRepository
{
    Task<Customer?> FindAsync(long id, CancellationToken cancellationToken);
}
