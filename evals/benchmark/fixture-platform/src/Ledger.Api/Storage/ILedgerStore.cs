using Ledger.Api.Domain;

namespace Ledger.Api.Storage;

internal interface ILedgerStore
{
    Task MigrateAsync(CancellationToken cancellationToken);

    Task<IReadOnlyList<LedgerEntry>> ListByCustomerAsync(long customerId, CancellationToken cancellationToken);

    Task<LedgerEntry> AddAsync(long customerId, long orderId, decimal amount, string kind, CancellationToken cancellationToken);
}
