"""Bounded real Host program-output probe for the PoE2 follow experiment.

This intentionally sends one short full-stick frame, immediately neutralizes
it, and releases the lease. It does not use keyboard mapping or LAN sync.
Run the script elevated because the workbench Host is elevated.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from auto_modules.adapters.virtual_gamepad import ProgramGamepadOutput, VirtualGamepadClient


def main() -> int:
    controller = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    if controller not in (1, 2):
        raise SystemExit("controller must be 1 or 2")
    log_path = REPOSITORY_ROOT / "data" / "logs" / "program_input_probe.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    def record(step: str, **details: object) -> None:
        with log_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"step": step, **details}, ensure_ascii=False) + "\n")

    client = VirtualGamepadClient()
    output = ProgramGamepadOutput(client, controller=controller)
    try:
        record("connect.start", controller=controller)
        client.connect(timeout=3.0)
        record("connect.success")
        status = client.status()
        record("status.before", status=status)
        output.start()
        record("program.acquire.success", controller=controller)
        output.write((1.0, 0.0), elapsed_ms=20, valid_for_ms=120)
        record("program.state.direction", controller=controller, duration_ms=120)
        time.sleep(0.12)
        output.write((0.0, 0.0), elapsed_ms=20, valid_for_ms=120)
        record("program.state.neutral", controller=controller)
        output.stop()
        record("program.release.success", controller=controller)
        record("status.after", status=client.status())
        return 0
    except Exception as exc:
        record("failed", type=type(exc).__name__, error=str(exc))
        return 1
    finally:
        try:
            output.close()
        except Exception as exc:
            record("close.failed", type=type(exc).__name__, error=str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
