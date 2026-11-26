"""HTML report generation from run results. Stdlib only.

The report is a single self-contained HTML file: inline SVG histograms,
metric tables, no external CSS/JS so it renders in any browser and
attaches cleanly to CI artifacts.
"""

import html
import json
import os

from . import metrics

_METRIC_ROWS = (
    ("count", "samples"),
    ("min_ns", "min"),
    ("mean_ns", "mean"),
    ("p50_ns", "p50"),
    ("p99_ns", "p99"),
    ("p999_ns", "p99.9"),
    ("max_ns", "max"),
)

_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>detlab report — __SCENARIO__</title>
<style>
body { font-family: ui-monospace, monospace; margin: 2rem; color: #111; }
h1 { font-size: 1.2rem; } h2 { font-size: 1rem; margin-top: 2rem; }
table { border-collapse: collapse; margin-top: .5rem; }
td, th { border: 1px solid #999; padding: .25rem .6rem; text-align: right; }
th { background: #eee; } td:first-child, th:first-child { text-align: left; }
.fail { color: #b00; font-weight: bold; }
.pass { color: #070; }
pre.meta { background: #f4f4f4; padding: .5rem; }
</style></head><body>
<h1>detlab report — __SCENARIO__</h1>
__BODY__
</body></html>"""


def _svg_histogram(result, width=720, height=160):
    lo, width_ns, counts = metrics.histogram(result["samples_ns"], bins=40)
    peak = max(counts)
    bar_w = width / len(counts)
    bars = []
    for i, c in enumerate(counts):
        h = (c / peak) * (height - 20) if peak else 0
        bars.append(
            f'<rect x="{i * bar_w:.1f}" y="{height - h:.1f}" '
            f'width="{bar_w - 1:.1f}" height="{h:.1f}" fill="#345"/>'
        )
    label = f"first bin floor {metrics.fmt_ns(lo)}, bin width {metrics.fmt_ns(width_ns)}"
    return (
        f'<svg viewBox="0 0 {width} {height}" width="{width}" '
        f'height="{height}">{"".join(bars)}</svg>'
        f"<div>{html.escape(label)}</div>"
    )


def _results_table(results):
    header = "".join(f"<th>{h}</th>" for _, h in _METRIC_ROWS)
    rows = []
    for r in results:
        cells = "".join(
            f"<td>{_fmt(r['summary'].get(k))}</td>" for k, _ in _METRIC_ROWS
        )
        rows.append(
            f'<tr><td>{html.escape(r["id"])}</td>{cells}</tr>'
        )
    return (
        f"<table><tr><th>scenario:probe</th>{header}</tr>{''.join(rows)}</table>"
    )


def _fmt(value):
    if isinstance(value, float):
        return f"{value:,.0f}"
    if isinstance(value, int):
        return f"{value:,}"
    if value is None:
        return "—"
    return html.escape(str(value))


def _check_section(ok, failures):
    if ok and not failures:
        return '<h2>baseline check</h2><p class="pass">PASS — no regressions</p>'
    rows = "".join(
        f'<tr><td>{html.escape(f["id"])}</td><td>{html.escape(f["metric"])}</td>'
        f"<td>{_fmt(f['baseline'])}</td><td class='fail'>{_fmt(f['run'])}</td>"
        f"<td>{_fmt(f['limit'])}</td></tr>"
        for f in failures
    )
    return (
        '<h2>baseline check</h2><p class="fail">FAIL</p>'
        "<table><tr><th>id</th><th>metric</th><th>baseline</th>"
        f"<th>run</th><th>limit</th></tr>{rows}</table>"
    )


def render(results, out_path, scenario_name="run", check_outcome=None):
    """Write a self-contained HTML report.

    check_outcome: optional (ok, failures) tuple from check.evaluate();
    when present the report shows the CI-gate verdict.
    """
    body = [_results_table(results)]
    for r in results:
        body.append(f'<h2>{html.escape(r["id"])}</h2>')
        body.append(_svg_histogram(r))
        body.append(
            f'<pre class="meta">{html.escape(json.dumps(r["meta"], indent=2))}</pre>'
        )
    if check_outcome is not None:
        body.append(_check_section(*check_outcome))

    page = (
        _PAGE.replace("__SCENARIO__", html.escape(scenario_name))
        .replace("__BODY__", "\n".join(body))
    )
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(page)
    return out_path
