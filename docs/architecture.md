# detlab architecture

## Data flow

```
scenarios/*.json --(detlab run)--> QEMU QNX 8.0 --SSH--> detlab-probe
        |                                                  |
        |                                          JSON + samples_ns
        v                                                  v
  results/run.json  <--------------------------------------+
        |
        +--(detlab report)-->  reports/report.html  (SVG histograms, tables)
        |
        +--(detlab check)-->  exit 0/1  (baseline regression gate for CI)
```

## Components

- **probe/** — C, one JSON document per invocation. Contract in
  `probe/include/detlab.h`: argv `key=value` in, one JSON doc out. The probe
  is deliberately dumb: it records raw `ClockCycles()` deltas; all math and
  summarizing live host-side so the on-target code stays auditable and the
  measurement loop stays cheap.
- **host/detlab/** — Python 3.10+ stdlib only.
  - `metrics.py` — pure math (percentiles, histograms)
  - `check.py` — pure regression decision logic
  - `runner.py` — local/remote execution, result normalization
  - `qemu.py` — QSTI VM lifecycle via `mkqnximage`
  - `report.py` — self-contained HTML report
  - `trace.py` — kernel trace capture/correlation (stub)
- **scenarios/** — declarative probe matrix; `rt-contract-example.json`
  shows the check-threshold idea (a timing contract encoded as data).

## Design rules

1. **Pure logic separated from I/O.** `metrics`/`check` import nothing that
   touches files or processes; that's what makes them testable without QNX.
2. **One probe process per scenario entry.** No shared state on the target;
   a crashed probe can't poison the next measurement.
3. **The probe measures, the host interprets.** Raw samples always survive
   in the run document (`samples` map) so a new percentile definition can be
   recomputed from old runs.
4. **Signed deltas.** A wakeup can land a few ns early (tick quantization);
   samples are `int64_t` so the data can't lie by construction.

## Verification status

| Component | Status | Verified by |
|---|---|---|
| `metrics.py`, `check.py` | **implemented, tested** | `tests/test_core.py` (12 tests, run on host) |
| `report.py` | implemented, exercised by synthetic demo | `detlab demo` |
| CLI (`run/report/check/demo`) | **implemented; `run` verified against live QNX** | smoke + default scenario on QEMU QSTI |
| `probe/src/jitter.c` | **implemented, compiled with qcc 12.2.0, RUNS ON TARGET** | smoke run: FIFO p50=3.3us vs OTHER p50=1.99ms |
| `probe/src/{preempt,policy,affinity}.c` | stubs with documented measurement designs | pending |
| `scripts/run-qnx-qemu.sh` | **implemented, boots QNX headless, no root needed** | live VM + serial console login |
| `qemu.py` "existing" mode | **implemented, verified against live VM** | smoke + default runs (SSH root@127.0.0.1:2222) |
| `qemu.py` "qsti" mode (mkqnximage launch) | **blocked without root**: mkqnximage's check-net requires brctl + virbr0 bridge + setuid qemu-bridge-helper | use scripts/run-qnx-qemu.sh instead |
| `trace.py` | stub, design documented | pending |
| CI QNX gate job | commented out, waiting on SDP install + secrets | pending |

## Target notes (QEMU QSTI 8.0.0, image 20260902) — learned the hard way

- Console login: `root`/`root`. SSH: root is blocked by
  `/etc/ssh/sshd_config.d/98-qnx_qsti.conf` (`PermitRootLogin no`); change to
  `prohibit-password` and `kill` sshd (slm respawns it). Root's home is
  `/data/home/root` (`/root` is a symlink).
- Do NOT run `mkqnximage --build` against the shipped image: it fails
  ("Non-directory 'bin' has child nodes") and truncates `output/ifs.bin`.
  Restore with:
  `cat qnx_sdp8.0_qemu_quickstart_*.tar.gz.* \| tar -xzOf - qemu/output/ifs.bin > qemu/output/ifs.bin`
- Kernel tick on the image is 1 ms, so late wakeups quantize to ~1 ms and
  early arrivals are real (measured -32 us to -45 us).

## First on-target session checklist

1. `make probe` — does `qcc -Vgcc_ntox86_64` accept the sources as written?
   (API risk: `SIGEV_PULSE_INIT`, `ConnectAttach(..., _NTO_SIDE_CHANNEL, 0)`,
   `SYSPAGE_ENTRY(qtime)->cycles_per_sec` — all straight from QNX 8.0 docs.)
2. `detlab-probe jitter iterations=1000` in the QEMU serial console —
   does the JSON land on stdout?
3. `detlab run scenarios/default.json --target qsti` — does `mkqnximage
   --getip` / SSH behave as `qemu.py` assumes?
4. Record `baselines/default.json`, then flip the commented CI job on.
