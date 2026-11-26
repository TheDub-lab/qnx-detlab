/*
 * Probe: policy — scheduling policy comparison.  [STUB]
 *
 * Planned measurement:
 *
 *   Same periodic workload as jitter.c, but driven under each policy:
 *   SCHED_FIFO, SCHED_RR, SCHED_SPORADIC (foreground/background budget
 *   verification — the QNX docs' canonical sporadic duty-cycle example),
 *   and the default time-sharing policy. One process per policy; the
 *   harness runs the matrix and the report lines the percentiles up
 *   side by side.
 *
 *   SCHED_SPORADIC args (beyond jitter's): repl_period_us, init_budget_ns,
 *   bg_priority — verifying that the OS actually demotes the thread to
 *   bg_priority once the budget is spent, and promotes it again at the
 *   next replenishment.
 *
 * Status: skeleton — see docs/architecture.md#verification-status.
 */

#include "detlab.h"

int run_policy(int argc, char *argv[])
{
    (void)argc;
    (void)argv;
    detlab_emit_error("policy", "not implemented yet (see probe/src/policy.c)");
    return 3;
}
