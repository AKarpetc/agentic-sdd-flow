namespace Ledger.Api.Configuration;

/// <summary>Where the statement lines live and where the schema comes from.</summary>
internal sealed class LedgerSettings
{
    public string ConnectionString { get; set; } = "Data Source=ledger;Mode=Memory;Cache=Shared";

    public string MigrationsPath { get; set; } = "Migrations";
}
