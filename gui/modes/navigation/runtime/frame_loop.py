from __future__ import annotations

import time

from core.events.debug import event_log

from ..event_adapter import event_status_text
from ..input import execute_navigation_intent
from ..presentation import (
    append_navigation_status_suffix,
    show_navigation_arrived,
    show_navigation_failed,
    show_navigation_relocalizing,
    show_navigation_runtime_status,
    update_localization_view,
)
from .intent_consumption import consume_navigation_intent
from .localization_tick import capture_navigation_localization_tick
from .loop import observe_navigation_events, update_navigation_task_controller
from .loop_helpers import compute_navigation_lookahead, should_run_navigation_tasks


class NavigationRuntimeFrameLoop:
    """Own one navigation timer tick for the navigation page."""

    def __init__(self, owner) -> None:
        self.owner = owner

    def run(self) -> None:
        owner = self.owner
        frame_tick = capture_navigation_localization_tick(
            build_capture_geometry=owner._build_capture_geometry,
            screen_capture=owner.app_context.screen_capture,
            nav_config=owner.nav_config,
            nav_core=owner.nav_core,
            tracker=owner.app_context.tracker,
            previous_player_local_pos=owner._current_player_local_pos,
        )
        if frame_tick is None:
            return

        capture_rect = frame_tick.capture_rect
        frame = frame_tick.frame
        player_pos = frame_tick.player_pos
        localization = frame_tick.localization
        owner._current_capture_rect = capture_rect
        owner._current_player_local_pos = player_pos
        owner._latest_minimap_frame = frame
        owner._latest_minimap_capture_rect = capture_rect
        owner._latest_minimap_player_local_pos = player_pos

        now_ms = int(time.time() * 1000)
        event_tick = observe_navigation_events(
            event_coordinator=owner.event_coordinator,
            event_observer=getattr(owner, "event_async_observer", None),
            build_event_tick=owner._build_event_tick,
            render_event_overlay=owner._render_event_overlay,
            event_dialog=owner.event_dialog,
            now_ms=now_ms,
            frame=frame,
            player_pos=player_pos,
            localized_pos=localization.localized_pos,
            confidence=localization.confidence,
        )

        intent = None
        if should_run_navigation_tasks(
            auto_navigation_enabled=owner.auto_navigation_enabled,
            manual_event_test_active=owner.portal_test_controller.active,
        ):
            lookahead = compute_navigation_lookahead(
                capture_width=capture_rect["width"],
                draw_scale=owner.nav_core.draw_scale,
            )
            intent = update_navigation_task_controller(
                navigation_task_controller=owner.navigation_task_controller,
                localization=localization,
                route_data=owner.route_data,
                event_coordinator=owner.event_coordinator,
                event_tick=event_tick,
                nav_core=owner.nav_core,
                path_finder=owner.app_context.path_finder,
                now_ms=now_ms,
                lookahead_distance=lookahead,
                manual_event_only=bool(
                    owner.portal_test_controller.active and not owner.auto_navigation_enabled
                ),
            )

        owner.player_item = update_localization_view(
            scene=owner.scene,
            view=owner.view,
            player_item=owner.player_item,
            nav_core=owner.nav_core,
            localization=localization,
            capture_rect=capture_rect,
            player_local_pos=player_pos,
            update_monitor_rect=owner._update_monitor_rect,
            update_game_view_rect=owner._update_game_view_rect,
        )

        show_navigation_runtime_status(
            owner.status_label,
            localized_pos=localization.localized_pos,
            confidence=localization.confidence,
            capture_rect=capture_rect,
            intent=intent,
            event_status=event_status_text(owner.event_coordinator),
        )

        if intent:
            owner._render_route_overlay(
                current_path=intent.path,
                current_subgoal=intent.subgoal,
                current_required_index=intent.required_index,
                current_guide_index=None,
                current_target_kind=intent.task_kind,
            )
            consumption = consume_navigation_intent(
                intent,
                now_ms=now_ms,
                request_global_relocalization=owner.nav_core.request_global_relocalization,
                log_event=event_log,
                show_relocalizing=lambda: show_navigation_relocalizing(owner.status_label),
                execute_intent=self._execute_navigation_intent,
                is_manual_event_test_active=lambda: owner.portal_test_controller.active,
                stop_manual_event_test=lambda reason: owner._set_portal_manual_test_active(False, reason=reason),
                stop_navigation_tasks=owner.navigation_task_controller.stop,
                disable_game_input_mode=lambda: owner._set_game_input_window_mode(False),
                reset_auto_navigation_button=lambda: owner.btn_auto_nav.setChecked(False),
                show_arrived=lambda: show_navigation_arrived(owner.status_label),
                show_failed=lambda message: show_navigation_failed(owner.status_label, message),
            )
            if consumption.skip_remaining_frame:
                return
            if consumption.terminal_navigation:
                owner.auto_navigation_enabled = False
        elif owner.route_data:
            owner._render_route_overlay()

    def _execute_navigation_intent(self, intent, now_ms: int) -> None:
        owner = self.owner
        result = execute_navigation_intent(
            intent,
            now_ms,
            motion_controller=owner.motion_controller,
            navigation_task_controller=owner.navigation_task_controller,
            enable_game_input_mode=lambda: owner._set_game_input_window_mode(True),
        )
        append_navigation_status_suffix(owner.status_label, result.status_suffix)
