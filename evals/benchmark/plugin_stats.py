#!/usr/bin/env python3
"""Stage-level statistics for the plugin arm, read from the dotnet-sdd workflow records a session left behind.

  python3 evals/benchmark/plugin_stats.py <results-dir> [more dirs…] > plugin-stats.md

For every <task>-plugin.json outcome the script finds the session's workflow record under
~/.claude/projects/<workspace-as-dir>/<session>/workflows/wf_*.json and reports: phases that actually ran
(Debug in particular), fix rounds per task and rounds that closed nothing, plan and final review verdicts,
deferred findings, the agents with the largest seconds-per-tool-call ratio, and whether the agents were
prompted with an undefined working directory (the skill passing `args` as a string).
"""

import glob
import json
import os
import re
import sys


def session_of(stream_path):
    with open(stream_path, encoding="utf-8") as handle:
        for line in handle:
            match = re.search(r'"session_id":\s*"([^"]+)"', line)
            if match:
                return match.group(1)
    return None


def workflow_records(workspace, session):
    project_dir = os.path.join(os.path.expanduser("~/.claude/projects"), os.path.abspath(workspace).replace("/", "-"))
    paths = sorted(glob.glob(os.path.join(project_dir, session, "workflows", "wf_*.json")), key=os.path.getmtime)
    return [json.load(open(path, encoding="utf-8")) for path in paths]


def agents_of(record):
    return [x for x in record.get("workflowProgress", []) if x.get("type") == "workflow_agent"]


def describe(outcome, record):
    result = record.get("result") or {}
    agents = agents_of(record)
    phases = sorted({a.get("phaseTitle") for a in agents if a.get("phaseTitle")})
    labels = [a.get("label", "") for a in agents]
    logs = record.get("logs") or []
    lines = []
    lines.append("- **workflow** `%s`: %s, %.1f min, %d agents, %d tool calls, %s tokens" % (
        record.get("runId"), record.get("status"), (record.get("durationMs") or 0) / 60000, len(agents), record.get("totalToolCalls") or 0,
        "{:,}".format(record.get("totalTokens") or 0)))
    lines.append("- **phases that ran**: " + ", ".join(phases))
    lines.append("- **Debug phase**: " + ("ran (%s)" % ", ".join(l for l in labels if l.startswith("debug")) if any(l.startswith("debug") for l in labels) else "did not run"))
    fix_rounds = {d["task"]: d.get("rounds", 0) for d in result.get("done", [])}
    lines.append("- **fix rounds per task**: " + (", ".join("task %s: %s" % (t, r) for t, r in sorted(fix_rounds.items())) or "–")
                 + "; fix agents: %d, repair agents: %d" % (sum(l.startswith("fix#") for l in labels), sum(l.startswith("repair#") for l in labels)))
    stalled = [l for l in logs if "without progress" in l or "fix cap reached" in l]
    lines.append("- **rounds that closed nothing**: " + (("; ".join(stalled)) if stalled else "none"))
    plan = result.get("planVerdict") or {}
    plan_findings = plan.get("findings") or []
    lines.append("- **plan review (workflow phase)**: %s, %d finding(s): %s" % (
        "approved" if plan.get("approved") else ("rejected" if plan else "–"), len(plan_findings),
        ", ".join("%s/%s" % (f.get("severity"), f.get("area", "")) for f in plan_findings) or "–"))
    final = result.get("finalVerdict") or {}
    lines.append("- **final review**: %s, %d finding(s)" % ("approved" if final.get("approved") else ("not approved" if final else "–"), len(final.get("findings") or [])))
    lines.append("- **rulings**: " + (", ".join("task %s %s" % (r.get("task", r.get("stage")), r.get("status")) for r in result.get("rulings", [])) or "none")
                 + "; **deferred minors**: %d; **open questions**: %d" % (len(result.get("deferred") or []), len(result.get("openQuestions") or [])))
    undefined = sum(1 for a in agents if "undefined" in (a.get("promptPreview") or ""))
    if undefined:
        lines.append("- ⚠️ **%d/%d agent prompts contain `undefined`** (the skill passed `args` as a JSON string, so `args.project` / `args.projectDir` were undefined inside the script)" % (undefined, len(agents)))
    lines.append("- **workflow log**: " + " · ".join(logs))
    ratio = sorted(agents, key=lambda a: -((a.get("durationMs") or 0) / 1000) / max(a.get("toolCalls") or 1, 1))
    lines.append("")
    lines.append("| agent | phase | state | time | tool calls | s / tool | tokens |")
    lines.append("|---|---|---|---|---|---|---|")
    for a in ratio[:8]:
        seconds = (a.get("durationMs") or 0) / 1000
        lines.append("| %s (%s) | %s | %s | %.1f min | %s | %.0f | %s |" % (
            a.get("label"), (a.get("agentType") or "workflow-subagent").replace("agentic-sdd-flow:", ""), a.get("phaseTitle"), a.get("state"),
            seconds / 60, a.get("toolCalls") or 0, seconds / max(a.get("toolCalls") or 1, 1), "{:,}".format(a.get("tokens") or 0)))
    return lines


def main():
    out = ["# Plugin arm — workflow stage statistics", ""]
    for d in sys.argv[1:]:
        for path in sorted(glob.glob(os.path.join(d, "*-plugin.json"))):
            outcome = json.load(open(path, encoding="utf-8"))
            if outcome.get("arm") != "plugin":
                continue
            stream = os.path.join(d, "%s-plugin.stream.jsonl" % outcome["task"])
            session = session_of(stream) if os.path.exists(stream) else None
            records = workflow_records(outcome["workspace"], session) if session else []
            out.append("## %s — %s (%s)" % (outcome["task"], os.path.basename(d.rstrip("/")), outcome["metrics"].get("reportedStatus") or outcome["metrics"].get("subtype")))
            out.append("")
            skill_dispatches = [x for x in outcome["metrics"].get("dispatches", []) if x["tool"] == "Agent" and "plan-reviewer" in x["label"]]
            out.append("- **plan review from the skill (before the workflow)**: %d dispatch(es)" % len(skill_dispatches))
            if not records:
                out.append("- no workflow record found for session %s" % session)
            for record in records:
                out += describe(outcome, record)
            out.append("")
    print("\n".join(out))


if __name__ == "__main__":
    main()
