"""Native editors for reusable, declarative action sequences."""
from copy import deepcopy
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QFormLayout,QLineEdit,QComboBox,QSpinBox,
    QDoubleSpinBox,QDialogButtonBox,QTableWidget,QTableWidgetItem,QPushButton,QHBoxLayout,
    QCheckBox,QLabel,QMessageBox)
from auto_modules.core.events.automation import ActionSequenceDefinition
from auto_modules.core.events.event_lifecycle import validate_parallel_step
from auto_modules.ui.widgets.gamepad_button_picker import GAMEPAD_INPUTS, GamepadButtonPicker


def spin(value, minimum=0, maximum=1000, decimal=False):
    widget=QDoubleSpinBox() if decimal else QSpinBox()
    # JSON uses null for optional numeric limits (for example end_ms and
    # max_runs).  Qt spin boxes only accept real numbers, so treat null as
    # the editor's neutral value instead of failing while opening the dialog.
    if value is None:
        value = minimum
    widget.setRange(minimum,maximum); widget.setValue(value)
    if decimal: widget.setDecimals(3)
    return widget


class ParallelGroupEditor(QDialog):
    """Edit the non-recursive action tracks inside one ordered step."""

    def __init__(self, tracks=None, duration_ms=1000, parent=None):
        super().__init__(parent)
        self.duration_ms = duration_ms
        self.setWindowTitle('编辑并行动作组')
        self.resize(900, 480)
        layout = QVBoxLayout(self)
        hint = QLabel('组内动作同时计时；延迟从动作组开始计算，所有动作结束或达到组时长后进入下一步骤。')
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(['延迟ms', '模式', '手柄输入/组合', '保持ms', '间隔ms', '结束ms'])
        layout.addWidget(self.table, 1)
        for track in tracks or ():
            self.add_track(track)
        actions = QHBoxLayout()
        layout.addLayout(actions)
        add = QPushButton('添加并行动作')
        add.clicked.connect(lambda: self.add_track({}))
        actions.addWidget(add)
        remove = QPushButton('删除选中动作')
        remove.clicked.connect(lambda: self.table.removeRow(self.table.currentRow()))
        actions.addWidget(remove)
        actions.addStretch(1)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        layout.addWidget(buttons)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)

    def add_track(self, track):
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(str(track.get('delay_ms', 0))))
        mode = QComboBox()
        mode.addItems(['once', 'continuous', 'frequency'])
        mode.setCurrentText(track.get('mode', 'once'))
        self.table.setCellWidget(row, 1, mode)
        self.table.setCellWidget(row, 2, GamepadButtonPicker(track.get('buttons', ['A'])))
        self.table.setItem(row, 3, QTableWidgetItem(str(track.get('hold_ms', 100))))
        self.table.setItem(row, 4, QTableWidgetItem(str(track.get('interval_ms') or '')))
        self.table.setItem(row, 5, QTableWidgetItem(str(track.get('end_ms') or '')))

    def value(self):
        tracks = []
        for row in range(self.table.rowCount()):
            mode = self.table.cellWidget(row, 1).currentText()
            picker = self.table.cellWidget(row, 2)
            track = {
                'buttons': picker.buttons(),
                'mode': mode,
                'delay_ms': int(self.table.item(row, 0).text() or 0),
                'hold_ms': int(self.table.item(row, 3).text() or 100),
            }
            interval = self.table.item(row, 4).text().strip()
            end = self.table.item(row, 5).text().strip()
            if mode == 'frequency':
                track['interval_ms'] = int(interval or 100)
            if end:
                track['end_ms'] = int(end)
            tracks.append(track)
        return tracks

    def _accept(self):
        try:
            validate_parallel_step({'op': 'parallel', 'ms': self.duration_ms, 'tracks': self.value()})
            self.accept()
        except (TypeError, ValueError) as exc:
            QMessageBox.warning(self, '检查并行动作组', str(exc))


