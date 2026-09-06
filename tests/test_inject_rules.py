import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import _paths

inject_rules = _paths.load_module("inject_rules", os.path.join(_paths.SCRIPTS, "inject-rules.py"))


class InjectorCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = os.path.realpath(self._tmp.name)
        patch = mock.patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": self.root}, clear=False)
        patch.start()
        self.addCleanup(patch.stop)
        note = mock.patch.object(inject_rules, "navigator_note", return_value="")
        note.start()
        self.addCleanup(note.stop)

    def write(self, rel, content):
        path = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(content)
        return path

    def run_mode(self, mode, payload=None, raw=None):
        stdin = io.StringIO(raw if raw is not None else json.dumps(payload or {}))
        stdout = io.StringIO()
        with mock.patch.object(sys, "stdin", stdin), mock.patch.object(sys, "argv", ["inject-rules.py", mode]):
            with contextlib.redirect_stdout(stdout):
                code = inject_rules.main()
        return code, stdout.getvalue()


class SessionMode(InjectorCase):
    def test_contract_and_overlay_are_injected_once(self):
        overlay = self.write(".claude/rules/OVERLAY-CONTRACT.md", "# Overlay\n\nThe billing service owns invoices.\n")
        code, out = self.run_mode("session")
        self.assertEqual(code, 0)
        self.assertEqual(out.count('<rules-contract enforcement="mandatory">'), 1)
        self.assertEqual(out.count("<overlay-contract source=\"%s\">" % overlay), 1)
        self.assertIn("The billing service owns invoices.", out)
        self.assertIn("</overlay-contract>", out)
        self.assertIn("# Rules Contract", out)
        self.assertIn("Plugin root: %s" % _paths.PLUGIN_ROOT, out)
        self.assertIn("/agentic-sdd-flow:dotnet-feature", out)
        self.assertTrue(out.rstrip().endswith("</rules-contract>"))

    def test_no_overlay_block_without_an_overlay_file(self):
        _, out = self.run_mode("session")
        self.assertIn("# Rules Contract", out)
        self.assertNotIn("<overlay-contract", out)

    def test_overlay_path_comes_from_config(self):
        self.write(".claude/agentic-sdd-flow.json", json.dumps({"overlayContract": "docs/OVERLAY.md"}))
        overlay = self.write("docs/OVERLAY.md", "custom overlay body")
        _, out = self.run_mode("session")
        self.assertIn("<overlay-contract source=\"%s\">" % overlay, out)
        self.assertIn("custom overlay body", out)

    def test_navigator_warning_is_surfaced(self):
        with mock.patch.object(inject_rules, "navigator_note", return_value="Roslyn navigator: WARN"):
            _, out = self.run_mode("session")
        self.assertIn("Roslyn navigator: WARN", out)

    def test_invalid_stdin_still_injects(self):
        code, out = self.run_mode("session", raw="garbage")
        self.assertEqual(code, 0)
        self.assertIn("# Rules Contract", out)


class PromptMode(InjectorCase):
    TRIGGERS = [
        "please run the dotnet-sdd workflow on temp/plans/x.md",
        "execute the plan",
        "выполни план из temp/plans",
        "/agentic-sdd-flow:dotnet-feature PROJ-1 add endpoint",
        "ultracode implement the brands endpoint",
        "use superpowers:writing-plans for this",
        "architecture-design for the outbox",
    ]

    def test_plan_flow_prompts_get_the_controller_contract(self):
        for prompt in self.TRIGGERS:
            with self.subTest(prompt=prompt):
                code, out = self.run_mode("prompt", {"prompt": prompt})
                self.assertEqual(code, 0)
                self.assertIn("You are the controller.", out)
                self.assertIn("# Rules Contract", out)

    def test_ordinary_prompts_are_left_alone(self):
        for prompt in ("fix the typo in README", "what does this handler do?", ""):
            with self.subTest(prompt=prompt):
                self.assertEqual(self.run_mode("prompt", {"prompt": prompt}), (0, ""))

    def test_overlay_rides_along_in_prompt_mode(self):
        self.write(".claude/rules/OVERLAY-CONTRACT.md", "overlay fact")
        _, out = self.run_mode("prompt", {"prompt": "execute the plan"})
        self.assertIn("overlay fact", out)


