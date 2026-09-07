#!/usr/bin/env python3
"""Turns benchmark outcome files into one Markdown comparison: per task, per arm, per stage.

  python3 evals/benchmark/report.py <results-dir> [more dirs…] > report.md
"""

import glob
import json
import os
import sys
from collections import defaultdict

FIXTURE_BLOCKING = 4  # fallback for outcomes written before acceptance.py recorded the fixture's own count
FIXTURES = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures.json"), encoding="utf-8"))
MANIFEST = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "tasks", "tasks.json"), encoding="utf-8"))


def load(dirs):
    rows = []
    for d in dirs:
        for path in sorted(glob.glob(os.path.join(d, "*.json"))):
            with open(path, encoding="utf-8") as handle:
                data = json.load(handle)
            if isinstance(data, dict) and "task" in data and "arm" in data:
                rows.append(data)
    return rows


def money(v):
    return "$%.2f" % v if isinstance(v, (int, float)) else "–"


def minutes(seconds):
    return "%.1f min" % (seconds / 60) if isinstance(seconds, (int, float)) else "–"


def tokens(m):
    t = m.get("tokens") or {}
    return "%s in / %s out / %s cache" % (fmt(t.get("input")), fmt(t.get("output")), fmt((t.get("cacheRead") or 0) + (t.get("cacheCreation") or 0)))


def fmt(n):
    return "{:,}".format(n) if isinstance(n, (int, float)) else "–"


def table(headers, rows):
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    out += ["| " + " | ".join(str(c) for c in row) + " |" for row in rows]
    return "\n".join(out)


def model_cost(m):
    """Sum of per-model costs; `total_cost_usd` under-counts sessions whose agents ran in a Workflow."""
    usage = m.get("modelUsage") or {}
    costs = [v.get("costUSD") for v in usage.values() if isinstance(v, dict) and isinstance(v.get("costUSD"), (int, float))]
    return sum(costs) if costs else None


def route_cell(r):
    """What the run actually did (plugin arm only) against what the task should have cost."""
    if r["arm"] != "plugin":
        return "–"
    expected = (r.get("taskMeta") or MANIFEST.get(r["task"], {})).get("expectedTier")
    route = r["metrics"].get("route")
    if not route:
        return "–"
    return route if route == expected or not expected else "%s (expected %s)" % (route, expected)


def baseline_blocking(r):
    """The violations the task's own fixture already carries — the Δ counts only what a run added."""
    conv = (r.get("acceptance") or {}).get("conventions") or {}
    if isinstance(conv.get("baselineBlocking"), int):
        return conv["baselineBlocking"]
    fixture = (r.get("taskMeta") or MANIFEST.get(r["task"], {})).get("fixture", "orders")
    return FIXTURES.get(fixture, {}).get("baselineBlocking", FIXTURE_BLOCKING)


def outcome_row(r):
    m, a = r["metrics"], r.get("acceptance", {})
    acc = a.get("acceptance", {})
    conv = a.get("conventions", {})
    git = a.get("git", {})
    tests = a.get("tests", {})
    agents = m.get("pulse") or m.get("agents") or []
    quality = a.get("quality") or {}
    return [
        r["label"] + ("" if (r.get("repeat") or 1) <= 1 else " ·r%d" % r["repeat"]) + (" ·forced %s" % r["forcedTier"] if r.get("forcedTier") else ""),
        route_cell(r),
        (m.get("reportedStatus") or m.get("subtype") or "–") + (" ⏱timeout" if r["session"].get("timedOut") else "")
        + (" ☠SIGTERM" if r["session"].get("exit") == 143 else ""),
        minutes(r["session"].get("wallSeconds")), money(m.get("costUsd")), money(model_cost(m)), tokens(m), m.get("turns") or "–",
        len(r.get("pulse") or []) or sum(1 for d in m.get("dispatches", []) if d["tool"] == "Agent"),
        sum((m.get("topLevelTools") or {}).values()) + sum((m.get("nestedTools") or {}).values()),
        "✅" if a.get("build", {}).get("ok") else "❌",
        "%s/%s" % (tests.get("passed", "–"), tests.get("total", "–")),
        "%s/%s" % (acc.get("passed", "–"), acc.get("total", "–")),
        "✅" if a.get("plantedBugFixed") else "❌",
        "%s%s" % (quality.get("testCases", "–"), "" if quality.get("reachesTheEndpoint") is None else (" ✅http" if quality.get("reachesTheEndpoint") else " ❌http")),
        "%+d" % (conv.get("blocking", 0) - baseline_blocking(r)) if conv else "–",
        "%s (%s ok)" % (git.get("commits", "–"), git.get("wellFormed", "–")),
    ]


