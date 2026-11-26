"""Baseline regression check: pure decision logic over summary dicts.

A baseline file is a JSON mapping of "<scenario-id>" -> summary (plus
optional thresholds). A check passes when, for every scenario in the
baseline:

    run[metric] <= max(baseline[metric] * (1 + regression_pct/100),
                       threshold max_ns if given)

Threshold keys mirror summary keys: "min_ns", "mean_ns", "p50_ns",
"p99_ns", "p999_ns", "max_ns". The wildcard entry "*" applies to any
metric without its own rule.
"""

import json

METRICS = ("min_ns", "mean_ns", "p50_ns", "p99_ns", "p999_ns", "max_ns")


def _rule(thresholds, metric):
    """Most specific rule wins: metric name over the "*" wildcard."""
    if metric in thresholds:
        return thresholds[metric]
    return thresholds.get("*")


def _violations(run_summary, baseline_summary, thresholds):
    thresholds = thresholds or {}
    failures = []
    for metric in METRICS:
        rule = _rule(thresholds, metric)
        if rule is None:
            continue
        run_val = run_summary.get(metric)
        base_val = baseline_summary.get(metric)
        if run_val is None or base_val is None:
            continue
        limit = base_val * (1 + rule.get("regression_pct", 0) / 100)
        if "max_ns" in rule:
            limit = max(limit, rule["max_ns"])
        if run_val > limit:
            failures.append(
                {
                    "metric": metric,
                    "baseline": base_val,
                    "run": run_val,
                    "limit": limit,
                }
            )
    return failures


def evaluate(run_results, baseline):
    """Compare run results against a baseline document.

    run_results: list of {"id": str, "summary": {...}} dicts
    baseline:   {"results": [{"id", "summary"}...],
                 "thresholds": {metric: {...}} | {"*": {...}}}

    Returns (ok: bool, failures: [{id, metric, baseline, run, limit}]).
    Scenarios present in the run but absent from the baseline are ignored
    (a baseline records what was once good; new probes have no history).
    """
    thresholds = baseline.get("thresholds", {})
    base_by_id = {r["id"]: r["summary"] for r in baseline.get("results", [])}

    failures = []
    for result in run_results:
        base_summary = base_by_id.get(result["id"])
        if base_summary is None:
            continue
        for bad in _violations(result["summary"], base_summary, thresholds):
            failures.append({"id": result["id"], **bad})
    return (not failures, failures)


def load_baseline(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
