
# 导航模式 (Navigation Mode) 技术说明文档

本篇文档旨在详细、精确地阐述“导航模式”的所有技术实现细节，严格基于当前项目 (`minimap_stitcher copy 5`) 的源代码。内容涵盖核心组件、执行流程、数据结构以及它们之间的相互关系，旨在为开发者提供一份清晰的调试与维护指南。

---

## 1. 架构总览

导航系统是一个典型的“模型-视图-控制器”(MVC)与信号槽机制相结合的架构。其核心组件协同工作，完成从参数配置、地图加载、实时定位到最终的运动控制的完整闭环。

**组件关系图 (文字表示):**

```mermaid
graph TD
    subgraph GUI Layer
        A[NavigationModeWidget] -- 拥有并控制 --> B[NavParametersDialog];
        A -- 拥有 --> G[QGraphicsView/Scene];
    end

    subgraph Data Layer
        C[NavConfig] -- 作为数据载体 --> A;
        C -- 作为数据载体 --> B;
    end

    subgraph Core Logic Layer
        D[NavigationCore] -- 拥有 --> E[HSVRecognizer];
        F[MotionController] -- 拥有 --> H[InputDriver];
    end

    %% 交互关系
    A -- "调用 `localize()`" --> D;
    A -- "调用 `update()`" --> F;
    B -- "`parameters_changed(NavConfig)` 信号" --> A;
    A -- "调用 `set_params()`" --> E;
    A -- "调用 `_apply_config_to_core()`" --> D;
    A -- "加载 `config.json`" --> C;
    C -- "填充UI" --> B;

```

-   **`NavigationModeWidget` (指挥官):** 位于 `gui/navigation_mode.py`，是整个导航功能的UI和逻辑中枢。它聚合了所有其他组件，响应用户操作，并驱动核心逻辑。
-   **`NavParametersDialog` (参数面板UI):** 位于 `gui/widgets/params_dialog.py`，是一个独立的对话框，负责展示和修改所有导航相关的算法参数。它通过Qt的信号槽机制与主窗口 `NavigationModeWidget` 解耦。
-   **`NavConfig` (数据模型):** 位于 `gui/navigation_params.py`，使用 `dataclass` 定义了一个强类型的配置树，作为系统内部数据交换的标准格式，并负责与 `config.json` 的序列化和反序列化。
-   **`NavigationCore` (导航核心):** 位于 `core/navigation_core.py`，负责地图数据的加载、管理，以及最核心的定位算法（`localize`）。它通过模板匹配和帧间跟踪（相位相关）来实现玩家在全局地图上的定位。
-   **`HSVRecognizer` (图像识别器):** 位于 `core/recognizer_optimized.py`，是定位算法的“眼睛”。它接收实时的小地图截图，通过一系列复杂的图像处理（HSV颜色过滤、CLAHE、Gamma校正、Top-hat变换等）提取出用于匹配的特征（如墙体、边缘）。
-   **`MotionController` (运动控制器):** 位于 `core/motion_controller.py`，负责将导航指令转换为具体的鼠标点击操作。它根据当前位置和目标位置计算移动向量，并调用底层驱动来模拟用户输入。

---

## 2. 核心组件详解

### 2.1 `NavigationModeWidget`

-   **文件路径:** `gui/navigation_mode.py`
-   **职责:** 作为导航模式的“大脑”，聚合UI和核心逻辑，调度所有任务。

#### 主要属性

-   `nav_core: NavigationCore`：导航核心逻辑的实例。
-   `motion_controller: MotionController`：运动控制器的实例。
-   `nav_config: NavConfig`：当前生效的导航配置对象。
-   `params_dialog: NavParametersDialog`：参数面板UI的实例。
-   `scene: QGraphicsScene` / `view: QGraphicsView`：用于显示地图和相关元素的图形视图。
-   `nav_timer: QTimer`：驱动 `navigation_loop` 方法高频执行的核心定时器。

#### 关键方法

