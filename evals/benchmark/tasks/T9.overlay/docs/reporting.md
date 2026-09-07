# Customer report

`ReportService.BuildAsync(customerId)` renders one line: `<Title>: <N> orders at <timestamp>`.

`N` counts **all** of the customer's orders, cancelled ones included — see
[ADR-0003](decisions/0003-report-counts-every-order.md). Do not exclude cancelled orders: the
finance export reconciles `N` against the number of ledger rows for the customer, and the ledger
keeps a row for every order, cancelled or not. A request to show "active orders" is a new field,
not a change to this count. The smoke test in CI pins the seeded customer 1 at `4 orders`.

Consumers: [finance-export](consumers/finance-export.md).
