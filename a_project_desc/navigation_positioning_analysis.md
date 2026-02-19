# 导航模式定位问题分析报告

**分析日期**: 2026 年 2 月 17 日  
**分析目标**: 排查导航模式加载后定位不准确的问题，特别是中心定位和监视范围显示问题

---

## 一、核心问题概述

用户报告的核心问题：
1. **导航模式加载后定位不准确**，存在偏移
2. **中心定位未显示**：加载地图时应在目标位置显示中心点
3. **监视范围幕布未显示**：应显示监视范围的绿色幕布
4. **导航模式与绘图模式环境不一致**，导致定位偏移

---

## 二、架构设计分析

### 2.1 设计要求

```
绘图模式 → 保存所有参数、状态、环境变量、中间变量
           ↓ (保存到 config.json 和 map_data.npz)
导航模式 → 独立加载 config.json，复刻绘图模式环境
           ↓
         实现与绘图模式完全一致的定位环境
```

### 2.2 数据流分析

#### 绘图模式保存的数据 (`config.json`):
```json
{
    "monitor_mode": "center",
    "monitor_center": [244, 148],      // 截图中心点（物理像素）
    "monitor_size": 200,                // 截图大小
    "monitor_region": null,             // 拉框模式区域（中心模式下为 null）
    "canvas_size": 5000,                // 画布大小
    "draw_scale": 2.0,                  // 绘图缩放比例
    "stitcher_params": {...},           // 拼接器参数
    "recognizer_params": {...},         // 识别器参数
    "nav_preferences": {...}            // 导航偏好
}
```

#### 导航模式加载的数据:
- `NavigationCore` 加载 `map_data.npz`（包含 wall_layer, explored_map, current_pos 等）
- `NavigationModeWidget` 加载 `config.json`（包含监控中心、大小、识别参数等）

---

## 三、关键问题点分析

### 3.1 问题 1：中心定位未显示

**现象**: 加载地图后，没有在目标位置显示中心点标记

**代码分析**:

在 `navigation_mode.py` 的 `load_map()` 方法中：
```python
def load_map(self):
    # ... 加载 config.json ...
    self.nav_core = NavigationCore(self.map_folder_path)
    self._apply_config_to_core()
    self.params_dialog.set_config_to_ui(self.nav_config)
    self._render_map()  # 渲染地图
```

在 `_render_map()` 方法中：
```python
def _render_map(self):
    map_img = self.nav_core.get_map_image()
    # ... 创建地图显示 ...
    
    self.player_item = self.scene.addEllipse(-5, -5, 10, 10, QPen(Qt.red), QBrush(Qt.red))
    self.player_item.setZValue(2); self.player_item.setVisible(False)  # 默认隐藏
    
    # ...
    
    if self.nav_core.last_pos:
        self.player_item.setPos(*self.nav_core.last_pos)
        self.player_item.setVisible(True)  # 只有在有 last_pos 时才显示
```

**问题根源**:
1. `player_item`（红色中心点标记）默认设置为 `setVisible(False)`
2. 只有在 `nav_core.last_pos` 存在时才显示
3. 但 `last_pos` 是从 `map_data.npz` 加载的，可能不是用户想要的初始位置
4. **没有主动在 `monitor_center` 位置显示中心点标记**

**设计要求**: 加载时应显示：
- 中心点标记（红色）在 `monitor_center` 位置
- 监视范围幕布（绿色方框）

### 3.2 问题 2：监视范围幕布未显示

**现象**: 加载地图后，没有显示监视范围的绿色幕布

**代码分析**:

在 `navigation_mode.py` 的 `toggle_navigation()` 方法中：
```python
def toggle_navigation(self):
    if self.btn_start.isChecked():
        # 检查配置
        if not self.nav_config or not self.nav_config.monitor_center or not self.nav_config.monitor_size:
            QMessageBox.warning(self, "警告", "地图配置不完整，缺少监控中心或大小！")
            self.btn_start.setChecked(False)
            return

        # 应用参数并显示幕布
        self._apply_config_to_core()
        center = self.nav_config.monitor_center
        size = self.nav_config.monitor_size
        self.overlay.set_geometry_and_show(center[0], center[1], size)  # ← 这里才显示幕布
```