-   **`__init__(self, main_window)`**
    -   **签名:** `def __init__(self, main_window)`
    -   **功能:** 初始化UI (`init_ui`)、实例化所有核心组件 (`NavigationCore`, `MotionController` 等)，并连接信号槽 (`_connect_signals`)。

-   **`load_map(self)`**
    -   **签名:** `def load_map(self)`
    -   **功能:** 加载用户在下拉列表中选择的地图。
    -   **执行流程:**
        1.  从UI的 `map_combo` 获取选择的地图名称。
        2.  构建地图数据文件夹的完整路径。
        3.  查找并加载该文件夹下的 `config.json` 文件。
        4.  使用 `NavConfig.from_dict()` 将 `json` 内容反序列化为 `self.nav_config` 对象。
        5.  实例化 `NavigationCore(map_folder_path)`，这会立即加载地图数据 (`map_data.npz`)。
        6.  调用 `_apply_config_to_core()` 将加载的配置应用到 `nav_core` 和 `motion_controller`。
        7.  调用 `self.params_dialog.set_config_to_ui(self.nav_config)`，用配置数据填充参数面板的UI。
        8.  调用 `_render_map()` 在 `QGraphicsView` 中渲染地图图像。
        9.  启用“开始导航”和“设置初始位置”按钮。

-   **`_apply_config_to_core(self)`**
    -   **签名:** `def _apply_config_to_core(self)`
    -   **功能:** 将 `self.nav_config` 对象中的参数应用到各个核心逻辑模块。
    -   **实现细节:**
        ```python
        # 将 RecognizerParams 对象转换为字典
        rec_params_dict = self.nav_config.recognizer_params.__dict__
        # 传递给识别器
        self.nav_core.recognizer.set_params(rec_params_dict)

        # 设置其他核心参数
        self.nav_core.draw_scale = self.nav_config.draw_scale
        self.nav_core.set_center_offset(self.nav_config.nav_preferences.center_offset_y)

        # 更新运动控制器参数
        prefs = self.nav_config.nav_preferences
        self.motion_controller.set_screen_params(
            center[0], center[1], self.nav_config.monitor_size, 
            prefs.y_bias, prefs.center_offset_y
        )
        ```

-   **`_on_parameter_changed(self, new_config: NavConfig)`**
    -   **签名:** `def _on_parameter_changed(self, new_config: NavConfig)`
    -   **功能:** 这是响应 `params_dialog` 的 `parameters_changed` 信号的槽函数。
    -   **实现:**
        1.  接收从UI面板传来的新的 `NavConfig` 对象，并更新自身的 `self.nav_config`。
        2.  立即调用 `_apply_config_to_core()`，将新的参数实时应用到后端核心。
        3.  更新参数面板的状态标签为“有未保存的修改”。

-   **`_save_nav_config(self)`**
    -   **签名:** `def _save_nav_config(self)`
    -   **功能:** 响应 `params_dialog` 的 `save_requested` 信号，保存当前配置。
    -   **实现:**
        1.  调用 `self.nav_config.to_dict()` 将配置对象序列化为字典。
        2.  使用 `json.dump()` 将字典写入当前地图文件夹下的 `config.json` 文件。

-   **`navigation_loop(self)`**
    -   **签名:** `def navigation_loop(self)`
    -   **功能:** 系统的“心跳”，由 `QTimer` 以10Hz的频率触发。
    -   **执行流程:**
        1.  从主窗口获取监控区域的中心点和大小。
        2.  调用 `screen_capture.capture_square()` 截取实时的小地图图像。
        3.  将截图 `frame` 传递给 `self.nav_core.localize(frame)` 进行定位。
        4.  `localize` 方法返回全局坐标 `(global_x, global_y)` 和置信度 `conf`。
        5.  如果定位成功 (`global_x` is not None):
            a.  计算在UI上显示的坐标（减去地图裁剪的偏移量 `crop_offset`）。
            b.  更新UI上的玩家图标 `self.player_item` 的位置。
            c.  将全局坐标传递给 `self.motion_controller.update((global_x, global_y))` 以执行移动。
            d.  更新状态栏的文本。
            e.  调用 `self.view.centerOn(...)` 使地图视图始终以玩家为中心。
        6.  如果定位失败，状态栏显示“定位丢失...”。

