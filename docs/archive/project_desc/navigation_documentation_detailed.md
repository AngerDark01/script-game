
# 导航模式深度技术剖析 (v3 - 终版)

本文档是对导航系统所有技术细节的最终、最详尽的剖析，严格遵循 `minimap_stitcher copy 5` 的当前代码实现。它包含了对“幕布”系统的深度分析、对定位算法准确性保障机制的微观审视，以及对坐标系转换的精密图解，旨在成为一份能指导深度调试和二次开发的权威指南。

---

## 1. 架构与数据流

导航系统是典型的分层架构，各层之间通过清晰定义的接口和数据对象进行通信。

-   **UI层 (`gui/`):** `NavigationModeWidget`, `NavParametersDialog`, `OverlayWindow`, `TransparentOverlay` 等，负责用户交互和状态展示。
-   **数据层 (`gui/navigation_params.py`):** `NavConfig` 数据类，是系统状态和配置的“单一事实来源”。
-   **核心逻辑层 (`core/`):** `NavigationCore`, `HSVRecognizer`, `MotionController`，负责执行计算密集型的定位、识别和控制任务。

**数据传递核心原则:** 数据总是单向流动。配置由 `config.json` 加载到 `NavConfig`，再由 `NavConfig` 分发到UI层进行显示和核心逻辑层进行应用。用户的修改通过UI层收集，生成新的 `NavConfig` 对象，再反向应用到核心逻辑层并可选择性地保存回 `config.json`。

---

## 2. 专题深潜：地图加载与参数传递的生命周期

用户点击“加载地图”按钮后，系统执行了一系列精密且环环相扣的操作，确保地图、配置、核心模块和UI四者正确同步。

### 2.1 `load_map()` 执行流详解

**入口:** `NavigationModeWidget.load_map()`

1.  **路径构建:** 确定所选地图的专属文件夹路径，后续所有文件操作都基于此路径。
2.  **配置加载与反序列化 (关键步骤):**
    -   代码: 
        ```python
        with open(config_path, 'r', ...) as f:
            config_dict = json.load(f)
            self.nav_config = NavConfig.from_dict(config_dict)
        ```
    -   **健壮性设计:** `NavConfig.from_dict()` 是一个**防御性**工厂方法。它使用 `data.get("key", {})` 安全地获取子字典。如果 `config.json` 中缺少某个部分（如 `recognizer_params`），它会得到一个空字典 `{}`。随后，`dataclass` 的构造函数 `RecognizerParams(**{})` 会使用在类定义中声明的所有字段的**默认值**来创建实例。这确保了即使配置文件不完整或过时，`self.nav_config` 也总是一个结构完整的对象，有效避免了 `KeyError`。
3.  **核心模块初始化:**
    -   `self.nav_core = NavigationCore(map_folder_path)`: 实例化导航核心。其 `__init__` 方法会立即加载 `map_data.npz` 文件（包含定位“底图” `wall_layer`）并实例化 `HSVRecognizer`。
4.  **参数首次应用:** `_apply_config_to_core()` 被调用，将 `self.nav_config` 中的参数**首次注入**到 `nav_core` 和 `motion_controller` 中。
5.  **UI同步:** `self.params_dialog.set_config_to_ui(self.nav_config)` 被调用，用配置数据填充参数面板的UI，确保UI显示的就是当前生效的配置。

---

## 3. 专题深潜：“幕布”系统 (Overlay) 的混乱与解析

您观察到的“幕布展示不全”问题，其根源在于系统中存在**两个设计目的不同、实现各异的“幕布”类**，并且在导航模式下发生了**错误的调用**。

### 3.1 两个“幕布”类的身份识别

1.  **`TransparentOverlay` (画框选择器)**
    -   **文件:** `gui/overlay.py`
    -   **设计目的:** 为“绘图模式”提供一个**交互式**的全屏覆盖层，让用户可以通过鼠标**拖拽**来画出一个矩形框，用于选择截图区域。
    -   **核心特性:**
        -   `WA_TransparentForMouseEvents, False`: **不**允许鼠标穿透，它需要捕获鼠标事件来进行画框。
        -   `paintEvent`: 逻辑复杂。绘制半透明背景，然后通过 `CompositionMode_Clear` 将选中的矩形区域“挖空”，使其变透明，以显示下方的游戏画面。它还负责绘制提示文字和矩形尺寸。

