/*
 * Shared probe helpers: argv parsing, syspage timing, JSON emission.
 */

#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <sys/syspage.h>

#include "detlab.h"

const char *arg_str(int argc, char *argv[], const char *key, const char *def)
{
    size_t klen = strlen(key);
    for (int i = 2; i < argc; i++) { /* argv[1] is the probe name */
        if (strncmp(argv[i], key, klen) == 0 && argv[i][klen] == '=') {
            return argv[i] + klen + 1;
        }
    }
    return def;
}

long arg_long(int argc, char *argv[], const char *key, long def)
{
    const char *v = arg_str(argc, argv, key, NULL);
    return v ? strtol(v, NULL, 10) : def;
}

uint64_t detlab_cycles_per_sec(void)
{
    return (uint64_t)SYSPAGE_ENTRY(qtime)->cycles_per_sec;
}

int64_t detlab_cycles_delta_to_ns(int64_t delta, uint64_t cycles_per_sec)
{
    /* Scale first in 128-bit range of practice: delta * 1e9 / cps.
     * deltas here are sub-second, so delta * 1e9 fits 64 bits for any
     * realistic cps (>10 MHz) and delta (<1 s). */
    return (int64_t)(((double)delta * 1e9) / (double)cycles_per_sec);
}

void detlab_emit(const char *probe_name, const char *json_meta,
                 const int64_t *samples_ns, size_t count)
{
    printf("{\"probe\":\"%s\",\"meta\":%s,\"samples_ns\":[", probe_name,
           json_meta);
    for (size_t i = 0; i < count; i++) {
        printf("%s%lld", i ? "," : "", (long long)samples_ns[i]);
    }
    printf("]}\n");
}

void detlab_emit_error(const char *probe_name, const char *fmt, ...)
{
    va_list ap;
    printf("{\"probe\":\"%s\",\"error\":\"", probe_name);
    va_start(ap, fmt);
    vprintf(fmt, ap);
    va_end(ap);
    printf("\"}\n");
}
