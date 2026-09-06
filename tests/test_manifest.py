"""Structural lint of the plugin: manifests, hooks, agents, skills, rules, workflows stay consistent."""

import glob
import json
import os
import re
import shutil
import subprocess
import unittest

import _paths

ROOT = _paths.PLUGIN_ROOT
NAVIGATOR_TOOLS = {
    "detect_antipatterns", "detect_circular_dependencies", "find_callers", "find_dead_code",
    "find_implementations", "find_overrides", "find_references", "find_symbol", "get_dependency_graph",
    "get_di_registrations", "get_diagnostics", "get_endpoint_map", "get_file_outline", "get_nuget_packages",
    "get_project_graph", "get_public_api", "get_symbol_detail", "get_symbol_source", "get_test_coverage_map",
    "get_type_hierarchy",
}
HOOK_EVENTS = {"SessionStart", "SubagentStart", "UserPromptSubmit", "PostToolUse", "PreToolUse", "Stop"}
LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def frontmatter(path):
    text = read(path)
    if not text.startswith("---\n"):
        return None, text
    end = text.find("\n---\n", 4)
    if end == -1:
        return None, text
    block = text[4:end]
    fields = {}
    for match in re.finditer(r"^([A-Za-z_-]+):[ \t]*(.*)$", block, re.MULTILINE):
        key, value = match.group(1), match.group(2).strip()
        if value in (">", ">-", "|", "|-", ""):
            tail = block[match.end():]
            value = " ".join(line.strip() for line in tail.splitlines() if line.startswith((" ", "\t")))
        fields[key] = value
    return fields, text[end + 5:]


def markdown_files(*subdirs):
    files = []
    for sub in subdirs:
        files += glob.glob(os.path.join(ROOT, sub, "*.md"))
    return sorted(files)


class Manifests(unittest.TestCase):
    def test_plugin_and_marketplace_agree(self):
        plugin = json.loads(read(os.path.join(ROOT, ".claude-plugin", "plugin.json")))
        market = json.loads(read(os.path.join(ROOT, ".claude-plugin", "marketplace.json")))
        self.assertEqual(plugin["name"], "agentic-sdd-flow")
        entries = [p for p in market["plugins"] if p["name"] == plugin["name"]]
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["version"], plugin["version"])
        self.assertEqual(entries[0]["source"], "./")
        self.assertEqual(market["name"], "agentic-sdd-flow")

    def test_hooks_reference_existing_scripts(self):
        hooks = json.loads(read(os.path.join(ROOT, "hooks", "hooks.json")))["hooks"]
        self.assertTrue(set(hooks) <= HOOK_EVENTS, set(hooks))
        self.assertEqual(set(hooks), {"SessionStart", "SubagentStart", "UserPromptSubmit", "PostToolUse"})
        for event, groups in hooks.items():
            for group in groups:
                for hook in group["hooks"]:
                    self.assertEqual(hook["type"], "command")
                    match = re.search(r"\$\{CLAUDE_PLUGIN_ROOT\}/([^\"\s]+)", hook["command"])
                    self.assertIsNotNone(match, hook["command"])
                    self.assertTrue(os.path.isfile(os.path.join(ROOT, match.group(1))), match.group(1))
        self.assertEqual(hooks["PostToolUse"][0]["matcher"], "Write|Edit|MultiEdit|NotebookEdit")

    def test_mcp_servers_resolve(self):
        servers = json.loads(read(os.path.join(ROOT, ".mcp.json")))["mcpServers"]
        self.assertEqual(set(servers), {"cwm-roslyn-navigator", "postgres-mcp", "mssql-mcp"})
        navigator = servers["cwm-roslyn-navigator"]["command"]
        self.assertTrue(navigator.startswith("${CLAUDE_PLUGIN_ROOT}/"))
        self.assertTrue(os.access(os.path.join(ROOT, navigator.split("}/", 1)[1]), os.X_OK))
        for name in ("postgres-mcp", "mssql-mcp"):
            env_values = " ".join(servers[name]["env"].values())
            self.assertIn("${ASF_", env_values, "%s must be configured through ASF_* variables" % name)

    def test_executables_are_executable(self):
        for path in glob.glob(os.path.join(ROOT, "bin", "*")):
            self.assertTrue(os.access(path, os.X_OK), path)


