# Minimap Stitcher 项目本体 (Ontology)

## 项目概述
Minimap Stitcher 是一个基于计算机视觉的实时游戏地图重建系统，支持火炬之光、流放之路等ARPG游戏。它使用HSV颜色分割、相位相关算法和实时拼接技术来构建完整的游戏地图。

## 模块结构

### 1. 核心模块 (core/)
#### 1.1 capture.py - 屏幕捕获模块
- **作用**: 跨平台屏幕捕获工具，支持正方形截图和中心点定位
- **实现功能**:
  - 优先使用 mss 库进行高性能截屏
  - 备选 PIL ImageGrab 方案
  - 支持正方形区域截取
  - 自动选择最优捕获方法
- **主要类**: `SquareScreenCapture` (别名为 `ScreenCapture`)
- **关键函数**:
  - `capture_square()`: 捕获正方形区域
  - `capture()`: 捕获指定区域
  - `_capture_mss()`: 使用 mss 捕获
  - `_capture_pil()`: 使用 PIL 捕获

#### 1.2 recognizer_optimized.py - HSV颜色识别模块
- **作用**: HSV颜色识别器，用于提取地图中的墙壁、迷雾和玩家标记
- **实现功能**:
  - HSV颜色空间分割
  - 多层特征提取（墙壁、迷雾、玩家）
  - 图像预处理（CLAHE增强、颜色深化）
  - 透明地图模式支持
- **主要类**: `HSVRecognizer`
- **关键函数**:
  - `extract_combined()`: 提取组合特征用于拼接
  - `extract_walls()`: 提取墙壁层
  - `extract_fog()`: 提取迷雾层
  - `extract_player()`: 提取玩家标记
  - `preprocess_image()`: 图像预处理
  - `get_raw_gray()`: 获取原始灰度图

#### 1.3 stitcher_optimized.py - 地图拼接模块
- **作用**: 实时地图拼接器，使用相位相关法进行位移计算
- **实现功能**:
  - 相位相关算法计算位移
  - 最优缝合线消除残影
  - 位移平滑处理
  - 多层地图管理（墙体、迷雾、探索区域）
- **主要类**: `MapStitcher`
- **关键函数**:
  - `add_frame()`: 添加新帧到地图
  - `_estimate_displacement_phase_correlation()`: 相位相关位移估计
  - `_place_frame_with_seam()`: 使用缝合线放置帧
  - `get_enhanced_map()`: 获取增强地图
  - `get_statistics()`: 获取统计信息

#### 1.4 tracker.py - 人物追踪模块
- **作用**: 从HSV mask中检测玩家位置并跟踪轨迹
- **实现功能**:
  - 从玩家mask中检测位置
  - 轨迹记录和绘制
  - 全局坐标轨迹管理
- **主要类**: `PlayerTracker`
- **关键函数**:
  - `detect_player()`: 检测玩家位置
  - `update_global_trail()`: 更新全局轨迹
  - `draw_trail_on_map()`: 在地图上绘制轨迹

#### 1.5 pathfinder.py - 路径查找模块
- **作用**: A*寻路算法实现，针对大地图进行优化
- **实现功能**:
  - 降采样网格寻路
  - A*算法实现
  - 障碍物膨胀处理
- **主要类**: `PathFinder`
- **关键函数**:
  - `find_path()`: 寻找路径
  - `_astar()`: A*算法实现
  - `_find_nearest_walkable()`: 寻找最近可通行点

### 2. GUI模块 (gui/)
#### 2.1 main_window.py - 主窗口模块
- **作用**: 集成所有功能的主界面，包括区域选择、实时监控、参数调整
- **实现功能**:
  - 区域选择和中心点选择
  - 实时监控控制
  - 参数调整界面
  - 地图显示和统计信息
  - 导航路径显示
- **主要类**: `MainWindow`
- **关键函数**:
  - `setup_ui()`: 设置界面
  - `select_region()`: 选择监控区域
  - `select_center_point()`: 选择中心点
  - `capture_and_process()`: 捕获并处理
  - `update_displays()`: 更新显示

#### 2.2 overlay.py - 透明覆盖层模块
- **作用**: 用于在屏幕上画框选择小地图区域的透明覆盖层
- **实现功能**:
  - 全屏透明覆盖
  - 鼠标拖拽选择区域
  - 键盘快捷键支持
- **主要类**: `TransparentOverlay`
- **关键函数**:
  - `paintEvent()`: 绘制覆盖层
  - `mousePressEvent()`: 鼠标按下事件
  - `keyPressEvent()`: 键盘事件

#### 2.3 center_selector.py - 中心点选择模块
- **作用**: 用于选择人物位置作为截图中心点的覆盖层
- **实现功能**:
  - 十字准星选择中心点
  - 键盘确认/取消操作
