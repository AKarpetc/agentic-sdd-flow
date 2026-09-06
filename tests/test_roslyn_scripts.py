import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest

import _paths

RESOLVER = os.path.join(_paths.BIN, "roslyn-resolve.sh")
BIND = os.path.join(_paths.BIN, "bind-roslyn.sh")
NAVIGATOR = os.path.join(_paths.BIN, "roslyn-navigator.sh")
QUERY = os.path.join(_paths.BIN, "roslyn-query.py")


class Fixture(unittest.TestCase):
    """A consumer repository with three project layouts and a name index."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = os.path.realpath(self._tmp.name)
        self.alpha = self.touch("Projects/Alpha/Alpha.sln")
        self.beta = self.touch("Projects/Beta/Beta.slnx")
        self.touch("Projects/Gamma/One.sln")
        self.touch("Projects/Gamma/Two.sln")
        os.makedirs(os.path.join(self.root, "Projects", "Delta"))
        self.touch(".claude/agentic-sdd-flow.json", json.dumps({"projects": {
            "named": "Projects/Alpha/Alpha.sln",
            "by-dir": "Projects/Beta",
            "dangling": "Projects/Nope/Nope.sln",
        }}))
        self.state = os.path.join(self.root, "state")

    def touch(self, rel, content=""):
        path = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as handle:
            handle.write(content)
        return path

    def env(self, **extra):
        return _paths.hook_env(CLAUDE_PROJECT_DIR=self.root, CLAUDE_PLUGIN_DATA=self.state, **extra)


class ResolveSolution(Fixture):
    def resolve(self, target):
        proc = subprocess.run(["bash", "-c", 'source "$1"; roslyn_resolve_solution "$2" "$3"', "_", RESOLVER, self.root, target],
                              capture_output=True, text=True, timeout=60)
        return proc.returncode, proc.stdout.strip()

    def test_absolute_and_root_relative_solution_paths(self):
        self.assertEqual(self.resolve(self.alpha), (0, self.alpha))
        self.assertEqual(self.resolve("Projects/Beta/Beta.slnx"), (0, self.beta))

    def test_missing_solution_file_fails(self):
        code, out = self.resolve("Projects/Alpha/Missing.sln")
        self.assertEqual(code, 1)
        self.assertIn("no solution file", out)

    def test_directory_paths(self):
        self.assertEqual(self.resolve(os.path.join(self.root, "Projects", "Alpha")), (0, self.alpha))
        self.assertEqual(self.resolve("Projects/Beta"), (0, self.beta))

    def test_indexed_names(self):
        self.assertEqual(self.resolve("named"), (0, self.alpha))
        self.assertEqual(self.resolve("by-dir"), (0, self.beta))

    def test_dangling_index_entry_falls_through_to_search(self):
        code, out = self.resolve("dangling")
        self.assertEqual(code, 1)
        self.assertIn('no .sln/.slnx found for "dangling"', out)

    def test_exact_then_substring_directory_match(self):
        self.assertEqual(self.resolve("Alpha"), (0, self.alpha))
        self.assertEqual(self.resolve("lph"), (0, self.alpha))

    def test_two_solutions_in_one_directory_is_ambiguous(self):
        code, out = self.resolve("Gamma")
        self.assertEqual(code, 1)
        self.assertIn("ambiguous", out)
        self.assertIn("One.sln", out)
        self.assertIn("Two.sln", out)

    def test_directory_without_a_solution_fails(self):
        code, out = self.resolve("Delta")
        self.assertEqual(code, 1)
        self.assertIn("no .sln/.slnx found", out)


class BindRoslyn(Fixture):
    def test_pins_the_resolved_solution(self):
        proc = subprocess.run([BIND, "Alpha"], capture_output=True, text=True, env=self.env(), timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("pinned: %s" % self.alpha, proc.stdout)
        with open(os.path.join(self.state, "roslyn-solution")) as handle:
            self.assertEqual(handle.read().strip(), self.alpha)

    def test_usage_shows_the_current_pin(self):
        os.makedirs(self.state)
        with open(os.path.join(self.state, "roslyn-solution"), "w") as handle:
            handle.write(self.beta + "\n")
        proc = subprocess.run([BIND], capture_output=True, text=True, env=self.env(), timeout=60)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("usage:", proc.stdout)
        self.assertIn(self.beta, proc.stdout)

    def test_unresolvable_target_fails(self):
        proc = subprocess.run([BIND, "Zeta"], capture_output=True, text=True, env=self.env(), timeout=60)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("error:", proc.stderr)


class NavigatorWrapper(Fixture):
    def setUp(self):
        super().setUp()
        self.fake = self.touch("fake-navigator.sh", "#!/bin/sh\necho \"ARGS:$*\"\n")
        os.chmod(self.fake, os.stat(self.fake).st_mode | stat.S_IXUSR)

    def launch(self, **extra):
        return subprocess.run([NAVIGATOR], capture_output=True, text=True, timeout=60,
                              env=self.env(ROSLYN_NAVIGATOR_BIN=self.fake, **extra))

    def test_pinned_solution_is_passed_to_the_tool(self):
        os.makedirs(self.state)
        with open(os.path.join(self.state, "roslyn-solution"), "w") as handle:
            handle.write("# pinned by tests\nnamed\n")
        proc = self.launch()
        self.assertEqual(proc.stdout.strip(), "ARGS:--solution %s" % self.alpha)
        self.assertIn("binding %s" % self.alpha, proc.stderr)

    def test_environment_override_beats_the_pointer(self):
        os.makedirs(self.state)
        with open(os.path.join(self.state, "roslyn-solution"), "w") as handle:
            handle.write("named\n")
        proc = self.launch(ROSLYN_SOLUTION="Beta")
        self.assertEqual(proc.stdout.strip(), "ARGS:--solution %s" % self.beta)

    def test_no_pin_falls_back_to_auto_discovery(self):
        proc = self.launch()
        self.assertEqual(proc.stdout.strip(), "ARGS:")
        self.assertIn("no solution pinned", proc.stderr)

    def test_unresolvable_pin_falls_back_with_the_reason(self):
        os.makedirs(self.state)
        with open(os.path.join(self.state, "roslyn-solution"), "w") as handle:
            handle.write("Zeta\n")
        proc = self.launch()
        self.assertEqual(proc.stdout.strip(), "ARGS:")
        self.assertIn("no .sln/.slnx found", proc.stderr)


class QueryRunner(Fixture):
    def test_unresolvable_target_exits_with_a_reason(self):
        proc = subprocess.run([sys.executable, QUERY, "Zeta", "--status"], capture_output=True, text=True,
                              env=self.env(), timeout=60)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("cannot resolve 'Zeta'", proc.stderr)

    def test_no_arguments_prints_usage(self):
        proc = subprocess.run([sys.executable, QUERY], capture_output=True, text=True, env=self.env(), timeout=60)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("roslyn-query.py <project-or-solution> <tool>", proc.stdout)

    def test_status_without_a_daemon_reports_not_running(self):
        socket_dir = os.path.join(self.root, "sockets")
        proc = subprocess.run([sys.executable, QUERY, "Alpha", "--stop"], capture_output=True, text=True,
                              env=self.env(TMPDIR=socket_dir), timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout), {"solution": self.alpha, "running": False})

    def test_socket_paths_are_stable_and_distinct(self):
        module = _paths.load_module("roslyn_query", QUERY)
        first = module.socket_path("/repo/A/App.sln")
        self.assertEqual(first, module.socket_path("/repo/A/App.sln"))
        self.assertNotEqual(first, module.socket_path("/repo/B/App.sln"))
        self.assertTrue(os.path.basename(first).startswith("App.sln-"))


if __name__ == "__main__":
    unittest.main()
