import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from unittest import mock

import _paths

check_rules = _paths.load_module("check_rules", os.path.join(_paths.SCRIPTS, "check-rules.py"))

SRC = "/repo/src/Orders/Foo.cs"
TEST = "/repo/tests/Orders.Tests/FooTests.cs"

CLEAN = textwrap.dedent("""\
    namespace P;

    /// <summary>Runs the thing.</summary>
    internal sealed class Foo
    {
        private readonly IBar _bar;

        public Foo(IBar bar)
        {
            _bar = bar;
        }

        public async Task<int> RunAsync(CancellationToken cancellationToken)
        {
            return await _bar.GetAsync(cancellationToken);
        }
    }
    """)


def ids(path, text):
    blocking, advisory = check_rules.inspect(path, text)
    return {rule for rule, _, _ in blocking}, {rule for rule, _, _ in advisory}


def wrap(body_line, path=SRC):
    """A clean file with one extra line inside the method body."""
    return CLEAN.replace("        return await _bar.GetAsync(cancellationToken);",
                         "        " + body_line + "\n        return await _bar.GetAsync(cancellationToken);")


class Structure(unittest.TestCase):
    def test_clean_file_has_no_findings(self):
        self.assertEqual(ids(SRC, CLEAN), (set(), set()))

    def test_two_top_level_types_block(self):
        text = CLEAN + "\ninternal sealed class Bar\n{\n}\n"
        blocking, _ = ids(SRC, text)
        self.assertIn("single-type-per-file", blocking)

    def test_filename_must_match_type(self):
        blocking, _ = ids("/repo/src/Wrong.cs", CLEAN)
        self.assertIn("filename-parity", blocking)

    def test_partial_types_skip_filename_parity(self):
        blocking, _ = ids("/repo/src/Foo.Part.cs", CLEAN.replace("internal sealed class", "internal partial class"))
        self.assertNotIn("filename-parity", blocking)

    def test_block_scoped_namespace_types_are_counted(self):
        text = "namespace P\n{\n    internal class Foo\n    {\n    }\n\n    internal class Bar\n    {\n    }\n}\n"
        blocking, _ = ids(SRC, text)
        self.assertIn("single-type-per-file", blocking)


class PrimaryConstructors(unittest.TestCase):
    def test_di_primary_constructor_blocks(self):
        text = "namespace P;\n\ninternal sealed class Foo(IBar bar, ILogger<Foo> logger)\n{\n}\n"
        blocking, _ = ids(SRC, text)
        self.assertIn("no-primary-ctor", blocking)

    def test_value_parameters_are_allowed(self):
        text = "namespace P;\n\ninternal sealed class Foo(int count, string name)\n{\n}\n"
        blocking, _ = ids(SRC, text)
        self.assertNotIn("no-primary-ctor", blocking)

    def test_positional_records_are_allowed(self):
        text = "namespace P;\n\ninternal sealed record Foo(IBar Bar, ILogger<Foo> Logger);\n"
        blocking, _ = ids(SRC, text)
        self.assertNotIn("no-primary-ctor", blocking)


class ConstructorStyleCounts(unittest.TestCase):
    def test_counts_primary_and_explicit_di_classes(self):
        primary = "internal sealed class A(IBar bar,\n    ILogger<A> logger)\n{\n}\n"
        self.assertEqual(check_rules.ctor_counts(primary), (1, 0))
        self.assertEqual(check_rules.ctor_counts(CLEAN), (0, 1))

    def test_value_only_constructors_are_not_counted(self):
        text = "internal sealed class A(int count)\n{\n}\n"
        self.assertEqual(check_rules.ctor_counts(text), (0, 0))


