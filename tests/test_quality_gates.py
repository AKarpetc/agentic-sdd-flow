import json
import os
import subprocess
import sys
import tempfile
import unittest

import _paths

GATES = os.path.join(_paths.PLUGIN_ROOT, "skills", "dotnet-quality-gates", "scripts")
crap = _paths.load_module("crap", os.path.join(GATES, "crap.py"))

COBERTURA = """<?xml version="1.0"?>
<coverage><sources><source>{root}/</source></sources><packages><package><classes>
  <class name="Shop.Pricing" filename="Pricing.cs">
    <methods>
      <method name="Legacy" complexity="12"><lines>
        <line number="2" hits="5"/><line number="3" hits="5"/><line number="4" hits="5"/>
      </lines></method>
      <method name="Fresh" complexity="10"><lines>
        <line number="7" hits="0"/><line number="8" hits="0"/>
      </lines></method>
    </methods>
  </class>
</classes></package></packages></coverage>
"""


def git(root, *args):
    subprocess.run(["git", "-C", root, *args], check=True, capture_output=True)


class Formula(unittest.TestCase):
    def test_uncovered_method_scores_complexity_squared_plus_complexity(self):
        score, coverage = crap.crap({"complexity": 10, "hits": {1: 0, 2: 0}})
        self.assertEqual((score, coverage), (110.0, 0.0))

    def test_fully_covered_method_scores_its_complexity(self):
        score, _ = crap.crap({"complexity": 7, "hits": {1: 3}})
        self.assertEqual(score, 7.0)


class MethodNames(unittest.TestCase):
    def test_async_state_machine_maps_to_its_method(self):
        self.assertEqual(crap.method_key("Shop.Job/<Execute>d__5", "MoveNext"), "Shop.Job.Execute")

    def test_local_function_keeps_its_outer_method(self):
        self.assertEqual(crap.method_key("Shop.Calc", "<Apply>g__Diff|1_3"), "Shop.Calc.Apply.Diff")


class BranchGate(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = os.path.realpath(self._tmp.name)
        git(self.root, "init", "-q", "-b", "master")
        git(self.root, "config", "user.email", "t@t")
        git(self.root, "config", "user.name", "t")
        self.source(["class Pricing {", "  int Legacy() {", "    return 1;", "  }"])
        git(self.root, "add", ".")
        git(self.root, "commit", "-q", "-m", "base")
        git(self.root, "switch", "-q", "-c", "feature")

    def source(self, lines):
        with open(os.path.join(self.root, "Pricing.cs"), "w", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")

    def run_gate(self):
        report = os.path.join(self.root, "coverage.cobertura.xml")
        with open(report, "w", encoding="utf-8") as handle:
            handle.write(COBERTURA.format(root=self.root))
        return subprocess.run([sys.executable, "-I", os.path.join(GATES, "crap.py"), report, "--repo", self.root],
                              capture_output=True, text=True)

    def test_new_uncovered_method_blocks_and_untouched_legacy_is_skipped(self):
        self.source(["class Pricing {", "  int Legacy() {", "    return 1;", "  }", "",
                     "  int Fresh() {", "    return 2;", "  }"])
        result = self.run_gate()
        self.assertEqual(result.returncode, 1)
        self.assertIn("| new | 7, 8 | `Shop.Pricing.Fresh`", result.stdout)
        self.assertNotIn("Legacy", result.stdout)

    def test_covered_change_in_legacy_method_is_reported_without_blocking(self):
        self.source(["class Pricing {", "  int Legacy() {", "    return 3;", "  }"])
        result = self.run_gate()
        self.assertEqual(result.returncode, 0)
        self.assertIn("| touched | — | `Shop.Pricing.Legacy`", result.stdout)


class Survivors(unittest.TestCase):
    def test_lists_open_mutants_and_scores_detected_ones(self):
        mutants = [{"status": status, "mutatorName": "Equality mutation", "replacement": "a <= b",
                    "location": {"start": {"line": line}}}
                   for status, line in (("Killed", 3), ("Timeout", 4), ("Survived", 5), ("CompileError", 6))]
        with tempfile.TemporaryDirectory() as tmp:
            report = os.path.join(tmp, "mutation-report.json")
            with open(report, "w", encoding="utf-8") as handle:
                json.dump({"files": {os.path.join(tmp, "Pricing.cs"): {"mutants": mutants}}}, handle)
            result = subprocess.run([sys.executable, "-I", os.path.join(GATES, "survivors.py"), report, "--repo", tmp],
                                    capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn("| Pricing.cs:5 | Survived | Equality mutation | `a <= b` |", result.stdout)
        self.assertIn("Mutation score 67%: 2 killed, 1 survived, 0 without coverage, 1 compile errors.", result.stdout)


if __name__ == "__main__":
    unittest.main()
