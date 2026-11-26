# On-target probe: one binary, one probe per invocation.
# Cross-compiled with qcc from QNX SDP 8.0.

QNX_ENV ?= $(HOME)/qnx800/qnxsdp-env.sh
QCC := $(shell command -v qcc 2>/dev/null)
ARCH ?= gcc_ntox86_64
CFLAGS ?= -Wall -Wextra -O2

SRC := src/main.c src/util.c src/jitter.c src/preempt.c src/policy.c src/affinity.c
BIN := detlab-probe

.PHONY: all clean

all: check-env $(BIN)

# Import the SDP environment in the same shell that builds.
check-env:
ifeq ($(QCC),)
	@bash -c 'source $(QNX_ENV) >/dev/null 2>&1 && command -v qcc >/dev/null' \
		|| { echo "qcc not found and $(QNX_ENV) did not provide it."; \
		     echo "Install QNX SDP 8.0 or set QNX_ENV."; exit 1; }
endif

$(BIN): $(SRC) include/detlab.h
	bash -c 'source $(QNX_ENV) >/dev/null 2>&1; \
		$${QNX_HOST}/usr/bin/qcc -V$(ARCH) $(CFLAGS) -Iinclude -o $@ $(SRC)' \
		|| { echo "build failed: is QNX SDP 8.0 installed?"; exit 1; }

clean:
	rm -f $(BIN) *.o
