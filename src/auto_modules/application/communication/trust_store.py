"""Persistent, non-secret trust metadata for communication peers."""

from __future__ import annotations

import json
import os
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from auto_modules.core.communication.contracts import Capability, PeerId
from auto_modules.paths import data_root


class TrustStoreError(RuntimeError):
    """A trust file could not be read safely."""


class CertificateFingerprintMismatch(TrustStoreError):
    """A known peer presented a different certificate fingerprint."""


@dataclass(frozen=True, slots=True)
class TrustRecord:
    peer_id: PeerId
    device_id: str
    certificate_fingerprint: str
    address: str
    port: int
    display_name: str = ""
    last_seen_ms: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.peer_id, PeerId):
            object.__setattr__(self, "peer_id", PeerId(str(self.peer_id)))
        for name in ("device_id", "certificate_fingerprint", "address"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")
        if isinstance(self.port, bool) or not isinstance(self.port, int) or not 0 < self.port <= 65535:
            raise ValueError("port must be between 1 and 65535")
        if self.last_seen_ms is not None and (
            isinstance(self.last_seen_ms, bool)
            or not isinstance(self.last_seen_ms, int)
            or self.last_seen_ms < 0
        ):
            raise ValueError("last_seen_ms must be a non-negative integer")

    def to_json(self) -> dict[str, Any]:
        return {
            "peerId": str(self.peer_id),
            "deviceId": self.device_id,
            "certificateFingerprint": self.certificate_fingerprint,
            "address": self.address,
            "port": self.port,
            "displayName": self.display_name,
            "lastSeenMs": self.last_seen_ms,
        }

    @classmethod
    def from_json(cls, value: Any) -> "TrustRecord":
        if not isinstance(value, dict):
            raise ValueError("trust record must be an object")
        return cls(
            peer_id=PeerId(value["peerId"]),
            device_id=value["deviceId"],
            certificate_fingerprint=value["certificateFingerprint"],
            address=value["address"],
            port=value["port"],
            display_name=value.get("displayName", ""),
            last_seen_ms=value.get("lastSeenMs"),
        )


class FileTrustStore:
    """Atomic file-backed trust, revocation, and recovery preference store."""

    def __init__(self, root: Path | str | None = None) -> None:
        self.root = Path(root) if root is not None else data_root() / "communication"
        self.root.mkdir(parents=True, exist_ok=True)
        self._trusted_path = self.root / "trusted_peers.json"
        self._revoked_path = self.root / "revocations.json"
        self._preferences_path = self.root / "capability_preferences.json"
        self._trusted = self._read_mapping(self._trusted_path)
        self._revoked = self._read_mapping(self._revoked_path)
        self._preferences = self._read_mapping(self._preferences_path)

    def get(self, peer_id: PeerId | str) -> TrustRecord | None:
        value = self._trusted.get(str(peer_id))
        return None if value is None else TrustRecord.from_json(value)

    def list_trusted(self) -> tuple[TrustRecord, ...]:
        return tuple(TrustRecord.from_json(value) for value in self._trusted.values())

    def save(self, record: TrustRecord, *, replace_certificate: bool = False) -> None:
        existing = self.get(record.peer_id)
        if (
            existing is not None
            and existing.certificate_fingerprint != record.certificate_fingerprint
            and not replace_certificate
        ):
            raise CertificateFingerprintMismatch(
                f"certificate fingerprint changed for peer {record.peer_id}"
            )
        self._trusted[str(record.peer_id)] = record.to_json()
        self._atomic_write(self._trusted_path, self._trusted)

    def revoke(self, peer_id: PeerId | str, *, reason: str = "") -> None:
        self._revoked[str(peer_id)] = {
            "revokedAtMs": int(time.time() * 1000),
            "reason": reason,
        }
        self._atomic_write(self._revoked_path, self._revoked)
        self.clear_recovery(peer_id)

    def is_revoked(self, peer_id: PeerId | str) -> bool:
        return str(peer_id) in self._revoked

    def forget(self, peer_id: PeerId | str) -> None:
        key = str(peer_id)
        self._trusted.pop(key, None)
        self._revoked.pop(key, None)
        self._preferences.pop(key, None)
        self._atomic_write(self._trusted_path, self._trusted)
        self._atomic_write(self._revoked_path, self._revoked)
        self._atomic_write(self._preferences_path, self._preferences)

    def set_recovery_capabilities(
        self, peer_id: PeerId | str, capabilities: Iterable[Capability]
    ) -> None:
        normalized = sorted({Capability(capability).value for capability in capabilities})
        self._preferences[str(peer_id)] = normalized
        self._atomic_write(self._preferences_path, self._preferences)

    def get_recovery_capabilities(self, peer_id: PeerId | str) -> set[Capability]:
        values = self._preferences.get(str(peer_id), [])
        if not isinstance(values, list):
            raise TrustStoreError(f"invalid capability preferences for peer {peer_id}")
        try:
            return {Capability(value) for value in values}
        except (TypeError, ValueError) as exc:
            raise TrustStoreError(f"invalid capability preferences for peer {peer_id}") from exc

    def clear_recovery(self, peer_id: PeerId | str) -> None:
        if str(peer_id) in self._preferences:
            self._preferences.pop(str(peer_id), None)
            self._atomic_write(self._preferences_path, self._preferences)

    def _read_mapping(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise TrustStoreError(f"cannot read {path}") from exc
        if not isinstance(value, dict):
            raise TrustStoreError(f"{path} must contain a JSON object")
        return value

    @staticmethod
    def _atomic_write(path: Path, value: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        except Exception:
            try:
                os.unlink(temporary)
            except OSError:
                pass
            raise

