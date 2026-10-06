"""Movement probe and dual-target methods extracted from the experiment page."""

from __future__ import annotations

import math
import time
from types import SimpleNamespace
from typing import Any, Mapping

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QMessageBox

from auto_modules.adapters.windows import find_process_window, is_process_foreground
from auto_modules.core.routing.geometry import point_distance
from auto_modules.core.localization.displacement import inverse_transform_local_displacement
from auto_modules.features.poe2.live_terrain.experimental.multiplayer_follow import (
    ClosedLoopMotionController,
    ControlMode,
    FollowState,
    MapIdentity,
    PositionSample,
    ProgramFollowOutput,
    RoleId,
    SimulatedFollowRuntime,
)
from auto_modules.features.poe2.live_terrain.experimental.multiplayer_localization import (
    inspect_minimap_contact,
)
from auto_modules.features.poe2.live_terrain.movement import native_route_vector_for_program_output
from auto_modules.features.poe2.live_terrain.player_position import find_process_id
from auto_modules.ui.modes.poe2_live_terrain.presenter import localization_display_point


class Poe2ProbeMixin:
    def start_program_move_probe(self) -> None:
        """Arm a standalone map-point movement test; no input is sent yet."""
        self._experiment_composition.move_probe.arm()
        self.stop_dual_target_experiment()
        if self._program_probe_timer.isActive() or self._program_probe_waiting_click:
            return
        if self.program_output_factory is None:
            self.program_probe_status_label.setText("程序移动实验：虚拟手柄输出未绑定")
            return
        if self._latest_dual_state is None or self._dual_follow_reference is None:
            self.program_probe_status_label.setText("程序移动实验：请先完成双人首帧和实时定位")
            return
        identity = self.program_probe_role_combo.currentData()
        if not identity:
            self.program_probe_status_label.setText("程序移动实验：请选择要移动的角色")
            return
        self.stop_follow_experiment()
        self._program_probe_waiting_click = True
        # A new user-armed movement experiment starts a fresh recovery budget;
        # an automatic resume keeps the previous timestamp for cooldown.
        self._program_probe_last_relocalization_at_ms = None
        self.program_probe_button.setEnabled(False)
        self.program_probe_stop_button.setEnabled(True)
        self.program_probe_status_label.setText(
            "已准备，不会立即发送输入；请在左侧大地图点击一个目标位置"
        )
        self._logger.info(
            "step=program_probe.armed_waiting_click role=%s controller=%s",
            identity,
            self.program_probe_controller_combo.currentData(),
        )

    def _start_program_move_probe_at(
        self, point: tuple[float, float], *, _confirmed: bool = False
    ) -> None:
        if not self._program_probe_waiting_click and not _confirmed:
            return
        identity = str(self.program_probe_role_combo.currentData() or "")
        state = self._latest_dual_state
        reference = self._dual_follow_reference
        if not identity or state is None or reference is None:
            self._logger.warning(
                "step=program_probe.start_rejected reason=missing_context role=%s "
                "has_state=%s has_reference=%s",
                identity or None,
                state is not None,
                reference is not None,
            )
            self.stop_program_move_probe()
            return
        current = state.players.get(identity)
        if current is None:
            self._logger.warning(
                "step=program_probe.start_rejected reason=missing_player_position role=%s",
                identity,
            )
            self.program_probe_status_label.setText("程序移动实验：所选角色当前没有可信位置")
            return
        if not _confirmed:
            answer = QMessageBox.question(
                self,
                "确认发送真实手柄输入",
                "确认后等待 10 秒切回 PoE2，再持续控制选定角色向地图目标移动；"
                "到达、阻塞、失焦或点击停止时会自动中性并释放。\n"
                "请确认游戏已打开、虚拟手柄已连接，并准备好管理员权限。",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                self._logger.info("step=program_probe.cancelled_by_user")
                self.program_probe_status_label.setText("已取消真实输入确认，仍可重新点击目标")
                return
            self._program_probe_pending_point = point
            self._program_probe_waiting_click = False
            self.program_probe_status_label.setText("已确认，10 秒内切回 PoE2；尚未发送输入")
            self._logger.info("step=program_probe.waiting_game_foreground seconds=10")
            self._program_probe_arm_timer.start(10_000)
            return
        point = self._program_probe_pending_point or point
        self._program_probe_pending_point = None
        try:
            game_pid = int(find_process_id())
            game_window = find_process_window(game_pid, title_substring="Path of Exile 2")
        except Exception as exc:
            self._logger.exception("step=program_probe.window_lookup_failed")
            self.stop_program_move_probe(reason=f"无法获取 PoE2 窗口：{exc}")
            return
        if game_window is None:
            self.stop_program_move_probe(reason="未找到 PoE2 可见窗口，未发送输入")
            return
        if not is_process_foreground(game_pid):
            self.stop_program_move_probe(reason="PoE2 当前不在前台，未发送输入")
            return
        self._program_probe_game_pid = game_pid
        self._program_probe_game_hwnd = game_window.hwnd
        self._program_probe_started_at_ms = int(time.time() * 1000)
        self._logger.info(
            "step=program_probe.window_ready pid=%s hwnd=%s title=%s",
            game_pid, game_window.hwnd, game_window.title,
        )
        map_identity = MapIdentity(
            str(self._snapshot.metadata.area_id),
            str(self._snapshot.metadata.instance_id),
        )
        role = RoleId("local-device", identity)
        runtime = SimulatedFollowRuntime(
            wall_map=reference.wall_layer,
            map_identity=map_identity,
            arrival_radius=8.0,
            speed_units_per_second=80.0,
            position_ttl_ms=self._FOLLOW_RUNTIME_MAX_FRAME_AGE_MS,
            downsample_factor=8,
            # The actor footprint is the hard body clearance. Keep the
            # downsample safety margin small so narrow doors are not inflated
            # twice into impossible walls.
            safety_margin=0,
            clearance_radius=20.0,
            clearance_weight=2.0,
            dead_end_weight=0.75,
            minimum_clearance=0.0,
            footprint_radius=0.0,
            inflate_collision=False,
            stalled_ticks=8,
            # Two visual samples can straddle a doorway transition. Require a
            # longer contact window before escalating to a memory re-anchor.
            contact_required_samples=4,
            local_lookahead=24.0,
            prediction_horizon=0.25,
            closed_loop_controller=ClosedLoopMotionController(
                expected_speed=80.0,
                arrival_radius=8.0,
                max_frame_age_ms=self._FOLLOW_RUNTIME_MAX_FRAME_AGE_MS,
            ),
        )
        now_ms = int(time.time() * 1000)
        runtime.add_follower(
            role,
            PositionSample(role, map_identity, current, now_ms, 1.0, "visual"),
            mode=ControlMode.PROGRAM,
        )
        runtime.set_simulated_target(point, now_ms=now_ms)
        self._program_probe_initial_position = tuple(float(value) for value in current)
        self._program_probe_last_position = self._program_probe_initial_position
        self._program_probe_target = tuple(float(value) for value in point)
        self._program_probe_last_observation = None
        self._logger.info(
            "step=program_probe.plan_context map_id=%s map_version=%s role=%s "
            "controller=%s start_native=%s target_native=%s target_display=%s "
            "transform_angle=%s transform_reflect=%s transform_scale=%s transform_translation=%s "
            "wall_shape=%s wall_pixels=%s downsample=%s arrival_radius=%s speed_units_per_second=%s "
            "position_ttl_ms=%s safety_margin=%s clearance_radius=%s clearance_weight=%s "
            "dead_end_weight=%s minimum_clearance=%s footprint_radius=%s collision_inflation=%s",
            map_identity.map_id,
            map_identity.map_version,
            identity,
            self.program_probe_controller_combo.currentData(),
            self._program_probe_initial_position,
            self._program_probe_target,
            self._clicked_target_display,
            getattr(self._dual_map_transform, "angle_degrees", None),
            getattr(self._dual_map_transform, "reflect_horizontal", None),
            getattr(self._dual_map_transform, "scale", None),
            getattr(self._dual_map_transform, "translation", None),
            tuple(int(value) for value in reference.wall_layer.shape),
            int((reference.wall_layer > 0).sum()),
            8,
            8.0,
            80.0,
            self._FOLLOW_RUNTIME_MAX_FRAME_AGE_MS,
            0,
            20.0,
            2.0,
            0.75,
            0.0,
            0.0,
            False,
        )
        controller = int(self.program_probe_controller_combo.currentData() or 1)
        output = None
        try:
            output = self.program_output_factory(controller)
            self._program_probe_output = ProgramFollowOutput(
                {role: output}, vector_transform=self._native_route_vector_for_input,
            )
            self._program_probe_output.arm(role)
            self._program_probe_role = role
            self._program_probe_runtime = runtime
            self._program_probe_controller = controller
            self._program_probe_ticks = 0
            self._program_probe_waiting_click = False
            self._program_probe_timer.start()
            self.program_probe_status_label.setText(
                f"控制器 {controller} 已取得租约，持续移动到 ({point[0]:.1f}, {point[1]:.1f})"
            )
            self._logger.info(
                "step=program_probe.acquire_success role=%s controller=%s target=%s",
                role.key,
                controller,
                point,
            )
            self._log_program_probe_diagnostics("acquired")
        except Exception as exc:
            if output is not None:
                try:
                    output.close()
                except Exception:
                    self._logger.exception("step=program_probe.cleanup_failed")
            self._program_probe_output = None
            self.program_probe_status_label.setText(f"程序移动实验失败：{exc}")
            self._logger.exception("step=program_probe.start_failed error=%s", exc)

    def _arm_program_move_probe(self) -> None:
        point = self._program_probe_pending_point
        if point is None:
            return
        self._start_program_move_probe_at(point, _confirmed=True)

    def _tick_program_move_probe(self) -> None:
        output = self._program_probe_output
        runtime = self._program_probe_runtime
        role = self._program_probe_role
        if output is None or runtime is None or role is None:
            self.stop_program_move_probe()
            return
        try:
            now_ms = int(time.time() * 1000)
            if self._program_probe_game_pid is None or not is_process_foreground(
                self._program_probe_game_pid
            ):
                self.stop_program_move_probe(reason="PoE2 已失去前台，已停止真实输入")
                return
            # A map run has no total-duration policy.  A long route remains
            # active until it reaches its target or an explicit operational
            # boundary occurs (foreground loss, map/relocalization failure,
            # user stop, or page shutdown).  Frame freshness and Host command
            # TTLs below are per-observation safety contracts; they are not a
            # wall-clock limit on completing the map.
            state = self._latest_dual_state
            if state is None:
                self.stop_program_move_probe(reason="人物位置暂时不可用，已停止")
                return
            current_position = state.players.get(role.actor_id)
            if current_position is None:
                if getattr(state, "recovery_requested", False):
                    previous = self._program_probe_last_observation
                    target = self._program_probe_target or getattr(
                        previous, "target_position", None
                    )
                    self._request_program_probe_relocalization(
                        target,
                        reason="视觉 marker 连续丢失，开始内存锚点重定位",
                        diagnostics={"tracker_reason": getattr(state, "reason", None)},
                    )
                else:
                    self.stop_program_move_probe(reason="人物位置暂时不可用，已停止")
                return
            if (
                self._latest_dual_captured_at_ms is None
                or now_ms - self._latest_dual_captured_at_ms > self._FOLLOW_RUNTIME_MAX_FRAME_AGE_MS
            ):
                self.stop_program_move_probe(reason="视觉定位帧已过期，已停止真实输入")
                return
            # Preserve the capture timestamp.  Reusing ``now_ms`` here would
            # make a frozen visual frame look fresh on every control tick and
            # defeat the runtime's stale-position fail-safe.  The control
            # loop may run faster than the visual worker, so freshness must be
            # measured from the last actual capture.
            visual_captured_at_ms = int(self._latest_dual_captured_at_ms)
            runtime.update_follower_position(
                PositionSample(
                    role,
                    runtime.map_identity,
                    state.players[role.actor_id],
                    visual_captured_at_ms,
                    1.0,
                    "visual",
                )
            )
            runtime.refresh_simulated_target(now_ms=now_ms)
            observation = runtime.tick(now_ms=now_ms)[role.key]
            output.apply(observation, elapsed_ms=50)
            self._update_program_probe_local_contact(state, role, observation)
            self._program_probe_ticks += 1
            self._program_probe_last_observation = observation
            if observation.position is not None:
                self._program_probe_last_position = tuple(observation.position)
            self._render_program_probe_overlay(observation)
            try:
                input_vector = self._native_route_vector_for_input(observation.vector)
            except Exception as transform_error:
                input_vector = None
                self._logger.warning(
                    "step=program_probe.vector_transform_failed tick=%s error=%s",
                    self._program_probe_ticks,
                    transform_error,
                )
            visual_age_ms = (
                None
                if self._latest_dual_captured_at_ms is None
                else max(0, now_ms - self._latest_dual_captured_at_ms)
            )
            self._logger.info(
                "step=program_probe.motion tick=%s coordinate_space=reference_native "
                "current=%s target=%s distance=%s route_length=%s route_detour_ratio=%s "
                "route_points=%s route_end=%s vector_native=%s vector_input=%s "
                "route_chain_points=%s route_collision_segments=%s route_walkable=%s "
                "plan_attempted_factors=%s plan_accepted_factor=%s "
                "plan_candidate_route_count=%s plan_relaxed_candidate_route_count=%s "
                "plan_selected_clearance_mode=%s plan_rejections=%s "
                "plan_start_metrics=%s plan_target_metrics=%s "
                "plan_selected_route_score=%s "
                "plan_selected_route_length=%s "
                "plan_selected_route_minimum_clearance=%s "
                "route_target_shift=%s route_deviation=%s "
                "safety_margin=%s clearance_radius=%s clearance_weight=%s "
                 "dead_end_weight=%s minimum_clearance=%s footprint_radius=%s "
                 "no_progress_ticks=%s direction_mismatch_ticks=%s "
                 "command_observed_alignment=%s command_observed_angle_degrees=%s "
                 "recovery_attempts=%s recovery_candidates_checked=%s "
                 "recovery_selected_index=%s recovery_target=%s "
                "observed_velocity=%s observed_speed=%s local_controller=%s "
                "observed_displacement=%s command_duration_ms=%s "
                "contact_evidence=%s local_obstacle_ahead=%s local_obstacle_distance=%s "
                "local_raw_obstacle_ahead=%s local_escape_available=%s "
                "local_free_left=%s local_free_right=%s relocalization_requested=%s "
                "visual_age_ms=%s capture_at_ms=%s reason=%s state=%s",
                self._program_probe_ticks,
                observation.position,
                observation.target_position,
                observation.distance,
                observation.diagnostics.get("route_length", 0.0),
                float(observation.diagnostics.get("route_length", 0.0))
                / max(float(observation.distance or 0.0), 1e-6),
                len(observation.route),
                observation.route[-1] if observation.route else None,
                tuple(round(float(value), 4) for value in observation.vector),
                None if input_vector is None else tuple(round(float(value), 4) for value in input_vector),
                observation.diagnostics.get("route_chain_points", 0),
                observation.diagnostics.get("route_collision_segments", 0),
                observation.diagnostics.get("route_walkable", False),
                observation.diagnostics.get("plan_attempted_factors", ()),
                observation.diagnostics.get("plan_accepted_factor"),
                observation.diagnostics.get("plan_candidate_route_count", 0),
                observation.diagnostics.get("plan_relaxed_candidate_route_count", 0),
                observation.diagnostics.get("plan_selected_clearance_mode"),
                observation.diagnostics.get("plan_rejections", ()),
                observation.diagnostics.get("plan_start_metrics"),
                observation.diagnostics.get("plan_target_metrics"),
                observation.diagnostics.get("plan_selected_route_score"),
                observation.diagnostics.get("plan_selected_route_length"),
                observation.diagnostics.get("plan_selected_route_minimum_clearance"),
                observation.diagnostics.get("route_target_shift"),
                observation.diagnostics.get("route_deviation"),
                observation.diagnostics.get("route_safety_margin", 0),
                observation.diagnostics.get("route_clearance_radius", 0.0),
                observation.diagnostics.get("route_clearance_weight", 0.0),
                 observation.diagnostics.get("route_dead_end_weight", 0.0),
                 observation.diagnostics.get("route_minimum_clearance", 0.0),
                 observation.diagnostics.get("route_footprint_radius", 0.0),
                 observation.diagnostics.get("no_progress_ticks", 0),
                 observation.diagnostics.get("direction_mismatch_ticks", 0),
                 observation.diagnostics.get("command_observed_alignment"),
                 observation.diagnostics.get("command_observed_angle_degrees"),
                 observation.diagnostics.get("recovery_attempts", 0),
                observation.diagnostics.get("recovery_candidates_checked", 0),
                observation.diagnostics.get("recovery_selected_index"),
                observation.diagnostics.get("recovery_target"),
                observation.diagnostics.get("observed_velocity", (0.0, 0.0)),
                observation.diagnostics.get("observed_speed", 0.0),
                observation.diagnostics.get("local_controller", {}),
                observation.diagnostics.get("observed_displacement", 0.0),
                observation.diagnostics.get("command_duration_ms", 0),
                observation.diagnostics.get("contact_evidence"),
                observation.diagnostics.get("local_obstacle_ahead"),
                observation.diagnostics.get("local_obstacle_distance"),
                observation.diagnostics.get("local_raw_obstacle_ahead"),
                observation.diagnostics.get("local_escape_available", False),
                observation.diagnostics.get("local_free_left"),
                observation.diagnostics.get("local_free_right"),
                observation.diagnostics.get("relocalization_requested", False),
                visual_age_ms,
                self._latest_dual_captured_at_ms,
                observation.reason,
                observation.state.value,
            )
            if self._program_probe_ticks == 1 or self._program_probe_ticks % 5 == 0:
                self._log_program_probe_diagnostics(f"tick={self._program_probe_ticks}")
            self.program_probe_status_label.setText(
                f"移动状态：{observation.state.value} | {observation.reason} | "
                f"距离 {observation.distance if observation.distance is not None else '暂无'}"
            )
            if observation.diagnostics.get("relocalization_requested"):
                self._request_program_probe_relocalization(
                    self._program_probe_target or observation.target_position,
                    reason="小地图连续撞墙，开始内存锚点重定位",
                    diagnostics=dict(observation.diagnostics),
                )
                return
            if observation.state.value in {
                "arrived",
                "blocked",
                "waiting_position",
                "map_mismatch",
            }:
                self.stop_program_move_probe(reason=f"移动结束：{observation.reason}")
        except Exception as exc:
            self._logger.exception("step=program_probe.write_failed error=%s", exc)
            self.program_probe_status_label.setText(f"程序移动输出失败：{exc}")
            self.stop_program_move_probe()

    def _update_program_probe_local_contact(self, state: Any, role: RoleId, observation: Any) -> None:
        """Feed the latest minimap wall beam into the generic follow runtime."""
        runtime = self._program_probe_runtime
        if runtime is not None:
            self._update_follow_local_contact(
                runtime, state, role, observation, log_step="program_probe",
            )

    def _update_follow_local_contact(
        self,
        runtime: SimulatedFollowRuntime,
        state: Any,
        role: RoleId,
        observation: Any,
        *,
        log_step: str,
        emit_log: bool = True,
    ) -> None:
        combined = self._latest_dual_combined
        if combined is None or state is None or state.transform is None:
            return
        screen_position = state.screen_positions.get(role.actor_id)
        if screen_position is None:
            return
        wall_mask = combined[0] if isinstance(combined, (tuple, list)) else combined
        try:
            screen_vector = inverse_transform_local_displacement(
                observation.vector,
                angle_degrees=state.transform.angle_degrees,
                reflect_horizontal=state.transform.reflect_horizontal,
                scale=state.transform.scale,
            )
            contact = inspect_minimap_contact(wall_mask, screen_position, screen_vector)
            runtime.update_local_contact(
                role,
                wall_ahead=contact.wall_ahead,
                blocking_wall_ahead=contact.blocking_wall_ahead,
                escape_available=contact.escape_available,
                wall_distance=contact.wall_distance,
                free_left=contact.free_left,
                free_right=contact.free_right,
                captured_at_ms=self._latest_dual_captured_at_ms,
            )
            if emit_log:
                self._logger.info(
                    "step=%s.local_contact role=%s player_screen=%s "
                    "command_screen=%s raw_wall_ahead=%s blocking_wall_ahead=%s "
                    "centerline_wall_distance=%s narrow_passage=%s wall_distance=%s "
                    "escape_available=%s free_left=%.3f free_right=%.3f",
                    log_step,
                    role.key,
                    tuple(round(float(value), 2) for value in screen_position),
                    tuple(round(float(value), 3) for value in screen_vector),
                    contact.wall_ahead,
                    contact.blocking_wall_ahead,
                    contact.centerline_wall_distance,
                    contact.narrow_passage,
                    contact.wall_distance,
                    contact.escape_available,
                    contact.free_left,
                    contact.free_right,
                )
        except Exception as exc:
            # Contact evidence is advisory.  A malformed/temporarily
            # unavailable minimap frame must not be reported as a Host write
            # failure and must not release the active program lease.
            self._logger.warning(
                "step=%s.local_contact_failed error_type=%s error=%s",
                log_step,
                type(exc).__name__,
                exc,
            )

    def _log_program_probe_diagnostics(self, phase: str) -> None:
        output = self._program_probe_output
        if output is None:
            return
        observation = self._program_probe_last_observation
        if observation is not None:
            self._logger.info(
                "step=program_probe.motion_summary phase=%s state=%s reason=%s "
                "policy=%s complexity_state=%s complexity=%s command_id=%s "
                "command_duration_ms=%s calibration_confidence=%s calibration_samples=%s "
                "calibration_speed_gain=%s",
                phase,
                observation.state.value,
                observation.reason,
                observation.diagnostics.get("motion_loop_policy"),
                observation.diagnostics.get("motion_loop_state"),
                observation.diagnostics.get("motion_loop_complexity"),
                observation.diagnostics.get("motion_loop_command_id"),
                observation.diagnostics.get("command_duration_ms"),
                observation.diagnostics.get("calibration_confidence"),
                observation.diagnostics.get("calibration_samples"),
                observation.diagnostics.get("calibration_speed_gain"),
            )
        try:
            diagnostics = output.diagnostics()
            self._logger.info(
                "step=program_probe.host_final_before_release controller=%s diagnostics=%s",
                self._program_probe_controller,
                diagnostics,
            )
        except Exception as exc:
            self._logger.warning(
                "step=program_probe.host_final_diagnostics_failed controller=%s error=%s",
                self._program_probe_controller,
                exc,
            )
        try:
            diagnostics = output.diagnostics()
        except Exception as exc:
            self._logger.exception("step=program_probe.diagnostics_failed phase=%s error=%s", phase, exc)
            return
        self._logger.info("step=program_probe.%s diagnostics=%s", phase, diagnostics)
        controller_state = diagnostics.get("state", {})
        self.program_probe_status_label.setText(
            f"控制器 {self._program_probe_controller} | lease={diagnostics.get('acquired')} | "
            f"state=({controller_state.get('leftStickX', 0)}, {controller_state.get('leftStickY', 0)})"
        )

    def _render_program_probe_overlay(self, observation: Any | None) -> None:
        """Draw the active program route in the same native/display frame.

        The line deliberately starts at the latest native player sample and
        ends at the exact native target.  This makes a bad route transform
        visible independently of the Xbox output and prevents a display-only
        rotation from hiding a target-distance mismatch.
        """
        state = self._latest_dual_state
        source_size = self._dual_map_source_size
        transform = self._dual_map_transform
        if state is None or source_size is None or transform is None:
            return
        players = {
            str(identity): localization_display_point(
                point, source_size=source_size, transform=transform,
            )
            for identity, point in state.players.items() if point is not None
        }
        routes = {}
        if observation is not None:
            route_points = []
            if observation.position is not None:
                route_points.append(observation.position)
            route_points.extend(observation.route)
            if observation.target_position is not None and (
                not route_points
                or point_distance(route_points[-1], observation.target_position) > 1e-6
            ):
                route_points.append(observation.target_position)
            if len(route_points) >= 2:
                routes[observation.follower.key] = tuple(
                    localization_display_point(
                        point, source_size=source_size, transform=transform,
                    )
                    for point in route_points
                )
        target = self._clicked_target_display
        self.map_widget.set_overlay(players=players, target=target, routes=routes)

    def _clear_program_probe_recovery(self) -> None:
        self._program_probe_recovery_target = None
        self._program_probe_recovery_identity = None
        self._program_probe_recovery_controller = None
        self._program_probe_recovery_started_at_ms = None
        self._program_probe_recovery_attempts = 0

    def _clear_dual_recovery_contexts(self) -> None:
        """Atomically discard every delayed resume owned by this map session."""
        self._clear_program_probe_recovery()
        self._clear_dual_follow_recovery_context()
        self._dual_target_recovery = None
        self._logger.info("step=dual_motion.recovery_contexts_cleared")

    def _save_dual_follow_recovery_context(self) -> None:
        """Keep a visual-follow target while the tracker re-registers."""
        if self._follow_runtime is None or (
            not self._follow_live_mode and self._clicked_target_source is None
        ):
            return
        self._dual_recovery_follow_live = self._follow_live_mode
        self._dual_recovery_follow_instance_id = self._follow_runtime.map_identity.map_version
        self._dual_recovery_follow_radius = self.follow_footprint_radius.value()
        self._dual_recovery_follow_target_source = (
            None if self._follow_live_mode else tuple(self._clicked_target_source)
        )
        self._dual_recovery_follow_p1 = (
            str(self.follow_p1_combo.currentData())
            if self.follow_p1_combo.currentData() is not None else None
        )
        self._dual_recovery_follow_p2 = (
            str(self.follow_p2_combo.currentData())
            if self.follow_p2_combo.currentData() is not None else None
        )
        self._dual_recovery_follow_mode = (
            str(self.follow_mode_combo.currentData())
            if self.follow_mode_combo.currentData() is not None else None
        )
        self._logger.info(
            "step=dual_motion.follow_recovery_context_saved target_source=%s "
            "p1=%s p2=%s mode=%s live=%s instance=%s radius=%s",
            self._dual_recovery_follow_target_source,
            self._dual_recovery_follow_p1,
            self._dual_recovery_follow_p2,
            self._dual_recovery_follow_mode,
            self._dual_recovery_follow_live,
            self._dual_recovery_follow_instance_id,
            self._dual_recovery_follow_radius,
        )

    def _clear_dual_follow_recovery_context(self) -> None:
        self._dual_recovery_follow_target_source = None
        self._dual_recovery_follow_live = False
        self._dual_recovery_follow_instance_id = None
        self._dual_recovery_follow_radius = None
        self._dual_recovery_follow_p1 = None
        self._dual_recovery_follow_p2 = None
        self._dual_recovery_follow_mode = None

    def _save_dual_target_recovery_context(self) -> None:
        if (
            self._dual_target_runtime is None or self._clicked_target_source is None
            or self._snapshot is None or len(self._dual_target_roles) != 2
        ):
            return
        self._dual_target_recovery = (
            self._clicked_target_source,
            self._dual_target_roles[0].actor_id,
            self._dual_target_roles[1].actor_id,
            str(self._snapshot.metadata.instance_id),
        )
        self._logger.info(
            "step=dual_target.recovery_saved context=%s", self._dual_target_recovery,
        )

    def _maybe_resume_dual_target_after_relocalization(self) -> None:
        context = self._dual_target_recovery
        state = self._latest_dual_state
        captured_at_ms = self._latest_dual_captured_at_ms
        if context is None or state is None or self._snapshot is None:
            return
        source, p1, p2, instance_id = context
        if instance_id != str(self._snapshot.metadata.instance_id):
            self._dual_target_recovery = None
            self.dual_target_status_label.setText("双人同目标：地图实例变化，已安全停止")
            return
        if getattr(state, "recovery_requested", False) or not self._recovery_frame_usable(
            state, required_identities=(p1, p2),
        ):
            return
        # Keep the recovery hand-off on the same freshness contract as the
        # actual start method.  Consuming a 301–700ms frame here would clear
        # the saved context, only for start_dual_target_experiment() to reject
        # that same frame and leave the experiment idle.
        if captured_at_ms is None or int(time.time() * 1000) - int(captured_at_ms) > self._FOLLOW_RUNTIME_MAX_FRAME_AGE_MS:
            return
        if state.players.get(p1) is None or state.players.get(p2) is None:
            return
        self._dual_target_recovery = None
        for combo, identity in ((self.dual_target_p1_combo, p1), (self.dual_target_p2_combo, p2)):
            index = combo.findData(identity)
            if index < 0:
                self.dual_target_status_label.setText("双人同目标：恢复后角色身份变化，已安全停止")
                return
            combo.setCurrentIndex(index)
        self.start_dual_target_experiment()
        if self._dual_target_runtime is None:
            self._logger.error("step=dual_target.recovery_failed reason=runtime_rebuild")
            return
        self._logger.info("step=dual_target.recovery_resumed target_source=%s", source)
        self._on_follow_map_click(*source)

    def _maybe_resume_dual_follow_after_relocalization(self) -> None:
        target = self._dual_recovery_follow_target_source
        live_mode = self._dual_recovery_follow_live
        state = self._latest_dual_state
        captured_at_ms = self._latest_dual_captured_at_ms
        if (target is None and not live_mode) or state is None or self._snapshot is None:
            return
        if self._dual_recovery_follow_instance_id != str(self._snapshot.metadata.instance_id):
            self._clear_dual_follow_recovery_context()
            self._follow_recovery_pending = True
            self.follow_status_label.setText("实时跟随：地图实例变化，等待重新定位（会话保留）")
            self._logger.warning(
                "step=live_role_follow.recovery_waiting reason=map_instance_changed "
                "follow_session_preserved=True",
            )
            return
        required_identities = (
            (self._dual_recovery_follow_p1, self._dual_recovery_follow_p2)
            if live_mode else ()
        )
        if getattr(state, "recovery_requested", False) or not self._recovery_frame_usable(
            state, required_identities=required_identities,
        ):
            return
        recovery_frame_age_limit = (
            self._FOLLOW_START_MAX_FRAME_AGE_MS
            if live_mode else self._FOLLOW_RUNTIME_MAX_FRAME_AGE_MS
        )
        if captured_at_ms is None or int(time.time() * 1000) - int(captured_at_ms) > recovery_frame_age_limit:
            self._logger.debug(
                "step=live_role_follow.recovery_waiting reason=frame_not_fresh "
                "frame_age_ms=%s max_age_ms=%s live=%s",
                None if captured_at_ms is None else int(time.time() * 1000) - int(captured_at_ms),
                recovery_frame_age_limit,
                live_mode,
            )
            return
        if live_mode and (
            self._dual_recovery_follow_p1 == self._dual_recovery_follow_p2
            or state.players.get(self._dual_recovery_follow_p1) is None
            or state.players.get(self._dual_recovery_follow_p2) is None
        ):
            return
        # A live follow recovery is a non-terminal transition.  Keep the
        # existing runtime/output/session and only replace its visual anchor;
        # calling start_follow_experiment() here would invoke the user-stop
        # lifecycle and make a successful re-anchor look like a stop.
        if live_mode and self._follow_recovery_pending and self._follow_runtime is not None:
            if self._sync_live_follow_from_fresh_frame(
                state,
                captured_at_ms=int(captured_at_ms),
                now_ms=int(time.time() * 1000),
            ):
                self._follow_recovery_pending = False
                self._clear_dual_follow_recovery_context()
                self._follow_stale_since_ms = None
                self._follow_stale_release_sent = False
                self._follow_stale_recovery_requested = False
                self.follow_status_label.setText("实时跟随：视觉恢复完成，继续跟随")
                self._logger.info(
                    "step=live_role_follow.recovery_resumed_in_place "
                    "captured_at_ms=%s session_id=%s",
                    captured_at_ms,
                    self._follow_session_id,
                )
                # Tracker re-anchoring is synchronous, while output ownership
                # is normally acquired by the periodic follow tick. Run one
                # guarded tick now so recovery cannot finish with a ready
                # tracker and an idle program output.
                self._logger.info(
                    "step=live_role_follow.recovery_resume_tick session_id=%s "
                    "output_before=%s",
                    self._follow_session_id,
                    None if self._follow_program_output is None
                    else self._follow_program_output.snapshot(),
                )
                self._tick_follow_experiment()
            return
        # Click mode restores its saved point; live mode uses only this fresh
        # frame's selected leader position after rebuilding the runtime.
        if self._dual_recovery_follow_p1 is not None:
            index = self.follow_p1_combo.findData(self._dual_recovery_follow_p1)
            if index >= 0:
                self.follow_p1_combo.setCurrentIndex(index)
        if self._dual_recovery_follow_p2 is not None:
            index = self.follow_p2_combo.findData(self._dual_recovery_follow_p2)
            if index >= 0:
                self.follow_p2_combo.setCurrentIndex(index)
        if self._dual_recovery_follow_mode is not None:
            index = self.follow_mode_combo.findData(self._dual_recovery_follow_mode)
            if index >= 0:
                self.follow_mode_combo.setCurrentIndex(index)
        if self._dual_recovery_follow_radius is not None:
            self.follow_footprint_radius.setValue(self._dual_recovery_follow_radius)
        self.start_follow_experiment(_sync_phase="recovery_sync")
        if self._follow_runtime is None:
            self._logger.error(
                "step=dual_motion.follow_recovery_failed reason=runtime_rebuild_failed "
                "target_source=%s",
                target,
            )
            self._clear_dual_follow_recovery_context()
            return
        self._clear_dual_follow_recovery_context()
        self._logger.info(
            "step=dual_motion.follow_recovery_resumed target_source=%s "
            "captured_at_ms=%s live=%s",
            target,
            captured_at_ms,
            live_mode,
        )
        if not live_mode:
            self._on_follow_map_click(*target)

    @staticmethod
    def _recovery_frame_usable(
        state: Any, *, required_identities: tuple[str, ...] = (),
    ) -> bool:
        """Accept a fresh wall-trusted degraded frame during recovery.

        A marker can be temporarily hidden or overlap another marker while the
        wall registration is already valid.  The tracker keeps a bounded,
        timestamped estimate for that identity, so requiring the literal
        ``tracking`` state here would leave the saved session suspended until a
        later frame happens to show every marker at once.
        """
        status = str(getattr(state, "status", ""))
        if status == "tracking":
            return True
        if status != "degraded":
            return False
        diagnostics = getattr(state, "diagnostics", {}) or {}
        if not bool(diagnostics.get("wall_trusted", False)):
            return False
        players = getattr(state, "players", {}) or {}
        return all(identity is not None and players.get(identity) is not None
                   for identity in required_identities)

    def _maybe_resume_program_probe_after_relocalization(self) -> None:
        """Resume the saved target after a fresh dual visual frame arrives."""
        target = self._program_probe_recovery_target
        identity = self._program_probe_recovery_identity
        controller = self._program_probe_recovery_controller
        state = self._latest_dual_state
        captured_at_ms = self._latest_dual_captured_at_ms
        if target is None or identity is None or controller is None or state is None:
            return
        if getattr(state, "recovery_requested", False) or not self._recovery_frame_usable(
            state, required_identities=(identity,),
        ):
            return
        if captured_at_ms is None or int(time.time() * 1000) - int(captured_at_ms) > 1_000:
            return
        current = state.players.get(identity)
        if current is None:
            return
        role_index = self.program_probe_role_combo.findData(identity)
        controller_index = self.program_probe_controller_combo.findData(controller)
        if role_index < 0 or controller_index < 0:
            self._logger.error(
                "step=program_probe.relocalization_failed reason=selection_missing "
                "role=%s controller=%s",
                identity,
                controller,
            )
            self._clear_program_probe_recovery()
            return
        attempt = self._program_probe_recovery_attempts
        self.program_probe_role_combo.setCurrentIndex(role_index)
        self.program_probe_controller_combo.setCurrentIndex(controller_index)
        self._clear_program_probe_recovery()
        self._logger.info(
            "step=program_probe.relocalization_resumed target=%s role=%s controller=%s "
            "fresh_capture_at_ms=%s current=%s attempt=%s",
            target,
            identity,
            controller,
            captured_at_ms,
            current,
            attempt,
        )
        self._start_program_move_probe_at(target, _confirmed=True)

    def _request_program_probe_relocalization(
        self,
        target: tuple[float, float] | None,
        *,
        reason: str,
        diagnostics: dict[str, Any] | None = None,
    ) -> None:
        """Transition program movement into one bounded memory re-anchor."""
        recovery_now_ms = int(time.time() * 1000)
        self._logger.warning(
            "step=program_probe.relocalization_requested reason=%s diagnostics=%s",
            reason,
            diagnostics or {},
        )
        if (
            self._program_probe_last_relocalization_at_ms is not None
            and recovery_now_ms - self._program_probe_last_relocalization_at_ms < 10_000
        ):
            self._logger.warning(
                "step=program_probe.relocalization_cooldown elapsed_ms=%s",
                recovery_now_ms - self._program_probe_last_relocalization_at_ms,
            )
            self.stop_program_move_probe(reason="重定位冷却中，已停止输入等待人工检查")
            return
        if target is None or self._program_probe_role is None:
            self._logger.error(
                "step=program_probe.relocalization_failed reason=missing_resume_context "
                "target=%s role=%s",
                target,
                self._program_probe_role,
            )
            self.stop_program_move_probe(reason="重定位缺少目标上下文，已停止输入")
            return
        self._program_probe_last_relocalization_at_ms = recovery_now_ms
        recovery_identity = self._program_probe_role.actor_id
        recovery_controller = self._program_probe_controller
        self.stop_program_move_probe(reason=reason)
        self._program_probe_recovery_target = tuple(float(value) for value in target)
        self._program_probe_recovery_identity = str(recovery_identity)
        self._program_probe_recovery_controller = int(recovery_controller)
        self._program_probe_recovery_started_at_ms = recovery_now_ms
        self._program_probe_recovery_attempts += 1
        self._logger.info(
            "step=program_probe.relocalization_context_saved target=%s role=%s "
            "controller=%s attempt=%s",
            self._program_probe_recovery_target,
            self._program_probe_recovery_identity,
            self._program_probe_recovery_controller,
            self._program_probe_recovery_attempts,
        )
        if self._dual_motion_tracker is not None:
            self._start_dual_motion(recovery=True)
        else:
            self._logger.error(
                "step=program_probe.relocalization_failed reason=dual_tracker_missing"
            )
            self._clear_program_probe_recovery()

    def stop_program_move_probe(
        self,
        *,
        reason: str | None = None,
        _preserve_recovery: bool = False,
    ) -> None:
        self._experiment_composition.move_probe.stop()
        stop_reason = reason or "requested"
        previous_ticks = self._program_probe_ticks
        stopped_at_ms = int(time.time() * 1000)
        elapsed_ms = (
            None
            if self._program_probe_started_at_ms is None
            else max(0, stopped_at_ms - self._program_probe_started_at_ms)
        )
        displacement = None
        if self._program_probe_initial_position is not None and self._program_probe_last_position is not None:
            displacement = (
                self._program_probe_last_position[0] - self._program_probe_initial_position[0],
                self._program_probe_last_position[1] - self._program_probe_initial_position[1],
            )
        last_observation = self._program_probe_last_observation
        self._logger.info(
            "step=program_probe.stop_summary reason=%s ticks=%s elapsed_ms=%s "
            "role=%s controller=%s initial_native=%s last_native=%s target_native=%s "
            "displacement_native=%s final_distance=%s final_state=%s final_reason=%s",
            stop_reason,
            previous_ticks,
            elapsed_ms,
            self._program_probe_role.key if self._program_probe_role is not None else None,
            self._program_probe_controller,
            self._program_probe_initial_position,
            self._program_probe_last_position,
            self._program_probe_target,
            displacement,
            getattr(last_observation, "distance", None),
            getattr(getattr(last_observation, "state", None), "value", None),
            getattr(last_observation, "reason", None),
        )
        self._program_probe_arm_timer.stop()
        self._program_probe_timer.stop()
        self._program_probe_waiting_click = False
        self._program_probe_pending_point = None
        self._program_probe_game_pid = None
        self._program_probe_game_hwnd = None
        self._program_probe_started_at_ms = None
        self._program_probe_initial_position = None
        self._program_probe_last_position = None
        self._program_probe_target = None
        self._program_probe_last_observation = None
        self._program_probe_runtime = None
        self._program_probe_role = None
        if not _preserve_recovery:
            self._clear_program_probe_recovery()
        output, self._program_probe_output = self._program_probe_output, None
        if output is None:
            self.program_probe_stop_button.setEnabled(False)
            self.program_probe_button.setEnabled(True)
            if reason:
                self.program_probe_status_label.setText(reason)
            self._logger.info(
                "step=program_probe.stop reason=%s ticks=%s output_present=False",
                stop_reason,
                previous_ticks,
            )
            return
        try:
            output.release_all()
            self._logger.info("step=program_probe.neutral controller=%s", self._program_probe_controller)
        except Exception:
            self._logger.exception("step=program_probe.neutral_failed")
        finally:
            try:
                output.close_all()
                self._logger.info("step=program_probe.release_success controller=%s", self._program_probe_controller)
            except Exception as exc:
                self._logger.exception("step=program_probe.release_failed error=%s", exc)
        self.program_probe_button.setEnabled(True)
        self.program_probe_stop_button.setEnabled(False)
        self.program_probe_status_label.setText(reason or "测试结束：已发送中性并释放程序租约")
        self._logger.info(
            "step=program_probe.stop reason=%s ticks=%s output_present=True",
            stop_reason,
            previous_ticks,
        )
