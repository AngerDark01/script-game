# PoE2 导航兼容实时跟踪断点

最后更新：2026-09-23

## 当前状态

**第一版正式 hybrid tracker 与测试台多帧实验均已完成单元/聚焦回归；真实移动轨迹、真实丢失恢复和多地图方向泛化仍待实机验收。**

采用方案 A：

```text
首帧/恢复：一次内存锚点 + 锚点附近形状注册
正常跟踪：帧间位移预测为主
局部形状：只做预测后的纠偏或位移失败备用
视觉丢失：只开启一个新的内存恢复 revision
```

## 已完成

- 新增通用 `canonical_wall_mask()` 和 `canonical_boundary_from_walkable()`，统一视觉墙体和内存 terrain 边界的二值形状表示。
- 新增通用 `transform_local_displacement()`，显式处理旋转、水平镜像和比例对位移向量的影响。
- 新增 `estimate_bounded_displacement()`，复用导航模式的 phase correlation，并加入质量、最大位移和失败原因门控。
- `reference_boundary_layer()` 已改为使用通用 canonical boundary；第一页绘图模式未修改。
- `VisualLocalTracker` 已改为位移优先：成功来源为 `visual_f2f`；位移质量不足才调用有界 `LocalMapMatcher`，来源为 `visual_local`；两者均失败才交给 hybrid controller 触发恢复。
- tracker 不再丢弃 `previous_frame`，也不再把每帧局部 Chamfer 搜索作为主路径。
- 首帧和同实例恢复仍由 `AnchoredAbsoluteRegistrar` 负责，没有改成整图搜索。

## 当前调用链

```text
HybridLocalizationSession.tick()
 -> HybridLocalizationController.update()
 -> NEED_ABSOLUTE/RECOVERY_PENDING:
    memory anchor -> anchored local registration
 -> LOCAL_TRACKING:
    canonical previous/current wall mask
    -> bounded phase displacement
    -> similarity transform to global delta
    -> previous position - global delta
    -> optional bounded shape correction
 -> publish HybridLocalizationState
```

## 验证结果

```text
canonical wall / displacement / tracker / registrar focused: 21 passed
continuous tracker replay: 5 passed
PoE2 terrain + hybrid + UI + composition + architecture: 204 passed
```

正式 hybrid 的连续帧回放、`compileall`、`git diff --check` 已完成；仍需实机静止、移动、遮挡/丢失、恢复和换图验收。多帧实验的 schema 3 回放已可执行，但没有把实验 factory 接入正式 tracker。

## 尚未验证的风险

1. phase correlation 在真实稀疏或重复墙体中的质量是否足够。
2. 旋转、镜像、比例变换后的位移方向是否与 PoE2 terrain 坐标一致。
3. canonical wall 的闭运算参数是否适用于不同地图和不同颜色配置。
4. f2f 预测失败后的局部 Chamfer 半径是否需要按速度动态调整。
5. 实机移动期间是否会出现连续误差积累或错误恢复。

## 下一步入口

1. 用现有样本生成连续帧回放，记录 `shift/quality/global_shift/source/position`。
2. 回放方向正确后启动 GUI 做真实移动测试。
3. 确认正常移动期间 `memory_read_count` 保持不变。
4. 制造一次视觉丢失，确认最多增加一次内存读取并回到 `anchored_absolute -> visual_f2f`。
5. 换图确认旧 registration、轨迹和方向不会泄漏到新实例。

## 2026-09-22 实机失败排查断点

用户实机反馈首帧定位失败，画面随后不再变化。当前已确认：

- `session.tick()` 先调用 `controller.prepare_capture()` 读取一次内存锚点，再采集一帧；随后 `controller.update(frame)` 在同一恢复版本内只调用一次 `absolute_registrar.register()`。
- 首帧注册失败后状态转为 `RECOVERY_REQUIRED`，页面主动停止 `monitor_timer`；因此失败后的监控画面保持最后一帧是保护行为，不是同一帧在后台无限匹配。
- 日志中的三次注册分别对应三次恢复版本（`read_count=1/2/3`），由用户重复点击“重新定位”触发，不是单次 tick 重复调用。
- 最新失败样本 `20260922-133833-660635-MapFlotsam-1E44BF94`：一次注册耗时约 `4927.7 ms`，候选最佳为 `angle=219, reflection=true, scale=0.81`，`anchor_error=1.98`，但 `forward_coverage=0.6336 < 0.65`，因此被拒绝。
- 另一个同地图样本 `20260922-043532-966126-MapFlotsam-1E44BF94` 可返回 `anchored_candidate`，最佳锚点误差约 `7.10`、`forward_coverage=0.7838`。这说明当前优先问题是样本特征/候选稳定性差异，而不是控制器把同一帧重复匹配。
- 当前匹配耗时主要来自精搜：粗搜 1 次约 `245~332 ms`，随后每个 refine seed 约 `186~346 ms`；本断点阶段暂不改线程和性能架构，先稳定候选与拒绝原因。

