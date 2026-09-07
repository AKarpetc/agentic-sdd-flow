#!/usr/bin/env python3
"""Ranked full-text search over a repository's *records* — the sources `evidence-reconciler` must not miss.

Why this exists: the reconciler's job is to find every source that states or enforces a behaviour before it
rules on a contradiction. Plain `grep` misses the decisive source whenever it is phrased differently from
the brief ("active orders" in the ticket, "cancelled rows stay in the ledger" in the ADR) — and a missed
ADR is exactly the failure the agent is there to prevent. This is a *candidate generator* with BM25
ranking over stdlib SQLite FTS5: no server, no model, no embeddings, no data leaving the machine. The agent
must still open and read what it returns; a hit is a lead, never evidence.

  evidence-index.py build <repo> [--out <db>]        index the records under <repo>
  evidence-index.py query <repo> "<terms>" [-n 8]    ranked passages (builds/refreshes the index if stale)

Indexed: docs/**, **/decisions/**, **/consumers/**, CHANGELOG*, ADR*, *.md at the root, CI files
(.gitlab-ci.yml, .github/workflows/*), smoke scripts under scripts/, and the XML doc comments of *.cs.
Not indexed: source bodies (Roslyn answers those exactly), bin/obj, .git, node_modules.
"""

import argparse
import glob
import hashlib
import json
import os
import re
import sqlite3
import sys

RECORD_GLOBS = (
    "docs/**/*.md", "docs/**/*.markdown", "*.md", "**/decisions/**/*.md", "**/consumers/**/*.md",
    "CHANGELOG*", "ADR*", ".gitlab-ci.yml", ".github/workflows/*.yml", ".github/workflows/*.yaml",
    "scripts/*.sh", "**/*.csproj", "**/appsettings*.json",
)
SOURCE_GLOB = "**/*.cs"
SKIP = re.compile(r"[/\\](bin|obj|node_modules|\.git|packages|TestResults)[/\\]")
XMLDOC = re.compile(r"^\s*///(.*)$")
COMMENT = re.compile(r"^\s*//(?!/)(.*)$")
DEFAULT_DB = os.path.join(".superpowers", "sdd", "evidence-index.sqlite")


def files(repo):
    seen = set()
    for pattern in RECORD_GLOBS:
        for path in glob.glob(os.path.join(repo, pattern), recursive=True):
            if os.path.isfile(path) and not SKIP.search(path) and path not in seen:
                seen.add(path)
                yield path, "record"
    for path in glob.glob(os.path.join(repo, SOURCE_GLOB), recursive=True):
        if os.path.isfile(path) and not SKIP.search(path) and path not in seen:
            seen.add(path)
            yield path, "source"


def passages(path, kind):
    """A record is chunked by heading; a source contributes only its XML docs and comments — the prose a
    developer wrote about intent, which is where a contradiction hides."""
    try:
        text = open(path, encoding="utf-8-sig", errors="replace").read()
    except OSError:
        return
    if kind == "source":
        block, start = [], 0
        for number, line in enumerate(text.splitlines(), 1):
            match = XMLDOC.match(line) or COMMENT.match(line)
            if match:
                if not block:
                    start = number
                block.append(match.group(1).strip())
            elif block:
                yield start, "\n".join(block)
                block = []
        if block:
            yield start, "\n".join(block)
        return
    heading, block, start = "", [], 1
    for number, line in enumerate(text.splitlines(), 1):
        if re.match(r"^\s{0,3}#{1,6}\s", line) and block:
            yield start, (heading + "\n" + "\n".join(block)).strip()
            heading, block, start = line, [], number
        elif re.match(r"^\s{0,3}#{1,6}\s", line):
            heading, start = line, number
        else:
            block.append(line)
    if block or heading:
        yield start, (heading + "\n" + "\n".join(block)).strip()


def fingerprint(repo):
    digest = hashlib.sha256()
    for path, kind in sorted(files(repo)):
        try:
            digest.update(("%s:%d:%d" % (path, os.path.getmtime(path), os.path.getsize(path))).encode())
        except OSError:
            continue
    return digest.hexdigest()


def build(repo, db_path):
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
    if os.path.exists(db_path):
        os.remove(db_path)
    db = sqlite3.connect(db_path)
    db.execute("create virtual table passages using fts5(path, line UNINDEXED, kind UNINDEXED, body)")
    db.execute("create table meta (key text primary key, value text)")
    count = 0
    for path, kind in files(repo):
        for line, body in passages(path, kind):
            if len(body.strip()) < 20:
                continue
            db.execute("insert into passages (path, line, kind, body) values (?,?,?,?)",
                       (os.path.relpath(path, repo), line, kind, body[:8000]))
            count += 1
    db.execute("insert into meta (key, value) values ('fingerprint', ?)", (fingerprint(repo),))
    db.execute("insert into meta (key, value) values ('passages', ?)", (str(count),))
    db.commit()
    db.close()
    return count


def stale(repo, db_path):
    if not os.path.exists(db_path):
        return True
    try:
        db = sqlite3.connect(db_path)
        stored = db.execute("select value from meta where key='fingerprint'").fetchone()
        db.close()
    except sqlite3.Error:
        return True
    return not stored or stored[0] != fingerprint(repo)


def query(repo, db_path, terms, limit):
    db = sqlite3.connect(db_path)
    # OR over the terms: recall is the point — the agent filters, the index must not hide a source.
    words = [w for w in re.findall(r"[\w./-]{3,}", terms.lower())][:24]
    if not words:
        return []
    expression = " OR ".join('"%s"' % w.replace('"', "") for w in words)
    try:
        rows = db.execute(
            "select path, line, kind, snippet(passages, 3, '«', '»', ' … ', 24), bm25(passages) "
            "from passages where passages match ? order by bm25(passages) limit ?",
            (expression, limit)).fetchall()
    except sqlite3.OperationalError as error:
        return [{"error": str(error)}]
    finally:
        db.close()
    return [{"path": p, "line": l, "kind": k, "snippet": s, "score": round(-score, 2)} for p, l, k, s, score in rows]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("action", choices=("build", "query"))
    parser.add_argument("repo")
    parser.add_argument("terms", nargs="?", default="")
    parser.add_argument("-n", "--limit", type=int, default=8)
    parser.add_argument("--out")
    args = parser.parse_args()
    repo = os.path.abspath(args.repo)
    db_path = args.out or os.path.join(repo, DEFAULT_DB)
    if args.action == "build":
        print(json.dumps({"db": db_path, "passages": build(repo, db_path)}, indent=2))
        return 0
    if stale(repo, db_path):
        build(repo, db_path)
    hits = query(repo, db_path, args.terms, args.limit)
    print(json.dumps({"db": db_path, "terms": args.terms, "hits": hits}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