class SubagentMode(InjectorCase):
    def test_emits_additional_context_json(self):
        self.write(".claude/rules/OVERLAY-CONTRACT.md", "overlay fact")
        code, out = self.run_mode("subagent", {"agent_type": "agentic-sdd-flow:code-reviewer"})
        self.assertEqual(code, 0)
        payload = json.loads(out)
        block = payload["hookSpecificOutput"]
        self.assertEqual(block["hookEventName"], "SubagentStart")
        context = block["additionalContext"]
        self.assertIn('<rules-contract enforcement="mandatory">', context)
        self.assertIn("## Roslyn access", context)
        self.assertIn(os.path.join(_paths.PLUGIN_ROOT, "bin", "roslyn-query.py"), context)
        self.assertIn("overlay fact", context)
        self.assertIn("# Rules Contract", context)
        self.assertIn("## Working budget", context)
        self.assertIn("dotnet --version", context)
        self.assertLess(context.index("## Working budget"), context.index("# Rules Contract"))

    def test_budget_is_for_agents_only(self):
        _, session = self.run_mode("session")
        _, prompt = self.run_mode("prompt", {"prompt": "execute the plan"})
        self.assertNotIn("## Working budget", session)
        self.assertNotIn("## Working budget", prompt)

    def test_default_mode_is_subagent(self):
        stdin = io.StringIO("{}")
        stdout = io.StringIO()
        with mock.patch.object(sys, "stdin", stdin), mock.patch.object(sys, "argv", ["inject-rules.py"]):
            with contextlib.redirect_stdout(stdout):
                inject_rules.main()
        self.assertEqual(json.loads(stdout.getvalue())["hookSpecificOutput"]["hookEventName"], "SubagentStart")


class NavigatorNote(unittest.TestCase):
    def note_for(self, listing):
        completed = subprocess.CompletedProcess(args=[], returncode=0, stdout=listing, stderr="")
        with mock.patch.object(inject_rules.subprocess, "run", return_value=completed):
            return inject_rules.navigator_note()

    def test_current_version_is_silent(self):
        for version in ("0.8.0", "0.9.3", "0.10.1", "1.0.0"):
            with self.subTest(version=version):
                self.assertEqual(self.note_for("cwm.roslynnavigator   %s   cwm-roslyn-navigator\n" % version), "")

    def test_old_version_warns(self):
        note = self.note_for("cwm.roslynnavigator   0.7.2   cwm-roslyn-navigator\n")
        self.assertIn("0.7.2 is below 0.8.0", note)
        self.assertIn("dotnet tool update", note)

    def test_missing_tool_is_reported(self):
        self.assertIn("not installed", self.note_for("Package Id   Version   Commands\n"))

    def test_missing_dotnet_is_reported(self):
        with mock.patch.object(inject_rules.subprocess, "run", side_effect=OSError("no dotnet")):
            self.assertIn("`dotnet` not found", inject_rules.navigator_note())


class HookProcess(unittest.TestCase):
    """The script as the SessionStart hook runs it: a real subprocess with stdin JSON."""

    def test_session_mode_prints_the_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, ".claude", "rules"))
            with open(os.path.join(tmp, ".claude", "rules", "OVERLAY-CONTRACT.md"), "w") as handle:
                handle.write("overlay fact")
            proc = subprocess.run([sys.executable, os.path.join(_paths.SCRIPTS, "inject-rules.py"), "session"],
                                  input="{}", capture_output=True, text=True,
                                  env=_paths.hook_env(CLAUDE_PROJECT_DIR=tmp), timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.count("<rules-contract"), 1)
        self.assertEqual(proc.stdout.count("<overlay-contract"), 1)
        self.assertIn("overlay fact", proc.stdout)


if __name__ == "__main__":
    unittest.main()