### 2.2 `NavParametersDialog`

-   **文件路径:** `gui/widgets/params_dialog.py`
-   **职责:** 提供一个与主逻辑解耦的UI界面，用于展示和编辑所有导航算法的参数。

#### 通信机制

-   **发出信号:**
    -   `parameters_changed = Signal(NavConfig)`: 当UI上任何一个参数控件的值发生变化时，此信号被触发，并携带一个根据当前UI状态新创建的 `NavConfig` 对象。
    -   `save_requested = Signal()`: 当用户点击“保存”按钮时触发。
-   **接收数据 (公共方法):**
    -   `set_config_to_ui(self, config: NavConfig)`: 这是一个公共方法，由外部调用（`NavigationModeWidget`），用于接收一个 `NavConfig` 对象并用其内容填充整个UI界面。

#### 关键方法

-   **`_on_ui_changed(self)`**
    -   **功能:** 几乎所有UI控件的 `valueChanged` 或 `stateChanged` 信号都连接到此槽。
    -   **实现:**
        1.  调用 `get_config_from_ui()` 从所有UI控件收集当前值，并组装成一个新的 `NavConfig` 对象。
        2.  发出 `parameters_changed` 信号，并将这个新的 `NavConfig` 对象作为参数传递出去。

-   **`get_config_from_ui(self) -> NavConfig`**
    -   **功能:** 遍历UI上所有的 `QSpinBox`, `QCheckBox`, `QLineEdit` 等控件，读取它们当前的值。
    -   **实现:** 将读取到的值填充到 `NavPreferences` 和 `RecognizerParams` 的新实例中，最后将它们组装成一个 `NavConfig` 对象并返回。`_parse_hsv_list` 辅助函数用于安全地将字符串 `"[0, 0, 0]"` 解析为列表。

### 2.3 `NavConfig` (及子类)

-   **文件路径:** `gui/navigation_params.py`
-   **职责:** 定义导航系统所有配置参数的“形状”和默认值，并提供序列化和反序列化的能力。

#### 数据结构

-   **`NavConfig`**: 顶层容器。
    -   `nav_preferences: NavPreferences`
    -   `recognizer_params: RecognizerParams`
    -   以及其他基本参数如 `draw_scale`。
-   **`NavPreferences`**: 包含与导航控制和坐标映射相关的参数，如 `k_ratio`, `y_bias`。
-   **`RecognizerParams`**: 包含所有与图像识别算法相关的参数，是数量最多、最复杂的部分。

#### 关键方法

-   **`from_dict(cls, data: dict)`**: 类方法，接收从 `config.json` 加载的字典，并安全地构造一个 `NavConfig` 实例。它能处理字典中缺少某些键的情况，并使用 `dataclass` 中定义的默认值。
-   **`to_dict(self)`**: 实例方法，将当前的配置对象转换回一个可以被 `json.dump` 理解的字典，用于保存。

### 2.4 `NavigationCore`

-   **文件路径:** `core/navigation_core.py`
-   **职责:** 执行核心的定位任务。

#### 关键方法

