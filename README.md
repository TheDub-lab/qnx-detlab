# detlab — determinism regression harness for QNX 8.0

detlab boots QNX 8.0 (Quick Start Target Image) in headless QEMU, deploys
on-target timing probes over SSH, runs a scenario matrix of scheduling and
latency measurements, and produces percentile reports. `detlab check`
compares a run against a recorded baseline and exits nonzero on regression,
so determinism can be gated in CI like any other test.

```
+------------------- Linux host -------------------+
| detlab run      -> QEMU (headless) -SSH-> probe   |
| detlab report   -> HTML: histograms + percentiles|
| detlab check    -> baseline compare, CI exit code|
+--------------------------------------------------+
```

## Components

| Path | What | Language |
|---|---|---|
| `probe/` | On-target timing probes (`detlab-probe` binary) | C (QNX) |
| `host/detlab/` | CLI harness: QEMU control, deploy, run, report, check | Python 3.10+, stdlib only |
| `scenarios/` | Declarative scenario/timing-contract definitions | JSON |
| `docs/` | Architecture notes, codelab, submission text | Markdown |

**New to QNX?** Read the codelab —
[from zero to a determinism CI gate on QNX 8.0](docs/codelab.md) —
a verified step-by-step walkthrough (free license → headless install →
QNX in QEMU → first measurement → CI gate).

## Prerequisites

- QNX SDP 8.0 (free non-commercial license via
  [QNX Everywhere](https://www.qnx.com/getqnx)), installed at `~/qnx800`
- QNX SDP 8.0 Quick Start Target Image for QEMU
  (`com.qnx.qnx800.quickstart.qemu` package, unpacked via its
  `unpack_qemu_image.sh`)
- QEMU (the image scripts expect qemu-system-x86_64)
- Python 3.10+ on the host (no third-party packages)

## Build the probe

```sh
make probe          # sources ~/qnx800/qnxsdp-env.sh, cross-compiles with qcc
```

Output: `probe/detlab-probe`, an x86_64 QNX executable.

## Run

```sh
# full pipeline against the QEMU target
detlab run scenarios/default.json --target qsti --out results/default.json
detlab report results/default.json --out reports/default.html

# record a baseline, then gate on it later
detlab report results/default.json --baseline-out baselines/default.json
detlab check results/new.json --baseline baselines/default.json && echo DETERMINISM-OK
```

See `scenarios/rt-contract-example.json` for encoding a timing contract
(deadline + acceptable jitter under load) as a checkable scenario.

## Scenario JSON

```json
{
  "name": "rt-contract-example",
  "probes": [
    {"probe": "jitter",
     "args": {"period_us": 1000, "iterations": 100000,
              "policy": "fifo", "priority": 50}}
  ]
}
```

Each probe invocation gets its `args` expanded to `key=value` command-line
arguments on the target; the probe prints one JSON document on stdout.

## QNX-specific technologies used

- `ClockCycles()`, `SYSPAGE_ENTRY(qtime)->cycles_per_sec` — cycle-counter-based timing
- `timer_create` + `SIGEV_PULSE` / `MsgReceivePulse()` — timer wakeup path
- `SCHED_FIFO` / `SCHED_RR` / `SCHED_SPORADIC` via `sched_setscheduler()` —
  scheduling policy matrix
- `ClockPeriod()` — kernel tick reporting
- Planned: `tracelogger` / kernel event trace correlation (see
  `docs/architecture.md`)

## Target

- QNX SDP 8.0 (qcc `gcc_ntox86_64` toolchain)
- Target: QEMU (QNX SDP 8.0 QSTI), x86_64 guest; the probe also builds for
  any QNX 8.0-supported target by changing the `-V` arch flag

## Status

See `docs/architecture.md#verification-status` for what is implemented,
what is stubbed, and what is pending verification against a live QNX target.
