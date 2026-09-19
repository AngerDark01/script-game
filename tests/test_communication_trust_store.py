from __future__ import annotations

import json

import pytest

from auto_modules.application.communication.trust_store import (
    CertificateFingerprintMismatch,
    FileTrustStore,
    TrustRecord,
    TrustStoreError,
)
from auto_modules.core.communication.contracts import Capability, PeerId


def record(fingerprint: str = "fp-a") -> TrustRecord:
    return TrustRecord(
        peer_id=PeerId("peer-a"),
        device_id="device-a",
        certificate_fingerprint=fingerprint,
        address="127.0.0.1",
        port=4567,
        display_name="A",
        last_seen_ms=100,
    )


def test_trust_store_persists_records_and_capability_preferences(tmp_path) -> None:
    store = FileTrustStore(tmp_path)
    store.save(record())
    store.set_recovery_capabilities(
        PeerId("peer-a"), [Capability.POSITION_PUBLISH, Capability.EVENT_SUBSCRIBE]
    )

    reloaded = FileTrustStore(tmp_path)
    assert reloaded.get(PeerId("peer-a")) == record()
    assert reloaded.get_recovery_capabilities(PeerId("peer-a")) == {
        Capability.POSITION_PUBLISH,
        Capability.EVENT_SUBSCRIBE,
    }


def test_changed_certificate_is_rejected_unless_peer_is_forgotten(tmp_path) -> None:
    store = FileTrustStore(tmp_path)
    store.save(record())
    with pytest.raises(CertificateFingerprintMismatch):
        store.save(record("fp-b"))
    store.revoke(PeerId("peer-a"))
    assert store.is_revoked(PeerId("peer-a")) is True
    store.forget(PeerId("peer-a"))
    assert store.get(PeerId("peer-a")) is None
    assert store.is_revoked(PeerId("peer-a")) is False


def test_malformed_json_fails_closed_with_diagnostic_error(tmp_path) -> None:
    (tmp_path / "trusted_peers.json").write_text("{bad", encoding="utf-8")
    with pytest.raises(TrustStoreError) as error:
        FileTrustStore(tmp_path)
    assert "trusted_peers.json" in str(error.value)


def test_store_does_not_write_to_current_working_directory(tmp_path) -> None:
    store = FileTrustStore(tmp_path / "communication")
    store.save(record())
    assert (tmp_path / "communication" / "trusted_peers.json").is_file()