2.  **`OverlayWindow` (状态显示器)**
    -   **文件:** `gui/overlay_window.py`
    -   **设计目的:** 提供一个**非交互式**的、纯粹用于**状态展示**的覆盖层。它的任务只是在屏幕指定位置显示一个简单的绿色矩形框和十字准星。
    -   **核心特性:**
        -   `WindowTransparentForInput`: **允许**鼠标穿透。这是一个纯粹的“显示器”，不应干扰用户对下方窗口的操作。
        -   `paintEvent`: 逻辑简单。直接在透明画布上根据 `self.center_pos` 和 `self.viewport_size` 绘制一个矩形和十字准星。

### 3.2 问题的根源：错误的调用链

1.  **`NavigationModeWidget` 的意图:** 导航模式需要一个**非交互式**的幕布来显示当前的截图区域。因此，它正确地实例化了 `OverlayWindow`:
    ```python
    # gui/navigation_mode.py
    self.overlay = OverlayWindow()
    ```

2.  **`ImprovedMainWindow` 的误解:** 主窗口 `ImprovedMainWindow` 拥有一个用于“画框选择”的 `TransparentOverlay` 实例:
    ```python
    # gui/improved_main_window.py
    self.overlay = TransparentOverlay()
    ```

3.  **致命的调用:** 当导航模式更新幕布时，它调用了主窗口的方法 `self.main_window.update_overlay_for_nav()`。而这个方法的实现是：
    ```python
    # gui/improved_main_window.py
    def update_overlay_for_nav(self, center_x, center_y, size):
        # 这里的 self.overlay 是 TransparentOverlay 的实例！
        self.overlay.setGeometry(x, y, size, size) # 错误地尝试移动和缩放一个为全屏设计的窗口
        self.overlay.start_point = QPoint(x, y)   # 错误地手动设置其内部绘制状态
        self.overlay.end_point = QPoint(x + size, y + size)
        self.overlay.update() 
    ```

**结论:** 导航模式的更新逻辑，本应作用于 `NavigationModeWidget` 自己的 `OverlayWindow` 实例，但却错误地调用到了主窗口，并以一种不兼容的方式操作了主窗口的 `TransparentOverlay` 实例。这导致了您观察到的各种显示异常和功能错乱。

---

## 4. 专题深潜：坐标系转换的精密图解

系统内存在四个核心坐标系，其转换关系是所有几何计算的基础。

-   **全局坐标系 (Global):** `map_data.npz` 中 `wall_layer` 数组的索引。绝对基准。
-   **截图坐标系 (Minimap):** 实时截取的小地图图像内的像素坐标。
-   **屏幕坐标系 (Screen):** 整个显示器的像素坐标。
-   **UI视图坐标系 (View):** `QGraphicsView` 中显示的、经过裁剪的地图上的坐标。

### 4.1 核心转换公式与推导

**推导前提:**
-   `draw_scale` (e.g., 2.0): 建图时，截图(1x)被放大到这个比例后绘制到全局地图(2x)上。
-   `k_ratio` (e.g., 10.0): 经验系数，定义了“截图中的1像素位移”对应“屏幕上多少像素的鼠标移动”。
-   `crop_offset`: `(ox, oy)`，UI视图相对于全局地图左上角的偏移。

**1. UI视图 -> 全局 (地图点击)**
`Global = View + crop_offset`
```python
# handle_map_click()
target_x = pos.x() + self.nav_core.crop_offset[0]
```

**2. 全局 -> UI视图 (显示玩家)**
`View = Global - crop_offset`
```python
# navigation_loop()
display_x = global_x - self.nav_core.crop_offset[0]
```

**3. 全局位移 -> 屏幕位移 (核心换算)**
这是一个两步过程：`Global -> Minimap -> Screen`

-   **Step 1: Global -> Minimap**
    `Minimap_Displacement = Global_Displacement / draw_scale`

-   **Step 2: Minimap -> Screen**
    `Screen_Displacement = Minimap_Displacement * k_ratio`

