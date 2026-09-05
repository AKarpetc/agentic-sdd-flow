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
