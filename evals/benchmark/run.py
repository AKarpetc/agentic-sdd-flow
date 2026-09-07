#!/usr/bin/env python3
"""End-to-end benchmark: the same feature tasks with superpowers alone and with this plugin.

  python3 evals/benchmark/run.py --task T1 [--task T2 ...] [--arm baseline --arm plugin] --out DIR [--timeout 5400]

Every (task, arm) runs a headless `claude -p` session in a fresh copy of evals/benchmark/fixture, streams the
session to <out>/<task>-<arm>.stream.jsonl with an arrival timestamp per event, then runs acceptance.py on
the workspace and writes <out>/<task>-<arm>.json with session metrics, a per-agent timeline and the checks.
"""

import argparse
import concurrent.futures
import json
import os
import re
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURE = os.path.join(HERE, "fixture")
TASKS = os.path.join(HERE, "tasks")
ACCEPTANCE = os.path.join(HERE, "acceptance.py")
MANIFEST = json.load(open(os.path.join(TASKS, "tasks.json"), encoding="utf-8"))
KEYS = {task: meta["key"] for task, meta in MANIFEST.items()}
TOOLS = ["Bash", "Read", "Write", "Edit", "MultiEdit", "Glob", "Grep", "Agent", "Skill", "Workflow", "TodoWrite", "TaskOutput", "Monitor"]


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def prompt_for(task, arm):
    title = read(os.path.join(TASKS, task + ".md")).splitlines()[0].lstrip("# ").split("—", 1)[-1].strip()
    return "\n\n".join([
        read(os.path.join(TASKS, "_preamble.md")).strip(),
        "Process for this run: " + arm["instruction"].replace("<TASK-KEY>", KEYS[task]).replace("<title>", title),
        read(os.path.join(TASKS, task + ".md")).strip(),
    ])


def prepare_workspace(root, name):
    workspace = os.path.join(root, name)
    shutil.copytree(FIXTURE, workspace, ignore=shutil.ignore_patterns("bin", "obj"))
    git = ["git", "-C", workspace, "-c", "user.name=bench", "-c", "user.email=bench@example.com"]
    subprocess.run(["git", "init", "-q", "-b", "main", workspace], check=True)
    subprocess.run(git + ["add", "."], check=True)
    subprocess.run(git + ["commit", "-q", "-m", "fixture"], check=True)
    subprocess.run(git + ["tag", "fixture"], check=True)
    return workspace


def session_env():
    """Environment for a headless session: not nested in a Claude Code session, and no idle ceiling on background work.

    `claude -p` keeps running while a background Workflow or Agent is alive, but by default gives up after
    10 minutes of "idle waiting" (CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS) and aborts the work — the plugin arm's
    dotnet-sdd workflow was killed mid-agent that way. The runner's own --timeout still bounds the session.
    """
    env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}
    env.setdefault("CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS", "0")
    return env


def session_command(arm, max_turns, model=None):
    """`claude -p` argv without the prompt: the prompt goes in on stdin. `model` pins both arms to one model —
    without it the session takes the user's default, and the 0.2.7 measurement ended up with T1–T3 on one model
    and T4 on another.

    With the prompt in argv, every session's command line contains the fixture's project name, and a
    neighbouring session's `pkill -f "Orders.Api"` after a smoke test SIGTERMs this session too (exit 143,
    the background workflow aborted mid-agent) — that is how four plugin-arm runs died in the first measurement.
    """
    command = ["claude", "-p", "--output-format", "stream-json", "--verbose", "--max-turns", str(max_turns),
               "--no-session-persistence", "--permission-mode", "acceptEdits", "--allowedTools", *TOOLS]
    if model:
        command += ["--model", model]
    if arm.get("settings"):
        command += ["--settings", json.dumps(arm["settings"])]
    return command


