#!/usr/bin/env python3
"""Shared helpers: locate the consuming project's root and read `.claude/agentic-sdd-flow.json`."""

import json
import os
import subprocess

CONFIG_REL = os.path.join(".claude", "agentic-sdd-flow.json")
DEFAULT_OVERLAY_REL = os.path.join(".claude", "rules", "OVERLAY-CONTRACT.md")

DEFAULTS = {
    "taskKeyPattern": r"[A-Z][A-Z0-9]+-\d+",
    "plansDir": "temp/plans",
    "adrDir": "docs/architecture/decisions",
    "docsPaths": ["docs", "CLAUDE.md"],
    "projects": {},
    "checks": {},
    "routing": {},  # {"default": quick|mix|light|standard|deep, "maxAutoTier": ...} — see routing_policy()
    "handoffs": {},
    "overlayContract": DEFAULT_OVERLAY_REL,
}


def _has_marker(directory):
    return (os.path.isfile(os.path.join(directory, CONFIG_REL))
            or os.path.isfile(os.path.join(directory, DEFAULT_OVERLAY_REL)))


def find_project_root(start=None):
    """CLAUDE_PROJECT_DIR if set; otherwise walk up from `start` to the first directory that
    holds a plugin config or overlay contract; otherwise the git top-level; otherwise `start`."""
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    if env and os.path.isdir(env):
        return os.path.abspath(env)
    current = os.path.abspath(start or os.getcwd())
    probe = current
    while True:
        if _has_marker(probe):
            return probe
        parent = os.path.dirname(probe)
        if parent == probe:
            break
        probe = parent
    try:
        top = subprocess.run(["git", "-C", current, "rev-parse", "--show-toplevel"],
                             capture_output=True, text=True, timeout=5)
        if top.returncode == 0 and top.stdout.strip():
            return top.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return current


TIERS = ["quick", "mix", "light", "standard", "deep"]


def routing_policy(cfg):
    """The repository's routing preference, normalised: {"default": <tier>, "maxAutoTier": <tier>}.

    `default` is the route to take when nothing in the brief demands more; `maxAutoTier` is the highest
    route the sizing gate may pick on its own — above it the user has to say so. Unknown tier names are
    dropped rather than guessed, so a typo turns the policy off instead of silently routing somewhere."""
    if str(os.environ.get("ASF_ROUTING_POLICY", "")).strip().lower() in ("off", "0", "ignore", "none"):
        return {}  # the plugin's own evals measure the sizing gate; a host policy would decide for it
    raw = cfg.get("routing")
    if not isinstance(raw, dict):
        return {}
    policy = {}
    for key in ("default", "maxAutoTier"):
        value = str(raw.get(key, "")).strip().lower()
        if value in TIERS:
            policy[key] = value
    if isinstance(raw.get("note"), str) and raw["note"].strip():
        policy["note"] = raw["note"].strip()
    return policy


def load_config(root):
    """Merged config: DEFAULTS overridden by `.claude/agentic-sdd-flow.json` when present."""
    merged = json.loads(json.dumps(DEFAULTS))
    path = os.path.join(root, CONFIG_REL)
    if not os.path.isfile(path):
        return merged
    try:
        with open(path, encoding="utf-8") as handle:
            user = json.load(handle)
    except (OSError, ValueError):
        return merged
    for key, value in user.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key].update(value)
        else:
            merged[key] = value
    return merged


def overlay_contract_path(root, cfg):
    path = cfg.get("overlayContract") or DEFAULT_OVERLAY_REL
    if not os.path.isabs(path):
        path = os.path.join(root, path)
    return path if os.path.isfile(path) else None


def data_dir():
    """Per-machine state directory for the plugin."""
    path = os.environ.get("CLAUDE_PLUGIN_DATA") or os.path.join(os.path.expanduser("~"), ".agentic-sdd-flow")
    os.makedirs(path, exist_ok=True)
    return path
