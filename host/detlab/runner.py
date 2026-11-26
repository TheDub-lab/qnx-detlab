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


def _normalize(scenario_name, probe_name, doc):
    if "error" in doc:
        raise ProbeError(f"probe {probe_name} failed: {doc['error']}")
    samples = doc.get("samples_ns", [])
    if not samples:
        raise ProbeError(f"probe {probe_name} returned no samples")
    return {
        "id": f"{scenario_name}:{probe_name}",
        "probe": probe_name,
        "meta": doc.get("meta", {}),
        "samples_ns": samples,
        "summary": metrics.summarize(samples),
    }


def run_local(scenario_name, probe_name, args, binary, timeout=120):
    """Run the probe binary directly (argv = [binary, probe, k=v, ...])."""
    argv = [str(binary), probe_name] + [
        f"{k}={v}" for k, v in (args or {}).items()
    ]
    proc = subprocess.run(argv, capture_output=True, timeout=timeout)
    if proc.returncode != 0:
        raise ProbeError(
            f"probe exited {proc.returncode}: {proc.stdout.decode()[:200]}"
        )
    return _normalize(scenario_name, probe_name, json.loads(proc.stdout))


def run_remote(scenario_name, probe_name, args, target, timeout=900,
               remote_binary="/tmp/detlab-probe"):
    """Run the probe on a target over SSH; target exposes exec(cmd, timeout)."""
    kv = " ".join(f"{k}={v}" for k, v in (args or {}).items())
    stdout = target.exec(f"{remote_binary} {probe_name} {kv}", timeout=timeout)
    return _normalize(scenario_name, probe_name, json.loads(stdout))


def run_scenario(scenario, mode, binary=None, target=None):
    """Run all probes in a scenario document; returns list of results."""
    results = []
    for entry in scenario["probes"]:
        if mode == "local":
            results.append(
                run_local(scenario["name"], entry["probe"],
                          entry.get("args", {}), binary)
            )
        else:
            results.append(
                run_remote(scenario["name"], entry["probe"],
                           entry.get("args", {}), target)
            )
    return results
