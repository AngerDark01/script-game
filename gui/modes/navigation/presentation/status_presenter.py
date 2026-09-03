from __future__ import annotations


def build_navigation_status_text(
    *,
    localized_pos,
    confidence: float,
    capture_rect: dict,
    intent=None,
    event_status: str = "",
) -> str:
    if localized_pos is not None:
        x, y = localized_pos
        status_text = (
            f"位置: ({int(x)}, {int(y)}) | 置信度: {confidence:.2f} | "
            f"监视: {capture_rect['width']}x{capture_rect['height']}"
        )
    else:
        status_text = f"定位中... 监视: {capture_rect['width']}x{capture_rect['height']}"

    if intent:
        if intent.message:
            status_text += f" | 导航: {intent.message}"
        if intent.path_kind and intent.path_kind != "none":
            status_text += f" | path:{intent.path_kind}"
    if event_status:
        status_text += f" | {event_status}"
    return status_text


def show_navigation_runtime_status(
    status_label,
    *,
    localized_pos,
    confidence: float,
    capture_rect: dict,
    intent=None,
    event_status: str = "",
) -> None:
    status_label.setText(
        build_navigation_status_text(
            localized_pos=localized_pos,
            confidence=confidence,
            capture_rect=capture_rect,
            intent=intent,
            event_status=event_status,
        )
    )


def append_navigation_status_suffix(status_label, suffix: str | None) -> None:
    if suffix:
        status_label.setText(f"{status_label.text()} | {suffix}")


def show_navigation_relocalizing(status_label) -> None:
    append_navigation_status_suffix(status_label, "正在重新定位")


def show_navigation_arrived(status_label) -> None:
    status_label.setText("已到达出口区域")


def show_navigation_failed(status_label, message: str | None) -> None:
    status_label.setText(message or "自动导航失败")
