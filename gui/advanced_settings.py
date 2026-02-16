"""
高级参数调节面板
允许用户调节图像处理的各种参数
"""

import json
from datetime import datetime

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, 
    QSlider, QLabel, QPushButton, QSpinBox, 
    QDoubleSpinBox, QCheckBox, QTextEdit, QTabWidget, QWidget
)
from PySide6.QtCore import Qt


class AdvancedSettingsDialog(QDialog):
    """高级参数调节对话框"""

    def __init__(self, parent, current_params):
        super().__init__(parent)
        self.setWindowTitle("高级参数调节")
        self.resize(800, 600)
        
        # current_params is a dict passed from main_window
        self.current_params = current_params
        
        # 保存recognizer引用以便实时应用
        if hasattr(parent, 'recognizer'):
            self.recognizer = parent.recognizer
        else:
            self.recognizer = None

        # 保存stitcher引用以便实时应用
        if hasattr(parent, 'stitcher'):
            self.stitcher = parent.stitcher
        else:
            self.stitcher = None
        
        self.setup_ui()
        self.load_current_params()

    def setup_ui(self):
        """设置界面"""
        layout = QVBoxLayout(self)
        
        # 创建选项卡
        tab_widget = QTabWidget()
        
        # 图像预处理选项卡
        preprocessing_tab = self.create_preprocessing_tab()
        tab_widget.addTab(preprocessing_tab, "图像预处理")
        
        # 特征提取选项卡
        feature_tab = self.create_feature_tab()
        tab_widget.addTab(feature_tab, "特征提取")
        
        # 参数管理选项卡
        param_tab = self.create_param_management_tab()
        tab_widget.addTab(param_tab, "参数管理")
        
        # 拼接算法选项卡
        stitcher_tab = self.create_stitcher_tab()
        tab_widget.addTab(stitcher_tab, "拼接算法")

        layout.addWidget(tab_widget)
        
        # 底部按钮
        button_layout = QHBoxLayout()
        
        self.apply_btn = QPushButton("应用参数")
        self.apply_btn.clicked.connect(self.apply_params)
        button_layout.addWidget(self.apply_btn)
        
        self.reset_btn = QPushButton("重置为默认")
        self.reset_btn.clicked.connect(self.reset_to_default)
        button_layout.addWidget(self.reset_btn)
        
        self.ok_btn = QPushButton("确定")
        self.ok_btn.clicked.connect(self.accept)
        button_layout.addWidget(self.ok_btn)
        
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)
        
        layout.addLayout(button_layout)

    def create_info_label(self, text):
        """创建说明标签"""
        label = QLabel(text)
        label.setWordWrap(True)
        label.setStyleSheet("color: #bdc3c7; font-size: 11px; font-style: italic; margin-bottom: 5px; background-color: #2c3e50; padding: 5px; border-radius: 3px;")
        return label

    def create_preprocessing_tab(self):
        """创建图像预处理选项卡"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # 高斯模糊组
        blur_group = QGroupBox("高斯模糊")
        blur_layout = QHBoxLayout()
        
        # 说明
        blur_group.setLayout(blur_layout) # 注意：这里原代码结构有点怪，layout是在最后设置的
        # 重新组织布局
        blur_main_layout = QVBoxLayout()
        blur_main_layout.addWidget(self.create_info_label(
            "作用：去除图像噪点，平滑细节。\n"
            "调节：通常保持3。图像非常嘈杂时可调大。\n"
            "影响：过大会导致墙体模糊，丢失细节。"
        ))
        
        blur_controls = QHBoxLayout()
        blur_controls.addWidget(QLabel("模糊强度:"))
        self.blur_strength_spin = QSpinBox()
        self.blur_strength_spin.setRange(1, 15)
        self.blur_strength_spin.setSingleStep(2)  # 只允许奇数
        self.blur_strength_spin.setValue(3)
        blur_controls.addWidget(self.blur_strength_spin)
        
        blur_main_layout.addLayout(blur_controls)
        blur_group.setLayout(blur_main_layout)
        layout.addWidget(blur_group)
        
        # 颜色深化组
        deepen_group = QGroupBox("颜色深化")
        deepen_layout = QVBoxLayout()
        
        deepen_layout.addWidget(self.create_info_label(
            "作用：增强特定颜色的墙体（如蓝色/红色），压暗背景。\n"
            "调节：蓝色地图建议开启并调高蓝色增强。\n"
            "影响：使特定颜色的墙体与背景对比更明显。"
        ))
        
        # 深化开关
        self.deepen_enabled_check = QCheckBox("启用颜色深化")
        deepen_layout.addWidget(self.deepen_enabled_check)
        
        # 对比度增强
        contrast_layout = QHBoxLayout()
        contrast_layout.addWidget(QLabel("对比度增强系数:"))
        self.contrast_factor_spin = QDoubleSpinBox()
        self.contrast_factor_spin.setRange(0.5, 3.0)
        self.contrast_factor_spin.setSingleStep(0.1)
        self.contrast_factor_spin.setValue(1.2)
        contrast_layout.addWidget(self.contrast_factor_spin)
        contrast_layout.addWidget(QLabel("(α值，值越大对比度越高)"))
        deepen_layout.addLayout(contrast_layout)
        
        # 蓝色增强
        blue_layout = QHBoxLayout()
        blue_layout.addWidget(QLabel("蓝色通道增强:"))
        self.blue_boost_spin = QDoubleSpinBox()
        self.blue_boost_spin.setRange(0.5, 3.0)
        self.blue_boost_spin.setSingleStep(0.1)
        self.blue_boost_spin.setValue(1.1)
        blue_layout.addWidget(self.blue_boost_spin)
        blue_layout.addWidget(QLabel("(蓝色通道乘数)"))
        deepen_layout.addLayout(blue_layout)
        
        deepen_group.setLayout(deepen_layout)
        layout.addWidget(deepen_group)
        
        # Gamma校正组
        gamma_group = QGroupBox("Gamma校正 (中间调压暗)")
        gamma_layout = QVBoxLayout()
        
        gamma_layout.addWidget(self.create_info_label(
            "作用：压暗中间调（灰色背景），保留高光（墙体）。\n"
            "调节：背景噪点多、像雪花一样时，调大Gamma值。\n"
            "影响：值越大背景越黑，越干净，但可能丢失暗淡的墙体。"
        ))
        
        gamma_controls = QHBoxLayout()
        self.gamma_enabled_check = QCheckBox("启用Gamma校正")
        gamma_controls.addWidget(self.gamma_enabled_check)
        
        gamma_controls.addWidget(QLabel("Gamma值:"))
        self.gamma_value_spin = QDoubleSpinBox()
        self.gamma_value_spin.setRange(0.1, 5.0)
        self.gamma_value_spin.setSingleStep(0.1)
        self.gamma_value_spin.setValue(2.0)
        self.gamma_value_spin.setToolTip("值越大，中间调越暗。用于压暗背景噪音，突出高亮墙体。")
        gamma_controls.addWidget(self.gamma_value_spin)
        
        gamma_layout.addLayout(gamma_controls)
        gamma_group.setLayout(gamma_layout)
        layout.addWidget(gamma_group)
        
        # TopHat结构提取组
        tophat_group = QGroupBox("TopHat结构提取 (增强细微线条)")
        tophat_layout = QVBoxLayout()
        
        tophat_layout.addWidget(self.create_info_label(
            "作用：提取比背景亮的小尺寸结构（如细墙体），无视背景亮度变化。\n"
            "调节：核大小应略大于墙体宽度。增强强度控制提取出来的亮度。\n"
            "影响：能有效连接断裂的墙体，解决光照不均匀问题。"
        ))
        
        self.tophat_enabled_check = QCheckBox("启用TopHat")
        tophat_layout.addWidget(self.tophat_enabled_check)
        
        tophat_params = QHBoxLayout()
        tophat_params.addWidget(QLabel("核大小:"))
        self.tophat_kernel_spin = QSpinBox()
        self.tophat_kernel_spin.setRange(3, 31)
        self.tophat_kernel_spin.setSingleStep(2)
        self.tophat_kernel_spin.setValue(15)
        self.tophat_kernel_spin.setToolTip("结构元素的尺寸。应略大于墙体宽度。")
        tophat_params.addWidget(self.tophat_kernel_spin)
        
        tophat_params.addWidget(QLabel("增强强度:"))
        self.tophat_strength_spin = QSpinBox()
        self.tophat_strength_spin.setRange(1, 10)
        self.tophat_strength_spin.setValue(4)
        self.tophat_strength_spin.setToolTip("提取出的结构增强倍数。")
        tophat_params.addWidget(self.tophat_strength_spin)
        
        tophat_layout.addLayout(tophat_params)
        tophat_group.setLayout(tophat_layout)
        layout.addWidget(tophat_group)

        # CLAHE增强组
        clahe_group = QGroupBox("CLAHE增强")
        clahe_layout = QVBoxLayout()
        
        clahe_layout.addWidget(self.create_info_label(
            "作用：自适应直方图均衡，增强局部对比度。\n"
            "调节：裁剪限制越小，对比度增强越温和；网格越大，处理越粗糙。\n"
            "影响：让暗处的墙体也能被识别出来，但也会放大噪点。"
        ))
        
        self.clahe_enabled_check = QCheckBox("启用CLAHE增强")
        clahe_layout.addWidget(self.clahe_enabled_check)
        
        clahe_params_layout = QHBoxLayout()
        
        clip_layout = QVBoxLayout()
        clip_layout.addWidget(QLabel("CLAHE裁剪限制:"))
        self.clahe_clip_spin = QDoubleSpinBox()
        self.clahe_clip_spin.setRange(0.1, 10.0)
        self.clahe_clip_spin.setSingleStep(0.1)
        self.clahe_clip_spin.setValue(2.0)
        clip_layout.addWidget(self.clahe_clip_spin)
        clahe_params_layout.addLayout(clip_layout)
        
        grid_layout = QVBoxLayout()
        grid_layout.addWidget(QLabel("CLAHE网格大小:"))
        self.clahe_grid_spin = QSpinBox()
        self.clahe_grid_spin.setRange(2, 32)
        self.clahe_grid_spin.setSingleStep(1)
        self.clahe_grid_spin.setValue(8)
        grid_layout.addWidget(self.clahe_grid_spin)
        clahe_params_layout.addLayout(grid_layout)
        
        clahe_layout.addLayout(clahe_params_layout)
        clahe_group.setLayout(clahe_layout)
        layout.addWidget(clahe_group)
        
        layout.addStretch()
        
        return tab

    def create_feature_tab(self):
        """创建特征提取选项卡"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # 透明地图模式组
        trans_group = QGroupBox("半透明地图模式 (针对灰色线条地图)")
        trans_layout = QVBoxLayout()
        
        trans_layout.addWidget(self.create_info_label(
            "作用：专为半透明/灰白地图设计的特殊提取算法。\n"
            "原理：基于亮度(V)与饱和度(S)的差值来提取墙体 (墙体通常亮且白)。\n"
            "影响：开启后将忽略HSV颜色范围，使用专用算法。"
        ))
        
        self.transparent_mode_check = QCheckBox("启用透明地图模式")
        trans_layout.addWidget(self.transparent_mode_check)
        
        thresh_layout = QHBoxLayout()
        thresh_layout.addWidget(QLabel("灰白提取阈值 (V-S):"))
        self.trans_wall_thresh_spin = QSpinBox()
        self.trans_wall_thresh_spin.setRange(0, 255)
        self.trans_wall_thresh_spin.setValue(60)
        thresh_layout.addWidget(self.trans_wall_thresh_spin)
        thresh_layout.addWidget(QLabel("(值越大只保留越白的部分)"))
        trans_layout.addLayout(thresh_layout)
        
        penalty_layout = QHBoxLayout()
        penalty_layout.addWidget(QLabel("饱和度惩罚系数:"))
        self.trans_sat_penalty_spin = QDoubleSpinBox()
        self.trans_sat_penalty_spin.setRange(0.0, 5.0)
        self.trans_sat_penalty_spin.setSingleStep(0.1)
        self.trans_sat_penalty_spin.setValue(1.5)
        self.trans_sat_penalty_spin.setToolTip("用于抑制彩色区域。分数 = V - S * 系数。系数越大，彩色区域得分越低。")
        penalty_layout.addWidget(self.trans_sat_penalty_spin)
        trans_layout.addLayout(penalty_layout)
        
        trans_group.setLayout(trans_layout)
        layout.addWidget(trans_group)

        # 饱和度过滤组 (新增)
        sat_group = QGroupBox("饱和度过滤 (解决彩色地图问题)")
        sat_layout = QVBoxLayout()
        
        sat_layout.addWidget(self.create_info_label(
            "作用：强制去除高饱和度的彩色区域（如玩家箭头、技能特效）。\n"
            "调节：蓝色/彩色地图请【关闭】或【设置过滤半径】（只过滤玩家周围）。\n"
            "影响：在白色地图中能完美去除箭头；但在彩色地图中会误删墙体。"
        ))
        
        self.sat_filter_check = QCheckBox("启用饱和度过滤 (去除彩色杂点)")
        sat_layout.addWidget(self.sat_filter_check)
        
        thresh_layout = QHBoxLayout()
        thresh_layout.addWidget(QLabel("过滤阈值:"))
        self.sat_thresh_spin = QSpinBox()
        self.sat_thresh_spin.setRange(0, 255)
        self.sat_thresh_spin.setValue(40)
        thresh_layout.addWidget(self.sat_thresh_spin)
        thresh_layout.addWidget(QLabel("(S通道，>此值被视为杂点)"))
        sat_layout.addLayout(thresh_layout)
        
        radius_layout = QHBoxLayout()
        radius_layout.addWidget(QLabel("过滤半径:"))
        self.sat_radius_spin = QSpinBox()
        self.sat_radius_spin.setRange(0, 500)
        self.sat_radius_spin.setValue(0)
        radius_layout.addWidget(self.sat_radius_spin)
        radius_layout.addWidget(QLabel("(0=全局过滤, >0=仅过滤玩家周围)"))
        sat_layout.addLayout(radius_layout)
        
        sat_group.setLayout(sat_layout)
        layout.addWidget(sat_group)
        
        # Canny边缘检测组
        edge_group = QGroupBox("Canny边缘检测")
        edge_layout = QVBoxLayout()
        
        edge_layout.addWidget(self.create_info_label(
            "作用：检测图像中的边缘线条（用于辅助配准）。\n"
            "调节：低阈值越小，细节越多（但也越噪）；高阈值越大，边缘要求越严格。\n"
            "影响：提供额外的几何特征，帮助在纯色墙体上进行配准。"
        ))
        
        # 低阈值
        low_layout = QHBoxLayout()
        low_layout.addWidget(QLabel("低阈值:"))
        self.edge_low_spin = QSpinBox()
        self.edge_low_spin.setRange(0, 255)
        self.edge_low_spin.setValue(50)
        low_layout.addWidget(self.edge_low_spin)
        edge_layout.addLayout(low_layout)
        
        # 高阈值
        high_layout = QHBoxLayout()
        high_layout.addWidget(QLabel("高阈值:"))
        self.edge_high_spin = QSpinBox()
        self.edge_high_spin.setRange(0, 255)
        self.edge_high_spin.setValue(150)
        high_layout.addWidget(self.edge_high_spin)
        edge_layout.addLayout(high_layout)
        
        edge_group.setLayout(edge_layout)
        layout.addWidget(edge_group)
        
        # 权重设置组
        weight_group = QGroupBox("特征融合权重")
        weight_layout = QVBoxLayout()
        
        weight_layout.addWidget(self.create_info_label(
            "作用：决定最终用于配准的图像中，各部分特征的占比。\n"
            "调节：墙体权重通常最高；边缘权重次之；灰度权重用于补充纹理。\n"
            "影响：权重分配不当可能导致配准偏向于噪点而非真实墙体。"
        ))
        
        # 墙壁权重
        wall_w_layout = QHBoxLayout()
        wall_w_layout.addWidget(QLabel("墙壁层权重:"))
        self.wall_weight_spin = QSpinBox()
        self.wall_weight_spin.setRange(0, 100)
        self.wall_weight_spin.setValue(50)
        wall_w_layout.addWidget(self.wall_weight_spin)
        weight_layout.addLayout(wall_w_layout)
        
        # 边缘权重
        edge_w_layout = QHBoxLayout()
        edge_w_layout.addWidget(QLabel("边缘层权重:"))
        self.edge_weight_spin = QSpinBox()
        self.edge_weight_spin.setRange(0, 100)
        self.edge_weight_spin.setValue(30)
        edge_w_layout.addWidget(self.edge_weight_spin)
        weight_layout.addLayout(edge_w_layout)
        
        # 灰度权重
        gray_w_layout = QHBoxLayout()
        gray_w_layout.addWidget(QLabel("灰度层权重:"))
        self.gray_weight_spin = QSpinBox()
        self.gray_weight_spin.setRange(0, 100)
        self.gray_weight_spin.setValue(20)
        gray_w_layout.addWidget(self.gray_weight_spin)
        weight_layout.addLayout(gray_w_layout)
        
        weight_group.setLayout(weight_layout)
        layout.addWidget(weight_group)
        
        layout.addStretch()
        return tab

    def get_params(self):
        """获取当前设置的参数"""
        return self.current_params

    def create_param_management_tab(self):
        """创建参数管理选项卡"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # 保存参数组
        save_group = QGroupBox("保存参数")
        save_layout = QVBoxLayout()
        
        save_btn_layout = QHBoxLayout()
        self.save_current_btn = QPushButton("保存当前参数")
        self.save_current_btn.clicked.connect(self.save_current_params)
        save_btn_layout.addWidget(self.save_current_btn)
        
        self.param_name_edit = QLineEdit()
        self.param_name_edit.setPlaceholderText("输入参数配置名称")
        save_btn_layout.addWidget(self.param_name_edit)
        
        save_layout.addLayout(save_btn_layout)
        
        self.save_status_label = QLabel("")
        save_layout.addWidget(self.save_status_label)
        
        save_group.setLayout(save_layout)
        layout.addWidget(save_group)
        
        # 加载参数组
        load_group = QGroupBox("加载参数")
        load_layout = QVBoxLayout()
        
        load_btn_layout = QHBoxLayout()
        self.load_params_btn = QPushButton("浏览并加载参数")
        self.load_params_btn.clicked.connect(self.load_params_from_file)
        load_btn_layout.addWidget(self.load_params_btn)

        self.apply_loaded_btn = QPushButton("应用加载的参数")
        self.apply_loaded_btn.clicked.connect(self.apply_loaded_params)
        load_btn_layout.addWidget(self.apply_loaded_btn)

        load_layout.addLayout(load_btn_layout)

        self.loaded_params_text = QTextEdit()
        self.loaded_params_text.setMaximumHeight(150)
        self.loaded_params_text.setReadOnly(True)
        load_layout.addWidget(self.loaded_params_text)

        load_group.setLayout(load_layout)
        layout.addWidget(load_group)

        # 预设参数组
        preset_group = QGroupBox("预设参数")
        preset_layout = QHBoxLayout()

        self.preset_combo = QComboBox()
        self.preset_combo.addItems([
            "默认参数",
            "流放之路优化",
            "火炬之光优化",
            "高对比度模式",
            "低对比度模式"
        ])
        preset_layout.addWidget(self.preset_combo)

        self.apply_preset_btn = QPushButton("应用预设")
        self.apply_preset_btn.clicked.connect(self.apply_preset)
        preset_layout.addWidget(self.apply_preset_btn)

        preset_group.setLayout(preset_layout)
        layout.addWidget(preset_group)

        layout.addStretch()

        return tab

    def create_stitcher_tab(self):
        """创建拼接算法选项卡"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # 配准参数组
        match_group = QGroupBox("配准参数 (Frame-to-Frame)")
        match_layout = QVBoxLayout()
        
        match_layout.addWidget(self.create_info_label(
            "作用：控制帧与帧之间（F2F）的匹配严格程度。\n"
            "调节：如果经常出现红色❌（配准失败），请调低阈值。\n"
            "影响：阈值过低可能导致误匹配（地图乱飞）；阈值过高会导致断连。"
        ))
        
        conf_layout = QHBoxLayout()
        conf_layout.addWidget(QLabel("F2F匹配阈值:"))
        self.conf_thresh_spin = QDoubleSpinBox()
        self.conf_thresh_spin.setRange(0.1, 0.9)
        self.conf_thresh_spin.setSingleStep(0.05)
        self.conf_thresh_spin.setValue(0.30)
        self.conf_thresh_spin.setToolTip("Frame-to-Frame匹配的最低置信度。低于此值视为匹配失败。")
        conf_layout.addWidget(self.conf_thresh_spin)
        match_layout.addLayout(conf_layout)
        
        match_group.setLayout(match_layout)
        layout.addWidget(match_group)
        
        # 锚点参数组
        anchor_group = QGroupBox("锚点参数 (Keyframe Anchor)")
        anchor_layout = QVBoxLayout()
        
        anchor_layout.addWidget(self.create_info_label(
            "作用：控制关键帧（Anchor）的切换频率。\n"
            "调节：调高=频繁切换（精度高但累积误差大）；调低=很少切换（稳但可能跟丢）。\n"
            "影响：这是防止地图“漂移”和“双眼皮”的核心机制。"
        ))
        
        key_layout = QHBoxLayout()
        key_layout.addWidget(QLabel("关键帧维持阈值:"))
        self.keyframe_thresh_spin = QDoubleSpinBox()
        self.keyframe_thresh_spin.setRange(0.1, 0.9)
        self.keyframe_thresh_spin.setSingleStep(0.05)
        self.keyframe_thresh_spin.setValue(0.25)
        self.keyframe_thresh_spin.setToolTip("只要与关键帧的匹配度高于此值，就不切换关键帧。用于减少累积误差。")
        key_layout.addWidget(self.keyframe_thresh_spin)
        anchor_layout.addLayout(key_layout)
        
        anchor_group.setLayout(anchor_layout)
        layout.addWidget(anchor_group)
        
        # 融合参数组
        merge_group = QGroupBox("融合参数 (Weighted Merge)")
        merge_layout = QVBoxLayout()
        
        merge_layout.addWidget(self.create_info_label(
            "作用：控制地图的更新速度和抗噪能力。\n"
            "调节：增量越小，墙体变实越慢，但抗噪越好；最大权重控制墙体'厚度'上限。\n"
            "影响：防止单帧的错误识别污染整个地图。"
        ))
        
        add_layout = QHBoxLayout()
        add_layout.addWidget(QLabel("单帧权重增量:"))
        self.weight_add_spin = QDoubleSpinBox()
        self.weight_add_spin.setRange(0.05, 1.0)
        self.weight_add_spin.setSingleStep(0.05)
        self.weight_add_spin.setValue(0.3)
        self.weight_add_spin.setToolTip("每帧匹配成功后，墙体权重的增加值。值越小越抗噪，但更新越慢。")
        add_layout.addWidget(self.weight_add_spin)
        merge_layout.addLayout(add_layout)
        
        cap_layout = QHBoxLayout()
        cap_layout.addWidget(QLabel("最大权重限制:"))
        self.weight_cap_spin = QDoubleSpinBox()
        self.weight_cap_spin.setRange(1.0, 20.0)
        self.weight_cap_spin.setSingleStep(0.5)
        self.weight_cap_spin.setValue(5.0)
        self.weight_cap_spin.setToolTip("权重的上限值。防止权重无限累积。")
        cap_layout.addWidget(self.weight_cap_spin)
        merge_layout.addLayout(cap_layout)
        
        merge_group.setLayout(merge_layout)
        layout.addWidget(merge_group)
        
        layout.addStretch()
        return tab

    def load_current_params(self):
        """加载当前参数到界面"""
        params = self.current_params

        # 预处理参数
        self.blur_strength_spin.setValue(3)  # 高斯模糊核大小固定为3x3
        self.deepen_enabled_check.setChecked(params.get('deepen_enabled', True))
        self.contrast_factor_spin.setValue(params.get('deepen_factor', 1.2))
        self.blue_boost_spin.setValue(params.get('blue_boost', 1.1))
        
        self.gamma_enabled_check.setChecked(params.get('gamma_enabled', True))
        self.gamma_value_spin.setValue(params.get('gamma_value', 2.0))
        
        self.tophat_enabled_check.setChecked(params.get('tophat_enabled', True))
        self.tophat_kernel_spin.setValue(params.get('tophat_kernel_size', 15))
        self.tophat_strength_spin.setValue(params.get('tophat_strength', 4))
        
        self.clahe_enabled_check.setChecked(params.get('clahe_enabled', True))
        self.clahe_clip_spin.setValue(params.get('clahe_clip', 2.0))
        self.clahe_grid_spin.setValue(params.get('clahe_grid', 8))

        # 特征提取参数
        self.edge_low_spin.setValue(params.get('edge_low', 50))
        self.edge_high_spin.setValue(params.get('edge_high', 150))
        self.wall_weight_spin.setValue(params.get('wall_weight', 50))
        self.edge_weight_spin.setValue(params.get('edge_weight', 30))
        self.gray_weight_spin.setValue(params.get('gray_weight', 20))
        
        # 透明模式参数
        self.transparent_mode_check.setChecked(params.get('transparent_mode', False))
        self.trans_wall_thresh_spin.setValue(params.get('trans_wall_thresh', 60))
        self.trans_sat_penalty_spin.setValue(params.get('trans_sat_penalty', 1.5))

        # 饱和度过滤
        self.sat_filter_check.setChecked(params.get('sat_filter_enabled', True))
        self.sat_thresh_spin.setValue(params.get('sat_filter_thresh', 40))
        self.sat_radius_spin.setValue(params.get('sat_filter_radius', 0))

        # 拼接器参数
        if hasattr(self, 'conf_thresh_spin'):
            self.conf_thresh_spin.setValue(params.get('conf_thresh', 0.30))
            self.keyframe_thresh_spin.setValue(params.get('keyframe_thresh', 0.25))
            self.weight_add_spin.setValue(params.get('weight_add', 0.3))
            self.weight_cap_spin.setValue(params.get('weight_cap', 5.0))

    def apply_params(self):
        """应用参数到识别器"""
        params = {
            # 预处理参数
            'deepen_enabled': self.deepen_enabled_check.isChecked(),
            'deepen_factor': self.contrast_factor_spin.value(),
            'blue_boost': self.blue_boost_spin.value(),
            'gamma_enabled': self.gamma_enabled_check.isChecked(),
            'gamma_value': self.gamma_value_spin.value(),
            'tophat_enabled': self.tophat_enabled_check.isChecked(),
            'tophat_kernel_size': self.tophat_kernel_spin.value(),
            'tophat_strength': self.tophat_strength_spin.value(),
            'clahe_enabled': self.clahe_enabled_check.isChecked(),
            'clahe_clip': self.clahe_clip_spin.value(),
            'clahe_grid': self.clahe_grid_spin.value(),

            # 特征提取参数
            'edge_low': self.edge_low_spin.value(),
            'edge_high': self.edge_high_spin.value(),
            'wall_weight': self.wall_weight_spin.value(),
            'edge_weight': self.edge_weight_spin.value(),
            'gray_weight': self.gray_weight_spin.value(),
            
            # 透明模式参数
            'transparent_mode': self.transparent_mode_check.isChecked(),
            'trans_wall_thresh': self.trans_wall_thresh_spin.value(),
            'trans_sat_penalty': self.trans_sat_penalty_spin.value(),

            # 饱和度过滤参数
            'sat_filter_enabled': self.sat_filter_check.isChecked(),
            'sat_filter_thresh': self.sat_thresh_spin.value(),
            'sat_filter_radius': self.sat_radius_spin.value(),

            # 拼接器参数
            'conf_thresh': self.conf_thresh_spin.value() if hasattr(self, 'conf_thresh_spin') else 0.3,
            'keyframe_thresh': self.keyframe_thresh_spin.value() if hasattr(self, 'keyframe_thresh_spin') else 0.25,
            'weight_add': self.weight_add_spin.value() if hasattr(self, 'weight_add_spin') else 0.3,
            'weight_cap': self.weight_cap_spin.value() if hasattr(self, 'weight_cap_spin') else 5.0
        }

        if self.recognizer:
            self.recognizer.set_params(params)
        else:
            print("⚠️ 警告：无法实时应用参数（未找到识别器实例）")
            
        if self.stitcher:
            self.stitcher.set_params(params)
        else:
            print("⚠️ 警告：无法实时应用参数（未找到拼接器实例）")

        self.current_params = params

        print("✅ 参数已应用")

    def reset_to_default(self):
        """重置为默认参数"""
        # 重置为默认值
        self.deepen_enabled_check.setChecked(True)
        self.contrast_factor_spin.setValue(1.2)
        self.blue_boost_spin.setValue(1.1)
        self.gamma_enabled_check.setChecked(True)
        self.gamma_value_spin.setValue(2.0)
        self.tophat_enabled_check.setChecked(True)
        self.tophat_kernel_spin.setValue(15)
        self.tophat_strength_spin.setValue(4)
        self.clahe_enabled_check.setChecked(True)
        self.clahe_clip_spin.setValue(2.0)
        self.clahe_grid_spin.setValue(8)

        self.edge_low_spin.setValue(50)
        self.edge_high_spin.setValue(150)
        self.wall_weight_spin.setValue(50)
        self.edge_weight_spin.setValue(30)
        self.gray_weight_spin.setValue(20)
        
        self.sat_filter_check.setChecked(True)
        self.sat_thresh_spin.setValue(40)
        self.sat_radius_spin.setValue(0)
        
        self.transparent_mode_check.setChecked(False)
        self.trans_wall_thresh_spin.setValue(60)
        self.trans_sat_penalty_spin.setValue(1.5)
        
        if hasattr(self, 'conf_thresh_spin'):
            self.conf_thresh_spin.setValue(0.30)
            self.keyframe_thresh_spin.setValue(0.25)
            self.weight_add_spin.setValue(0.3)
            self.weight_cap_spin.setValue(5.0)

    def save_current_params(self):
        """保存当前参数到文件"""
        if not self.param_name_edit.text().strip():
            self.save_status_label.setText("请输入参数配置名称")
            return

        param_name = self.param_name_edit.text().strip()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"params_{param_name}_{timestamp}.json"

        params = {
            'name': param_name,
            'timestamp': datetime.now().isoformat(),
            'parameters': self.current_params
        }

        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(params, f, indent=2, ensure_ascii=False)

            self.save_status_label.setText(f"✅ 参数已保存到 {filename}")
        except Exception as e:
            self.save_status_label.setText(f"❌ 保存失败: {str(e)}")

    def load_params_from_file(self):
        """从文件加载参数"""
        filename, _ = QFileDialog.getOpenFileName(
            self, "选择参数文件", "", "JSON Files (*.json)"
        )

        if not filename:
            return

        try:
            with open(filename, 'r', encoding='utf-8') as f:
                data = json.load(f)

            if 'parameters' in data:
                params = data['parameters']
                self.loaded_params_text.setPlainText(json.dumps(params, indent=2, ensure_ascii=False))

                # 临时存储以便应用
                self.temp_loaded_params = params
                self.save_status_label.setText(f"已加载参数文件: {filename}")
            else:
                self.loaded_params_text.setPlainText("文件格式错误：缺少parameters字段")

        except Exception as e:
            self.loaded_params_text.setPlainText(f"加载失败: {str(e)}")

    def apply_loaded_params(self):
        """应用已加载的参数"""
        if hasattr(self, 'temp_loaded_params'):
            params = self.temp_loaded_params
            # 更新界面控件
            self.deepen_enabled_check.setChecked(params.get('deepen_enabled', True))
            self.contrast_factor_spin.setValue(params.get('deepen_factor', 1.2))
            self.blue_boost_spin.setValue(params.get('blue_boost', 1.1))
            self.clahe_enabled_check.setChecked(params.get('clahe_enabled', True))
            self.clahe_clip_spin.setValue(params.get('clahe_clip', 2.0))
            self.clahe_grid_spin.setValue(params.get('clahe_grid', 8))

            self.edge_low_spin.setValue(params.get('edge_low', 50))
            self.edge_high_spin.setValue(params.get('edge_high', 150))
            self.wall_weight_spin.setValue(params.get('wall_weight', 50))
            self.edge_weight_spin.setValue(params.get('edge_weight', 30))
            self.gray_weight_spin.setValue(params.get('gray_weight', 20))

            self.sat_filter_check.setChecked(params.get('sat_filter_enabled', True))
            self.sat_thresh_spin.setValue(params.get('sat_filter_thresh', 40))
            self.sat_radius_spin.setValue(params.get('sat_filter_radius', 0))

            print("✅ 已加载参数，点击应用参数按钮生效")

    def apply_preset(self):
        """应用预设参数"""
        preset = self.preset_combo.currentText()

        if preset == "默认参数":
            self.reset_to_default()
        elif preset == "流放之路优化":
            # 为流放之路优化的参数
            self.contrast_factor_spin.setValue(1.3)
            self.blue_boost_spin.setValue(1.2)
            self.edge_low_spin.setValue(40)
            self.edge_high_spin.setValue(120)
            self.wall_weight_spin.setValue(60)
            self.edge_weight_spin.setValue(25)
            self.gray_weight_spin.setValue(15)
        elif preset == "火炬之光优化":
            # 为火炬之光优化的参数
            self.contrast_factor_spin.setValue(1.1)
            self.blue_boost_spin.setValue(1.0)
            self.edge_low_spin.setValue(60)
            self.edge_high_spin.setValue(180)
            self.wall_weight_spin.setValue(45)
            self.edge_weight_spin.setValue(35)
            self.gray_weight_spin.setValue(20)
        elif preset == "高对比度模式":
            self.contrast_factor_spin.setValue(1.5)
            self.blue_boost_spin.setValue(1.3)
            self.clahe_clip_spin.setValue(3.0)
        elif preset == "低对比度模式":
            self.contrast_factor_spin.setValue(1.0)
            self.blue_boost_spin.setValue(1.0)
            self.clahe_clip_spin.setValue(1.5)


# 导入必要的模块
from PySide6.QtWidgets import QWidget, QComboBox, QLineEdit, QFileDialog