"""Follow workbench: configuration never implies arming either controller."""
from copy import deepcopy
from pathlib import Path
import json
from PySide6.QtCore import QTimer,Qt,QRectF,Signal
from PySide6.QtGui import QPainter,QColor,QPen
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QFormLayout,QPushButton,QLabel,QLineEdit,
    QComboBox,QTabWidget,QTableWidget,QTableWidgetItem,QListWidget,QPlainTextEdit,QFileDialog,QMessageBox,QScrollArea,QCheckBox)
from auto_modules.application.follow.config import FollowConfig,FollowConfigStore
from auto_modules.application.follow.service import FollowService
from auto_modules.application.follow.resources import load_follow_maps
from auto_modules.paths import data_root
from auto_modules.ui.modes.map_editor.canvas import WallEditorCanvas
from auto_modules.ui.theme import COLORS
from .editors import ActorEditor,ChainEditor,spin


class SearchCanvas(WallEditorCanvas):
    region_chosen=Signal(tuple,tuple)
    def __init__(self,parent=None):
        super().__init__(parent); self.first=None; self.last=None; self.positions={}; self.paths={}
        self.stroke_started.connect(self._begin); self.stroke_extended.connect(self._extend); self.stroke_finished.connect(self._finish)
    def _begin(self,p): self.first=self.last=p; self.update()
    def _extend(self,p): self.last=p; self.update()
    def _finish(self):
        if self.first is not None: self.region_chosen.emit(self.first,self.last)
    def paintEvent(self,event):
        super().paintEvent(event)
        painter=QPainter(self); painter.translate(self.pan_offset); painter.scale(self.zoom,self.zoom)
        pen=QPen(QColor(COLORS['primary'])); pen.setCosmetic(True); painter.setPen(pen)
        if self.first is not None:
            x,y=self.first; xx,yy=self.last
            painter.drawRect(QRectF(min(x,xx),min(y,yy),max(1,abs(xx-x)),max(1,abs(yy-y))))
        for actor,path in self.paths.items():
            for a,b in zip(path,path[1:]): painter.drawLine(int(a[0]),int(a[1]),int(b[0]),int(b[1]))
        for actor,p in self.positions.items():
            painter.drawEllipse(QRectF(p[0]-3,p[1]-3,6,6)); painter.drawText(int(p[0]+5),int(p[1]),actor)


