# From zero to a determinism CI gate on QNX 8.0

> A complete, verified walkthrough: free QNX 8.0 license → headless install →
> QNX in QEMU → your first cycle-accurate timing measurement → a CI gate
> that fails when a build gets less deterministic.
>
> Every command and output below was executed end-to-end on Arch Linux
> (Hyprland/Wayland); it works the same on Ubuntu 22.04/24.04. Allow
> ~2 hours plus download time, and **~85 GB of disk** (the SDP is 3.6 GB;
> the QEMU image unpacks to 48 GB).

**Why this codelab exists:** QNX's core promise is time — not *fast*, but
*predictable*. Yet determinism is the one property of a QNX system that
isn't automatically tested today; the official tooling (tracelogger +
System Profiler in the IDE) is GUI-bound. This walkthrough ends with the
missing piece: a measurement your CI can gate on. The tool is
[detlab](https://github.com/TheDub-lab/qnx-detlab); you can follow along
with it, or build your own from the pieces shown here.

---

## Step 0 — Prerequisites

| Requirement | Check |
|---|---|
| Linux host (x86_64), any distro | `uname -m` → x86_64 |
| ~85 GB free disk | `df -h ~` |
| QEMU | `qemu-system-x86_64 --version` |
| Python 3.10+ | `python3 --version` |
| KVM access (fast, not required) | `test -w /dev/kvm && echo ok` |

No IDE, no Momentics, no supported-distro requirement — everything below
is command-line.

---

## Step 1 — Get QNX 8.0 free (QNX Everywhere)

1. Create a myQNX account at <https://www.qnx.com/getqnx>.
   *(Gotcha: the create-account form is hidden behind a JS reveal that
   breaks when the page rewrites its URL params — if you only see a login
   form, reload with the `#showcreate` anchor, or run
   `[...document.querySelectorAll('div')].find(d => /New to myQNX/.test(d.textContent)).style.display='block'`
   in DevTools.)*
2. Complete the QNX Everywhere license form (non-commercial use).
3. **Accept AND deploy the license to your own user** in the
   [myQNX License Manager](https://www.qnx.com/account/dashboard/).
   This is the single most common failure: a requested-and-accepted
   license that was never *deployed* leaves the installer unable to see
   any products, with an error message that doesn't tell you why.

Your license certificate PDF contains three things — keep them:

```
Serial Number:         <your serial>
Registration Password: <your password>
License Key:           XXXX-XXXX-XXXX-XXXX-XXXX
```

---

## Step 2 — Headless install (no IDE, any distro)

QNX officially supports Ubuntu/RHEL hosts, but the Software Center ships a
headless CLI (`qnxsoftwarecenter_clt`) that works anywhere with Java —
it bundles its own JRE.

Download the QSC Linux installer while logged in (the file is auth-gated):
<https://www.qnx.com/download/group.html?programid=29178> —
`qnx-setup-2.0.4-202501021438-linux.run`. Verify the MD5 against the
download page, then:

```sh
chmod +x qnx-setup-2.0.4-*-linux.run
./qnx-setup-2.0.4-*-linux.run force-override disable-auto-start \
    agree-to-license-terms ~/qnxinstall
```

Activate your license key (offline, no credentials needed):

```sh
cd ~/qnxinstall/qnxsoftwarecenter
./qnxsoftwarecenter_clt -addLicenseKey XXXX-XXXX-XXXX-XXXX-XXXX
./qnxsoftwarecenter_clt -listLicenseKeys
# [XXXX-XXXX-XXXX-XXXX-XXXX] - Activated - QNX Software Development
#   Platform 8.0 Education (Development Seat with IDE)
```

Now the package install. First sync the full package metadata (the GUI
login stores a session the CLI shares; or pass `-myqnx.user/-myqnx.password`):

```sh
./qnxsoftwarecenter_clt -mirror
```

**Gotcha:** a plain `-mirrorBaseline com.qnx.qnx800` fetches only thin
baseline metadata; the install then fails with
`Missing requirement: ... com.qnx.qnx800.target 0.0.1.0`. Run the full
`-mirror` (deprecated but complete), then install:

```sh
./qnxsoftwarecenter_clt -cleanInstall -destination ~/qnx800 \
    -installBaseline com.qnx.qnx800
```

Verify — this is the toolchain everything else depends on:

```sh
source ~/qnx800/qnxsdp-env.sh
qcc --version
# Toolchain:  gcc   Version: 12.2.0
echo $QNX_TARGET
# /home/<you>/qnx800/target/qnx
```

---

## Step 3 — QNX 8.0 in QEMU (no root required)

Install the Quick Start Target Image package through the same CLI:

```sh
./qnxsoftwarecenter_clt -destination ~/qnx800 \
    -installPackage "com.qnx.qnx800.quickstart.qemu=<latest version>"
```

Unpack it (2.5 GB download → 48 GB on disk):

```sh
cd ~/qnx800/images/qemu && ./unpack_qemu_image.sh
```

**Gotchas learned the hard way:**

- *Never* run `mkqnximage --build` against the shipped image — it fails
  with `Non-directory 'bin' has child nodes` and **truncates
  `output/ifs.bin`**. Restore with:
  `cat qnx_sdp8.0_qemu_quickstart_*.tar.gz.* | tar -xzOf - qemu/output/ifs.bin > qemu/output/ifs.bin`
- `mkqnximage --run` demands `brctl` + a network bridge + a setuid
  helper — all root privileges. Skip it entirely: launch QEMU directly
  with user-mode networking and an SSH forward
  ([run-qnx-qemu.sh](../scripts/run-qnx-qemu.sh) does exactly this):

```sh
qemu-system-x86_64 --enable-kvm --cpu host -smp 4 -m 4G \
    -nographic -vga none -serial mon:stdio \
    -kernel output/ifs.bin \
    -drive file=output/disk-qemu.vmdk,if=ide,id=drv0 \
    -netdev user,id=net0,hostfwd=tcp:127.0.0.1:2222-:22 \
    -device virtio-net-pci,netdev=net0,mac=52:54:00:cf:bf:ed \
    -object rng-random,filename=/dev/urandom,id=rng0 \
    -device virtio-rng-pci,rng=rng0
```

Boot messages scroll by; `/dev/screen` failures are expected (headless)
and harmless. When you see `Process count:28`, the system is up.

---

## Step 4 — Log in, enable SSH automation

The serial console (the launching terminal) shows a `login:` prompt:

```
login: root
Password: root
```

SSH is where automation wants to live, but the image ships root login
disabled. Fix it once:

```sh
# on the target (serial console):
sed -i 's/PermitRootLogin no/PermitRootLogin prohibit-password/' \
    /etc/ssh/sshd_config.d/98-qnx_qsti.conf
kill <sshd pid>          # slm respawns it with the new config
```

Install your public key — note root's **home is `/data/home/root`**
(`/root` is a symlink):

```sh
mkdir -p /data/home/root/.ssh
echo "<your pubkey>" > /data/home/root/.ssh/authorized_keys
chmod 700 /data/home/root/.ssh && chmod 600 /data/home/root/.ssh/authorized_keys
```

From the host: `ssh -p 2222 root@127.0.0.1 "uname -a"`

```
QNX qnxqemu 8.0.0 2026/06/05-16:26:03EDT x86pc x86_64
```

---

## Step 5 — Your first timing loop (and why `gettimeofday` is wrong)

Timing on QNX starts with `ClockCycles()` — a free-running 64-bit hardware
counter (RDTSC on x86, CNTVCT_EL0 on ARM). It is **not** a kernel call
and has no jitter of its own. Convert to seconds with the syspage value:

```c
#include <stdio.h>
#include <sys/neutrino.h>
#include <sys/syspage.h>

int main(void) {
    uint64_t cps = (uint64_t)SYSPAGE_ENTRY(qtime)->cycles_per_sec;
    uint64_t a = ClockCycles();
    /* ... work ... */
    uint64_t b = ClockCycles();
    printf("elapsed: %llu ns\n",
           (unsigned long long)((b - a) * 1000.0 / (cps / 1000000.0)));
    return 0;
}
```

Cross-compile and deploy:

```sh
qcc -Vgcc_ntox86_64 timing.c -o timing        # host, QNX_TARGET in scope
file timing
# ELF 64-bit LSB pie executable, x86-64, interpreter /usr/lib/ldqnx-64.so.2
scp -P 2222 timing root@127.0.0.1:/tmp/      # the interpreter path is the
                                             # QNX tell — Linux can't run it
```

**QNX 8.0 API note:** `setprio()` is gone — use POSIX
`sched_setscheduler()` / `sched_setparam()`.

---

## Step 6 — The wakeup path: what "late" actually means

A real-time loop wakes from a periodic timer. The path is
`timer_create` + `SIGEV_PULSE` → kernel → pulse delivery → your thread
scheduled — and *every* hop can add time. This is detlab's jitter probe
in essence ([jitter.c](../probe/src/jitter.c)):

```c
int chid = ChannelCreate(0);
int coid = ConnectAttach(0, 0, chid, _NTO_SIDE_CHANNEL, 0);
struct sigevent ev;
SIGEV_PULSE_INIT(&ev, coid, priority, _PULSE_CODE_MINAVAIL, 0);
timer_t timerid;
timer_create(CLOCK_MONOTONIC, &ev, &timerid);
timer_settime(timerid, 0, &its /* period */, NULL);

/* receive loop */
MsgReceivePulse(chid, &pulse, sizeof(pulse), NULL);
uint64_t now = ClockCycles();
int64_t delta = (int64_t)(now - expected_cycles);   /* signed! */
expected_cycles += period_cycles;
```

Three things that matter more than they look:

1. **Signed deltas.** Timer quantization means a wakeup can land a few
   µs *early*. Clamping to zero hides real behavior — we measured
   −32 µs to −45 µs early arrivals routinely.
2. **Allocate and fault-in buffers BEFORE arming the timer.** A
   `calloc` after `timer_settime` lets page faults stall the receive
   loop; the pulse queue overflows, pulses are silently dropped, and the
   expected schedule shifts forever (observed as exact +N×period steps).
3. **The kernel tick quantizes everything** — report
   `ClockPeriod(CLOCK_MONOTONIC, ...)` alongside your results (1 ms on
   the QSTI image) or the numbers mislead.

Run the probe on the target and you get raw wakeup deltas in
nanoseconds, one JSON document on stdout:

```sh
/tmp/detlab-probe jitter period_us=10000 iterations=1000 policy=fifo priority=50
```

---

## Step 7 — Measure like an engineer: percentiles, two views

One number lies. A wakeup distribution needs percentiles — and it needs
**two views**:

- **Offset from schedule** — arrival vs. the ideal wakeup time. Measures
  cumulative schedule fidelity. On a VM, a one-time stall re-anchors the
  timer and the offset absorbs it *forever* (we measured a +994 µs step
  on a 1 ms period that never recovered — a real QEMU/KVM artifact your
  harness should surface, not hide).
- **Inter-arrival spacing** — the time between consecutive wakeups.
  Measures per-wakeup consistency: what the application actually feels.

detlab computes both host-side from the same raw samples
(`spacing_i = period + offset_i − offset_{i−1}`):

```sh
detlab run scenarios/default.json --target qsti --out results/default.json
detlab report results/default.json --out reports/default.html
```

Real numbers from the QSTI target (QEMU, 1 ms tick):

```
jitter-10ms-fifo   offset  p50 −5.9 µs   p99 402 µs   max 893 µs
jitter-10ms-fifo   spacing p50 10 000.0 µs (exact)  p99 10 383 µs
```

Sub-6 µs median schedule fidelity on an *emulated* target — and the
policy comparison the whole pitch rests on, from the same session:

```
1 kHz loop, SCHED_FIFO:   p50  3.3 µs
1 kHz loop, SCHED_OTHER:  p50  ≈ 2 ms   (600× worse, same code)
```

---

## Step 8 — Make it a gate: determinism that can FAIL

Record a baseline, then check every run against it:

```sh
detlab report results/default.json --baseline-out baselines/default.json
detlab check results/new.json --baseline baselines/default.json && echo OK
```

A contract gates both directions: `regression_pct` (lateness ceiling)
and `floor_pct` (rate floor — spacing p50 must stay near the period).
Now break the system *on purpose*: change the loop's period constant
10 ms → 1 ms — a classic config refactor mistake:

```
$ detlab check /tmp/demo-run-bad.json --baseline baselines/demo.json
REGRESSION control-loop p99_ns: run=3013818 baseline=399905 limit=999762
REGRESSION control-loop sp_p50_ns: run=999908 baseline=9998618 limit=7998894
FAIL
exit=1
```

A gate that cannot fail is not a gate — verify both directions before
you trust it.

---

## Step 9 — Wire it into CI

The repo's [workflow](../.github/workflows/ci.yml) shows the shape:
host-logic tests on every push, and a determinism gate job that installs
the SDP headlessly, boots QNX, runs the scenario matrix, and lets
`detlab check`'s exit code decide the build's fate. Every commit then
answers the question QNX exists for:

> *did this change make the system less deterministic?*

---

## Where to go next

- Implement `preempt`/`policy`/`affinity` probes (designs documented in
  the source): measure the scheduler's dispatch path, verify
  `SCHED_SPORADIC` duty cycles, quantify CPU-affinity misconfiguration.
- Add `tracelogger` capture and correlate kernel events with latency
  outliers — the *why*, not just the *how much*.
- Run the same probe on a Raspberry Pi 5 (change `-Vgcc_ntox86_64` to
  `-Vgcc_ntoaarch64le`) for hardware-grounded numbers.

Questions or improvements: [open an issue](https://github.com/TheDub-lab/qnx-detlab/issues).
