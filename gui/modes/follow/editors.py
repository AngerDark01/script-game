"""Small native editors for reusable actor detectors and event-chain steps."""
from copy import deepcopy
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QFormLayout,QLineEdit,QComboBox,QSpinBox,
    QDoubleSpinBox,QDialogButtonBox,QTableWidget,QTableWidgetItem,QPushButton,QHBoxLayout,
    QCheckBox,QLabel,QFileDialog,QMessageBox)
from core.events.follow_chain import FollowChainDefinition
from gui.widgets.gamepad_button_picker import GAMEPAD_INPUTS, GamepadButtonPicker


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


class ActorEditor(QDialog):
    def __init__(self,actor,parent=None):
        super().__init__(parent); self.setWindowTitle('角色识别与独立控制'); self.resize(520,650)
        self.actor=deepcopy(actor); layout=QVBoxLayout(self); form=QFormLayout(); layout.addLayout(form)
        self.identity=QLineEdit(actor['actor_id']); form.addRow('角色标识',self.identity)
        self.slot=spin(actor['controller'],1,2); form.addRow('虚拟手柄',self.slot)
        self.lag=spin(actor['lag_distance'],0,1000,True); form.addRow('沿B的轨迹保持距离（地图像素）',self.lag)
        self.algorithm=QComboBox(); self.algorithm.addItems(['color','template']); self.algorithm.setCurrentText(actor['algorithm'])
        form.addRow('颜色 / ID模板',self.algorithm)
        p=actor['parameters']; self.colors={}
        for key,label,default,upper in [('hue_min','色相下限',40,179),('hue_max','色相上限',80,179),
            ('saturation_min','饱和度下限',100,255),('saturation_max','饱和度上限',255,255),
            ('value_min','亮度下限',100,255),('value_max','亮度上限',255,255),
            ('min_area','标记最小面积',2,10000),('max_area','标记最大面积',100,10000)]:
            self.colors[key]=spin(p.get(key,default),0,upper); form.addRow(label,self.colors[key])
        self.template=QLineEdit(p.get('template_path','')); form.addRow('ID模板图片',self.template)
        browse=QPushButton('选择模板图片'); browse.clicked.connect(self._browse); form.addRow(browse)
        self.basis=[]
        for label,value in zip(('地图X → 摇杆X','地图Y → 摇杆X','地图X → 摇杆Y','地图Y → 摇杆Y'),actor['basis']):
            w=spin(value,-10,10,True); self.basis.append(w); form.addRow(label,w)
        hint=QLabel('颜色取原始小地图；两个人物必须使用不同的颜色范围或ID模板。\n默认Y轴反向：地图向下为正，Xbox向上为正。'); hint.setWordWrap(True); layout.addWidget(hint)
        buttons=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel); layout.addWidget(buttons)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject)

    def _browse(self):
        path,_=QFileDialog.getOpenFileName(self,'选择ID模板','','Images (*.png *.jpg *.bmp)')
        if path: self.template.setText(path)

    def value(self):
        algorithm=self.algorithm.currentText()
        parameters={k:w.value() for k,w in self.colors.items()} if algorithm=='color' else {'template_path':self.template.text(),'threshold':.85}
        return dict(actor_id=self.identity.text().strip(),controller=self.slot.value(),lag_distance=self.lag.value(),
            algorithm=algorithm,parameters=parameters,basis=[w.value() for w in self.basis])


class ChainEditor(QDialog):
    columns=('op','button','ms','name','then','else','target','count')
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
        hint=QLabel('步骤从0编号。wait=等待；button=手柄按键；condition=条件分支；retry=有限重试；emit=模块钩子。\n内置条件：localized、leader_fresh。分支填目标步骤编号。未知钩子不会执行外部代码。')
        hint.setWordWrap(True); layout.addWidget(hint)
        self.table=QTableWidget(0,len(self.columns)); self.table.setHorizontalHeaderLabels(['动作','手柄输入','持续ms','条件/钩子','真跳转','假跳转','重试起点','重试次数'])
        layout.addWidget(self.table,1)
        for step in chain['steps']: self.add_step(step)
        row=QHBoxLayout(); layout.addLayout(row)
        add=QPushButton('添加步骤'); add.clicked.connect(lambda:self.add_step({'op':'wait','ms':100})); row.addWidget(add)
        remove=QPushButton('删除选中步骤'); remove.clicked.connect(lambda:self.table.removeRow(self.table.currentRow())); row.addWidget(remove)
        buttons=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel); layout.addWidget(buttons)
        buttons.accepted.connect(self._accept); buttons.rejected.connect(self.reject)

    def add_step(self,step):
        r=self.table.rowCount(); self.table.insertRow(r)
        for c,key in enumerate(self.columns):
            if key in ('op','button'):
                w=QComboBox()
                if key == 'op':
                    w.addItems(['wait','button','condition','retry','emit'])
                    w.setCurrentText(str(step.get(key, 'wait')))
                else:
                    for value, label in GAMEPAD_INPUTS:
                        w.addItem(label, value)
                    w.setCurrentIndex(max(0, w.findData(str(step.get(key, 'A')))))
                self.table.setCellWidget(r,c,w)
            else: self.table.setItem(r,c,QTableWidgetItem(str(step.get(key,''))))

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
            step={}
            for c,key in enumerate(self.columns):
                w=self.table.cellWidget(r,c)
                value=(w.currentData() if key == 'button' else w.currentText()) if w else self.table.item(r,c).text().strip()
                if value: step[key]=int(value) if key in ('ms','then','else','target','count') else value
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
            value=self.value(); FollowChainDefinition(value['name'],value['steps'],timeout_ms=value['timeout_ms'])
            self.accept()
        except (ValueError,KeyError) as exc: QMessageBox.warning(self,'检查事件链',str(exc))
