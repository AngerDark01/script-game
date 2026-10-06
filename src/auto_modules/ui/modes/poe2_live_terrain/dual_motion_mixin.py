"""Dual visual motion methods extracted from the experiment page."""

from __future__ import annotations

import time
from types import SimpleNamespace
from typing import Any, Mapping

from PySide6.QtCore import QTimer

from auto_modules.features.poe2.live_terrain.experimental.hybrid_localization.models import HybridFrame
from auto_modules.features.poe2.live_terrain.experimental.recovery.controller import RecoveryObservation
from auto_modules.features.poe2.live_terrain.experimental.multiplayer_localization import (
    MarkerColorProfile, marker_candidates_from_observation, detect_saturated_marker_observation,
)
from auto_modules.features.poe2.live_terrain.experimental.multiplayer_localization.dual_motion import RolePredictionHint
from auto_modules.features.poe2.live_terrain.experimental.multiplayer_follow import RoleId
from auto_modules.ui.modes.poe2_live_terrain.presenter import (
    localization_display_point,
    prepare_localization_map,
    present_player_position_overlay,
    terrain_pixmap,
)
from auto_modules.features.poe2.live_terrain.terrain_reference import build_reference
from auto_modules.features.poe2.live_terrain.experimental.multiplayer_localization.occlusion_archive import (
    save_dual_occlusion_evidence,
)


