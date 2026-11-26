"""QNX QEMU target lifecycle: launch, wait for SSH, execute, teardown.

UNVERIFIED against a live QSTI 0.5.0 image — this module is written from
the documented mkqnximage interface and must be exercised in the first
on-target session. See docs/architecture.md#verification-status.

Documented interface this relies on (QNX "Quick Start Target Image for
QEMU" guide, updated 2026-09-24):
    mkqnximage --run    launch the VM (serial console on the invoking tty)
    mkqnximage --getip  print the VM's IP address (from the same runtime dir)
    mkqnximage --stop   shut the VM down
The QSTI image runs an SSH server; the harness logs in as root.

For a fully headless/custom launch (e.g. -nographic with explicit
hostfwd), set "launch_cmd" / "getip_cmd" in the target config to override
the mkqnximage defaults.
"""

import os
import shlex
import subprocess
import time


class QemuTargetError(Exception):
    pass


class QemuTarget:
    """One running QNX VM. Supports the exec() contract runner.run_remote
    expects; keep deployment and execution behind that single boundary."""

    def __init__(self, config):
        self.qsti_dir = config.get(
            "qsti_dir",
            os.environ.get(
                "DETLAB_QSTI_DIR",
                os.path.expanduser("~/qnx800/images/qemu/qemu"),
            ),
        )
        self.ssh_user = config.get("ssh_user", "root")
        self.launch_cmd = config.get("launch_cmd", "mkqnximage --run")
        self.getip_cmd = config.get("getip_cmd", "mkqnximage --getip")
        self.stop_cmd = config.get("stop_cmd", "mkqnximage --stop")
        self.ssh_port = int(config.get("ssh_port", 22))
        self.vm = None
        self.ip = None

    def start(self, boot_timeout=180):
        if not os.path.isdir(self.qsti_dir):
            raise QemuTargetError(
                f"QSTI runtime dir not found: {self.qsti_dir} "
                "(set DETLAB_QSTI_DIR or config 'qsti_dir')"
            )
        self.vm = subprocess.Popen(
            shlex.split(self.launch_cmd),
            cwd=self.qsti_dir,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        deadline = time.monotonic() + boot_timeout
        while time.monotonic() < deadline:
            if self.vm.poll() is not None:
                raise QemuTargetError("QEMU exited during boot")
            ip = self._probe_ip()
            if ip:
                self.ip = ip
                return self
            time.sleep(5)
        raise QemuTargetError(f"VM did not report an IP within {boot_timeout}s")

    def _probe_ip(self):
        try:
            out = subprocess.run(
                shlex.split(self.getip_cmd),
                cwd=self.qsti_dir,
                capture_output=True,
                timeout=30,
            )
        except subprocess.TimeoutExpired:
            return None
        if out.returncode != 0:
            return None
        for token in out.stdout.decode().split():
            # first thing on the line that parses as an IPv4 address
            if len(token.split(".")) == 4 and all(
                p.isdigit() for p in token.split(".")
            ):
                return token
        return None

    def _ssh_argv(self, cmd):
        return [
            "ssh",
            "-o", "BatchMode=yes",
            "-o", "StrictHostKeyChecking=accept-new",
            "-o", f"ConnectTimeout=10",
            "-p", str(self.ssh_port),
            f"{self.ssh_user}@{self.ip}",
            cmd,
        ]

    def exec(self, cmd, timeout=120):
        """Run a shell command on the target; return stdout. Raises
        QemuTargetError on nonzero exit so callers never mistake
        failure for data."""
        proc = subprocess.run(
            self._ssh_argv(cmd), capture_output=True, timeout=timeout
        )
        if proc.returncode != 0:
            raise QemuTargetError(
                f"ssh command failed ({proc.returncode}): "
                f"{proc.stderr.decode()[:300]}"
            )
        return proc.stdout

    def put(self, local_path, remote_path):
        proc = subprocess.run(
            [
                "scp",
                "-o", "BatchMode=yes",
                "-o", "StrictHostKeyChecking=accept-new",
                "-P", str(self.ssh_port),
                local_path,
                f"{self.ssh_user}@{self.ip}:{remote_path}",
            ],
            capture_output=True,
            timeout=120,
        )
        if proc.returncode != 0:
            raise QemuTargetError(f"scp failed: {proc.stderr.decode()[:300]}")

    def stop(self):
        if self.vm is not None and self.vm.poll() is None:
            subprocess.run(
                shlex.split(self.stop_cmd),
                cwd=self.qsti_dir,
                capture_output=True,
                timeout=30,
            )
            self.vm.wait(timeout=30)
        self.vm = None

    def __enter__(self):
        return self.start()

    def __exit__(self, *exc):
        self.stop()
        return False
