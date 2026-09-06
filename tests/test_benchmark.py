"""The end-to-end benchmark stays runnable: tasks, arms, fixture and the checker agree with each other."""

import importlib.util
import json
import os
import unittest

import _paths

BENCH = os.path.join(_paths.PLUGIN_ROOT, "evals", "benchmark")


def load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(BENCH, name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Benchmark(unittest.TestCase):
    def test_tasks_have_criteria_and_keys(self):
        for task, key in (("T1", "ORD-42"), ("T2", "ORD-43"), ("T3", "ORD-44")):
            with self.subTest(task=task):
                text = open(os.path.join(BENCH, "tasks", task + ".md"), encoding="utf-8").read()
                self.assertIn(key, text)
                self.assertIn("Acceptance criteria", text)
                self.assertIn("dotnet test", text)

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

    def test_checker_covers_every_task(self):
        acceptance = load("acceptance")
        self.assertEqual(set(acceptance.ACCEPTANCE), {"T1", "T2", "T3"})
        self.assertEqual(set(acceptance.PLANTED), {"T1", "T2", "T3"})
        for task, fn in acceptance.ACCEPTANCE.items():
            checks = fn("http://127.0.0.1:1")  # nothing listens: every check fails, but the names must be stable
            with self.subTest(task=task):
                self.assertGreaterEqual(len(checks), 4)
                self.assertIn(acceptance.PLANTED[task], [c["name"] for c in checks])
                self.assertTrue(all(not c["ok"] for c in checks))


if __name__ == "__main__":
    unittest.main()
