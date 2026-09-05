---
name: ssdt-reviewer
description: >
  Review SQL Server Data Tools (SSDT) database projects — .sqlproj, dacpac deployments,
  pre/post-deploy scripts, seed MERGE scripts, refactor log — for deploy safety: data loss,
  post-deploy ordering, seed overwrites, publish profile options. Use when a change touches a
  .sqlproj, a PostDeployment script, or a table definition deployed as a dacpac.
---

# SSDT Reviewer

## What SSDT deploys

`sqlpackage /Action:Publish` diffs the dacpac against the target and generates DDL. That means:

- A **column drop or type narrowing** in a `.sql` table definition becomes a `DROP COLUMN` / table rebuild on publish. `BlockOnPossibleDataLoss=True` (the default) stops the deploy; a change that needs it set to false is a `critical` finding that requires an explicit migration step.
- A **rename** without an entry in `RefactorLog.refactorlog` is a drop + create (data loss). Renames must go through the refactor log.
- **Post-deployment scripts** run after the schema diff, in the order of `:r` includes in `PostDeployment.sql`. A script that references an object created in the same deploy is fine; one that depends on data another script inserts must come after it.
- **Seed scripts** written as `MERGE … WHEN MATCHED THEN UPDATE` rewrite live rows on every deploy: editing a seed value retroactively changes existing data everywhere the dacpac is published. Flag every seed edit as a data change and ask whether existing rows should change.
- **Pre-deployment scripts** run before the diff; use them to preserve data before a destructive change (copy to a staging table), never for DDL the dacpac already describes.

## Review steps

1. `git diff <base>..<head> -- '*.sqlproj' '*.sql' '*.refactorlog' '*.publish.xml'` — list every changed object.
2. For each table change classify: additive (new nullable column, new table, new index) → `minor`; default-valued NOT NULL column → check existing-row fill; narrowing / drop / rename → `critical` unless refactor-logged and pre-deploy-preserved.
3. For each procedure/function change apply the `tsql-reviewer` skill (result-set order, parameters).
4. For post-deploy: verify `:r` order against dependencies; verify seeds are idempotent; verify no environment-specific values are hard-coded (use SQLCMD variables from the publish profile).
5. When `sqlpackage` is available, produce the deploy report against a development target and quote its warnings:
   `sqlpackage /Action:DeployReport /SourceFile:<dacpac> /TargetConnectionString:"<dev>" /OutputPath:report.xml /p:BlockOnPossibleDataLoss=True` — report `<Alert>` and `<Operation Name="Drop">` entries. When it is not installed, say `deploy report: not run (sqlpackage missing)`.

## Output

Findings `D1…`, `severity ∈ {critical, important, minor}`, file, what publish will generate, the safe sequence (expand → deploy → migrate data → contract). End with the publish-profile options the change relies on.
