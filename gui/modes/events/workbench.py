"""Focused event workbench; navigation/follow execution remains elsewhere."""
from copy import deepcopy
from pathlib import Path
import json
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QTabWidget, QTableWidget, QTableWidgetItem)
from core.runtime_paths import data_root
from ..follow.editors import ChainEditor


class EventWorkbenchPage(QWidget):
    def __init__(self, parent=None, *, root=None):
        super().__init__(parent)
        self.path = Path(root or data_root(Path(__file__).resolve().parents[3]) / 'configs' / 'events') / 'events.json'
        self.events = self._load(); self._build(); self._refresh()

    def _load(self):
        try:
            data = json.loads(self.path.read_text(encoding='utf-8'))
            return data if isinstance(data, list) else []
        except (OSError, ValueError): return []

    def _build(self):
        root = QVBoxLayout(self); head = QHBoxLayout(); root.addLayout(head)
        title = QLabel('事件工作台'); title.setStyleSheet('font-size: 22px; font-weight: 700;'); head.addWidget(title)
        head.addWidget(QLabel('编辑按键事件、组合轨道和远程触发规则；跟随执行请到导航模式配置。'), 1)
        self.save = QPushButton('保存事件版本'); self.save.clicked.connect(self._save); head.addWidget(self.save)
        self.status = QLabel('未运行 · 仅编辑配置'); root.addWidget(self.status)
        self.tabs = QTabWidget(); root.addWidget(self.tabs, 1)
        self._build_library(); self._build_routes(); self._build_runtime()

    def _build_library(self):
        page = QWidget(); layout = QHBoxLayout(page)
        self.list = QListWidget(); self.list.currentRowChanged.connect(self._select); layout.addWidget(self.list, 1)
        right = QVBoxLayout(); layout.addLayout(right, 3); actions = QHBoxLayout(); right.addLayout(actions)
        for text, cb in [('新建事件', self._new), ('编辑事件', self._edit), ('复制事件', self._copy), ('删除事件', self._remove)]:
            b = QPushButton(text); b.clicked.connect(cb); actions.addWidget(b)
        self.summary = QLabel('请选择一个事件'); self.summary.setWordWrap(True); right.addWidget(self.summary)
        self.track_table = QTableWidget(0, 5); self.track_table.setHorizontalHeaderLabels(['模式', '按钮/组合', '保持(ms)', '间隔(ms)', '轨道结束(ms)']); right.addWidget(self.track_table, 2)
        self.timeline = QLabel('时间线预览将在选择事件后显示'); self.timeline.setStyleSheet('padding: 16px; background: rgba(255,255,255,0.04);'); right.addWidget(self.timeline)
        self.tabs.addTab(page, '事件库 / 编排')

    def _build_routes(self):
        page = QWidget(); layout = QVBoxLayout(page); layout.addWidget(QLabel('把来源电脑的快捷键或远程操作，路由到目标电脑和目标手柄。'))
        self.routes = QTableWidget(0, 5); self.routes.setHorizontalHeaderLabels(['来源设备', '触发键', '事件', '目标设备', '目标手柄']); layout.addWidget(self.routes, 1)
        add = QPushButton('新增触发规则'); add.clicked.connect(self._add_route); layout.addWidget(add); self.tabs.addTab(page, '触发与路由')

    def _build_runtime(self):
        page = QWidget(); layout = QVBoxLayout(page); layout.addWidget(QLabel('显示远程事件的发送、接收和执行状态，不表示游戏内技能成功。'))
        self.runtime = QTableWidget(0, 6); self.runtime.setHorizontalHeaderLabels(['目标设备', '手柄', '事件', '状态', '当前轨道', '下一步']); layout.addWidget(self.runtime); self.tabs.addTab(page, '运行监控')

    def _refresh(self):
        self.list.clear(); self.list.addItems([e.get('name', '未命名事件') for e in self.events])
        if self.events: self.list.setCurrentRow(0)

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
        dialog = ChainEditor(self.events[row], self)
        if dialog.exec(): self.events[row] = dialog.value(); self._refresh(); self.list.setCurrentRow(row)

    def _copy(self):
        row = self.list.currentRow()
        if row < 0: return
        item = deepcopy(self.events[row]); item['name'] = item.get('name', '事件') + ' 副本'; self.events.append(item); self._refresh(); self.list.setCurrentRow(len(self.events)-1)

    def _remove(self):
        row = self.list.currentRow()
        if row >= 0: self.events.pop(row); self._refresh()

    def _add_route(self):
        r = self.routes.rowCount(); self.routes.insertRow(r)
        for c, value in enumerate(('B端', 'F5', self.events[0]['name'] if self.events else '', 'A端', 'Controller 1')): self.routes.setItem(r, c, QTableWidgetItem(value))

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True); self.path.write_text(json.dumps(self.events, ensure_ascii=False, indent=2), encoding='utf-8'); self.status.setText(f'已保存 {len(self.events)} 个事件')