class Poe2DualMotionMixin:
    def _start_dual_motion(
        self, *, recovery: bool, first_frame_ready: bool = False,
        preserve_follow: bool = False,
    ) -> None:
        if self._closing:
            self._logger.info(
                "step=dual_motion.start_ignored reason=page_closing recovery=%s",
                recovery,
            )
            return
        if self._snapshot is None:
            self._show_error(RuntimeError("请先获取当前地图"))
            return
        if not first_frame_ready:
            if self._dual_first_frame_worker is not None and self._dual_first_frame_worker.is_running:
                self.dual_motion_status_label.setText("双人实时：后台首帧恢复仍在进行")
                return
            if any(
                worker.is_running
                for worker in self._retired_dual_first_frame_workers
            ):
                self.dual_motion_status_label.setText("双人实时：等待后台首帧恢复线程退出")
                return
        self.stop_dual_motion(
            clear_first_frame=False,
            preserve_program_probe_recovery=recovery,
            preserve_follow=preserve_follow,
        )
        self.stop_hybrid_localization()
        self.stop_multiframe_localization()
        self.stop_preview()
        if self.capture_monitor_window is not None:
            stop_monitoring = getattr(self.capture_monitor_window, "stop_monitoring", None)
            if callable(stop_monitoring):
                stop_monitoring()
        retired_running = tuple(
            worker
            for worker in self._retired_dual_motion_workers
            if self._dual_worker_is_running(worker)
        )
        if retired_running:
            # A native capture call may ignore stop() until its current frame
            # returns.  Never read a new first frame or create a second worker
            # against the same provider while one of those workers is alive.
            self._dual_motion_restart_pending = bool(recovery)
            self._logger.warning(
                "step=dual_motion.restart_deferred reason=retired_worker_running "
                "recovery=%s retired=%s",
                recovery,
                len(retired_running),
            )
            self.dual_motion_status_label.setText("双人实时：等待旧截图线程退出后恢复")
            return
        if (
            recovery
            and not first_frame_ready
            and hasattr(self.monitor_config, "localization_fps")
        ):
            if self._start_dual_first_frame_async(recovery=True):
                return
            self._logger.error(
                "step=program_probe.relocalization_failed "
                "reason=background_first_frame_unavailable"
            )
            if not preserve_follow:
                self._clear_dual_recovery_contexts()
                self.dual_motion_status_label.setText("双人实时：无法启动后台恢复定位")
            else:
                self._logger.warning(
                    "step=dual_motion.recovery_deferred reason=background_first_frame_unavailable "
                    "follow_prediction_continues=True",
                )
            return
        # A recovery must take a fresh memory anchor and a fresh visual frame.
        # Reusing the old registration would preserve the transform that just
        # lost contact with the live character. Normal starts still reuse a
        # successful manual first-frame run to avoid transient-frame failures.
        # ``first_frame_ready`` is the hand-off from the asynchronous recovery
        # worker.  The worker has already applied its bundle to
        # ``_last_dual_first_frame_result`` and ``_dual_initial_frame``; do not
        # clear the result merely because this restart is a recovery.  The old
        # expression (``None if recovery else ...``) made an accepted worker
        # result fail the validation below when ``first_frame_ready=True``.
        result = self._last_dual_first_frame_result
        self._logger.info(
            "step=dual_motion.first_frame_context recovery=%s first_frame_ready=%s "
            "status=%s accepted=%s has_frame=%s",
            recovery,
            first_frame_ready,
            None if result is None else result.status,
            None if result is None else result.accepted,
            self._dual_initial_frame is not None,
        )
        if (
            not first_frame_ready
            and (recovery or result is None or not result.accepted or self._dual_initial_frame is None)
        ):
            if recovery:
                self._logger.info(
                    "step=program_probe.relocalization_started recovery=%s "
                    "attempt=%s target=%s role=%s",
                    recovery,
                    self._program_probe_recovery_attempts,
                    self._program_probe_recovery_target,
                    self._program_probe_recovery_identity,
                )
            self.run_dual_first_frame_experiment(
                render_map=False,
                force_memory_read=recovery,
            )
            result = self._last_dual_first_frame_result
        if result is None or not result.accepted or self._dual_initial_frame is None:
            self.dual_motion_status_label.setText("双人实时：首帧配准未通过")
            if recovery:
                self._logger.error(
                    "step=program_probe.relocalization_failed reason=first_frame_rejected"
                )
                if not preserve_follow:
                    self._clear_dual_recovery_contexts()
                else:
                    self._logger.warning(
                        "step=dual_motion.recovery_deferred reason=first_frame_rejected "
                        "follow_prediction_continues=True",
                    )
            return
        try:
            reference = self._map_orientation().transform_reference(build_reference(self._snapshot))
            if self.dual_motion_tracker_factory is not None:
                tracker = self.dual_motion_tracker_factory(reference)
            else:
                runtime = MapRuntime.from_wall_layer(
                    reference_boundary_layer(reference),
                    map_id=self._snapshot.metadata.area_id,
                    map_version=self._snapshot.metadata.instance_id,
                )
                tracker = DualVisualTracker(
                    LocalMapMatcher(runtime, max_error=4.0, min_margin=0.02),
                    marker_hold_ms=round(self.dual_marker_hold_seconds.value() * 1000),
                    marker_max_uncertainty=self.dual_marker_error_limit.value(),
                )
            initial = tracker.start(self._dual_initial_frame, result, self._dual_initial_candidates)
            base = terrain_pixmap(self._snapshot, self._map_orientation())
            self.map_widget.set_image(prepare_localization_map(base, initial.transform))
            self._dual_map_source_size = (base.width(), base.height())
            self._dual_motion_tracker = tracker
            self._dual_motion_frame_count = 0
            self._dual_evidence_count = 0
            self._dual_evidence_signature = None
            self._dual_map_transform = initial.transform
            self._dual_follow_reference = reference
            self._latest_dual_state = initial
            self._render_dual_motion_state(initial, self._dual_map_source_size)
            self.start_follow_button.setEnabled(True)
            self.start_dual_target_button.setEnabled(True)
            # Production monitor profiles expose localization_fps and use the
            # bounded worker.  Minimal test/dummy configs intentionally keep
            # the legacy synchronous hook so existing deterministic page tests
            # can call _tick_dual_motion() directly.
            worker = None
            if hasattr(self.monitor_config, "localization_fps"):
                self._dual_motion_generation += 1
                self._dual_motion_controller.start(self._dual_motion_generation)
                worker_recognizer = None
                # HSVRecognizer owns a CLAHE native object.  Keep the GUI
                # recognizer out of the capture thread even though the
                # current page normally stops preview before starting this
                # loop; this also makes reopening the monitor window safe.
                try:
                    get_params = getattr(self.recognizer, "get_params", None)
                    set_params = getattr(self.recognizer, "set_params", None)
                    if callable(get_params) and callable(set_params):
                        candidate = type(self.recognizer)()
                        candidate.set_params(dict(get_params()))
                        worker_recognizer = candidate
                except Exception:
                    self._logger.exception(
                        "step=dual_motion.worker_recognizer_clone_failed; falling back to synchronous capture"
                    )
                if worker_recognizer is not None:
                    worker = Poe2DualMotionWorker(
                        tracker=tracker,
                        preview_provider=self.preview_provider,
                        recognizer=worker_recognizer,
                        monitor_config=self.monitor_config,
                        fps=int(getattr(self.monitor_config, "localization_fps", 30)),
                        generation=self._dual_motion_generation,
                        cleanup=getattr(self.preview_provider, "close_current_thread", None),
                    )
                    worker.result_available.connect(self._on_dual_worker_result)
                    worker.frame_failed.connect(self._on_dual_worker_frame_failed)
                    worker.failed.connect(self._on_dual_worker_failed)
                    worker.finished.connect(self._on_dual_worker_finished)
                    self._dual_motion_worker = worker
                    # This timer only drains the latest completed result; capture
                    # and recognition no longer run in the Qt GUI thread.
                    # The worker is configured for 30 FPS.  A 16 ms drain
                    # wakes Qt twice for most completed frames without
                    # producing another capture result; 33 ms matches the
                    # producer cadence and keeps the UI responsive when
                    # preview/overlay work is active.
                    self._dual_motion_timer.setInterval(self._DUAL_WORKER_DRAIN_INTERVAL_MS)
                else:
                    self._logger.warning(
                        "step=dual_motion.worker_disabled reason=recognizer_not_isolated "
                        "fallback=synchronous_capture"
                    )
                    self._dual_motion_timer.setInterval(self._localization_interval())
            else:
                self._dual_motion_timer.setInterval(self._localization_interval())
            self._dual_motion_timer.start()
            if worker is not None:
                worker.start()
            self.start_dual_motion_button.setEnabled(False)
            self.stop_dual_motion_button.setEnabled(True)
            self._logger.info(
                "step=dual_motion.started instance=%s interval_ms=%s memory_reads=%s recovery=%s",
                self._snapshot.metadata.instance_id,
                self._dual_motion_timer.interval(),
                self._dual_first_frame_read_count,
                recovery,
            )
            if recovery:
                self._logger.info(
                    "step=program_probe.relocalization_registration_success "
                    "memory_reads=%s transform=%s; waiting_for_fresh_visual_frame=True",
                    self._dual_first_frame_read_count,
                    getattr(initial, "transform", None),
                )
        except Exception as exc:
            # Keep an accepted manual first frame available for a retry.  A
            # failed realtime construction must not force a new memory read
            # and transient screenshot registration.
            self.stop_dual_motion(
                clear_first_frame=False,
                preserve_follow=bool(preserve_follow),
            )
            self._logger.exception("step=dual_motion.start_failed")
            self.dual_motion_status_label.setText(f"双人实时：启动失败 | {exc}")
            self._show_error(exc)
            if recovery:
                self._logger.error(
                    "step=program_probe.relocalization_failed reason=tracker_start_failed error=%s",
                    exc,
                )
                if not preserve_follow:
                    self._clear_dual_recovery_contexts()
                else:
                    self._follow_recovery_pending = True
                    self._schedule_live_follow_recovery_retry("tracker_start_failed")

    def stop_dual_motion(
        self,
        *,
        clear_first_frame: bool = True,
        preserve_program_probe_recovery: bool = False,
        preserve_follow: bool = False,
    ) -> None:
        self._dual_motion_controller.stop(self._dual_motion_generation)
        # A user-initiated stop, a worker failure, and a map reset all cancel
        # any delayed restart request.  The recovery path sets a new pending
        # value only after this method returns, so this cannot cancel a fresh
        # request that is currently being scheduled.
        self._dual_motion_restart_pending = None
        self.stop_program_move_probe(
            _preserve_recovery=preserve_program_probe_recovery,
        )
        if not preserve_follow:
            self.stop_follow_experiment(
                _preserve_recovery=preserve_program_probe_recovery,
            )
        else:
            self._logger.info(
                "step=follow_experiment.recovery_transition "
                "action=preserve_session output_kept=True timer_kept=True",
            )
        self.stop_dual_target_experiment(
            _preserve_recovery=preserve_program_probe_recovery,
        )
        was_active = self._dual_motion_timer.isActive()
        self._dual_motion_timer.stop()
        first_frame_worker = self._dual_first_frame_worker
        if first_frame_worker is not None:
            first_frame_worker.stop()
            wait = getattr(first_frame_worker, "wait", None)
            stopped = wait(0) if callable(wait) else True
            self._dual_first_frame_worker = None
            self._dual_first_frame_pending_recovery = False
            self._dual_first_frame_started_at = None
            if not stopped:
                self._logger.info(
                    "step=dual_first_frame.worker_retired generation=%s",
                    first_frame_worker.generation,
                )
            if first_frame_worker not in self._retired_dual_first_frame_workers:
                self._retired_dual_first_frame_workers.append(first_frame_worker)
        worker = self._dual_motion_worker
        if worker is not None:
            worker.stop()
            wait = getattr(worker, "wait", None)
            # Do not hold the Qt event loop for a native capture call.  The
            # worker remains strongly referenced in the retired list and its
            # finished signal schedules any deferred recovery restart after
            # the capture backend has actually returned.
            stopped = wait(0) if callable(wait) else True
            # Keep the QObject strongly referenced until its queued
            # ``finished`` signal has been delivered, even when the Python
            # thread joined successfully.  Dropping it immediately can let
            # Qt tear down a signal/slot connection while a native preview
            # frame is still being retired, which is a known Qt6Gui crash
            # boundary on Windows.
            self._dual_motion_worker = None
            if worker not in self._retired_dual_motion_workers:
                self._retired_dual_motion_workers.append(worker)
            if stopped:
                self._logger.info(
                    "step=dual_motion.worker_stop_completed generation=%s",
                    self._dual_motion_generation,
                )
            else:
                # Do not destroy the last Python reference while native
                # capture is still running.  Keep it until its finished
                # signal arrives so a late callback cannot use freed state.
                self._logger.warning(
                    "step=dual_motion.worker_stop_deferred generation=%s retired=%s "
                    "reason=native_capture_still_returning",
                    self._dual_motion_generation,
                    len(self._retired_dual_motion_workers),
                )
        self._dual_motion_tracker = None
        if not preserve_follow:
            self._dual_map_source_size = None
            self._dual_map_transform = None
            self._dual_follow_reference = None
            self._latest_dual_state = None
            self._latest_dual_captured_at_ms = None
            self._latest_dual_processed = None
        if clear_first_frame:
            self._last_dual_first_frame_result = None
            self._dual_initial_frame = None
            self._dual_initial_candidates = ()
        if not preserve_follow:
            self.start_follow_button.setEnabled(False)
        self.start_dual_target_button.setEnabled(False)
        self.start_dual_motion_button.setEnabled(self._snapshot is not None)
        if not preserve_follow:
            self.stop_dual_motion_button.setEnabled(False)
        if was_active:
            if preserve_follow:
                self.dual_motion_status_label.setText("双人实时：视觉恢复中，跟随预测继续")
                self._logger.info(
                    "step=dual_motion.recovery_transition frames=%s "
                    "follow_prediction_continues=True",
                    self._dual_motion_frame_count,
                )
            else:
                self.dual_motion_status_label.setText("双人实时：已停止")
                self._logger.info("step=dual_motion.stopped frames=%s", self._dual_motion_frame_count)

    def _on_dual_worker_result(self, generation: int) -> None:
        if self._closing or generation != self._dual_motion_generation:
            return
        try:
            self._drain_dual_motion_worker()
        except Exception as exc:
            self._logger.exception("step=dual_motion.result_dispatch_failed error=%s", exc)
            continued = self._continue_live_follow_after_dual_failure(
                "result_dispatch_failed", exc,
            )
            if not continued:
                self.stop_dual_motion()
                self.dual_motion_status_label.setText(f"双人实时：渲染失败 | {exc}")

    def _on_dual_worker_failed(self, generation: int, error: Exception) -> None:
        if self._closing or generation != self._dual_motion_generation:
            return
        self._logger.error("step=dual_motion.worker_failed error=%s", error)
        continued = self._continue_live_follow_after_dual_failure("worker_failed", error)
        if not continued:
            self.stop_dual_motion()
            self.dual_motion_status_label.setText(f"双人实时：失败 | {error}")
            self._show_error(error)

    def _on_dual_worker_frame_failed(
        self, generation: int, error: Exception, consecutive_failures: int
    ) -> None:
        if self._closing or generation != self._dual_motion_generation:
            return
        worker = self._dual_motion_worker
        max_failures = int(getattr(worker, "max_consecutive_failures", 3) or 3)
        if (
            consecutive_failures > 1
            and consecutive_failures < max_failures
            and consecutive_failures % 5 != 0
        ):
            self._dual_frame_failure_suppressed += 1
            return
        suppressed = self._dual_frame_failure_suppressed
        self._dual_frame_failure_suppressed = 0
        self._logger.warning(
            "step=dual_motion.frame_failed generation=%s consecutive=%s "
            "failed_frames=%s suppressed=%s error=%s",
            generation,
            consecutive_failures,
            getattr(worker, "failed_frames", None),
            suppressed,
            error,
        )

    def _on_dual_worker_finished(self, generation: int) -> None:
        self._logger.info("step=dual_motion.worker_finished generation=%s", generation)
        self._retired_dual_motion_workers = [
            worker
            for worker in self._retired_dual_motion_workers
            if worker.generation != generation
        ]
        pending = self._dual_motion_restart_pending
        if self._closing or self._snapshot is None:
            self._dual_motion_restart_pending = None
            if pending is not None:
                self._logger.info(
                    "step=dual_motion.restart_cancelled reason=page_not_active "
                    "closing=%s has_snapshot=%s",
                    self._closing,
                    self._snapshot is not None,
                )
            return
        if (
            pending is not None
            and self._dual_motion_worker is None
            and not any(
                self._dual_worker_is_running(worker)
                for worker in self._retired_dual_motion_workers
            )
        ):
            self._dual_motion_restart_pending = None
            session_token = self._dual_motion_session_token
            self._logger.info(
                "step=dual_motion.restart_resumed generation=%s recovery=%s",
                generation,
                pending,
            )
            QTimer.singleShot(
                0,
                lambda recovery=pending, token=session_token: self._resume_dual_motion_restart(
                    recovery=recovery,
                    session_token=token,
                ),
            )

    def _begin_live_follow_recovery_episode(self, reason: str) -> None:
        """Open one recovery episode for the active live-follow session."""
        if self._follow_recovery_episode_active:
            return
        self._recovery_controller.observe(
            RecoveryObservation(str(reason), recovery_requested=True)
        )
        self._follow_recovery_episode_active = True
        self._follow_recovery_episode_reason = str(reason)
        self._follow_recovery_episode_suppressed = 0
        self._logger.info(
            "step=live_role_follow.recovery_episode_started reason=%s session_id=%s",
            reason,
            self._follow_session_id,
        )

    def _clear_live_follow_recovery_episode(self, reason: str) -> None:
        """Close the episode after a fresh/stable observation is accepted."""
        if self._follow_recovery_episode_active:
            self._logger.info(
                "step=live_role_follow.recovery_episode_cleared reason=%s "
                "episode_reason=%s suppressed=%s session_id=%s",
                reason,
                self._follow_recovery_episode_reason,
                self._follow_recovery_episode_suppressed,
                self._follow_session_id,
            )
        self._follow_recovery_episode_active = False
        self._follow_recovery_episode_reason = None
        self._follow_recovery_episode_suppressed = 0
        self._recovery_controller.clear(reason)
        self._follow_recovery_retry_delay_ms = 0

    def _continue_live_follow_after_dual_failure(
        self, reason: str, error: Exception | None = None,
    ) -> bool:
        """Keep an active live-follow session alive across capture failures.

        Visual/capture failures are recoverable observations. They may release
        the current stick output, but they must not destroy the follow runtime,
        timer, target session, or prediction state. The recovery retry rebuilds
        the visual worker and re-anchors when a fresh frame arrives.
        """
        active = bool(self._follow_live_mode and self._follow_runtime is not None)
        if not active:
            return False
        if self._follow_recovery_episode_active:
            self._follow_recovery_episode_suppressed += 1
            if self._follow_recovery_episode_suppressed == 1 or (
                self._follow_recovery_episode_suppressed % 25 == 0
            ):
                self._logger.info(
                    "step=live_role_follow.recovery_episode_suppressed reason=%s "
                    "source=dual_failure count=%s episode_reason=%s",
                    reason,
                    self._follow_recovery_episode_suppressed,
                    self._follow_recovery_episode_reason,
                )
            self._follow_recovery_pending = True
            self._schedule_live_follow_recovery_retry("episode_suppressed")
            return True
        self._begin_live_follow_recovery_episode(reason)
        self._follow_recovery_pending = True
        if self._follow_program_output is not None:
            try:
                self._follow_program_output.release_all()
            except Exception:
                self._logger.exception(
                    "step=live_role_follow.recovery_release_failed reason=%s", reason,
                )
        self._logger.warning(
            "step=live_role_follow.recovery_deferred reason=%s "
            "follow_prediction_continues=True error=%s",
            reason, error,
        )
        self.dual_motion_status_label.setText("双人实时：视觉链路暂时异常，跟随预测继续")
        self.follow_status_label.setText("实时跟随：视觉链路暂时异常，跟随预测继续")
        self.stop_dual_motion(
            preserve_program_probe_recovery=True,
            preserve_follow=True,
        )
        self._schedule_live_follow_recovery_retry(reason)
        return True

    @staticmethod
    def _dual_worker_is_running(worker: Any) -> bool:
        value = getattr(worker, "is_running", False)
        return bool(value() if callable(value) else value)

    def _resume_dual_motion_restart(self, *, recovery: bool, session_token: int) -> None:
        if (
            self._closing
            or session_token != self._dual_motion_session_token
            or self._snapshot is None
        ):
            self._logger.info(
                "step=dual_motion.restart_cancelled reason=session_changed "
                "closing=%s token=%s current_token=%s has_snapshot=%s",
                self._closing,
                session_token,
                self._dual_motion_session_token,
                self._snapshot is not None,
            )
            return
        # A retired capture worker can finish after an active live-follow
        # session requested recovery. Preserve that session when the fresh
        # worker is finally allowed to start.
        preserve_follow = bool(self._follow_live_mode and self._follow_runtime is not None)
        self._start_dual_motion(
            recovery=recovery,
            preserve_follow=preserve_follow,
        )

    def _drain_dual_motion_worker(self) -> None:
        worker = self._dual_motion_worker
        if worker is None:
            return
        result = worker.take_latest()
        if result is None:
            return
        if self._dual_motion_controller.publish(self._dual_motion_generation, result) is None:
            self._logger.debug(
                "step=dual_motion.frame_ignored reason=retired_generation generation=%s",
                self._dual_motion_generation,
            )
            return
        if self._follow_live_mode and self._follow_runtime is not None:
            foreground, foreground_reason = self._refresh_follow_game_window()
            if not foreground:
                # Do not let a browser/Workbench frame become the latest
                # localization state.  The normal follow tick will hold the
                # output at the foreground gate and wait for a real PoE2
                # frame, instead of counting this frame as marker loss.
                self._logger.warning(
                    "step=dual_motion.capture_frame_ignored reason=%s "
                    "captured_at_ms=%s pid=%s hwnd=%s",
                    foreground_reason,
                    result.captured_at_ms,
                    self._follow_game_pid,
                    self._follow_game_hwnd,
                )
                if self._follow_program_output is not None:
                    self._follow_program_output.release_all()
                return
        state = result.state
        self._dual_motion_frame_count += 1
        self._latest_dual_state = state
        self._latest_dual_captured_at_ms = int(result.captured_at_ms)
        self._latest_dual_raw = result.raw
        self._latest_dual_combined = result.combined
        self._latest_dual_processed = getattr(result, "processed", None)
        self._record_dual_observation_evidence(
            state, result.raw, result.candidates, result.captured_at_ms,
        )
        now = time.perf_counter()
        if now - self._dual_last_ui_render_at >= 1.0 / 12.0:
            self._dual_last_ui_render_at = now
            self._render_preview(
                result.raw,
                combined=result.combined,
                processed=getattr(result, "processed", None),
            )
        source_size = self._dual_map_source_size
        if source_size is not None:
            self._render_dual_motion_state(state, source_size)
        if self._dual_motion_frame_count % 30 == 0 or state.status != "tracking":
            self._logger.info(
                "step=dual_motion.tick frame=%s status=%s reason=%s quality=%.3f "
                "visible=%s correction=%s recovery=%s diagnostics=%s",
                self._dual_motion_frame_count, state.status, state.reason,
                state.wall_quality, tuple(k for k, v in state.players.items() if v is not None),
                state.correction_attempted, state.recovery_requested, dict(state.diagnostics),
            )
            self._logger.info(
                "step=dual_motion.timing frame=%s capture_ms=%.1f recognition_ms=%.1f "
                "tracking_ms=%.1f total_worker_ms=%.1f dropped_results=%s completed_frames=%s",
                self._dual_motion_frame_count,
                result.capture_ms,
                result.recognition_ms,
                result.tracking_ms,
                result.capture_ms + result.recognition_ms + result.tracking_ms,
                worker.dropped_results,
                worker.completed_frames,
            )
        revision = worker.take_pending_recovery_revision()
        if revision or state.recovery_requested:
            revision = revision or state.recovery_revision
            self._logger.warning("step=dual_motion.recovery revision=%s", revision)
            live_follow_recovery = bool(
                self._follow_live_mode and self._follow_runtime is not None
            )
            recovery_episode_already_active = bool(
                live_follow_recovery and self._follow_recovery_episode_active
            )
            if recovery_episode_already_active:
                self._follow_recovery_episode_suppressed += 1
                self._follow_recovery_pending = True
                if self._follow_recovery_episode_suppressed == 1 or (
                    self._follow_recovery_episode_suppressed % 25 == 0
                ):
                    self._logger.info(
                        "step=live_role_follow.recovery_episode_suppressed "
                        "reason=%s source=dual_motion count=%s",
                        state.reason, self._follow_recovery_episode_suppressed,
                    )
                return
            if live_follow_recovery:
                self._begin_live_follow_recovery_episode(f"motion:{state.reason}")
            if not self._claim_dual_recovery(reason=f"motion:{state.reason}"):
                if live_follow_recovery:
                    self._follow_recovery_pending = True
                    self.dual_motion_status_label.setText(
                        "双人实时：视觉恢复冷却中，跟随预测继续"
                    )
                    self._logger.warning(
                        "step=dual_motion.recovery_deferred reason=cooldown "
                        "follow_prediction_continues=True revision=%s",
                        revision,
                    )
                    return
                self.stop_dual_motion()
                self.dual_motion_status_label.setText("双人实时：恢复后连续失配，请检查监控配置并手动重启")
                self._logger.warning("step=dual_motion.recovery_cooldown revision=%s", revision)
                return
            self._save_dual_follow_recovery_context()
            self._save_dual_target_recovery_context()
            self._follow_recovery_pending = live_follow_recovery
            self.stop_dual_motion(
                preserve_program_probe_recovery=True,
                preserve_follow=live_follow_recovery,
            )
            if live_follow_recovery:
                self._start_dual_motion(recovery=True, preserve_follow=True)
            else:
                self._start_dual_motion(recovery=True)
            return
        self._maybe_resume_program_probe_after_relocalization()
        self._maybe_resume_dual_follow_after_relocalization()
        self._maybe_resume_dual_target_after_relocalization()

    def _tick_dual_motion(self) -> None:
        if self._dual_motion_worker is not None:
            self._drain_dual_motion_worker()
            return
        source_size = self._dual_map_source_size
        if (
            self._dual_motion_tracker is None
            or self.preview_provider is None
            or self.recognizer is None
            or source_size is None
        ):
            return
        tick_started = time.perf_counter()
        try:
            raw = self.preview_provider(self.monitor_config)
            if raw is None:
                raise RuntimeError("截图后端返回空帧")
            if self._follow_live_mode and self._follow_runtime is not None:
                foreground, foreground_reason = self._refresh_follow_game_window()
                if not foreground:
                    self._logger.warning(
                        "step=dual_motion.capture_frame_ignored reason=%s "
                        "pid=%s hwnd=%s",
                        foreground_reason,
                        self._follow_game_pid,
                        self._follow_game_hwnd,
                    )
                    if self._follow_program_output is not None:
                        self._follow_program_output.release_all()
                    return
            capture_elapsed_ms = (time.perf_counter() - tick_started) * 1000.0
            captured_at_ms = int(time.time() * 1000)
            # Reuse the wall preprocessing result for the preview instead of
            # running the expensive preprocessing a second time every few
            # frames.  The fallback keeps compatibility with test/dummy
            # recognizers that only expose ``extract_combined``.
            processed = None
            extract_with_processed = getattr(self.recognizer, "extract_combined_with_processed", None)
            if callable(extract_with_processed):
                processed, combined = extract_with_processed(
                    raw, player_pos=None, exclude_player=False, exclude_dynamic=False,
                )
            else:
                combined = self.recognizer.extract_combined(
                    raw, player_pos=None, exclude_player=False, exclude_dynamic=False,
                )
            recognition_elapsed_ms = (time.perf_counter() - tick_started) * 1000.0 - capture_elapsed_ms
            mask = combined[0] if isinstance(combined, (tuple, list)) else combined
            profiles = tuple(
                MarkerColorProfile.from_dict(item)
                for item in getattr(self.monitor_config, "dual_marker_profiles", ())
            )
            observation = detect_saturated_marker_observation(
                raw, captured_at_ms, profiles=profiles or None,
            )
            frame = HybridFrame(
                captured_at_ms, captured_at_ms, mask,
                (float(mask.shape[1]) / 2.0, float(mask.shape[0]) / 2.0),
            )
            candidates = marker_candidates_from_observation(observation, max_candidates=6)
            hints = {
                identity: RolePredictionHint((value[0], value[1]), value[2], value[3])
                for identity, value in self._current_follow_prediction_hints(captured_at_ms).items()
            }
            state = (
                self._dual_motion_tracker.tick(frame, candidates, prediction_hints=hints)
                if hints else self._dual_motion_tracker.tick(frame, candidates)
            )
            tracking_elapsed_ms = (time.perf_counter() - tick_started) * 1000.0 - capture_elapsed_ms - recognition_elapsed_ms
            self._dual_motion_frame_count += 1
            self._latest_dual_state = state
            self._latest_dual_captured_at_ms = captured_at_ms
            self._latest_dual_raw = raw
            self._latest_dual_combined = combined
            self._latest_dual_processed = processed
            self._record_dual_observation_evidence(state, raw, candidates, captured_at_ms)
            if self._dual_motion_frame_count % 3 == 0:
                self._render_preview(raw, combined=combined, processed=processed)
            self._render_dual_motion_state(state, source_size)
            self._maybe_resume_program_probe_after_relocalization()
            self._maybe_resume_dual_follow_after_relocalization()
            self._maybe_resume_dual_target_after_relocalization()
            if self._dual_motion_frame_count % 30 == 0 or state.status != "tracking":
                self._logger.info(
                    "step=dual_motion.tick frame=%s status=%s reason=%s quality=%.3f "
                    "visible=%s correction=%s recovery=%s diagnostics=%s",
                    self._dual_motion_frame_count, state.status, state.reason,
                    state.wall_quality, tuple(k for k, v in state.players.items() if v is not None),
                    state.correction_attempted, state.recovery_requested, dict(state.diagnostics),
                )
                self._logger.info(
                    "step=dual_motion.timing frame=%s capture_ms=%.1f recognition_ms=%.1f tracking_ms=%.1f total_ms=%.1f",
                    self._dual_motion_frame_count,
                    capture_elapsed_ms,
                    recognition_elapsed_ms,
                    tracking_elapsed_ms,
                    (time.perf_counter() - tick_started) * 1000.0,
                )
            if state.recovery_requested:
                self._logger.warning("step=dual_motion.recovery revision=%s", state.recovery_revision)
                live_follow_recovery = bool(
                    self._follow_live_mode and self._follow_runtime is not None
                )
                recovery_episode_already_active = bool(
                    live_follow_recovery and self._follow_recovery_episode_active
                )
                if recovery_episode_already_active:
                    self._follow_recovery_episode_suppressed += 1
                    self._follow_recovery_pending = True
                    if self._follow_recovery_episode_suppressed == 1 or (
                        self._follow_recovery_episode_suppressed % 25 == 0
                    ):
                        self._logger.info(
                            "step=live_role_follow.recovery_episode_suppressed "
                            "reason=%s source=dual_motion count=%s",
                            state.reason, self._follow_recovery_episode_suppressed,
                        )
                    return
                if live_follow_recovery:
                    self._begin_live_follow_recovery_episode(f"motion:{state.reason}")
                if not self._claim_dual_recovery(reason=f"motion:{state.reason}"):
                    if live_follow_recovery:
                        self._follow_recovery_pending = True
                        self.dual_motion_status_label.setText(
                            "双人实时：视觉恢复冷却中，跟随预测继续"
                        )
                        self._logger.warning(
                            "step=dual_motion.recovery_deferred reason=cooldown "
                            "follow_prediction_continues=True revision=%s",
                            state.recovery_revision,
                        )
                        return
                    self.stop_dual_motion()
                    self.dual_motion_status_label.setText(
                        "双人实时：恢复后连续失配，请检查监控配置并手动重启"
                    )
                    self._logger.warning(
                        "step=dual_motion.recovery_cooldown revision=%s",
                        state.recovery_revision,
                    )
                    return
                self._save_dual_follow_recovery_context()
                self._save_dual_target_recovery_context()
                self._follow_recovery_pending = live_follow_recovery
                self.stop_dual_motion(
                    preserve_program_probe_recovery=True,
                    preserve_follow=live_follow_recovery,
                )
                if live_follow_recovery:
                    self._start_dual_motion(recovery=True, preserve_follow=True)
                else:
                    self._start_dual_motion(recovery=True)
        except Exception as exc:
            self._logger.exception("step=dual_motion.tick_failed")
            continued = self._continue_live_follow_after_dual_failure("tick_failed", exc)
            if not continued:
                self.stop_dual_motion()
                self.dual_motion_status_label.setText(f"双人实时：失败 | {exc}")

    def _record_dual_observation_evidence(
        self, state: Any, raw: Any, candidates: Any, captured_at_ms: int,
    ) -> None:
        if state.status == "tracking":
            self._dual_evidence_signature = None
            return
        if raw is None or self._dual_evidence_count >= 6:
            return
        diagnostics = dict(getattr(state, "diagnostics", {}) or {})
        signature = (
            state.status, state.reason,
            tuple(diagnostics.get("missing_identities", ())),
            tuple(diagnostics.get("expired_marker_identities", ())),
        )
        if signature == self._dual_evidence_signature:
            return
        root = getattr(self.archive, "root", None)
        if root is None:
            return
        try:
            profiles = tuple(
                MarkerColorProfile.from_dict(item)
                for item in getattr(self.monitor_config, "dual_marker_profiles", ())
            )
            path = save_dual_occlusion_evidence(
                root, raw=raw, profiles=profiles, candidates=tuple(candidates),
                frame_id=int(diagnostics.get("failed_frame_id", captured_at_ms)),
                captured_at_ms=int(captured_at_ms), status=state.status,
                reason=state.reason, diagnostics=diagnostics,
            )
        except Exception as exc:
            self._logger.warning("step=dual_motion.evidence_failed error=%s", exc)
            return
        self._dual_evidence_count += 1
        self._dual_evidence_signature = signature
        self._logger.info(
            "step=dual_motion.evidence_saved path=%s count=%s",
            path, self._dual_evidence_count,
        )

    def _render_dual_motion_state(self, state: Any, source_size: tuple[int, int]) -> None:
        self._latest_dual_state = state
        self._sync_follow_role_choices(state.players)
        visible = {
            identity: localization_display_point(
                point, source_size=source_size, transform=state.transform,
            )
            for identity, point in state.players.items() if point is not None
        }
        identities = tuple(state.players)
        primary = visible.get(identities[0]) if identities else None
        secondary = tuple(visible[identity] for identity in identities[1:] if identity in visible)
        if self._follow_runtime is not None:
            # The visual tracker and the follow timer share one map widget;
            # render the follow overlay once.  Do not first paint the plain
            # tracker overlay and then immediately replace it: that causes
            # duplicate Qt updates and briefly hides the predicted route.
            self._render_follow_overlay()
        elif self._dual_target_runtime is not None:
            self._render_dual_target_overlay()
        else:
            self.map_widget.set_overlay(
                position=primary,
                candidates=secondary,
                target=self._clicked_target_display,
            )
        focus = primary or (secondary[0] if secondary else None)
        if focus is not None:
            self.map_widget.focus_on_point(focus, zoom_multiplier=self.map_follow_zoom_multiplier)
        positions = " | ".join(
            f"{identity}: {point[0]:.1f},{point[1]:.1f}" if point is not None else f"{identity}: 未识别"
            for identity, point in state.players.items()
        )
        self.dual_motion_status_label.setText(
            f"双人实时：{state.status} | {state.reason} | {positions} | 墙体 {state.wall_quality:.2f}"
        )