class LineRules(unittest.TestCase):
    def test_ioptions_blocks_outside_tests(self):
        blocking, _ = ids(SRC, wrap("IOptions<Settings> options = null!;"))
        self.assertIn("no-ioptions", blocking)

    def test_ioptions_snapshot_and_monitor_are_allowed(self):
        for line in ("IOptionsSnapshot<Settings> a = null!;", "IOptionsMonitor<Settings> b = null!;",
                     "IConfigureOptions<Settings> c = null!;"):
            with self.subTest(line=line):
                blocking, _ = ids(SRC, wrap(line))
                self.assertNotIn("no-ioptions", blocking)

    def test_ioptions_is_ignored_in_test_files(self):
        blocking, _ = ids(TEST, wrap("IOptions<Settings> options = null!;"))
        self.assertNotIn("no-ioptions", blocking)

    def test_sync_over_async_blocks(self):
        for line in ("task.Wait();", "var x = task.GetAwaiter().GetResult();"):
            with self.subTest(line=line):
                blocking, _ = ids(SRC, wrap(line))
                self.assertIn("no-sync-over-async", blocking)

    def test_async_void_blocks(self):
        text = CLEAN.replace("public async Task<int> RunAsync", "public async void RunAsync")
        blocking, _ = ids(SRC, text)
        self.assertIn("no-async-void", blocking)

    def test_datetime_now_blocks_but_utcnow_passes(self):
        blocking, _ = ids(SRC, wrap("var now = DateTime.Now;"))
        self.assertIn("no-datetime-now", blocking)
        blocking, _ = ids(SRC, wrap("var now = DateTimeOffset.Now;"))
        self.assertIn("no-datetime-now", blocking)
        blocking, _ = ids(SRC, wrap("var now = DateTime.UtcNow;"))
        self.assertNotIn("no-datetime-now", blocking)

    def test_moq_blocks_only_in_test_files(self):
        blocking, _ = ids(TEST, wrap("var bar = new Mock<IBar>();"))
        self.assertIn("no-moq", blocking)
        blocking, _ = ids(SRC, wrap("var bar = new Mock<IBar>();"))
        self.assertNotIn("no-moq", blocking)

    def test_advisory_rules(self):
        cases = {
            "no-null-guard": "_bar = bar ?? throw new ArgumentNullException(nameof(bar));",
            "no-arg-do": "_bar.Save(Arg.Do<Order>(o => captured = o));",
            "no-task-fromresult-stub": "_bar.GetAsync(default).Returns(Task.FromResult(1));",
            "prefer-init": "public int Count { get; set; }",
        }
        for rule, line in cases.items():
            with self.subTest(rule=rule):
                blocking, advisory = ids(SRC, wrap(line))
                self.assertIn(rule, advisory)
                self.assertNotIn(rule, blocking)

    def test_prefer_init_skips_record_lines(self):
        _, advisory = ids(SRC, wrap("record Point { public int X { get; set; } }"))
        self.assertNotIn("prefer-init", advisory)

    def test_bare_xunit_assert_is_advisory_in_tests(self):
        _, advisory = ids(TEST, wrap("Assert.Equal(1, 1);"))
        self.assertIn("fluentassertions", advisory)
        _, advisory = ids(SRC, wrap("Assert.Equal(1, 1);"))
        self.assertNotIn("fluentassertions", advisory)


