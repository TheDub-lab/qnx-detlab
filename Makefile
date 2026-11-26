QNX_ENV ?= $(HOME)/qnx800/qnxsdp-env.sh
PYTHON ?= python3

.PHONY: probe test demo clean

# Cross-compile the on-target probe with the QNX SDP 8.0 toolchain.
probe:
	@if [ ! -f "$(QNX_ENV)" ]; then \
		echo "QNX SDP environment not found at $(QNX_ENV)"; \
		echo "Set QNX_ENV=<path>/qnxsdp-env.sh (see README.md)"; \
		exit 1; \
	fi
	$(MAKE) -C probe QNX_ENV="$(QNX_ENV)"

# Host-side unit tests (pure logic, no QNX needed).
test:
	$(PYTHON) -m unittest discover -s tests -v

# Synthetic end-to-end demo: fake probe data -> report + baseline check.
# Runs with no QNX SDP and no QEMU; exercises report/check paths.
demo:
	$(PYTHON) -m detlab demo --out-dir scratch-demo

clean:
	$(MAKE) -C probe clean
	rm -rf scratch-demo
