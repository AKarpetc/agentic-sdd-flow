"""Shared locations and loaders for the plugin's test-suite (stdlib unittest only)."""

import importlib.util
import os
import sys

PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(PLUGIN_ROOT, "scripts")
BIN = os.path.join(PLUGIN_ROOT, "bin")
RULES = os.path.join(PLUGIN_ROOT, "rules")

if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)


def load_module(name, path):
    """Imports a script whose filename is not a valid module name (e.g. check-rules.py)."""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def hook_env(**extra):
    """A subprocess environment with no inherited project/plugin-data pointers."""
    env = {k: v for k, v in os.environ.items() if k not in ("CLAUDE_PROJECT_DIR", "CLAUDE_PLUGIN_DATA")}
    env.update(extra)
    return env