class Agents(unittest.TestCase):
    agents = markdown_files("agents")

    def test_agents_exist(self):
        self.assertGreaterEqual(len(self.agents), 20)

    def test_frontmatter_is_complete_and_named_after_the_file(self):
        for path in self.agents:
            with self.subTest(agent=os.path.basename(path)):
                fields, body = frontmatter(path)
                self.assertIsNotNone(fields, "missing frontmatter")
                self.assertEqual(fields.get("name"), os.path.basename(path)[:-3])
                self.assertTrue(fields.get("description"), "missing description")
                self.assertTrue(fields.get("tools"), "missing tools")
                self.assertTrue(body.strip(), "empty body")

    def test_agents_cannot_dispatch_other_agents(self):
        for path in self.agents:
            with self.subTest(agent=os.path.basename(path)):
                fields, _ = frontmatter(path)
                tools = {tool.strip() for tool in fields["tools"].split(",")}
                self.assertFalse(tools & {"Agent", "Task", "Workflow"}, tools)

    def test_roslyn_tools_exist_on_the_navigator(self):
        for path in self.agents:
            with self.subTest(agent=os.path.basename(path)):
                fields, _ = frontmatter(path)
                names = re.findall(r"mcp__cwm-roslyn-navigator__([a-z_]+)", fields["tools"])
                self.assertTrue(set(names) <= NAVIGATOR_TOOLS, set(names) - NAVIGATOR_TOOLS)

    def test_db_agents_list_both_mcp_spellings(self):
        for path in self.agents:
            fields, _ = frontmatter(path)
            for server in ("postgres-mcp", "mssql-mcp"):
                bare = re.findall(r"(?<![\w-])mcp__%s__([a-z_]+)" % server, fields["tools"])
                prefixed = re.findall(r"mcp__plugin_agentic-sdd-flow_%s__([a-z_]+)" % server, fields["tools"])
                with self.subTest(agent=os.path.basename(path), server=server):
                    self.assertEqual(set(bare), set(prefixed))


class HandOffs(unittest.TestCase):
    def readme_keys(self):
        readme = read(os.path.join(ROOT, "README.md"))
        section = readme.split("## Company overlay", 1)[1].split("## Roslyn", 1)[0]
        return set(re.findall(r"^\| `([a-z-]+)` \|", section, re.MULTILINE))

    def test_readme_lists_the_keys_agents_use(self):
        keys = self.readme_keys()
        self.assertGreaterEqual(len(keys), 8)
        used = set()
        for path in markdown_files("agents"):
            used |= {key for key in keys if "`%s`" % key in read(path)}
        self.assertEqual(used, keys, "README keys nobody hands off to: %s" % (keys - used))

    def test_example_overlay_maps_known_keys_only(self):
        example = os.path.join(ROOT, "examples", "overlay", ".claude", "agentic-sdd-flow.json")
        cfg = json.loads(read(example))
        self.assertTrue(set(cfg.get("handoffs", {})) <= self.readme_keys(), set(cfg.get("handoffs", {})))
        overlay = os.path.join(ROOT, "examples", "overlay", cfg.get("overlayContract", ".claude/rules/OVERLAY-CONTRACT.md"))
        self.assertTrue(os.path.isfile(overlay), overlay)


class Skills(unittest.TestCase):
    def test_every_skill_has_a_named_skill_md(self):
        dirs = sorted(d for d in glob.glob(os.path.join(ROOT, "skills", "*")) if os.path.isdir(d))
        self.assertGreaterEqual(len(dirs), 50)
        for directory in dirs:
            with self.subTest(skill=os.path.basename(directory)):
                path = os.path.join(directory, "SKILL.md")
                self.assertTrue(os.path.isfile(path), "missing SKILL.md")
                fields, _ = frontmatter(path)
                self.assertIsNotNone(fields)
                self.assertEqual(fields.get("name"), os.path.basename(directory))
                self.assertTrue(fields.get("description"))

    def test_entry_point_skills_are_present(self):
        for name in ("dotnet-feature", "dotnet-code-review", "tests-writer", "architecture-design", "spec-coding"):
            self.assertTrue(os.path.isfile(os.path.join(ROOT, "skills", name, "SKILL.md")), name)


