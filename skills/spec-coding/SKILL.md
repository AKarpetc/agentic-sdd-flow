---
name: spec-coding
description: Run the Spec-coding MCP workflow (spec-driven development). Starts with mcp__spec-coding__spec_coding_workflow_start and walks through goal → requirements → design → tasks → execution phases, with user confirmation gates between phases. Use when the user asks to "start spec coding", "spec workflow", "spec-driven development", or wants to develop a feature via formal spec phases.
---

# Spec-Coding Workflow

Drive a feature through the Spec-coding MCP's phased, spec-driven development workflow.

## How to run

1. **Load the MCP tool schemas** if they are deferred:
   use `ToolSearch` with query `select:mcp__spec-coding__spec_coding_workflow_start` (and other `mcp__spec-coding__*` tools as needed).

2. **Start the workflow** by calling `mcp__spec-coding__spec_coding_workflow_start` with the user's feature request / task description.

3. **Follow the instructions returned by the MCP exactly.** The server orchestrates the phases; do not skip ahead or invent your own phase order. The available phase tools are:

   | Phase | Start tool | Confirmation tool |
   |---|---|---|
   | Goal | (part of `spec_coding_workflow_start`) | `spec_coding_goal_confirmed` |
   | Requirements | `spec_coding_requirements_start` | `spec_coding_requirements_confirmed` |
   | Design | `spec_coding_design_start` | `spec_coding_design_confirmed` |
   | Tasks | `spec_coding_tasks_start` | `spec_coding_tasks_confirmed` |
   | Execution | `spec_coding_execute_start` | — |

4. **Confirmation gates**: at the end of each phase, present the produced artifact (goal statement, requirements, design, task list) to the user and get their explicit approval before calling the corresponding `*_confirmed` tool and moving to the next phase. Never call a `*_confirmed` tool without user sign-off.

5. **During execution**, follow the repo's global rules:
   - `${CLAUDE_PLUGIN_ROOT}/rules/code-convention.md` and the nearest `.editorconfig`
   - `${CLAUDE_PLUGIN_ROOT}/rules/test-convention.md` — delegate test authoring to the `tests-writer` agent
   - Use the `dotnet-code-review` skill for any review step

## Notes

- All `mcp__spec-coding` tools are pre-allowed in `.claude/settings.local.json` — they run without permission prompts.
- If the user provides a Jira ticket or spec doc, pass its content (or a summary) into `spec_coding_workflow_start` as the task context.
