# 绘制地图(Stitching)工作流程与参数全解

本文档旨在详细梳理"绘制地图"功能的完整工作流程，并列出在此过程中涉及的所有关键参数，以确保在"导航模式"加载地图时，能够100%复现绘制时的环境配置。本文档重点强调调试和故障排查，详细说明每个环节的具体实现思路和方法。

## 一、 核心组件架构

绘制地图功能主要由以下几个核心模块协同工作：

- **`gui/improved_main_window.py`**: 主UI窗口，管理所有UI组件和用户交互，是参数配置的入口。
- **`gui/advanced_settings.py`**: 高级设置面板，用于微调图像识别的复杂参数。
- **`core/stitcher_core.py`**: 拼接核心，负责接收图像、计算位移、并将图像拼接到全局地图上。
- **`core/recognizer_optimized.py`**: 图像识别器，负责从原始截图中提取出用于匹配的"墙体"等特征。
- **`core/capture.py`**: 屏幕捕捉模块，根据指定区域从屏幕上截图。

## 二、 详细工作流程与实现思路

### 步骤 1: 参数配置 (用户操作)

#### 1.1 定义捕捉区域
- **文件位置**: `gui/improved_main_window.py`
- **实现函数**: `select_center_point()` 
  ```python
  def select_center_point(self):
      """选择中心点位置"""
  ```
- **实现思路**：创建 `CenterPointSelector` 覆盖层，全屏显示并捕获鼠标点击事件。
- **坐标转换函数**: `gui/improved_main_window.py` 中的 `_compute_scale()`
  ```python
  def _compute_scale(self):
      """计算从Qt逻辑坐标到物理像素的缩放系数"""
  ```
  转换逻辑：
  ```python
  sx, sy = self._compute_scale()  # 计算缩放系数
  px_x = int(x * sx)  # 转换为物理像素
  px_y = int(y * sy)
  ```
- **参数存储**：
  - `monitor_center`: (px_x, px_y) - 物理像素坐标
  - `monitor_size`: 截图区域边长，默认200px
- **调试要点**：检查 `monitor_center` 是否为物理像素坐标，而非逻辑坐标。

#### 1.2 配置图像识别
- **实现思路**：通过UI滑块和高级设置面板，将参数实时同步到 `HSVRecognizer` 实例。
- **参数同步机制**: `gui/improved_main_window.py` 中的 `update_*_params()` 系列函数：
  - `update_hsv_params()`:
    ```python
    def update_hsv_params(self):
        """更新HSV参数"""
    ```
  - `update_feature_params()`:
    ```python
    def update_feature_params(self):
        """更新特征参数"""
    ```
  - `update_merge_params()`:
    ```python
    def update_merge_params(self):
        """更新融合参数"""
    ```
  - 这些方法构建参数字典并调用 `recognizer.set_params()`。
- **调试要点**：确认所有UI参数都正确传递到识别器，特别是HSV范围参数。

#### 1.3 配置拼接参数
- **draw_scale**：绘制比例，默认2.0，决定地图分辨率。
- **调试要点**：确保绘图和导航时使用相同的 `draw_scale`。

### 步骤 2: 启动绘制

#### 2.1 初始化
- **实现函数**: `gui/improved_main_window.py` 中的 `__init__()` 方法：
  ```python
  def __init__(self):
      # 创建核心组件
      self.screen_capture = ScreenCapture()
      self.recognizer = HSVRecognizer()
      self.stitcher = MapStitcher(canvas_size=5000)
  ```
- **参数注入函数**: `core/recognizer_optimized.py` 中的 `set_params()`:
  ```python
  def set_params(self, params):
      """设置参数 (支持部分更新)"""
  ```
  和 `core/stitcher_core.py` 中的 `set_params()`:
  ```python
  def set_params(self, params):
      """设置参数"""
  ```
- **调试要点**：验证参数是否正确注入到实例中。

