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

## 2. Size the change, then **propose the route** — do not just pick one

Answer the five questions in [references/sizing.md](references/sizing.md) from the brief plus a **budgeted**
look at the repository (at most: one `roslyn-query.py <project> get_endpoint_map` or one Grep for the symbol
the brief names). Do not explore further to decide — the gate must be cheaper than the work.

Then **present three routes with what each costs, recommend one, and say why** — in this shape, at most
ten lines, before any work starts:

```
Sizing: 3 files, one internal endpoint, no store, no contract, behaviour specified.
  A. superpowers      brainstorming → TDD in this session, no plugin agent   ≈ $2–4,  4–8 min   ← recommended
  B. mix              A, then the plugin's verified review gate on the branch ≈ $6–10, 12–20 min
  C. agentic (light)  plan → dotnet-sdd, implement/tests per task + review    ≈ $9–14, 20–25 min
Recommended A: the rules gate runs either way through the hooks, and on this size the measured
difference between A and C was cost only — same files, same tests. Say B or C to override.
```

**Recommend by the table below** — it is what the measurements support, not a preference:

| The change | Recommend | Why |
|---|---|---|
| one or two files, behaviour specified | **A `superpowers`** | measured parity with the plugin on the simple task at a third of the cost |
| inside one service: several files, new types, state, an internal endpoint | **B `mix`** | the flow that writes code fastest, plus the one thing it has no equivalent for — a verified review with the defect floor |
| a data store, a migration on existing rows, an external contract (gRPC, public endpoint, published event), two or more projects, new infrastructure | **C `agentic`** (`standard`, or `deep` when the design itself is open) | a plan, a per-task gate and a design record are worth their price only where a mistake reaches another team |
| the brief contradicts the repository (a doc, an ADR, a test, CI, a consumer note) | any route **plus** `evidence-reconciler` first | never let a route decide a contradiction |

Rules for the proposal:

- 🔴 **A repository's routing policy outranks the table.** `routing` in `.claude/agentic-sdd-flow.json`
  (`default`, `maxAutoTier`) is injected into your context as a `<routing-policy>` block. Where it is set,
  `default` is what you take unless the brief demands more, and you **never** route above `maxAutoTier`
  on your own judgement — recommend the higher route in one line, say what it would buy, and continue at
  the ceiling until the user answers. The policy never suspends a mandatory route (review →
  `dotnet-code-review`, test authoring → `tests-writer`, contradiction → `evidence-reconciler`) and never
  suspends the rules. **It does not forbid agents, only routes**: handing one job to the agent that owns it
  — `tests-writer`, `code-reviewer`, `dotnet-architect` or the `architecture-design` workflow for a design
  question, `debugger` for a root cause — is allowed at any tier when the work needs it; what the ceiling
  stops is buying a plan-driven workflow's whole agent chain for the ticket unasked.
- **The user's answer wins**, including "just do it" (→ A) and `--tier quick|light|standard|deep` (→ that route).
- **Non-interactive or headless run** (no human to answer, a benchmark, a `-p` session): take the
  recommendation, state it in one line, continue. Never block on the menu.
- **Estimates come from [sizing.md](references/sizing.md)**, which carries the measured numbers. Do not invent
  a figure; if a route has no measurement for this size, say `unmeasured`.
- **One route up, never two**, and only on evidence found during the run:
  - A → B when the change turns out to touch a third production file or a behaviour another service reads;
  - B → C when a task needs a migration, a contract change, or the review finds a `critical`;
  - C → `deep` **only with the user's word**.
- De-escalation mid-run is not allowed: once the design pipeline has run, its spec is executed.

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

## Route map

| Route | Section | What runs |
|---|---|---|
| A `superpowers` (= `quick`) | 3q | the superpowers flow in this session, no plugin agent |
| B `mix` | 3m | 3q, then `dotnet-sdd` in `mode: 'review'` on the branch |
| C `agentic` — `light` | 3l | short plan → `dotnet-sdd` `mode: 'light'` |
| C `agentic` — `standard` | 3s | brainstorm → plan → one plan review → `dotnet-sdd` |
| C `agentic` — `deep` | 3d | `architecture-design` first, then `standard` |

