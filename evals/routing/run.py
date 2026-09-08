#!/usr/bin/env python3
"""Routing evals: does a session with the plugin hand each kind of request to the right agent, skill or workflow?

Runs every case in evals/routing/cases.json as a headless `claude -p` session inside a throwaway copy of
the fixture repository, records the tool calls the top-level session makes, and checks them against the
case's expectations. Stand-in for `claude plugin eval` where that command is not enabled.

  python3 evals/routing/run.py [--case NAME ...] [--workers N] [--model MODEL] [--out DIR]
"""

import argparse
import concurrent.futures
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))


def load_cases(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def prepare_workspace(fixture, root, name):
    workspace = os.path.join(root, name)
    shutil.copytree(fixture, workspace, ignore=shutil.ignore_patterns("bin", "obj"))
    git = ["git", "-C", workspace, "-c", "user.name=evals", "-c", "user.email=evals@example.com"]
    subprocess.run(["git", "init", "-q", workspace], check=True)
    subprocess.run(git + ["add", "."], check=True)
    subprocess.run(git + ["commit", "-q", "-m", "fixture"], check=True)
    return workspace


def run_case(case, defaults, fixture, root, model, timeout):
    """`fixture` is the suite default; a case may point at another repository (a multi-service one, say)
    with its own `fixture` key, relative to this directory."""
    if case.get("fixture"):
        fixture = os.path.normpath(os.path.join(HERE, case["fixture"]))
    workspace = prepare_workspace(fixture, root, case["name"])
    allowed = list(defaults["allowed_tools"]) + list(case.get("allowed_tools_extra", []))
    command = ["claude", "-p", case["prompt"], "--output-format", "stream-json", "--verbose",
               "--max-turns", str(case.get("max_turns", defaults["max_turns"])),
               "--no-session-persistence", "--permission-mode", "acceptEdits",
               "--allowedTools", *allowed]
    if model:
        command += ["--model", model]
    # Same isolation as the benchmark: these cases exist to watch the sizing gate decide, so the host
    # repository's config — its overlay and above all its routing policy — must not reach the session.
    env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}
    env["CLAUDE_PROJECT_DIR"] = os.path.abspath(workspace)
    env["ASF_ROUTING_POLICY"] = "off"
    started = time.time()
    stream_path = os.path.join(root, case["name"] + ".stream.jsonl")
    timed_out = False
    with open(stream_path, "w", encoding="utf-8") as stream, open(stream_path + ".stderr", "w", encoding="utf-8") as errors:
        proc = subprocess.Popen(command, cwd=workspace, env=env, stdout=stream, stderr=errors, text=True)
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            proc.kill()
            proc.wait()
    with open(stream_path, encoding="utf-8") as handle:
        raw = handle.read()
    outcome = score(case, raw, workspace)
    if timed_out:
        outcome["subtype"] = "harness_timeout"
    outcome.update({"exit": proc.returncode, "seconds": round(time.time() - started, 1)})
    return outcome


def parse_stream(raw):
    """Top-level tool calls, subagent tool calls, assistant text and the result event of one session."""
    top, nested, texts, result = [], [], [], {}
    for line in raw.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if event.get("type") == "assistant":
            bucket = nested if event.get("parent_tool_use_id") else top
            for block in event.get("message", {}).get("content", []):
                if block.get("type") == "tool_use":
                    bucket.append((block["name"], json.dumps(block.get("input", {}), ensure_ascii=False)))
                elif block.get("type") == "text" and not event.get("parent_tool_use_id"):
                    texts.append(block.get("text", ""))
        elif event.get("type") == "result":
            result = event
    return top, nested, texts, result