class Comments(unittest.TestCase):
    def test_inline_comment_in_body_blocks(self):
        blocking, _ = ids(SRC, wrap("// fetch the value"))
        self.assertIn("no-inline-comments", blocking)

    def test_block_comment_in_body_blocks(self):
        blocking, _ = ids(SRC, wrap("/* legacy path */"))
        self.assertIn("no-inline-comments", blocking)

    def test_aaa_markers_are_allowed(self):
        for marker in ("// Arrange", "// Act", "// Assert", "// Act & Assert"):
            with self.subTest(marker=marker):
                blocking, _ = ids(TEST, wrap(marker))
                self.assertNotIn("no-inline-comments", blocking)

    def test_comment_between_members_is_allowed(self):
        text = CLEAN.replace("    private readonly IBar _bar;", "    // wiring\n    private readonly IBar _bar;")
        blocking, _ = ids(SRC, text)
        self.assertNotIn("no-inline-comments", blocking)

    def test_url_inside_string_literal_is_not_a_comment(self):
        blocking, _ = ids(SRC, wrap('var url = "https://example.com/x";'))
        self.assertNotIn("no-inline-comments", blocking)

    def test_artefact_references_block(self):
        for line in ("// Task 5 adds the lookup", "/// Added per the plan.", "// see 02-implementation-plan.md"):
            with self.subTest(line=line):
                text = CLEAN.replace("/// <summary>Runs the thing.</summary>", line)
                blocking, _ = ids(SRC, text)
                self.assertIn("no-artefact-comments", blocking)

    def test_long_xml_doc_is_advisory(self):
        doc = "\n".join("/// prose line %d" % i for i in range(6))
        text = CLEAN.replace("/// <summary>Runs the thing.</summary>", doc)
        _, advisory = ids(SRC, text)
        self.assertIn("xmldoc-brevity", advisory)

    def test_short_xml_doc_with_tags_only_is_fine(self):
        text = CLEAN.replace("/// <summary>Runs the thing.</summary>",
                             "/// <summary>\n/// Runs the thing.\n/// </summary>\n/// <param name=\"x\">x</param>")
        _, advisory = ids(SRC, text)
        self.assertNotIn("xmldoc-brevity", advisory)


class CsprojRules(unittest.TestCase):
    def test_fluentassertions_must_be_v7(self):
        blocking, _ = ids("/repo/A.csproj", '<PackageReference Include="FluentAssertions" Version="8.1.0" />')
        self.assertIn("fluentassertions-v7", blocking)
        blocking, _ = ids("/repo/A.csproj", '<PackageReference Include="FluentAssertions" Version="7.2.0" />')
        self.assertEqual(blocking, set())

    def test_moq_package_blocks(self):
        blocking, _ = ids("/repo/A.csproj", '<PackageReference Include="Moq" Version="4.20.0" />')
        self.assertIn("no-moq", blocking)


