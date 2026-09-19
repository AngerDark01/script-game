"""Focused event workbench; navigation/follow execution remains elsewhere."""
from pathlib import Path

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QTabWidget, QTableWidget, QTableWidgetItem, QComboBox, QTextEdit, QLineEdit)
from auto_modules.paths import data_root
from auto_modules.application.event_workbench import EventWorkbenchService
from .action_sequence_editor import ChainEditor

KEY_OPTIONS = ['F1','F2','F3','F4','F5','F6','F7','F8','F9','F10','F11','F12',
               'W','A','S','D','Q','E','R','SPACE','UP','DOWN','LEFT','RIGHT']
CONTROLLER_SELECTIONS = {
    'Controller 1': (1,),
    'Controller 2': (2,),
    'Controller 1 + 2': (1, 2),
}


class EventWorkbenchPage(QWidget):
    def __init__(self, parent=None, *, root=None, service=None, communication_manager=None, communication_adapter=None):
        super().__init__(parent)
        config_root = Path(
            root or data_root() / 'events'
        )
        self.communication_manager = communication_manager
        self.communication_adapter = communication_adapter
        self.service = service or EventWorkbenchService(
            config_root,
            communication_manager=communication_manager,
            communication_adapter=communication_adapter,
        )
        self.events = self.service.load_local_events()
        self.remote_events = self.service.load_remote_events()
        self.routes_data = self.service.load_routes()
        self._shutdown = False
        self._build()
        self._refresh()
        self._refresh_routes()
        self.runtime_timer = QTimer(self)
        self.runtime_timer.setInterval(150)
        self.runtime_timer.timeout.connect(self._poll_runtime)
        self.runtime_timer.start()
        self.catalog_timer = QTimer(self)
        self.catalog_timer.setInterval(1000)
        self.catalog_timer.timeout.connect(self._refresh_remote_catalog)
        self.catalog_timer.start()
        self.service.start()
        self._poll_runtime()
        self._refresh_remote_catalog()

    def _visible_events(self):
        return [(event, False) for event in self.events if not event.get('deleted')] + [(event, True) for event in self.remote_events if not event.get('deleted')]

    def _event_names(self):
        return [str(event.get('name', '')) for event, _ in self._visible_events() if event.get('name')]

    def _build(self):
        self.setObjectName('eventWorkbench')
        self.setStyleSheet('''
        #eventWorkbench { background:#09111f; color:#e7eef8; }
        QPushButton { min-height:36px; padding:0 16px; border-radius:8px; border:1px solid #2e4967; background:#17283d; color:#e7eef8; }
        QPushButton:hover { background:#203954; border-color:#35b9f2; }
        QPushButton[role="primary"] { background:#1aa6dc; border-color:#43c7f3; color:#061321; font-weight:700; }
        QTabWidget::pane { border:0; }
        QTabBar::tab { background:#0e1a2b; color:#91a7bd; padding:14px 18px; margin:3px; border-radius:8px; min-width:130px; }
        QTabBar::tab:selected { background:#163653; color:#53c8f4; border:1px solid #2e9bc7; }
        QListWidget { background:#0d1929; border:1px solid #213750; padding:8px; border-radius:10px; }
        QListWidget::item { padding:13px 12px; border-radius:7px; color:#a9bbcf; }
        QListWidget::item:selected { background:#174363; color:#f3fbff; }
        QTableWidget { background:#0d1929; border:1px solid #213750; border-radius:8px; gridline-color:#1d3047; }
        QHeaderView::section { background:#15263b; color:#86a7c6; border:0; padding:9px; }
        ''')
        root = QVBoxLayout(self); root.setContentsMargins(24,20,24,24); root.setSpacing(14)
        head = QHBoxLayout(); root.addLayout(head)
        title_box=QVBoxLayout(); head.addLayout(title_box)
        kicker=QLabel('AUTOMATION STUDIO'); kicker.setStyleSheet('color:#6e9fc9; font-size:11px; font-weight:700;'); title_box.addWidget(kicker)
        title = QLabel('事件工作台'); title.setStyleSheet('font-size:26px; font-weight:800;'); title_box.addWidget(title)
        subtitle=QLabel('把按键动作编排成可复用事件，再路由到指定电脑和手柄。'); subtitle.setStyleSheet('color:#93a7bd;'); title_box.addWidget(subtitle)
        head.addStretch(); self.save = QPushButton('保存事件版本'); self.save.setProperty('role','primary'); self.save.clicked.connect(self._save); head.addWidget(self.save)
        self.status = QLabel('● 仅编辑配置'); self.status.setStyleSheet('color:#93a7bd;'); root.addWidget(self.status)
        self.catalog_status = QLabel('事件目录同步：后台中'); self.catalog_status.setStyleSheet('color:#6f9ab8;'); root.addWidget(self.catalog_status)
        buttons = QHBoxLayout(); root.addLayout(buttons)
        self.runtime_button = QPushButton('启动本机监控服务'); self.runtime_button.clicked.connect(self._toggle_runtime); buttons.addWidget(self.runtime_button)
        self.remote_button = QPushButton('启动远程事件监控'); self.remote_button.clicked.connect(self._toggle_remote_runtime); buttons.addWidget(self.remote_button)
        # Horizontal workspace tabs keep Chinese labels readable at normal widths.
        self.tabs = QTabWidget(); self.tabs.setTabPosition(QTabWidget.North); root.addWidget(self.tabs, 1)
        self._build_library(); self._build_routes(); self._build_runtime(); self._build_remote_sender()

    def _build_remote_sender(self):
        page = QWidget(); layout = QVBoxLayout(page)
        layout.addWidget(QLabel('远程事件发送：不依赖定位监视，只发送事件到已配对设备。'))
        self.remote_device = QLineEdit(); self.remote_device.setPlaceholderText('目标设备 ID'); layout.addWidget(self.remote_device)
        self.remote_event = QComboBox(); self.remote_event.setEditable(True)
        self.remote_event.setPlaceholderText('填写 A 端已有的事件名称')
        self.remote_event.addItems(self._event_names()); layout.addWidget(self.remote_event)
        self.remote_controller = QComboBox(); self.remote_controller.addItems(['Controller 1','Controller 2','Controller 1 + 2']); layout.addWidget(self.remote_controller)
        button = QPushButton('发送远程事件'); button.clicked.connect(self._send_remote_event); layout.addWidget(button)
        self.remote_status = QLabel('未发送'); layout.addWidget(self.remote_status); layout.addStretch()
        self.tabs.addTab(page, '远程发送')

    def _send_remote_event(self):
        try:
            controllers = CONTROLLER_SELECTIONS[self.remote_controller.currentText()]
            reply = self.service.send_remote_event(
                self.remote_device.text(),
                self.remote_event.currentText(),
                controllers,
            )
            self.remote_status.setText(f'发送成功：{reply}')
        except Exception as exc:
            self.remote_status.setText(f'发送失败：{exc}')

    def _build_library(self):
        page = QWidget(); layout = QHBoxLayout(page)
        self.list = QListWidget(); self.list.currentRowChanged.connect(self._select); layout.addWidget(self.list, 1)
        right = QVBoxLayout(); layout.addLayout(right, 3); actions = QHBoxLayout(); right.addLayout(actions)
        for text, cb in [('新建事件', self._new), ('编辑事件', self._edit), ('复制事件', self._copy), ('删除事件', self._remove)]:
            b = QPushButton(text); b.clicked.connect(cb)
            if text == '新建事件': b.setProperty('role', 'primary')
            if text == '删除事件': b.setStyleSheet('color:#ff9d9d; border-color:#70414a;')
            actions.addWidget(b)
        self.summary = QLabel('请选择一个事件'); self.summary.setWordWrap(True); right.addWidget(self.summary)
        self.track_table = QTableWidget(0, 5); self.track_table.setHorizontalHeaderLabels(['模式', '按钮/组合', '保持(ms)', '间隔(ms)', '轨道结束(ms)']); right.addWidget(self.track_table, 2)
        self.timeline = QLabel('时间线预览将在选择事件后显示'); self.timeline.setStyleSheet('padding: 16px; background: rgba(255,255,255,0.04);'); right.addWidget(self.timeline)
        self.tabs.addTab(page, '事件库')

    def _build_routes(self):
        page = QWidget(); layout = QVBoxLayout(page); layout.addWidget(QLabel('把来源电脑的快捷键或远程操作，路由到目标电脑和目标手柄。'))
        self.routes = QTableWidget(0, 5); self.routes.setHorizontalHeaderLabels(['来源设备', '触发键', '事件', '目标设备', '目标手柄']); layout.addWidget(self.routes, 1)
        row=QHBoxLayout(); add = QPushButton('新增触发规则'); add.clicked.connect(self._add_route); row.addWidget(add)
        remove=QPushButton('删除选中规则'); remove.clicked.connect(self._remove_route); remove.setStyleSheet('color:#ff9d9d; border-color:#70414a;'); row.addWidget(remove); row.addStretch(); layout.addLayout(row); self.tabs.addTab(page, '触发与路由')

    def _build_runtime(self):
        page = QWidget(); layout = QVBoxLayout(page); layout.addWidget(QLabel('显示远程事件的发送、接收和执行状态，不表示游戏内技能成功。'))
        self.runtime_table = QTableWidget(0, 6); self.runtime_table.setHorizontalHeaderLabels(['目标设备', '手柄', '事件', '状态', '当前轨道', '下一步']); layout.addWidget(self.runtime_table); self.tabs.addTab(page, '运行监控')
        layout.addWidget(QLabel('本机事件链路日志'))
        self.local_log = QTextEdit(); self.local_log.setReadOnly(True); self.local_log.setMaximumHeight(180)
        self.local_log.setStyleSheet('QTextEdit { background:#071321; color:#9fd7f5; border:1px solid #213750; border-radius:8px; padding:8px; font-family:Consolas; }')
        layout.addWidget(self.local_log)

    def _refresh(self):
        self.list.clear()
        for event, remote in self._visible_events():
            label = f"{event.get('name', '未命名事件')}  ·  {'远程只读' if remote else '本机可编辑'}  ·  v{event.get('revision', 1)}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, {'remote': remote, 'event': event})
            self.list.addItem(item)
        if self.list.count(): self.list.setCurrentRow(0)

    def _refresh_routes(self):
        self.routes.setRowCount(0)
        for route in self.routes_data:
            r=self.routes.rowCount(); self.routes.insertRow(r)
            self._set_route_row(r, route)

    def _set_route_row(self, row, route):
        source=QComboBox(); source.addItems(['本机','已配对设备']); source.setCurrentText(route.get('source','本机')); self.routes.setCellWidget(row,0,source)
        trigger=QComboBox(); trigger.addItems(KEY_OPTIONS); trigger.setCurrentText(route.get('trigger','F5')); self.routes.setCellWidget(row,1,trigger)
        event=QComboBox(); event.setEditable(True)
        event.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        event.setPlaceholderText('填写目标设备上的事件名称')
        names=self._event_names()
        existing=str(route.get('event','')).strip()
        if existing and existing not in names: names.insert(0, existing)
        event.addItems(names); event.setCurrentText(existing); self.routes.setCellWidget(row,2,event)
        target=QComboBox(); target.addItems(['本机','已配对设备']); target.setCurrentText(route.get('target','本机')); self.routes.setCellWidget(row,3,target)
        controller=QComboBox(); controller.addItems(['Controller 1','Controller 2','Controller 1 + 2']); controller.setCurrentText(route.get('controller','Controller 1')); self.routes.setCellWidget(row,4,controller)

    def _select(self, row):
        self.track_table.setRowCount(0)
        if row < 0 or row >= self.list.count():
            self.summary.setText('请选择一个事件')
            return
        data = self.list.item(row).data(Qt.ItemDataRole.UserRole) or {}
        event = data.get('event', {}); tracks = event.get('tracks', [])
        self.summary.setText(f"{event.get('name')}\n执行次数：{event.get('max_runs') or '不限'} · 循环：{'是' if event.get('loop') else '否'} · 结束：{event.get('end_ms') or '手动停止'}")
        for track in tracks:
            r = self.track_table.rowCount(); self.track_table.insertRow(r)
            for c, value in enumerate([track.get('mode', 'once'), '+'.join(track.get('buttons', [])), track.get('hold_ms', 0), track.get('interval_ms', ''), track.get('end_ms', '')]): self.track_table.setItem(r, c, QTableWidgetItem(str(value)))
        self.timeline.setText('时间线：' + '  |  '.join(f"{'+'.join(t.get('buttons', []))} {t.get('mode', 'once')}" for t in tracks) if tracks else '暂无轨道')

    def _new(self):
        draft = self.service.new_event_draft(
            dict(name='新事件', steps=[], tracks=[])
        )
        dialog = ChainEditor(draft, self)
        if dialog.exec(): self.events.append(dialog.value()); self._refresh(); self.list.setCurrentRow(len(self.events)-1)

    def _edit(self):
        row = self.list.currentRow()
        if row < 0: return
        data = self.list.item(row).data(Qt.ItemDataRole.UserRole) or {}
        if data.get('remote'):
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(self, '远程事件只读', '该事件由配对设备管理，请在事件所属设备上修改。')
            return
        local_row = self.events.index(data.get('event')) if data.get('event') in self.events else -1
        if local_row < 0: return
        try:
            dialog = ChainEditor(self.events[local_row], self)
            if dialog.exec():
                updated = {**self.events[local_row], **dialog.value()}
                self.events[local_row] = updated; self._refresh(); self.list.setCurrentRow(row)
        except Exception as exc:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(self, '打开事件失败', f'事件编辑器无法打开：{exc}')

    def _copy(self):
        row = self.list.currentRow()
        if row < 0: return
        current = self.list.item(row).data(Qt.ItemDataRole.UserRole) or {}
        if current.get('remote'): return
        item = self.service.new_event_draft(current.get('event'))
        item['name'] = item.get('name', '事件') + ' 副本'
        self.events.append(item); self._refresh(); self.list.setCurrentRow(len(self.events)-1)

    def _remove(self):
        row = self.list.currentRow()
        if row >= 0 and row < self.list.count():
            current = self.list.item(row).data(Qt.ItemDataRole.UserRole) or {}
            if current.get('remote'): return
        if row >= 0:
            current = self.list.item(row).data(Qt.ItemDataRole.UserRole) or {}
            if current.get('event') in self.events:
                self.events.remove(current['event'])
                self._refresh()

    def _add_route(self):
        r = self.routes.rowCount(); self.routes.insertRow(r)
        route=dict(source='本机',trigger='F5',event=self.events[0]['name'] if self.events else '',target='本机',controller='Controller 1')
        self._set_route_row(r,route); self.routes_data.append(route)

    def _remove_route(self):
        row=self.routes.currentRow()
        if row >= 0:
            self.routes.removeRow(row)
            if row < len(self.routes_data): self.routes_data.pop(row)

    def _save(self):
        self.routes_data=[]
        for r in range(self.routes.rowCount()):
            source=self.routes.cellWidget(r,0).currentText() if self.routes.cellWidget(r,0) else ''
            controller=self.routes.cellWidget(r,4).currentText() if self.routes.cellWidget(r,4) else ''
            values=[source]+[self.routes.cellWidget(r,c).currentText().strip() if self.routes.cellWidget(r,c) else '' for c in (1,2,3)]+[controller]
            self.routes_data.append(dict(zip(('source','trigger','event','target','controller'),values)))
        self.events = self.service.save(self.events, self.routes_data)
        self._refresh()
        self.status.setText('事件和路由已保存')

    def _toggle_runtime(self):
        enabled = not self.service.status().local_running
        if enabled:
            self._save()
        self.service.set_local_running(enabled)
        self._poll_runtime()

    def _toggle_remote_runtime(self):
        enabled = not self.service.status().remote_running
        if enabled:
            self._save()
        self.service.set_remote_running(enabled)
        self._poll_runtime()

    def _refresh_remote_catalog(self):
        latest = self.service.load_remote_events()
        if latest != self.remote_events:
            selected = self.list.currentRow()
            self.remote_events = latest
            self._refresh()
            if hasattr(self, 'remote_event'):
                current = self.remote_event.currentText()
                self.remote_event.blockSignals(True)
                self.remote_event.clear(); self.remote_event.addItems(self._event_names()); self.remote_event.setCurrentText(current)
                self.remote_event.blockSignals(False)
            names = self._event_names()
            if hasattr(self, 'routes'):
                for row in range(self.routes.rowCount()):
                    combo = self.routes.cellWidget(row, 2)
                    if combo is not None:
                        value = combo.currentText(); combo.blockSignals(True); combo.clear(); combo.addItems(names); combo.setCurrentText(value); combo.blockSignals(False)
            if 0 <= selected < self.list.count():
                self.list.setCurrentRow(selected)
        status = self.service.status()
        if status.error:
            self.catalog_status.setText(f'事件目录同步：等待连接 ({status.error})')
        elif status.peer_count:
            self.catalog_status.setText(
                f'事件目录同步：已连接 {status.peer_count} 台设备，'
                f'已读取 {len(self.remote_events)} 个远程事件'
            )
        else:
            self.catalog_status.setText('事件目录同步：等待共享同步通道')

    def shutdown(self):
        """Stop workbench-owned workers before the host process closes."""
        if self._shutdown:
            return
        self._shutdown = True
        self.catalog_timer.stop()
        self.runtime_timer.stop()
        self.service.shutdown()

    def closeEvent(self, event):
        self.shutdown()
        super().closeEvent(event)

    def _poll_runtime(self):
        status = self.service.status()
        self.runtime_button.setText(
            '停止本机监控服务' if status.local_running else '启动本机监控服务'
        )
        self.remote_button.setText(
            '停止远程事件监控' if status.remote_running else '启动远程事件监控'
        )
        detail = f' · 最近：{status.last_event}' if status.last_event else ''
        if status.error:
            self.status.setText(f'事件服务等待连接：{status.error}')
        elif status.local_running and status.remote_running:
            self.status.setText(
                f'本机与远程事件监听中 · 本机 {status.trigger_count} 次 · '
                f'远程 {status.receive_count} 次{detail}'
            )
        elif status.local_running:
            self.status.setText(f'本机事件监听中 · 已触发 {status.trigger_count} 次{detail}')
        elif status.remote_running:
            self.status.setText(f'远程事件监听中 · 已接收 {status.receive_count} 次{detail}')
        else:
            self.status.setText('事件服务后台运行；监控已停止')
        self.local_log.setPlainText('\n'.join(self.service.recent_log_lines(limit=80)))