def stage_rows(r):
    rows = []
    for d in r["metrics"].get("dispatches", []):
        rows.append(["%.1f" % (d["t"] / 60), d["tool"], d["label"], d.get("description", "")])
    return rows


def agent_rows(r):
    src = r.get("pulse") or r["metrics"].get("agents") or []
    rows = sorted(src, key=lambda a: -a.get("seconds", 0))
    return [[a.get("type"), "%.1f min" % (a.get("seconds", 0) / 60), a.get("tools", 0), a.get("description", a.get("status", ""))] for a in rows[:12]]


def main():
    rows = load(sys.argv[1:])
    by_task = defaultdict(list)
    for r in rows:
        by_task[r["task"]].append(r)
    out = ["# Benchmark: superpowers alone vs agentic-sdd-flow", ""]
    headers = ["arm", "route", "status", "wall", "cost", "Σ model cost", "tokens", "turns", "agents", "tool calls", "build", "own tests", "acceptance", "planted bug", "tests written", "Δ violations", "commits"]
    totals = defaultdict(lambda: {"cost": 0.0, "model_cost": 0.0, "wall": 0.0, "acc": 0, "acc_total": 0, "bugs": 0, "n": 0})
    for task in sorted(by_task):
        meta = MANIFEST.get(task, {})
        heading = "## %s%s" % (task, " — %s, %s (expected tier: %s)" % (meta["key"], meta["class"], meta["expectedTier"]) if meta else "")
        out += [heading, "", table(headers, [outcome_row(r) for r in sorted(by_task[task], key=lambda r: r["arm"])]), ""]
        for r in sorted(by_task[task], key=lambda r: r["arm"]):
            t = totals[r["arm"]]
            t["cost"] += r["metrics"].get("costUsd") or 0
            t["model_cost"] += model_cost(r["metrics"]) or 0
            t["wall"] += r["session"].get("wallSeconds") or 0
            acc = r.get("acceptance", {}).get("acceptance", {})
            t["acc"] += acc.get("passed", 0) or 0
            t["acc_total"] += acc.get("total", 0) or 0
            t["bugs"] += 1 if r.get("acceptance", {}).get("plantedBugFixed") else 0
            t["n"] += 1
            out += ["### %s — stages (minute of dispatch)" % r["label"], "", table(["min", "tool", "target", "description"], stage_rows(r)) or "_no dispatches_", ""]
            agents = agent_rows(r)
            if agents:
                out += ["Longest agents:", "", table(["agent", "time", "tool calls", "note"], agents), ""]
            conflict = r.get("conflict")
            if conflict:
                q = r.get("acceptance", {}).get("quality", {})
                wrong_way = q.get("docRewrittenTowardBrief") or q.get("docRewrittenTowardCode")
                out += ["Conflict (truth = %s): noticed in the final message %s · records touched: %s · doc rewritten the wrong way %s · ADR touched %s · CI smoke now expects %s · code filters cancelled %s" % (
                    conflict.get("truth"), "✅" if conflict.get("noticedInFinalMessage") else "❌", ", ".join(q.get("recordsTouched") or []) or "none",
                    "❌ yes" if wrong_way else "✅ no", "yes" if q.get("adrTouched") else "no", q.get("ciSmokeExpects"), q.get("reportServiceFiltersCancelled")), ""]
            quality = r.get("acceptance", {}).get("quality", {})
            if quality.get("servicesTouched") is not None:
                out += ["Reach: services touched %s · contracts %s · migrations added %s · applied migrations edited %s · "
                        "inventory stock writes %s · checkout calls the stock endpoint %s · hard-coded peer urls %s · "
                        "ADR-0001 edited %s · decisions added %s" % (
                            ", ".join(quality.get("servicesTouched") or []) or "none",
                            len(quality.get("contractsTouched") or []),
                            ", ".join(quality.get("migrationsAdded") or []) or "none",
                            "❌ " + ", ".join(quality["appliedMigrationsEdited"]) if quality.get("appliedMigrationsEdited") else "✅ no",
                            quality.get("inventoryStockWrites"),
                            "❌ yes" if quality.get("checkoutTouchesStockEndpoint") else "✅ no",
                            "❌ " + str(quality["hardcodedPeerUrls"]) if quality.get("hardcodedPeerUrls") else "✅ none",
                            "❌ yes" if quality.get("adr0001Edited") else "✅ no",
                            ", ".join(quality.get("decisionsAdded") or []) or "none"), ""]
            failed = [c for c in r.get("acceptance", {}).get("acceptance", {}).get("checks", []) if not c["ok"]]
            if failed:
                out += ["Failed acceptance checks:", ""] + ["- %s — %s" % (c["name"], c["detail"][:140]) for c in failed] + [""]
    out += ["## Totals", "", table(["arm", "runs", "cost", "Σ model cost", "wall", "acceptance", "planted bugs fixed", "Σ model cost per passed check"],
                                    [[arm, t["n"], money(t["cost"]), money(t["model_cost"]), minutes(t["wall"]), "%d/%d" % (t["acc"], t["acc_total"]), "%d/%d" % (t["bugs"], t["n"]),
                                      money(t["model_cost"] / t["acc"]) if t["acc"] else "–"] for arm, t in sorted(totals.items())]), ""]
    by_class = defaultdict(lambda: defaultdict(lambda: {"cost": 0.0, "acc": 0, "acc_total": 0, "n": 0}))
    for r in rows:
        klass = (r.get("taskMeta") or MANIFEST.get(r["task"], {})).get("class", "?")
        cell = by_class[klass][r["arm"]]
        cell["cost"] += model_cost(r["metrics"]) or r["metrics"].get("costUsd") or 0
        acc = r.get("acceptance", {}).get("acceptance", {})
        cell["acc"] += acc.get("passed", 0) or 0
        cell["acc_total"] += acc.get("total", 0) or 0
        cell["n"] += 1
    if by_class:
        order = ["simple", "medium", "complex", "vague", "conflict"]
        class_rows = []
        for klass in sorted(by_class, key=lambda k: order.index(k) if k in order else 99):
            for arm, cell in sorted(by_class[klass].items()):
                class_rows.append([klass, arm, cell["n"], money(cell["cost"] / cell["n"] if cell["n"] else 0),
                                   "%d/%d" % (cell["acc"], cell["acc_total"])])
        out += ["## By task class", "", table(["class", "arm", "runs", "Σ model cost per run", "acceptance"], class_rows), ""]
    out += ["Δ violations = blocking convention violations in the final tree minus the count its own fixture already carries (4 for the single-solution fixture, %d for the platform). Acceptance = hidden HTTP checks against `dotnet run`. Stage minutes are arrival times of top-level Skill/Agent/Workflow dispatches; agent times come from the plugin's pulse (plugin arm) or nested tool events (baseline). cost = the CLI's `total_cost_usd`; Σ model cost = the sum of `modelUsage[*].costUSD`, which also counts agents that ran inside a Workflow. route = the tier the plugin arm actually ran, read off its own Workflow dispatches (quick = no workflow, light/standard = dotnet-sdd `mode`, deep = architecture-design ran). tests written = `[Fact]`/`[Theory]` count in the final tree, with ✅http when at least one test file drives the API through `WebApplicationFactory`/`CreateClient`." % FIXTURES.get("platform", {}).get("baselineBlocking", 0)]
    print("\n".join(out))


if __name__ == "__main__":
    main()
