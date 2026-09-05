---
name: tsql-reviewer
description: >
  Review T-SQL — stored procedures, functions, views, ad-hoc queries and SSDT object scripts —
  for correctness, backward compatibility and performance (SARGability, implicit conversions,
  parameter sniffing, index use, set-based vs cursor). Use when a change touches .sql files or
  when a procedure is slow. Pairs with sqlserver-query-plans for plan reading and mssql-mcp for
  live schema and SHOWPLAN.
---

# T-SQL Reviewer

Checklists distilled from vince-winkintel/sql-server-skills (MIT) and common SQL Server practice; rewritten for this plugin.

## Inputs

- The changed `.sql` files (diff range) or the procedure name.
- Live access when available: `mssql-mcp` `describe_table` (columns, indexes), `explain_query` (estimated plan) — read-only. Without it, reason from the DDL in the repository and say so.

## 1. Backward compatibility (blocking)

- **Result sets:** a procedure that returns several result sets keeps their order; a **new SELECT goes at the end**. Reordering or inserting breaks every reader that consumes by position.
- **Columns:** never remove or rename a column of an existing result set; add new columns at the end of the select list. Type widening is safe, narrowing is not.
- **Parameters:** new parameters get defaults; removing or reordering positional parameters breaks callers that pass positionally. `find_references`/grep the calling code for the procedure name to see how it is invoked.
- **Return codes / output params:** keep existing semantics.

## 2. Correctness

- Set-based logic over cursors and `WHILE` loops unless the row-by-row is required (and say why).
- `SET NOCOUNT ON` at the top of procedures; `SET XACT_ABORT ON` when the procedure writes.
- Transactions: explicit `BEGIN TRAN … COMMIT` with `TRY/CATCH` and `THROW`; no nested transaction assumptions; no transaction held across a network round trip.
- `NULL` semantics in comparisons and `NOT IN` (use `NOT EXISTS`).
- `MERGE` on a seed/reference table rewrites matching rows every deploy — flag any seed edit as a data change, not a script change.
- Idempotent DDL in scripts (`IF OBJECT_ID(...) IS NULL`, `CREATE OR ALTER`).

## 3. Performance

- **SARGable predicates:** no function on the column side (`WHERE CAST(col …)`, `WHERE YEAR(col)=`, `LIKE '%x'`), no arithmetic on the column.
- **Implicit conversions:** compare the parameter type with the column type (`describe_table`); `nvarchar` parameter vs `varchar` column is a scan.
- **Parameter sniffing:** wildly different parameter cardinalities → consider `OPTION (RECOMPILE)` on the statement, or `OPTIMIZE FOR`, or local variables — recommend the narrowest.
- **Index use:** check predicates and joins against existing indexes (`describe_table`); missing-index DDL from a plan is a hint, not a recommendation — load `sqlserver-query-plans` for the plan.
- **Temp tables vs table variables vs CTEs:** large intermediate sets → temp table with statistics; CTE is not materialised.
- `SELECT *` in procedures, `DISTINCT` to hide a join bug, scalar UDFs in predicates, `NOLOCK` as a performance fix — all findings.

## Output

Findings with ids `S1…`, `severity ∈ {critical, important, minor}`, `File:Line` (or procedure name), the rule, the fix as T-SQL. Compatibility breaks are `critical`. End with "Verified with: <mssql-mcp calls | repository DDL only>".