**问题根源**:
1. 幕布只在点击"开始导航"按钮时才显示
2. **加载地图时没有显示幕布**
3. 用户无法在加载地图后立即看到监视范围

### 3.3 问题 3：定位偏移问题

**现象**: 导航模式定位与绘图模式存在偏移

**代码分析**:

#### 3.3.1 绘图模式的坐标系统

在 `main_window.py` 的 `capture_and_process()` 中：
```python
def capture_and_process(self):
    if self.monitor_center:
        # 使用中心点模式
        center_x, center_y = self.monitor_center
        img = self.screen_capture.capture_square(center_x, center_y, self.monitor_size)
        
        # 在中心点模式下，玩家位置就是图像中心
        player_pos = (self.monitor_size // 2, self.monitor_size // 2)
```

#### 3.3.2 导航模式的坐标系统

在 `navigation_mode.py` 的 `navigation_loop()` 中：
```python
def navigation_loop(self):
    if not self.nav_config or not self.nav_config.monitor_center: return

    center_x, center_y = self.nav_config.monitor_center
    size = self.nav_config.monitor_size
    frame = self.main_window.screen_capture.capture_square(center_x, center_y, size)
```

#### 3.3.3 关键差异分析

**发现的关键差异**:

| 项目 | 绘图模式 | 导航模式 | 是否一致 |
|------|---------|---------|---------|
| 截图中心 | `self.monitor_center` | `self.nav_config.monitor_center` | ✓ 一致 |
| 截图大小 | `self.monitor_size` | `self.nav_config.monitor_size` | ✓ 一致 |
| 截图方法 | `capture_square()` | `capture_square()` | ✓ 一致 |
| 识别器参数 | `self.recognizer` | `self.nav_core.recognizer` | ⚠️ 需检查 |
| 玩家位置 | `(size//2, size//2)` | 未显式设置 | ⚠️ **不一致** |

**潜在问题点**:

1. **识别器参数同步**:
   - 绘图模式使用 `self.recognizer`（在 `main_window.py` 中初始化）
   - 导航模式使用 `self.nav_core.recognizer`（在 `NavigationCore` 中初始化）
   - 虽然 `_apply_config_to_core()` 会同步参数，但需要确认是否完全同步

2. **玩家位置处理**:
   - 绘图模式显式设置 `player_pos = (self.monitor_size // 2, self.monitor_size // 2)`
   - 导航模式在 `navigation_loop()` 中没有设置 `player_pos`
   - `NavigationCore.localize()` 方法内部使用 `self.center_offset_y` 进行偏移校正

3. **中心偏移量 (center_offset_y)**:
   - 在 `config.json` 中：`"center_offset_y": 0`
   - 在 `NavigationCore` 中通过 `set_center_offset()` 设置
   - 在 `MotionController` 中也使用这个参数

### 3.4 问题 4：环境配置同步不完整

**代码分析**:

在 `navigation_mode.py` 的 `_apply_config_to_core()` 方法中：
```python
def _apply_config_to_core(self):
    if not self.nav_core or not self.nav_config:
        return

    # 应用参数到核心模块
    rec_params_dict = self.nav_config.recognizer_params.__dict__
    self.nav_core.recognizer.set_params(rec_params_dict)
    self.nav_core.draw_scale = self.nav_config.draw_scale
    self.nav_core.set_center_offset(self.nav_config.nav_preferences.center_offset_y)

    # 设置运动控制器参数
    prefs = self.nav_config.nav_preferences
    center = self.nav_config.monitor_center
    size = self.nav_config.monitor_size
    if center and size > 0:
        self.motion_controller.set_screen_params(
            center[0], center[1], size,
            prefs.y_bias, prefs.center_offset_y
        )
```

**潜在问题**:
1. `draw_scale` 被设置到 `nav_core.draw_scale`，但需要确认是否与绘图模式一致
2. `config.json` 中的 `stitcher_params` 没有被使用（导航模式不需要拼接器）
3. `monitor_center` 和 `monitor_size` 是从 `config.json` 加载的，应该与绘图模式一致

---

## 四、详细代码审查

### 4.1 配置加载流程

```
navigation_mode.py::load_map()
    ↓
读取 map_data/{map_name}/config.json
    ↓
NavConfig.from_dict(config_dict)  # 解析配置
    ↓
NavigationCore(map_folder_path)  # 创建核心
    ↓
_apply_config_to_core()  # 应用配置到核心模块
    ↓
params_dialog.set_config_to_ui()  # 更新 UI
    ↓
_render_map()  # 渲染地图显示
```