class ChainEditor(QDialog):
    columns=('op','button','ms','parallel','name','then','else','target','count')
    def __init__(self,chain=None,parent=None):
        super().__init__(parent); self.resize(1050,760); self.setMinimumSize(900,650); self.setWindowTitle('自定义事件链')
        chain=chain or dict(name='',steps=[])
        layout=QVBoxLayout(self); form=QFormLayout(); layout.addLayout(form)
        self.name=QLineEdit(chain['name']); form.addRow('事件名称（两端一致）',self.name)
        self.priority=spin(chain.get('priority',0),0,100); form.addRow('优先级（数值越大越优先）',self.priority)
        self.timeout=spin(chain.get('timeout_ms',30000),1,60000); form.addRow('总超时（毫秒）',self.timeout)
        self.resume=QCheckBox('正常完成后恢复跟随（回城链建议不勾选）'); self.resume.setChecked(chain.get('resume',False)); form.addRow(self.resume)
        self.enabled=QCheckBox('允许此事件链执行'); self.enabled.setChecked(chain.get('enabled',True)); form.addRow(self.enabled)
        self.max_runs=spin(chain.get('max_runs',0),0,100000); form.addRow('事件执行次数（0=不限）',self.max_runs)
        self.loop=QCheckBox('循环执行'); self.loop.setChecked(chain.get('loop',False)); form.addRow(self.loop)
        self.event_end=spin(chain.get('end_ms',0),0,3600000); form.addRow('事件结束时间（毫秒，0=不限）',self.event_end)
        layout.addWidget(QLabel('并行输入轨道：支持按键和左摇杆八方向移动，可单次、持续或按频率重复。'))
        self.track_table=QTableWidget(0,5); self.track_table.setHorizontalHeaderLabels(['模式','手柄输入/组合','保持ms','间隔ms','轨道结束ms'])
        layout.addWidget(self.track_table,1)
        for track in chain.get('tracks',[]): self.add_track(track)
        track_row=QHBoxLayout(); layout.addLayout(track_row)
        add_track=QPushButton('添加输入轨道'); add_track.clicked.connect(lambda:self.add_track({})); track_row.addWidget(add_track)
        remove_track=QPushButton('删除轨道'); remove_track.clicked.connect(lambda:self.track_table.removeRow(self.track_table.currentRow())); track_row.addWidget(remove_track)
        hint=QLabel('步骤从0编号。等待和单个输入可直接配置；并行动作组可在一个顺序步骤中同时移动、按键或按频率执行。\n条件分支填目标步骤编号；未知模块钩子不会执行外部代码。')
        hint.setWordWrap(True); layout.addWidget(hint)
        self.table=QTableWidget(0,len(self.columns)); self.table.setHorizontalHeaderLabels(['动作','手柄输入','持续ms','并行动作','条件/钩子','真跳转','假跳转','重试起点','重试次数'])
        layout.addWidget(self.table,1)
        for step in chain['steps']: self.add_step(step)
        row=QHBoxLayout(); layout.addLayout(row)
        add=QPushButton('添加步骤'); add.clicked.connect(lambda:self.add_step({'op':'wait','ms':100})); row.addWidget(add)
        remove=QPushButton('删除选中步骤'); remove.clicked.connect(lambda:self.table.removeRow(self.table.currentRow())); row.addWidget(remove)
        buttons=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel); layout.addWidget(buttons)
        buttons.accepted.connect(self._accept); buttons.rejected.connect(self.reject)

    def add_step(self,step):
        r=self.table.rowCount(); self.table.insertRow(r)
        op_widget = None
        button_widget = None
        parallel_widget = None
        for c,key in enumerate(self.columns):
            if key in ('op','button'):
                w=QComboBox()
                if key == 'op':
                    for value, label in (
                        ('wait', '等待'), ('button', '单个手柄输入'), ('parallel', '并行动作组'),
                        ('condition', '条件分支'), ('retry', '有限重试'), ('emit', '模块钩子')):
                        w.addItem(label, value)
                    w.setCurrentIndex(max(0, w.findData(str(step.get(key, 'wait')))))
                    op_widget = w
                else:
                    for value, label in GAMEPAD_INPUTS:
                        w.addItem(label, value)
                    w.setCurrentIndex(max(0, w.findData(str(step.get(key, 'A')))))
                    button_widget = w
                self.table.setCellWidget(r,c,w)
            elif key == 'parallel':
                w = QPushButton()
                w.parallel_tracks = deepcopy(step.get('tracks', []))
                self._sync_parallel_button(w)
                w.clicked.connect(lambda _checked=False, button=w: self._edit_parallel_group(button))
                self.table.setCellWidget(r, c, w)
                parallel_widget = w
            else: self.table.setItem(r,c,QTableWidgetItem(str(step.get(key,''))))
        op_widget.currentIndexChanged.connect(
            lambda _index, op=op_widget, button=button_widget, group=parallel_widget:
                self._sync_step_widgets(op.currentData(), button, group))
        self._sync_step_widgets(op_widget.currentData(), button_widget, parallel_widget)

    @staticmethod
    def _sync_parallel_button(button):
        button.setText(f'编辑动作组 ({len(button.parallel_tracks)})')

    @staticmethod
    def _sync_step_widgets(op, button, group):
        button.setEnabled(op == 'button')
        group.setEnabled(op == 'parallel')

    def _edit_parallel_group(self, button):
        row = next((r for r in range(self.table.rowCount())
                    if self.table.cellWidget(r, self.columns.index('parallel')) is button), -1)
        if row < 0:
            return
        duration_item = self.table.item(row, self.columns.index('ms'))
        try:
            duration_ms = int(duration_item.text() or 1000)
        except ValueError:
            duration_ms = 1000
        dialog = ParallelGroupEditor(button.parallel_tracks, duration_ms, self)
        if dialog.exec() == QDialog.Accepted:
            button.parallel_tracks = dialog.value()
            self._sync_parallel_button(button)

    def add_track(self, track):
        r=self.track_table.rowCount(); self.track_table.insertRow(r)
        mode=QComboBox(); mode.addItems(['once','continuous','frequency']); mode.setCurrentText(track.get('mode','once')); self.track_table.setCellWidget(r,0,mode)
        combo=GamepadButtonPicker(track.get('buttons', ['A']))
        self.track_table.setCellWidget(r,1,combo)
        self.track_table.setItem(r,2,QTableWidgetItem(str(track.get('hold_ms',100))))
        self.track_table.setItem(r,3,QTableWidgetItem(str(track.get('interval_ms',''))))
        self.track_table.setItem(r,4,QTableWidgetItem(str(track.get('end_ms') or '')))

    def value(self):
        steps=[]
        for r in range(self.table.rowCount()):
            op = self.table.cellWidget(r, self.columns.index('op')).currentData()
            step={'op': op}
            for key in ('ms','name','then','else','target','count'):
                item = self.table.item(r, self.columns.index(key))
                value = item.text().strip() if item else ''
                if value:
                    step[key]=int(value) if key in ('ms','then','else','target','count') else value
            if op == 'button':
                step['button'] = self.table.cellWidget(r, self.columns.index('button')).currentData()
            elif op == 'parallel':
                group = self.table.cellWidget(r, self.columns.index('parallel'))
                step['tracks'] = deepcopy(group.parallel_tracks)
            steps.append(step)
        tracks=[]
        for r in range(self.track_table.rowCount()):
            mode=self.track_table.cellWidget(r,0).currentText()
            button_widget=self.track_table.cellWidget(r,1)
            buttons=button_widget.buttons() if isinstance(button_widget, GamepadButtonPicker) else tuple()
            if not buttons:
                buttons=('A',)
            track={'mode':mode,'buttons':buttons,'hold_ms':int(self.track_table.item(r,2).text() or 0)}
            interval=self.track_table.item(r,3).text().strip(); end=self.track_table.item(r,4).text().strip()
            if interval: track['interval_ms']=int(interval)
            if end: track['end_ms']=int(end)
            tracks.append(track)
        return dict(name=self.name.text().strip(),steps=steps,tracks=tracks,max_runs=self.max_runs.value() or None,
            loop=self.loop.isChecked(),end_ms=self.event_end.value() or None,priority=self.priority.value(),
            timeout_ms=self.timeout.value(),resume=self.resume.isChecked(),enabled=self.enabled.isChecked())

    def _accept(self):
        try:
            value=self.value(); ActionSequenceDefinition(value['name'],value['steps'],timeout_ms=value['timeout_ms'])
            self.accept()
        except (ValueError,KeyError) as exc: QMessageBox.warning(self,'检查事件链',str(exc))