#### 2.2 启动线程
- **实现函数**: `gui/improved_main_window.py` 中的 `toggle_monitoring()`:
  ```python
  def toggle_monitoring(self):
      """切换监控状态"""
  ```
  启动 `QTimer` 执行 `capture_and_process` 循环：
  ```python
  self.capture_timer.timeout.connect(self.capture_and_process)
  ```
- **调试要点**：确保线程安全，避免UI线程和处理线程间的竞争条件。

### 步骤 3: 拼接循环 (后台自动执行)

#### 3.1 截图 (`capture`)
- **实现函数**: `gui/improved_main_window.py` 中的 `capture_and_process()`:
  ```python
  def capture_and_process(self):
      """捕获并处理（核心循环）"""
  ```
- **具体实现**：
  ```python
  center_x, center_y = self.monitor_center
  img = self.screen_capture.capture_square(center_x, center_y, self.monitor_size)
  ```
- **截图函数**: `core/capture.py` 中的 `capture_square()`:
  ```python
  def capture_square(self, center_x, center_y, size):
      """
      捕获正方形区域
      Args:
          center_x: 中心点X坐标（物理像素）
          center_y: 中心点Y坐标（物理像素）
          size: 正方形边长（物理像素）
      Returns:
          numpy array (BGR格式)
      """
  ```
- **调试要点**：确认截图区域正确，中心点坐标和尺寸参数无误。

#### 3.2 图像识别 (`recognize`)
- **实现函数**: `core/recognizer_optimized.py` 中的 `extract_combined()`:
  ```python
  def extract_combined(self, img, player_pos=None):
      """
      ⭐ 优化版：提取组合特征用于拼接
      """
  ```
  调用方式：`recognizer.extract_combined(img, player_pos=player_pos)`
- **player_pos计算**: 在中心点模式下，玩家位置为图像中心 `(self.monitor_size // 2, self.monitor_size // 2)`。
- **预处理流程**：
  1. Gamma校正 (`_preprocess_for_wall()`)：压暗背景，突出高亮墙体
  2. CLAHE (`_preprocess_for_wall()`)：增强局部对比度
  3. TopHat (`_preprocess_for_wall()`)：提取细微结构
  4. HSV过滤 (`extract_walls()`, `extract_fog()`, `extract_player()`)：提取墙体、迷雾、玩家特征
- **调试要点**：检查预处理后的图像是否正确提取了特征，特别是墙体轮廓。

#### 3.3 位移计算 (`stitch`)
- **实现函数**: `core/stitcher_core.py` 中的 `_estimate_displacement()`:
  ```python
  def _estimate_displacement(self, img1, img2):
      """核心相位相关计算"""
  ```
- **算法核心**：
  ```python
  shift, response = cv2.phaseCorrelate(img1.astype(np.float32), img2.astype(np.float32), window=hann)
  ```
- **关键帧机制**: `add_frame()` 方法中实现优先与关键帧匹配的逻辑，减少累积误差。
- **调试要点**：验证位移计算的准确性，检查是否存在异常大的位移跳跃。

#### 3.4 地图更新 (`update`)
- **实现函数**: `core/stitcher_core.py` 中的 `add_frame()`:
  ```python
  def add_frame(self, img, match_mask, save_mask, fog_mask, raw_gray=None, player_pos=None):
      """
      添加新帧 (核心逻辑)
      """
  ```
  调用 `_merge_frame_weighted()` 方法：
  ```python
  def _merge_frame_weighted(self, save_mask, fog_mask, h, w, px, py, force=False):
      """
      加权融合算法 (Weighted Merge)
      """
  ```
- **坐标转换**：将像素位移转换为全局地图坐标。
- **加权融合**：使用权重层累积置信度，防止噪点污染。
- **调试要点**：检查地图更新是否正确，权重层是否正常累积。

### 步骤 4: 保存地图与配置

#### 4.1 收集参数
- **实现函数**: `gui/improved_main_window.py` 中的 `save_map()`:
  ```python
  def save_map(self):
      """保存地图 (新版：保存为数据包 + 配置文件)"""
  ```