-   **`localize(self, minimap_img)`**: 这是该类最核心的方法。
    -   **签名:** `def localize(self, minimap_img)`
    -   **功能:** 根据输入的小地图截图，计算出玩家在全局地图中的精确坐标。
    -   **执行流程 (策略分支):**
        1.  **预处理:** 调用 `self.recognizer.extract_combined(minimap_img)` 提取特征掩码 (`match_mask` 和 `wall_mask`)。
        2.  **帧间跟踪 (优先):** 如果系统已处于定位状态 (`self.is_localized`) 并且拥有上一帧的特征 (`self.prev_mask`)，则优先使用 **相位相关** (`_estimate_displacement`) 计算当前帧与上一帧之间的位移 `shift`。
            -   **优点:** 速度极快，计算成本低。
            -   **实现:** `self.current_pos -= shift * self.draw_scale`。位移需要乘以 `draw_scale` 从截图坐标系转换到全局地图坐标系。
        3.  **模板匹配 (校准/初始化):** 如果帧间跟踪失败，或系统尚未定位，则执行模板匹配。
            -   **搜索区域:** 如果已有一个大致位置 (`self.is_localized`)，则在全局地图 `self.wall_layer` 上以该位置为中心，裁剪出一个**局部搜索区域** (`search_area`)，以提高效率。否则，在整个 `self.wall_layer` 上进行**全局搜索**。
            -   **模板:** 使用从当前截图提取的 `wall_mask`，并将其 `cv2.resize` 到 `draw_scale` (2x) 以匹配 `wall_layer` 的尺寸。
            -   **匹配:** 调用 `cv2.matchTemplate(search_area, wall_mask_scaled, cv2.TM_CCOEFF_NORMED)`。
            -   **结果解析:** 如果匹配的最高置信度 `max_val` 超过阈值 (`0.6`)，则认为定位成功。根据返回的最佳匹配位置 `max_loc` 和搜索区域的偏移 `top_left_offset` 计算出最终的全局坐标。
            -   **状态更新:** 定位成功后，设置 `self.is_localized = True`，并保存当前帧的 `match_mask` 到 `self.prev_mask`，为下一次帧间跟踪做准备。

### 2.5 `HSVRecognizer`

-   **文件路径:** `core/recognizer_optimized.py`
-   **职责:** 作为计算机视觉的核心，将原始的彩色图像转换为用于匹配的二值化特征图。

#### 关键方法

-   **`set_params(self, params)`**: 接收一个字典，并用其中的值更新识别器的所有内部参数。这是UI层与核心算法层之间的桥梁。
-   **`extract_combined(self, img, player_pos=None)`**: 提取用于定位的组合特征。
    -   **返回:** `(match_mask, wall_mask, fog_mask)` 元组。
    -   **`wall_mask`:** 纯粹的墙体二值图，用于与全局地图进行模板匹配。
    -   **`match_mask`:** 融合了墙体和Canny边缘检测的结果 (`cv2.addWeighted`)，包含更多细节，用于高精度的帧间跟踪。
-   **`_preprocess_for_wall(self, img)`**: 墙体提取的专用预处理流程，非常激进，旨在最大化对比度，只保留高亮线条。
    -   **流程:** Gamma压暗 -> 高斯模糊 -> CLAHE -> Top-Hat -> 截断与拉伸 -> 颜色深化。
-   **`_compute_transparency_score(self, img)`**: “透明地图模式”下的核心算法。
    -   **目的:** 专门处理那种背景高亮、线条灰白的“透明”小地图。
    -   **核心思想:**
        1.  **颜色分数:** `V - S * penalty`。利用“墙体是高亮度(V)低饱和度(S)”的特点，计算一个基础分数。
        2.  **结构分数:** 使用 `cv2.MORPH_TOPHAT` (顶帽变换) 提取图像中的高亮线性结构，有效抑制大面积的白色背景块。
        3.  **融合:** `cv2.min(score_color, tophat_boosted)`。最终的分数必须同时满足“颜色像墙”和“结构像线”两个条件，从而精确地提取出墙体。

### 2.6 `MotionController`

-   **文件路径:** `core/motion_controller.py`
-   **职责:** 将抽象的导航指令（从A点到B点）转换为具体的、模拟真人的鼠标点击。

#### 关键方法

