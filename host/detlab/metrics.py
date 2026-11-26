"""Pure metric math over latency samples. No I/O, no globals.

A "summary" dict is the interchange format used by report/check/baselines:

    {"count": int, "min_ns": int, "mean_ns": float,
     "p50_ns": int, "p99_ns": int, "p999_ns": int, "max_ns": int}
"""

import math

PERCENTILE_POINTS = (50, 99, 99.9)


def percentile(sorted_samples, q):
    """Nearest-rank percentile of pre-sorted samples. q is 0-100."""
    if not sorted_samples:
        raise ValueError("percentile of empty sample set")
    if len(sorted_samples) == 1:
        return sorted_samples[0]
    rank = max(1, math.ceil(q / 100 * len(sorted_samples)))
    return sorted_samples[rank - 1]


def summarize(samples_ns):
    """Summarize raw latency samples (ns) into the interchange summary."""
    if not samples_ns:
        raise ValueError("cannot summarize empty sample set")
    ordered = sorted(samples_ns)
    return {
        "count": len(ordered),
        "min_ns": ordered[0],
        "mean_ns": sum(ordered) / len(ordered),
        "p50_ns": percentile(ordered, 50),
        "p99_ns": percentile(ordered, 99),
        "p999_ns": percentile(ordered, 99.9),
        "max_ns": ordered[-1],
    }


def spacing_series(samples_ns, period_ns):
    """Inter-arrival spacing deviations, host-side from raw offset samples.

    spacing_i = period + (offset_i - offset_{i-1}) — reconstructs the
    time between consecutive wakeups. Unlike the raw offsets (which
    measure cumulative schedule fidelity and absorb any one-time slip
    forever), spacing measures per-wakeup consistency: what an RT
    application actually experiences at each wakeup.
    """
    if len(samples_ns) < 2:
        raise ValueError("spacing needs at least two samples")
    return [
        period_ns + (samples_ns[i] - samples_ns[i - 1])
        for i in range(1, len(samples_ns))
    ]


def histogram(samples_ns, bins=40):
    """Return (bin_floor_ns, bin_width_ns, counts) for rendering."""
    if not samples_ns:
        raise ValueError("cannot histogram empty sample set")
    lo = min(samples_ns)
    hi = max(samples_ns)
    width = max(1, math.ceil((hi - lo) / bins)) if hi > lo else 1
    counts = [0] * bins
    for s in samples_ns:
        idx = min(bins - 1, int((s - lo) // width))
        counts[idx] += 1
    return lo, width, counts


def fmt_ns(ns):
    """Human-readable latency: 1_234 ns -> '1.23 us'."""
    if abs(ns) >= 1_000_000:
        return f"{ns / 1_000_000:.2f} ms"
    if abs(ns) >= 1_000:
        return f"{ns / 1_000:.2f} us"
    return f"{ns} ns"
