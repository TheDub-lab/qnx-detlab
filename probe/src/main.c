/*
 * detlab-probe — dispatcher. One probe per process; see include/detlab.h
 * for the argv/JSON contract.
 */

#include <string.h>

#include "detlab.h"

int main(int argc, char *argv[])
{
    if (argc < 2) {
        detlab_emit_error("none", "usage: detlab-probe <probe> [key=value ...]");
        return 2;
    }

    const char *probe = argv[1];
    if (strcmp(probe, "jitter") == 0) {
        return run_jitter(argc, argv);
    }
    if (strcmp(probe, "preempt") == 0) {
        return run_preempt(argc, argv);
    }
    if (strcmp(probe, "policy") == 0) {
        return run_policy(argc, argv);
    }
    if (strcmp(probe, "affinity") == 0) {
        return run_affinity(argc, argv);
    }

    detlab_emit_error(probe, "unknown probe");
    return 2;
}