下一步排查必须以失败/成功样本成对对比，记录墙体像素数、组件清理结果、候选角度/镜像/比例、正反向覆盖率和叠图；在证据明确前不要单独放宽 `minimum_forward_coverage`。

本阶段不发送 Xbox、键盘、鼠标、Host 或 LAN 输入。

## 2026-09-22 全局恢复与自动方向展示修复

本轮针对“首帧和后续全局恢复都可能报错、成功后大地图方向仍不对”完成三项修复：

1. `AnchoredAbsoluteRegistrar` 的恢复路径先沿用上一注册的角度/镜像/比例做快速 translation-only 搜索；如果该 basin 因当前帧遮挡、比例变化或墙体缺失而失败，会在同一次内存锚点下自动回退完整角度/镜像/比例搜索，不会重新读内存。回退结果在 diagnostics 中标记为 `search_mode=full_similarity_recovery`，并记录 `attempt_count=2`。
2. 精搜候选通过 score、coverage 和 walkable 门后，使用 memory anchor 做优先消歧。默认 `anchor_acceptance_radius=8px`、`anchor_disambiguation_gap=2px`；最近锚点候选与下一个近锚点候选相差至少 2px 时，即使纯视觉 score 分差小，也发布 `anchored_candidate`。这修复了实机样本中视觉分数第一名误压过锚点误差更小候选导致的 `ambiguous`。
3. `present_localization_overlay()` 在绘制轨迹和 marker 后，使用成功 registration 的逆角度和水平镜像对整张大地图做任意角度变换，使地图、人物点和轨迹保持同一坐标系。页面元数据显示 `方向：自动校准 X°`；数据采集页现在也注入 hybrid factory，可以独立复测相同链路。

离线复测：`20260922-144211-152568-MapFlotsam-1E44BF94` 由 `ambiguous` 变为 `anchored_candidate`，最佳候选从视觉分较高的 `215°` 调整为锚点误差 `2.40px` 的 `182°`；相关 PoE2/hybrid/UI 回归 `195 + 22` 通过，compileall 通过。

尚未完成：实机重新启动后的每次恢复、真实移动时的任意角度地图视觉效果，以及多地图随机方向的泛化；本轮没有执行输入控制、网络同步或自动移动。

## 2026-09-23 首帧匹配窗口按截图尺度校准

用户澄清本轮“缩小范围”指匹配使用的 terrain 网格，而不是 UI 地图展示范围：应以内存人物位置为中心，截取与当前小地图截图覆盖尺度相称的 native terrain。

样本证据：当前真实小地图为 `200 x 200`，人物 marker 为 `(100, 100)`，MapFlotsam native terrain 为 `2416 x 2277`。同一批首帧样本复测如下：

| 粗搜/精搜半径 | 状态 | 最佳锚点误差 | forward coverage | 说明 |
|---|---|---:|---:|---|
| `180/130` | `anchored_candidate` | `7.10px` | `0.784` | 可用，但窗口明显偏大 |
| `150/110` | `anchored_candidate` | `0.18px` | `0.759` | 保留墙体且候选集合更小，作为默认 |
| `140/100` | rejected | `4.06px` | `0.638` | 有效墙体被裁切，分数低于 `0.50` |
| `130/96` | rejected | `9.60px` | `0.634` | 墙体信息进一步不足 |
| `120/90` | rejected | `9.32px` | `0.509` | 明显丢失匹配结构 |

