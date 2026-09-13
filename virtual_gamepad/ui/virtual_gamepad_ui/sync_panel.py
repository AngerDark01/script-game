"""LAN configuration UI. All network I/O remains in the host, outside Qt."""
from __future__ import annotations

import threading
import uuid
from typing import Any, Callable

from PySide6.QtCore import QObject, QRunnable, QThreadPool, QTimer, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QLineEdit,
    QComboBox, QSpinBox, QPushButton, QCheckBox, QListWidget, QListWidgetItem,
    QMessageBox, QScrollArea,
)
from PySide6.QtCore import Qt


class _Signals(QObject):
    done = Signal(object)


class _Request(QRunnable):
    def __init__(self, factory, signals, command, payload, closing=False):
        super().__init__()
        self.factory, self.signals, self.command, self.payload = factory, signals, command, payload
        self.closing = closing

    def run(self):
        client, watchdog = None, None
        result = {"command": self.command, "closing": self.closing, "sequence": self.payload.get("_uiSequence", 0)}
        try:
            client = self.factory()
            # Native pipe close cancels a stuck read without holding the GUI thread.
            watchdog = threading.Timer(1.5, client.close)
            watchdog.daemon = True
            watchdog.start()
            client.connect(timeout=0.25)
            value = client.request(self.command, self.payload)
            if value.get("ok") is False:
                raise RuntimeError(str(value.get("error", "操作失败")))
            result["status"] = value.get("status", value)
        except Exception as exc:
            # An older host that explicitly does not implement sync cannot have
            # an active LAN session. Do not mask connection/timeout failures.
            if not (self.command == "sync.stop" and str(exc) == "unknown_type: Unknown message type: sync.stop"):
                result["error"] = str(exc)
        finally:
            if watchdog: watchdog.cancel()
            if client:
                try: client.close()
                except Exception: pass
        try: self.signals.done.emit(result)
        except RuntimeError: pass


