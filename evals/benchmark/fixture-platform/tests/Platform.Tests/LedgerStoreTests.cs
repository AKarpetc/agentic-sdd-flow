using FluentAssertions;
using Ledger.Api.Configuration;
using Ledger.Api.Storage;
using Microsoft.Extensions.Options;
using NSubstitute;

namespace Platform.Tests;

public sealed class LedgerStoreTests
{
    [Fact]
    public async Task ListByCustomerAsync_ReturnsTheStatementLinesTheMigrationsSeeded()
    {
        await using var store = Store("ledger-list-tests");
        await store.MigrateAsync(CancellationToken.None);

        var entries = await store.ListByCustomerAsync(1, CancellationToken.None);

        entries.Select(entry => entry.Amount).Should().Equal(10.00m, 20.50m);
    }

    [Fact]
    public async Task AddAsync_AppendsAStatementLineForTheCustomer()
    {
        await using var store = Store("ledger-add-tests");
        await store.MigrateAsync(CancellationToken.None);

        var entry = await store.AddAsync(3, 900, 42.00m, "charge", CancellationToken.None);

        entry.Id.Should().BeGreaterThan(3);
        (await store.ListByCustomerAsync(3, CancellationToken.None)).Should().ContainSingle()
            .Which.Amount.Should().Be(42.00m);
    }

    private static LedgerStore Store(string name)
    {
        var settings = new LedgerSettings
        {
            ConnectionString = $"Data Source={name};Mode=Memory;Cache=Shared",
            MigrationsPath = Path.Combine(AppContext.BaseDirectory, "Migrations"),
        };
        var options = Substitute.For<IOptions<LedgerSettings>>();
        options.Value.Returns(settings);
        return new LedgerStore(options);
    }
}
