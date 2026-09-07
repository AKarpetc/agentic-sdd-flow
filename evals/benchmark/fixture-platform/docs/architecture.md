# The orders platform

Five HTTP services and one shared contracts library. Every service owns its own data; nothing reads
another service's store. `Platform.Contracts` is the only assembly they share — a change to a record in
it is a change to every service that speaks that message.

| Service | Port | Owns | Store |
|---|---|---|---|
| `Checkout.Api` | 5081 | the public checkout, the fan-out and the compensation | none — it holds nothing of its own |
| `Orders.Api` | 5082 | orders and customers | in-memory, seeded |
| `Inventory.Api` | 5083 | stock per SKU and the reservations against it | in-memory, seeded |
| `Pricing.Api` | 5084 | the price list and the promotions | configuration (`Pricing` section) |
| `Ledger.Api` | 5085 | statement lines | SQLite, schema from `src/Ledger.Api/Migrations/*.sql` |

## Wiring

Peer addresses come from configuration only: `Services:<Name>:BaseUrl`, bound in `Checkout.Api/Program.cs`
onto typed `HttpClient`s. The environment overrides them (`Services__Orders__BaseUrl=…`), which is how the
services are relocated onto other ports in tests and in CI. **No service may hard-code a peer's port.**

`scripts/run-all.sh` starts all five on the ports above and waits for each to answer `/`;
`scripts/stop-all.sh` stops them; `scripts/smoke-checkout.sh` is the CI smoke.

## The checkout today

`POST /api/checkout` `{customerId, requestId, lines[]}`:

1. read the customer from `Orders.Api` (404 if unknown),
2. reserve every line at `Inventory.Api`, in order,
3. price the basket at `Pricing.Api`,
4. create the order at `Orders.Api` at the quoted total,
5. answer `{orderId, subtotal, total, reservationIds}`.

When a step after the first reservation fails, the reservations already taken are released
(`DELETE /api/reservations/{id}`) and the failure is answered as ProblemDetails: `409` for stock,
`400` for a SKU nothing can price, `404` for an unknown customer.

`requestId` is carried in the request and **not used for anything yet** — a repeat of the same
`requestId` runs the whole flow again and creates a second order.

`Ledger.Api` is not in the checkout path at all: statement lines are written by a nightly import that
lives outside this repository. Its schema comes from the numbered files in `src/Ledger.Api/Migrations/`,
applied in name order at start-up and recorded in `schema_migrations` — **an applied migration is never
edited; the next number is added instead.**

## Money

Every amount on the platform is a bare `decimal` and is understood to be USD — see
[ADR-0001](decisions/ADR-0001-amounts-are-usd.md). `CustomerView.Currency` exists and is served by
`Orders.Api` (customer 3 is `CAD`), but no other service reads it.
