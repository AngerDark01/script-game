"""Offline reproduction of a Windows spawn child exiting during main import.

No application imports, capture, memory reads, Host, or input. Run `blocked`
to model bootstrap's import-time single-instance exit, or `clean` as control.
The invoking test runner must impose a timeout on the blocked variant.
"""
from __future__ import annotations

import faulthandler
import multiprocessing as mp
import sys


if __name__ == "__mp_main__" and sys.argv[1:2] == ["blocked"]:
    print("child_import: simulated single-instance rejection", flush=True)
    raise SystemExit(0)


def receive(payload: bytes) -> None:
    print(f"child_target_reached bytes={len(payload)}", flush=True)


def main() -> None:
    if sys.argv[1:2] not in (["blocked"], ["clean"]):
        raise SystemExit("usage: spawn_import_exit_probe.py blocked|clean")
    faulthandler.dump_traceback_later(2, repeat=False)
    process = mp.get_context("spawn").Process(
        target=receive, args=(bytes(6 * 1024 * 1024),), daemon=True,
    )
    print("parent: process.start enter", flush=True)
    process.start()
    print("parent: process.start returned", flush=True)
    process.join(3)
    if process.is_alive():
        process.terminate()
        process.join(1)
    faulthandler.cancel_dump_traceback_later()
    print(f"parent: child exit={process.exitcode}", flush=True)


if __name__ == "__main__":
    main()
