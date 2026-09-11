# 通用事件工作台：开发计划与断点

## Goal

在已有模块上实现可复用的事件、事件组、跨电脑/手柄触发及并行跟随，不增加技能视觉识别。

## Architecture Overview

依据 `2026-09-11-event-workbench-design.md`。保持现有 EventRegistry 和有限序列处理器；新增定时与组合职责；每手柄单一输出拥有者；跟随作为可组合的持续行为。局域网协议与配对复用，不重造驱动和导航。

## Tech Stack

Python 3.12、pytest 虚拟时钟测试、PySide6 工作台、现有 Windows multiprocessing、C# .NET 8 宿主/LAN 服务。新增定时功能仅使用标准库；OpenCV 留在定位侧，不引入技能识别依赖。

## 执行纪律

- 工作目录：`D:/ACloud/auto_modules`。回滚基线：`4025221`。
- 先写失败测试，运行确认失败原因，再实现、回归、按任务提交。下文命令的结果均是预期，不是已执行结果。
- 每个完成项记录提交号、实际测试命令/结果、遗留问题。只提交本任务文件，保留其他更改。
- 本文第一阶段提供可执行小任务；后续阶段是依赖明确的开发清单，须在轮到该阶段时结合前阶段实际接口继续展开，不能当作已详细化或已完成。
- 本计划不授权发送真实游戏输入；真实验收须先获得用户配置和明确开始指令。

## 第一阶段：组合按键与周期基础（已完成，2026-09-11）

以下代码和预期输出保留为原任务定义。实际实现另补充了组合键列表隔离、非法时间戳测试；实际验证结果及提交号见末尾进度记录。

### Task 1：复用按钮表，规范化单键/组合键（2–5 分钟）

修改：`D:/ACloud/auto_modules/core/events/follow_chain.py`。
新增：`D:/ACloud/auto_modules/tests/test_event_button_chords.py`。

先添加完整测试：

```python
import pytest
from core.events.follow_chain import button_mask


def test_single_and_chord_use_existing_masks():
    assert button_mask({'button': 'A'}) == 0x1000
    assert button_mask({'buttons': ['A', 'RB']}) == 0x1200
    assert button_mask({'buttons': ['A', 'A']}) == 0x1000


@pytest.mark.parametrize('step', [
    {}, {'buttons': []}, {'buttons': 'A'}, {'buttons': ['LT']},
    {'buttons': [None]}, {'button': 'A', 'buttons': ['B']},
])
def test_invalid_or_ambiguous_chord_is_rejected(step):
    with pytest.raises(ValueError):
        button_mask(step)
```

运行 `python -m pytest tests/test_event_button_chords.py -q`：预期首次导入失败，新增下列完整函数后 7 passed。

在既有 BUTTONS 表后添加，不复制按钮表：

```python
def button_mask(step):
    if 'button' in step and 'buttons' in step:
        raise ValueError('choose button or buttons, not both')
    names = step.get('buttons') if 'buttons' in step else [step.get('button')]
    if not isinstance(names, (list, tuple)) or not 1 <= len(names) <= 16:
        raise ValueError('one to sixteen Xbox buttons required')
    mask = 0
    for name in names:
        if not isinstance(name, str) or name not in BUTTONS:
            raise ValueError('unknown Xbox button')
        mask |= BUTTONS[name]
    return mask
```

提交：`git add core/events/follow_chain.py tests/test_event_button_chords.py`，然后 `git commit -m "feat: normalize event button chords"`。

### Task 2：有限序列支持组合按钮，保持旧配置兼容（2–5 分钟）

修改同 Task 1 两个文件。在测试文件追加：

```python
from core.events.follow_chain import FollowChainDefinition
from core.events.models import EventTask, EventTick, EventActionType


def test_chord_releases_before_next_button_without_localization():
    definition = FollowChainDefinition('skill', [
        {'op': 'button', 'buttons': ['A', 'RB'], 'ms': 80},
        {'op': 'wait', 'ms': 20},
        {'op': 'button', 'button': 'X', 'ms': 60},
    ])
    handler = definition.create_handler({})
    task = EventTask('one', 'skill', (0, 0), 0, 0)
    handler.start(task)
    assert handler.update(EventTick(0), task).metadata['buttons'] == 0x1200
    assert handler.update(EventTick(79), task).metadata['buttons'] == 0x1200
    assert handler.update(EventTick(80), task).metadata['buttons'] == 0
    assert handler.update(EventTick(100), task).metadata['buttons'] == 0x4000
    assert handler.update(EventTick(160), task).type == EventActionType.COMPLETE
```

运行 `python -m pytest tests/test_event_button_chords.py tests/test_follow_chain.py -q`：预期新测试失败于旧单按钮校验。最小修改：用以下完整代码段替换现有 `op == 'button'` 验证：

```python
            if op == 'button':
                button_mask(step)
```