实现已落在 `experimental/hybrid_localization/absolute_registrar.py`：默认 `crop_radius=150`、`refine_crop_radius=110`，新增 `capture_reference_size=200`。`HybridFrame.from_evidence()` 保存真实 `capture_size` 诊断；正式实机帧按 wall mask 实际边长同比例缩放窗口，例如 `320 x 320` 自动得到 `240/176`。离线探针和手工构造 frame 未提供该诊断时，仍使用显式半径，避免测试数据被隐式改写。

新增诊断字段：`capture_size`、`crop_radius`、`refine_crop_radius`。这使日志可以直接核对“截图尺寸 -> 匹配 terrain 窗口”的关系，不再只看到候选分数而无法判断搜索集合是否过大或被裁切。

验证：absolute registrar、models、session focused `25 passed`；`compileall` 和 `git diff --check` 通过；同一真实样本以 `150/110` 返回 `anchored_candidate`。本轮未发送 Xbox、键鼠、Host、LAN 或自动移动输入。下一步实机应记录上述三个窗口诊断字段，并在不同 `capture_size`/地图方向下确认首帧仍落在内存锚点附近。

## 2026-09-23 地图显示放大与人物跟随

定位页的完整 native 地图仍保留原坐标和全图内容，但展示不再只按整张 pixmap fit：`ScalableMapWidget.focus_on_point()` 会按源坐标放大并将人物放到视口中心。PoE2 正式页和数据采集页默认使用 `2.4x` 跟随放大，定位失败时以最后可信位置保持视野；旋转/镜像后的显示坐标由 presenter 的同一变换矩阵计算。该层只改变 Qt 视图，不改变视觉匹配、人物坐标、内存读取或定位状态机。

## 2026-09-23 连续轨迹旋转方向修复

本轮确认了“离线地图方向正确，但人物移动轨迹没有同步”的根因：首帧形状匹配通过 `similarity_search.transform_feature()` 使用 OpenCV 图像坐标矩阵 `[[cos, sin], [-sin, cos]]`；连续帧 `VisualLocalTracker.track()` 原先通过通用 `transform_local_displacement()` 使用笛卡尔矩阵 `[[cos, -sin], [sin, cos]]`。同一个正角度在两处的 y 方向相反，所以 `visual_f2f` 的 `global_shift` 会把真实移动投影到相反方向。presenter 的“先画轨迹再整体逆变换”只能保持显示层同变换，无法修正已经错误计算的全局位置。

已修复 `core/localization/displacement.py`：保留水平镜像 -> 旋转 -> 比例的顺序，旋转矩阵改为与 OpenCV feature transform 一致的图像坐标语义。新增回归覆盖：

- 正角度 90° 的右移向量应转为向上；
- 任意角度、水平镜像和比例下，位移变换等于 `transform_feature()` 对两个点分别变换后的差值。

验证：`tests/test_displacement.py`、`tests/poe2_live_terrain/test_hybrid_visual_local_tracker.py`、`tests/test_poe2_live_terrain_presenter_position.py` 共 `15 passed`。该修复不增加内存读取，不触发 Xbox/键鼠/Host/LAN 输入，也不修改第一页绘图模式。下一步实机只需记录首帧角度、连续帧 `shift/global_shift/position`，确认人物沿实际通道移动时轨迹方向一致。

## 2026-09-23 首帧参数回归修复

本轮实机失败发生在 `absolute_registration`，不是连续位移变换：失败诊断仍显示 `capture_size=200`、粗搜/精搜 `150/110`，说明缩小匹配范围仍生效。当前 wall mask 顶部的动态文字/传送点粗块干扰了候选，导致最佳候选降到 `score=0.492`、`coverage=0.609`、`scale=0.31` 并被拒绝。

对失败帧和此前成功帧做参数复放后，PoE2 实验默认 `top_exclusion_rows` 从 `25` 调整为 `40`：同一失败帧可恢复到约 `angle=219~221°、scale≈0.75`，结构分约 `0.55`、覆盖率约 `0.75`；此前成功样本仍通过。没有降低普通候选的 score 门槛，也没有改变 `150/110` 搜索窗口。diagnostics 现在额外记录顶部清理行数和人物清理半径。相关回归共 `190 passed`，compileall 通过。

## 2026-09-23 多帧全局注册与导航闭环设计入口

完整待实现方案已记录在：

`docs/plans/2026-09-23-poe2-multiframe-localization-navigation-design.md`

