"""Container healthcheck for the worker service (A10).

The worker has no HTTP port, so liveness is checked by process presence inside the
same container: at least one process whose cmdline contains ``worker.main``.
Deeper "is it actually consuming jobs" monitoring is done out-of-band by
``scripts/operation_healthcheck.py`` (job-queue effect), which keeps DB
credentials out of the healthcheck. Exit 0 = alive, 1 = not found.
"""
import pathlib
import sys

for proc in pathlib.Path("/proc").iterdir():
    if not proc.name.isdigit():
        continue
    try:
        cmdline = (proc / "cmdline").read_bytes()
    except OSError:
        continue
    if b"worker.main" in cmdline:
        sys.exit(0)
sys.exit(1)
