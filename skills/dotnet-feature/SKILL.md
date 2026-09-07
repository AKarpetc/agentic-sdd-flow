---
name: dotnet-feature
description: >
  Single entry point for plan-driven .NET feature work: size the change, then run the route it
  deserves — inline for a one-file fix, a light workflow for a small change, the full
  implement → tests → review → verified fix loop for a feature, the design pipeline for a change
  that crosses services. Use for "implement feature PROJ-123 …", "do task PROJ-123",
  "/dotnet-feature PROJ-123 <description>".
---

# dotnet-feature

Runs one ticket end-to-end. It never pushes, never merges and never opens a PR.

🔴 **Every run starts with the sizing gate in step 2.** Running the full route on a one-file change costs
five to ten times what the change is worth; running the inline route on a cross-service change ships an
unreviewed design. The gate is what makes the flow affordable — do not skip it, and state the tier you
picked in one line before you start work.

## 1. Resolve the inputs

- **Task key**: the first argument matching `taskKeyPattern` from `.claude/agentic-sdd-flow.json`
  (default `[A-Z][A-Z0-9]+-\d+`); else the current branch name of the target repository; else ask.
- **Project**: the argument naming a project, matched against `projects` in the config or a
  directory under the repository root; `projectDir` is its absolute path (the directory holding
  the `.sln`/`.slnx`). Ask if ambiguous.
- **Description**: the rest of the arguments.
- **Forced tier** (optional): `--tier quick|light|standard|deep` anywhere in the arguments, or the user
  saying "just do it" / "full review please". An explicit tier always wins over the gate.

## 2. Size the change — the tier gate

Answer the five questions in [references/sizing.md](references/sizing.md) from the brief plus a **budgeted**
look at the repository (at most: one `roslyn-query.py <project> get_endpoint_map` or one Grep for the symbol
the brief names). Do not explore further to decide — the gate is meant to be cheaper than the work.

| Tier | The change looks like | Route |
|---|---|---|
| `quick` | one or two files, no new endpoint / contract / migration / package, behaviour already specified (a bug fix, a rename, a guard, a threshold) | **step 3q** — inline, no plan, no workflow |
| `light` | one project, roughly ≤ 5 files, one endpoint or one service behaviour, no data store, no external contract | **step 3l** — plan + `dotnet-sdd` in `mode: 'light'` |
| `standard` | a feature inside one service: several tasks, new types, tests across layers | **step 3s** — brainstorm + plan + plan review + `dotnet-sdd` |
| `deep` | two or more projects, a data store / migration on existing rows, an external contract (gRPC, public endpoint, published event), new infrastructure, or the user asks for a design | **step 3d** — `architecture-design`, then `standard` |

**One tier up, never two.** When two tiers fit, take the cheaper one and let the escalation rules move it up:

- `quick` → `light` when the fix needs a second file you did not expect, or the change has no test that can
  cover it without new plumbing.
- `light` → `standard` when the implementer reports `done_with_concerns` about scope, the Debug phase ran,
  or the final review returns a `critical` finding.
- `standard` → `deep` **only with the user's word.** If a task turns out to change a contract or a store,
  stop, say so, and ask.

Announce the outcome in one line: `Tier: light — one endpoint in shop-api, no store or contract change.`
De-escalation mid-run is not allowed: once the design pipeline has run, its spec is executed.

🔴 **When the brief contradicts the repository, nobody picks a side.** If the budgeted look (or
brainstorming, or the implementer) finds that a criterion in the brief states a behaviour that the code,
a test, a CI assertion, an ADR, a doc, a comment or a consumer note contradicts, dispatch
`agentic-sdd-flow:evidence-reconciler` with the claim, the observed behaviour and the sources you saw
**before** anything changes that behaviour. It weighs every source (executed > decided > descriptive >
intent) and returns `brief`, `code` or `undecided` with the evidence. `brief` → the code drifted: fix it
at the root and correct the stale comment/doc. `code` or `undecided` → the brief is wrong or the record is
split: show the evidence table to the user and **stop until they rule** — never "fix" an ADR, a CI
assertion or a consumer contract to match a ticket. Inside `dotnet-sdd` this happens on its own
(Reconcile phase; the workflow returns `status: 'contradiction'` for you to act on).

## 3q. `quick` — inline

No brainstorming, no plan, no workflow. In this session:

1. Read the code the brief names (Roslyn first).
2. Make the change yourself, or dispatch `agentic-sdd-flow:dotnet-implementer` for one task when the change
   spans more than one file.
3. Dispatch `agentic-sdd-flow:tests-writer` for the behaviour you changed — this is not optional, it is
   the one gate a `quick` run keeps.
4. Review the diff yourself with the `dotnet-code-review` skill, scoped to the changed files. Fix what it
   files as `critical` or `important`, and any `defect` of any severity.
5. Commit as `<TASK-KEY>: <Description>` on the current branch, report the branch, and stop.

Budget: one implementer-sized pass and one tests pass. If you find yourself opening a fifth file, escalate
to `light` and say so.

## 3l. `light` — plan, then the light workflow

1. Skip `superpowers:brainstorming`. Write the plan yourself as `<plansDir>/<YYYY-MM-DD>-<TASK-KEY>.md`
   with `### Task N` headings, a Files block and a test line per task — the same shape `writing-plans`
   produces, only shorter (usually two or three tasks). Do **not** dispatch `plan-reviewer`.