-   **合并公式:** `Screen_Displacement = (Global_Displacement / draw_scale) * k_ratio`

-   **代码实现 (`handle_map_click`):**
    ```python
    dx_global = target_x - self.nav_core.current_pos[0]
    # 核心公式应用，同时加入了纵向补偿 y_bias
    dx_screen = (dx_global / self.nav_core.draw_scale) * prefs.k_ratio
    dy_screen = (dy_global / self.nav_core.draw_scale) * prefs.k_ratio * prefs.y_bias
    ```

---

## 5. 专题深潜：定位准确性的保障机制

系统的定位并非依赖单一算法，而是一套结合了多种图像处理技术和策略的组合拳。

### 5.1 核心算法：双策略定位 `NavigationCore.localize()`

`localize` 方法智能地在两种模式间切换：

-   **模式一：帧间跟踪 (Phase Correlation)** - **为速度和流畅**
    -   **触发时机:** `is_localized` 为 `True` 且 `prev_mask` 存在。
    -   **算法原理:** `cv2.phaseCorrelate` 通过计算两图频谱的互功率谱，快速找到平移关系，对光照变化不敏感，计算成本极低。

-   **模式二：模板匹配 (Template Matching)** - **为准确和纠错**
    -   **触发时机:** 初始化时，或帧间跟踪失败时。
    -   **失败回退机制:** `localize` 方法中包含一个关键的纠错逻辑。如果在**局部搜索**中匹配失败（置信度低于 `0.6`），代码会执行：
        ```python
        # NavigationCore.localize():L262
        print(f"Local search failed... Switching to global search next time.")
        self.is_localized = False 
        self.prev_mask = None # 丢失跟踪
        ```
        将 `is_localized` 设为 `False` 会导致下一次调用 `localize` 时，系统**自动放弃局部搜索，转而在整个 `wall_layer` 上进行全局搜索**，直到重新找到玩家位置。这是系统定位鲁棒性的关键保障。

### 5.2 特征提取的艺术：`HSVRecognizer` 的图像炼金术

-   **王牌算法：`_compute_transparency_score()`**
    -   **问题:** 解决《暗黑破坏神》等游戏中，背景高亮、线条灰白的“透明地图”的识别难题。
    -   **两步验证法:**
        1.  **颜色验证:** `score = V - S * penalty`。利用“墙体是高亮度(V)低饱和度(S)”的特点，初步筛掉彩色背景。
        2.  **结构验证:** `cv2.morphologyEx(..., cv2.MORPH_TOPHAT, ...)`。顶帽变换是形态学中的一个关键操作，它的物理意义是 **“从原图中减去其开运算（先腐蚀后膨胀）的结果”**。这使得它能精确提取出图中所有**比其邻域更亮的、细小的物体**，同时完美地抑制大面积的明亮背景。这正是区分“细线状的墙”和“大片状的透光背景”的数学武器。
        3.  **精髓融合:** `cv2.min(score_color, tophat_boosted)`。通过取两者的最小值，代码强制要求一个像素**必须同时满足“颜色像墙”和“结构像线”** 两个条件，从而实现极高的准确性。

-   **噪声抑制：玩家箭头过滤**
    -   **问题:** 玩家在小地图上的箭头是高亮特征，会干扰定位和地图绘制。
    -   **双重保险:**
        1.  **饱和度过滤:** 在 `extract_combined` 中，`sat_filter_enabled` 逻辑检查原始图像的饱和度 `s_raw`。由于墙体是灰度，饱和度极低，而玩家箭头是彩色的，饱和度很高。`color_mask = (s_raw > self.sat_filter_thresh)` 可以精准地识别出玩家箭头并将其从 `wall_mask` 中剔除。
        2.  **中心区域遮罩:** `cv2.circle(..., radius, 0, -1)`。在特征提取的最后，代码强制在 `match_mask` 和 `wall_mask` 的中心区域（假定玩家总在截图中心）画一个黑色的实心圆，作为最后的保险，确保玩家箭头及其附近的特效被彻底抹除。

这份文档现在包含了对您所关心问题的深度解答，以及对代码实现细节更精确的描述。希望能为您提供实质性的帮助。
