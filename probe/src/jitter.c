/*
 * Probe: jitter — periodic timer wakeup latency.
 *
 * Arms a periodic CLOCK_MONOTONIC timer that delivers SIGEV_PULSE events
 * to this process, then measures how far each wakeup lands from its ideal
 * schedule (arrival - (start + n * period)) in nanoseconds.
 *
 * Args:
 *   period_us   timer period in microseconds          (default 1000)
 *   iterations  wakeups to measure                    (default 100000)
 *   warmup      initial wakeups skipped before recording (default 100)
 *   policy      fifo | rr | other                     (default fifo)
 *   priority    scheduling priority                    (default 50)
 *
 * The sample is taken at MsgReceivePulse() return, i.e. it includes timer
 * fire -> kernel -> pulse delivery -> thread scheduled. That is the number
 * a real-time application actually experiences.
 */

#include <errno.h>
#include <process.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#include <sys/neutrino.h>
#include <sys/syspage.h>

#include "detlab.h"

static int apply_policy(const char *policy, int priority)
{
    struct sched_param sp;
    memset(&sp, 0, sizeof(sp));
    sp.sched_priority = priority;

    if (strcmp(policy, "fifo") == 0) {
        return sched_setscheduler(0, SCHED_FIFO, &sp);
    }
    if (strcmp(policy, "rr") == 0) {
        return sched_setscheduler(0, SCHED_RR, &sp);
    }
    /* "other": default time-sharing policy. setprio() is gone in QNX 8.0;
     * sched_setparam() with a priority is the replacement. */
    return sched_setparam(0, &sp);
}

int run_jitter(int argc, char *argv[])
{
    long period_us = arg_long(argc, argv, "period_us", 1000);
    long iterations = arg_long(argc, argv, "iterations", 100000);
    long warmup = arg_long(argc, argv, "warmup", 100);
    const char *policy = arg_str(argc, argv, "policy", "fifo");
    long priority = arg_long(argc, argv, "priority", 50);

    if (period_us <= 0 || iterations <= 0 || warmup < 0) {
        detlab_emit_error("jitter", "invalid period_us/iterations/warmup");
        return 2;
    }

    uint64_t cps = detlab_cycles_per_sec();
    if (cps == 0) {
        detlab_emit_error("jitter", "syspage reports cycles_per_sec == 0");
        return 1;
    }

    if (apply_policy(policy, (int)priority) != 0) {
        detlab_emit_error("jitter", "sched policy %s prio %ld failed: %s",
                          policy, priority, strerror(errno));
        return 1;
    }

    int chid = ChannelCreate(0);
    if (chid == -1) {
        detlab_emit_error("jitter", "ChannelCreate: %s", strerror(errno));
        return 1;
    }
    int coid = ConnectAttach(0, 0, chid, _NTO_SIDE_CHANNEL, 0);
    if (coid == -1) {
        detlab_emit_error("jitter", "ConnectAttach: %s", strerror(errno));
        return 1;
    }

    struct sigevent ev;
    SIGEV_PULSE_INIT(&ev, coid, (int)priority, _PULSE_CODE_MINAVAIL, 0);

    timer_t timerid;
    if (timer_create(CLOCK_MONOTONIC, &ev, &timerid) != 0) {
        detlab_emit_error("jitter", "timer_create: %s", strerror(errno));
        return 1;
    }

    /* Report the kernel tick alongside the results: on PC hardware the
     * tick quantizes all timers, and hiding it misleads readers. */
    struct _clockperiod cp;
    long tick_ns = -1;
    if (ClockPeriod(CLOCK_MONOTONIC, NULL, &cp, 0) == 0) {
        tick_ns = (long)cp.nsec;
    }

    struct itimerspec its;
    its.it_value.tv_sec = period_us / 1000000;
    its.it_value.tv_nsec = (period_us % 1000000) * 1000;
    its.it_interval = its.it_value;
    if (timer_settime(timerid, 0, &its, NULL) != 0) {
        detlab_emit_error("jitter", "timer_settime: %s", strerror(errno));
        return 1;
    }

    int64_t *samples = calloc((size_t)iterations, sizeof(int64_t));
    if (samples == NULL) {
        detlab_emit_error("jitter", "out of memory for %ld samples",
                          iterations);
        return 1;
    }

    /* Sync phase: the first pulse tells us where the schedule actually
     * started (the first expiry is relative to timer_settime). */
    struct _pulse pulse;
    uint64_t expected_cycles = 0;
    uint64_t period_cycles = (uint64_t)(((double)period_us * cps) / 1e6);
    size_t recorded = 0;

    for (long i = 0; i < iterations + warmup + 1; i++) {
        if (MsgReceivePulse(chid, &pulse, sizeof(pulse), NULL) == -1) {
            detlab_emit_error("jitter", "MsgReceivePulse: %s",
                              strerror(errno));
            free(samples);
            return 1;
        }
        uint64_t now = ClockCycles();

        if (i == 0) {
            expected_cycles = now + period_cycles;
            continue;
        }
        if (i <= warmup) {
            expected_cycles += period_cycles;
            continue;
        }

        int64_t delta = (int64_t)(now - expected_cycles);
        samples[recorded++] = detlab_cycles_delta_to_ns(delta, cps);
        expected_cycles += period_cycles;
    }

    char meta[512];
    snprintf(meta, sizeof(meta),
             "{\"period_us\":%ld,\"iterations\":%ld,\"warmup\":%ld,"
             "\"policy\":\"%s\",\"priority\":%ld,"
             "\"cycles_per_sec\":%llu,\"clock_period_ns\":%ld,"
             "\"signal\":\"SIGEV_PULSE\",\"clock\":\"CLOCK_MONOTONIC\"}",
             period_us, iterations, warmup, policy, priority,
             (unsigned long long)cps, tick_ns);

    detlab_emit("jitter", meta, samples, recorded);

    free(samples);
    return 0;
}
