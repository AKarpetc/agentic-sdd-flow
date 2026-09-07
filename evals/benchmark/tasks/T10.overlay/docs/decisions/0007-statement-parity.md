# ADR-0007: Statement parity with the ledger

- Status: Accepted (2026-02-11)
- Deciders: finance platform, orders team

## Context

The periodic statement is reconciled line by line against the ledger. The ledger never drops a line: a
reversal is posted as its own entry and the original stays. When the statement narrowed its line count to
exclude reversed entries, the parity check failed for every payer who had ever reversed one, and the
finance on-call was paged three times in a fortnight.

## Decision

Every line raised for a payer is counted in the statement, reversals included. Narrowing the count is a
parity break and needs finance sign-off, not a ticket.

## Consequences

- A view that needs only actionable lines adds its own field; the parity count is not repurposed.
- The parity guard in CI pins the count for the seeded payer and must not be relaxed to make a build pass.
