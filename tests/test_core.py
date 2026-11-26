"""Unit tests for metrics.py and check.py (pure logic, no QNX needed)."""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "host"))

from detlab import check as check_mod   # noqa: E402
from detlab import metrics              # noqa: E402


class TestMetrics(unittest.TestCase):
    def test_percentile_nearest_rank(self):
        samples = list(range(1, 101))  # 1..100
        self.assertEqual(metrics.percentile(samples, 50), 50)
        self.assertEqual(metrics.percentile(samples, 99), 99)
        self.assertEqual(metrics.percentile(samples, 99.9), 100)

    def test_percentile_single_sample(self):
        self.assertEqual(metrics.percentile([42], 99), 42)

    def test_percentile_empty_raises(self):
        with self.assertRaises(ValueError):
            metrics.percentile([], 50)

    def test_summarize_fields(self):
        s = metrics.summarize([100, 200, 300, 400, 1000])
        self.assertEqual(s["count"], 5)
        self.assertEqual(s["min_ns"], 100)
        self.assertEqual(s["max_ns"], 1000)
        self.assertEqual(s["mean_ns"], 400.0)

    def test_summarize_empty_raises(self):
        with self.assertRaises(ValueError):
            metrics.summarize([])

    def test_histogram_covers_range(self):
        lo, width, counts = metrics.histogram([0, 39], bins=40)
        self.assertEqual(lo, 0)
        self.assertEqual(width, 1)
        self.assertEqual(sum(counts), 2)

    def test_fmt_ns_units(self):
        self.assertEqual(metrics.fmt_ns(500), "500 ns")
        self.assertEqual(metrics.fmt_ns(1500), "1.50 us")
        self.assertEqual(metrics.fmt_ns(1_500_000), "1.50 ms")


class TestCheck(unittest.TestCase):
    def base_summary(self, p99=1000):
        return {"p99_ns": p99, "max_ns": p99 * 2}

    def test_pass_on_improvement(self):
        baseline = {
            "results": [{"id": "s:jitter", "summary": self.base_summary(1000)}],
            "thresholds": {"*": {"regression_pct": 10}},
        }
        run = [{"id": "s:jitter", "summary": self.base_summary(900)}]
        ok, failures = check_mod.evaluate(run, baseline)
        self.assertTrue(ok)
        self.assertEqual(failures, [])

    def test_fail_on_regression(self):
        baseline = {
            "results": [{"id": "s:jitter", "summary": self.base_summary(1000)}],
            "thresholds": {"*": {"regression_pct": 10}},
        }
        run = [{"id": "s:jitter", "summary": self.base_summary(1200)}]
        ok, failures = check_mod.evaluate(run, baseline)
        self.assertFalse(ok)
        self.assertEqual(len(failures), 2)  # p99_ns and max_ns both regress

    def test_metric_specific_rule_beats_wildcard(self):
        baseline = {
            "results": [
                {"id": "s:j", "summary": {"p99_ns": 1000, "max_ns": 5000}}
            ],
            "thresholds": {
                "*": {"regression_pct": 10},
                "max_ns": {"max_ns": 1_000_000},  # effectively unbounded
            },
        }
        run = [{"id": "s:j", "summary": {"p99_ns": 1000, "max_ns": 900_000}}]
        ok, failures = check_mod.evaluate(run, baseline)
        # p99 unchanged; max allowed by its own rule
        self.assertTrue(ok)

    def test_new_scenarios_ignored(self):
        baseline = {"results": [], "thresholds": {}}
        run = [{"id": "new:probe", "summary": self.base_summary(10**9)}]
        ok, failures = check_mod.evaluate(run, baseline)
        self.assertTrue(ok)

    def test_baseline_roundtrip(self):
        doc = {"results": [{"id": "a", "summary": self.base_summary()}]}
        with tempfile.NamedTemporaryFile("w", suffix=".json",
                                          delete=False) as f:
            json.dump(doc, f)
            path = f.name
        try:
            loaded = check_mod.load_baseline(path)
            self.assertEqual(loaded["results"][0]["id"], "a")
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