def score(case, raw, workspace):
    """Applies the case's expectations to a recorded session. A session that hits max_turns after the
    right dispatch still passes: the harness judges who was handed the work, not whether it finished."""
    top, nested, texts, result = parse_stream(raw)
    checks = []

    def matches(rule):
        pattern = re.compile(rule["input"])
        return [f"{name} {inp[:160]}" for name, inp in top if name == rule["tool"] and pattern.search(inp)]

    if case.get("expect_any"):
        hits = [hit for rule in case["expect_any"] for hit in matches(rule)]
        checks.append(("expect_any", bool(hits), hits or ["no matching dispatch"]))
    for rule in case.get("forbid", []):
        hits = matches(rule)
        checks.append((f"forbid {rule['tool']} /{rule['input']}/", not hits, hits or ["clean"]))
    for needle in case.get("stream_contains", []):
        checks.append((f"stream contains {needle!r}", needle in raw, []))
    for pattern in case.get("text_regex", []):
        hit = re.search(pattern, "\n".join(texts), re.IGNORECASE | re.DOTALL) is not None
        checks.append((f"assistant text matches /{pattern}/", hit, []))
    for rule in case.get("file_absent", []):
        path = os.path.join(workspace, rule["path"])
        text = open(path, encoding="utf-8").read() if os.path.exists(path) else ""
        offending = re.search(rule["regex"], text) is not None
        checks.append((f"file {rule['path']} has no /{rule['regex']}/", os.path.exists(path) and not offending,
                       ["file missing"] if not os.path.exists(path) else []))

    return {
        "name": case["name"],
        "passed": all(ok for _, ok, _ in checks),
        "subtype": result.get("subtype"),
        "checks": [{"check": label, "ok": ok, "evidence": evidence} for label, ok, evidence in checks],
        "dispatches": [f"{name} {inp[:200]}" for name, inp in top if name in ("Agent", "Skill", "Workflow")],
        "subagent_calls": len(nested),
        "tool_calls": len(top),
        "turns": result.get("num_turns"),
        "cost_usd": result.get("total_cost_usd"),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--case", action="append", help="run only these case names (repeatable)")
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--model")
    parser.add_argument("--out", help="results directory (default: a temp directory)")
    parser.add_argument("--rescore", metavar="DIR", help="re-score the <case>.stream.jsonl files in DIR instead of running")
    parser.add_argument("--timeout", type=int, default=900, help="seconds per session; a timed-out session is scored on what it streamed")
    args = parser.parse_args()

    suite = load_cases(os.path.join(HERE, "cases.json"))
    fixture = os.path.normpath(os.path.join(HERE, suite["fixture"]))
    cases = [c for c in suite["cases"] if not args.case or c["name"] in args.case]
    root = args.rescore or args.out or tempfile.mkdtemp(prefix="routing-evals-")
    os.makedirs(root, exist_ok=True)

    results = []
    if args.rescore:
        for case in cases:
            stream = os.path.join(root, case["name"] + ".stream.jsonl")
            if not os.path.exists(stream):
                continue
            results.append(score(case, open(stream, encoding="utf-8").read(), os.path.join(root, case["name"])))
        return report(results, root)
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(run_case, c, suite["defaults"], fixture, root, args.model, args.timeout): c["name"] for c in cases}
        for future in concurrent.futures.as_completed(futures):
            name = futures[future]
            try:
                results.append(future.result())
            except Exception as exc:  # a harness failure is a result too
                results.append({"name": name, "passed": False, "checks": [], "dispatches": [], "error": repr(exc)})
            latest = results[-1]
            print(f"{'done' if latest['passed'] else 'FAIL'}  {latest['name']:22s} "
                  f"turns={latest.get('turns')} cost=${latest.get('cost_usd') or 0:.2f} {latest.get('seconds', 0)}s", flush=True)

    return report(results, root)


def report(results, root):
    results.sort(key=lambda r: r["name"])
    with open(os.path.join(root, "summary.json"), "w", encoding="utf-8") as handle:
        json.dump(results, handle, indent=2, ensure_ascii=False)
    failed = [r for r in results if not r["passed"]]
    total = sum(r.get("cost_usd") or 0 for r in results)
    for r in results:
        labels = []
        for d in r["dispatches"]:
            target = re.search(r"(agentic-sdd-flow:[a-z-]+|superpowers:[a-z-]+)", d)
            labels.append(d.split(" ", 1)[0] + " " + (target.group(1) if target else "?"))
        print(f"{'PASS' if r['passed'] else 'FAIL'}  {r['name']:22s} {str(r.get('subtype') or ''):17s} dispatch: {'; '.join(labels) or '-'}")
    print(f"\n{len(results) - len(failed)}/{len(results)} passed, ${total:.2f} total, results in {root}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
