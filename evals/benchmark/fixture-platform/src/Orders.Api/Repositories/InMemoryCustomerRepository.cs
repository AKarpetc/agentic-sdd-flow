using System.Collections.Concurrent;
using Orders.Api.Domain;

namespace Orders.Api.Repositories;

/// <summary>Process-local customer store; the platform's source of a customer's account currency.</summary>
internal sealed class InMemoryCustomerRepository : ICustomerRepository
{
    private readonly ConcurrentDictionary<long, Customer> _customers = new(Seed().ToDictionary(customer => customer.Id));

    public Task<Customer?> FindAsync(long id, CancellationToken cancellationToken)
    {
        _customers.TryGetValue(id, out var customer);
        return Task.FromResult(customer);
    }

    private static IEnumerable<Customer> Seed()
    {
        yield return new Customer(1, "USD");
        yield return new Customer(2, "USD");
        yield return new Customer(3, "CAD");
    }
}
