"""Localization and map presentation methods extracted from the experiment page."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Mapping, cast

from auto_modules.ui.widgets.aspect_preview import AspectPreviewLabel
from auto_modules.features.poe2.live_terrain.orientation import TerrainOrientation
from auto_modules.ui.modes.poe2_live_terrain.presenter import (
    build_localization_presentation,
    localization_display_point,
    localization_source_point,
    prepare_localization_map,
    present_localization_overlay,
    present_player_position_overlay,
    terrain_pixmap,
)


class Poe2LocalizationMixin:
    def _render_dual_first_frame_result(self, result: Any, snapshot: Any, *, render_map: bool = True) -> None:
        diagnostics = dict(getattr(result, "diagnostics", {}) or {})
        read_count = self._dual_first_frame_read_count
        details = [
            f"双人首帧：{result.status} | {result.reason} | 内存读取 {read_count} 次",
            f"候选 {diagnostics.get('candidate_count', 0)} | 配对 {diagnostics.get('evaluated_assignment_count', 0)}",
        ]
        for identity, player in getattr(result, "players", {}).items():
            details.append(
                f"{identity}: screen=({player.screen_position[0]:.1f}, {player.screen_position[1]:.1f}) "
                f"map=({player.mapped_position[0]:.1f}, {player.mapped_position[1]:.1f}) "
                f"误差 {player.anchor_error:.2f} | 置信度 {player.confidence:.3f}"
            )
        registration = getattr(result, "primary_registration", None)
        transform = getattr(registration, "transform", None)
        if transform is not None:
            details.append(
                f"方向 {transform.angle_degrees:.1f}°"
                f"{'，水平镜像' if transform.reflect_horizontal else ''} | 比例 {transform.scale:.3f}"
            )
        registration_diagnostics = dict(getattr(registration, "diagnostics", {}) or {})
        if registration_diagnostics:
            joint = diagnostics.get("joint_initialization", {})
            details.append(
                f"共同墙体覆盖率 {float(registration_diagnostics.get('joint_shape_coverage', registration_diagnostics.get('best_forward_coverage', 0.0))):.3f}"
                f" | 配对误差 {float(joint.get('registration_pair_distance_error', 0.0)):.2f}"
            )
            if joint:
                details.append(
                    f"配对模式 {joint.get('pair_mode', 'unknown')}"
                    f" | 屏幕基线 {float(joint.get('screen_baseline', 0.0)):.2f}"
                    f" | 网格基线 {float(joint.get('native_baseline', 0.0)):.2f}"
                )
        self.dual_first_frame_status_label.setText("\n".join(details))
        if not render_map:
            return
        base = terrain_pixmap(snapshot, self._map_orientation())
        transform = getattr(registration, "transform", None)
        overlay = prepare_localization_map(base, transform)
        source_size = (base.width(), base.height())
        for player in getattr(result, "players", {}).values():
            display_point = localization_display_point(
                player.mapped_position,
                source_size=source_size,
                transform=transform,
            )
            overlay = present_player_position_overlay(
                overlay,
                cast("PlayerPositionSample", SimpleNamespace(grid=display_point)),
                source_shape=(overlay.height(), overlay.width()),
                orientation=None,
            )
        self.map_widget.set_image(overlay)
        players = tuple(getattr(result, "players", {}).values())
        if players:
            self.map_widget.focus_on_point(
                localization_display_point(
                    players[0].mapped_position,
                    source_size=source_size,
                    transform=transform,
                ),
                zoom_multiplier=self.map_follow_zoom_multiplier,
            )

    def start_hybrid_localization(self) -> None:
        if self._snapshot is None:
            self._show_error(RuntimeError("请先获取当前地图"))
            return
        if self.hybrid_localization_factory is None:
            self._show_error(RuntimeError("混合定位实验工厂未注入"))
            return
        self.stop_dual_motion()
        self.stop_hybrid_localization()
        self.stop_multiframe_localization()
        self.stop_preview()
        self._dual_preview_active = False
        if self.capture_monitor_window is not None:
            stop_monitoring = getattr(self.capture_monitor_window, "stop_monitoring", None)
            if callable(stop_monitoring):
                stop_monitoring()
        try:
            experiment = self.hybrid_localization_factory(
                self._snapshot,
                lambda: self.monitor_config,
            )
            experiment.session.add_listener(self.handle_hybrid_state)
            experiment.session.start()
            self._hybrid_experiment = experiment
            self.hybrid_timer.setInterval(self._localization_interval())
            self.hybrid_timer.start()
            self._tick_hybrid_localization()
        except Exception as exc:
            self.hybrid_timer.stop()
            self._hybrid_experiment = None
            self._logger.exception("step=hybrid.start_failed error=%s", exc)
            self._show_error(exc)
            return
        self.start_hybrid_button.setEnabled(False)
        self.stop_hybrid_button.setEnabled(True)
        self.start_single_frame_button.setEnabled(False)
        self.stop_single_frame_button.setEnabled(True)
        self._logger.info("step=hybrid.started interval_ms=%s", self.hybrid_timer.interval())

    def start_multiframe_localization(self) -> None:
        if self._snapshot is None or self.multiframe_localization_factory is None:
            self._show_error(RuntimeError("请先获取地图并注入多帧实验工厂"))
            return
        binding = getattr(self.monitor_config, "binding", None)
        if binding is None:
            self._show_error(RuntimeError("请先配置 PoE2 小地图监控区域"))
            self._logger.warning("step=multiframe.start_rejected reason=missing_monitor_binding")
            return
        self.stop_dual_motion()
        self.stop_multiframe_localization()
        # The preview and detached monitor use the same capture/recognizer
        # resources.  Keep one sampling loop active for deterministic timing.
        self.stop_preview()
        self._dual_preview_active = False
        if self.capture_monitor_window is not None:
            stop_monitoring = getattr(self.capture_monitor_window, "stop_monitoring", None)
            if callable(stop_monitoring):
                stop_monitoring()
        experiment = None
        try:
            experiment = self.multiframe_localization_factory(self._snapshot, lambda: self.monitor_config)
            strategy_a, strategy_b = self.multiframe_panel.selected_strategies()
            experiment.coordinator.set_strategies_enabled(strategy_a=strategy_a, strategy_b=strategy_b)
            experiment.session.start()
            self._multiframe_experiment = experiment
            self._multiframe_trajectory.clear()
            self._multiframe_trajectory_version = 0
            self._multiframe_timer.setInterval(self._localization_interval())
            self._multiframe_timer.start()
            self._tick_multiframe()
        except Exception as exc:
            self._multiframe_timer.stop()
            if experiment is not None:
                close = getattr(experiment.session, "close", None)
                if callable(close):
                    close()
            self._multiframe_experiment = None
            self.multiframe_panel.set_running(False)
            self.multiframe_panel.set_archive_available(False)
            self._logger.exception("step=multiframe.start_failed error=%s", exc)
            self._show_error(exc)
            return
        self.start_multiframe_button.setEnabled(False)
        self.stop_multiframe_button.setEnabled(True)
        self.multiframe_panel.set_running(True)
        self.multiframe_panel.set_archive_available(False)
        self._logger.info("step=multiframe.started interval_ms=%s", self._multiframe_timer.interval())

    def stop_multiframe_localization(self) -> None:
        self._multiframe_timer.stop()
        experiment = self._multiframe_experiment
        if experiment is not None:
            close = getattr(experiment.session, "close", None)
            if callable(close):
                close()
            else:
                experiment.session.stop()
        self._multiframe_experiment = None
        self._last_multiframe_state = None
        self._multiframe_trajectory.clear()
        self._multiframe_trajectory_version = 0
        self.start_multiframe_button.setEnabled(self.multiframe_localization_factory is not None and self._snapshot is not None)
        self.stop_multiframe_button.setEnabled(False)
        self.multiframe_panel.set_running(False)
        self.multiframe_panel.set_archive_available(False)

    def reset_multiframe_localization(self) -> None:
        self.stop_multiframe_localization()
        self._multiframe_experiment = None
        self._last_multiframe_state = None
        self._multiframe_trajectory.clear()
        self._multiframe_trajectory_version = 0
        self.multiframe_status_label.setText("多帧定位：未启动")
        self.multiframe_position_label.setText("多帧位置：暂无")
        self.multiframe_panel.set_submap(None)
        self.multiframe_panel.set_archive_available(False)

    def save_multiframe_experiment(self) -> None:
        experiment = self._multiframe_experiment
        if experiment is None:
            self._show_error(RuntimeError("多帧定位实验尚未启动"))
            return
        if not self._multiframe_archive_ready():
            self._show_error(RuntimeError("多帧实验尚未形成可归档的锚点、参考地图和证据"))
            return
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
        target = Path("data/poe2_live_terrain_test/multiframe_sessions") / timestamp
        try:
            saved = experiment.archive.save(
                target,
                evidence=experiment.window.snapshot(),
                anchor=experiment.coordinator.anchor,
                instance_id=experiment.coordinator.instance_id,
                reference=experiment.coordinator.reference,
                estimate=self._last_multiframe_state,
                diagnostics={
                    "recovery_revision": experiment.coordinator.recovery_revision,
                    "memory_read_count": int(getattr(experiment.anchor_provider, "read_count", 0)),
                    "phase": experiment.coordinator.phase.value,
                },
            )
        except Exception as exc:
            self._logger.exception("step=multiframe.archive_failed error=%s", exc)
            self._show_error(exc)
            return
        self._logger.info("step=multiframe.archive_saved path=%s", saved)
        self.multiframe_status_label.setText(f"多帧实验已保存：{saved}")

    def _multiframe_archive_ready(self) -> bool:
        experiment = self._multiframe_experiment
        if experiment is None:
            return False
        coordinator = getattr(experiment, "coordinator", None)
        window = getattr(experiment, "window", None)
        return bool(
            getattr(coordinator, "anchor", None) is not None
            and getattr(coordinator, "reference", None) is not None
            and window is not None
            and tuple(window.snapshot())
        )

    def _tick_multiframe(self) -> None:
        experiment = self._multiframe_experiment
        if experiment is None:
            return
        try:
            state = experiment.session.tick()
        except Exception as exc:
            self._logger.exception("step=multiframe.tick_failed error=%s", exc)
            self.stop_multiframe_localization()
            self._show_error(exc)
            return
        self._last_multiframe_state = state
        candidates = tuple(getattr(state, "candidate_regions", ()) or ())
        keyframes = len(experiment.window.snapshot())
        reads = int(getattr(experiment.anchor_provider, "read_count", 0))
        evidence_bytes = int(getattr(experiment.window, "estimated_bytes", 0))
        registration_version = int(getattr(state, "registration_version", 0))
        if registration_version != self._multiframe_trajectory_version:
            self._multiframe_trajectory.clear()
            self._multiframe_trajectory_version = registration_version
        if state.position is not None and state.fresh:
            self._multiframe_trajectory.append(tuple(state.position))
            self._multiframe_trajectory = self._multiframe_trajectory[-200:]
        self.multiframe_status_label.setText(
            f"多帧定位：{state.status} | evidence {state.evidence_version} | "
            f"候选 {len(candidates)} | 关键帧 {keyframes} | 内存读取 {reads} | "
            f"恢复版本 {experiment.coordinator.recovery_revision} | {state.reason}"
        )
        self.multiframe_position_label.setText(f"多帧位置：{state.position if state.position is not None else '暂无'}")
        self.multiframe_panel.set_state(
            status=state.status,
            evidence_version=state.evidence_version,
            recovery_revision=experiment.coordinator.recovery_revision,
            reason=state.reason,
            position=state.position,
            keyframes=keyframes,
            candidates=len(candidates),
            memory_reads=reads,
            registration_pending=experiment.session.registration_pending,
            strategy_a_status=getattr(experiment.coordinator.last_strategy_a_result, "status", None),
            best_candidate=getattr(experiment.coordinator.last_strategy_b_result, "best", None),
            evidence_bytes=evidence_bytes,
            tick_elapsed_ms=float(getattr(experiment.session, "last_tick_elapsed_ms", 0.0)),
            registration_elapsed_ms=float(getattr(experiment.session, "last_registration_elapsed_ms", 0.0)),
        )
        submap = experiment.submap.rebuild(experiment.window.snapshot())
        self.multiframe_panel.set_submap(submap.wall_mask)
        self.multiframe_panel.set_archive_available(self._multiframe_archive_ready())
        if self._snapshot is not None:
            native_pixmap = terrain_pixmap(self._snapshot)
            overlay_state = build_localization_presentation(
                state,
                registration=experiment.coordinator.registration,
                coordinator_registration_version=int(
                    getattr(experiment.coordinator, "registration_version", registration_version)
                ),
                trajectory=self._multiframe_trajectory,
                candidates=candidates,
            )
            overlay = present_localization_overlay(native_pixmap, overlay_state)
            self.map_widget.set_image(overlay)
            self._focus_map_on_state(overlay_state, source_size=native_pixmap.size())
            transform = getattr(experiment.coordinator.registration, "transform", None)
            lines = [line for line in self.metadata_label.text().splitlines() if not line.startswith("方向：")]
            if transform is not None and overlay_state.registration is not None:
                lines.append(
                    f"方向：多帧自动校准 {float(transform.angle_degrees):.1f}°"
                    f"{'，水平镜像' if transform.reflect_horizontal else ''}"
                )
            else:
                lines.append("方向：等待自动校准（native）")
            self.metadata_label.setText("\n".join(lines))
        self._logger.info(
            "step=multiframe.state phase=%s status=%s source=%s position=%s evidence=%s keyframes=%s evidence_bytes=%s candidates=%s reads=%s pending=%s tick_ms=%.2f registration_ms=%.2f reason=%s diagnostics=%s",
            experiment.coordinator.phase.value,
            state.status,
            state.source,
            state.position,
            state.evidence_version,
            keyframes,
            evidence_bytes,
            len(candidates),
            reads,
            experiment.session.registration_pending,
            float(getattr(experiment.session, "last_tick_elapsed_ms", 0.0)),
            float(getattr(experiment.session, "last_registration_elapsed_ms", 0.0)),
            state.reason,
            dict(getattr(state, "diagnostics", {}) or {}),
        )

    def stop_hybrid_localization(self) -> None:
        self.hybrid_timer.stop()
        experiment = self._hybrid_experiment
        if experiment is not None:
            experiment.session.stop()
        self.start_hybrid_button.setEnabled(
            self.hybrid_localization_factory is not None and self._snapshot is not None
        )
        self.stop_hybrid_button.setEnabled(False)
        self.retry_hybrid_button.setEnabled(False)
        self.stop_single_frame_button.setEnabled(False)
        self.start_single_frame_button.setEnabled(
            self.hybrid_localization_factory is not None and self._snapshot is not None
        )

    def retry_hybrid_recovery(self) -> None:
        if self._hybrid_experiment is None:
            self._show_error(RuntimeError("混合定位尚未启动"))
            return
        try:
            self._hybrid_experiment.session.retry_recovery()
        except Exception as exc:
            self._logger.exception("step=hybrid.retry_failed error=%s", exc)
            self._show_error(exc)
            return
        self.retry_hybrid_button.setEnabled(False)
        self.hybrid_status_label.setText("混合定位：已允许单次恢复，等待下一帧")
        self._logger.info("step=hybrid.retry_requested")

    def _tick_hybrid_localization(self) -> None:
        if self._hybrid_experiment is None:
            return
        try:
            self._hybrid_experiment.session.tick()
        except Exception as exc:
            self.hybrid_timer.stop()
            self.stop_hybrid_button.setEnabled(False)
            self.start_hybrid_button.setEnabled(self._snapshot is not None)
            self._logger.exception("step=hybrid.tick_failed error=%s", exc)
            self._show_error(exc)

    def _hybrid_read_count(self) -> int:
        provider = getattr(self._hybrid_experiment, "anchor_provider", None)
        return int(getattr(provider, "read_count", 0))

    def _map_orientation(self) -> TerrainOrientation:
        return TerrainOrientation()

    def handle_hybrid_state(self, state: Any) -> None:
        self._last_hybrid_state = state
        mode = getattr(getattr(state, "mode", "unknown"), "value", getattr(state, "mode", "unknown"))
        source = str(getattr(state, "source", "failed"))
        confidence = float(getattr(state, "confidence", 0.0))
        revision = int(getattr(state, "recovery_revision", 0))
        reason = str(getattr(state, "reason", "") or "")
        reads = self._hybrid_read_count()
        details = (
            f"混合定位：{mode} | 来源 {source} | 置信度 {confidence:.3f} | "
            f"内存读取 {reads} 次 | 恢复版本 {revision}"
        )
        if reason:
            details += f" | {reason}"
        diagnostics = getattr(state, "diagnostics", {})
        if isinstance(diagnostics, Mapping):
            registration_reason = str(diagnostics.get("reason", "") or "")
            if registration_reason and registration_reason != reason:
                details += f" | {registration_reason}"
            numeric_details = (
                ("best_score", "候选分", 3),
                ("best_forward_coverage", "覆盖", 3),
                ("best_angle", "角度", 1),
                ("best_scale", "比例", 3),
                ("best_anchor_error", "锚点误差", 2),
            )
            for key, label, precision in numeric_details:
                value = diagnostics.get(key)
                if isinstance(value, (int, float)):
                    suffix = "°" if key == "best_angle" else ""
                    details += f" | {label} {float(value):.{precision}f}{suffix}"
        self.hybrid_status_label.setText(details)
        self.single_frame_status_label.setText(details.replace("混合定位：", "首帧定位：", 1))
        position = getattr(state, "position", None)
        if position is None:
            self.hybrid_position_label.setText("实时位置：本帧无可信位置")
        else:
            self.hybrid_position_label.setText(
                f"实时位置：({float(position[0]):.2f}, {float(position[1]):.2f})"
            )
        mode_name = str(mode)
        self.retry_hybrid_button.setEnabled(mode_name == "recovery_required")
        if self._terrain_base_pixmap is not None:
            base_pixmap = self._terrain_base_pixmap
            overlay = present_localization_overlay(base_pixmap, state)
            self.map_widget.set_image(overlay)
            self._focus_map_on_state(state, source_size=base_pixmap.size())
        transform = getattr(getattr(state, "registration", None), "transform", None)
        if transform is not None:
            lines = [
                line for line in self.metadata_label.text().splitlines()
                if not line.startswith("方向：")
            ]
            lines.append(
                f"方向：自动校准 {float(transform.angle_degrees):.1f}°"
                f"{'，水平镜像' if transform.reflect_horizontal else ''}"
            )
            self.metadata_label.setText("\n".join(lines))
        if self.capture_monitor_window is not None:
            self.capture_monitor_window.handle_hybrid_state(state, read_count=reads)
        self._logger.info(
            "step=hybrid.state mode=%s source=%s confidence=%.3f position=%s reads=%s revision=%s reason=%s diagnostics=%s",
            mode,
            source,
            confidence,
            position,
            reads,
            revision,
            reason,
            dict(diagnostics) if isinstance(diagnostics, Mapping) else {},
        )

    def _focus_map_on_state(self, state: Any, *, source_size) -> None:
        position = getattr(state, "position", None)
        if position is None:
            position = getattr(state, "latest_confirmed_position", None)
        if position is None:
            return
        registration = getattr(state, "registration", None)
        transform = getattr(registration, "transform", None)
        point = localization_display_point(
            position,
            source_size=(source_size.width(), source_size.height()),
            transform=transform,
        )
        self.map_widget.focus_on_point(
            point,
            zoom_multiplier=self.map_follow_zoom_multiplier,
        )