### 4.2 配置保存流程

```
绘图模式::save_map()
    ↓
stitcher.save_map_package(folder_path)  # 保存 map_data.npz
    ↓
save_config()  # 保存 config.json
    ↓
{
    "monitor_center": self.monitor_center,
    "monitor_size": self.monitor_size,
    "recognizer_params": self.recognizer.get_params(),
    ...
}
```

### 4.3 定位流程对比

#### 绘图模式定位流程:
```
capture_and_process()
    ↓
capture_square(center_x, center_y, size)  # 截图
    ↓
recognizer.extract_combined(img)  # 提取特征
    ↓
stitcher.add_frame(img, combined, wall_mask, fog_mask, raw_gray, player_pos)
    ↓
phaseCorrelate(prev_mask, curr_mask)  # 计算位移
    ↓
更新 current_x, current_y
```

#### 导航模式定位流程:
```
navigation_loop()
    ↓
main_window.screen_capture.capture_square(center_x, center_y, size)  # 截图
    ↓
nav_core.localize(frame)
    ↓
recognizer.extract_combined(minimap_img)  # 提取特征
    ↓
matchTemplate(wall_layer, wall_mask_scaled)  # 模板匹配
    ↓
返回 (global_x, global_y, confidence)
```

**关键差异**:
1. 绘图模式使用 `phaseCorrelate` 进行帧间配准
2. 导航模式使用 `matchTemplate` 进行全局/局部搜索
3. 两种方法的坐标计算逻辑可能不同

### 4.4 坐标计算分析

#### NavigationCore.localize() 中的坐标计算:

```python
# 模板匹配成功后
offset_y_scaled = self.center_offset_y * self.draw_scale

center_x = top_left_offset[0] + max_loc[0] + w_t // 2
center_y = top_left_offset[1] + max_loc[1] + h_t // 2 + offset_y_scaled

self.current_pos = (center_x, center_y)
```

**这里的关键点**:
1. `center_offset_y` 会被乘以 `draw_scale` 后应用到 Y 坐标
2. 如果 `center_offset_y = 0`，则没有额外偏移
3. `max_loc` 是模板匹配的左上角坐标
4. `w_t // 2` 和 `h_t // 2` 是模板中心

#### StitcherCore.add_frame() 中的坐标计算:

```python
# 相位相关计算位移
shift, response = cv2.phaseCorrelate(keyframe_mask, match_mask)

dx_global = k_dx * self.draw_scale
dy_global = k_dy * self.draw_scale

target_x = self.keyframe_pos[0] - dx_global
target_y = self.keyframe_pos[1] - dy_global

self.current_x = target_x
self.current_y = target_y
```

**关键差异**:
1. 导航模式使用模板匹配，直接计算绝对位置
2. 绘图模式使用相位相关，计算相对位移
3. 两种方法的误差来源不同

---

## 五、问题总结

### 5.1 确认的问题

| 问题编号 | 问题描述 | 严重程度 | 是否导致偏移 |
|---------|---------|---------|-------------|
| P1 | 加载地图后中心点未显示 | 高 | 否（UI 问题） |
| P2 | 加载地图后监视幕布未显示 | 高 | 否（UI 问题） |
| P3 | 识别器参数可能未完全同步 | 中 | **是** |
| P4 | player_pos 在导航模式中未显式设置 | 中 | **是** |
| P5 | center_offset_y 的应用方式需要验证 | 中 | **是** |
| P6 | 模板匹配与相位相关的坐标计算差异 | 低 | 可能 |

### 5.2 潜在的设计问题

1. **配置分离问题**:
   - 绘图模式的配置保存在 `config.json`
   - 但导航模式加载时，某些参数可能需要重新计算
   - 例如：`monitor_center` 是物理像素坐标，但可能受到 DPI 缩放影响

2. **识别器状态问题**:
   - 绘图模式的 `recognizer` 在运行过程中可能被修改（通过 UI）
   - 导航模式加载时从 `config.json` 恢复参数
   - 但如果 `config.json` 不是最新的，会导致参数不一致

