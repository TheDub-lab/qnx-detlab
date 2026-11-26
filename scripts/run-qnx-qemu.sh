#!/bin/bash
# Headless launcher for the QNX SDP 8.0 QSTI (Quick Start Target Image) in QEMU.
#
# Bypasses mkqnximage's bridge networking setup (brctl/virbr0/setuid
# qemu-bridge-helper, all root-dependent) and uses QEMU user-mode
# networking with an SSH port-forward instead:
#
#   ssh -p 2222 root@127.0.0.1
#
# Derived from mkqnximage's own runimage arguments (qemu_options, options
# files): -kernel ifs.bin, ide disk, virtio-net, virtio-rng, 4 vCPU/4G RAM.
# No root required anywhere.

set -euo pipefail

QSTI_DIR="${QSTI_DIR:-$HOME/qnx800/images/qemu/qemu}"
SSH_PORT="${QSTI_SSH_PORT:-2222}"

if [ ! -f "$QSTI_DIR/output/ifs.bin" ]; then
    echo "QSTI image not found at $QSTI_DIR (set QSTI_DIR)" >&2
    exit 1
fi

cd "$QSTI_DIR"

KVM_ARGS="--enable-kvm --cpu host"
if [ ! -w /dev/kvm ]; then
    echo "WARNING: /dev/kvm not writable, using TCG emulation (slow)" >&2
    KVM_ARGS="--cpu max"
fi

exec qemu-system-x86_64 \
    $KVM_ARGS \
    -smp "${QSTI_SMP:-4}" \
    -m "${QSTI_RAM:-4G}" \
    -nographic -vga none \
    -serial mon:stdio \
    -kernel output/ifs.bin \
    -drive file=output/disk-qemu.vmdk,if=ide,id=drv0 \
    -netdev "user,id=net0,hostfwd=tcp:127.0.0.1:${SSH_PORT}-:22" \
    -device virtio-net-pci,netdev=net0,mac=52:54:00:cf:bf:ed \
    -object rng-random,filename=/dev/urandom,id=rng0 \
    -device virtio-rng-pci,rng=rng0 \
    -pidfile output/qemu-detlab.pid