class FollowPage(QWidget):
    open_lan_requested=Signal()
    def __init__(self,parent=None,*,config_root=None,service_factory=FollowService):
        super().__init__(parent)
        self.store=FollowConfigStore(config_root or data_root()/'follow')
        self.service_factory=service_factory; self.service=None; self.overlay=None
        self.config_error=''
        try: self.config=self.store.load()
        except Exception as exc: self.config=FollowConfig(); self.config_error=str(exc)
        self._build(); self._populate()
        self.timer=QTimer(self); self.timer.setInterval(150); self.timer.timeout.connect(self._poll); self.timer.start()

    def _build(self):
        layout=QVBoxLayout(self)
        title=QLabel('局域网自动跟随'); title.setStyleSheet('font-size: 21px; font-weight: 600;'); layout.addWidget(title)
        helptext=QLabel('B端手工操作并共享位置；A端独立控制两个人物。先启动定位监视，确认准确后再开启对应角色。')
        helptext.setWordWrap(True); layout.addWidget(helptext)
        controls=QHBoxLayout(); layout.addLayout(controls)
        self.monitor=QPushButton('启动定位监视'); self.monitor.clicked.connect(self._start); controls.addWidget(self.monitor)
        self.stop_button=QPushButton('停止全部'); self.stop_button.clicked.connect(self.stop_runtime); controls.addWidget(self.stop_button)
        self.save_button=QPushButton('保存为新版本'); self.save_button.clicked.connect(self._save); controls.addWidget(self.save_button)
        self.versions=QComboBox(); controls.addWidget(self.versions,1)
        restore=QPushButton('加载所选版本'); restore.clicked.connect(self._restore); controls.addWidget(restore)
        self.banner=QLabel('未运行 · 映射与程序控制均不会自动开启'); self.banner.setWordWrap(True); layout.addWidget(self.banner)
        self.tabs=QTabWidget(); layout.addWidget(self.tabs,1)
        setup=QWidget(); form=QFormLayout(setup)
        self.role=QComboBox(); self.role.addItems(['A','B']); form.addRow('本机角色',self.role)
        self.map_path=QLineEdit(); form.addRow('地图包（map_data.npz）',self.map_path)
        browse=QPushButton('选择地图并预览'); browse.clicked.connect(self._browse); form.addRow(browse)
        self.map_id=QLineEdit(); form.addRow('共同地图标识',self.map_id)
        self.leader=QLineEdit(); form.addRow('B端设备ID（A端填写）',self.leader)
        self.leader_actor=QLineEdit(); form.addRow('B端角色标识（与对端配置一致）',self.leader_actor)
        self.recipient=QLineEdit(); form.addRow('A端设备ID（B端填写）',self.recipient)
        self.targets=QLineEdit(); form.addRow('B端事件目标角色（逗号分隔）',self.targets)
        self.record=QCheckBox('记录本次定位与控制诊断（最多1000帧，含屏幕小地图，请勿含敏感信息）'); form.addRow(self.record)
        lan=QPushButton('打开局域网配对与接收权限'); lan.clicked.connect(self.open_lan_requested.emit); form.addRow(lan)
        self.actor_table=QTableWidget(0,4); self.actor_table.setHorizontalHeaderLabels(['角色','手柄','跟随距离','识别方式']); self.actor_table.setEditTriggers(QTableWidget.NoEditTriggers)
        form.addRow(self.actor_table)
        row=QHBoxLayout(); add=QPushButton('添加角色'); edit=QPushButton('配置选中角色'); remove=QPushButton('移除角色')
        add.clicked.connect(lambda:self._actor(True)); edit.clicked.connect(lambda:self._actor(False)); remove.clicked.connect(self._remove_actor)
        for b in (add,edit,remove): row.addWidget(b)
        form.addRow(row)
        self.actor_controls=QHBoxLayout(); form.addRow(self.actor_controls)
        self.tabs.addTab(self._scroll(setup),'连接与角色')
        local=QWidget(); ll=QVBoxLayout(local); lf=QFormLayout(); ll.addLayout(lf)
        self.roi=[spin(0,-20000,20000),spin(0,-20000,20000),spin(300,16,2048),spin(300,16,2048)]
        row=QHBoxLayout()
        for label,w in zip(('屏幕X','屏幕Y','宽','高'),self.roi): row.addWidget(QLabel(label)); row.addWidget(w)
        lf.addRow('小地图物理像素区域',row)
        choose=QPushButton('在屏幕上框选小地图'); choose.clicked.connect(self._select_roi); lf.addRow(choose)
        self.origin=[spin(0,-100000,100000,True),spin(0,-100000,100000,True)]
        row=QHBoxLayout()
        for w in self.origin: row.addWidget(w)
        lf.addRow('小地图左上角在大地图的位置',row)
        self.radius=spin(100,0,1000); self.scale=spin(1,.1,10,True); self.clearance=spin(2,0,20)
        self.period=spin(50,20,200); self.ttl=spin(250,50,500)
        lf.addRow('局部搜索半径（地图像素）',self.radius); lf.addRow('小地图 → 大地图比例',self.scale); lf.addRow('避墙安全距离（地图像素）',self.clearance)
        lf.addRow('定位采样周期（毫秒）',self.period); lf.addRow('坐标有效期（毫秒）',self.ttl)
        self.reference=QComboBox(); self.reference.addItems(['base','active']); lf.addRow('定位参考墙：原始 / 活动版本',self.reference)
        self.recognizer=QPlainTextEdit(); self.recognizer.setMaximumHeight(100); lf.addRow('现有墙体识别参数（JSON，可从绘图配置复制）',self.recognizer)
        hint=QLabel('地图左键圈出“小地图中心”可能所在范围；右键 / 中键拖动，滚轮缩放。只在圈选范围内重定位，不自动全图扫描。'); hint.setWordWrap(True); ll.addWidget(hint)
        self.canvas=SearchCanvas(); self.canvas.region_chosen.connect(self._region); ll.addWidget(self.canvas,1)
        self.tabs.addTab(self._scroll(local),'定位与地图')
        events=QWidget(); el=QVBoxLayout(events)
        self.chain_list=QListWidget(); el.addWidget(self.chain_list)
        row=QHBoxLayout(); el.addLayout(row)
        for label,callback in [('新增事件链',lambda:self._chain(True)),('编辑',lambda:self._chain(False)),('删除',self._remove_chain)]:
            b=QPushButton(label); b.clicked.connect(callback); row.addWidget(b)
        ef=QFormLayout(); el.addLayout(ef)
        self.shortcut_table=QTableWidget(0,2); self.shortcut_table.setHorizontalHeaderLabels(['快捷键','事件名称']); ef.addRow(self.shortcut_table)
        addkey=QPushButton('增加快捷键'); addkey.clicked.connect(lambda:self._add_shortcut('F12','')); ef.addRow(addkey)
        self.event_name=QLineEdit('follow.pause'); ef.addRow('发送事件名称',self.event_name)
        send=QPushButton('发送到目标角色'); send.clicked.connect(self._send); ef.addRow(send)
        warning=QLabel('F7/F8：暂停对应手柄；F9：宿主急停。事件快捷键在监视运行时生效。\n远程事件仅作用于A端已手动开启的角色；回城链默认完成后暂停。'); warning.setWordWrap(True); el.addWidget(warning)
        self.tabs.addTab(events,'事件链与快捷键')
        self.status_text=QPlainTextEdit(); self.status_text.setReadOnly(True); self.tabs.addTab(self.status_text,'运行诊断')

    @staticmethod
    def _scroll(widget):
        scroll=QScrollArea(); scroll.setWidgetResizable(True); scroll.setWidget(widget); return scroll

    def _populate(self):
        c=self.config; self.role.setCurrentText(c.role); self.map_path.setText(c.map_path); self.map_id.setText(c.map_id)
        self.leader.setText(c.leader_device); self.recipient.setText(c.recipient_device); self.targets.setText(','.join(c.event_targets))
        self.leader_actor.setText(c.leader_actor); self.period.setValue(c.period_ms); self.ttl.setValue(c.position_ttl_ms)
        self.record.setChecked(c.record)
        for w,value in zip(self.roi,c.roi): w.setValue(value)
        for w,value in zip(self.origin,c.initial_origin): w.setValue(value)
        self.radius.setValue(c.search_radius); self.scale.setValue(c.scale); self.clearance.setValue(c.clearance); self.reference.setCurrentText(c.reference_walls)
        self.recognizer.setPlainText(json.dumps(c.recognizer,ensure_ascii=False,indent=2))
        self._actors(); self._chains(); self.shortcut_table.setRowCount(0)
        for key,name in c.shortcuts.items(): self._add_shortcut(key,name)
        self._versions()
        if self.config_error: self.banner.setText('配置读取失败，未运行：'+self.config_error)

    def _collect(self):
        c=deepcopy(self.config); c.role=self.role.currentText(); c.map_path=self.map_path.text().strip(); c.map_id=self.map_id.text().strip()
        c.leader_device=self.leader.text().strip(); c.recipient_device=self.recipient.text().strip(); c.event_targets=[t.strip() for t in self.targets.text().split(',') if t.strip()]
        c.leader_actor=self.leader_actor.text().strip(); c.period_ms=self.period.value(); c.position_ttl_ms=self.ttl.value()
        c.roi=[w.value() for w in self.roi]; c.initial_origin=[w.value() for w in self.origin]
        c.search_radius=self.radius.value(); c.scale=self.scale.value(); c.clearance=self.clearance.value(); c.reference_walls=self.reference.currentText()
        c.recognizer=json.loads(self.recognizer.toPlainText() or '{}')
        c.record=self.record.isChecked()
        c.shortcuts={}
        for r in range(self.shortcut_table.rowCount()):
            key=self.shortcut_table.cellWidget(r,0).currentText(); name=self.shortcut_table.item(r,1).text().strip()
            if name:
                if key in c.shortcuts: raise ValueError('快捷键不能重复')
                c.shortcuts[key]=name
        return c.validate()

    def _versions(self):
        self.versions.clear()
        for p in self.store.versions(): self.versions.addItem(p.stem,str(p))
    def _save(self):
        if self.service is not None: self.banner.setText('请先停止监视，再保存配置修改'); return
        try: self.config=self._collect(); p=self.store.save(self.config); self._versions(); self.banner.setText('已保存新版本：'+p.stem)
        except Exception as exc: self.banner.setText('保存失败：'+str(exc))
    def _restore(self):
        if self.service is not None: self.banner.setText('请先停止监视再加载版本'); return
        try:
            if self.versions.currentData(): self.config=self.store.load(self.versions.currentData()); self._populate()
        except Exception as exc: self.banner.setText('加载配置失败：'+str(exc))

    def _actors(self):
        self.actor_table.setRowCount(len(self.config.actors))
        while self.actor_controls.count():
            item=self.actor_controls.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        for r,a in enumerate(self.config.actors):
            for col,value in enumerate((a['actor_id'],a['controller'],a['lag_distance'],a['algorithm'])): self.actor_table.setItem(r,col,QTableWidgetItem(str(value)))
            for name,kind in [('开启','start'),('暂停','stop')]:
                button=QPushButton(f"{a['actor_id']} {name}"); button.clicked.connect(lambda checked=False,actor=a['actor_id'],kind=kind:self._control(actor,kind)); self.actor_controls.addWidget(button)
    def _actor(self,add):
        if self.service: return
        index=self.actor_table.currentRow()
        if not add and index<0: return
        actor=dict(actor_id='B' if self.role.currentText()=='B' else 'A2',controller=2,lag_distance=15.,basis=[1.,0.,0.,-1.],algorithm='color',parameters={}) if add else self.config.actors[index]
        dialog=ActorEditor(actor,self)
        if dialog.exec():
            if add: self.config.actors.append(dialog.value())
            else: self.config.actors[index]=dialog.value()
            self._actors()
    def _remove_actor(self):
        r=self.actor_table.currentRow()
        if r>=0 and not self.service: self.config.actors.pop(r); self._actors()
    def _chains(self): self.chain_list.clear(); self.chain_list.addItems([c['name'] for c in self.config.chains])
    def _chain(self,add):
        if self.service: return
        r=self.chain_list.currentRow()
        if not add and r<0:return
        dialog=ChainEditor(None if add else self.config.chains[r],self)
        if dialog.exec():
            if add:self.config.chains.append(dialog.value())
            else:self.config.chains[r]=dialog.value()
            self._chains()
    def _remove_chain(self):
        r=self.chain_list.currentRow()
        if r>=0 and not self.service:self.config.chains.pop(r); self._chains()
    def _add_shortcut(self,key,name):
        r=self.shortcut_table.rowCount(); self.shortcut_table.insertRow(r); combo=QComboBox(); combo.addItems(['F1','F2','F3','F4','F5','F6','F10','F11','F12']); combo.setCurrentText(key)
        self.shortcut_table.setCellWidget(r,0,combo); self.shortcut_table.setItem(r,1,QTableWidgetItem(name))
    def _browse(self):
        if self.service is not None: self.banner.setText('请先停止监视，再切换地图'); return
        path,_=QFileDialog.getOpenFileName(self,'选择地图包',self.map_path.text(),'Map (*.npz)')
        if not path:return
        self.map_path.setText(path)
        if not self.map_id.text():self.map_id.setText(Path(path).parent.name)
        try: reference,_=load_follow_maps(self._collect()); self.canvas.set_wall_layer(reference.wall_layer*255)
        except Exception as exc:self.banner.setText('地图预览失败：'+str(exc))
    def _region(self,a,b):
        self.origin[0].setValue((a[0]+b[0])/2-self.roi[2].value()*self.scale.value()/2)
        self.origin[1].setValue((a[1]+b[1])/2-self.roi[3].value()*self.scale.value()/2)
        distance=max(abs(a[0]-b[0]),abs(a[1]-b[1]))/2
        if distance>0:self.radius.setValue(round(distance))
    def _select_roi(self):
        if self.service is not None: self.banner.setText('请先停止监视，再重新框选'); return
        from auto_modules.ui.selection.region_overlay import TransparentOverlay
        self.overlay=TransparentOverlay()
        def selected(x,y,w,h):
            ratio=self.overlay.devicePixelRatioF(); origin=self.overlay.geometry().topLeft()
            for field,value in zip(self.roi,((x+origin.x())*ratio,(y+origin.y())*ratio,w*ratio,h*ratio)): field.setValue(round(value))
        self.overlay.region_selected.connect(selected); self.overlay.show(); self.overlay.raise_(); self.overlay.activateWindow()
    def _start(self):
        try:
            self.config=self._collect(); self.config.validate(for_start=True)
            service=self.service_factory(self.config); service.start(); self.service=service
            self.monitor.setEnabled(False); self.banner.setText('监视已启动；角色仍需分别点击开启。')
        except Exception as exc:self.banner.setText('未启动：'+str(exc))
    def _control(self,actor,kind):
        try:
            if self.service is None:raise ValueError('请先启动定位监视')
            if self.config.role!='A':raise ValueError('B端只共享位置，不启用手柄')
            self.service.command(actor,kind)
        except Exception as exc:self.banner.setText(str(exc))
    def _send(self):
        try:
            if self.service is None:raise ValueError('请先启动监视')
            self.service.send_event(self.event_name.text().strip())
        except Exception as exc:self.banner.setText(str(exc))
    def _poll(self):
        if self.service is None:return
        status=self.service.status(); self.status_text.setPlainText(json.dumps(status,ensure_ascii=False,indent=2))
        workers=status['workers']; vision=workers.get('vision',{})
        self.canvas.positions=vision.get('positions',{}); self.canvas.paths={a:v.get('path',()) for a,v in workers.items() if a!='vision'}; self.canvas.update()
        errors=[v['error'] for v in [status['network'],*workers.values()] if v.get('error')]
        self.banner.setText('；'.join(errors) if errors else f"定位：{'有效' if vision.get('registration') else '等待匹配'} · 耗时 {vision.get('localization_ms','—')} ms · "+' / '.join(f"{a}: {v.get('mode','')} {v.get('state','')}" for a,v in workers.items() if a!='vision'))
        if not status['running']:
            self.stop_runtime()
            if errors:self.banner.setText('已停止：'+'；'.join(errors))
    def stop_runtime(self):
        if self.service is not None:
            self.service.stop(); self.service=None
        self.monitor.setEnabled(True); self.banner.setText('已停止 · 程序输出释放，需重新手动开启')

    def closeEvent(self,event):
        self.stop_runtime(); self.timer.stop(); super().closeEvent(event)
