"""Focused event workbench; navigation/follow execution remains elsewhere."""
from copy import deepcopy
from pathlib import Path
import json
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QTabWidget, QTableWidget, QTableWidgetItem, QComboBox)
from core.runtime_paths import data_root
from core.runtime.local_event_runtime import LocalEventRuntime
from ..follow.editors import ChainEditor

KEY_OPTIONS = ['F1','F2','F3','F4','F5','F6','F7','F8','F9','F10','F11','F12',
               'W','A','S','D','Q','E','R','SPACE','UP','DOWN','LEFT','RIGHT']


class EventWorkbenchPage(QWidget):
    def __init__(self, parent=None, *, root=None):
        super().__init__(parent)
        self.path = Path(root or data_root(Path(__file__).resolve().parents[3]) / 'configs' / 'events') / 'events.json'
        self.routes_path = self.path.with_name('routes.json')
        self.events = self._load(); self.routes_data = self._load_routes(); self._build(); self._refresh(); self._refresh_routes()
        self.runtime = LocalEventRuntime(root=self.path.parent)

    def _load(self):
        try:
            data = json.loads(self.path.read_text(encoding='utf-8'))
            return data if isinstance(data, list) else []
        except (OSError, ValueError): return []

    def _load_routes(self):
        try:
            data=json.loads(self.routes_path.read_text(encoding='utf-8'))
            return data if isinstance(data,list) else []
        except (OSError, ValueError): return []

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
        self.runtime_button = QPushButton('启动本机事件测试'); self.runtime_button.clicked.connect(self._toggle_runtime); root.addWidget(self.runtime_button)
        # Horizontal workspace tabs keep Chinese labels readable at normal widths.
        self.tabs = QTabWidget(); self.tabs.setTabPosition(QTabWidget.North); root.addWidget(self.tabs, 1)
        self._build_library(); self._build_routes(); self._build_runtime()

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
        self.runtime = QTableWidget(0, 6); self.runtime.setHorizontalHeaderLabels(['目标设备', '手柄', '事件', '状态', '当前轨道', '下一步']); layout.addWidget(self.runtime); self.tabs.addTab(page, '运行监控')

    def _refresh(self):
        self.list.clear(); self.list.addItems([e.get('name', '未命名事件') for e in self.events])
        if self.events: self.list.setCurrentRow(0)

    def _refresh_routes(self):
        self.routes.setRowCount(0)
        for route in self.routes_data:
            r=self.routes.rowCount(); self.routes.insertRow(r)
            self._set_route_row(r, route)

    def _set_route_row(self, row, route):
        source=QComboBox(); source.addItems(['本机','已配对设备']); source.setCurrentText(route.get('source','本机')); self.routes.setCellWidget(row,0,source)
        trigger=QComboBox(); trigger.addItems(KEY_OPTIONS); trigger.setCurrentText(route.get('trigger','F5')); self.routes.setCellWidget(row,1,trigger)
        event=QComboBox(); event.addItems([str(e.get('name','')) for e in self.events if e.get('name')]); event.setCurrentText(route.get('event','')); self.routes.setCellWidget(row,2,event)
        target=QComboBox(); target.addItems(['本机','已配对设备']); target.setCurrentText(route.get('target','本机')); self.routes.setCellWidget(row,3,target)
        controller=QComboBox(); controller.addItems(['Controller 1','Controller 2','Controller 1 + 2']); controller.setCurrentText(route.get('controller','Controller 1')); self.routes.setCellWidget(row,4,controller)

    def _select(self, row):
        self.track_table.setRowCount(0)
        if row < 0 or row >= len(self.events): self.summary.setText('请选择一个事件'); return
        event = self.events[row]; tracks = event.get('tracks', [])
        self.summary.setText(f"{event.get('name')}\n执行次数：{event.get('max_runs') or '不限'} · 循环：{'是' if event.get('loop') else '否'} · 结束：{event.get('end_ms') or '手动停止'}")
        for track in tracks:
            r = self.track_table.rowCount(); self.track_table.insertRow(r)
            for c, value in enumerate([track.get('mode', 'once'), '+'.join(track.get('buttons', [])), track.get('hold_ms', 0), track.get('interval_ms', ''), track.get('end_ms', '')]): self.track_table.setItem(r, c, QTableWidgetItem(str(value)))
        self.timeline.setText('时间线：' + '  |  '.join(f"{'+'.join(t.get('buttons', []))} {t.get('mode', 'once')}" for t in tracks) if tracks else '暂无轨道')

    def _new(self):
        dialog = ChainEditor(dict(name='新事件', steps=[], tracks=[]), self)
        if dialog.exec(): self.events.append(dialog.value()); self._refresh(); self.list.setCurrentRow(len(self.events)-1)

    def _edit(self):
        row = self.list.currentRow()
        if row < 0: return
        try:
            dialog = ChainEditor(self.events[row], self)
            if dialog.exec(): self.events[row] = dialog.value(); self._refresh(); self.list.setCurrentRow(row)
        except Exception as exc:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(self, '打开事件失败', f'事件编辑器无法打开：{exc}')

    def _copy(self):
        row = self.list.currentRow()
        if row < 0: return
        item = deepcopy(self.events[row]); item['name'] = item.get('name', '事件') + ' 副本'; self.events.append(item); self._refresh(); self.list.setCurrentRow(len(self.events)-1)

    def _remove(self):
        row = self.list.currentRow()
        if row >= 0: self.events.pop(row); self._refresh()

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
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.routes_data=[]
        for r in range(self.routes.rowCount()):
            source=self.routes.cellWidget(r,0).currentText() if self.routes.cellWidget(r,0) else ''
            controller=self.routes.cellWidget(r,4).currentText() if self.routes.cellWidget(r,4) else ''
            values=[source]+[self.routes.cellWidget(r,c).currentText().strip() if self.routes.cellWidget(r,c) else '' for c in (1,2,3)]+[controller]
            self.routes_data.append(dict(zip(('source','trigger','event','target','controller'),values)))
        self.path.write_text(json.dumps(self.events, ensure_ascii=False, indent=2), encoding='utf-8')
        self.routes_path.write_text(json.dumps(self.routes_data, ensure_ascii=False, indent=2), encoding='utf-8')

    def _toggle_runtime(self):
        if self.runtime.thread and self.runtime.thread.is_alive():
            self.runtime.stop()
            self.runtime_button.setText('启动本机事件测试')
            self.status.setText('本机事件测试已停止')
            return
        self._save()
        self.runtime = LocalEventRuntime(root=self.path.parent)
        self.runtime.start()
        self.runtime_button.setText('停止本机事件测试')
        self.status.setText('本机事件测试已启动；事件触发键不会被 Xbox 映射层吞掉')
