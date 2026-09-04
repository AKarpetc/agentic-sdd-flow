---
name: dotnet-feature
description: >
  Single entry point for plan-driven .NET feature work: brainstorm the design (approval gate),
  write the plan, then execute it with the dotnet-sdd workflow (implement → tests → review →
  verified fix loop → final review) and hand back a branch. Use for "implement feature
  PROJ-123 …", "do task PROJ-123", "/dotnet-feature PROJ-123 <description>".
---

# dotnet-feature

Runs one ticket end-to-end. It never pushes, never merges and never opens a PR.

## 1. Resolve the inputs

- **Task key**: the first argument matching `taskKeyPattern` from `.claude/agentic-sdd-flow.json`
  (default `[A-Z][A-Z0-9]+-\d+`); else the current branch name of the target repository; else ask.
- **Project**: the argument naming a project, matched against `projects` in the config or a
  directory under the repository root; `projectDir` is its absolute path (the directory holding
  the `.sln`/`.slnx`). Ask if ambiguous.
- **Description**: the rest of the arguments.

## 2. Design — `superpowers:brainstorming`

Invoke `superpowers:brainstorming` with the description. Keep its approval gate. Then:

- **spike** or **bounded** → no workflow. Finish the work in this session using
  `tests-writer` for tests and the `dotnet-code-review` skill for review. Stop here.
- **architectural** → continue.

## 3. Plan — `superpowers:writing-plans`

Invoke `superpowers:writing-plans`. Save the plan as `<plansDir>/<YYYY-MM-DD>-<TASK-KEY>.md`
(`plansDir` from config, default `temp/plans/`, resolved from the repository root — never inside
the target project's tracked tree). When the skill offers its **Execution Handoff** menu, do not
show it: go to step 4.

## 4. Execute — the `dotnet-sdd` workflow

Call `Workflow({ name: 'agentic-sdd-flow:dotnet-sdd', args: { project, projectDir, plan, taskKey } })`.
(This skill's instructions are the user's opt-in for the Workflow tool.) If the runtime reports
the name as unknown, the plugin was installed during this session — ask the user to restart
Claude Code, then retry.

## 5. Act on the result

- `status: 'done'` → invoke `superpowers:finishing-a-development-branch`; decline merge, push
  and PR; report the branch name, the commit range and `deferred` minors.
- `status: 'blocked'` → show `openQuestions` and `rulings` verbatim; wait for answers; rerun step
  4 with `args.answers = { "<taskId>": { "<question>": "<answer>" } }` and the same `resumeFromRunId` if the
  runtime offers one.
- `status: 'unstable'` → show `rulings` (parked/stalled findings) and `deferred`; ask whether to
  run another fix wave, park them, or stop.

Always finish with the branch name and "not pushed".
