# orders-platform

Five services, one shared contracts library, two data stores. Start here:
[docs/architecture.md](docs/architecture.md) — what each service owns, how they find each other, and how
the checkout runs today. Decisions are in [docs/decisions/](docs/decisions/).

```
dotnet build Platform.slnx
dotnet test  Platform.slnx
./scripts/run-all.sh          # all five, on the ports in their appsettings.json
./scripts/smoke-checkout.sh   # the CI smoke
./scripts/stop-all.sh
```

Peer addresses come from configuration (`Services:<Name>:BaseUrl`) and are overridden with
`Services__<Name>__BaseUrl` in the environment — never hard-code a port.