def run_session(prompt, workspace, arm, stream_path, timeout, max_turns, model=None):
    command = session_command(arm, max_turns, model)
    env = session_env()
    started = time.time()
    timed_out = False
    with open(stream_path, "w", encoding="utf-8") as stream, open(stream_path + ".stderr", "w", encoding="utf-8") as errors:
        proc = subprocess.Popen(command, cwd=workspace, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=errors, text=True)
        proc.stdin.write(prompt)
        proc.stdin.close()
        try:
            for line in proc.stdout:  # arrival time per event: the stream carries none of its own
                stream.write(json.dumps({"t": round(time.time() - started, 2)}) + "\t" + line.rstrip("\n") + "\n")
                stream.flush()
                if time.time() - started > timeout:
                    timed_out = True
                    proc.kill()
                    break
            proc.wait(timeout=60)
        except Exception:
            proc.kill()
    return {"wallSeconds": round(time.time() - started, 1), "timedOut": timed_out, "exit": proc.returncode, "model": model or "default"}


def workflow_args(inp):
    """`mode` / `scope` decide which route the plugin took; callers pass args as an object or as a JSON string."""
    raw = inp.get("args")
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except ValueError:
            raw = None
    if not isinstance(raw, dict):
        return {}
    return {key: raw[key] for key in ("mode", "scope") if key in raw}


def route_taken(dispatches):
    """The tier the plugin arm actually ran, read off its own dispatches — never off what the session claims."""
    workflows = [d for d in dispatches if d["tool"] == "Workflow"]
    if any("architecture-design" in d["label"] for d in workflows):
        return "deep"
    sdd = [d for d in workflows if "dotnet-sdd" in d["label"]]
    if not sdd:
        return "quick"
    return "light" if any(d.get("mode") == "light" for d in sdd) else "standard"


def parse_stream(stream_path):
    events = []
    for line in open(stream_path, encoding="utf-8"):
        try:
            meta, raw = line.split("\t", 1)
            events.append((json.loads(meta)["t"], json.loads(raw)))
        except (ValueError, KeyError):
            continue
    result, top_calls, nested_calls, dispatches, final_text = {}, {}, {}, [], ""
    segments = []  # one `result` event per time the model yielded; the session resumes when a background task reports
    agents = {}  # tool_use_id -> {type, description, start, last, tools}
    for t, ev in events:
        kind = ev.get("type")
        if kind == "assistant":
            parent = ev.get("parent_tool_use_id")
            for block in ev.get("message", {}).get("content", []):
                if block.get("type") == "tool_use":
                    name = block["name"]
                    bucket = nested_calls if parent else top_calls
                    bucket[name] = bucket.get(name, 0) + 1
                    if parent and parent in agents:
                        agents[parent]["last"] = t
                        agents[parent]["tools"] += 1
                    if not parent and name in ("Agent", "Skill", "Workflow"):
                        inp = block.get("input", {})
                        label = inp.get("subagent_type") or inp.get("skill") or inp.get("name") or inp.get("scriptPath") or "?"
                        dispatch = {"t": t, "tool": name, "label": label, "description": inp.get("description", "")[:80]}
                        if name == "Workflow":
                            dispatch.update(workflow_args(inp))
                        dispatches.append(dispatch)
                        if name == "Agent":
                            agents[block["id"]] = {"type": label, "description": inp.get("description", "")[:80], "start": t, "last": t, "tools": 0}
                elif block.get("type") == "text" and not parent:
                    final_text = block.get("text", "")
        elif kind == "result":
            result = ev
            segments.append(ev.get("num_turns") or 0)
    usage = result.get("usage", {})
    status = re.search(r"STATUS:\s*(\w+)", final_text)
    return {
        "subtype": result.get("subtype"), "turns": sum(segments) or result.get("num_turns"), "segments": len(segments),
        "costUsd": result.get("total_cost_usd"),
        "tokens": {"input": usage.get("input_tokens"), "output": usage.get("output_tokens"),
                   "cacheRead": usage.get("cache_read_input_tokens"), "cacheCreation": usage.get("cache_creation_input_tokens")},
        "durationApiMs": result.get("duration_api_ms"), "modelUsage": result.get("modelUsage"),
        "topLevelTools": top_calls, "nestedTools": nested_calls, "dispatches": dispatches, "route": route_taken(dispatches),
        "agents": [dict(v, seconds=round(v["last"] - v["start"], 1)) for v in agents.values()],
        "reportedStatus": status.group(1) if status else None, "finalText": final_text[-1500:],
    }


