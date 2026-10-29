"""CRAP score per method from coverlet cobertura reports, limited to the methods a branch changed.

CRAP = complexity^2 * (1 - coverage)^3 + complexity, coverage = covered lines / coverable lines.
Exit code 1 when a method over the threshold is new, or has a changed line no test runs.
"""

import argparse
import glob
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict

STATE_MACHINE = re.compile(r"/<(?P<name>[^<>]+)>d__\d+$")
NESTED_CLOSURE = re.compile(r"/<.*$")
LOCAL_FUNCTION = re.compile(r"^<(?P<outer>[^<>]+)>g__(?P<name>[^|]+)\|")


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reports", nargs="+", help="cobertura files or globs")
    parser.add_argument("--repo", default=".", help="git repository root")
    parser.add_argument("--base", default="master", help="base branch for the diff")
    parser.add_argument("--threshold", type=float, default=10.0)
    parser.add_argument("--all", action="store_true", help="every method, not only changed ones")
    return parser.parse_args()


def changed_lines(repo, base):
    merge_base = subprocess.check_output(["git", "-C", repo, "merge-base", base, "HEAD"], text=True).strip()
    diff = subprocess.check_output(
        ["git", "-C", repo, "diff", "-U0", "--no-color", merge_base, "--", "*.cs"], text=True)
    result = defaultdict(set)
    current = None
    for line in diff.splitlines():
        if line.startswith("+++ "):
            current = None if line.endswith("/dev/null") else line[6:]
        elif line.startswith("@@") and current:
            start, _, count = re.search(r"\+(\d+)(,(\d+))?", line).groups()
            length = 1 if count is None else int(count)
            result[current].update(range(int(start), int(start) + length))
    return result


def method_key(class_name, method_name):
    match = STATE_MACHINE.search(class_name)
    if match:
        return NESTED_CLOSURE.sub("", class_name) + "." + match.group("name")
    local = LOCAL_FUNCTION.match(method_name)
    if local:
        return NESTED_CLOSURE.sub("", class_name) + "." + local.group("outer") + "." + local.group("name")
    return NESTED_CLOSURE.sub("", class_name) + "." + method_name


def load(report_paths, repo):
    methods = {}
    for path in report_paths:
        root = ET.parse(path).getroot()
        sources = [s.text or "" for s in root.iter("source")]
        for cls in root.iter("class"):
            file_name = cls.get("filename")
            if "/obj/" in file_name.replace("\\", "/"):
                continue
            absolute = file_name if os.path.isabs(file_name) else os.path.join(sources[0] if sources else "", file_name)
            relative = os.path.relpath(absolute, repo)
            for method in cls.iter("method"):
                key = method_key(cls.get("name"), method.get("name"))
                entry = methods.setdefault(key, {"file": relative, "complexity": 0, "hits": {}})
                entry["complexity"] = max(entry["complexity"], int(method.get("complexity", "1")))
                for line in method.iter("line"):
                    number = int(line.get("number"))
                    entry["hits"][number] = max(entry["hits"].get(number, 0), int(line.get("hits", "0")))
    return methods


def crap(entry):
    lines = entry["hits"]
    coverage = sum(1 for hits in lines.values() if hits > 0) / len(lines) if lines else 1.0
    complexity = entry["complexity"]
    return complexity ** 2 * (1 - coverage) ** 3 + complexity, coverage


def main():
    args = parse_args()
    repo = os.path.abspath(args.repo)
    paths = sorted({p for pattern in args.reports for p in glob.glob(pattern, recursive=True)})
    if not paths:
        sys.exit("no cobertura reports matched")
    methods = load(paths, repo)
    changed = None if args.all else changed_lines(repo, args.base)
    rows = []
    for key, entry in methods.items():
        lines = set(entry["hits"])
        touched = lines if changed is None else changed.get(entry["file"], set()) & lines
        if not touched:
            continue
        score, coverage = crap(entry)
        uncovered = sorted(n for n in touched if entry["hits"][n] == 0)
        status = "new" if changed is not None and touched == lines else "touched"
        rows.append((score, coverage, entry["complexity"], status, uncovered, key, entry["file"], min(lines)))
    rows.sort(key=lambda row: row[0], reverse=True)
    over = [row for row in rows if row[0] >= args.threshold]
    blocking = [row for row in over if row[3] == "new" or row[4]]
    print("| CRAP | Coverage | Complexity | Status | Uncovered changed lines | Method | Location |")
    print("|---|---|---|---|---|---|---|")
    for score, coverage, complexity, status, uncovered, key, file_name, line in over or rows[:10]:
        lines_text = ", ".join(map(str, uncovered[:8])) + (" …" if len(uncovered) > 8 else "") or "—"
        print(f"| {score:.1f} | {coverage:.0%} | {complexity} | {status} | {lines_text} | `{key}` | {file_name}:{line} |")
    print(f"\n{len(rows)} methods checked, {len(over)} at or above CRAP {args.threshold:g}, {len(blocking)} blocking.")
    sys.exit(1 if blocking else 0)


if __name__ == "__main__":
    main()
