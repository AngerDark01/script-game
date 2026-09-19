from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_communication_docs_describe_shared_session_and_map_boundary() -> None:
    architecture = (ROOT / "ARCHITECTURE_GUIDE.md").read_text(encoding="utf-8")
    protocol = (ROOT / "services/lan_input_sync/docs/protocol-v1.md").read_text(encoding="utf-8")
    assert "one PeerSession per peer" in architecture
    assert "map.publish" in architecture
    assert "capabilities" in protocol
    assert "start-data" in protocol


def test_plan_records_manual_disconnect_recovery_rule() -> None:
    plan = (ROOT / "docs/plans/2026-09-19-communication-layer-refactor-draft.md").read_text(encoding="utf-8")
    assert "用户手动断开、手动停止、忘记设备或急停" in plan
    assert "不实现地图同步业务" in plan
