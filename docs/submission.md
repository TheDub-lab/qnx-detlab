# Devpost submission — detlab

**Title:** detlab — determinism, gated. A regression harness for QNX 8.0.

**Category:** Developer Tooling & Host Tools

**Video:** VIDEO_URL

**Repo:** https://github.com/TheDub-lab/qnx-detlab

**Codelab (bonus field):** https://github.com/TheDub-lab/qnx-detlab/blob/master/docs/codelab.md

## Description (paste into the submission form)

QNX is sold on a guarantee about when your code runs. Yet determinism —
the property QNX is sold on — is the one thing a QNX team cannot
automatically test today. `tracelogger` captures traces from the CLI,
but analysis is IDE-bound (System Profiler), and nothing turns timing
into a pass/fail gate. detlab is that missing piece: a small on-target
probe suite plus a host harness that ends with a real CI exit code.

### What it does

- **Measures wakeup timing on the QNX 8.0 target, cycle-counter-based.**
  A C probe (cross-compiled with `qcc -Vgcc_ntox86_64`) arms a periodic
  `CLOCK_MONOTONIC` timer delivering `SIGEV_PULSE` events and records
  every wakeup delta against the ideal schedule in nanoseconds —
  100,000 samples per run, raw data preserved.
- **Reports two complementary views.** Offset-from-schedule (cumulative
  schedule fidelity) and inter-arrival spacing (per-wakeup consistency —
  what the RT application actually feels). Both are computed host-side
  from the same raw samples, so old runs can be re-analyzed under new
  definitions.
- **Gates determinism in CI.** Scenarios declare the timing contract
  (period, policy, priority, deadlines). `detlab check` compares a run
  against a recorded baseline and exits nonzero on regression —
  lateness ceilings (`regression_pct`) *and* rate floors (`floor_pct`,
  e.g. a period config error that makes the loop run 10× too fast).
- **Runs headless end to end.** No IDE anywhere: headless license
  activation, headless package install, headless QEMU target (SSH deploy
  with user-mode networking — no root, no network bridge).

### Real numbers from the QNX QSTI target (QEMU, 1 ms kernel tick)

| measurement | result |
|---|---|
| 100 Hz SCHED_FIFO loop, offset p50 | **−5.9 µs** (p99 402 µs) |
| inter-arrival spacing p50 | **10 000.0 µs — exact** |
| same 1 kHz loop, SCHED_FIFO vs SCHED_OTHER | **p50 3.3 µs vs ≈2 ms** (600×) |
| on-camera regression | period drift 10 ms→1 ms caught: **FAIL, exit 1** |

Negative offsets mean a wakeup landed *before* its ideal time — deltas
are measured against the ideal schedule, anchored at the first wakeup,
and early arrivals are real (1 ms tick quantization).

Absolute numbers on QEMU are emulator-bound; the contribution is the
gate, which runs identically on a Raspberry Pi 5 or real hardware
(one toolchain flag).

### How we use QNX-specific technology

The probe is built entirely on QNX 8.0 APIs: `ClockCycles()` +
`SYSPAGE_ENTRY(qtime)->cycles_per_sec` (cycle-counter timing),
`timer_create` + `SIGEV_PULSE`/`MsgReceivePulse()` (the wakeup path),
`sched_setscheduler()` with `SCHED_FIFO`/`SCHED_RR` (policy matrix),
`ClockPeriod()` (tick quantization reporting), the QNX QSTI QEMU target,
and `qcc` cross-compilation. Porting to a Raspberry Pi 5 is one flag
(`-Vgcc_ntoaarch64le`).

### Engineering honesty

The repo's
[verification-status table](https://github.com/TheDub-lab/qnx-detlab/blob/master/docs/architecture.md)
tracks implemented vs stubbed vs verified, and every claim above is backed
by a real run recorded in git. Five real bugs were found by measurement
rather than review — including a pulse-queue overflow caused by
allocating the sample buffer after arming the timer (deterministic
+N×period schedule steps), a QEMU vCPU-stall artifact that re-anchors
periodic timers (the reason the spacing metric exists), and a result-ID
collision that silently discarded raw samples. 16 unit tests cover the
pure decision logic; the gate was verified to fail *and* pass against
live targets.

### What's next

`preempt`/`policy`/`affinity` probes (designs documented in source —
dispatch latency, `SCHED_SPORADIC` duty-cycle verification, affinity
misconfiguration cost) and `tracelogger` trace correlation to attribute
latency outliers to kernel events.

### Built with

C (QNX 8.0, `qcc` 12.2.0), Python 3.10+ (stdlib only), QEMU, QNX QSTI,
GitHub Actions. By Michael Hammett.
