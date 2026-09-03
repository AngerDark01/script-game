from __future__ import annotations

from PySide6.QtWidgets import QVBoxLayout

from ..route import RoutePanelController
from .compact import NavigationCompactUiController
from .components.map_view import build_navigation_map_view
from .components.status import build_status_label
from .components.toolbars import (
    build_map_selector_bar,
    build_navigation_actions_bar,
    build_route_tools_bar,
    build_utility_bar,
)


def build_navigation_ui(owner) -> None:
    """Build the navigation page controls and attach them to the owner widget."""
    layout = QVBoxLayout(owner)
    layout.setContentsMargins(8, 8, 8, 8)
    layout.setSpacing(6)

    owner.map_selector_bar = build_map_selector_bar(owner)
    owner.navigation_actions_bar = build_navigation_actions_bar(owner)
    owner.utility_bar = build_utility_bar(owner)
    owner.route_tools_bar = build_route_tools_bar(owner)

    layout.addWidget(owner.map_selector_bar)
    layout.addWidget(owner.navigation_actions_bar)
    layout.addWidget(owner.utility_bar)
    layout.addWidget(owner.route_tools_bar)

    layout.addWidget(build_navigation_map_view(owner), 1)
    layout.addWidget(build_status_label(owner))

    owner.route_panel = RoutePanelController(
        owner.route_editor,
        set_exit_button=owner.btn_set_exit,
        add_required_button=owner.btn_add_required,
        undo_required_button=owner.btn_undo_required,
        add_guide_button=owner.btn_add_guide,
        undo_guide_button=owner.btn_undo_guide,
        clear_route_button=owner.btn_clear_route,
        save_route_button=owner.btn_save_route,
        auto_nav_button=owner.btn_auto_nav,
        status_label=owner.status_label,
    )

    owner.navigation_compact_controller = NavigationCompactUiController(
        owner,
        route_tools_bar=owner.route_tools_bar,
    )
    owner.navigation_compact_controller.set_compact_mode(True)