- **收集内容**：
  - 监控参数：`monitor_center`, `monitor_size`
  - 拼接参数：`draw_scale`, `stitcher_params` (来自 `stitcher.get_params()`)
  - 识别参数：`recognizer_params` (来自 `recognizer.get_params()`)
  - 导航参数：`nav_preferences`
- **调试要点**：确认所有参数都被正确收集，无遗漏。

#### 4.2 写入文件
- **地图数据保存函数**: `core/stitcher_core.py` 中的 `save_map_package()`:
  ```python
  def save_map_package(self, folder_path):
      """
      保存地图包 (数据 Only)
      """
  ```
  使用 `np.savez_compressed()` 保存到 `map_data.npz`。
- **配置文件保存**: `gui/improved_main_window.py` 中的 `save_map()` 函数使用 `json.dump()` 保存到 `config.json`。
- **调试要点**：验证文件是否正确写入，参数是否完整保存。

## 三、 参数全解与调试要点

### 3.1 Capture & Stitcher 参数

| 参数名 | 类型 | 来源模块 | 描述 | 调试要点 |
| :--- | :--- | :--- | :--- | :--- |
| `monitor_center` | `list[int, int]` | `improved_main_window` | 截图区域在屏幕上的中心点坐标, `[x, y]`。 | 确认为物理像素坐标，非逻辑坐标 |
| `monitor_size` | `int` | `improved_main_window` | 截图区域的边长。 | 确认尺寸与实际截图一致 |
| `draw_scale` | `float` | `stitcher_core` | 绘制地图的放大比例，决定了地图精度。 | 绘图和导航必须使用相同值 |
| `canvas_size` | `int` | `stitcher_core` | 全局画布的尺寸，决定了地图的最大范围。 | 确认画布足够大，避免边界冲突 |

### 3.2 Recognizer 参数

| 参数名 | 类型 | 描述 | 调试要点 |
| :--- | :--- | :--- | :--- |
| `wall_hsv_min/max` | `list` | 墙体识别的HSV颜色范围。 | 根据游戏地图颜色调整，确保准确识别墙体 |
| `fog_hsv_min/max` | `list` | 迷雾识别的HSV颜色范围。 | 确保迷雾区域正确识别 |
| `player_hsv_min/max` | `list` | 玩家箭头识别的HSV颜色范围。 | 避免玩家箭头干扰墙体识别 |
| `enable_wall/fog` | `bool` | 启用/禁用相应识别。 | 根据需要启用 |
| `clahe_enabled` | `bool` | 启用CLAHE增强。 | 提高对比度，有助于特征提取 |
| `gamma_enabled` | `bool` | 启用Gamma校正。 | 压暗背景，突出高亮特征 |
| `tophat_enabled` | `bool` | 启用顶帽变换。 | 提取细微结构，适用于复杂地图 |
| `sat_filter_enabled` | `bool` | 启用饱和度过滤。 | 去除彩色箭头等干扰 |
| `clahe_clip` | `float` | CLAHE裁剪限制。 | 控制对比度增强强度，过高会产生噪点 |
| `gamma_value` | `float` | Gamma校正值。 | 大于1压暗，小于1提亮 |
| `tophat_strength` | `float` | 顶帽变换强度。 | 控制提取细节的强度 |
| `trans_sat_penalty` | `float` | 透明模式饱和度惩罚。 | 控制彩色区域的抑制程度 |
| `edge_low/high` | `int` | Canny边缘检测阈值。 | 控制边缘检测的敏感度 |

### 3.3 Stitcher 参数

| 参数名 | 类型 | 来源模块 | 描述 | 调试要点 |
| :--- | :--- | :--- | :--- | :--- |
| `conf_thresh` | `float` | `stitcher_core` | F2F匹配最低置信度阈值。 | 过低导致误匹配，过高导致断连 |
| `keyframe_thresh` | `float` | `stitcher_core` | 关键帧维持阈值。 | 控制关键帧切换频率 |
| `weight_add` | `float` | `stitcher_core` | 单帧权重增量。 | 控制地图更新速度和抗噪能力 |
| `weight_cap` | `float` | `stitcher_core` | 最大权重限制。 | 防止权重无限累积 |

