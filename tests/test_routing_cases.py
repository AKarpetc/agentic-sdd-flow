"""The routing eval suite stays well-formed: every case is runnable and every expectation names a real agent, skill or tool."""

import glob
import json
import os
import re
import unittest

import _paths

ROOT = _paths.PLUGIN_ROOT
SUITE = os.path.join(ROOT, "evals", "routing", "cases.json")
TOOLS = {"Agent", "Skill", "Workflow", "Read", "Write", "Edit", "Grep", "Glob", "Bash"}


def load():
    with open(SUITE, encoding="utf-8") as handle:
        return json.load(handle)


class RoutingCases(unittest.TestCase):
    suite = load()
    agents = {os.path.basename(p)[:-3] for p in glob.glob(os.path.join(ROOT, "agents", "*.md"))}
    skills = {os.path.basename(p) for p in glob.glob(os.path.join(ROOT, "skills", "*")) if os.path.isdir(p)}
    workflows = {os.path.basename(p)[:-3] for p in glob.glob(os.path.join(ROOT, "workflows", "*.js"))}

    def test_fixture_and_runner_exist(self):
        fixture = os.path.normpath(os.path.join(os.path.dirname(SUITE), self.suite["fixture"]))
        self.assertTrue(os.path.isfile(os.path.join(fixture, "Orders.sln")), fixture)
        self.assertTrue(os.access(os.path.join(os.path.dirname(SUITE), "run.py"), os.X_OK))

    def test_case_names_are_unique_and_prompts_present(self):
        names = [c["name"] for c in self.suite["cases"]]
        self.assertEqual(len(names), len(set(names)))
        for case in self.suite["cases"]:
            with self.subTest(case=case["name"]):
                self.assertTrue(case["prompt"].strip())
                self.assertTrue(any(k in case for k in ("expect_any", "forbid", "stream_contains", "file_absent")),
                                "a case with nothing to check proves nothing")

    def test_rules_compile_and_name_real_targets(self):
        for case in self.suite["cases"]:
            for rule in case.get("forbid", []):
                with self.subTest(case=case["name"], rule=rule):
                    self.assertIn(rule["tool"], TOOLS)
                    re.compile(rule["input"])
            for rule in case.get("expect_any", []):
                with self.subTest(case=case["name"], rule=rule):
                    self.assertIn(rule["tool"], TOOLS)
                    re.compile(rule["input"])
                    for agent in re.findall(r"agentic-sdd-flow:\(?([a-z|-]+)\)?", rule["input"]):
                        for name in agent.split("|"):
                            self.assertIn(name, self.agents, name)
                    if rule["tool"] == "Skill" and rule["input"]:
                        for name in rule["input"].split("|"):
                            self.assertIn(name, self.skills, name)
                    if rule["tool"] == "Workflow" and rule["input"]:
                        self.assertIn(rule["input"], self.workflows)

    def test_allowed_tools_are_well_formed(self):
        pattern = re.compile(r"^[A-Za-z]+(\([^)]+\))?$")
        for entry in self.suite["defaults"]["allowed_tools"] + [t for c in self.suite["cases"] for t in c.get("allowed_tools_extra", [])]:
            with self.subTest(tool=entry):
                self.assertRegex(entry, pattern)


if __name__ == "__main__":
    unittest.main()
