"""Execute probe invocations and normalize their JSON output.

Two execution paths, deliberately identical above this layer:
  - local:  subprocess on a QNX host (Developer Desktop) or for tests
  - target: ssh through a Target handle (see qemu.py)

Every probe result is normalized to:
    {"id": "<scenario>:<probe>", "probe": ..., "meta": {...},
     "samples_ns": [...], "summary": {...}}
with "summary" computed here so the probe stays dumb.
"""

import json
import subprocess

from . import metrics


class ProbeError(Exception):
    """Probe ran but failed, or produced output we could not parse."""


def _normalize(result_id, probe_name, doc, args=None):
    if "error" in doc:
        raise ProbeError(f"probe {probe_name} failed: {doc['error']}")
    samples = doc.get("samples_ns", [])
    if not samples:
        raise ProbeError(f"probe {probe_name} returned no samples")

    summary = metrics.summarize(samples)
    # Inter-arrival spacing summary (needs the nominal period).
    period_ns = None
    sources = []
    if args:
        sources.append(args.get("period_us"))
    meta = doc.get("meta", {})
    sources.append(meta.get("period_us"))
    for value in sources:
        if value is not None:
            period_ns = float(value) * 1000.0
            break
    if period_ns is not None and len(samples) >= 2:
        summary["spacing"] = metrics.summarize(
            metrics.spacing_series(samples, period_ns)
        )

    return {
        "id": result_id,
        "probe": probe_name,
        "meta": meta,
        "samples_ns": samples,
        "summary": summary,
    }


def run_local(result_id, probe_name, args, binary, timeout=120):
    """Run the probe binary directly (argv = [binary, probe, k=v, ...])."""
    argv = [str(binary), probe_name] + [
        f"{k}={v}" for k, v in (args or {}).items()
    ]
    proc = subprocess.run(argv, capture_output=True, timeout=timeout)
    if proc.returncode != 0:
        raise ProbeError(
            f"probe exited {proc.returncode}: {proc.stdout.decode()[:200]}"
        )
    return _normalize(result_id, probe_name, json.loads(proc.stdout), args)


def run_remote(result_id, probe_name, args, target, timeout=900,
               remote_binary="/tmp/detlab-probe"):
    """Run the probe on a target over SSH; target exposes exec(cmd, timeout)."""
    kv = " ".join(f"{k}={v}" for k, v in (args or {}).items())
    stdout = target.exec(f"{remote_binary} {probe_name} {kv}", timeout=timeout)
    return _normalize(result_id, probe_name, json.loads(stdout), args)


def run_scenario(scenario, mode, binary=None, target=None):
    """Run all probes in a scenario document; returns list of results.

    Scenario entries may carry an explicit "id"; otherwise the id is
    "<scenario>:<probe>". Duplicate ids within a scenario get a
    stable ":2", ":3" suffix so raw samples never overwrite each other.
    """
    results = []
    seen = {}
    for entry in scenario["probes"]:
        probe_name = entry["probe"]
        base_id = entry.get("id", f"{scenario['name']}:{probe_name}")
        seen[base_id] = seen.get(base_id, 0) + 1
        result_id = base_id if seen[base_id] == 1 else f"{base_id}:{seen[base_id]}"
        if mode == "local":
            results.append(
                run_local(result_id, probe_name, entry.get("args", {}), binary)
            )
        else:
            results.append(
                run_remote(result_id, probe_name, entry.get("args", {}), target)
            )
    return results
