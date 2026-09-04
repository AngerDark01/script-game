import importlib.util
import sys
import types
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "live_gamepad_probe.py"
SPEC = importlib.util.spec_from_file_location("live_gamepad_probe", SCRIPT)
probe = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules.setdefault("pydirectinput", types.ModuleType("pydirectinput"))
SPEC.loader.exec_module(probe)


def test_detects_lower_integrity_sender():
    assert probe.sender_is_lower_integrity({"rid": 0x2000}, {"rid": 0x3000})


def test_does_not_block_equal_or_unknown_integrity():
    assert not probe.sender_is_lower_integrity({"rid": 0x3000}, {"rid": 0x3000})
    assert not probe.sender_is_lower_integrity({"error": "denied"}, {"rid": 0x3000})
