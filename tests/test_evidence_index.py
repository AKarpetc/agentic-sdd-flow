"""The evidence index: recall over a repository's records, without a server, a model or a network."""

import json
import os
import subprocess
import sys
import tempfile
import unittest

import _paths

INDEX = os.path.join(_paths.PLUGIN_ROOT, "bin", "evidence-index.py")
ADR = """# ADR-0003: The customer report counts every order

- Status: Accepted (2026-01-20)

## Decision

N in the customer report is the total number of the customer's orders, whatever their status. The finance
export reconciles it against the ledger, which keeps a row for every order, cancelled or not.
"""
CS = """namespace Orders.Api.Services;

/// <summary>
/// Builds the customer report; the count covers every order, cancelled ones included (ADR-0003).
/// </summary>
internal sealed class ReportService
{
    // every order, cancelled included - ADR-0003
    public string Build() => "x";
}
"""


def run(*args):
    proc = subprocess.run([sys.executable, INDEX, *args], capture_output=True, text=True, timeout=120)
    if proc.returncode != 0:
        raise AssertionError(proc.stderr)
    return json.loads(proc.stdout)


class EvidenceIndex(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = self.tmp.name
        os.makedirs(os.path.join(self.repo, "docs", "decisions"))
        os.makedirs(os.path.join(self.repo, "src", "Services"))
        with open(os.path.join(self.repo, "docs", "decisions", "0003-counts.md"), "w", encoding="utf-8") as h:
            h.write(ADR)
        with open(os.path.join(self.repo, "src", "Services", "ReportService.cs"), "w", encoding="utf-8") as h:
            h.write(CS)
        with open(os.path.join(self.repo, "CHANGELOG.md"), "w", encoding="utf-8") as h:
            h.write("# Changelog\n\n## 1.4.0\n- Report counts every order per ADR-0003.\n")

    def tearDown(self):
        self.tmp.cleanup()

    def test_it_finds_the_decisive_record_from_the_briefs_wording(self):
        result = run("query", self.repo, "the report should show only active orders, excluding cancelled ones", "-n", "6")
        paths = [hit["path"] for hit in result["hits"]]
        self.assertIn(os.path.join("docs", "decisions", "0003-counts.md"), paths,
                      "the ADR decides the case and shares no decisive keyword with the query")
        self.assertTrue(any(p.endswith("ReportService.cs") for p in paths), "the XML doc states intent too")

    def test_source_bodies_are_not_indexed_only_their_prose(self):
        result = run("query", self.repo, "internal sealed class ReportService Build", "-n", "6")
        bodies = [h for h in result["hits"] if "internal sealed class" in h["snippet"]]
        self.assertEqual(bodies, [], "Roslyn answers code exactly; the index carries the prose about intent")

    def test_the_index_rebuilds_itself_when_a_record_changes(self):
        run("build", self.repo)
        with open(os.path.join(self.repo, "docs", "decisions", "0004-new.md"), "w", encoding="utf-8") as h:
            h.write("# ADR-0004\n\nThe nightly reconciliation job pages finance on a mismatch.\n")
        result = run("query", self.repo, "nightly reconciliation pages finance on a mismatch", "-n", "4")
        self.assertTrue(any("0004-new.md" in hit["path"] for hit in result["hits"]),
                        "a stale index that looks fresh is the failure mode this must not have")

    def test_it_needs_no_server_model_or_network(self):
        source = open(INDEX, encoding="utf-8").read()
        for forbidden in ("chromadb", "pinecone", "openai", "requests", "urllib", "sentence_transformers", "socket"):
            self.assertNotIn(forbidden, source, "the index must stay stdlib-only and offline")
        self.assertIn("fts5", source.lower())

    def test_the_reconciler_is_told_to_use_it_as_a_lead_not_as_evidence(self):
        agent = open(os.path.join(_paths.PLUGIN_ROOT, "agents", "evidence-reconciler.md"), encoding="utf-8").read()
        self.assertIn("evidence-index.py", agent)
        self.assertIn("leads, not evidence", agent)
        self.assertIn("twice", agent, "query in the brief's vocabulary and in the code's")


if __name__ == "__main__":
    unittest.main()