### 3.4 Navigation UI 参数

| 参数名 | 类型 | 来源模块 | 描述 | 调试要点 |
| :--- | :--- | :--- | :--- | :--- |
| `y_bias` | `float` | `navigation_mode` | 鼠标Y轴灵敏度修正。 | 调整鼠标映射的准确性 |
| `center_offset_y` | `int` | `navigation_mode` | 角色Y轴偏移量。 | 校准角色在小地图中的位置 |
| `k_ratio` | `float` | `navigation_mode` | 鼠标映射系数。 | 控制地图坐标到屏幕坐标的转换 |

## 四、 中心点定位模式详解与调试

### 4.1 中心点模式的工作原理

在中心点定位模式下，用户通过点击屏幕上的游戏小地图中心来定义截图区域。这种模式与传统的区域选择模式有显著区别：

- **传统区域模式**：用户选择一个矩形区域，截图时直接按该区域坐标进行。
- **中心点模式**：用户指定一个中心点 `(center_x, center_y)` 和一个尺寸 `size`，截图区域为以中心点为中心的正方形区域。

### 4.2 中心点模式的坐标计算

在中心点模式下，截图区域的计算方式如下：

```
half_size = size // 2
x = center_x - half_size
y = center_y - half_size
```

截图区域为 `(x, y, size, size)`，即以 `(center_x, center_y)` 为中心的 `size × size` 正方形。

### 4.3 常见问题：绘图与导航的坐标不一致

**问题现象**：绘图时以中心点辐射出一个正方形，但在导航加载时，将中心点作为监视窗口的左上角。

**根本原因**：绘图和导航模式对 `monitor_center` 参数的理解或使用方式不一致。

**调试方法**：
1. **绘图模式验证**：
   - 在 `capture_and_process` 方法中，确认截图区域计算为：
   ```python
   img = self.screen_capture.capture_square(center_x, center_y, self.monitor_size)
   # 实际截图区域为 (center_x - size//2, center_y - size//2, size, size)
   ```
2. **导航模式验证**：
   - 在 `navigation_loop` 方法中，确认截图区域计算为：
   ```python
   frame = self.main_window.screen_capture.capture_square(center_x, center_y, size)
   ```
3. **坐标系统一致性**：确保两个模式都使用相同的坐标计算方式。

### 4.4 关键参数在两种模式中的含义

| 参数 | 绘图模式 | 导航模式 | 一致性要求 | 调试验证方法 |
| :--- | :--- | :--- | :--- | :--- |
| `monitor_center` | 截图区域中心点 | 截图区域中心点 | 必须相同 | 打印坐标值，确认一致 |
| `monitor_size` | 截图区域边长 | 截图区域边长 | 必须相同 | 确认尺寸值一致 |
| `draw_scale` | 绘图时的放大比例 | 导航时的参考比例 | 必须相同 | 验证配置文件中值一致 |

## 五、 调试定位不准问题指南

### 5.1 常见定位不准的原因

1. **参数不一致**：绘图和导航时的参数不完全相同。
2. **图像识别问题**：墙体识别不够准确，导致特征匹配失败。
3. **坐标系统错位**：绘图和导航时的坐标系统不一致。
4. **关键帧系统不稳定**：关键帧频繁切换或匹配失败。

### 5.2 调试步骤

#### 5.2.1 检查参数一致性
- **验证方法**：
  1. 比较绘图时保存的 `config.json` 与导航时加载的配置。
  2. 使用以下代码验证关键参数：
  ```python
  # 检查监控参数
  assert config['monitor_center'] == expected_center
  assert config['monitor_size'] == expected_size
  assert config['draw_scale'] == expected_scale
  
  # 检查识别参数
  rec_params = config['recognizer_params']
  assert rec_params['wall_hsv_min'] == expected_hsv_min
  # ... 检查其他关键参数
  ```

