# ADR-0001 — Every amount on the platform is USD

- Status: accepted
- Date: 2026-04-18

## Context

The platform launched in one market. Prices, order totals and statement lines are all `decimal`, and the
currency is implicit in the deployment. `Orders.Api` already stores a `Currency` on the customer record,
because the account system it was imported from carried one, and customer 3 is `CAD`.

## Decision

Amounts stay bare `decimal` and are USD everywhere. `CustomerView.Currency` is served but **ignored**: no
pricing, order or ledger path reads it. The ledger's `entries` table has no currency column, and the
nightly import that writes it assumes USD.

## Consequences

- A second currency cannot be sold today: pricing has one price list, and a `CAD` customer would be
  charged USD prices and billed in USD.
- The `Currency` field on the customer is a known trap — it reads as if it were honoured.
- Undoing this decision means a coordinated change: the contracts, every service that carries an amount,
  and a migration that gives the existing statement lines the currency they were always in.
