#!/usr/bin/env python3
"""Objective checks on a finished benchmark workspace: build, the repository's own tests, hidden HTTP
acceptance against the running API, convention violations in the final tree, and git hygiene.

  python3 evals/benchmark/acceptance.py <task-id> <workspace> [--port 5177] > result.json
"""

import argparse
import glob
import json
import os
import re
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN_ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(PLUGIN_ROOT, "scripts"))
import importlib.util  # noqa: E402

spec = importlib.util.spec_from_file_location("check_rules", os.path.join(PLUGIN_ROOT, "scripts", "check-rules.py"))
check_rules = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check_rules)

ENV = dict(os.environ, DOTNET_CLI_TELEMETRY_OPTOUT="1", DOTNET_NOLOGO="1", ASPNETCORE_ENVIRONMENT="Development",
           DOTNET_CLI_UI_LANGUAGE="en")  # the test summary is parsed; a localized SDK prints "Пройдено!" instead of "Passed!"
SUMMARY = re.compile(r"(?:Passed|Failed)!\s+-\s+Failed:\s+(\d+),\s+Passed:\s+(\d+),\s+Skipped:\s+(\d+),\s+Total:\s+(\d+)")


def sh(args, cwd, timeout=600):
    proc = subprocess.run(args, cwd=cwd, env=ENV, capture_output=True, text=True, timeout=timeout)
    return proc.returncode, proc.stdout + proc.stderr


def build(workspace):
    code, out = sh(["dotnet", "build", "Orders.slnx", "-nologo", "-v", "q"], workspace)
    errors = len(re.findall(r"error CS\d+", out))
    return {"ok": code == 0, "errors": errors, "tail": out[-1200:]}


def tests(workspace):
    code, out = sh(["dotnet", "test", "Orders.slnx", "-nologo", "-v", "q", "--no-build"], workspace, timeout=900)
    summaries = [tuple(int(n) for n in m) for m in SUMMARY.findall(out)]  # one line per test assembly
    failed = sum(s[0] for s in summaries)
    passed = sum(s[1] for s in summaries)
    total = sum(s[3] for s in summaries)
    if total == 0:  # newer test SDK output
        passed = sum(int(n) for n in re.findall(r"Passed:\s+(\d+)", out))
        failed = sum(int(n) for n in re.findall(r"Failed:\s+(\d+)", out))
        total = passed + failed
    return {"ok": code == 0, "passed": passed, "failed": failed, "total": total, "tail": out[-800:]}


def http(method, url, body=None):
    request = urllib.request.Request(url, method=method, data=json.dumps(body).encode() if body is not None else None,
                                     headers={"Content-Type": "application/json"} if body is not None else {})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            raw = response.read().decode()
            if not raw.strip():
                return response.status, None
            try:
                return response.status, json.loads(raw)
            except ValueError:
                return response.status, raw
    except urllib.error.HTTPError as error:
        raw = error.read().decode()
        try:
            return error.code, json.loads(raw)
        except ValueError:
            return error.code, raw
    except (urllib.error.URLError, socket.timeout, ConnectionError) as error:
        return 0, str(error)