def pulse_for(stream_path):
    """The plugin arm's agent pulse (workflow agents do not appear as nested events in the stream)."""
    session = None
    for line in open(stream_path, encoding="utf-8"):
        match = re.search(r'"session_id":\s*"([^"]+)"', line)
        if match:
            session = match.group(1)
            break
    if not session:
        return None
    path = os.path.expanduser("~/.agentic-sdd-flow/pulse/%s.json" % session)
    if not os.path.exists(path):
        return None
    agents = json.load(open(path)).get("agents", {})
    return [{"type": v["type"], "seconds": round(v.get("last", 0) - v.get("started", 0), 1), "tools": v.get("tools", 0), "status": v.get("status")} for v in agents.values()]


def run_pair(task, arm_name, arm, root, timeout, max_turns, port, model=None):
    name = "%s-%s" % (task, arm_name)
    workspace = prepare_workspace(root, name)
    stream_path = os.path.join(root, name + ".stream.jsonl")
    session = run_session(prompt_for(task, arm), workspace, arm, stream_path, timeout, max_turns, model)
    metrics = parse_stream(stream_path)
    pulse = pulse_for(stream_path) if arm_name == "plugin" else None
    acceptance = subprocess.run([sys.executable, ACCEPTANCE, task, workspace, "--port", str(port)], capture_output=True, text=True, timeout=1800)
    try:
        checks = json.loads(acceptance.stdout)
    except ValueError:
        checks = {"error": acceptance.stdout[-800:] + acceptance.stderr[-800:]}
    outcome = {"task": task, "arm": arm_name, "label": arm["label"], "taskMeta": MANIFEST.get(task, {}),
               "session": session, "metrics": metrics, "pulse": pulse, "acceptance": checks, "workspace": workspace}
    with open(os.path.join(root, name + ".json"), "w", encoding="utf-8") as handle:
        json.dump(outcome, handle, indent=2, ensure_ascii=False)
    acc = checks.get("acceptance", {})
    print("done  %-12s %-9s wall=%.0fs cost=$%.2f turns=%s acceptance=%s/%s build=%s tests=%s/%s route=%s (expected %s)" % (
        task, arm_name, session["wallSeconds"], metrics["costUsd"] or 0, metrics["turns"], acc.get("passed"), acc.get("total"),
        checks.get("build", {}).get("ok"), checks.get("tests", {}).get("passed"), checks.get("tests", {}).get("total"),
        metrics["route"] if arm_name == "plugin" else "-", MANIFEST.get(task, {}).get("expectedTier", "?")), flush=True)
    return outcome


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--task", action="append", help="task id from tasks/tasks.json; repeatable")
    parser.add_argument("--class", dest="klass", action="append", choices=sorted({m["class"] for m in MANIFEST.values()}),
                        help="run every task of this class (simple/medium/complex/vague); repeatable")
    parser.add_argument("--arm", action="append")
    parser.add_argument("--out", required=True)
    parser.add_argument("--timeout", type=int, default=5400)
    parser.add_argument("--max-turns", type=int, default=120)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--port-base", type=int, default=5200, help="first acceptance port; give each concurrent runner its own range")
    parser.add_argument("--model", help="pin both arms to one model id (recorded in session.model); default: the CLI's default")
    args = parser.parse_args()
    arms = json.load(open(os.path.join(TASKS, "arms.json")))
    tasks = list(args.task or [])
    for klass in args.klass or []:
        tasks += [task for task, meta in MANIFEST.items() if meta["class"] == klass and task not in tasks]
    if not tasks:
        parser.error("give at least one --task or --class")
    selected = [(t, a) for t in sorted(set(tasks), key=lambda t: list(MANIFEST).index(t) if t in MANIFEST else 99) for a in (args.arm or list(arms))]
    os.makedirs(args.out, exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(run_pair, t, a, arms[a], args.out, args.timeout, args.max_turns, args.port_base + i, args.model) for i, (t, a) in enumerate(selected)]
        for future in concurrent.futures.as_completed(futures):
            try:
                future.result()
            except Exception as exc:
                print("FAILED", repr(exc), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
