# 地图墙体编辑器设计

**日期：** 2026-09-04  
**状态：** 已确认，待实现  
**范围：** 为总工作台新增 `地图编辑` 页面；编辑每张已保存地图的人工墙体修正，并让修正后的墙体同时用于定位模板与寻路障碍。

## 背景与目标

当前每张地图包位于 `map_data/<地图名>/`，其中 `map_data.npz` 保存了地图拼接产物和原始 `wall_layer`。定位会将当前小地图提取出的墙体模板与已保存的全局墙体图对齐；寻路从同一份墙体图生成更宽容的导航障碍层。

自动绘制出的墙体会有缺失或误识别。用户需要在不重绘地图、不改动原始地图包的前提下：

- 加载已有地图；
- 手动增加墙体或擦除墙体；
- 缩放、平移并连续绘制；
- 撤销、重做、放弃未保存修改；
- 保存后，在下次加载地图时同时影响定位和寻路。

## 已选方案：非破坏性墙体修正层

保留 `map_data.npz` 原样；每张地图新增独立的修正层文件：

```text
map_data/<地图名>/
├─ map_data.npz            # 由绘图模式生成的原始地图包，不直接改写
├─ config.json             # 原有绘图 / 导航配置，保留全部字段
└─ wall_overrides.npz      # 新增的人工墙体修正层
```

`wall_overrides.npz` 包含与原始 `wall_layer` 相同尺寸的两个 `uint8` 二值数组：

- `add_mask`：人工确认存在墙体的位置；
- `erase_mask`：人工确认不存在墙体的位置。

一个像素只能位于其中一层。每次“加墙”会清除同位置的 `erase_mask`；每次“擦墙”会清除同位置的 `add_mask`。

最终墙体合成规则如下：

```text
effective_wall = base_wall.copy()
effective_wall[erase_mask > 0] = 0
effective_wall[add_mask > 0] = 255
```

合成顺序使最近一次用户操作拥有确定的覆盖结果。原始墙体保持可恢复；后续同名地图重新绘制后，修正层仍可继续叠加到新的基础墙体上。

## 配置元信息

保存修正层时，保留 `config.json` 所有既有字段，并合并：

```json
{
  "wall_overrides": {
    "enabled": true,
    "file": "wall_overrides.npz",
    "format_version": 1
  }
}
```

数组不写入 JSON，避免 5,000 至 7,500 像素级墙体图造成巨大、缓慢且难以校验的配置文件。

## 模块边界

```text
core/map_editing/
├─ models.py       # WallOverrideDocument、编辑模式、保存结果
├─ operations.py   # 圆形画笔在地图坐标上应用加墙 / 擦墙
├─ composition.py  # 原始墙体 + add/erase mask → effective_wall
└─ storage.py      # map_data、修正层、config 的校验及原子读写

gui/modes/map_editor/
├─ widget.py       # 页面组合根
├─ canvas.py       # 预览绘制、缩放平移、屏幕坐标 → 地图坐标
└─ controller.py   # 地图选择、命令栈、脏状态、保存与重载
```

`core/map_editing` 不导入 Qt。GUI 只把鼠标交互转换成地图像素坐标与编辑命令。

## 总 UI 集成

总工作台增加第四个正式模式按钮：`🧱 地图编辑`。页面与绘图、导航、虚拟手柄并列，切换到页面时刷新可编辑的 `map_data/` 地图列表。

页面包含：

- 地图选择下拉框及加载按钮；
- `加墙` / `擦墙` 两种互斥工具；
- 画笔半径；
- 放大、缩小、适应画布；
- 撤销、重做、重新加载、清除修正、保存；
- 画布状态：地图名称、原始尺寸、修改计数、未保存标记；
- 可缩放、可平移地图画布。

画布以灰度地图为底图；基础墙体、人工加墙、人工擦墙分别使用清晰且可区分的叠加色。拖动鼠标连续绘制。无论显示缩放比例如何，画笔均在地图原始像素坐标工作。

## 加载和运行时语义

`core.localization.map_package.load_navigation_map_package()` 在读出 `map_data.npz` 的 `wall_layer` 后，调用 `core.map_editing` 合成有效墙体。之后既有流程不需要知道 UI 编辑器：

```text
map_data.npz 的 base wall_layer
  + wall_overrides.npz
  → effective wall_layer
  → 定位的全局墙体模板
  → derive_navigation_wall_layer(...)
  → A* 导航障碍图
```

若 `config.json` 没有 `wall_overrides` 字段、修正文件不存在或修正层被禁用，则使用原始 `wall_layer`，完全兼容已有地图。

正在运行的导航不会在编辑器保存时热替换内存中的地图。保存成功后页面提示用户在导航页面重新加载当前地图；这样不会在路径运行中突然改变障碍图或定位模板。

## 存储安全

- 保存到同目录临时文件，完成后用原子替换更新 `wall_overrides.npz`；
- 配置通过“读出 → 合并 `wall_overrides` → 临时文件 → 原子替换”写入；
- 保存前验证原始地图和两张修正层形状一致；
- 形状不匹配、缺失 `wall_layer`、损坏 npz 或 JSON 时拒绝保存，并保留已有文件；
- 清除修正仅清空编辑器内存状态，必须经过保存才影响磁盘。

## 验收条件

1. 同一像素的加墙 / 擦墙操作遵循最后一次操作；合成结果正确。
2. 保存后重新打开同一地图，画布与有效墙体保持一致。
3. 已有 `config.json` 字段完全保留，只新增或更新 `wall_overrides`。
4. 没有修正层的旧地图能够照旧加载。
5. `NavigationCore` 加载带修正层的地图后，`wall_layer` 是合成结果，`nav_wall_layer` 从它重新生成。
6. 画布缩放和拖动不改变真实地图坐标；连续画笔不会在拖动间产生断点。
7. 保存成功不会改变正在运行导航的内存地图；重新加载后才生效。