3. **坐标系统一致性问题**:
   - 绘图模式：`monitor_center` → 截图 → `player_pos = (size//2, size//2)`
   - 导航模式：`monitor_center` → 截图 → `player_pos` 未显式设置
   - `NavigationCore.localize()` 内部使用 `center_offset_y` 进行校正

---

## 六、修复建议

### 6.1 立即修复（高优先级）

#### 修复 P1: 加载时显示中心点

在 `navigation_mode.py` 的 `_render_map()` 方法中：
```python
def _render_map(self):
    # ... 现有代码 ...
    
    # 新增：显示监控中心点
    if self.nav_config and self.nav_config.monitor_center:
        # 计算中心点在地图显示坐标中的位置
        offset_x, offset_y = self.nav_core.crop_offset
        center_x = self.nav_config.monitor_center[0] - offset_x
        center_y = self.nav_config.monitor_center[1] - offset_y
        
        # 创建中心点标记（红色）
        self.center_marker = self.scene.addEllipse(
            center_x - 5, center_y - 5, 10, 10,
            QPen(Qt.red, 3), QBrush(Qt.red)
        )
        self.center_marker.setZValue(3)
        
        # 创建监视范围标记（绿色方框）
        size = self.nav_config.monitor_size
        self.monitor_rect = self.scene.addRect(
            center_x - size // 2, center_y - size // 2,
            size, size,
            QPen(Qt.green, 2), QBrush(Qt.NoBrush)
        )
        self.monitor_rect.setZValue(2)
```

#### 修复 P2: 加载时显示监视幕布

在 `navigation_mode.py` 的 `load_map()` 方法中，`_render_map()` 调用后：
```python
def load_map(self):
    # ... 现有代码 ...
    self._render_map()
    
    # 新增：显示监视幕布
    if self.nav_config and self.nav_config.monitor_center:
        center = self.nav_config.monitor_center
        size = self.nav_config.monitor_size
        self.overlay.set_geometry_and_show(center[0], center[1], size)
    
    # ...
```

### 6.2 核心修复（中优先级）

#### 修复 P3: 确保识别器参数完全同步

在 `navigation_mode.py` 的 `_apply_config_to_core()` 方法中：
```python
def _apply_config_to_core(self):
    if not self.nav_core or not self.nav_config:
        return

    # 完整同步识别器参数
    rec_params_dict = self.nav_config.recognizer_params.__dict__
    self.nav_core.recognizer.set_params(rec_params_dict)
    
    # 同步 draw_scale
    self.nav_core.draw_scale = self.nav_config.draw_scale
    
    # 同步 center_offset_y
    self.nav_core.set_center_offset(self.nav_config.nav_preferences.center_offset_y)
    
    # 同步 motion_controller
    prefs = self.nav_config.nav_preferences
    center = self.nav_config.monitor_center
    size = self.nav_config.monitor_size
    if center and size > 0:
        self.motion_controller.set_screen_params(
            center[0], center[1], size,
            prefs.y_bias, prefs.center_offset_y
        )
    
    # 新增：验证同步
    print(f"[导航模式] 识别器参数已同步:")
    print(f"  - transparent_mode: {self.nav_core.recognizer.transparent_mode}")
    print(f"  - wall_weight: {self.nav_core.recognizer.wall_weight}")
    print(f"  - edge_weight: {self.nav_core.recognizer.edge_weight}")
    print(f"  - draw_scale: {self.nav_core.draw_scale}")
    print(f"  - center_offset_y: {self.nav_core.center_offset_y}")
```

#### 修复 P4: 明确设置 player_pos

在 `navigation_mode.py` 的 `navigation_loop()` 方法中：
```python
def navigation_loop(self):
    if not self.nav_config or not self.nav_config.monitor_center: return

    center_x, center_y = self.nav_config.monitor_center
    size = self.nav_config.monitor_size
    frame = self.main_window.screen_capture.capture_square(center_x, center_y, size)
    if frame is None: return

    # 明确设置 player_pos 为图像中心（与绘图模式一致）
    player_pos = (size // 2, size // 2)
    
    # 传递给 localize 方法（需要修改 localize 签名）
    global_x, global_y, conf = self.nav_core.localize(frame, player_pos=player_pos)
```

注意：这需要修改 `NavigationCore.localize()` 方法签名，添加 `player_pos` 参数。

