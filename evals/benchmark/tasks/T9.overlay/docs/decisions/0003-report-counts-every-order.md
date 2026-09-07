# ADR-0003: The customer report counts every order, cancelled included

- Status: Accepted (2026-01-20)
- Deciders: finance, orders team

## Context

The finance export reconciles the customer report's `N orders` against the ledger, which keeps a row
for every order ever placed — cancelled orders stay in the ledger with a reversal entry. Excluding
cancelled orders from the report made the reconciliation alert fire on every customer with a
cancellation (2026-01, three false pages).

## Decision

`N` in the customer report is the total number of the customer's orders, whatever their status.

## Consequences

- Anyone who needs "active orders" adds a new field; the existing count is not repurposed.
- A change to this rule reopens the reconciliation with finance and needs their sign-off.