2. `Workflow({ name: 'agentic-sdd-flow:dotnet-sdd', args: { project, projectDir, plan, taskKey, mode: 'light' } })`.
   Light mode implements and tests each task, then reviews the **whole branch once** at the end with one
   fix wave — there is no per-task review loop and no plan review.
3. Continue at step 5.

## 3s. `standard` — brainstorm, plan, full workflow

1. **Design** — invoke `superpowers:brainstorming` with the description and keep its approval gate. Its own
   steps 4–5 (propose 2–3 approaches, present the design) carry the design; the design pipeline is for `deep`.
   If brainstorming itself concludes **spike** or **bounded**, drop to `quick` and finish in this session.
2. **Plan** — invoke `superpowers:writing-plans`. Save the plan as `<plansDir>/<YYYY-MM-DD>-<TASK-KEY>.md`
   (`plansDir` from config, default `temp/plans/`, resolved from the repository root — never inside the
   target project's tracked tree). When the skill offers its **Execution Handoff** menu, do not show it.
3. **Plan review — once, not twice.** Dispatch `agentic-sdd-flow:plan-reviewer` with the plan path and the
   spec path; apply every critical and important finding to the plan yourself and dispatch the reviewer once
   more (it verdicts the prior ids first). When it approves, pass `skipPlanReview: true` to the workflow —
   the workflow's own Plan review phase would otherwise review the same plan a second time.
4. `Workflow({ name: 'agentic-sdd-flow:dotnet-sdd', args: { project, projectDir, plan, taskKey, spec, skipPlanReview: true } })`.
   (This skill's instructions are the user's opt-in for the Workflow tool.) If the runtime reports the name
   as unknown, the plugin was installed during this session — ask the user to restart Claude Code, then retry.
   If it returns `status: plan_rejected`, its `openQuestions` are the findings — fix the plan and rerun.

## 3d. `deep` — the design pipeline first

1. Run `superpowers:brainstorming` through its clarifying questions (its step 3), then:
2. Resolve `plansDir`, `adrDir` from `.claude/agentic-sdd-flow.json` (defaults `temp/plans`,
   `docs/architecture/decisions`), `specsDir = docs/superpowers/specs` under the repository root,
   `slug = <TASK-KEY>-<kebab topic>`, `workDir = <plansDir>/architecture/<slug>`, and the projects
   list `[{ name, dir, solution }]` (from `projects` in the config or the resolved project directories).
3. **Size the pipeline too.** Pass `scope: 'compact'` unless the change spans two or more services *and*
   either crosses a trust boundary or touches a store; with `compact`, also pass
   `trustBoundaryChange: true|false` and `dataChange: true|false` honestly — they gate the threat model and
   the data review. `compact` runs one judge focus instead of five and keeps the three lenses.
4. First run (read-only):
   `Workflow({ name: 'agentic-sdd-flow:architecture-design', args: { brief, projects, nfrs, workDir, adrDir, specsDir, slug, scope, trustBoundaryChange, dataChange } })`.
   If the name is unknown, run it via `scriptPath: '<plugin root>/workflows/architecture-design.js'`.
5. Present to the user, verbatim from the result: the winner and runner-up (`decision.winnerId`,
   `decision.runnerUpId`, their summaries and estimates), the decision table, `decision.openDecisions`,
   `threats` with `critical`/`important` severity, `data.findings`, and `unanswered` drivers, and the
   paths of the proposal files whose mermaid sketches show each design. Ask
   which proposal to approve (or what to change). **Stop until the user answers.**
6. Second run: the same call plus `approvedProposalId` and `resumeFromRunId` from the first run.
   It writes the ADRs and the spec; then continue with brainstorming's steps 7–8 (spec self-review,
   user reviews the spec) on `specPath`. Always pass `resumeFromRunId`; if the second run's
   `decision.winnerId` differs from the id you approved, stop and show both — do not write ADRs from a
   different decision table.
7. Continue at step 3s with that spec (plan → one plan review → the workflow).

## 4. Resuming a workflow

`resumeFromRunId` replays cached agent results for unchanged prompts. After **editing the plan**, do not
resume: the cached rejection would be replayed. Start a fresh run instead.

## 5. Act on the result

- `status: 'done'` → invoke `superpowers:finishing-a-development-branch`; decline merge, push
  and PR; report the branch name, the commit range and `deferred` minors.
- `status: 'blocked'` → show `openQuestions` and `rulings` verbatim; wait for answers; rerun the
  workflow with `args.answers = { "<taskId>": { "<question>": "<answer>" } }`.
- `status: 'unstable'` → show `rulings` (parked/stalled findings) and `deferred`; ask whether to
  run another fix wave, park them, or stop. If the run was `light` and something serious is parked,
  offer the `standard` rerun rather than another light wave.
- `status: 'contradiction'` → show `reconciled` verbatim: for each entry the claim, the observed
  behaviour, the verdict with its confidence, the evidence table and the stale sources. Ask the user
  which is right (or relay the reconciler's questions to the owner it names); then rerun the workflow
  with `args.truth = { "<taskId>": "brief" | "code" }`. With `code`, the brief is wrong: say so in the
  final report, and the ticket's author corrects it — the repository's records stay as they are.

Always finish with the tier you ran, the branch name and "not pushed".