class Rules(unittest.TestCase):
    def test_contract_names_only_existing_rule_files(self):
        contract = read(os.path.join(_paths.RULES, "RULES-CONTRACT.md"))
        for target in LINK.findall(contract):
            self.assertTrue(os.path.isfile(os.path.join(_paths.RULES, target)), target)

    def test_relative_links_resolve(self):
        broken = []
        for path in markdown_files("rules", "knowledge", "agents") + [os.path.join(ROOT, "README.md")]:
            for target in LINK.findall(read(path)):
                if target.startswith(("http://", "https://", "mailto:", "#")):
                    continue
                resolved = os.path.normpath(os.path.join(os.path.dirname(path), target.split("#", 1)[0]))
                if not os.path.exists(resolved):
                    broken.append("%s -> %s" % (os.path.relpath(path, ROOT), target))
        self.assertEqual(broken, [])

    def test_readme_check_ids_match_the_gate(self):
        source = read(os.path.join(_paths.SCRIPTS, "check-rules.py"))
        in_code = set(re.findall(r'\(\s*"([a-z0-9-]+)",\s*re\.compile', source))
        in_code |= set(re.findall(r'(?:blocking|advisory)\.append\(\("([a-z0-9-]+)"', source))
        readme = read(os.path.join(ROOT, "README.md"))
        paragraph = readme.split("Check ids you can tune per repository:", 1)[1].split("\n\n", 1)[0]
        in_readme = set(re.findall(r"`([a-z0-9-]+)`", paragraph))
        self.assertEqual(in_readme, in_code)


class Sketches(unittest.TestCase):
    """Design artifacts are drawn as Mermaid: the convention file exists and every design stage is wired to it."""

    REFERENCE = os.path.join(ROOT, "skills", "architecture-design", "references", "sketch-conventions.md")

    def test_reference_exists_and_forbids_experimental_c4(self):
        text = read(self.REFERENCE)
        self.assertIn("```mermaid", text)
        self.assertIn("C4Context", text)
        for kind in ("flowchart", "sequenceDiagram", "erDiagram", "stateDiagram-v2"):
            self.assertIn(kind, text)

    def test_design_stages_reference_the_convention(self):
        wired = [os.path.join(ROOT, "agents", "design-%s.md" % lens) for lens in ("simplicity", "scalability", "boundaries", "judge")]
        wired += [os.path.join(ROOT, "workflows", "architecture-design.js"),
                  os.path.join(ROOT, "skills", "architecture-design", "SKILL.md")]
        for path in wired:
            with self.subTest(file=os.path.relpath(path, ROOT)):
                self.assertIn("sketch-conventions.md", read(path))

    def test_workflow_asks_for_mermaid_at_context_proposal_and_spec(self):
        text = read(os.path.join(ROOT, "workflows", "architecture-design.js"))
        self.assertGreaterEqual(text.count("sketch-conventions.md"), 4)
        self.assertIn("mermaid fences", text)