### 6.3 验证修复（低优先级）

#### 验证 P5: center_offset_y 的应用

需要验证 `center_offset_y` 在绘图模式和导航模式中的应用是否一致：

**绘图模式**:
- 在 `stitcher.add_frame()` 中，`player_pos` 用于确定截图中心相对于玩家位置的偏移
- 如果 `player_pos = (size//2, size//2)`，则截图中心就是玩家位置

**导航模式**:
- 在 `NavigationCore.localize()` 中，`center_offset_y` 被乘以 `draw_scale` 后加到 Y 坐标
- 这可能导致偏移

**建议**: 统一 `center_offset_y` 的应用方式，确保在两种模式中一致。

---

## 七、测试建议

### 7.1 单元测试

1. **测试配置加载**:
   - 验证 `config.json` 的所有字段都能正确加载
   - 验证 `NavConfig.from_dict()` 和 `to_dict()` 的往返转换

2. **测试识别器参数同步**:
   - 验证 `recognizer.set_params()` 后所有参数都正确设置
   - 比较绘图模式和导航模式的 `recognizer.get_params()` 输出

3. **测试坐标计算**:
   - 给定相同的截图和参数，验证两种模式的输出坐标是否一致

### 7.2 集成测试

1. **端到端测试**:
   - 在绘图模式下保存地图
   - 在导航模式下加载同一地图
   - 验证中心点和监视幕布正确显示
   - 验证定位坐标准确

2. **偏移测试**:
   - 在固定位置截图
   - 分别在绘图模式和导航模式下运行
   - 比较输出坐标的差异

---

## 八、结论

### 8.1 核心问题

1. **UI 显示问题**（高优先级）:
   - 加载地图后中心点未显示
   - 加载地图后监视幕布未显示

2. **参数同步问题**（中优先级）:
   - 识别器参数可能未完全同步
   - `player_pos` 在导航模式中未显式设置

3. **坐标计算问题**（需要验证）:
   - `center_offset_y` 的应用方式需要验证
   - 模板匹配与相位相关的坐标计算差异

### 8.2 修复优先级

1. **立即修复**: P1, P2（UI 显示问题）
2. **核心修复**: P3, P4（参数同步和坐标计算）
3. **验证修复**: P5, P6（需要进一步测试验证）

### 8.3 设计原则确认

**设计要求**: "导航模式通过加载保存的 config.json 每个地图一个环境，不共享绘图模式的环境"

**当前实现**: 
- ✓ 导航模式独立加载 `config.json`
- ✓ 导航模式有独立的 `NavigationCore`、`MotionController`、`OverlayWindow`
- ✓ 导航模式不修改绘图模式的状态

**需要改进**:
- ⚠️ 加载后应主动显示中心点和监视幕布
- ⚠️ 应确保识别器参数完全同步
- ⚠️ 应明确设置 `player_pos` 与绘图模式一致

---

## 附录 A: config.json 字段说明

| 字段 | 说明 | 导航模式使用 |
|------|------|-------------|
| `monitor_mode` | 监控模式（center/region） | ✓ |
| `monitor_center` | 截图中心点（物理像素） | ✓ |
| `monitor_size` | 截图大小 | ✓ |
| `monitor_region` | 拉框模式区域 | ✗ |
| `canvas_size` | 画布大小 | ✓（从 map_data.npz 加载） |
| `draw_scale` | 绘图缩放比例 | ✓ |
| `stitcher_params` | 拼接器参数 | ✗ |
| `recognizer_params` | 识别器参数 | ✓ |
| `nav_preferences` | 导航偏好 | ✓ |

## 附录 B: 关键代码位置

| 模块 | 文件 | 关键方法 |
|------|------|---------|
| NavigationCore | `core/navigation_core.py` | `localize()`, `_load_map_data()` |
| NavigationMode | `gui/navigation_mode.py` | `load_map()`, `_render_map()`, `navigation_loop()` |
| HSVRecognizer | `core/recognizer_optimized.py` | `extract_combined()`, `set_params()` |
| MotionController | `core/motion_controller.py` | `set_screen_params()`, `update()` |
| OverlayWindow | `gui/overlay_window.py` | `set_geometry_and_show()` |
| NavConfig | `gui/navigation_params.py` | `from_dict()`, `to_dict()` |
