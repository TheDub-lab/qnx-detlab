# Codelab: from zero to a determinism CI gate on QNX 8.0

> Target: the $3,500 Best Codelab bonus. This is the outline; the finished
> codelab will be a step-by-step walkthrough with expected outputs at each
> stage. Written to be honest — every step is one the author actually ran.

## Audience

Systems developers who know C and Linux but have never touched QNX.

## Steps

1. **Get QNX 8.0 free** — license at qnx.com/getqnx, headless QSC CLI install
   (`qnxsoftwarecenter_clt`), no IDE required.
2. **Boot QNX in QEMU** — unpack the QSTI, `mkqnximage --run`, first shell.
3. **Your first timing loop** — `ClockCycles()` and the syspage; why
   `gettimeofday()` is the wrong tool and what determinism even means.
4. **The wakeup path** — `timer_create` + `SIGEV_PULSE` + `MsgReceivePulse`:
   what happens between "timer fires" and "your code runs".
5. **Measure it** — build `detlab-probe`, run the jitter probe, read the
   histogram. Where does the p99.9 tail come from? (`ClockPeriod`, tick
   quantization, the 153 ns lesson from the QNX timing docs.)
6. **Policies** — rerun under `SCHED_FIFO` vs default; then `SCHED_SPORADIC`
   and the duty-cycle budget.
7. **Make it a gate** — record a baseline, break the system on purpose
   (add a CPU hog at a bad priority), watch `detlab check` fail, fix it,
   watch it pass.
8. **Wire it into CI** — the GitHub Actions job: determinism regression
   testing on every commit.

## Why it could win

Not a toy walkthrough: it ends with a reusable engineering practice
(continuous determinism testing) that QNX's own IDE-bound tooling doesn't
offer, demonstrated on the free QNX 8.0 license everyone can get.
