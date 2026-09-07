using System.Globalization;
using Ledger.Api.Configuration;
using Ledger.Api.Domain;
using Microsoft.Data.Sqlite;
using Microsoft.Extensions.Options;

namespace Ledger.Api.Storage;

/// <summary>The statement store: one connection kept open for the process, schema applied from Migrations/.</summary>
internal sealed class LedgerStore : ILedgerStore, IAsyncDisposable
{
    private readonly IOptions<LedgerSettings> _settings;
    private readonly SemaphoreSlim _gate = new(1, 1);
    private SqliteConnection? _connection;

    public LedgerStore(IOptions<LedgerSettings> settings)
    {
        _settings = settings;
    }

    public async Task MigrateAsync(CancellationToken cancellationToken)
    {
        var connection = await ConnectionAsync(cancellationToken);
        await ExecuteAsync(connection, "CREATE TABLE IF NOT EXISTS schema_migrations (name TEXT PRIMARY KEY)", cancellationToken);
        foreach (var file in MigrationFiles())
        {
            var name = Path.GetFileName(file);
            if (await AppliedAsync(connection, name, cancellationToken))
            {
                continue;
            }

            await ExecuteAsync(connection, await File.ReadAllTextAsync(file, cancellationToken), cancellationToken);
            // record it so the next start skips it
            await ExecuteAsync(connection, $"INSERT INTO schema_migrations (name) VALUES ('{name}')", cancellationToken);
        }
    }

    public async Task<IReadOnlyList<LedgerEntry>> ListByCustomerAsync(long customerId, CancellationToken cancellationToken)
    {
        var connection = await ConnectionAsync(cancellationToken);
        await _gate.WaitAsync(cancellationToken);
        try
        {
            using var command = connection.CreateCommand();
            command.CommandText = "SELECT id, customer_id, order_id, amount, kind FROM entries WHERE customer_id = $customer ORDER BY id";
            command.Parameters.AddWithValue("$customer", customerId);
            var entries = new List<LedgerEntry>();
            await using var reader = await command.ExecuteReaderAsync(cancellationToken);
            while (await reader.ReadAsync(cancellationToken))
            {
                entries.Add(Read(reader));
            }

            return entries;
        }
        finally
        {
            _gate.Release();
        }
    }

    public async Task<LedgerEntry> AddAsync(long customerId, long orderId, decimal amount, string kind, CancellationToken cancellationToken)
    {
        var connection = await ConnectionAsync(cancellationToken);
        await _gate.WaitAsync(cancellationToken);
        try
        {
            using var command = connection.CreateCommand();
            command.CommandText = "INSERT INTO entries (customer_id, order_id, amount, kind) VALUES ($customer, $order, $amount, $kind); SELECT last_insert_rowid()";
            command.Parameters.AddWithValue("$customer", customerId);
            command.Parameters.AddWithValue("$order", orderId);
            command.Parameters.AddWithValue("$amount", amount.ToString("0.00", CultureInfo.InvariantCulture));
            command.Parameters.AddWithValue("$kind", kind);
            var id = (long)(await command.ExecuteScalarAsync(cancellationToken))!;
            return new LedgerEntry(id, customerId, orderId, amount, kind);
        }
        finally
        {
            _gate.Release();
        }
    }

    public async ValueTask DisposeAsync()
    {
        if (_connection is not null)
        {
            await _connection.DisposeAsync();
        }

        _gate.Dispose();
    }

    private IEnumerable<string> MigrationFiles()
    {
        var directory = Path.IsPathRooted(_settings.Value.MigrationsPath)
            ? _settings.Value.MigrationsPath
            : Path.Combine(AppContext.BaseDirectory, _settings.Value.MigrationsPath);
        return Directory.Exists(directory)
            ? Directory.GetFiles(directory, "*.sql").OrderBy(path => path, StringComparer.Ordinal)
            : Enumerable.Empty<string>();
    }

    private async Task<SqliteConnection> ConnectionAsync(CancellationToken cancellationToken)
    {
        if (_connection is not null)
        {
            return _connection;
        }

        await _gate.WaitAsync(cancellationToken);
        try
        {
            _connection ??= await OpenAsync(cancellationToken);
            return _connection;
        }
        finally
        {
            _gate.Release();
        }
    }

    private async Task<SqliteConnection> OpenAsync(CancellationToken cancellationToken)
    {
        var connection = new SqliteConnection(_settings.Value.ConnectionString);
        await connection.OpenAsync(cancellationToken);
        return connection;
    }

    private static async Task<bool> AppliedAsync(SqliteConnection connection, string name, CancellationToken cancellationToken)
    {
        using var command = connection.CreateCommand();
        command.CommandText = "SELECT COUNT(*) FROM schema_migrations WHERE name = $name";
        command.Parameters.AddWithValue("$name", name);
        return (long)(await command.ExecuteScalarAsync(cancellationToken))! > 0;
    }

    private static async Task ExecuteAsync(SqliteConnection connection, string sql, CancellationToken cancellationToken)
    {
        using var command = connection.CreateCommand();
        command.CommandText = sql;
        await command.ExecuteNonQueryAsync(cancellationToken);
    }

    private static LedgerEntry Read(SqliteDataReader reader)
    {
        return new LedgerEntry(
            reader.GetInt64(0),
            reader.GetInt64(1),
            reader.GetInt64(2),
            decimal.Parse(reader.GetString(3), CultureInfo.InvariantCulture),
            reader.GetString(4));
    }
}
