# Consumer: finance-export

Nightly job. Reads every customer report line, parses `<N> orders`, and compares `N` with the number
of ledger rows for that customer. A mismatch pages the finance on-call.

- Owner: finance platform, `#finance-platform` in Slack.
- Contract: `N` = all orders of the customer, cancelled included (ADR-0003). The ledger never drops a
  cancelled order.
- Any change to what `N` counts must be coordinated with the ledger side first.
