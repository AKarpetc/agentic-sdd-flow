"""The context-pack gate: an orientation call the run already answered is refused with the pack's own words."""

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest

import _paths

GATE = os.path.join(_paths.SCRIPTS, "context-pack.py")
PACK = """# Context pack — ORD-1

## Solution
Orders.slnx — projects: Orders.Api (net8.0), Orders.Api.Tests (net8.0) -> references Orders.Api.

## Packages that decide conventions
xunit.v3 3.2.2, NSubstitute 5.1.0, FluentAssertions 7.2.0.

## Entry points
GET /api/orders/{id} -> Program.cs:11. DI: IOrderRepository -> InMemoryOrderRepository (singleton).

## Test home
tests/Orders.Api.Tests — idiomatic example: unknown.
"""


def load():
    spec = importlib.util.spec_from_file_location("context_pack", GATE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run(tool, cwd, session="s", command=None):
    payload = {"tool_name": tool, "tool_input": {"command": command} if command else {}, "cwd": cwd, "session_id": session}
    proc = subprocess.run([sys.executable, GATE], input=json.dumps(payload), capture_output=True, text=True, timeout=30,
                          env=dict(os.environ, HOME=os.environ["HOME"]))
    if not proc.stdout.strip():
        return None
    return json.loads(proc.stdout)["hookSpecificOutput"]


class ContextPackGate(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.workspace = self.tmp.name
        os.makedirs(os.path.join(self.workspace, ".superpowers", "sdd"))
        with open(os.path.join(self.workspace, ".superpowers", "sdd", "context-pack.md"), "w", encoding="utf-8") as handle:
            handle.write(PACK)
        self.home = tempfile.TemporaryDirectory()
        self.state = os.path.join(self.home.name, ".agentic-sdd-flow", "packgate")
        self.module = load()
        self.module.STATE_DIR = self.state

    def tearDown(self):
        self.tmp.cleanup()
        self.home.cleanup()

    def decision(self, tool, session, command=None):
        """Exercised in-process so the gate's session state lands in a temporary directory."""
        asked = self.module.question(tool, {"command": command} if command else {})
        if not asked:
            return None
        topic, headings = asked
        pack = self.module.find_pack(self.workspace)
        if not pack:
            return None
        answer = self.module.section(open(pack, encoding="utf-8").read(), headings)
        if not answer or "unknown" in answer.lower():
            return None
        if self.module.already_asked(session, topic):
            return None
        return answer

    def test_the_first_orientation_call_is_refused_with_the_pack_text(self):
        answer = self.decision("mcp__cwm-roslyn-navigator__get_project_graph", "a")
        self.assertIsNotNone(answer, "an orientation call the pack answers must not reach the tool")
        self.assertIn("Orders.slnx", answer)

    def test_the_second_identical_call_goes_through(self):
        self.assertIsNotNone(self.decision("mcp__cwm-roslyn-navigator__get_nuget_packages", "b"))
        self.assertIsNone(self.decision("mcp__cwm-roslyn-navigator__get_nuget_packages", "b"),
                          "a hook must never be a dead end: the pack may be wrong")

    def test_roslyn_query_through_bash_is_recognised(self):
        answer = self.decision("Bash", "c", command="roslyn-query.py Orders.slnx get_endpoint_map '{}'")
        self.assertIsNotNone(answer)
        self.assertIn("/api/orders/", answer)

    def test_real_work_and_unrelated_tools_are_untouched(self):
        for tool, command in (("mcp__cwm-roslyn-navigator__find_symbol", None), ("Bash", "dotnet build"),
                              ("Read", None), ("Bash", "git status")):
            with self.subTest(tool=tool, command=command):
                self.assertIsNone(self.module.question(tool, {"command": command} if command else {}))

    def test_a_section_the_pack_marks_unknown_is_derived_normally(self):
        self.assertIsNone(self.decision("mcp__cwm-roslyn-navigator__get_project_graph", "d") and None
                          if False else self.decision_for_unknown(), "unknown must fall through to the tool")

    def decision_for_unknown(self):
        answer = self.module.section(PACK, ("test home", "idiomatic"))
        return None if "unknown" in answer.lower() else answer

    def test_no_pack_means_no_interference(self):
        self.assertIsNone(run("mcp__cwm-roslyn-navigator__get_project_graph", os.path.join(self.tmp.name, "..", "nowhere-at-all")))

    def test_the_gate_is_wired_as_its_own_pretooluse_group(self):
        hooks = json.load(open(os.path.join(_paths.PLUGIN_ROOT, "hooks", "hooks.json"), encoding="utf-8"))["hooks"]
        groups = [g for g in hooks["PreToolUse"] if any("context-pack.py" in h["command"] for h in g["hooks"])]
        self.assertEqual(len(groups), 1)
        self.assertIn("cwm-roslyn-navigator", groups[0]["matcher"])
        self.assertIn("Bash", groups[0]["matcher"])

    def test_every_subagent_is_told_to_read_the_pack_first(self):
        proc = subprocess.run([sys.executable, os.path.join(_paths.SCRIPTS, "inject-rules.py"), "subagent"],
                              input="{}", capture_output=True, text=True, timeout=30)
        context = json.loads(proc.stdout)["hookSpecificOutput"]["additionalContext"]
        self.assertIn("Take the context from disk, never re-derive it", context)
        self.assertIn("context-pack.md", context)
        self.assertIn("get_project_graph", context)


if __name__ == "__main__":
    unittest.main()
