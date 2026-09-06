#!/usr/bin/env python3
"""Agent pulse: what every running subagent is doing right now, for the status line.

Hook mode (`note`) — bound to PreToolUse, SubagentStart and SubagentStop. Reads the hook payload
on stdin; when it carries an `agent_id` (the call happened inside a subagent) it records the agent
type, start time, tool count and the last action in ${CLAUDE_PLUGIN_DATA}/pulse/<session_id>.json.
Never blocks, never writes to stdout: exit 0 on every path.

Render mode (`render`) — a status line command. Reads the status-line JSON on stdin, finds the
session's pulse file and prints one line such as
  ⟳ tests-writer 2m10s · Bash dotnet test (14)  |  ⟳ code-reviewer 0m40s · Read OrderService.cs (6)
Finished agents stay visible for a short while as ✓, then disappear.
"""

import fcntl
import json
import os
import sys
import time

DONE_VISIBLE_SECONDS = 120
STALE_AGENT_SECONDS = 4 * 3600
STALE_FILE_SECONDS = 24 * 3600
ACTION_WIDTH = 48


def pulse_dir():
    """Fixed per user, not per plugin data dir: the hook (inside the plugin) and the status line
    (outside it) must agree on the path even when only one of them sees CLAUDE_PLUGIN_DATA."""
    path = os.environ.get("ASF_PULSE_DIR") or os.path.join(os.path.expanduser("~"), ".agentic-sdd-flow", "pulse")
    os.makedirs(path, exist_ok=True)
    return path


def pulse_file(session_id):
    safe = "".join(ch for ch in str(session_id) if ch.isalnum() or ch in "-_") or "unknown"
    return os.path.join(pulse_dir(), safe + ".json")


def summarise(tool, tool_input):
    """`Bash dotnet test`, `Edit OrderService.cs`, `Grep IOrderRepository` — the shortest true phrase."""
    tool_input = tool_input or {}
    hint = ""
    if tool == "Bash":
        hint = str(tool_input.get("description") or tool_input.get("command") or "").split("\n", 1)[0]
    elif tool in ("Read", "Write", "Edit", "MultiEdit", "NotebookEdit"):
        hint = os.path.basename(str(tool_input.get("file_path") or tool_input.get("notebook_path") or ""))
    elif tool in ("Grep", "Glob"):
        hint = str(tool_input.get("pattern") or "")
    elif tool == "Agent":
        hint = str(tool_input.get("subagent_type") or tool_input.get("description") or "")
    elif tool == "Skill":
        hint = str(tool_input.get("skill") or "")
    elif tool and tool.startswith("mcp__"):
        tool = tool.split("__")[-1]
        hint = str(tool_input.get("query") or tool_input.get("name") or tool_input.get("symbolName") or "")
    text = (tool or "?") + (" " + hint if hint else "")
    return text if len(text) <= ACTION_WIDTH else text[:ACTION_WIDTH - 1] + "…"


def update(path, mutate):
    """Read-modify-write under an exclusive lock; parallel agents share one file."""
    with open(path, "a+", encoding="utf-8") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        handle.seek(0)
        try:
            state = json.loads(handle.read() or "{}")
        except ValueError:
            state = {}
        agents = state.setdefault("agents", {})
        mutate(agents)
        now = time.time()
        for agent_id in [k for k, v in agents.items() if now - v.get("last", now) > STALE_AGENT_SECONDS]:
            del agents[agent_id]
        handle.seek(0)
        handle.truncate()
        json.dump(state, handle)


def note(payload):
    agent_id = payload.get("agent_id")
    if not agent_id:
        return
    event = payload.get("hook_event_name")
    now = time.time()
    agent_type = str(payload.get("agent_type") or "agent").split(":")[-1]

    def mutate(agents):
        entry = agents.setdefault(agent_id, {"type": agent_type, "started": now, "tools": 0, "action": "starting", "status": "running"})
        entry["last"] = now
        if event == "SubagentStop":
            entry["status"] = "done"
            entry["action"] = "done"
        elif event in ("PreToolUse", "PostToolUse"):
            entry["tools"] += 1
            entry["action"] = summarise(payload.get("tool_name"), payload.get("tool_input"))

    update(pulse_file(payload.get("session_id")), mutate)


def prune_files():
    now = time.time()
    for name in os.listdir(pulse_dir()):
        path = os.path.join(pulse_dir(), name)
        try:
            if now - os.path.getmtime(path) > STALE_FILE_SECONDS:
                os.unlink(path)
        except OSError:
            pass


def elapsed(seconds):
    seconds = int(max(0, seconds))
    return "%dm%02ds" % divmod(seconds, 60) if seconds < 3600 else "%dh%02dm" % divmod(seconds // 60, 60)


def render(payload):
    path = pulse_file(payload.get("session_id"))
    if not os.path.exists(path):
        return ""
    try:
        with open(path, encoding="utf-8") as handle:
            agents = json.load(handle).get("agents", {})
    except (OSError, ValueError):
        return ""
    now = time.time()
    parts = []
    for entry in sorted(agents.values(), key=lambda e: e.get("started", 0)):
        if entry.get("status") == "done":
            if now - entry.get("last", 0) <= DONE_VISIBLE_SECONDS:
                parts.append("✓ %s %s" % (entry["type"], elapsed(entry["last"] - entry["started"])))
            continue
        parts.append("⟳ %s %s · %s (%d)" % (entry["type"], elapsed(now - entry["started"]), entry.get("action", ""), entry.get("tools", 0)))
    return "  |  ".join(parts)


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "note"
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        payload = {}
    try:
        if mode == "render":
            sys.stdout.write(render(payload))
        else:
            note(payload)
            if payload.get("hook_event_name") == "SubagentStop":
                prune_files()
    except Exception:  # a broken pulse must never break a tool call or the status line
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