#### 5.2.2 验证图像识别
- **验证方法**：
  1. 在绘图模式下，观察预处理后的图像是否正确提取了墙体特征。
  2. 检查HSV范围参数是否适合当前游戏地图的颜色特征。
  3. 使用调试代码输出识别结果：
  ```python
  # 在recognizer.extract_combined中添加调试输出
  print(f"Wall mask non-zero count: {cv2.countNonZero(wall_mask)}")
  print(f"Fog mask non-zero count: {cv2.countNonZero(fog_mask)}")
  ```

#### 5.2.3 验证坐标系统
- **验证方法**：
  1. 确认绘图和导航时的截图区域计算方式一致。
  2. 检查 `monitor_center` 是否始终表示截图区域的中心点。
  3. 验证坐标转换逻辑：
  ```python
  # 验证截图区域计算
  expected_x = center_x - size // 2
  expected_y = center_y - size // 2
  actual_region = (expected_x, expected_y, size, size)
  ```

#### 5.2.4 检查关键帧系统
- **验证方法**：
  1. 监控关键帧切换频率：`stats['keyframe_switches']`。
  2. 检查匹配质量：`stats['match_quality']`。
  3. 验证阈值设置：`conf_thresh`, `keyframe_thresh`。

### 5.3 参数调整建议

- **提高匹配精度**：适当提高 `conf_thresh` (0.30 → 0.40) 和 `keyframe_thresh` (0.25 → 0.30)。
- **增强抗噪能力**：适当降低 `weight_add` (0.3 → 0.2)，增加地图更新的稳定性。
- **优化图像识别**：
  - 调整HSV范围以适应当前地图
  - 启用CLAHE和Gamma校正以增强对比度
  - 使用TopHat变换提取细微结构
- **处理彩色地图**：启用 `sat_filter_enabled` 并调整 `sat_filter_thresh`。

### 5.4 故障排查清单

当遇到定位不准问题时，请按以下清单逐一排查：

- [ ] 确认绘图和导航使用相同的 `config.json` 文件
- [ ] 验证 `monitor_center` 和 `monitor_size` 参数是否一致
- [ ] 检查 `draw_scale` 是否在两个模式中相同
- [ ] 确认HSV参数是否适合当前游戏地图
- [ ] 验证截图区域是否正确（中心点模式下应为中心而非左上角）
- [ ] 检查图像识别是否正常（墙体、迷雾特征是否正确提取）
- [ ] 监控匹配质量指标是否稳定
- [ ] 检查关键帧切换是否过于频繁
- [ ] 验证坐标转换逻辑是否正确

## 六、 代码结构检查与维护

### 6.1 重复定义问题修复

**问题**：`core/recognizer_optimized.py` 中存在两个同名的 `get_params` 和 `set_params` 方法，导致部分参数未被保存。

**修复方法**：
1. 合并两个 `get_params` 方法，确保包含所有参数
2. 合并两个 `set_params` 方法，确保处理所有参数
3. 删除重复的第二个方法定义

**验证方法**：
```python
# 验证参数完整性
recognizer = HSVRecognizer()
params = recognizer.get_params()
assert 'wall_hsv_min' in params  # 确保HSV参数存在
assert 'clahe_grid' in params    # 确保高级参数存在
```

### 6.2 参数完整性验证

**问题**：`save_config` 函数只保存了部分识别器参数。

**修复方法**：修改为保存完整的 `recognizer.get_params()`。

**验证方法**：
```python
# 检查保存的参数数量
config = load_config()
saved_params = config['特征参数']
assert len(saved_params) == len(recognizer.get_params())  # 参数数量应一致
```

### 6.3 参数同步验证

**问题**：UI控件更新时，部分参数未同步到识别器。

**修复方法**：确保 `update_feature_params` 等函数将所有UI参数正确传递给识别器。

**验证方法**：
```python
# 验证参数同步
ui_value = self.clahe_check.isChecked()
recognizer_value = self.recognizer.clahe_enabled
assert ui_value == recognizer_value  # UI值应与识别器值同步
```