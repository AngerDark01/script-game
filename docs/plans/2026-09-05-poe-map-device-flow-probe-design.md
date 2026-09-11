# PoE 地图装置定位—移动—交互探针设计

## 目标

在不改动正式业务链路的前提下，验证“主屏截图 → OCR 识别地图装置 → 固定人物锚点计算方向 → Xbox 左摇杆短脉冲移动 → 闭环校正 → A 键交互”的组合是否可行。

## 边界

- 探针脚本位于仓库外：`D:/ACloud/poe_map_device_flow_probe.py`。
- 只使用现有 `DesktopFrameSource`、RapidOCR、`DesktopCoordinateMapper` 和 `VirtualGamepadActionAdapter`。
- 不修改旧导航、识别、地图编辑器或 GUI 实现。
- 默认 dry-run；真实输入必须显式传入 `--execute`。

## 运动模型

不把屏幕像素距离直接当成游戏世界距离。每个控制周期都重新识别目标，并用目标向量的变化估算有效进度：

```text
progress = dot(previous_delta - current_delta, commanded_screen_direction)
speed_px_s = progress / pulse_duration_s
```

速度仅用于调整下一次脉冲时长和力度；移动始终由视觉闭环控制。

Xbox 轴约定：

- 屏幕右 → `LeftX > 0`
- 屏幕左 → `LeftX < 0`
- 屏幕上 → `LeftY > 0`
- 屏幕下 → `LeftY < 0`

每个脉冲结束显式发送 `(0, 0)`，并等待画面稳定。连续丢失目标、无进度、超过步数/时长或目标跳变时立即停止并回中。

## 目标选择与到达

- OCR 文本按精确值匹配 `地图装置`。
- 过滤右上角小地图重复标签；优先主画面较大且置信度高的文本框。
- 人物屏幕锚点使用已确认的 `(1335, 850)`。
- 初始到达距离阈值为 160 像素。
- 实机模式要求目标附近绿色交互提示出现后才允许按 A。
- A 按下约 80 ms 后释放，截图变化比例用于给出 `opened` 或 `action_sent_unverified`。

## 验证顺序

1. Python 语法检查和离线方向/进度计算测试。
2. dry-run：确认主屏尺寸、OCR 目标筛选、目标向量和建议动作。
3. 单次短脉冲：确认上下方向符号和实际进度。
4. 限定步数的完整闭环，只有达到交互门槛才发送 A。

