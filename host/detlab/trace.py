"""Kernel event trace capture and correlation.  [STUB]

Planned design (see docs/architecture.md):

  capture(target, duration_s) -> local .kev path
      ssh: tracelogger -S <duration>s -T <n>s -s <size>
      (QNX ships only instrumented kernels, so every target can trace)
      then scp the resulting /dev/shmem/tracebuffer.kev back to the host.

  correlate(kev_path, latency_samples)
      Parse events around each latency outlier (>p99.9) to answer
      "what was the kernel doing when this wakeup was late?".
      Two implementation options, in order of preference:
        1. traceprinter text output on the host, line-parsed (documented,
           stable, ugly-but-robust)
        2. libtraceparser C helper for structured events (richer, but the
           8.0 API surface must be verified first)

  Report integration: annotate the HTML report's outlier table with the
  dominant kernel events per spike.

Status: not implemented. Deliberately kept out of runner.py so the core
pipeline works without it.
"""

from .qemu import QemuTargetError


def capture(target, duration_s=10):
    """Capture a kernel event trace on the target; return local .kev path."""
    raise NotImplementedError("trace capture pending first on-target session")


def correlate(kev_path, samples_ns):
    """Return kernel events correlated with latency outliers."""
    raise NotImplementedError("trace correlation pending traceprinter access")