class ApplyConfig(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = os.path.realpath(self._tmp.name)
        patch = mock.patch.dict(os.environ, {}, clear=False)
        patch.start()
        self.addCleanup(patch.stop)
        os.environ.pop("CLAUDE_PROJECT_DIR", None)
        os.makedirs(os.path.join(self.root, ".claude"))
        os.makedirs(os.path.join(self.root, "src"))
        self.path = os.path.join(self.root, "src", "Foo.cs")

    def configure(self, checks):
        with open(os.path.join(self.root, ".claude", "agentic-sdd-flow.json"), "w") as handle:
            json.dump({"checks": checks}, handle)

    def test_retiering(self):
        self.configure({"no-ioptions": "advisory", "prefer-init": "block", "no-datetime-now": "off"})
        blocking = [("no-ioptions", 1, "a"), ("no-datetime-now", 2, "b"), ("no-moq", 3, "c")]
        advisory = [("prefer-init", 4, "d"), ("no-arg-do", 5, "e")]
        kept_blocking, kept_advisory = check_rules.apply_config(self.path, blocking, advisory)
        self.assertEqual([r for r, _, _ in kept_blocking], ["no-moq", "prefer-init"])
        self.assertEqual([r for r, _, _ in kept_advisory], ["no-ioptions", "no-arg-do"])

    def test_no_config_keeps_tiers(self):
        blocking = [("no-moq", 3, "c")]
        advisory = [("no-arg-do", 5, "e")]
        self.assertEqual(check_rules.apply_config(self.path, blocking, advisory), (blocking, advisory))


class HookEndToEnd(unittest.TestCase):
    """Runs the script exactly as the PostToolUse hook does: JSON on stdin, exit code + streams out."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = os.path.realpath(self._tmp.name)
        os.makedirs(os.path.join(self.root, "src"))

    def write(self, rel, text, encoding="utf-8"):
        path = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding=encoding) as handle:
            handle.write(text)
        return path

    def run_hook(self, payload, raw=None):
        proc = subprocess.run([sys.executable, os.path.join(_paths.SCRIPTS, "check-rules.py")],
                              input=raw if raw is not None else json.dumps(payload),
                              capture_output=True, text=True, env=_paths.hook_env(), timeout=60)
        return proc.returncode, proc.stdout, proc.stderr

    def test_blocking_violation_exits_2_with_rule_id(self):
        path = self.write("src/Probe.cs", "namespace P;\n\ninternal class Probe(IFoo foo)\n{\n}\n")
        code, out, err = self.run_hook({"tool_input": {"file_path": path}})
        self.assertEqual(code, 2)
        self.assertIn("[no-primary-ctor]", err)
        self.assertIn("Probe.cs:3", err)
        self.assertEqual(out, "")

    def test_clean_file_is_silent(self):
        path = self.write("src/Foo.cs", CLEAN)
        self.assertEqual(self.run_hook({"tool_input": {"file_path": path}}), (0, "", ""))

    def test_advisory_only_returns_additional_context(self):
        path = self.write("src/Foo.cs", wrap("public int Count { get; set; }"))
        code, out, err = self.run_hook({"tool_input": {"file_path": path}})
        self.assertEqual((code, err), (0, ""))
        payload = json.loads(out)
        self.assertEqual(payload["hookSpecificOutput"]["hookEventName"], "PostToolUse")
        self.assertIn("prefer-init", payload["hookSpecificOutput"]["additionalContext"])

    def test_tool_response_file_path_is_honoured(self):
        path = self.write("src/Probe.cs", "namespace P;\n\ninternal class Probe(IFoo foo)\n{\n}\n")
        code, _, err = self.run_hook({"tool_response": {"filePath": path}, "tool_input": {}})
        self.assertEqual(code, 2)
        self.assertIn("no-primary-ctor", err)

    def test_generated_and_build_paths_are_skipped(self):
        bad = "namespace P;\n\ninternal class Probe(IFoo foo)\n{\n}\n"
        for rel in ("src/obj/Probe.cs", "src/bin/Probe.cs", "src/Migrations/Probe.cs", "src/Probe.g.cs", "src/Probe.Designer.cs"):
            with self.subTest(path=rel):
                path = self.write(rel, bad)
                self.assertEqual(self.run_hook({"tool_input": {"file_path": path}})[0], 0)

    def test_non_csharp_and_missing_files_are_ignored(self):
        path = self.write("src/notes.md", "// Task 5")
        self.assertEqual(self.run_hook({"tool_input": {"file_path": path}})[0], 0)
        self.assertEqual(self.run_hook({"tool_input": {"file_path": os.path.join(self.root, "src", "Gone.cs")}})[0], 0)

    def test_invalid_payload_is_ignored(self):
        self.assertEqual(self.run_hook(None, raw="not json")[0], 0)
        self.assertEqual(self.run_hook({"tool_input": {}})[0], 0)

    def test_bom_files_are_read(self):
        path = self.write("src/Probe.cs", "namespace P;\n\ninternal class Probe(IFoo foo)\n{\n}\n", encoding="utf-8-sig")
        self.assertEqual(self.run_hook({"tool_input": {"file_path": path}})[0], 2)

    def test_only_newly_introduced_violations_block(self):
        git = ["git", "-C", self.root, "-c", "user.name=t", "-c", "user.email=t@example.com"]
        subprocess.run(["git", "init", "-q", self.root], check=True)
        path = self.write("src/Foo.cs", wrap("var now = DateTime.Now;"))
        subprocess.run(git + ["add", "."], check=True)
        subprocess.run(git + ["commit", "-q", "-m", "legacy"], check=True)

        code, _, err = self.run_hook({"tool_input": {"file_path": path}})
        self.assertEqual((code, err), (0, ""), "a committed violation must not block a no-op rewrite")

        self.write("src/Foo.cs", wrap("var now = DateTime.Now;\n        task.Wait();"))
        code, _, err = self.run_hook({"tool_input": {"file_path": path}})
        self.assertEqual(code, 2)
        self.assertIn("no-sync-over-async", err)
        self.assertNotIn("no-datetime-now", err)

    def test_checks_config_can_silence_a_rule(self):
        self.write(".claude/agentic-sdd-flow.json", json.dumps({"checks": {"no-primary-ctor": "off"}}))
        path = self.write("src/Probe.cs", "namespace P;\n\ninternal class Probe(IFoo foo)\n{\n}\n")
        self.assertEqual(self.run_hook({"tool_input": {"file_path": path}}), (0, "", ""))


class ServiceConstructorStyle(unittest.TestCase):
    """The primary-constructor gate follows the style the service already uses."""

    PRIMARY = "namespace P;\n\ninternal sealed class {name}(IBar bar)\n{{\n}}\n"
    EXPLICIT = ("namespace P;\n\ninternal sealed class {name}\n{{\n    private readonly IBar _bar;\n\n"
                "    public {name}(IBar bar)\n    {{\n        _bar = bar;\n    }}\n}}\n")

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = os.path.realpath(self._tmp.name)
        self.data = os.path.join(self.root, ".data")

    def write(self, rel, text):
        path = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        return path

    def service(self, primary, explicit, git=True):
        for i in range(primary):
            self.write(f"src/P{i}.cs", self.PRIMARY.format(name=f"P{i}"))
        for i in range(explicit):
            self.write(f"src/E{i}.cs", self.EXPLICIT.format(name=f"E{i}"))
        if git:
            cmd = ["git", "-C", self.root, "-c", "user.name=t", "-c", "user.email=t@example.com"]
            subprocess.run(["git", "init", "-q", self.root], check=True)
            subprocess.run(cmd + ["add", "."], check=True)
            subprocess.run(cmd + ["commit", "-q", "--allow-empty", "-m", "service"], check=True)
        else:
            self.write("Service.sln", "")

    def run_new_primary(self):
        path = self.write("src/Probe.cs", self.PRIMARY.format(name="Probe"))
        proc = subprocess.run([sys.executable, os.path.join(_paths.SCRIPTS, "check-rules.py")],
                              input=json.dumps({"tool_input": {"file_path": path}}),
                              capture_output=True, text=True, timeout=60,
                              env=_paths.hook_env(CLAUDE_PLUGIN_DATA=self.data))
        return proc.returncode, proc.stderr

    def test_primary_majority_service_accepts_a_new_primary_constructor(self):
        self.service(primary=3, explicit=1)
        self.assertEqual(self.run_new_primary(), (0, ""))

    def test_primary_majority_is_read_from_the_cache_on_the_second_write(self):
        self.service(primary=3, explicit=1)
        self.assertEqual(self.run_new_primary()[0], 0)
        self.assertTrue(os.path.isfile(os.path.join(self.data, "ctor-style.json")))
        self.assertEqual(self.run_new_primary()[0], 0)

    def test_primary_majority_without_git_uses_the_solution_directory(self):
        self.service(primary=2, explicit=0, git=False)
        self.assertEqual(self.run_new_primary()[0], 0)

    def test_explicit_majority_service_still_blocks(self):
        self.service(primary=1, explicit=3)
        code, err = self.run_new_primary()
        self.assertEqual(code, 2)
        self.assertIn("[no-primary-ctor]", err)

    def test_tie_blocks(self):
        self.service(primary=2, explicit=2)
        self.assertEqual(self.run_new_primary()[0], 2)

    def test_no_established_pattern_blocks(self):
        self.service(primary=0, explicit=0)
        self.assertEqual(self.run_new_primary()[0], 2)

    def test_explicit_checks_tier_overrides_the_service_style(self):
        self.write(".claude/agentic-sdd-flow.json", json.dumps({"checks": {"no-primary-ctor": "block"}}))
        self.service(primary=3, explicit=0)
        self.assertEqual(self.run_new_primary()[0], 2)


if __name__ == "__main__":
    unittest.main()