class WorkDistribution(unittest.TestCase):
    """Which agent each workflow phase dispatches to — the plugin's division of labour, pinned."""

    EXPECTED = {
        "dotnet-sdd.js": {
            "Analyze": set(), "Implement": {"implementer"}, "Tests": {"tests"}, "Review": {"reviewer"},
            "Verify": {"verifier"}, "Fix": {"implementer"}, "Final review": {"reviewer"},
        },
        "architecture-design.js": {
            "Drivers": set(), "Context": set(), "Proposals": {"simplicity", "scalability", "boundaries"},
            "Judge": {"judge"}, "Threats": {"security"}, "Data": {"migration"}, "Critic": set(), "Record": set(),
        },
    }
    PARALLEL = {"dotnet-sdd.js": {"Verify"}, "architecture-design.js": {"Context", "Proposals", "Judge"}}

    @staticmethod
    def segments(text):
        """Maps each phase label to the AGENT keys dispatched inside that phase's code."""
        found = {}
        parts = re.split(r"phase\('([^']+)'\)", text)
        for label, body in zip(parts[1::2], parts[2::2]):
            found.setdefault(label, {"agents": set(), "parallel": False})
            found[label]["agents"] |= set(re.findall(r"agentType: AGENT\.(\w+)", body))
            found[label]["parallel"] |= "parallel(" in body
        return found

    def test_each_phase_goes_to_its_agent(self):
        for name, expected in self.EXPECTED.items():
            found = self.segments(read(os.path.join(ROOT, "workflows", name)))
            with self.subTest(workflow=name):
                self.assertEqual(set(found), set(expected), "phases declared vs expected")
                for label, agents in expected.items():
                    self.assertEqual(found[label]["agents"], agents, "%s › %s" % (name, label))

    def test_fan_out_phases_run_in_parallel(self):
        for name, phases in self.PARALLEL.items():
            found = self.segments(read(os.path.join(ROOT, "workflows", name)))
            for label in phases:
                with self.subTest(workflow=name, phase=label):
                    self.assertTrue(found[label]["parallel"])

    def test_reviewer_never_implements_and_implementer_never_reviews(self):
        text = read(os.path.join(ROOT, "workflows", "dotnet-sdd.js"))
        found = self.segments(text)
        self.assertNotIn("reviewer", found["Implement"]["agents"] | found["Fix"]["agents"])
        self.assertNotIn("implementer", found["Review"]["agents"] | found["Final review"]["agents"])
        self.assertIn("agentType: AGENT.verifier", text)

    def test_meta_phases_match_the_dispatched_phases(self):
        for name in self.EXPECTED:
            text = read(os.path.join(ROOT, "workflows", name))
            meta = text.split("\n}\n", 1)[0]
            declared = re.findall(r"title: '([^']+)'", meta)
            with self.subTest(workflow=name):
                self.assertEqual(set(declared), set(self.EXPECTED[name]))


class Workflows(unittest.TestCase):
    workflows = sorted(glob.glob(os.path.join(ROOT, "workflows", "*.js")))

    def test_both_workflows_ship(self):
        self.assertEqual([os.path.basename(p) for p in self.workflows], ["architecture-design.js", "dotnet-sdd.js"])

    @unittest.skipUnless(shutil.which("node"), "node is not installed")
    def test_scripts_parse(self):
        for path in self.workflows:
            with self.subTest(workflow=os.path.basename(path)):
                proc = subprocess.run(["node", "--check", path], capture_output=True, text=True, timeout=60)
                self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_meta_is_a_literal_with_phases(self):
        for path in self.workflows:
            with self.subTest(workflow=os.path.basename(path)):
                text = read(path)
                self.assertTrue(text.startswith("export const meta = {"))
                meta = text.split("\n}\n", 1)[0]
                self.assertIn("name:", meta)
                self.assertIn("description:", meta)
                self.assertIn("phases:", meta)
                self.assertNotIn("${", meta, "meta must be a pure literal")

    def test_dispatched_agents_exist_and_are_namespaced(self):
        agents = {os.path.basename(p)[:-3] for p in markdown_files("agents")}
        for path in self.workflows:
            with self.subTest(workflow=os.path.basename(path)):
                text = read(path)
                self.assertIn("const PREFIX = 'agentic-sdd-flow:'", text)
                names = set(re.findall(r"PREFIX \+ '([a-z-]+)'", text))
                self.assertTrue(names)
                self.assertTrue(names <= agents, names - agents)
                self.assertNotIn("agentType: '", text.replace("agentType: PREFIX", ""),
                                 "agents must be dispatched through PREFIX")


if __name__ == "__main__":
    unittest.main()
