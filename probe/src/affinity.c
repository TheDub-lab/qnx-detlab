/*
 * Probe: affinity — RT thread interference under CPU load.  [STUB]
 *
 * Planned measurement:
 *
 *   1. Pin a jitter probe (same pulse-timer loop as jitter.c) to CPU A
 *      via ThreadCtl(_CTL_SET_CPU...)/pthread affinity, run N CPU-hog
 *      threads at lower priority on the same CPU vs. other CPUs.
 *   2. Sample set 1: hogs elsewhere -> RT thread's wakeup distribution.
 *      Sample set 2: hogs on the same CPU -> measure the tail.
 *   3. Args: pin_cpu, hogs, hogs_cpu, hog_prio.
 *
 *   The comparison is the product feature: it shows what a misconfigured
 *   affinity mask costs in p99.9 wakeup latency.
 *
 * Status: skeleton — see docs/architecture.md#verification-status.
 */

#include "detlab.h"

int run_affinity(int argc, char *argv[])
{
    (void)argc;
    (void)argv;
    detlab_emit_error("affinity", "not implemented yet (see probe/src/affinity.c)");
    return 3;
}
