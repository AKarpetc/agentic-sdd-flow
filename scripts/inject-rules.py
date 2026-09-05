#!/usr/bin/env python3
"""Injects the plugin's rules contract (and the project's overlay contract, if any).

Modes:
  session   SessionStart hook  — prints the contract to stdout (added to the session context).
  subagent  SubagentStart hook — emits JSON additionalContext for every dispatched agent.
  prompt    UserPromptSubmit   — prints the contract when the prompt starts a plan-driven flow.
"""

import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import asf_config  # noqa: E402

PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTRACT = os.path.join(PLUGIN_ROOT, "rules", "RULES-CONTRACT.md")
MIN_NAVIGATOR = (0, 8, 0)

PLAN_FLOW = re.compile(
    r"subagent-driven-development|executing-plans|writing-plans|test-driven-development"
    r"|spec-coding|execute\s+(?:the\s+)?plan|выполн\w*\s+план"
    r"|\bworkflow\b|ultracode|dotnet-sdd|architecture-design|dotnet-feature",
    re.IGNORECASE,
)

ROSLYN_ACCESS = """\
## Roslyn access
Default: run `{bin_dir}/roslyn-query.py <project-or-solution> <tool> '<json-args>'` through Bash
(also available as bare `roslyn-query.py` when the plugin's bin/ is on PATH). First call per solution:
`get_project_graph`. An empty result, or a solution path that is not the one you meant, is a mis-bind —
never "clean code". Run `roslyn-query.py <solution> --restart` after switching branches. The
`mcp__cwm-roslyn-navigator__*` tools are a fallback that serves only the pinned solution."""

SUBAGENT_HEADER = """\
<rules-contract enforcement="mandatory">
The rules below are project law: they outrank your task brief, your plan, and any skill you load.
Code that violates them is rejected by an automated hook on every Write/Edit, so writing it only
costs you a round trip.

Plugin root: {plugin_root} — agents/, skills/, rules/, knowledge/ and bin/ live under it; use
these absolute paths, never search the filesystem for them.

If you write or review C#, read the full rules before you start:
{rules_dir}/code-convention.md, single-type-per-file.md, common.md, test-convention.md
(and {rules_dir}/kit-overrides.md for where these conventions beat imported skill advice).

{roslyn}

{contract}
{overlay}
</rules-contract>"""

PROMPT_HEADER = """\
<rules-contract enforcement="mandatory">
This flow produces code that must follow the rules below. They outrank the plan and any skill
you load, and a Write/Edit hook rejects violations automatically.

You are the controller. Two obligations that only you can meet:
1. Copy this contract into the plan's **Global Constraints** section, and into the
   `[GLOBAL_CONSTRAINTS]` block of every implementer and reviewer dispatch. A subagent
   reviewing against a brief that omits these rules will approve violating code.
2. Treat a violation found in review as an Important finding — it enters the fix loop.

{contract}
{overlay}
</rules-contract>"""

SESSION_HEADER = """\
<rules-contract enforcement="mandatory">
These conventions are injected by the agentic-sdd-flow plugin. Full texts: {rules_dir}/.
Plugin root: {plugin_root} — agents/, skills/, rules/, knowledge/ and bin/ live under it; use
these absolute paths, never search the filesystem for them.
Entry point for feature work: /agentic-sdd-flow:dotnet-feature <TASK-KEY> <description>.
{navigator}
{contract}
{overlay}
</rules-contract>"""


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def overlay_block():
    root = asf_config.find_project_root()
    cfg = asf_config.load_config(root)
    path = asf_config.overlay_contract_path(root, cfg)
    if not path:
        return ""
    return "\n<overlay-contract source=\"%s\">\n%s\n</overlay-contract>" % (path, read(path))


def navigator_note():
    try:
        out = subprocess.run(["dotnet", "tool", "list", "--global"], capture_output=True,
                             text=True, timeout=8).stdout
    except (OSError, subprocess.SubprocessError):
        return "Roslyn navigator: `dotnet` not found — roslyn-query.py will fail until the .NET SDK is installed."
    match = re.search(r"cwm\.roslynnavigator\s+(\d+)\.(\d+)\.(\d+)", out, re.IGNORECASE)
    if not match:
        return "Roslyn navigator: CWM.RoslynNavigator is not installed; roslyn-query.py installs it on first use."
    version = tuple(int(part) for part in match.groups())
    if version < MIN_NAVIGATOR:
        return ("Roslyn navigator: CWM.RoslynNavigator %d.%d.%d is below 0.8.0 — run "
                "`dotnet tool update --global CWM.RoslynNavigator`." % version)
    return ""


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "subagent"
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        payload = {}
    if not os.path.exists(CONTRACT):
        return 0
    rules_dir = os.path.join(PLUGIN_ROOT, "rules")
    fields = {"rules_dir": rules_dir, "contract": read(CONTRACT), "overlay": overlay_block(),
              "roslyn": ROSLYN_ACCESS.format(bin_dir=os.path.join(PLUGIN_ROOT, "bin")),
              "navigator": navigator_note(), "plugin_root": PLUGIN_ROOT}

    if mode == "session":
        sys.stdout.write(SESSION_HEADER.format(**fields))
        return 0
    if mode == "prompt":
        if not PLAN_FLOW.search(payload.get("prompt", "")):
            return 0
        sys.stdout.write(PROMPT_HEADER.format(**fields))
        return 0
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "SubagentStart",
        "additionalContext": SUBAGENT_HEADER.format(**fields),
    }}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
