#!/usr/bin/env python3
"""PreToolUse gate: an orientation call that the run's context pack already answers is redirected to the pack.

Subagents cannot share context; they share the filesystem. The dotnet-sdd workflow writes one
`.superpowers/sdd/context-pack.md` per run (solution layout, packages, endpoints, DI, the test project,
the build/test commands) and hands its path to every agent. Without enforcement each agent still
re-derives all of it — on the 0.2.8 benchmark that orientation was paid ~25 times in one run.

This hook denies the *repeat*: the first time an agent asks for something the pack states, the tool call
is refused and the pack's own text is handed back in the refusal, so the agent gets the answer without a
round trip. Ask a second time for the same thing and it goes through — the pack may be wrong or stale,
and a hook must never be a dead end.

Reads the PreToolUse payload on stdin, prints a permission decision on stdout.
"""

import json
import os
import re
import sys

PACK_RELATIVE = os.path.join(".superpowers", "sdd", "context-pack.md")
STATE_DIR = os.path.expanduser("~/.agentic-sdd-flow/packgate")

# tool → (regex that recognises the question, heading keywords whose pack section answers it)
TOPICS = (
    ("graph", re.compile(r"get_project_graph|get_dependency_graph"), ("solution", "project", "framework")),
    ("packages", re.compile(r"get_nuget_packages"), ("package", "nuget", "convention")),
    ("endpoints", re.compile(r"get_endpoint_map"), ("entry point", "endpoint", "route")),
    ("di", re.compile(r"get_di_registrations"), ("di", "registration", "entry point")),
)
ORIENTATION_TOOLS = re.compile(r"^mcp__(?:plugin_agentic-sdd-flow_)?cwm-roslyn-navigator__(\w+)$")


def payload():
    try:
        return json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return {}


def question(tool_name, tool_input):
    """The orientation topic this call asks about, or None when the call is real work."""
    probe = ""
    match = ORIENTATION_TOOLS.match(tool_name or "")
    if match:
        probe = match.group(1)
    elif tool_name == "Bash":
        command = str(tool_input.get("command", ""))
        if "roslyn-query.py" not in command:
            return None
        probe = command
    else:
        return None
    for topic, pattern, headings in TOPICS:
        if pattern.search(probe):
            return topic, headings
    return None


def find_pack(cwd):
    """The pack of the run this agent belongs to: beside the working directory, or at the repo root above it."""
    override = os.environ.get("ASF_CONTEXT_PACK")
    if override and os.path.isfile(override):
        return override
    directory = os.path.abspath(cwd or os.getcwd())
    for _ in range(4):
        candidate = os.path.join(directory, PACK_RELATIVE)
        if os.path.isfile(candidate):
            return candidate
        parent = os.path.dirname(directory)
        if parent == directory:
            break
        directory = parent
    return None


def section(text, headings):
    """The pack's own words on this topic — headings match loosely, because the pack is written by a model."""
    blocks, current, title = [], [], ""
    for line in text.splitlines():
        if re.match(r"^\s*(#{1,6}\s|[-*]\s*\*\*)", line) and current:
            blocks.append((title, current))
            current, title = [], line
        elif re.match(r"^\s*(#{1,6}\s|[-*]\s*\*\*)", line):
            title = line
            current = [line]
        else:
            current.append(line)
    if current:
        blocks.append((title, current))
    hits = []
    for title, lines in blocks:
        haystack = (title + " " + " ".join(lines[:2])).lower()
        if any(word in haystack for word in headings):
            hits.append("\n".join(lines).strip())
    return "\n\n".join(hits)[:4000]


def already_asked(session, topic):
    """One refusal per topic per session; the second identical question is allowed through."""
    if not session:
        return False
    path = os.path.join(STATE_DIR, "%s.json" % re.sub(r"[^A-Za-z0-9_.-]", "_", session))
    try:
        state = json.load(open(path, encoding="utf-8"))
    except (OSError, ValueError):
        state = {}
    seen = topic in state
    state[topic] = state.get(topic, 0) + 1
    try:
        os.makedirs(STATE_DIR, exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(state, handle)
    except OSError:
        pass
    return seen


def record(pack, topic, tool, outcome):
    """One line per orientation attempt, next to the pack: the evidence for whether agents take context
    from disk or rebuild it. Never fails the hook — a log that breaks a tool call is worse than no log."""
    try:
        with open(os.path.join(os.path.dirname(pack), "packgate.log"), "a", encoding="utf-8") as handle:
            handle.write("%s\t%s\t%s\n" % (outcome, topic, tool))
    except OSError:
        pass


def deny(reason):
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": reason,
    }}))
    return 0


def main():
    data = payload()
    asked = question(data.get("tool_name"), data.get("tool_input") or {})
    if not asked:
        return 0
    topic, headings = asked
    pack = find_pack(data.get("cwd"))
    if not pack:
        return 0
    try:
        text = open(pack, encoding="utf-8").read()
    except OSError:
        return 0
    answer = section(text, headings)
    if not answer or re.search(r"\bunknown\b", answer, re.IGNORECASE):
        record(pack, topic, data.get("tool_name", "?"), "unanswered")
        return 0  # the pack does not answer this one: derive it, and say so in your report
    if already_asked(data.get("session_id"), topic):
        record(pack, topic, data.get("tool_name", "?"), "second-ask-allowed")
        return 0  # asked twice: the pack may be wrong, let the agent check for itself
    record(pack, topic, data.get("tool_name", "?"), "redirected")
    return deny(
        "This run already answered that. Do not re-derive the %s — it is in the context pack at %s, "
        "which is authoritative for this run:\n\n%s\n\nUse it and spend your tool calls on the code your task "
        "is about. If a line of it is wrong, say so in your report and ask again — the second identical call "
        "goes through." % (topic, pack, answer))


if __name__ == "__main__":
    sys.exit(main())
