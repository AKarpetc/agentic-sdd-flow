# Customer report

`ReportService.BuildAsync(customerId)` renders one line: `<Title>: <N> orders at <timestamp>`.

`N` is the payer's statement line count under the parity rule — see
[ADR-0007](decisions/0007-statement-parity.md). Do not narrow it. A view that needs only the lines a
customer can still act on is a new field, not a change to this number. The parity guard in CI pins the
seeded payer 1 at `4 orders`.

Consumers: [statement-reconciliation](consumers/statement-reconciliation.md).