## 3q. `quick` — the superpowers flow, no plugin agents

A one- or two-file change does not need the plugin's machinery; it needs the plugin's *rules*, and those
are already in force through the hooks (the injected contract, the write gate on `.cs`/`.csproj`). So:

1. Invoke `superpowers:brainstorming` and let it size the change itself; when it concludes spike or
   bounded (it will, for a `quick` change), continue with `superpowers:test-driven-development` in this
   session — red test, code, green, refactor — for every branch the brief names, including the entry point
   (endpoint, handler) once.
2. Dispatch **no** plugin agent: no implementer, no `tests-writer`, no reviewer, no workflow. The write gate
   rejects a convention violation the moment it is written; the tests are yours to write, under the test
   contract in your context.
3. Commit as `<TASK-KEY>: <Description>` on the current branch, report the branch, and stop.

Measured on the benchmark's simple task (T5, Opus 5): this flow delivers 5/5 with an endpoint test in
≈ 4 minutes for ≈ $2; the same change through `light` cost $7 and 16 minutes for the same tree. If a
fourth production file opens, or brainstorming itself concludes the change is not bounded, escalate to
`light` and say so.

## 3m. `mix` — superpowers writes it, the plugin gates it

The fastest writer and the gate the writer does not have. Nothing else.

1. Record the branch point first: `git -C <projectDir> rev-parse HEAD` → `base`.
2. Do the work exactly as in **3q** (brainstorming → `superpowers:test-driven-development`), committing as
   you go. No implementer, no `tests-writer`, no plan.
3. Gate it:
   `Workflow({ name: 'agentic-sdd-flow:dotnet-sdd', args: { project, projectDir, taskKey, mode: 'review', base } })`.
   Review mode has no plan and no tasks: it reviews the whole branch once at full effort, sends every
   critical/important finding and every `defect` through `findings-verifier`, runs one fix wave and a
   scoped re-review, and returns the same result shape as any other run.
4. Continue at step 5.

Use it when the change lives in one service but somebody else's code depends on its behaviour — the
review, the defect floor and the verifier are what you are paying for, and they cost one agent pass over
a finished branch instead of three per plan task.

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
3. **Plan review — at most twice, and the second one is the last.** Dispatch
   `agentic-sdd-flow:plan-reviewer` with the plan path and the spec path; apply every critical and important
   finding to the plan yourself and dispatch the reviewer once more (it verdicts the prior ids first).
   🔴 **Do not dispatch a third time.** If the second pass still returns findings, apply them and execute —
   only an unresolved `critical` (a task that cannot be implemented as written) buys one more round, and
   then you say so in one line. A third round bought nothing measurable and cost 20 minutes of reviewer time
   on the 2026-09-08 deep run, on a plan whose implementation was then cut short by the budget.
   When it approves, pass `skipPlanReview: true` to the workflow — the workflow's own Plan review phase
   would otherwise review the same plan a second time.
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
6. Second run — a **record** pass, not a replay: the same call plus `approvedProposalId`, `resumeFromRunId`
   from the first run, and 🔴 **`priorRun`: the whole result object the first run returned**. With `priorRun`
   the workflow skips phases 1–7 and goes straight to the ADRs and the spec. Without it the panel runs again,
   and the resume cache only saves you while every prompt is byte-identical — so the moment you improve the
   brief in answer to the design review, the cache misses and the whole pipeline replays (measured
   2026-09-08: 21 minutes, aborted by hand). **Never edit the brief between the two calls** — corrections to
   the design go into the record pass as part of `priorRun.designReview`, or into the spec fix pass.
   Then continue with brainstorming's steps 7–8 (spec self-review, user reviews the spec) on `specPath`.
   If the second run's `decision.winnerId` differs from the id you approved, stop and show both — do not
   write ADRs from a different decision table.
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
