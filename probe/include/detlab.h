#ifndef DETLAB_H
#define DETLAB_H

/*
 * detlab probe suite — shared helpers.
 *
 * Probe contract (low-surprise, one purpose per process):
 *   detlab-probe <probe-name> [key=value ...]
 *   - all input arrives as argv key=value pairs (no config files, no stdin)
 *   - exactly one JSON document is printed on stdout on success
 *   - errors print {"error": "..."} on stdout and exit nonzero
 */

#include <stddef.h>
#include <stdint.h>

/* argv key=value accessors: last occurrence wins, defaults if absent. */
const char *arg_str(int argc, char *argv[], const char *key, const char *def);
long arg_long(int argc, char *argv[], const char *key, long def);

/*
 * Timing. ClockCycles() is a free-running 64-bit counter (RDTSC on x86,
 * CNTVCT_EL0 on ARM); convert deltas to nanoseconds against the syspage
 * cycles_per_sec value. Deliberately signed: a wakeup can land a few ns
 * early (timer quantization), and hiding that would be a lie.
 */
uint64_t detlab_cycles_per_sec(void);
int64_t detlab_cycles_delta_to_ns(int64_t delta, uint64_t cycles_per_sec);

/*
 * Result emission. json_meta must already be valid JSON
 * (e.g. {"period_us":1000}); the caller owns formatting it.
 */
void detlab_emit(const char *probe_name, const char *json_meta,
                 const int64_t *samples_ns, size_t count);
void detlab_emit_error(const char *probe_name, const char *fmt, ...);

/* Probe entry points. Each parses its own args; 0 on success. */
int run_jitter(int argc, char *argv[]);
int run_preempt(int argc, char *argv[]);
int run_policy(int argc, char *argv[]);
int run_affinity(int argc, char *argv[]);

#endif /* DETLAB_H */
