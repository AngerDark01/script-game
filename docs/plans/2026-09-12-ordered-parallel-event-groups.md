# 顺序事件中的并行动作组

## 目标

在已有事件模型中增加一种非递归的 `parallel` 顺序步骤。步骤内部的移动、按键和频率动作并行执行；达到动作组时长后，事件继续执行下一个顺序步骤。

## 数据格式

```json
{
  "op": "parallel",
  "ms": 1000,
  "tracks": [
    {"buttons": ["LS_RIGHT"], "mode": "continuous", "delay_ms": 0},
    {"buttons": ["RB"], "mode": "once", "delay_ms": 200, "hold_ms": 100},
    {"buttons": ["X"], "mode": "frequency", "delay_ms": 100, "hold_ms": 50, "interval_ms": 250, "end_ms": 800}
  ]
}
```

`ms` 是动作组的硬边界。`delay_ms`、`end_ms` 都相对于动作组起点。第一版不允许动作组内部再次嵌套动作组。

## 模块复用

- `core/events/event_lifecycle.py`：计算动作组当前应输出的声明式手柄输入。
- `core/events/gamepad_output.py`：继续负责把合并后的按键和左摇杆方向转换为完整 XInput 状态。
- `core/runtime/event_session.py`：本机和远端事件继续共用同一个会话模型。
- `gui/modes/follow/editors.py`：事件链编辑器通过独立对话框编辑组内动作。

## 完成状态

- [x] 延迟、单次、持续和频率动作语义
- [x] 移动与按键同时输出
- [x] 动作组结束后准确进入下一顺序步骤
- [x] 循环和执行次数边界
- [x] 非递归校验和输入范围校验
- [x] 编辑器保存与重新载入
- [x] 远端事件到虚拟手柄状态的集成测试
- [x] Python 事件回归和 .NET 虚拟手柄 Host 回归
