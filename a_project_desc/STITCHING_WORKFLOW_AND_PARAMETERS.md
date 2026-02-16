# 绘制地图(Stitching)工作流程与参数全解

本文档旨在详细梳理“绘制地图”功能的完整工作流程，并列出在此过程中涉及的所有关键参数，以确保在“导航模式”加载地图时，能够100%复现绘制时的环境配置。

## 一、 核心组件

绘制地图功能主要由以下几个核心模块协同工作：

- **`gui/improved_main_window.py`**: 主UI窗口，管理所有UI组件和用户交互，是参数配置的入口。
- **`gui/advanced_settings.py`**: 高级设置面板，用于微调图像识别的复杂参数。
- **`core/stitcher_core.py`**: 拼接核心，负责接收图像、计算位移、并将图像拼接到全局地图上。
- **`core/recognizer_optimized.py`**: 图像识别器，负责从原始截图中提取出用于匹配的“墙体”等特征。
- **`core/capture.py`**: 屏幕捕捉模块，根据指定区域从屏幕上截图。

## 二、 工作流程详解

### 步骤 1: 参数配置 (用户操作)

在开始绘制之前，用户通过UI设置所有必要的参数。

1.  **定义捕捉区域**:
    -   **交互**: 用户点击“选择中心点”，然后在屏幕上点击游戏小地图的中心。
    -   **参数**:
        -   `monitor_center`: (x, y) 坐标，定义了截图区域的中心。
        -   `monitor_size`: 截图区域的边长（正方形），通常固定为200像素。

2.  **配置图像识别**:
    -   **交互**: 用户通过主界面的滑块或“高级设置”面板调整参数。
    -   **目的**: 优化 `HSVRecognizer` 的性能，使其能准确地从不同光照、不同风格的游戏地图中提取出稳定的墙体轮廓。
    -   **参数**: 详见第三节的 `Recognizer` 参数列表。

3.  **配置拼接参数**:
    -   **交互**: 用户在UI上设置。
    -   **参数**:
        -   `draw_scale`: 绘制比例。这是一个至关重要的参数，决定了地图的分辨率。默认`2.0`，意味着最终生成的地图分辨率是原始小地图的两倍。导航时必须使用完全相同的比例。

### 步骤 2: 启动绘制

1.  **初始化**:
    -   程序根据UI设置，创建并配置 `StitcherCore` 和 `HSVRecognizer` 实例。
    -   所有在UI上设置的识别器参数通过 `recognizer.set_params()` 方法注入到 `HSVRecognizer` 对象中。

2.  **启动线程**:
    -   一个独立的 `StitcherThread` 线程启动，开始执行核心的拼接循环，防止UI卡顿。

### 步骤 3: 拼接循环 (后台自动执行)

1.  **`capture`**: 捕捉模块根据 `monitor_center` 和 `monitor_size` 截取一帧屏幕图像。
2.  **`recognize`**: `StitcherCore` 将截图交给 `HSVRecognizer`。后者通过一系列预处理（Gamma, CLAHE, TopHat等）和颜色过滤，生成一张只包含墙体轮廓等关键特征的二值化“特征图”。
3.  **`stitch`**: `StitcherCore` 使用相位相关（Phase Correlation）算法对比当前帧的“特征图”和上一帧的“特征图”，计算出高精度的像素位移 `(dx, dy)`。
4.  **`update`**: 根据位移更新玩家在全局地图上的坐标，并将当前帧的“特征图”绘制到全局地图的对应位置。
5.  **重复**: 持续该循环，直到用户点击“停止”。

### 步骤 4: 保存地图与配置

1.  **收集参数**: 当用户点击“保存”时，程序会执行一个关键操作：**收集本次绘制会话期间使用的所有参数**。
    -   从主窗口获取 `monitor_center`, `monitor_size`。
    -   从 `StitcherCore` 获取 `draw_scale`。
    -   调用 `recognizer.get_params()` 获取一个包含所有识别器设置的完整字典。
    -   从导航UI面板收集 `y_bias`, `center_offset_y` 等需要与地图绑定的参数。

2.  **写入文件**:
    -   **地图数据**: 将拼接好的、巨大的地图数组保存为 `map_data.npz`。
    -   **配置文件**: 将上一步收集到的所有参数打包成一个字典，以JSON格式写入到 `config.json` 文件中。

## 三、 参数全解

以下是在 `config.json` 中必须保存的、确保环境一致性的所有参数。

### 1. Capture & Stitcher 参数

| 参数名 | 类型 | 来源模块 | 描述 |
| :--- | :--- | :--- | :--- |
| `monitor_center` | `list[int, int]` | `improved_main_window` | 截图区域在屏幕上的中心点坐标, `[x, y]`。 |
| `monitor_size` | `int` | `improved_main_window` | 截图区域的边长。 |
| `draw_scale` | `float` | `stitcher_core` | 绘制地图的放大比例，决定了地图精度。 |

### 2. Recognizer 参数

这些参数通过 `recognizer.get_params()` 统一获取。

| 参数名 | 类型 | 描述 |
| :--- | :--- | :--- |
| `wall_hsv_min` | `list` | 墙体识别的HSV颜色下限。 |
| `wall_hsv_max` | `list` | 墙体识别的HSV颜色上限。 |
| `fog_hsv_min` | `list` | 迷雾识别的HSV颜色下限。 |
| `fog_hsv_max` | `list` | 迷雾识别的HSV颜色上限。 |
| `player_hsv_min`| `list` | 玩家箭头识别的HSV颜色下限。 |
| `player_hsv_max`| `list` | 玩家箭头识别的HSV颜色上限。 |
| `enable_wall` | `bool` | 是否启用墙体识别。 |
| `enable_fog` | `bool` | 是否启用迷雾识别。 |
| `clahe_enabled` | `bool` | 是否启用CLAHE（自适应直方图均衡化）增强。 |
| `deepen_enabled`| `bool` | 是否启用颜色深化处理。 |
| `gamma_enabled` | `bool` | 是否启用Gamma校正（用于压暗背景）。 |
| `tophat_enabled`| `bool` | 是否启用顶帽变换（用于提取精细线条）。 |
| `sat_filter_enabled`| `bool` | 是否启用饱和度过滤（用于去除彩色箭头）。 |
| `clahe_clip` | `float` | CLAHE的裁剪限制，控制对比度增强强度。 |
| `deepen_factor` | `float` | 颜色深化的系数。 |
| `blue_boost` | `float` | 蓝色通道增强系数。 |
| `gamma_value` | `float` | Gamma校正值，大于1压暗图像。 |
| `tophat_strength`| `float` | 顶帽变换结果的增强强度。 |
| `trans_sat_penalty`| `float` | （透明地图模式）饱和度惩罚系数。 |
| `sat_filter_thresh`| `int` | 饱和度过滤的阈值。 |
| `wall_weight` | `int` | （已废弃或少用）墙体特征的权重。 |
| `edge_weight` | `int` | （已废弃或少用）边缘特征的权重。 |
| `edge_low` | `int` | Canny边缘检测的低阈值。 |
| `edge_high` | `int` | Canny边缘检测的高阈值。 |

### 3. Navigation UI 参数

这些参数虽然在导航面板中设置，但逻辑上与特定地图的校准相关，因此也需要随地图一起保存。

| 参数名 | 类型 | 来源模块 | 描述 |
| :--- | :--- | :--- | :--- |
| `y_bias` | `float` | `navigation_mode` | 鼠标点击Y轴的灵敏度/比例修正。 |
| `center_offset_y`| `int` | `navigation_mode` | 角色在小地图截图中的Y轴像素偏移量。 |
