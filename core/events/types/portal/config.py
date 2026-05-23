from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PortalEventConfig:
    enabled: bool = True
    priority: int = 100
    interaction: str = "key"
    minimap_threshold: float = 0.74
    max_candidates: int = 2
    min_blue_ratio: float = 0.08
    stable_frames: int = 3
    localization_cluster_radius: int = 56
    stable_variance: float = 1600.0
    dedupe_radius: int = 32
    localization_max_samples: int = 12
    localization_cluster_ttl_ms: int = 12000
    memory_confirm_frames: int = 1
    arrival_radius: int = 80
    interact_radius: int = 36
    retry_limit: int = 2
    cooldown_ms: int = 120000
    cooldown_radius: int = 260
    exit_complete_radius: int = 120
    type_cooldown_ms: int = 10000
    click_wait_ms: int = 1200
    confirm_timeout_ms: int = 2500
    portal_point_click_wait_ms: int = 350
    post_interact_wait_ms: int = 800
    teleport_timeout_ms: int = 6000
    teleport_min_distance: int = 180
    environment_change_threshold: float = 0.18

    @classmethod
    def from_dict(cls, data: dict | None):
        values = data or {}
        return cls(
            enabled=bool(values.get("enabled", True)),
            priority=int(values.get("priority", 100)),
            interaction=str(values.get("interaction", "key")),
            minimap_threshold=float(values.get("minimap_threshold", 0.74)),
            max_candidates=int(values.get("max_candidates", 2)),
            min_blue_ratio=float(values.get("min_blue_ratio", 0.08)),
            stable_frames=int(values.get("stable_frames", values.get("confirm_frames", 3))),
            localization_cluster_radius=int(values.get("localization_cluster_radius", 56)),
            stable_variance=float(values.get("stable_variance", 1600.0)),
            dedupe_radius=int(values.get("dedupe_radius", 32)),
            localization_max_samples=int(values.get("localization_max_samples", 12)),
            localization_cluster_ttl_ms=int(values.get("localization_cluster_ttl_ms", 12000)),
            memory_confirm_frames=int(values.get("memory_confirm_frames", 1)),
            arrival_radius=int(values.get("arrival_radius", 80)),
            interact_radius=int(values.get("interact_radius", 36)),
            retry_limit=int(values.get("retry_limit", 2)),
            cooldown_ms=int(values.get("cooldown_ms", 120000)),
            cooldown_radius=int(values.get("cooldown_radius", 260)),
            exit_complete_radius=int(values.get("exit_complete_radius", 120)),
            type_cooldown_ms=int(values.get("type_cooldown_ms", 10000)),
            click_wait_ms=int(values.get("click_wait_ms", 1200)),
            confirm_timeout_ms=int(values.get("confirm_timeout_ms", 2500)),
            portal_point_click_wait_ms=int(values.get("portal_point_click_wait_ms", 350)),
            post_interact_wait_ms=int(values.get("post_interact_wait_ms", 800)),
            teleport_timeout_ms=int(values.get("teleport_timeout_ms", 6000)),
            teleport_min_distance=int(values.get("teleport_min_distance", 180)),
            environment_change_threshold=float(values.get("environment_change_threshold", 0.18)),
        )

    def to_dict(self) -> dict:
        return dict(self.__dict__)
