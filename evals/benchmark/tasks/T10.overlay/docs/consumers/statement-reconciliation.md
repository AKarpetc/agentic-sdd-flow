# Consumer: statement-reconciliation

Nightly job of the finance platform. Parses the line count out of each payer's statement and compares it
with the number of ledger entries for that payer. A mismatch pages the finance on-call.

- Owner: finance platform, `#finance-platform` in Slack.
- Contract: the count is every line raised for the payer, reversals included (ADR-0007).
- The ledger keeps reversed entries for seven years; the reconciliation cannot compensate for a narrowed
  count on the producer side.