def run_api(workspace, port):
    # Own process group: `dotnet run` spawns the API as a child that outlives a plain kill of the parent,
    # and a leaked API would answer the next run's acceptance client on the same port.
    proc = subprocess.Popen(["dotnet", "run", "--project", "src/Orders.Api", "--no-build", "--urls", f"http://127.0.0.1:{port}"],
                            cwd=workspace, env=ENV, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    deadline = time.time() + 60
    while time.time() < deadline:
        if http("GET", f"http://127.0.0.1:{port}/")[0] != 0:
            return proc
        if proc.poll() is not None:
            break
        time.sleep(0.5)
    stop_api(proc)
    return None


def stop_api(proc):
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    proc.wait(timeout=30)


def near(a, b):
    try:
        return abs(float(a) - float(b)) < 0.001
    except (TypeError, ValueError):
        return False


def acceptance_t1(base):
    checks = []
    for cid, total in ((1, 37.75), (2, 100.0), (3, 0), (99, 0)):
        status, body = http("GET", f"{base}/api/customers/{cid}/orders/total")
        ok = status == 200 and isinstance(body, dict) and near(body.get("total"), total) and str(body.get("customerId")) == str(cid)
        checks.append({"name": f"total customer {cid} = {total}", "ok": ok, "detail": f"{status} {body}"})
    return checks


def acceptance_t2(base):
    checks = []
    for oid, expected in ((101, 204), (102, 204), (104, 409), (103, 409), (999, 404)):
        status, body = http("POST", f"{base}/api/orders/{oid}/cancel")
        ok = status == expected
        if expected == 409:
            ok = ok and isinstance(body, dict) and bool(body.get("title"))
        checks.append({"name": f"cancel {oid} -> {expected}", "ok": ok, "detail": f"{status} {str(body)[:120]}"})
    status, body = http("GET", f"{base}/api/orders/101")
    checks.append({"name": "101 persisted as Cancelled", "ok": status == 200 and isinstance(body, dict) and str(body.get("status")).lower() == "cancelled", "detail": f"{status} {body}"})
    status, body = http("GET", f"{base}/api/orders/104")
    checks.append({"name": "104 still Shipped", "ok": status == 200 and isinstance(body, dict) and str(body.get("status")).lower() == "shipped", "detail": f"{status} {body}"})
    status, body = http("GET", f"{base}/api/outbox")
    ok = status == 200 and isinstance(body, list) and [str(e.get("orderId")) for e in body if isinstance(e, dict)] == ["101", "102"] \
        and all(e.get("type") == "OrderCancelled" for e in body if isinstance(e, dict))
    checks.append({"name": "outbox has OrderCancelled 101, 102", "ok": ok, "detail": f"{status} {str(body)[:160]}"})
    return checks


def acceptance_t3(base):
    checks = []
    def page(cid, p, s):
        return http("GET", f"{base}/api/customers/{cid}/orders?page={p}&size={s}")
    for cid, p, s, ids, total in ((1, 1, 2, [101, 102], 4), (1, 2, 2, [103, 104], 4), (1, 3, 2, [], 4), (2, 1, 10, [201, 202], 2), (99, 1, 5, [], 0)):
        status, body = page(cid, p, s)
        got = [int(i.get("id")) for i in body.get("items", [])] if isinstance(body, dict) and isinstance(body.get("items"), list) else None
        ok = status == 200 and got == ids and isinstance(body, dict) and body.get("totalItems") == total and body.get("page") == p and body.get("size") == s
        checks.append({"name": f"customer {cid} page {p} size {s} -> {ids} of {total}", "ok": ok, "detail": f"{status} {str(body)[:160]}"})
    for p, s, param in ((0, 2, "page"), (1, 0, "size"), (1, 101, "size")):
        status, body = page(1, p, s)
        ok = status == 400 and isinstance(body, dict) and param in str(body.get("detail", "")).lower()
        checks.append({"name": f"page={p} size={s} -> 400 naming {param}", "ok": ok, "detail": f"{status} {str(body)[:160]}"})
    return checks


def acceptance_t4(base):
    checks = []
    for oid, subtotal, discounts, total in ((101, 10.0, [], 10.0), (102, 20.5, [("PCT10", 2.05)], 18.45),
                                             (201, 100.0, [("PCT10", 10.0), ("FIVEOFF", 5.0)], 85.0), (104, 7.25, [], 7.25)):
        status, body = http("GET", f"{base}/api/orders/{oid}/pricing")
        got = [(str(d.get("code")), d.get("amount")) for d in body.get("discounts", [])] if isinstance(body, dict) and isinstance(body.get("discounts"), list) else None
        ok = status == 200 and isinstance(body, dict) and str(body.get("orderId")) == str(oid) and near(body.get("subtotal"), subtotal) \
            and near(body.get("total"), total) and got is not None and [c for c, _ in got] == [c for c, _ in discounts] \
            and all(near(a, b) for (_, a), (_, b) in zip(got, discounts))
        checks.append({"name": f"pricing {oid} -> total {total} via {[c for c, _ in discounts]}", "ok": ok, "detail": f"{status} {str(body)[:160]}"})
    status, body = http("GET", f"{base}/api/orders/103/pricing")
    checks.append({"name": "pricing cancelled 103 -> 409 with title", "ok": status == 409 and isinstance(body, dict) and bool(body.get("title")), "detail": f"{status} {str(body)[:120]}"})
    status, body = http("GET", f"{base}/api/orders/999/pricing")
    route_exists = checks[0]["ok"]  # without the route every id is a 404, which must not count
    checks.append({"name": "pricing unknown 999 -> 404", "ok": status == 404 and route_exists, "detail": f"{status} {str(body)[:120]}"})
    for cid, needle in ((2, "15.00"), (1, "2.05")):
        status, body = http("GET", f"{base}/api/customers/{cid}/report")
        checks.append({"name": f"report customer {cid} contains {needle}", "ok": status == 200 and needle in str(body), "detail": f"{status} {str(body)[:160]}"})
    return checks


def acceptance_t5(base):
    checks = []
    for oid, status_name in ((101, "Placed"), (201, "Placed")):
        status, body = http("GET", f"{base}/api/orders/{oid}")
        ok = status == 200 and isinstance(body, dict) and str(body.get("id")) == str(oid) \
            and str(body.get("status")) == status_name
        if oid == 101:
            ok = ok and str(body.get("customerId")) == "1" and near(body.get("total"), 10.0)
        checks.append({"name": f"order {oid} still 200 with its shape", "ok": ok, "detail": f"{status} {str(body)[:120]}"})
    status, body = http("GET", f"{base}/api/orders/999")
    ok = status == 404 and isinstance(body, dict) and bool(body.get("title")) and "999" in str(body.get("detail", ""))
    checks.append({"name": "unknown 999 -> 404 ProblemDetails naming the id", "ok": ok, "detail": f"{status} {str(body)[:160]}"})
    for oid in (0, -5):
        status, body = http("GET", f"{base}/api/orders/{oid}")
        ok = status == 400 and isinstance(body, dict) and "id" in str(body.get("detail", "")).lower()
        checks.append({"name": f"id {oid} -> 400 naming id", "ok": ok, "detail": f"{status} {str(body)[:160]}"})
    return checks


def acceptance_t6(base):
    """Sequential by design: the state machine is exercised in order against one fresh process."""
    checks = []

    def transition(oid, to, request_id):
        return http("POST", f"{base}/api/orders/{oid}/transitions", {"to": to, "requestId": request_id})

    status, first = transition(101, "Paid", "r1")
    ok = status == 200 and isinstance(first, dict) and str(first.get("orderId")) == "101" \
        and str(first.get("status")).lower() == "paid"
    checks.append({"name": "101 Placed -> Paid = 200", "ok": ok, "detail": f"{status} {str(first)[:120]}"})
    status, repeat = transition(101, "Paid", "r1")
    checks.append({"name": "same requestId repeats -> 200 with the same body", "ok": status == 200 and repeat == first,
                   "detail": f"{status} {str(repeat)[:120]}"})
    status, body = http("GET", f"{base}/api/orders/101/history")
    entry = body[0] if isinstance(body, list) and len(body) == 1 and isinstance(body[0], dict) else None
    ok = status == 200 and entry is not None and str(entry.get("from")).lower() == "placed" \
        and str(entry.get("to")).lower() == "paid" and str(entry.get("requestId")) == "r1"
    checks.append({"name": "101 history has exactly one entry after the idempotent repeat", "ok": ok, "detail": f"{status} {str(body)[:160]}"})
    status, body = transition(101, "Shipped", "r2")
    checks.append({"name": "101 Paid -> Shipped = 200", "ok": status == 200 and isinstance(body, dict) and str(body.get("status")).lower() == "shipped",
                   "detail": f"{status} {str(body)[:120]}"})
    status, body = transition(104, "Cancelled", "r3")
    checks.append({"name": "104 Shipped -> Cancelled = 409", "ok": status == 409 and isinstance(body, dict) and bool(body.get("title")),
                   "detail": f"{status} {str(body)[:160]}"})
    status, body = transition(103, "Paid", "r4")
    checks.append({"name": "103 Cancelled -> Paid = 409", "ok": status == 409, "detail": f"{status} {str(body)[:120]}"})
    status, body = transition(999, "Paid", "r5")
    checks.append({"name": "unknown 999 -> 404", "ok": status == 404 and checks[0]["ok"], "detail": f"{status} {str(body)[:120]}"})
    status, body = transition(201, "Frozen", "r6")
    checks.append({"name": "unknown target status -> 400", "ok": status == 400, "detail": f"{status} {str(body)[:120]}"})
    status, body = http("GET", f"{base}/api/orders/101")
    checks.append({"name": "101 persisted as Shipped", "ok": status == 200 and isinstance(body, dict) and str(body.get("status")).lower() == "shipped",
                   "detail": f"{status} {str(body)[:120]}"})
    status, body = http("GET", f"{base}/api/orders/201/history")
    checks.append({"name": "201 never moved -> empty history", "ok": status == 200 and body == [], "detail": f"{status} {str(body)[:120]}"})
    return checks


def acceptance_t7(base):
    checks = []

    def attention(cid):
        status, body = http("GET", f"{base}/api/customers/{cid}/attention")
        items = body.get("items") if isinstance(body, dict) else None
        ids = [i.get("orderId") for i in items] if isinstance(items, list) and all(isinstance(i, dict) for i in items) else None
        return status, body, items, ids

    status, body, items, ids = attention(1)
    ok = status == 200 and isinstance(body, dict) and str(body.get("customerId")) == "1" and ids is not None \
        and any(str(i) == "102" for i in ids) and not any(str(i) == "103" for i in ids)
    checks.append({"name": "customer 1 attention has 102, not 103", "ok": ok, "detail": f"{status} {str(body)[:160]}"})
    reasons_ok = items is not None and bool(items) and all(isinstance(i.get("reason"), str) and i["reason"].strip() for i in items)
    checks.append({"name": "every item carries a non-empty reason", "ok": bool(reasons_ok), "detail": f"{status} {str(items)[:160]}"})
    unique_ok = ids is not None and len(ids) == len({str(i) for i in ids})
    checks.append({"name": "no order appears twice", "ok": bool(unique_ok), "detail": str(ids)[:160]})
    status, body, items, ids = attention(2)
    checks.append({"name": "customer 2 attention excludes the cancelled 202", "ok": status == 200 and ids is not None and not any(str(i) == "202" for i in ids),
                   "detail": f"{status} {str(body)[:160]}"})
    for cid in (3, 99):
        status, body, items, ids = attention(cid)
        checks.append({"name": f"customer {cid} -> 200 with an empty items array", "ok": status == 200 and items == [],
                       "detail": f"{status} {str(body)[:160]}"})
    return checks



ACCEPTANCE = {"T1": acceptance_t1, "T2": acceptance_t2, "T3": acceptance_t3, "T4": acceptance_t4,
              "T5": acceptance_t5, "T6": acceptance_t6, "T7": acceptance_t7}
# The one check per task that cannot pass unless the pre-existing defect is fixed at its root.
PLANTED = {"T1": "total customer 1 = 37.75", "T2": "cancel 102 -> 204", "T3": "customer 1 page 1 size 2 -> [101, 102] of 4",
           "T4": "report customer 2 contains 15.00", "T5": "unknown 999 -> 404 ProblemDetails naming the id",
           "T6": "104 Shipped -> Cancelled = 409", "T7": "customer 1 attention has 102, not 103"}


def quality_common(workspace):
    """Signals that separate the arms on every task, not only on T4: does the suite reach the endpoint at all,
    and how much of it is there. The 0.2.7 measurement found 0 % endpoint coverage in the baseline's trees."""
    tests = {}
    for path in glob.glob(os.path.join(workspace, "tests", "**", "*.cs"), recursive=True):
        if not re.search(r"[/\\](obj|bin)[/\\]", path):
            tests[os.path.relpath(path, workspace)] = open(path, encoding="utf-8-sig").read()
    text = "\n".join(tests.values())
    http_files = [p for p, t in tests.items() if re.search(r"WebApplicationFactory|CreateClient\(", t)]
    return {
        "testFiles": len(tests),
        "testCases": len(re.findall(r"\[\s*(?:Fact|Theory)\b", text)),
        "httpLevelTestFiles": http_files,
        "reachesTheEndpoint": bool(http_files),
        "theoryCases": len(re.findall(r"\[\s*InlineData\b", text)) + len(re.findall(r"TheoryData<", text)),
    }


def quality_t4(workspace):
    """Design signals the T4 brief asks for without naming a mechanism: a controllable clock, options done the
    plugin's way, promotions in configuration, promotion kinds as separate types."""
    src = {}
    for path in glob.glob(os.path.join(workspace, "src", "**", "*.cs"), recursive=True):
        if not re.search(r"[/\\](obj|bin)[/\\]", path):
            src[os.path.relpath(path, workspace)] = open(path, encoding="utf-8-sig").read()
    clock_files = [p for p, t in src.items() if re.search(r"\bTimeProvider\b|I\w*Clock\b", t)]
    system_clock = {p: len(re.findall(r"DateTime(?:Offset)?\.(?:Now|UtcNow)", t)) for p, t in src.items()}
    system_clock = {p: n for p, n in system_clock.items() if n and not re.search(r"Clock|TimeProvider", p)}
    settings = ""
    for name in ("appsettings.json", "appsettings.Development.json"):
        path = os.path.join(workspace, "src", "Orders.Api", name)
        if os.path.exists(path):
            settings += open(path, encoding="utf-8-sig").read()
    kinds = [p for p, t in src.items() if re.search(r"(?:class|record)\s+\w*(?:Percent|Percentage|Fixed|Amount)\w*(?:Promotion|Discount|Rule)\b", t)]
    return {
        "clockAbstraction": bool(clock_files), "clockFiles": clock_files,
        "systemClockCallsOutsideClock": sum(system_clock.values()), "systemClockFiles": system_clock,
        "iOptionsUsages": sum(t.count("IOptions<") for t in src.values()),
        "iOptionsSnapshotOrMonitorUsages": sum(len(re.findall(r"IOptions(?:Snapshot|Monitor)<", t)) for t in src.values()),
        "promotionsInAppsettings": '"Promotions"' in settings,
        "promotionKindTypes": kinds,
        "reportServiceStillHasPrimaryCtor": bool(re.search(r"class ReportService\s*\(", src.get(os.path.join("src", "Orders.Api", "Services", "ReportService.cs"), ""))),
    }


def conventions(workspace):
    per_rule, files = {}, 0
    for path in glob.glob(os.path.join(workspace, "**", "*.cs"), recursive=True):
        if re.search(r"[/\\](obj|bin|Migrations)[/\\]", path):
            continue
        files += 1
        with open(path, encoding="utf-8-sig") as handle:
            blocking, advisory = check_rules.inspect(path, handle.read())
        for rule, _, _ in blocking:
            per_rule[rule] = per_rule.get(rule, 0) + 1
        for rule, _, _ in advisory:
            per_rule["advisory:" + rule] = per_rule.get("advisory:" + rule, 0) + 1
    blocking_total = sum(v for k, v in per_rule.items() if not k.startswith("advisory:"))
    advisory_total = sum(v for k, v in per_rule.items() if k.startswith("advisory:"))
    return {"files": files, "blocking": blocking_total, "advisory": advisory_total, "perRule": per_rule}


def git_hygiene(workspace, key):
    code, log = sh(["git", "log", "--format=%s", "fixture..HEAD"], workspace)
    if code != 0:
        code, log = sh(["git", "log", "--format=%s"], workspace)
        messages = [m for m in log.splitlines() if m.strip() and m.strip() != "fixture"]
    else:
        messages = [m for m in log.splitlines() if m.strip()]
    good = [m for m in messages if re.match(r"^%s: \S" % re.escape(key), m)]
    _, stat = sh(["git", "diff", "--shortstat", "fixture", "HEAD"], workspace)
    _, names = sh(["git", "diff", "--name-only", "fixture", "HEAD"], workspace)
    _, dirty = sh(["git", "status", "--short"], workspace)
    return {"commits": len(messages), "wellFormed": len(good), "messages": messages[:20], "shortstat": stat.strip(),
            "filesChanged": [n for n in names.splitlines() if n.strip()], "uncommitted": len([l for l in dirty.splitlines() if l.strip()])}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("task")
    parser.add_argument("workspace")
    parser.add_argument("--port", type=int, default=5177)
    args = parser.parse_args()
    key = json.load(open(os.path.join(HERE, "tasks", "tasks.json")))[args.task]["key"]
    result = {"task": args.task, "build": build(args.workspace)}
    result["tests"] = tests(args.workspace) if result["build"]["ok"] else {"ok": False, "passed": 0, "failed": 0, "total": 0, "tail": "no build"}
    checks = []
    if result["build"]["ok"]:
        api = run_api(args.workspace, args.port)
        if api is None:
            checks = [{"name": "api starts", "ok": False, "detail": "dotnet run did not answer within 60 s"}]
        else:
            try:
                checks = ACCEPTANCE[args.task](f"http://127.0.0.1:{args.port}")
            finally:
                stop_api(api)
    result["acceptance"] = {"passed": sum(c["ok"] for c in checks), "total": len(checks) or len(ACCEPTANCE[args.task]("http://127.0.0.1:1")), "checks": checks}
    result["plantedBugFixed"] = any(c["ok"] and c["name"] == PLANTED[args.task] for c in checks)
    result["conventions"] = conventions(args.workspace)
    result["quality"] = quality_common(args.workspace)
    if args.task == "T4":
        result["quality"].update(quality_t4(args.workspace))
    result["git"] = git_hygiene(args.workspace, key)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