-   **`update(self, current_pos)`**: 由 `navigation_loop` 调用，在每次成功定位后执行。
    -   **功能:** 计算从 `current_pos` 到 `self.target_pos` 的移动向量。
    -   **实现:**
        1.  计算当前位置与目标的距离 `distance`。
        2.  如果 `distance` 小于 `arrival_threshold`，则停止移动。
        3.  如果需要移动，且 `self.control_enabled` 为 `True`，则调用 `_perform_click_move()`。
-   **`_perform_click_move(self, dx, dy, global_dist)`**
    -   **功能:** 计算出屏幕上的精确点击位置并执行点击。
    -   **坐标转换逻辑:**
        1.  **全局距离 -> 屏幕距离:** `screen_dist = (global_dist / self.draw_scale) * self.k_ratio`。
        2.  **计算点击坐标:**
            -   从屏幕中心 `self.screen_center` 开始。
            -   考虑角色Y轴偏移 `self.center_offset_y`。
            -   将方向向量 `(dx, dy)` 乘以 `screen_dist` 和 `y_bias` (纵向补偿)，得到屏幕上的位移向量。
            -   最终点击坐标 = `有效中心点` + `位移向量`。
        3.  **执行:** 调用 `self.driver.click(click_x, click_y)`。

---

## 3. 关键执行流程

### 流程1: 参数从UI到核心的传递

1.  **用户操作:** 用户在 `NavParametersDialog` 上拖动一个滑块（例如 `clahe_clip_spin`）。
2.  **信号触发:** `valueChanged` 信号触发，调用 `_on_ui_changed` 槽函数。
3.  **数据收集:** `_on_ui_changed` 调用 `get_config_from_ui()`，从所有UI控件读取当前值，创建一个全新的 `NavConfig` 对象。
4.  **信号发射:** `NavParametersDialog` 发射 `parameters_changed(new_config)` 信号。
5.  **主窗口接收:** `NavigationModeWidget` 中的槽函数 `_on_parameter_changed` 被调用，接收到 `new_config`。
6.  **应用配置:** `_on_parameter_changed` 将 `self.nav_config` 更新为 `new_config`，并立即调用 `_apply_config_to_core()`。
7.  **核心更新:** `_apply_config_to_core` 将新参数逐一设置到 `NavigationCore` 和 `HSVRecognizer` 中。例如，调用 `self.nav_core.recognizer.set_params(...)`。
8.  **实时生效:** 在下一次 `navigation_loop` 执行时，`localize` 方法就会使用刚刚更新的参数进行图像处理。

### 流程2: 点击地图移动 (Click-to-Move)

1.  **用户操作:** 用户在 `NavigationModeWidget` 的 `QGraphicsView` 上点击一个点。
2.  **事件过滤:** `eventFilter` 捕获到 `QGraphicsSceneMousePress` 事件，调用 `handle_map_click(scene_pos)`。
3.  **坐标转换 (UI -> 全局):**
    -   `scene_pos` 是在**裁剪后**的地图UI上的坐标。
    -   `target_x = scene_pos.x() + self.nav_core.crop_offset[0]`。通过加上地图自动裁剪时记录的偏移量，将UI坐标转换为全局地图坐标。
4.  **逻辑分支 (非Hint模式):**
    -   检查系统是否已定位 (`self.nav_core.is_localized`)。
    -   **计算屏幕位移:**
        -   `dx_global = target_x - self.nav_core.current_pos[0]` (计算全局坐标系下的位移)。
        -   `dx_screen = (dx_global / self.nav_core.draw_scale) * prefs.k_ratio` (将全局位移转换到屏幕坐标系下的位移)。
    -   **计算目标点击点:** `target_screen_x = screen_center_x + dx_screen`。
    -   **执行移动:** 调用 `self.motion_controller.driver.move_to(target_screen_x, target_screen_y)` 直接移动到计算出的屏幕坐标。

**注意:** 当前的“点击移动”实现是**直接映射**，而非设置一个持续导航的目标点。它计算出从当前角色位置到地图点击位置所需的屏幕位移，然后直接模拟一次鼠标移动。它**不**会调用 `motion_controller.set_target()` 来启动持续的自动寻路。
