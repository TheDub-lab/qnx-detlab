/*
 * Probe: preempt — priority preemption latency.  [STUB]
 *
 * Planned measurement (design decision, not yet implemented):
 *
 *   1. Spawn a low-priority worker that busy-loops on a shared CPU.
 *   2. Parent creates a channel; a "release" pulse triggers the
 *      high-priority thread to wake and timestamp itself with
 *      ClockCycles().
 *   3. Sample = (high-prio thread's first instruction time)
 *              - (release pulse send time), both on the same CPU.
 *   4. Args: release_method={pulse,eventvar,condvar}, load_prio,
 *      iterations, pin_cpu.
 *
 * This isolates the scheduler's dispatch path from the timer hardware
 * path probed by jitter.c, and the release_method axis shows the cost
 * of each QNX wakeup primitive (MsgSendPulse vs. pthread_cond vs.
 * InterruptWait).
 *
 * Status: skeleton — see docs/architecture.md#verification-status.
 */

#include "detlab.h"

int run_preempt(int argc, char *argv[])
{
    (void)argc;
    (void)argv;
    detlab_emit_error("preempt", "not implemented yet (see probe/src/preempt.c)");
    return 3;
}
