# Third-party notices

- Specialist agents and the skills listed in `rules/kit-overrides.md` are derived from
  [dotnet-claude-kit](https://github.com/codewithmukesh/dotnet-claude-kit) (MIT).
- The `dotnet-sdd` workflow calls the `task-brief`, `review-package` and `sdd-workspace`
  helper scripts shipped by [superpowers](https://github.com/obra/superpowers) (MIT) at runtime;
  no superpowers source is copied here.
- `skills/run-tests`, `skills/filter-syntax`, `skills/platform-detection`, `skills/test-gap-analysis`,
  `skills/assertion-quality`, `skills/grade-tests`, `skills/test-analysis-extensions` (dotnet.md only),
  `skills/analyzing-dotnet-performance` and `agents/test-quality-auditor.md` are copied from
  [dotnet/skills](https://github.com/dotnet/skills) (MIT, © .NET Foundation and Contributors) with
  edits noted in each file's frontmatter or the plugin README.
- `agents/docs-sync.md` is adapted from `docs-drift-editor` in
  [VoltAgent/awesome-claude-code-subagents](https://github.com/VoltAgent/awesome-claude-code-subagents) (MIT).
- `agents/concurrency-specialist.md` is adapted from `dotnet-concurrency-specialist` in
  [Aaronontheweb/dotnet-skills](https://github.com/Aaronontheweb/dotnet-skills) (MIT).
- `skills/sqlserver-query-plans` is copied from `query-plan-analysis` in
  [erikdarlingdata/claude-plugins](https://github.com/erikdarlingdata/claude-plugins) (MIT).
- `skills/tsql-reviewer` distils checklists from
  [vince-winkintel/sql-server-skills](https://github.com/vince-winkintel/sql-server-skills) (MIT).
- `skills/postgres-best-practices` is copied from `supabase-postgres-best-practices` in
  [supabase/agent-skills](https://github.com/supabase/agent-skills) (MIT) with the RLS and platform
  sections removed.
- `skills/postgres-migration` and `skills/design-postgres-tables` are copied from
  [timescale/pg-aiguide](https://github.com/timescale/pg-aiguide) (Apache-2.0; the NOTICE file
  sits next to each copy) with platform-specific sections removed.
- `agents/postgres-specialist.md` follows the measure-first loop of
  [yuribodo/postgres-query-optimization-skill](https://github.com/yuribodo/postgres-query-optimization-skill) (MIT).
- `skills/optimizing-ef-core-queries` is copied from [dotnet/skills](https://github.com/dotnet/skills) (MIT).
- `agents/migration-reviewer.md` adapts the three-layer structure of `data-migration-reviewer` in
  [EveryInc/compound-engineering-plugin](https://github.com/EveryInc/compound-engineering-plugin) (MIT)
  and the expand/contract checklist of [wshobson/agents](https://github.com/wshobson/agents) (MIT).
- `skills/architecture-design/references/{baseline-builder,current-architecture,proposal-builder,decision-recorder,diagram-builder,migration-planner}.md`
  are copied from the architecture-suite of [levnikolaevich/claude-code-skills](https://github.com/levnikolaevich/claude-code-skills) (MIT).
- `references/c4-model.md` from [cheriftj/c4-model-skill](https://github.com/cheriftj/c4-model-skill) (MIT);
  `references/review-rubric.md` and `references/adr-madr.md` from
  [gauravs19/enterprise-architecture-skill](https://github.com/gauravs19/enterprise-architecture-skill) (MIT);
  `references/scenario-compare.md` and `references/nfr-capture.md` from
  [DavidROliverBA/Daves-Claude-Code-Skills](https://github.com/DavidROliverBA/Daves-Claude-Code-Skills) (MIT);
  `references/adr-process.md` from [joestump/claude-plugin-sdd](https://github.com/joestump/claude-plugin-sdd) (MIT).
- `skills/stride-threat-model` from [ivan-sincek/threat-modeling-agent-skills](https://github.com/ivan-sincek/threat-modeling-agent-skills) (MIT);
  `skills/threat-mitigation-mapping` from [wshobson/agents](https://github.com/wshobson/agents) (MIT).
