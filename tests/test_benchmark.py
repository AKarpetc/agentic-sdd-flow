"""The end-to-end benchmark stays runnable: tasks, arms, fixture and the checker agree with each other."""

import glob
import importlib.util
import json
import os
import unittest

import _paths

BENCH = os.path.join(_paths.PLUGIN_ROOT, "evals", "benchmark")
MANIFEST = json.load(open(os.path.join(BENCH, "tasks", "tasks.json"), encoding="utf-8"))


def load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(BENCH, name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Benchmark(unittest.TestCase):
    def test_tasks_have_criteria_and_keys(self):
        for task, meta in MANIFEST.items():
            with self.subTest(task=task):
                text = open(os.path.join(BENCH, "tasks", task + ".md"), encoding="utf-8").read()
                self.assertIn(meta["key"], text)
                self.assertIn("Acceptance criteria", text)
                self.assertIn("dotnet test", text)

    def test_manifest_covers_every_class_and_agrees_with_the_files(self):
        classes = {meta["class"] for meta in MANIFEST.values()}
        self.assertEqual(classes, {"simple", "medium", "complex", "vague", "conflict"}, "the suite must span the whole size range and the conflict class")
        self.assertTrue({meta["expectedTier"] for meta in MANIFEST.values()} <= {"quick", "mix", "light", "standard", "deep"})
        keys = [meta["key"] for meta in MANIFEST.values()]
        self.assertEqual(len(keys), len(set(keys)), "task keys must be unique: git hygiene is scored per key")
        files = {os.path.basename(p)[:-3] for p in glob.glob(os.path.join(BENCH, "tasks", "T*.md"))}
        self.assertEqual(files, set(MANIFEST), "every task file needs a manifest entry and vice versa")
        for task, meta in MANIFEST.items():
            if "overlay" in meta:
                self.assertTrue(os.path.isdir(os.path.join(BENCH, "tasks", meta["overlay"])), meta["overlay"])

    def test_conflict_tasks_are_mirrors_with_opposite_truths(self):
        conflict = {t: m for t, m in MANIFEST.items() if m["class"] == "conflict"}
        self.assertEqual({m["truth"] for m in conflict.values()}, {"brief", "code"}, "one variant per direction")
        mirrors = {t: m for t, m in conflict.items() if t in ("T8", "T9")}
        briefs = {open(os.path.join(BENCH, "tasks", t + ".md"), encoding="utf-8").read().replace(m["key"], "KEY") for t, m in mirrors.items()}
        self.assertEqual(len(briefs), 1, "T8 and T9 must share one brief: only the records differ")
        self.assertIn("decide from the evidence", next(iter(briefs)))
        for task, meta in mirrors.items():
            overlay = os.path.join(BENCH, "tasks", meta["overlay"])
            service = open(os.path.join(overlay, "src", "Orders.Api", "Services", "ReportService.cs"), encoding="utf-8").read()
            self.assertIn("list.Count", service, "the code counts every order in both variants")
            ci = open(os.path.join(overlay, ".gitlab-ci.yml"), encoding="utf-8").read()
            self.assertIn('"3 orders"' if meta["truth"] == "brief" else '"4 orders"', ci, "CI pins the number the records support")
        self.assertTrue(os.path.isfile(os.path.join(BENCH, "tasks", conflict["T9"]["overlay"], "docs", "decisions", "0003-report-counts-every-order.md")))

    def test_conflict_signals_read_the_untouched_overlays_correctly(self):
        run = load("run")
        acceptance = load("acceptance")
        import shutil
        import tempfile
        for task, meta in ((t, m) for t, m in MANIFEST.items() if m["class"] == "conflict"):
            with self.subTest(task=task), tempfile.TemporaryDirectory() as tmp:
                ws = os.path.join(tmp, task)
                shutil.copytree(os.path.join(BENCH, "fixture"), ws, ignore=shutil.ignore_patterns("bin", "obj"))
                shutil.copytree(os.path.join(BENCH, "tasks", meta["overlay"]), ws, dirs_exist_ok=True)
                q = acceptance.quality_conflict(ws, meta["truth"])
                self.assertEqual(q["reportingDocSaysExcluded"], meta["truth"] == "brief")
                self.assertEqual(q["reportingDocSaysAll"], meta["truth"] == "code")
                self.assertFalse(q["docRewrittenTowardBrief"] or q["docRewrittenTowardCode"])
                self.assertEqual(q["ciSmokeExpects"], "3" if meta["truth"] == "brief" else "4")
        self.assertTrue(run.conflict_signals("T9", {"finalText": "NOTES: kept the count per ADR-0003"})["noticedInFinalMessage"])
        self.assertFalse(run.conflict_signals("T8", {"finalText": "NOTES: done"})["noticedInFinalMessage"])
        self.assertIsNone(run.conflict_signals("T5", {"finalText": "conflict"}))

    def test_runner_and_checker_take_the_keys_from_the_manifest(self):
        run = load("run")
        self.assertEqual(run.KEYS, {task: meta["key"] for task, meta in MANIFEST.items()})
        self.assertIn('tasks.json', open(os.path.join(BENCH, "acceptance.py"), encoding="utf-8").read())

    def test_route_is_read_off_the_dispatches_not_off_the_session(self):
        run = load("run")
        self.assertEqual(run.route_taken([]), "quick")
        self.assertEqual(run.route_taken([{"tool": "Agent", "label": "agentic-sdd-flow:tests-writer"}]), "quick")
        self.assertEqual(run.route_taken([{"tool": "Workflow", "label": "agentic-sdd-flow:dotnet-sdd", "mode": "light", "t": 9}]), "light")
        self.assertEqual(run.route_taken([{"tool": "Workflow", "label": "agentic-sdd-flow:dotnet-sdd", "t": 9}]), "standard")
        self.assertEqual(run.route_taken([{"tool": "Workflow", "label": "agentic-sdd-flow:dotnet-sdd", "mode": "review", "t": 9}]), "mix")
        self.assertEqual(run.route_taken([{"tool": "Skill", "label": "superpowers:test-driven-development", "t": 2},
                                          {"tool": "Workflow", "label": "agentic-sdd-flow:dotnet-sdd", "t": 9}]), "mix",
                         "superpowers wrote the code before the workflow was called: that is the mix route")
        self.assertEqual(run.route_taken([{"tool": "Workflow", "label": "agentic-sdd-flow:architecture-design", "t": 3},
                                          {"tool": "Workflow", "label": "agentic-sdd-flow:dotnet-sdd", "t": 9}]), "deep")
        self.assertEqual(run.workflow_args({"args": '{"mode": "light", "plan": "x"}'}), {"mode": "light"})
        self.assertEqual(run.workflow_args({"args": {"scope": "compact"}}), {"scope": "compact"})
        self.assertEqual(run.workflow_args({"args": "not json"}), {})

    def test_the_paraphrase_conflict_shares_no_decisive_word_with_its_records(self):
        """T10 is the recall test: if the brief and the records used the same vocabulary, grep would settle it."""
        brief = open(os.path.join(BENCH, "tasks", "T10.md"), encoding="utf-8").read().lower()
        adr = open(os.path.join(BENCH, "tasks", "T10.overlay", "docs", "decisions", "0007-statement-parity.md"), encoding="utf-8").read().lower()
        self.assertIn("open", brief)
        self.assertIn("cancelled", brief)
        for word in ("cancelled", "open orders"):
            self.assertNotIn(word, adr, "the decisive ADR must not repeat the brief's vocabulary")
        for word in ("parity", "reversal", "payer"):
            self.assertIn(word, adr)
            self.assertNotIn(word, brief)
        self.assertEqual(MANIFEST["T10"]["truth"], "code")

    def test_the_runner_can_repeat_and_force_a_route(self):
        run = load("run")
        import inspect
        params = inspect.signature(run.run_pair).parameters
        self.assertIn("repeat", params, "one run per cell is a sample, not a distribution")
        self.assertIn("force_tier", params, "a route the gate avoids still has to be measurable")

    def test_endpoint_coverage_is_measured_on_every_task(self):
        acceptance = load("acceptance")
        signals = acceptance.quality_common(os.path.join(BENCH, "fixture"))
        self.assertEqual(signals["testFiles"], 0, "the fixture ships an empty test project")
        self.assertFalse(signals["reachesTheEndpoint"])
        self.assertEqual(signals["testCases"], 0)

    def test_preamble_defines_the_final_message_contract(self):
        text = open(os.path.join(BENCH, "tasks", "_preamble.md"), encoding="utf-8").read()
        for line in ("STATUS:", "COMMITS:", "NOTES:"):
            self.assertIn(line, text)
        self.assertIn("never push", text)

    def test_arms_differ_only_by_plugin_and_process(self):
        arms = json.load(open(os.path.join(BENCH, "tasks", "arms.json")))
        self.assertEqual(set(arms), {"baseline", "plugin"})
        self.assertEqual(arms["baseline"]["settings"], {"enabledPlugins": {"agentic-sdd-flow@agentic-sdd-flow": False}})
        self.assertIsNone(arms["plugin"]["settings"])
        self.assertIn("superpowers:", arms["baseline"]["instruction"])
        self.assertIn("/agentic-sdd-flow:dotnet-feature", arms["plugin"]["instruction"])

    def test_neither_arm_is_told_which_tier_to_run(self):
        arms = json.load(open(os.path.join(BENCH, "tasks", "arms.json")))
        self.assertNotIn("--tier", arms["baseline"]["instruction"])
        self.assertIn("sizing gate", arms["plugin"]["instruction"])
        self.assertIn("never pass --tier", arms["plugin"]["instruction"])
        self.assertIn("respect its own sizing", arms["baseline"]["instruction"],
                      "the baseline must be allowed to scale down too, or the simple task is a stacked deck")

    def test_prompts_carry_the_task_key_and_title(self):
        run = load("run")
        arms = json.load(open(os.path.join(BENCH, "tasks", "arms.json")))
        prompt = run.prompt_for("T2", arms["plugin"])
        self.assertIn("/agentic-sdd-flow:dotnet-feature ORD-43 Cancel an order", prompt)
        self.assertIn("POST /api/orders/{id}/cancel", prompt)
        self.assertNotIn("<TASK-KEY>", prompt)

    def test_fixture_carries_the_planted_bugs(self):
        repo = open(os.path.join(BENCH, "fixture", "src", "Orders.Api", "Repositories", "InMemoryOrderRepository.cs"), encoding="utf-8").read()
        self.assertIn("order.Id == customerId", repo, "T1/T3 planted bug: wrong filter column")
        service = open(os.path.join(BENCH, "fixture", "src", "Orders.Api", "Services", "OrderService.cs"), encoding="utf-8").read()
        self.assertIn("OrderStatus.Placed or OrderStatus.Shipped", service, "T2 planted bug: Shipped instead of Paid")
        paging = open(os.path.join(BENCH, "fixture", "src", "Orders.Api", "Services", "PageMath.cs"), encoding="utf-8").read()
        self.assertIn("return page * size;", paging, "T3 planted bug: 0-based skip for 1-based pages")
        self.assertIn("api.nuget.org", open(os.path.join(BENCH, "fixture", "nuget.config"), encoding="utf-8").read())

    def test_runner_lifts_the_headless_idle_ceiling(self):
        run = load("run")
        env = run.session_env()
        self.assertEqual(env.get("CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS"), "0", "claude -p aborts a background Workflow after 10 idle minutes otherwise")
        self.assertNotIn("CLAUDECODE", env)

    def test_runner_keeps_the_prompt_out_of_argv(self):
        run = load("run")
        arms = json.load(open(os.path.join(BENCH, "tasks", "arms.json")))
        for arm in arms.values():
            command = run.session_command(arm, 120)
            self.assertEqual(command[:2], ["claude", "-p"])
            self.assertFalse(any("Orders.Api" in part for part in command), "a neighbour's pkill -f by project name would SIGTERM the session")

    def test_checker_parses_the_vstest_summary_in_english_only(self):
        acceptance = load("acceptance")
        self.assertEqual(acceptance.ENV.get("DOTNET_CLI_UI_LANGUAGE"), "en", "a localized SDK prints 'Пройдено!' and the summary regex misses it")
        mixed = "Failed!  - Failed:     1, Passed:     5, Skipped:     0, Total:     6, Duration: 2 ms - A.dll (net8.0)\n" \
                "Passed!  - Failed:     0, Passed:     3, Skipped:     1, Total:     4, Duration: 2 ms - B.dll (net8.0)\n"
        summaries = [tuple(int(n) for n in m) for m in acceptance.SUMMARY.findall(mixed)]
        self.assertEqual([s[1] for s in summaries], [5, 3], "passed must be counted on failing runs too")
        self.assertEqual(sum(s[0] for s in summaries), 1)
        self.assertEqual(sum(s[3] for s in summaries), 10)
        self.assertEqual(acceptance.SUMMARY.findall("Не пройден!: не пройдено 1, пройдено 1, всего 2"), [])

    def test_t4_quality_signals_on_the_untouched_fixture(self):
        acceptance = load("acceptance")
        q = acceptance.quality_t4(os.path.join(BENCH, "fixture"))
        self.assertFalse(q["clockAbstraction"])
        self.assertEqual(q["systemClockCallsOutsideClock"], 1, "ReportService.DateTime.Now")
        self.assertEqual(q["iOptionsUsages"], 1)
        self.assertFalse(q["promotionsInAppsettings"])
        self.assertTrue(q["reportServiceStillHasPrimaryCtor"])

    def test_checker_covers_every_task(self):
        acceptance = load("acceptance")
        self.assertEqual(set(acceptance.ACCEPTANCE), set(MANIFEST))
        self.assertEqual(set(acceptance.PLANTED), set(MANIFEST))
        for task, fn in acceptance.ACCEPTANCE.items():
            checks = fn("http://127.0.0.1:1")  # nothing listens: every check fails, but the names must be stable
            with self.subTest(task=task):
                self.assertGreaterEqual(len(checks), 4)
                self.assertIn(acceptance.PLANTED[task], [c["name"] for c in checks])
                self.assertTrue(all(not c["ok"] for c in checks))


if __name__ == "__main__":
    unittest.main()