class SyncPanel(QWidget):
    shutdown_finished = Signal(bool, str)

    def __init__(self, client_factory: Callable[[], Any], *, demo=False, parent=None):
        super().__init__(parent)
        self.factory, self.demo = client_factory, demo
        self.busy = False
        self.closing = False
        self._source = "lan-panel:" + uuid.uuid4().hex
        self._sequence = 0
        self._status: dict = {}
        self._pending_command = None
        self._stop_inflight = False
        self._pending_stops: list[dict] = []
        self._signals = _Signals(self)
        self._signals.done.connect(self._complete)
        self._timer = QTimer(self)
        self._timer.setInterval(500)
        self._timer.timeout.connect(self.refresh)
        self._build()

    def _build(self):
        # Keep popup lists readable on the dark workspace.  The popup is a
        # native view and does not inherit the panel's line-edit styling.
        self.setStyleSheet('''
            QComboBox { min-height:34px; padding:0 10px; border:1px solid #29435f;
                        border-radius:7px; background:#0d1a2b; color:#e7eef8; }
            QComboBox:hover, QComboBox:focus { border-color:#38bce9; }
            QComboBox QAbstractItemView { background:#102238; color:#e7eef8;
                        selection-background-color:#1c6a93; selection-color:#ffffff;
                        border:1px solid #315775; padding:4px; }
            QComboBox QAbstractItemView::item { min-height:30px; padding:5px 10px; }
            QComboBox QAbstractItemView::item:hover { background:#174363; color:#ffffff; }
        ''')
        outer = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)
        body = QWidget()
        scroll.setWidget(body)
        layout = QVBoxLayout(body)
        layout.setSpacing(12)
        title = QLabel("局域网设备同步")
        title.setProperty("role", "section-title")
        layout.addWidget(title)
        hint = QLabel("输入同步会接管手柄；位置与事件共享只传数据，不接管手柄。配对后仍需建立连接；F9 可紧急停止。")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.identity = QLabel("本机设备：等待宿主连接")
        self.identity.setTextFormat(Qt.TextFormat.PlainText)
        self.message = QLabel("")
        self.message.setWordWrap(True)
        self.message.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.identity)
        layout.addWidget(self.message)
        layout.addWidget(self._section('连接模式', '先选择本机角色，再保存设置；配对完成后仍需单独开启同步通道。'))
        form = QFormLayout()
        self.mode = QComboBox()
        for label, value in (("关闭", "off"), ("发送手柄：用本机控制其他电脑", "send"), ("接收手柄：由主设备控制本机", "receive"), ("事件/位置共享（不接管手柄）", "share")):
            self.mode.addItem(label, value)
        self.name = QLineEdit()
        self.name.setPlaceholderText("本机名称")
        self.address = QComboBox()
        self.address.setEditable(True)
        self.address.lineEdit().setPlaceholderText("选择本机局域网地址")
        self.rate = QComboBox()
        self.rate.addItem("125 Hz（低延迟）", 125)
        self.rate.addItem("60 Hz", 60)
        self.port = QSpinBox()
        self.port.setRange(1024, 65535)
        self.port.setValue(45873)
        self.c1, self.c2 = QCheckBox("Controller 1"), QCheckBox("Controller 2")
        self.c1.setChecked(True)
        self.c2.setChecked(True)
        routes = QHBoxLayout()
        routes.addWidget(self.c1)
        routes.addWidget(self.c2)
        form.addRow("模式", self.mode)
        form.addRow("设备名称", self.name)
        form.addRow("本机网络地址", self.address)
        form.addRow("端口", self.port)
        form.addRow("同步频率", self.rate)
        form.addRow("控制器范围", routes)
        self.receive_positions = QCheckBox("允许已配对设备共享位置")
        self.receive_events = QCheckBox("允许已配对设备发送行为事件")
        form.addRow("数据共享许可", self.receive_positions)
        form.addRow("", self.receive_events)
        layout.addLayout(form)
        buttons = QHBoxLayout()
        self.apply_button = self._button("保存并应用设置", self.apply_settings, buttons)
        self.receive_button = self._button("允许接收所选手柄", lambda: self.command("sync.start", {"controllers": self.controllers()}), buttons)
        self.receive_button.setEnabled(False)
        self._button("停止全部同步", lambda: self.command("sync.stop"), buttons)
        layout.addLayout(buttons)
        layout.addWidget(self._section('设备配对', '配对只建立可信设备关系，不会自动接管手柄。事件发送使用“事件/位置共享”模式；只有“发送手柄/接收手柄”模式才会传输手柄状态。'))
        pair_row = QHBoxLayout()
        self.code = QLabel("配对码：未开启")
        pair_row.addWidget(self.code)
        self.code_button = self._button("生成临时配对码", lambda: self.command("sync.pairing"), pair_row)
        self.code_button.setEnabled(False)
        layout.addLayout(pair_row)
        layout.addWidget(QLabel("发现的设备（选中可填入地址；也可手动输入）"))
        self.discovered = QListWidget()
        self.discovered.setMaximumHeight(100)
        self.discovered.itemClicked.connect(self._discovered_selected)
        layout.addWidget(self.discovered)
        pair_form = QHBoxLayout()
        self.peer_address, self.peer_code = QLineEdit(), QLineEdit()
        self.peer_address.setPlaceholderText("对方局域网 IP")
        self.peer_port = QSpinBox()
        self.peer_port.setRange(1024, 65535)
        self.peer_port.setValue(45873)
        self.peer_code.setPlaceholderText("对方显示的设备码")
        pair_form.addWidget(self.peer_address, 2)
        pair_form.addWidget(self.peer_port)
        pair_form.addWidget(self.peer_code)
        self.pair_button = self._button("发起配对", self.pair, pair_form)
        self.pair_button.setEnabled(False)
        layout.addLayout(pair_form)
        layout.addWidget(QLabel("待确认配对：核对两台电脑显示的校验码一致，再确认"))
        self.pending = QListWidget()
        self.pending.setMaximumHeight(110)
        layout.addWidget(self.pending)
        confirm_row = QHBoxLayout()
        self._button("校验一致，确认配对", lambda: self.confirm(True), confirm_row)
        self._button("拒绝", lambda: self.confirm(False), confirm_row)
        layout.addLayout(confirm_row)
        layout.addWidget(self._section('已配对设备', '选择设备后，再按需启动输入、事件或位置同步。'))
        layout.addWidget(QLabel("已配对设备：选中设备，使用上方控制器范围开始同步"))
        self.peers = QListWidget()
        self.peers.setMinimumHeight(100)
        layout.addWidget(self.peers)
        actions = QHBoxLayout()
        self.send_button = self._button("启动全部事件通道", self.start_all_events, actions)
        self.send_button.setEnabled(False)
        self._button("启动选中设备", self.start_peer, actions)
        self._button("停止选中设备", lambda: self.peer_command("sync.stop"), actions)
        self._button("重置连接状态", lambda: self.peer_command("sync.reset"), actions)
        self._button("移除选中设备", self.forget_peer, actions)
        layout.addLayout(actions)
        layout.addWidget(self._section('安全提示', '停止同步会清理远程按键并让虚拟手柄回中，不会删除配对关系。'))
        layout.addStretch()

    @staticmethod
    def _section(title, subtitle):
        box = QWidget(); layout = QVBoxLayout(box); layout.setContentsMargins(0, 14, 0, 4); layout.setSpacing(2)
        label = QLabel(title); label.setStyleSheet('font-size:14px; font-weight:700; color:#e7eef8;')
        hint = QLabel(subtitle); hint.setWordWrap(True); hint.setStyleSheet('font-size:11px; color:#8fa6bd;')
        layout.addWidget(label); layout.addWidget(hint)
        return box

    def _button(self, label, callback, layout):
        button = QPushButton(label)
        if '停止' in label or '拒绝' in label or '移除' in label:
            button.setStyleSheet('color:#ff9d9d; border-color:#70414a;')
        button.clicked.connect(callback)
        layout.addWidget(button)
        return button

    def controllers(self):
        return [n for n, check in ((1, self.c1), (2, self.c2)) if check.isChecked()]

    def apply_settings(self):
        payload = {"mode": self.mode.currentData(), "port": self.port.value(), "controllers": self.controllers(), "rateHz": self.rate.currentData()}
        payload.update(receivePositions=self.receive_positions.isChecked(), receiveEvents=self.receive_events.isChecked())
        if self.name.text().strip(): payload["name"] = self.name.text().strip()
        if self.address.currentText().strip(): payload["bindAddress"] = self.address.currentText().strip()
        self.command("sync.configure", payload)

    def pair(self):
        address = self.peer_address.text().strip()
        code = self.peer_code.text().strip()
        if not address:
            self.message.setText("请先填写对方设备的局域网 IP 地址。")
            self.peer_address.setFocus()
            return
        if len(code) != 8 or not code.isascii() or not code.isdigit():
            self.message.setText("配对码必须是对方设备显示的 8 位数字。")
            self.peer_code.setFocus()
            return
        self.message.setText("正在发起配对，请等待对方的待确认请求。")
        self.command("sync.pair", {"address": address, "port": self.peer_port.value(), "code": code})

    def confirm(self, allow):
        item = self.pending.currentItem()
        if item: self.command("sync.confirm", {"requestId": item.data(Qt.ItemDataRole.UserRole)["requestId"], "allow": allow})

    def start_peer(self):
        self.peer_command("sync.start", {"controllers": self.controllers()})

    def start_all_events(self):
        """Start one data-only event session for every paired peer."""
        if self._status.get("mode") != "share":
            self.message.setText("只有“位置与事件共享”模式支持同时启动全部事件通道。")
            return
        self.command("sync.start", {"controllers": [], "broadcast": True})

    def peer_command(self, command, extra=None):
        item = self.peers.currentItem()
        if item: self.command(command, {"deviceId": item.data(Qt.ItemDataRole.UserRole)["deviceId"], **(extra or {})})

    def forget_peer(self):
        if self.peers.currentItem() and QMessageBox.question(self, "移除配对", "移除后需要重新配对，确定移除？") == QMessageBox.StandardButton.Yes:
            self.peer_command("sync.forget")

    def _discovered_selected(self, item):
        peer = item.data(Qt.ItemDataRole.UserRole)
        self.peer_address.setText(peer.get("address", ""))
        self.peer_port.setValue(peer.get("port", 45873))

    def command(self, command, payload=None):
        if self.demo:
            self.message.setText("演示模式不会建立网络连接。")
            return
        if self.closing: return
        if command == "sync.stop":
            # Stop supersedes any queued start and fences any in-flight request.
            self._pending_command = None
            if self._stop_inflight:
                requested = dict(payload or {})
                if "deviceId" not in requested:
                    self._pending_stops = [{}]
                elif not any("deviceId" not in p for p in self._pending_stops) and requested not in self._pending_stops:
                    self._pending_stops.append(requested)
                return
            self._stop_inflight = True
        elif self.busy:
            # The periodic status poll must never start a second pipe request
            # while a user action (especially pairing) is in flight.  Starting
            # it here races the action response and makes the button appear to
            # do nothing because the older response is discarded by sequence.
            if command == "sync.status":
                return
            if command != "sync.status":
                if self._pending_command is None:
                    self._pending_command = (command, payload)
                    self.message.setText("操作已排队，等待当前请求完成…")
                else:
                    self.message.setText("已有操作等待处理，请稍候。")
            return
        self.busy = True
        self._sequence += 1
        payload = {**(payload or {}), "_uiSource": self._source, "_uiSequence": self._sequence}
        self.message.setText("正在处理…")
        QThreadPool.globalInstance().start(_Request(self.factory, self._signals, command, payload))

    def refresh(self):
        if self.isVisible(): self.command("sync.status")

    def _complete(self, result):
        if result.get("closing"):
            self.shutdown_finished.emit(not bool(result.get("error")), result.get("error", ""))
            return
        if result.get("sequence", self._sequence) < self._sequence:
            return
        self.busy = False
        if result.get("command") == "sync.stop":
            self._stop_inflight = False
        if self.closing: return
        if result.get("error"):
            self.message.setText(result["error"])
        else:
            self.render(result.get("status", {}))
        if self._pending_stops:
            payload = self._pending_stops.pop(0)
            self.command("sync.stop", payload)
        elif self._pending_command is not None:
            command, payload = self._pending_command
            self._pending_command = None
            self.command(command, payload)

    @staticmethod
    def _fill(widget, rows, text, key):
        current = widget.currentItem()
        selected = current.data(Qt.ItemDataRole.UserRole).get(key) if current else None
        widget.clear()
        for row in rows:
            item = QListWidgetItem(text(row))
            item.setData(Qt.ItemDataRole.UserRole, row)
            widget.addItem(item)
            if row.get(key) == selected: widget.setCurrentItem(item)

    def render(self, status):
        first = not self._status
        self._status = status
        applied_mode = status.get("mode", "off")
        ready = status.get("networkReady", False)
        self.receive_button.setEnabled(ready and applied_mode == "receive")
        self.code_button.setEnabled(ready and applied_mode in ("receive", "share"))
        self.pair_button.setEnabled(ready and applied_mode in ("send", "share"))
        self.send_button.setEnabled(ready and applied_mode in ("send", "share"))
        pairing_state = status.get("pairingState", "idle")
        pairing_labels = {"connecting": "正在连接对方设备", "waiting-confirmation": "等待对方确认配对", "paired": "配对已完成", "failed": "配对失败"}
        if pairing_state in pairing_labels and not status.get("error"):
            self.message.setText(pairing_labels[pairing_state])
        self.identity.setText(f"本机：{status.get('name', '')}  ·  {status.get('deviceId', '')}")
        labels = {"off": "关闭", "send": "发送", "receive": "接收", "share": "位置与事件共享"}
        self.message.setText(status.get("error") or f"当前模式：{labels.get(status.get('mode'), '等待连接')} · 网络：{'已就绪' if ready else '未就绪'} · 接收许可：{status.get('remoteEnabled', [])}")
        self.code.setText("配对码：" + (status.get("pairingCode") or "未开启"))
        if pairing_state in pairing_labels and not status.get("error"):
            self.message.setText(pairing_labels[pairing_state])
        if first:
            self.receive_positions.setChecked(status.get("receivePositions", False))
            self.receive_events.setChecked(status.get("receiveEvents", False))
            self.mode.setCurrentIndex(max(0, self.mode.findData(status.get("mode", "off"))))
            self.name.setText(status.get("name", ""))
            self.address.clear()
            self.address.addItems(status.get("addresses", []))
            self.address.setCurrentText(status.get("bindAddress", ""))
            self.rate.setCurrentIndex(max(0, self.rate.findData(status.get("rateHz", 125))))
            self.port.setValue(status.get("port", 45873))
            for n, check in ((1, self.c1), (2, self.c2)):
                check.setChecked(n in status.get("controllers", [1, 2]))
        self._fill(self.discovered, status.get("discovered", []), lambda p: f"{p.get('name')} · {p.get('address')}:{p.get('port')}", "deviceId")
        self._fill(self.pending, status.get("pending", []), lambda p: f"{p.get('name')} · 校验码 {p.get('fingerprint')} · {'本机已确认' if p.get('confirmed') else '等待确认'}", "requestId")
        def peer_text(p):
            if p.get('error'):
                state = '连接异常'
            elif p.get('connecting'):
                state = '连接中'
            elif p.get('syncing'):
                state = '事件通道已连接' if p.get('dataOnly') else '手柄通道已连接'
            elif p.get('connected'):
                state = '已建立控制连接'
            else:
                state = '已配对，未启动通道'
            return f"{p.get('name')} · {state} · C{p.get('controllers', [])} · RTT {p.get('rttMs', '—')}ms {p.get('error') or ''}"
        self._fill(self.peers, status.get("peers", []), peer_text, "deviceId")

    def showEvent(self, event):
        super().showEvent(event)
        if not self.closing:
            self._timer.start()
            self.refresh()

    def hideEvent(self, event):
        self._timer.stop()
        super().hideEvent(event)

    def shutdown(self):
        self.closing = True
        self._pending_command = None
        self._pending_stops.clear()
        self._timer.stop()
        self.setEnabled(False)
        if self.demo:
            self.shutdown_finished.emit(True, "")
            return
        # Newer sequence fences a command that was queued before shutdown.
        self._sequence += 1
        QThreadPool.globalInstance().start(_Request(self.factory, self._signals, "sync.stop",
            {"_uiSource": self._source, "_uiSequence": self._sequence}, closing=True))
