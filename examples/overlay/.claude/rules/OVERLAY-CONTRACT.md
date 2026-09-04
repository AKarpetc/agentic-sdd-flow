# Overlay Contract — <company name>

Extends the plugin conventions with facts about our systems. Never relaxes a plugin rule.

## Services
- `orders`, `catalog` are on source-generated Mediator. `legacy-api` still uses MediatR — keep it.
- Internal contracts are gRPC (protobuf-net, code-first). Public REST lives only in `public-api`.

## Infrastructure
- Secrets live in the secret manager; the config store is not a secret store.
- CI is GitLab; review environments are raised with the `deploy-review-env` skill.
- Metrics: Prometheus + OpenTelemetry; dashboards and alert rules have their own skills (see `handoffs`).

## Databases
- SQL Server schema is SSDT (dacpac). New result sets go at the end of a procedure. Seed scripts MERGE on every deploy.
- PostgreSQL migrations are EF Core; expand-contract for anything that touches a hot table.

## Process
- Commit keys come from Jira; branch names are `feature/<KEY>`.
