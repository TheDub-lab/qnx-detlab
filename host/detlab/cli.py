"""detlab command-line interface.

Subcommands:
    run     execute a scenario (local probe or QNX QEMU target)
    report  render HTML from a run document
    check   compare a run against a baseline; CI exit code
    demo    synthetic end-to-end demo (no QNX, no QEMU)
"""

import argparse
import json
import os
import random
import sys

from . import check as check_mod
from . import metrics
from . import report as report_mod
from . import runner
from .qemu import QemuTarget, QemuTargetError


def _load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _dump(doc, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2)
    return path


def _run_document(scenario, results, meta=None):
    return {
        "scenario": scenario["name"],
        "results": [
            {k: v for k, v in r.items() if k != "samples_ns"}
            for r in results
        ],
        "samples": {r["id"]: r["samples_ns"] for r in results},
        "meta": meta or {},
    }


def cmd_run(args):
    scenario = _load_json(args.scenario)
    if args.target == "local":
        results = runner.run_scenario(
            scenario, mode="local", binary=args.probe_binary
        )
        doc = _run_document(scenario, results, meta={"mode": "local"})
        _dump(doc, args.out)
        return 0

    target = QemuTarget(_load_json(args.target_config) if args.target_config else {})
    with target:
        target.put(args.probe_binary, "/tmp/detlab-probe")
        target.exec("chmod +x /tmp/detlab-probe")
        results = runner.run_scenario(
            scenario, mode="remote", target=target
        )
    doc = _run_document(
        scenario, results,
        meta={"mode": "qemu", "target_ip": target.ip},
    )
    _dump(doc, args.out)
    return 0


def cmd_report(args):
    doc = _load_json(args.run)
    # Re-join summaries with samples for histogram rendering.
    results = []
    for r in doc["results"]:
        results.append({**r, "samples_ns": doc["samples"][r["id"]]})
    check_outcome = None
    if args.baseline:
        baseline = check_mod.load_baseline(args.baseline)
        run_items = [
            {"id": r["id"], "summary": r["summary"]} for r in doc["results"]
        ]
        check_outcome = check_mod.evaluate(run_items, baseline)
    out = report_mod.render(
        results, args.out, scenario_name=doc.get("scenario", "run"),
        check_outcome=check_outcome,
    )
    if args.baseline_out:
        _dump(
            {
                "scenario": doc.get("scenario"),
                "results": [
                    {"id": r["id"], "summary": r["summary"]}
                    for r in doc["results"]
                ],
            },
            args.baseline_out,
        )
    print(out)
    return 0


def cmd_check(args):
    run_doc = _load_json(args.run)
    baseline = check_mod.load_baseline(args.baseline)
    run_items = [
        {"id": r["id"], "summary": r["summary"]} for r in run_doc["results"]
    ]
    ok, failures = check_mod.evaluate(run_items, baseline)
    for f in failures:
        print(
            f"REGRESSION {f['id']} {f['metric']}: "
            f"run={f['run']:.0f} baseline={f['baseline']:.0f} limit={f['limit']:.0f}",
            file=sys.stderr,
        )
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


def _synthetic_results(seed=7):
    """Deterministic fake probe data shaped like real jitter runs."""
    rng = random.Random(seed)
    results = []
    for name, mean, tail in (
        ("jitter-idle", 1_000, 8_000),
        ("jitter-loaded", 1_400, 60_000),
    ):
        samples = [
            int(rng.gauss(mean, 250)) + (rng.random() < 0.01) * tail
            for _ in range(50_000)
        ]
        results.append(
            {
                "id": f"demo:{name}",
                "probe": "jitter",
                "meta": {"period_us": 1000, "policy": "fifo",
                         "synthetic": True},
                "samples_ns": [s if s > 0 else 1 for s in samples],
            }
        )
    for r in results:
        r["summary"] = metrics.summarize(r["samples_ns"])
    return results


def cmd_demo(args):
    """Synthetic pipeline: fake data -> run doc -> report -> baseline check.

    Exercises report and check with zero QNX involvement; also serves as
    the fastest visual smoke test after host-side changes.
    """
    os.makedirs(args.out_dir, exist_ok=True)
    results = _synthetic_results()
    doc = _run_document({"name": "demo"}, results, meta={"mode": "synthetic"})
    _dump(doc, f"{args.out_dir}/demo-run.json")

    baseline = {
        "scenario": "demo",
        "results": [
            {"id": r["id"], "summary": r["summary"]} for r in results
        ],
        "thresholds": {"*": {"regression_pct": 10}},
    }
    _dump(baseline, f"{args.out_dir}/demo-baseline.json")

    out = report_mod.render(
        results, f"{args.out_dir}/demo-report.html", scenario_name="demo"
    )
    print(out)

    ok, _ = check_mod.evaluate(
        [{"id": r["id"], "summary": r["summary"]} for r in results], baseline
    )
    print(f"self-check against own baseline: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="detlab",
        description="Determinism regression harness for QNX 8.0",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="execute a scenario")
    p_run.add_argument("scenario", help="scenario JSON file")
    p_run.add_argument("--target", choices=["local", "qsti"], default="local")
    p_run.add_argument("--probe-binary", default="probe/detlab-probe")
    p_run.add_argument("--target-config", help="QEMU/QSTI config JSON")
    p_run.add_argument("--out", default="results/run.json")
    p_run.set_defaults(fn=cmd_run)

    p_rep = sub.add_parser("report", help="render HTML report from a run")
    p_rep.add_argument("run", help="run document JSON")
    p_rep.add_argument("--out", default="reports/report.html")
    p_rep.add_argument("--baseline", help="also run the CI check")
    p_rep.add_argument("--baseline-out", help="record this run as baseline")
    p_rep.set_defaults(fn=cmd_report)

    p_chk = sub.add_parser("check", help="compare run against baseline")
    p_chk.add_argument("run", help="run document JSON")
    p_chk.add_argument("--baseline", required=True)
    p_chk.set_defaults(fn=cmd_check)

    p_demo = sub.add_parser("demo", help="synthetic end-to-end demo")
    p_demo.add_argument("--out-dir", default="scratch-demo")
    p_demo.set_defaults(fn=cmd_demo)

    args = parser.parse_args(argv)
    try:
        return args.fn(args)
    except (QemuTargetError, runner.ProbeError, FileNotFoundError,
            json.JSONDecodeError) as e:
        print(f"detlab: {e}", file=sys.stderr)
        return 2
