---
name: dotnet-quality-gates
description: Use before opening or updating an MR on a .NET branch that changes logic, or when asked how well the tests catch bugs in a branch — "прогони мутанты", "Stryker", "CRAP", "какие изменения не покрыты тестами", "mutation score", "quality gate before MR". Measures the branch diff with real tools; for reasoning-only gap analysis use test-gap-analysis, for a whole-suite audit test-quality-auditor.
---

# .NET quality gates on the branch diff

Two deterministic gates over the lines the branch changed: **CRAP < 10** per method (coverage × complexity) and **no surviving mutant** (Stryker.NET). Scripts live in `${CLAUDE_PLUGIN_ROOT}/skills/dotnet-quality-gates/scripts/`.

Gates adapted from Robert C. Martin's [`ub-mode`](https://github.com/unclebob/ub-mode) (MIT): its Crapper and Mutator rules, ported from Clojure tooling to coverlet and Stryker.NET.

## Variables — repeat them in every shell call

```bash
REPO=$(git rev-parse --show-toplevel); QG=~/.cache/dotnet-quality-gates; OUT=${TMPDIR:-/tmp}/qg-$(basename "$REPO"); BASE=master
```

`BASE` must be a local branch (Stryker's `--since` needs one). Without a local `master`: `git fetch origin master:master`.

## Setup — once per machine, outside the repository

```bash
dotnet tool install dotnet-stryker --version 5.0.0 --tool-path $QG
```

Never add the tool to the repository's `.config/dotnet-tools.json`; every report goes to `$OUT`, never into the repository.

## Gate 1 — CRAP

```bash
dotnet test "$REPO/<Solution>.sln" --collect:"XPlat Code Coverage" --results-directory $OUT/cov
python3 -I ${CLAUDE_PLUGIN_ROOT}/skills/dotnet-quality-gates/scripts/crap.py "$OUT/cov/*/coverage.cobertura.xml" --repo "$REPO" --base $BASE
```

Needs `coverlet.collector` in the test projects; without it, report gate 1 as not run — adding the package is a repository change the user approves. If some test projects need Docker, run each Docker-free test project instead of the solution; the script merges every report the glob matches.

## Gate 2 — mutations

The production projects to mutate are those owning a changed `.cs` file: `git -C "$REPO" diff --name-only $BASE -- '*.cs'`. For each, from the directory of the unit-test project that references it:

```bash
$QG/dotnet-stryker --project <Production>.csproj --since:$BASE \
  --reporter json --reporter cleartext --output $OUT/stryker-<Production> --concurrency 6
```

`--project` is the file name of a project the test project references, not a path. `--since` mutates changed code and code whose tests changed, about 2–3 minutes per changed file; add `--mutate "**/<File>.cs"` to narrow a large diff. Then, from anywhere:

```bash
python3 -I ${CLAUDE_PLUGIN_ROOT}/skills/dotnet-quality-gates/scripts/survivors.py "$OUT/stryker-*/reports/mutation-report.json" --repo "$REPO"
```

## Acting on the result

Both scripts exit 1 when a row blocks; the last printed line is the summary that goes into the ticket, never into the MR description. A CRAP row **blocks** when its status is `new` (the whole method is in the diff) or it lists uncovered changed lines. Take the first matching row:

| Row | Action |
|---|---|
| CRAP ≥ 10, status `new` | Test it (TDD), then split it until it is under 10 |
| CRAP ≥ 10, `touched`, uncovered changed lines listed | Cover those changed lines only, not the rest of the method — hand the rows to `agentic-sdd-flow:tests-writer` |
| CRAP ≥ 10, `touched`, no uncovered changed lines | Legacy debt: list it in the report, do not refactor it unasked |
| `Survived` / `NoCoverage` mutant | Hand the table to `agentic-sdd-flow:tests-writer`: one behaviour test that fails on the mutant |
| Equivalent mutant (same observable behaviour) | Skip it and name it in the report with the reason |

On the `quick` route the session writes those tests itself instead of dispatching `tests-writer`. Re-run both gates after the tests land.

## Common mistakes

- Running Stryker without `--since` on a large solution — hours, not minutes.
- Integration-test projects as the Stryker working directory: they need Docker and multiply the run time; use unit tests.
- Counting `CompileError` mutants as a gap — they are Stryker noise. Stryker's log counts them for the whole project, `survivors.py` only for mutated files.
