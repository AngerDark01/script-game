from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QTableWidget, QTableWidgetItem


FULL_TASK_HEADERS = [
    "ID",
    "事件",
    "状态",
    "识别次数",
    "置信度",
    "地图坐标",
    "尝试次数",
    "最近识别",
]

COMPACT_TASK_HEADERS = [
    "事件",
    "状态",
    "置信度",
    "地图坐标",
]


def configure_task_table(table: QTableWidget, *, compact: bool = False) -> None:
    """Apply common read-only task-table behavior."""
    table.setColumnCount(len(COMPACT_TASK_HEADERS if compact else FULL_TASK_HEADERS))
    table.setHorizontalHeaderLabels(COMPACT_TASK_HEADERS if compact else FULL_TASK_HEADERS)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
    table.setEditTriggers(QAbstractItemView.NoEditTriggers)
    table.setSelectionBehavior(QAbstractItemView.SelectRows)


def render_task_rows(table: QTableWidget, tasks: list, *, compact: bool = False) -> None:
    """Render live event task state rows into a full or compact task table."""
    table.setRowCount(len(tasks))
    for row, task in enumerate(tasks):
        if compact:
            _set_item(table, row, 0, task.event_type)
            _set_item(table, row, 1, state_text(task.state))
            _set_item(table, row, 2, f"{float(task.confidence):.2f}")
            _set_item(table, row, 3, f"({task.global_pos[0]}, {task.global_pos[1]})")
            continue
        _set_item(table, row, 0, task.id)
        _set_item(table, row, 1, task.event_type)
        _set_item(table, row, 2, state_text(task.state))
        _set_item(table, row, 3, str(task.seen_count))
        _set_item(table, row, 4, f"{float(task.confidence):.2f}")
        _set_item(table, row, 5, f"({task.global_pos[0]}, {task.global_pos[1]})")
        _set_item(table, row, 6, str(task.attempts))
        _set_item(table, row, 7, str(task.last_seen_ms))


def state_text(state) -> str:
    value = getattr(state, "value", str(state))
    return {
        "observed": "已发现",
        "pending": "待处理",
        "running": "处理中",
        "completed": "已完成",
        "failed": "失败",
        "ignored": "已忽略",
    }.get(str(value).lower(), str(value))


def _set_item(table: QTableWidget, row: int, column: int, text: str) -> None:
    item = QTableWidgetItem(text)
    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
    table.setItem(row, column, item)
