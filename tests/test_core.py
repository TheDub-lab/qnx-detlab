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

    def test_spacing_series_reconstructs_period(self):
        # offsets: constant 10us slip at index 2 (one-time schedule step)
        samples = [5, 6, 10010, 10014, 10019]
        spacing = metrics.spacing_series(samples, period_ns=1000)
        # spacing around the step is ~1ms + 10000; elsewhere ~1ms + jitter
        self.assertAlmostEqual(spacing[0], 1001.0)
        self.assertAlmostEqual(spacing[1], 11004.0)
        self.assertAlmostEqual(spacing[3], 1005.0)

    def test_spacing_series_needs_two_samples(self):
        with self.assertRaises(ValueError):
            metrics.spacing_series([5], period_ns=1000)

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

    def test_negative_baseline_direction(self):
        # min_ns is negative (early wakeups): a run identical to baseline
        # must PASS; only meaningfully-more-negative runs fail.
        baseline = {
            "results": [
                {"id": "s:j", "summary": {"min_ns": -42000, "p99_ns": 300000}}
            ],
            "thresholds": {"*": {"regression_pct": 30}},
        }
        same = [{"id": "s:j", "summary": {"min_ns": -42000, "p99_ns": 300000}}]
        ok, failures = check_mod.evaluate(same, baseline)
        self.assertTrue(ok)

        worse_early = [
            {"id": "s:j", "summary": {"min_ns": -100000, "p99_ns": 300000}}
        ]
        ok, failures = check_mod.evaluate(worse_early, baseline)
        self.assertFalse(ok)
        self.assertEqual(failures[0]["metric"], "min_ns")

    def test_floor_catches_rate_violation(self):
        # A period config error: spacing p50 collapses to the wrong period.
        baseline = {
            "results": [
                {"id": "s:loop", "summary": {"sp_p50_ns": 10000000}}
            ],
            "thresholds": {"sp_p50_ns": {"floor_pct": 20}},
        }
        healthy = [{"id": "s:loop", "summary": {"sp_p50_ns": 10002000}}]
        ok, _ = check_mod.evaluate(healthy, baseline)
        self.assertTrue(ok)

        too_fast = [{"id": "s:loop", "summary": {"sp_p50_ns": 1000000}}]
        ok, failures = check_mod.evaluate(too_fast, baseline)
        self.assertFalse(ok)
        self.assertEqual(failures[0]["direction"], "floor")

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
