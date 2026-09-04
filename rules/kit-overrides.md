# Overrides for the imported dotnet-claude-kit Skills

The skills under [skills/](../skills/) listed below, the knowledge base in [knowledge/](../knowledge/), and the specialist agents that load them were imported from [dotnet-claude-kit](https://github.com/codewithmukesh/dotnet-claude-kit). They encode **that project's** opinions, which are not always this plugin's.

🔴 **Precedence — these conventions always win.** When an imported skill or knowledge doc conflicts with any of:

- [common.md](common.md)
- [code-convention.md](code-convention.md)
- [test-convention.md](test-convention.md)
- [single-type-per-file.md](single-type-per-file.md)
- the project's nearest `.editorconfig` or the project's own nested rules

…the convention is authoritative and the kit guidance is discarded. Never "modernize" existing code toward a kit default that these conventions forbid.

## Known Conflicts — Apply This Side

| Topic | Kit says | 🔴 This convention (use this) |
|---|---|---|
| **Primary constructors** | Use them for DI (`modern-csharp`, `scaffold`, all architecture skills) | **Banned for DI-resolved classes** — explicit ctor + `private readonly _field`. See [code-convention.md § Constructors](code-convention.md). Records/DTOs may use positional params. |
| **Mediator vs MediatR** | Defaults to source-generated `Mediator`; MediatR flagged commercial | **Aligned — the kit's default is now this plugin's too.** Source-generated `Mediator` is the standard for all new services and new CQRS code ([common.md § CQRS with Mediator](common.md)). Existing MediatR services (the services listed in the overlay contract) keep MediatR; migrate only on explicit request, via [knowledge/mediatr-to-mediator-migration.md](../knowledge/mediatr-to-mediator-migration.md). Never register both in one service. |
| **Assertions** | Plain xUnit `Assert`; FluentAssertions avoided kit-wide | **FluentAssertions v7.2.0** pinned, with `BeEquivalentTo` for object comparison ([test-convention.md](test-convention.md)). v7 is MIT/Apache and its license does not expire — the kit's commercial warning applies only to v8+, which this plugin never uses. |
| **Mocking** | Barely opinionated | **NSubstitute only** — never Moq ([test-convention.md](test-convention.md)). |
| **Test authoring** | The kit's own `testing`/`tdd` skills (deliberately **not** imported) | Delegate to the [tests-writer](../agents/tests-writer.md) agent / [tests-writer](../skills/tests-writer/SKILL.md) skill, or an additional per-service test skill named in the overlay contract. |
| **Target framework / language version** | Assumes `net10.0` + C# 14 everywhere | Target frameworks vary per project (net8.0 through net10.0, some legacy netstandard2.x). **Check the target project's TFM before using any C# 13/14 feature.** Never bump a TFM as a side effect. |
| **`IOptions<T>`** | Uses `IOptions<T>` in samples | **Never `IOptions<T>`** — `IOptionsSnapshot<T>` for scoped/transient, `IOptionsMonitor<T>` for singleton ([code-convention.md § IOptions](code-convention.md)). |
| **Access modifiers** | Frequently `public` | Most restrictive possible — `internal` implementations, `public` interfaces ([code-convention.md](code-convention.md)). |
| **New solutions/projects** | `.slnx`, central package management, kit folder layout | Fine for **new** projects. Do **not** restructure an existing solution, rename projects, or introduce `Directory.Packages.props` without explicit approval. |
| **Commit messages** | Conventional Commits — `chore: apply dotnet format`, `feat: …` (`de-sloppify` step table, scaffolds) | **`<TASK-KEY>: <Description>`** — `PROJ-42: Add the order lookup endpoint`. Type prefixes are forbidden; an optional type goes at the end in parentheses: `PROJ-118: Remove dead code (chore)`. See [code-convention.md § Git](code-convention.md#git-️). |
| **Architecture** | Vertical Slice Architecture is the kit default ([ADR 001](../knowledge/decisions/001-vsa-default.md)) | Existing services have their own established structure. Match the project you are in; propose, never impose. |

## Imported Skills

**Baseline:** `modern-csharp`

**API:** `minimal-api`, `api-versioning`, `authentication`, `error-handling`

**Data:** `ef-core`, `configuration`, `migrate`

**Architecture:** `architecture-advisor`, `project-structure`, `scaffold`, `project-setup`, `vertical-slice`, `clean-architecture`, `ddd`

**Ops:** `docker`, `ci-cd`, `aspire`

**Quality:** `build-fix`, `de-sloppify`, `dependency-injection`, `caching`

## Roslyn MCP Requirement

The imported agents are MCP-first — they navigate code with the `cwm-roslyn-navigator` Roslyn tools instead of reading files. Five of the tools they reference (`get_endpoint_map`, `get_di_registrations`, `get_symbol_source`, `get_file_outline`, `get_nuget_packages`) require **CWM.RoslynNavigator ≥ 0.8.0**:

```bash
dotnet tool update --global CWM.RoslynNavigator
dotnet tool list --global | grep -i roslyn   # verify >= 0.8.0
```

Two ways to reach it:

1. **Dynamic runner (default):** `roslyn-query.py <project-or-solution> <tool> '<json-args>'` (on `PATH` via the plugin's `bin/`). It launches one navigator per solution, keeps it warm behind a socket and needs no re-pinning. First call per solution: `get_project_graph` — an empty result or a foreign solution path means a mis-bind, never "clean code". `--restart` after switching branches.
2. **Pinned MCP server (fallback):** `mcp__cwm-roslyn-navigator__*` binds **one solution per launch**, read from `${CLAUDE_PLUGIN_DATA}/roslyn-solution`. Switch it with `bind-roslyn.sh <project-name-or-path>` and reconnect the server (`/mcp` → `cwm-roslyn-navigator` → reconnect). A navigator bound elsewhere returns empty results, not errors.