处理器定时返回替换为：

```python
            if op in ('wait', 'button') and now-self.step_started < duration:
                return EventAction.wait(duration-(now-self.step_started), metadata={
                    'buttons': button_mask(step) if op == 'button' else 0})
```

重跑同一命令：预期 10 passed。此测试只说明处理器无需视觉，不说明跟随运行时已解耦。

提交：`git add core/events/follow_chain.py tests/test_event_button_chords.py`，然后 `git commit -m "feat: execute timed Xbox button chords"`。

### Task 3：固定节拍、不重叠、不补发的周期器（2–5 分钟）

新增：`D:/ACloud/auto_modules/core/events/periodic_schedule.py`、`D:/ACloud/auto_modules/tests/test_event_periodic_schedule.py`。

先写测试：

```python
import pytest
from core.events.periodic_schedule import PeriodicSchedule


def test_fixed_cadence_skips_missed_ticks_and_busy_cycles():
    schedule = PeriodicSchedule(500, first_due_ms=0)
    assert schedule.poll(0)
    assert not schedule.poll(499)
    assert not schedule.poll(500, busy=True)
    assert not schedule.poll(501)
    assert schedule.poll(1600)
    assert schedule.next_due_ms == 2000
    assert not schedule.poll(1600)
    assert schedule.poll(2000)


def test_delayed_first_run_and_backwards_clock():
    schedule = PeriodicSchedule(100, first_due_ms=100)
    assert not schedule.poll(99)
    assert schedule.poll(100)
    with pytest.raises(ValueError):
        schedule.poll(99)


@pytest.mark.parametrize('interval', [0, -1, 1.5, True])
def test_rejects_invalid_interval(interval):
    with pytest.raises(ValueError):
        PeriodicSchedule(interval, first_due_ms=0)
```

运行 `python -m pytest tests/test_event_periodic_schedule.py -q`：预期模块缺失。再添加实现：

```python
class PeriodicSchedule:
    """Caller-owned monotonic milliseconds; no threads, I/O or catch-up queue."""

    def __init__(self, interval_ms, *, first_due_ms):
        if type(interval_ms) is not int or interval_ms <= 0:
            raise ValueError('positive integer interval required')
        if type(first_due_ms) is not int or first_due_ms < 0:
            raise ValueError('nonnegative integer deadline required')
        self.interval_ms = interval_ms
        self.next_due_ms = first_due_ms
        self.last_poll_ms = None

    def poll(self, now_ms, *, busy=False):
        if type(now_ms) is not int or now_ms < 0:
            raise ValueError('nonnegative integer timestamp required')
        if self.last_poll_ms is not None and now_ms < self.last_poll_ms:
            raise ValueError('monotonic clock required')
        self.last_poll_ms = now_ms
        if now_ms < self.next_due_ms:
            return False
        skipped = (now_ms - self.next_due_ms) // self.interval_ms
        self.next_due_ms += (skipped + 1) * self.interval_ms
        return not busy
```

重跑同一命令：预期 6 passed。次数、暂停、取消由上层实例生命周期负责，不塞进纯时间计算器。

提交：`git add core/events/periodic_schedule.py tests/test_event_periodic_schedule.py`，然后 `git commit -m "feat: add non-burst periodic event timing"`。

## P1.5：轨道事件模型（下一批）

在进入输出合并前，先把本次确认的事件模型落成纯逻辑模块：持续轨道、频率轨道（保持时长/间隔/轨道结束时间）、单次轨道与其他轨道并行，以及事件级次数/循环/结束时间。使用虚拟单调时钟测试，不接手柄、不依赖定位、不做画面识别。

预期文件：`core/events/action_tracks.py`、`core/events/event_lifecycle.py`、`tests/test_action_tracks.py`、`tests/test_event_lifecycle.py`。验证同一时间点可同时产生持续组合键和单次组合键；错过节拍不补发；次数或结束时间先到即结束；无结束条件的循环配置被拒绝；事件结束清理全部按钮贡献。

## 后续阶段清单（待按实际接口展开成小任务）