该方案修订了“首帧单次匹配成功后就直接进入跟踪”的边界：首帧/恢复首先进入全局注册证据阶段，可在移动时用 A（有限局部墙体拼图）或 B（共同变换候选）积累证据，确认人物和参考地图方向一致后，才进入正常 `F2F 位移预测 + 稀疏局部纠偏`。图片中的时序滤波只在固定候选内部融合，不能在未解决方向/镜像时平均候选。

正常导航向定位消费的是带 `instance_id`、`coordinate_space`、`registration_version`、`position/velocity`、`covariance 或 candidate_regions`、`fresh/age/status` 的结果。定位为 `ambiguous/lost/过期` 时，路线相关执行暂停；恢复成功或注册版本变化后重新规划。真实输入仍不在当前设计/实验阶段执行。

## 2026-09-23 P0 多帧基础契约断点

多帧实验已落地最小基础层，但尚未改变当前导航兼容链路：`MultiFrameEvidence` 保存不可变帧与位移，`MotionGate` 区分 moving/stationary/unknown，`EvidenceWindow` 提供有界关键帧和 segment version。当前 `HybridLocalizationController`、正式导航页和 `VisualLocalTracker` 仍按既有单帧注册/F2F 逻辑运行。

验证：多帧基础测试和现有 displacement/frame-displacement 测试共 `18 passed`；segment 切换回归已覆盖；尚无方案 A/B、rolling submap、全局多帧注册或实机验证。下一步应先实现有界局部拼图和重建测试，避免直接把大画布拼接器接入首帧定位。

## 2026-09-23 多帧定位与导航 observation 实现断点

已实现 rolling submap、A/B 实验策略、位置状态估计、协调状态机、session、归档和 `NavigationLocalizationAdapter`。导航适配器只返回带 instance/version/位置/速度/协方差的 observation，并在状态不是 fresh confirmed 或结果过期时置为不可执行；它没有调用路径执行或输入设备。正式导航兼容 tracker 仍未替换。

历史快照：当时相关测试为 `54 passed`，尚未完成真实 native reference 的多帧注册回放。该结论已被 schema 3 archive/replay 与自动方向收口替代；错误证据仍必须停在 ambiguous/collecting，不得由滤波器强行确认，真实地图阈值仍需校准。

## 2026-09-23 多帧全局定位实验闭环完成

最新权威状态：多帧链路已在 PoE2 数据采集测试台完整实现，但没有替换本文件前部描述的正式 hybrid tracker。

实验调用链为：

```text
Qt timer
 -> capture + wall/observed/raw evidence
 -> MotionGate + bounded EvidenceWindow + RollingSubmap
 -> one native memory anchor per recovery revision
 -> async Strategy A / Strategy B registration
 -> version-fenced confirmation
 -> visual F2F tracking + state estimator
 -> DEGRADED after one failure
 -> RECOVERING only after bounded consecutive failures
 -> NavigationLocalizationAdapter (observation only)
```

已确认的代码不变量：

- native terrain 是唯一定位交换坐标；手工 profile 方向不参与 anchor/reference。
- 人物移动量为墙体视觉位移经确认相似变换后的负值。
- 静止帧不增加关键帧、不重复注册、不误触发恢复。
- 注册期间位移不丢失；换图、恢复、证据窗口或 segment 变化会拒绝旧 worker 结果。
- 定位不 fresh、歧义、丢失、过期或版本不符时，导航 observation 必须不可执行。
- 当前没有路线执行、Xbox、键鼠、Host 或 LAN 副作用。

验证结果：此前聚焦回归 `261 passed`，随后补充自动方向、registration validator、local corrector、schema 3 replay 和 typed boundary；当前包含全部 PoE2 实验、页面、组合、架构和位移回归的聚焦集合为 `282 passed`，编译、探针入口和 diff 检查通过。全仓最终结果为 `744 passed, 2 skipped, 4 failed`，失败仅为既有 PathFinder 行为冲突三项和当前环境缺少 `pydirectinput` metadata 一项。真实多帧 PoE2 数据尚未按新 archive schema 采集，因此真实 A/B 精度、P50/P95、性能和恢复频率仍未验证；下一步必须在测试台分别启用 A、B 和 A+B 采集移动序列，显式保存实验，再做调优集/留出集分离校准。实机完成前不得把 covariance 当成已标定统计置信度，也不得把实验 factory 接入正式自动导航执行。
