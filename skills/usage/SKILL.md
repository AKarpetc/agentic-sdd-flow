---
name: usage
description: Analyze Claude Code token usage, models, sessions, and costs from local JSONL logs
argument-hint: "[days]  (default: 7)"
allowed-tools: Bash
---

# Usage Analytics

Analyze local Claude Code session logs (`~/.claude/projects/`) to report token usage, models, cache stats, session count, users, and estimated API costs.

## Arguments

- `days` (optional, default: 7) — number of days to look back

## Procedure

1. Parse the `days` argument (default 7 if not provided)
2. Run the script below via Bash: `python3 /dev/stdin <DAYS> << 'PYEOF' ... PYEOF`
3. Present the output to the user as-is

```python
import json, os, sys
from datetime import datetime, timedelta
from collections import defaultdict
from pathlib import Path

days = int(sys.argv[1]) if len(sys.argv) > 1 else 7
claude_dir = Path.home() / ".claude"
projects_dir = claude_dir / "projects"

if not projects_dir.exists():
    print("ERROR: ~/.claude/projects/ not found. Is Claude Code installed?")
    sys.exit(1)

cutoff_ts = (datetime.now() - timedelta(days=days)).timestamp()
now = datetime.now()

TOKEN_KEYS = ("input", "output", "cache_write", "cache_read")
USAGE_MAP = {
    "input": "input_tokens",
    "output": "output_tokens",
    "cache_write": "cache_creation_input_tokens",
    "cache_read": "cache_read_input_tokens",
}

total = {k: 0 for k in TOKEN_KEYS}
models = defaultdict(lambda: {**{k: 0 for k in TOKEN_KEYS}, "requests": 0})
proj_stats = defaultdict(lambda: {**{k: 0 for k in TOKEN_KEYS}, "sessions": 0})
users = set()
session_count = 0
entrypoints = defaultdict(int)
versions = set()


def extract_user(pn):
    parts = pn.split("-")
    if len(parts) >= 3 and parts[1] in ("Users", "home"):
        return parts[2]
    return "unknown"


def extract_project(pn):
    parts = pn.lstrip("-").split("-")
    if len(parts) >= 3 and parts[0] in ("Users", "home"):
        return "/".join(parts[2:])
    return pn


def fmt(n):
    if n >= 1e9:
        return f"{n / 1e9:.2f}B"
    if n >= 1e6:
        return f"{n / 1e6:.1f}M"
    if n >= 1e3:
        return f"{n / 1e3:.1f}K"
    return str(n)


# Scan all JSONL files
all_jsonl = list(projects_dir.glob("*/*.jsonl")) + list(
    projects_dir.glob("*/*/subagents/*.jsonl")
)

for jp in all_jsonl:
    if jp.stat().st_mtime < cutoff_ts:
        continue

    is_sub = "/subagents/" in str(jp)
    pd = jp.parts[-4] if is_sub else jp.parts[-2]
    pn = extract_project(pd)
    users.add(extract_user(pd))

    try:
        with open(jp) as f:
            has = False
            for line in f:
                try:
                    obj = json.loads(line.strip())
                    if not isinstance(obj, dict):
                        continue
                    if obj.get("version"):
                        versions.add(obj["version"])
                    if obj.get("entrypoint"):
                        entrypoints[obj["entrypoint"]] += 1

                    usage = None
                    model_name = "unknown"

                    if obj.get("type") == "assistant":
                        msg = obj.get("message", {})
                        usage = msg.get("usage")
                        model_name = msg.get("model", "unknown")
                    elif "toolUseResult" in obj:
                        tur = obj["toolUseResult"]
                        if isinstance(tur, dict):
                            usage = tur.get("usage")
                            model_name = tur.get("model", "unknown")

                    if usage:
                        for k, uk in USAGE_MAP.items():
                            v = usage.get(uk, 0)
                            total[k] += v
                            models[model_name][k] += v
                            proj_stats[pn][k] += v
                        models[model_name]["requests"] += 1
                        has = True
                except Exception:
                    pass

            if has and not is_sub:
                session_count += 1
                proj_stats[pn]["sessions"] += 1
    except Exception:
        continue

# Pricing per 1M tokens
PRICING = {
    "claude-opus-4-6": {"input": 15, "output": 75, "cache_write": 18.75, "cache_read": 1.875},
    "claude-sonnet-4-6": {"input": 3, "output": 15, "cache_write": 3.75, "cache_read": 0.30},
    "claude-haiku-4-5": {"input": 0.8, "output": 4, "cache_write": 1.0, "cache_read": 0.08},
}
DEF_PRICING = {"input": 15, "output": 75, "cache_write": 18.75, "cache_read": 1.875}


def get_pricing(m):
    for k, p in PRICING.items():
        if k in m:
            return p
    return DEF_PRICING


def calc_cost(s, p=None):
    p = p or DEF_PRICING
    return sum(s[k] / 1e6 * p[k] for k in TOKEN_KEYS)


# --- Report ---
df = (now - timedelta(days=days)).strftime("%Y-%m-%d")
dt = now.strftime("%Y-%m-%d")

print(f"{'=' * 60}")
print(f"  Claude Code Usage Report")
print(f"  Period: {df} — {dt} ({days} days)")
print(f"{'=' * 60}")

print(f"\n--- Overview ---")
print(f"  Users:           {', '.join(sorted(users))}")
print(f"  Sessions:        {session_count}")
print(f"  Versions:        {', '.join(sorted(versions)) if versions else 'N/A'}")
ep = ", ".join(f"{k} ({v})" for k, v in sorted(entrypoints.items(), key=lambda x: -x[1]))
print(f"  Entrypoints:     {ep}")

print(f"\n--- Tokens ---")
labels = {"input": "Input", "output": "Output", "cache_write": "Cache write", "cache_read": "Cache read"}
for k in TOKEN_KEYS:
    print(f"  {labels[k] + ':':<17}{fmt(total[k]):>12}")
print(f"  {'─' * 30}")
print(f"  {'Total:':<17}{fmt(sum(total.values())):>12}")

print(f"\n--- By Model ---")
for m, s in sorted(models.items(), key=lambda x: -sum(x[1][k] for k in TOKEN_KEYS)):
    p = get_pricing(m)
    c = calc_cost(s, p)
    mt = sum(s[k] for k in TOKEN_KEYS)
    print(f"\n  {m}")
    print(f"    Requests:   {s['requests']}")
    print(f"    Input:      {fmt(s['input']):>10}   Output:     {fmt(s['output']):>10}")
    print(f"    Cache W:    {fmt(s['cache_write']):>10}   Cache R:    {fmt(s['cache_read']):>10}")
    print(f"    Total:      {fmt(mt):>10}   Est. cost:  ${c:.2f}")

print(f"\n--- By Project ---")
for p, s in sorted(proj_stats.items(), key=lambda x: -sum(x[1][k] for k in TOKEN_KEYS)):
    pt = sum(s[k] for k in TOKEN_KEYS)
    c = calc_cost(s)
    print(f"  {p}: {fmt(pt)} (~${c:.2f}) — {s['sessions']} sessions")

tc = sum(calc_cost(s, get_pricing(m)) for m, s in models.items())
print(f"\n--- Estimated Cost (API pricing) ---")
print(f"  Total:  ~${tc:.2f}")
print(f"  Note: On Max plan ($100-200/mo), included in subscription.")

if days < 30:
    factor = 30 / days
    print(f"\n--- Monthly Projection (x{factor:.1f}) ---")
    for k in TOKEN_KEYS:
        print(f"  {labels[k] + ':':<17}{fmt(int(total[k] * factor)):>12}")
    print(f"  Est. cost:   ~${tc * factor:.2f}")
    print(f"  Sessions:    ~{int(session_count * factor)}")

print()
```
