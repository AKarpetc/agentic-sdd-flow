import io
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

import _paths

SCRIPT = os.path.join(_paths.SCRIPTS, "agent-pulse.py")
pulse = _paths.load_module("agent_pulse", SCRIPT)


class PulseCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = os.path.join(self._tmp.name, "pulse")
        patch = mock.patch.dict(os.environ, {"ASF_PULSE_DIR": self.dir})
        patch.start()
        self.addCleanup(patch.stop)

    def note(self, payload, raw=None):
        proc = subprocess.run([sys.executable, SCRIPT, "note"], input=raw if raw is not None else json.dumps(payload),
                              capture_output=True, text=True, env=dict(os.environ), timeout=60)
        self.assertEqual((proc.returncode, proc.stdout), (0, ""), proc.stderr)

    def render(self, session="s1"):
        proc = subprocess.run([sys.executable, SCRIPT, "render"], input=json.dumps({"session_id": session}),
                              capture_output=True, text=True, env=dict(os.environ), timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return proc.stdout

    def state(self, session="s1"):
        with open(os.path.join(self.dir, session + ".json"), encoding="utf-8") as handle:
            return json.load(handle)["agents"]

    def event(self, name, agent="a1", agent_type="agentic-sdd-flow:tests-writer", **extra):
        payload = {"hook_event_name": name, "session_id": "s1", "agent_id": agent, "agent_type": agent_type}
        payload.update(extra)
        return payload


class Recording(PulseCase):
    def test_main_session_calls_leave_no_trace(self):
        self.note({"hook_event_name": "PreToolUse", "session_id": "s1", "tool_name": "Bash", "tool_input": {"command": "ls"}})
        self.assertFalse(os.path.exists(self.dir) and os.listdir(self.dir))
        self.assertEqual(self.render(), "")

    def test_subagent_lifecycle_is_recorded(self):
        self.note(self.event("SubagentStart"))
        self.note(self.event("PreToolUse", tool_name="Read", tool_input={"file_path": "/repo/src/OrderService.cs"}))
        self.note(self.event("PreToolUse", tool_name="Bash", tool_input={"command": "dotnet test --no-build", "description": "Run the tests"}))
        entry = self.state()["a1"]
        self.assertEqual(entry["type"], "tests-writer")
        self.assertEqual(entry["status"], "running")
        self.assertEqual(entry["tools"], 2)
        self.assertEqual(entry["action"], "Bash Run the tests")
        self.note(self.event("SubagentStop"))
        entry = self.state()["a1"]
        self.assertEqual((entry["status"], entry["action"]), ("done", "done"))

    def test_two_agents_share_one_file(self):
        self.note(self.event("SubagentStart", agent="a1"))
        self.note(self.event("SubagentStart", agent="a2", agent_type="agentic-sdd-flow:code-reviewer"))
        self.note(self.event("PreToolUse", agent="a2", agent_type="agentic-sdd-flow:code-reviewer", tool_name="Grep", tool_input={"pattern": "IOptions<"}))
        agents = self.state()
        self.assertEqual({a["type"] for a in agents.values()}, {"tests-writer", "code-reviewer"})
        self.assertEqual(agents["a2"]["action"], "Grep IOptions<")

    def test_garbage_input_is_ignored(self):
        self.note(None, raw="not json")
        self.assertFalse(os.path.exists(self.dir) and os.listdir(self.dir))


class Rendering(PulseCase):
    def test_running_agents_show_type_elapsed_action_and_count(self):
        self.note(self.event("SubagentStart"))
        self.note(self.event("PreToolUse", tool_name="Edit", tool_input={"file_path": "/repo/tests/OrderServiceTests.cs"}))
        line = self.render()
        self.assertIn("⟳ tests-writer 0m", line)
        self.assertIn("· Edit OrderServiceTests.cs (1)", line)

    def test_finished_agents_fade_out(self):
        self.note(self.event("SubagentStart"))
        self.note(self.event("SubagentStop"))
        self.assertIn("✓ tests-writer", self.render())
        path = os.path.join(self.dir, "s1.json")
        with open(path, encoding="utf-8") as handle:
            state = json.load(handle)
        state["agents"]["a1"]["last"] -= pulse.DONE_VISIBLE_SECONDS + 5
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(state, handle)
        self.assertEqual(self.render(), "")

    def test_unknown_session_renders_nothing(self):
        self.assertEqual(self.render("nope"), "")

    def test_two_running_agents_are_separated(self):
        self.note(self.event("SubagentStart", agent="a1"))
        self.note(self.event("SubagentStart", agent="a2", agent_type="agentic-sdd-flow:code-reviewer"))
        line = self.render()
        self.assertIn("  |  ", line)
        self.assertLess(line.index("tests-writer"), line.index("code-reviewer"))


class Summaries(unittest.TestCase):
    def test_short_true_phrases(self):
        cases = [
            ("Bash", {"command": "dotnet build\nmore", "description": "Build the solution"}, "Bash Build the solution"),
            ("Bash", {"command": "git status --short"}, "Bash git status --short"),
            ("Write", {"file_path": "/a/b/Probe.cs"}, "Write Probe.cs"),
            ("Glob", {"pattern": "**/*.csproj"}, "Glob **/*.csproj"),
            ("Agent", {"subagent_type": "agentic-sdd-flow:findings-verifier"}, "Agent agentic-sdd-flow:findings-verifier"),
            ("Skill", {"skill": "dotnet-code-review"}, "Skill dotnet-code-review"),
            ("mcp__cwm-roslyn-navigator__find_symbol", {"query": "OrderService"}, "find_symbol OrderService"),
            (None, {}, "?"),
        ]
        for tool, tool_input, expected in cases:
            with self.subTest(tool=tool):
                self.assertEqual(pulse.summarise(tool, tool_input), expected)

    def test_long_phrases_are_truncated(self):
        text = pulse.summarise("Bash", {"command": "x" * 200})
        self.assertEqual(len(text), pulse.ACTION_WIDTH)
        self.assertTrue(text.endswith("…"))

    def test_elapsed_formats(self):
        self.assertEqual(pulse.elapsed(0), "0m00s")
        self.assertEqual(pulse.elapsed(130), "2m10s")
        self.assertEqual(pulse.elapsed(3 * 3600 + 5 * 60), "3h05m")


if __name__ == "__main__":
    unittest.main()