- **主要类**: `CenterPointSelector`
- **关键函数**:
  - `paintEvent()`: 绘制覆盖层
  - `mousePressEvent()`: 选择中心点
  - `_draw_crosshair()`: 绘制十字准星

#### 2.4 color_picker.py - 颜色选择器模块
- **作用**: 交互式颜色选择工具，用于选择墙体和人物颜色
- **实现功能**:
  - 像素级颜色选择
  - HSV范围计算
  - 实时预览效果
  - 坐标映射处理
- **主要类**: `ColorPickerDialog`
- **关键函数**:
  - `calculate_hsv_ranges()`: 计算HSV范围
  - `update_preview()`: 更新预览
  - `on_pixel_clicked()`: 像素点击事件

#### 2.5 widgets.py - 自定义组件模块
- **作用**: 包含各种自定义GUI组件
- **实现功能**:
  - 可点击图像标签
  - 可缩放地图组件
  - 可折叠地图组
- **主要类**:
  - `ClickableImageLabel`: 可点击图像标签
  - `ScalableMapWidget`: 可缩放地图组件
  - `CollapsibleMapGroup`: 可折叠地图组
- **关键函数**:
  - `mousePressEvent()`: 鼠标点击事件处理
  - `zoom_in()/zoom_out()`: 缩放功能
  - `_apply_scale()`: 应用缩放

#### 2.6 advanced_settings.py - 高级设置模块
- **作用**: 高级参数调节面板，允许用户调节图像处理参数
- **实现功能**:
  - 图像预处理参数调节
  - 特征提取参数调节
  - 参数保存/加载
  - 预设参数管理
- **主要类**: `AdvancedSettingsDialog`
- **关键函数**:
  - `setup_ui()`: 设置界面
  - `apply_params()`: 应用参数
  - `load_current_params()`: 加载当前参数

### 3. 工具模块 (utils/)
#### 3.1 __init__.py - 工具模块初始化
- **作用**: 工具模块的初始化文件

### 4. 主程序模块
#### 4.1 main.py - 程序入口
- **作用**: 程序的主入口点
- **实现功能**:
  - 创建Qt应用程序
  - 初始化主窗口
  - 启动GUI界面
- **关键函数**: `main()`

#### 4.2 logging_system.py - 日志系统
- **作用**: 详细的日志记录系统
- **实现功能**:
  - 系统信息记录
  - 参数记录
  - 处理步骤记录
  - 日志文件管理
- **关键函数**:
  - `setup_detailed_logging()`: 设置详细日志
  - `log_image_processing_step()`: 记录图像处理步骤

## 模块间引用关系

### 核心模块内部引用
- `core/__init__.py` 导出所有核心类
- `recognizer_optimized.py` 使用 OpenCV 和 NumPy 进行图像处理
- `stitcher_optimized.py` 使用 OpenCV、NumPy 和 collections 模块
- `tracker.py` 使用 OpenCV、NumPy 和 collections 模块
- `pathfinder.py` 使用 OpenCV、NumPy 和 heapq 模块

### GUI模块引用关系
- `gui/__init__.py` 导出所有GUI类
- `main_window.py` 引用所有核心模块 (`ScreenCapture`, `HSVRecognizer`, `MapStitcher`, `PlayerTracker`)
- `main_window.py` 引用其他GUI模块 (`TransparentOverlay`, `CenterPointSelector`, `ColorPickerDialog`, `AdvancedSettingsDialog`)
- `color_picker.py` 引用 `recognizer_optimized.py` 中的 `HSVRecognizer`
- `widgets.py` 引用 PySide6 模块
- `advanced_settings.py` 引用 PySide6 模块

### 主程序引用关系
- `main.py` 引用 `gui.MainWindow`
- `main_window.py` 作为中央枢纽引用几乎所有其他模块

### 依赖关系图
```
main.py
  ↓
MainWindow (gui/main_window.py)
  ├── ScreenCapture (core/capture.py)
  ├── HSVRecognizer (core/recognizer_optimized.py)
  ├── MapStitcher (core/stitcher_optimized.py)
  ├── PlayerTracker (core/tracker.py)
  ├── PathFinder (core/pathfinder.py)
  ├── TransparentOverlay (gui/overlay.py)
  ├── CenterPointSelector (gui/center_selector.py)
  ├── ColorPickerDialog (gui/color_picker.py)
  ├── ClickableImageLabel (gui/widgets.py)
  └── AdvancedSettingsDialog (gui/advanced_settings.py)
```

## 项目特点
1. **高性能**: 使用相位相关算法进行快速位移计算
2. **实时处理**: 支持10fps实时处理
3. **多平台**: 支持Windows/Linux/Mac
4. **用户友好**: 提供直观的GUI界面
5. **可扩展**: 模块化设计便于功能扩展
6. **精确识别**: HSV颜色分割和图像增强技术