| 阶段 | 具体落点 | 必须验证的结果 |
|---|---|---|
| P2 通道归属 | 新 `core/actions/gamepad_compositor.py`、`tests/test_gamepad_compositor.py`；扩展 `core/actions/program_gamepad.py` | 轨道输出与跟随 LS 合成；同按钮释放不干扰其他持有者；独立点击冲突不丢边沿；RS/LT/RT 输出；每手柄只有一个 lease；过期贡献不得续命 |
| P3 普通事件运行时 | 新 `core/runtime/event_session.py`、`tests/test_event_session.py`；复用 `core/events/registry.py` | 没有地图或领导者坐标也能执行；周期本地运行；停止释放自己的通道；有界实例及错误隔离 |
| P4 跟随适配与插入 | 修改 `core/runtime/dual_follow_session.py`、`follower_controller.py`；新 `core/events/follow_behavior.py`；扩展 `tests/test_dual_follow_session.py` | 原跟随逻辑复用；暂停立即回中；插入后新位置恢复；停止/故障代次和嵌套暂停阻止错误恢复 |
| P5 组调度 | 新 `core/events/event_group.py`、`tests/test_event_group.py` | 顺序/并行/插入；持续事件启动后继续；循环检测；取消仅影响自己拥有的子实例 |
| P6 进程集成 | 修改 `core/runtime/follow_workers.py`、`follow_service.py`、`main.py`；扩展 `tests/test_follow_workers.py`、`test_follow_service.py` | 普通事件不加载地图、不启动视觉；每手柄最终输出独占；实际工作台入口 Windows spawn 不触发重复提权/单实例退出（先验证此风险） |
| P7 配置与迁移 | 新 `core/events/workbench_config.py`、`tests/test_event_workbench_config.py`；修改 `core/runtime/follow_config.py` | 事件/组/规则分开版本保存；旧链迁移；不自动授权；无效引用和快捷键冲突提示 |
| P8 LAN 路由与回执 | 扩展 `core/lan_follow/follow_transport.py`、`lan_input_sync/src/LanInputSync/LanSyncService.SharedData.cs`；扩展 `tests/test_follow_transport.py` 和现有 LAN 测试项目 | 指定来源/目标/事件授权；会话期限去重；幂等开始停止；多目标结果；断线停止所属远程实例；无旧操作重放 |
| P9 工作台编辑 | 修改 `gui/modes/follow/page.py`、`editors.py`；新 `gui/modes/follow/event_workbench.py`、`tests/test_event_workbench_ui.py`；扩展 `tests/test_follow_page.py` | 事件库/组/触发与执行/状态；无需 JSON；无需地图也能编辑普通事件；使用现有主题，不改其他页 |
| P10 验收 | 新 `docs/plans/2026-09-11-event-workbench-verification.md` | 离线时序、安全、旧功能回归；真实 UI/双机/游戏验证分别记录，禁止合成测试冒充实测 |

P2–P10 每阶段开发前补充 2–5 分钟任务、可复制测试和实现片段、精确验证命令。不得一边保留旧运行时写手柄，一边启动新运行时竞争输出。

## 进度记录

| 项目 | 状态 | 证据 |
|---|---|---|
| 用户设计确认 | 完成 | 同意不做技能视觉确认；按时间执行、与跟随组合 |
| 已有实现审查 | 完成 | 已读有限序列、注册器、动作适配器、program 输出、双跟随会话、配置和 UI 入口 |
| 设计和计划落档 | 完成 | 本文及配套设计；仅文档变更 |
| Task 1 单键/组合键规范化 | 完成 | `807d9a4`；先导入失败，再正常输入通过，非法配置由失败转通过；7 passed |
| Task 2 有限序列支持组合键 | 完成 | `5dbdfc9`；新时序用例先失败于旧单键验证；修复后通过；另补配置列表隔离测试并修复共享引用；相关组合/旧链/配置/会话测试 15 passed |
| Task 3 周期调度基础 | 完成 | `dd78d0c`；按节拍、忙时跳过、回退时钟、非法参数逐项先红后绿；10 passed |
| P1.5 轨道事件模型 | 待开发 | 已根据用户确认补充；尚未写入实现或运行测试 |
| P2–P10 | 待展开/开发 | 尚未修改运行时、协议和界面 |

### 首批验证记录

实际执行（系统 Python 3.12，工作目录 `D:/ACloud/auto_modules`）：

```powershell
python -m pytest tests/test_event_button_chords.py tests/test_event_periodic_schedule.py tests/test_follow_chain.py tests/test_follow_config.py tests/test_dual_follow_session.py tests/test_follow_workers.py tests/test_follow_service.py tests/test_follow_transport.py tests/test_follow_page.py tests/test_program_gamepad.py tests/test_gamepad_action_adapter.py tests/test_gamepad_motion.py -q
```

结果：**39 passed in 0.98s**。检查了本批代码差异，`git diff --check` 通过。没有执行完整项目测试、双机验证或游戏输入测试。

本批没有添加依赖、启动采集/驱动或触发真实按键；只扩展原处理器并增加纯时间调度器。周期器还没有接入服务和 UI，普通事件与跟随定位的运行时解耦也尚未完成，不能将这些底层测试解释为完整事件工作台可用。

## 当前断点

首批 Task 1–3 已完成并提交，按 executing-plans 批次流程到达检查点。下一步展开 P2 的通道归属与完整手柄状态输出任务，再实现 P3 普通事件运行时。当前 UI 未新增入口；不要直接让多个事件各自获取 program lease。原配置/单键执行保持兼容。无论后续执行方式，均保留每阶段测试与本地提交记录。
