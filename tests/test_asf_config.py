import json
import os
import subprocess
import tempfile
import unittest
from unittest import mock

import _paths  # noqa: F401  (puts scripts/ on sys.path)
import asf_config


class TempRoot(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = os.path.realpath(self._tmp.name)
        patch = mock.patch.dict(os.environ, {}, clear=False)
        patch.start()
        self.addCleanup(patch.stop)
        os.environ.pop("CLAUDE_PROJECT_DIR", None)
        os.environ.pop("CLAUDE_PLUGIN_DATA", None)

    def write(self, rel, content):
        path = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(content)
        return path

    def nested(self):
        path = os.path.join(self.root, "a", "b")
        os.makedirs(path, exist_ok=True)
        return path


class FindProjectRoot(TempRoot):
    def test_env_var_wins_over_markers(self):
        other = os.path.join(self.root, "other")
        os.makedirs(other)
        self.write(".claude/agentic-sdd-flow.json", "{}")
        os.environ["CLAUDE_PROJECT_DIR"] = other
        self.assertEqual(asf_config.find_project_root(self.nested()), other)

    def test_env_var_pointing_nowhere_is_ignored(self):
        os.environ["CLAUDE_PROJECT_DIR"] = os.path.join(self.root, "missing")
        self.write(".claude/agentic-sdd-flow.json", "{}")
        self.assertEqual(asf_config.find_project_root(self.nested()), self.root)

    def test_config_marker_is_found_walking_up(self):
        self.write(".claude/agentic-sdd-flow.json", "{}")
        self.assertEqual(asf_config.find_project_root(self.nested()), self.root)

    def test_overlay_marker_is_found_walking_up(self):
        self.write(".claude/rules/OVERLAY-CONTRACT.md", "# overlay")
        self.assertEqual(asf_config.find_project_root(self.nested()), self.root)

    def test_git_toplevel_is_the_fallback(self):
        subprocess.run(["git", "init", "-q", self.root], check=True)
        found = asf_config.find_project_root(self.nested())
        self.assertEqual(os.path.realpath(found), self.root)

    def test_start_directory_when_nothing_matches(self):
        nested = self.nested()
        self.assertEqual(os.path.realpath(asf_config.find_project_root(nested)), nested)


class LoadConfig(TempRoot):
    def test_defaults_when_no_file(self):
        cfg = asf_config.load_config(self.root)
        self.assertEqual(cfg, asf_config.DEFAULTS)
        cfg["projects"]["x"] = "x.sln"
        self.assertEqual(asf_config.DEFAULTS["projects"], {}, "load_config must hand out a copy")

    def test_user_values_override_and_dicts_merge(self):
        self.write(".claude/agentic-sdd-flow.json", json.dumps({
            "plansDir": "docs/plans",
            "docsPaths": ["docs"],
            "projects": {"alpha": "src/Alpha.sln"},
            "checks": {"no-moq": "off"},
        }))
        cfg = asf_config.load_config(self.root)
        self.assertEqual(cfg["plansDir"], "docs/plans")
        self.assertEqual(cfg["docsPaths"], ["docs"])
        self.assertEqual(cfg["projects"], {"alpha": "src/Alpha.sln"})
        self.assertEqual(cfg["checks"], {"no-moq": "off"})
        self.assertEqual(cfg["taskKeyPattern"], asf_config.DEFAULTS["taskKeyPattern"])
        self.assertEqual(cfg["overlayContract"], asf_config.DEFAULT_OVERLAY_REL)

    def test_invalid_json_falls_back_to_defaults(self):
        self.write(".claude/agentic-sdd-flow.json", "{not json")
        self.assertEqual(asf_config.load_config(self.root), asf_config.DEFAULTS)


class OverlayContractPath(TempRoot):
    def test_default_relative_path(self):
        path = self.write(".claude/rules/OVERLAY-CONTRACT.md", "# overlay")
        cfg = asf_config.load_config(self.root)
        self.assertEqual(asf_config.overlay_contract_path(self.root, cfg), path)

    def test_missing_file_is_none(self):
        cfg = asf_config.load_config(self.root)
        self.assertIsNone(asf_config.overlay_contract_path(self.root, cfg))

    def test_custom_relative_path_from_config(self):
        path = self.write("docs/OVERLAY.md", "# overlay")
        cfg = dict(asf_config.DEFAULTS, overlayContract="docs/OVERLAY.md")
        self.assertEqual(asf_config.overlay_contract_path(self.root, cfg), path)

    def test_custom_absolute_path_from_config(self):
        path = self.write("elsewhere/OVERLAY.md", "# overlay")
        cfg = dict(asf_config.DEFAULTS, overlayContract=path)
        self.assertEqual(asf_config.overlay_contract_path("/nonexistent", cfg), path)


class DataDir(TempRoot):
    def test_env_override_is_created(self):
        wanted = os.path.join(self.root, "state", "plugin")
        os.environ["CLAUDE_PLUGIN_DATA"] = wanted
        self.assertEqual(asf_config.data_dir(), wanted)
        self.assertTrue(os.path.isdir(wanted))


if __name__ == "__main__":
    unittest.main()
