import os
import cv2
import numpy as np
import ast # 安全地转换字符串到列表
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
    QComboBox, QGraphicsView, QGraphicsScene, QGraphicsPixmapItem,
    QMessageBox, QGraphicsPathItem, QSpinBox, QCheckBox, QGroupBox, QFormLayout, QDoubleSpinBox, QLineEdit
)
from PySide6.QtCore import Qt, QTimer, QPointF, QEvent
from PySide6.QtGui import QImage, QPixmap, QPainter, QPen, QColor, QBrush, QPainterPath

from core.navigation_core import NavigationCore
from core.motion_controller import MotionController

from gui.overlay_window import OverlayWindow

class NavigationModeWidget(QWidget):
    """
    导航模式主窗口
    """
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.nav_core = None
        self.motion_controller = MotionController()
        self.overlay = OverlayWindow() # 新增覆盖层
        self.nav_config = {} # 导航参数的独立存储
        self.map_folder_path = None # 当前加载的地图路径
        
        self.init_ui()
        
        # 导航定时器
        self.nav_timer = QTimer()
        self.nav_timer.timeout.connect(self.navigation_loop)
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # 1. 顶部控制栏
        top_bar = QHBoxLayout()
        
        self.map_combo = QComboBox()
        self.refresh_map_list()
        top_bar.addWidget(QLabel("选择地图:"))
        top_bar.addWidget(self.map_combo, 1)
        
        self.btn_load = QPushButton("加载地图")
        self.btn_load.clicked.connect(self.load_map)
        top_bar.addWidget(self.btn_load)
        
        # 初始位置提示按钮
        self.btn_hint = QPushButton("📍 设置初始位置")
        self.btn_hint.setCheckable(True)
        self.btn_hint.clicked.connect(self.toggle_hint_mode)
        self.btn_hint.setEnabled(False)
        top_bar.addWidget(self.btn_hint)
        
        self.btn_start = QPushButton("开始导航")
        self.btn_start.setCheckable(True)
        self.btn_start.clicked.connect(self.toggle_navigation)
        self.btn_start.setEnabled(False) # 加载地图前不可用
        top_bar.addWidget(self.btn_start)
        
        # 自动移动开关
        self.chk_auto_move = QCheckBox("启用自动移动")
        self.chk_auto_move.setChecked(False)
        self.chk_auto_move.stateChanged.connect(self.toggle_auto_move)
        top_bar.addWidget(self.chk_auto_move)
        
        layout.addLayout(top_bar)
        
        # 2. 新的导航参数面板
        main_params_group = QGroupBox("导航参数面板")
        main_params_layout = QVBoxLayout(main_params_group)

        # 2.1 可调节参数
        adjustable_group = QGroupBox("可调节参数")
        form_layout = QFormLayout(adjustable_group)

        self.nav_k_ratio_spin = QDoubleSpinBox()
        self.nav_k_ratio_spin.setRange(1.0, 50.0)
        self.nav_k_ratio_spin.setSingleStep(0.5)
        form_layout.addRow("鼠标映射系数 (K):", self.nav_k_ratio_spin)

        self.nav_y_bias_spin = QDoubleSpinBox()
        self.nav_y_bias_spin.setRange(0.5, 2.0)
        self.nav_y_bias_spin.setSingleStep(0.05)
        form_layout.addRow("鼠标纵向补偿 (Y-Bias):", self.nav_y_bias_spin)

        self.nav_center_offset_spin = QSpinBox()
        self.nav_center_offset_spin.setRange(-500, 500)
        self.nav_center_offset_spin.setSingleStep(10)
        form_layout.addRow("角色中心偏移 (Y-Offset):", self.nav_center_offset_spin)
        
        # HSV和其他识别参数
        self.nav_wall_hsv_min_edit = QLineEdit()
        self.nav_wall_hsv_max_edit = QLineEdit()
        form_layout.addRow("墙体HSV Min:", self.nav_wall_hsv_min_edit)
        form_layout.addRow("墙体HSV Max:", self.nav_wall_hsv_max_edit)

        # --- 连接信号 ---
        self.nav_k_ratio_spin.valueChanged.connect(self._on_parameter_changed)
        self.nav_y_bias_spin.valueChanged.connect(self._on_parameter_changed)
        self.nav_center_offset_spin.valueChanged.connect(self._on_parameter_changed)
        self.nav_wall_hsv_min_edit.textChanged.connect(self._on_parameter_changed)
        self.nav_wall_hsv_max_edit.textChanged.connect(self._on_parameter_changed)

        main_params_layout.addWidget(adjustable_group)

        # 2.2 只读信息
        info_group = QGroupBox("地图基础信息 (只读)")
        info_layout = QFormLayout(info_group)
        
        self.nav_info_draw_scale = QLabel("N/A")
        self.nav_info_monitor_center = QLabel("N/A")
        self.nav_info_monitor_size = QLabel("N/A")
        
        info_layout.addRow("地图精度 (Draw Scale):", self.nav_info_draw_scale)
        info_layout.addRow("截图中心 (Center):", self.nav_info_monitor_center)
        info_layout.addRow("截图大小 (Size):", self.nav_info_monitor_size)
        
        main_params_layout.addWidget(info_group)

        # 2.3 操作和状态
        action_layout = QHBoxLayout()
        self.nav_save_btn = QPushButton("保存当前导航参数")
        self.nav_save_btn.clicked.connect(self._save_nav_config)
        self.nav_status_label = QLabel("参数已加载")
        self.nav_status_label.setAlignment(Qt.AlignRight)
        
        action_layout.addWidget(self.nav_save_btn)
        action_layout.addWidget(self.nav_status_label, 1)
        main_params_layout.addLayout(action_layout)
        
        layout.addWidget(main_params_group)
        
        # 地图显示区域
        self.scene = QGraphicsScene()
        # 安装事件过滤器，以确保能捕获点击事件
        self.scene.installEventFilter(self)
        
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.Antialiasing)
        self.view.setDragMode(QGraphicsView.ScrollHandDrag)
        layout.addWidget(self.view)
        
        # 地图图元
        self.map_item = None
        self.player_item = None
        self.target_item = None
        self.monitor_rect_item = None # 新增：监视框 (同时作为安全视窗)
        self.path_item = None # 新增：路径线
        
        # 状态栏
        self.status_label = QLabel("请选择并加载地图")
        layout.addWidget(self.status_label)
        
    def refresh_map_list(self):
        """刷新地图列表"""
        self.map_combo.clear()
        
        # 获取项目根目录下的 map_data
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(current_dir)
        map_data_dir = os.path.join(project_root, "map_data")
        
        if os.path.exists(map_data_dir):
            dirs = [d for d in os.listdir(map_data_dir) if os.path.isdir(os.path.join(map_data_dir, d))]
            self.map_combo.addItems(dirs)
        else:
            self.map_combo.addItem("未找到 map_data 文件夹")

    def load_map(self):
        map_name = self.map_combo.currentText()
        if not map_name or map_name == "未找到 map_data 文件夹":
            return

        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(current_dir)
        self.map_folder_path = os.path.join(project_root, "map_data", map_name)

        try:
            # 1. 加载配置到 self.nav_config
            import json
            config_path = os.path.join(self.map_folder_path, "config.json")
            if os.path.exists(config_path):
                print(f"Loading config from {config_path}...")
                with open(config_path, 'r', encoding='utf-8') as f:
                    self.nav_config = json.load(f)
            else:
                # 如果没有配置文件，创建一个空的，避免后续代码出错
                self.nav_config = {}
                QMessageBox.warning(self, "警告", "未找到 config.json，将使用默认参数。")

            # 2. 初始化核心模块
            self.nav_core = NavigationCore(self.map_folder_path)

            # 3. 将加载的配置应用到核心模块和UI
            self._apply_config_to_core()
            self._update_panel_from_config()
            
            # --- BUGFIX: 强制再次从 self.nav_config 更新UI面板 ---
            # 确保即使用户界面有默认值，也会被配置文件覆盖
            nav_prefs = self.nav_config.get("nav_preferences", {})
            self.nav_k_ratio_spin.setValue(nav_prefs.get("k_ratio", 1.0))
            self.nav_y_bias_spin.setValue(nav_prefs.get("y_bias", 0.5))
            self.nav_center_offset_spin.setValue(nav_prefs.get("center_offset_y", 0))
            # --- END BUGFIX ---

            # 4. 渲染地图
            map_img = self.nav_core.get_map_image()
            h, w, c = map_img.shape
            if not map_img.flags['C_CONTIGUOUS']:
                map_img = np.ascontiguousarray(map_img)
            
            qimg = QImage(map_img.data, w, h, w * c, QImage.Format_RGB888)
            pixmap = QPixmap.fromImage(qimg)

            self.scene.clear()
            self.map_item = self.scene.addPixmap(pixmap)
            self.map_item.setZValue(0)

            self.player_item = self.scene.addEllipse(-5, -5, 10, 10, QPen(Qt.red), QBrush(Qt.red))
            self.player_item.setZValue(2)
            self.player_item.setVisible(False)

            self.target_item = self.scene.addRect(-5, -5, 10, 10, QPen(Qt.green), QBrush(Qt.green))
            self.target_item.setZValue(1)
            self.target_item.setVisible(False)

            self.btn_start.setEnabled(True)
            self.btn_hint.setEnabled(True)
            self.status_label.setText(f"地图 '{map_name}' 加载成功. 请设置初始位置或直接开始导航。")
            self.nav_status_label.setText("参数已加载")

            self.view.fitInView(self.map_item, Qt.KeepAspectRatio)

            if self.nav_core.last_pos is not None:
                last_x, last_y = self.nav_core.last_pos
                self.player_item.setPos(last_x, last_y)
                self.player_item.setVisible(True)
                self.player_item.setRect(-50, -50, 100, 100)

        except Exception as e:
            QMessageBox.critical(self, "错误", f"加载地图失败: {str(e)}")

    def _update_panel_from_config(self):
        """使用 self.nav_config 的内容填充UI面板"""
        # 提取参数，使用 .get() 提供默认值以增强健壮性
        nav_prefs = self.nav_config.get("nav_preferences", {})
        recognizer_params = self.nav_config.get("recognizer_params", {})
        
        # 更新可调节参数面板
        self.nav_k_ratio_spin.setValue(nav_prefs.get("k_ratio", 10.0))
        self.nav_y_bias_spin.setValue(nav_prefs.get("y_bias", 1.0))
        self.nav_center_offset_spin.setValue(nav_prefs.get("center_offset_y", 0))
        
        # 更新HSV值
        self.nav_wall_hsv_min_edit.setText(str(recognizer_params.get("wall_hsv_min", [0,0,0])))
        self.nav_wall_hsv_max_edit.setText(str(recognizer_params.get("wall_hsv_max", [255,255,255])))

        # 更新只读信息面板
        self.nav_info_draw_scale.setText(str(self.nav_config.get("draw_scale", "N/A")))
        self.nav_info_monitor_center.setText(str(self.nav_config.get("monitor_center", "N/A")))
        self.nav_info_monitor_size.setText(str(self.nav_config.get("monitor_size", "N/A")))
        
        print("UI panel updated from nav_config.")

    def _apply_config_to_core(self):
        """将 self.nav_config 的参数注入到核心模块"""
        if not self.nav_core:
            return

        # 提取参数
        nav_prefs = self.nav_config.get("nav_preferences", {})
        recognizer_params = self.nav_config.get("recognizer_params", {})
        
        # 1. 应用到 Recognizer
        if recognizer_params:
            self.nav_core.recognizer.set_params(recognizer_params)
            print("Applied recognizer_params to NavigationCore.")

        # 2. 应用到 NavigationCore
        self.nav_core.draw_scale = self.nav_config.get("draw_scale", 2.0)
        self.nav_core.set_center_offset(nav_prefs.get("center_offset_y", 0))
        print(f"Applied draw_scale ({self.nav_core.draw_scale}) and center_offset to NavigationCore.")

        # 3. 应用到 MotionController
        center = self.nav_config.get("monitor_center")
        if center:
            self.main_window.monitor_center = tuple(center)
            self.main_window.monitor_region = None
            
            size = self.nav_config.get("monitor_size", 200)
            self.main_window.monitor_size = size
            
            k_ratio = nav_prefs.get("k_ratio", 10.0)
            y_bias = nav_prefs.get("y_bias", 1.0)
            center_offset_y = nav_prefs.get("center_offset_y", 0)
            
            self.motion_controller.set_screen_params(center[0], center[1], size, y_bias, center_offset_y)
            print("Applied screen params to MotionController.")
            
            # 4. 更新黄框预览
            self.main_window.update_overlay_for_nav(center[0], center[1], size)
        else:
            # 兼容旧的或不完整的config
            print("Warning: monitor_center not found in config. MotionController and overlay not updated.")

    def _on_parameter_changed(self):
        """当导航参数面板中的任何一个值发生变化时调用。"""
        if not self.nav_core: # 如果还没有加载地图，则不执行任何操作
            return

        print("Parameter changed, updating config and applying to core...")
        self.nav_status_label.setText("有未保存的修改")

        # 1. 从UI读取值并更新 self.nav_config
        nav_prefs = self.nav_config.setdefault("nav_preferences", {})
        nav_prefs["k_ratio"] = self.nav_k_ratio_spin.value()
        nav_prefs["y_bias"] = self.nav_y_bias_spin.value()
        nav_prefs["center_offset_y"] = self.nav_center_offset_spin.value()

        recognizer_params = self.nav_config.setdefault("recognizer_params", {})
        try:
            # 使用 ast.literal_eval 安全地将字符串转为列表
            hsv_min = ast.literal_eval(self.nav_wall_hsv_min_edit.text())
            if isinstance(hsv_min, list) and len(hsv_min) == 3:
                recognizer_params["wall_hsv_min"] = hsv_min
            else:
                # 可以添加一些UI反馈，比如设置输入框边框为红色
                print(f"Warning: Invalid format for HSV Min: {self.nav_wall_hsv_min_edit.text()}")
        except (ValueError, SyntaxError):
            print(f"Warning: Could not parse HSV Min: {self.nav_wall_hsv_min_edit.text()}")

        try:
            hsv_max = ast.literal_eval(self.nav_wall_hsv_max_edit.text())
            if isinstance(hsv_max, list) and len(hsv_max) == 3:
                recognizer_params["wall_hsv_max"] = hsv_max
            else:
                print(f"Warning: Invalid format for HSV Max: {self.nav_wall_hsv_max_edit.text()}")
        except (ValueError, SyntaxError):
            print(f"Warning: Could not parse HSV Max: {self.nav_wall_hsv_max_edit.text()}")

        # 2. 立即将更新后的参数应用到核心模块
        self._apply_config_to_core()

    def _save_nav_config(self):
        """保存当前的导航参数到 config.json"""
        if not self.map_folder_path:
            QMessageBox.warning(self, "错误", "没有加载地图，无法保存参数。")
            return

        config_path = os.path.join(self.map_folder_path, "config.json")
        
        try:
            import json
            print(f"Saving navigation config to {config_path}...")
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(self.nav_config, f, indent=4, ensure_ascii=False)
            
            self.nav_status_label.setText("参数已保存")
            print("Save successful.")
        except Exception as e:
            QMessageBox.critical(self, "保存失败", f"无法写入 config.json: {e}")
            self.nav_status_label.setText("保存失败!")
            print(f"Error saving config: {e}")


    def eventFilter(self, watched, event):
        """事件过滤器：处理场景点击"""
        if watched == self.scene and event.type() == QEvent.GraphicsSceneMousePress:
            if event.button() == Qt.LeftButton:
                # 获取场景坐标
                scene_pos = event.scenePos()
                print(f"Scene clicked at: {scene_pos}")
                self.handle_map_click(scene_pos)
                return True # 标记事件已处理
        return super().eventFilter(watched, event)

    def handle_map_click(self, pos):
        """处理地图点击逻辑"""
        if not self.nav_core:
            return
            
        click_x, click_y = pos.x(), pos.y()
        
        # 坐标变换：局部显示 -> 全局
        offset_x, offset_y = self.nav_core.crop_offset
        target_x = click_x + offset_x
        target_y = click_y + offset_y
        
        # 模式判断：是设置目标点，还是设置初始位置提示
        if self.btn_hint.isChecked():
            # ... (原有 Hint 逻辑保持不变) ...
            # === 设置初始位置模式 ===
            self.nav_core.set_initial_hint((target_x, target_y))
            
            # 显示提示点（蓝色）
            if not hasattr(self, 'hint_item') or self.hint_item is None:
                pt_size = self.player_item.rect().width()
                self.hint_item = self.scene.addEllipse(-pt_size/2, -pt_size/2, pt_size, pt_size, QPen(Qt.blue), QBrush(Qt.blue))
                self.hint_item.setZValue(2.5)
            
            self.hint_item.setPos(click_x, click_y)
            self.hint_item.setVisible(True)
            self.status_label.setText(f"初始位置提示已设置: ({int(target_x)}, {int(target_y)})。请点击'开始导航'。")
            
            # --- 立即更新视觉反馈 ---
            # 即使还没开始导航，也先显示出玩家和监视框在点击的位置
            offset_x, offset_y = self.nav_core.crop_offset
            display_x = target_x - offset_x
            display_y = target_y - offset_y
            
            # 更新红点
            self.player_item.setPos(display_x, display_y)
            self.player_item.setVisible(True)
            
            # 更新黄框
            if self.monitor_rect_item is None:
                 if self.main_window.monitor_center:
                     size = self.main_window.monitor_size
                     w, h = size, size
                 elif self.main_window.monitor_region:
                     region = self.main_window.monitor_region
                     w, h = region[2], region[3]
                 else:
                     w, h = 200, 200
                 self.monitor_rect_item = self.scene.addRect(0, 0, w, h, QPen(Qt.yellow, 2), QBrush(Qt.NoBrush))
                 self.monitor_rect_item.setZValue(3)
            
            rect = self.monitor_rect_item.rect()
            self.monitor_rect_item.setPos(display_x - rect.width()/2, display_y - rect.height()/2)
            self.monitor_rect_item.setVisible(True)
            # ----------------------

            # 自动退出提示模式
            self.btn_hint.setChecked(False)
            self.toggle_hint_mode() # 恢复UI状态
            
        else:
            # === 映射点击模式 (Mapping Click) ===
            
            # 检查是否已定位
            if not self.nav_core.is_localized or self.nav_core.current_pos is None:
                QMessageBox.warning(self, "警告", "请先开始导航并等待定位成功。")
                return

            # 检查点击是否在视窗范围内
            if self.monitor_rect_item and self.monitor_rect_item.isVisible():
                # 获取视窗在场景中的矩形
                vp_rect = self.monitor_rect_item.sceneBoundingRect()
                if not vp_rect.contains(pos):
                    print("Click outside viewport, ignored.")
                    self.status_label.setText("点击无效：超出安全视窗范围")
                    return

            # 计算屏幕映射坐标
            # 1. 计算大地图位移 (Global Map Delta)
            curr_global = self.nav_core.current_pos
            dx_global = target_x - curr_global[0]
            dy_global = target_y - curr_global[1]
            
            # 2. 还原为小地图原始位移 (Raw Minimap Delta)
            draw_scale = self.nav_core.draw_scale
            dx_raw = dx_global / draw_scale
            dy_raw = dy_global / draw_scale
            
            # 3. 映射到屏幕位移 (Screen Delta)
            k_ratio = self.nav_k_ratio_spin.value() # 使用新的控件
            dx_screen = dx_raw * k_ratio
            dy_screen = dy_raw * k_ratio
            
            # 4. 计算屏幕绝对坐标
            # 获取屏幕中心 (从 MotionController 获取)
            center_x, center_y = self.motion_controller.screen_center
            
            # 应用 Y-Bias 到映射逻辑
            y_bias = self.nav_y_bias_spin.value() # 使用新的控件
            target_screen_x = center_x + dx_screen
            target_screen_y = center_y + (dy_screen * y_bias)
            
            # 5. 执行鼠标移动
            print(f"Mapping: Map({int(dx_global)}, {int(dy_global)}) -> Screen({int(dx_screen)}, {int(dy_screen)})")
            self.status_label.setText(f"映射测试: 移动鼠标至 ({int(target_screen_x)}, {int(target_screen_y)})")
            
            self.motion_controller.driver.move_to(target_screen_x, target_screen_y)
            
            # UI 反馈 (绿色目标点)
            self.target_item.setPos(click_x, click_y)
            self.target_item.setVisible(True)

    def toggle_hint_mode(self):
        if self.btn_hint.isChecked():
            self.status_label.setText("请在地图上点击您当前的大致位置...")
            # 禁用拖拽模式，以便鼠标点击可以正确传递给地图项
            self.view.setDragMode(QGraphicsView.NoDrag)
            self.view.setCursor(Qt.CrossCursor)
        else:
            self.status_label.setText("取消设置初始位置")
            # 恢复拖拽模式
            self.view.setDragMode(QGraphicsView.ScrollHandDrag)
            self.view.setCursor(Qt.ArrowCursor)

    def toggle_auto_move(self, state):
        """切换自动移动"""
        enabled = (state == Qt.Checked)
        self.motion_controller.set_control_enabled(enabled)
        if enabled:
            QMessageBox.information(self, "提示", "自动移动已启用！\n请确保游戏窗口在前台，且人物位于屏幕中心。")

    def toggle_navigation(self):
        if self.btn_start.isChecked():
            # 启动
            # 检查是否有监视区域或中心点
            if not self.main_window.monitor_region and not self.main_window.monitor_center:
                QMessageBox.warning(self, "警告", "请先在'绘图模式'设置监控区域或选择中心点！")
                self.btn_start.setChecked(False)
                return
            
            # 初始化运动控制器的屏幕参数
            center_offset_y = self.nav_center_offset_spin.value()
            if self.nav_core:
                self.nav_core.set_center_offset(center_offset_y)

            # 优先使用 monitor_center 作为屏幕中心，否则回退到屏幕物理中心
            if self.main_window.monitor_center:
                center = self.main_window.monitor_center
            else:
                screen_w = self.motion_controller.driver.screen_width
                screen_h = self.motion_controller.driver.screen_height
                center = (screen_w // 2, screen_h // 2)

            scale = 2.0
            if self.nav_core:
                scale = self.nav_core.draw_scale
                
            self.motion_controller.set_screen_params(
                center, 
                scale, 
                self.nav_k_ratio_spin.value(), 
                self.nav_y_bias_spin.value(),
                center_offset_y
            )
            
            # 同步 checkbox 状态
            self.motion_controller.set_control_enabled(self.chk_auto_move.isChecked())
                
            self.nav_timer.start(100) # 10Hz
            self.btn_start.setText("停止导航")
            self.status_label.setText("导航中... 正在定位...")
        else:
            # 停止
            self.nav_timer.stop()
            self.motion_controller.stop()
            self.btn_start.setText("开始导航")
            self.status_label.setText("导航暂停")
            
    def navigation_loop(self):
        """导航主循环"""
        # 1. 截图
        # 优先使用 monitor_center + monitor_size (中心点模式)
        if self.main_window.monitor_center:
            center_x, center_y = self.main_window.monitor_center
            size = self.main_window.monitor_size
            frame = self.main_window.screen_capture.capture_square(center_x, center_y, size)
        
        # 降级使用 monitor_region (区域选择模式)
        elif self.main_window.monitor_region:
            region = self.main_window.monitor_region
            # capture_region 已经在 core/capture.py 中添加了兼容
            frame = self.main_window.screen_capture.capture_region(region)
            
        else:
            print("Navigation Error: No monitor region or center set.")
            return
            
        if frame is None:
            return
            
        # 2. 定位
        global_x, global_y, conf = self.nav_core.localize(frame)
        
        if global_x is not None:
            # 坐标变换：全局 -> 局部显示
            offset_x, offset_y = self.nav_core.crop_offset
            display_x = global_x - offset_x
            display_y = global_y - offset_y
            
            # 更新玩家位置显示
            self.player_item.setPos(display_x, display_y)
            self.player_item.setVisible(True)



            # 3. 运动控制
            # 传入当前全局坐标
            cmd = self.motion_controller.update((global_x, global_y))
            
            status_text = f"位置: ({int(global_x)}, {int(global_y)}) | 置信度: {conf:.2f}"
            
            # if cmd['action'] == 'move':
            #     vec = cmd['vector']
            #     dist = cmd['distance']
            #     status_text += f" | 移动中: 距离 {int(dist)} px"
            #     if 'waypoint_index' in cmd:
            #          status_text += f" | 节点: {cmd['waypoint_index']}/{cmd['total_waypoints']}"
            #     # 在这里，实际的 MVP 不会真的去点鼠标，除非用户明确要求
            #     # 但根据计划，我们已经计算出了 vector，这里是执行层
            #     # print(f"Executing Move: {vec}") 
            # elif cmd['action'] == 'stop':
            #     status_text += " | 待机"
            
            status_text += " | 映射模式"
                
            self.status_label.setText(status_text)
            
            # 自动滚动视图以跟随玩家
            self.view.centerOn(display_x, display_y)
            
        else:
            self.status_label.setText("定位丢失...")
            # 也可以选择停止移动以安全
            # self.motion_controller.stop()
