"""Surviving and uncovered mutants from Stryker.NET mutation-report.json, as a brief for tests-writer.

Exit code 1 when any mutant survived or no test reached it.
"""

import argparse
import glob
import json
import os
import sys

OPEN_STATUSES = ("Survived", "NoCoverage")


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reports", nargs="+", help="mutation-report.json files or globs, merged")
    parser.add_argument("--repo", default=".", help="paths are printed relative to this directory")
    return parser.parse_args()


def main():
    args = parse_args()
    repo = os.path.abspath(args.repo)
    totals = {}
    rows = []
    paths = sorted({p for pattern in args.reports for p in glob.glob(pattern, recursive=True)})
    if not paths:
        sys.exit("no mutation reports matched")
    for path in paths:
        with open(path, encoding="utf-8") as stream:
            report = json.load(stream)
        for file_name, entry in report["files"].items():
            for mutant in entry["mutants"]:
                status = mutant["status"]
                totals[status] = totals.get(status, 0) + 1
                if status in OPEN_STATUSES:
                    replacement = " ".join(mutant.get("replacement", "").split())
                    rows.append((os.path.relpath(file_name, repo), mutant["location"]["start"]["line"],
                                 status, mutant["mutatorName"], replacement[:100]))
    rows.sort()
    print("| Location | Status | Mutator | Replacement |\n|---|---|---|---|")
    for file_name, line, status, mutator, replacement in rows:
        print(f"| {file_name}:{line} | {status} | {mutator} | `{replacement}` |")
    detected = totals.get("Killed", 0) + totals.get("Timeout", 0)
    tested = detected + sum(totals.get(s, 0) for s in OPEN_STATUSES)
    score = f"{detected / tested:.0%}" if tested else "n/a"
    print(f"\nMutation score {score}: {detected} killed, {totals.get('Survived', 0)} survived, "
          f"{totals.get('NoCoverage', 0)} without coverage, {totals.get('CompileError', 0)} compile errors.")
    sys.exit(1 if rows else 0)


if __name__ == "__main__":
    main()
