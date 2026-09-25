# PoE2 局部拼图形状配准断点

最后更新：2026-09-21（离线实验闭环完成，实机配对样本被拒绝）

## 当前目标

在实验台中验证“局部拼图对完整原生地形”的二维形状配准，自动恢复：

```text
旋转角度 + 统一比例 + 全局平移 + 可选水平镜像
```

墙体粗细不同不能影响结果。传送门、文字和少量拼图污染允许作为离群噪声存在。正确变换确定后，旋转角就是地图方向，局部人物坐标通过同一变换得到全局位置。

## 强制边界

- 当前阶段只允许修改 `tools/debug`、`tests/poe2_live_terrain`、实验输出和本断点文档。
- 不修改 `src/`、正式 PoE2 定位 runtime、第一页绘图模式或 profile。
- 不发送 Xbox、键盘、鼠标、Host 或 LAN 输入。
- 候选低于门槛或存在近似并列时必须返回 `rejected` / `ambiguous`，不能把最高候选写成已确认方向。
- 实验通过至少两个地图实例前，不下沉通用引擎。

## 已确认设计

```text
stitched_map.png                terrain.png
       |                            |
       +-- 墙体厚度归一化/骨架化 --+
                     |
          GeneralizedHoughGuil
                     |
       位置/角度/比例/镜像候选
                     |
    对称 trimmed Chamfer 容噪验证
                     |
       候选分差与多块一致性判断
                     |
       confirmed / ambiguous / rejected
```

连续角度实验已经证明：`GeneralizedHoughGuil` 不能在当前单像素、稀疏且可能断裂的墙体骨架上稳定恢复任意角度。它保留为原始实验函数，但不再是端到端注册的唯一候选来源。当前实现使用：

```text
全角度 / 全比例轮廓重叠粗搜索
  -> 每个比例保留独立候选，避免小比例垄断
  -> 对称 trimmed Chamfer 重新评分
  -> 最低分数 + 不同假设分差决定接受或拒绝
```

设计文档：

- `docs/plans/2026-09-21-poe2-partial-map-registration-design.md`
- `docs/plans/2026-09-21-poe2-partial-map-registration-implementation-plan.md`

## 当前实机数据

最新严格配对会话：

```text
data/poe2_live_terrain_test/stitching_sessions/
  20260921-144659-321287-a6ccb4c6767e/
```

该目录同时包含 `stitched_map.png`、`terrain.png` 和 `session.json`。清单已确认：

```text
terrain.status: available
terrain.instance_id: MapFlotsam:BB9AA6DE
terrain size: 3382 x 1863
frames: 228
successful matches: 216
```

因此“缺少同会话地形”的数据阻塞已经解除。

局部拼图：

```text
data/poe2_live_terrain_test/stitching_sessions/
  20260921-121018-260622-a6ccb4c6767e/
```

候选原生地图：

```text
data/poe2_live_terrain_test/samples/
  20260921-090840-957906-MapFlotsam-5C048CD0/terrain.png
```

两次截图的房间外轮廓、右下环形结构和人物位置一致，可用于候选实验；但最新 stitching session 自身记录 `terrain.status=missing`，所以报告必须明确地形来自外部历史样本，不能把实例配对视为正式契约。

已知拼图证据：

```text
frames: 217
successful matches: 216
mean match quality: 0.737722
trajectory points: 107
trajectory large steps: 44.82 px, 57.07 px
wall pixels: 19841
coarse-block region: approximately x=298..367, y=505..525
```

## 已否定方案

旧离线探针把角度、镜像、比例和平移直接联合穷举，并用完整拼图做刚性 Chamfer。当前首选为：

```text
angle: 94 degrees
reflection: false
scale: 0.16
score: 0.462466
```

该候选低于 `0.72` 旧门槛且叠图不成立，不是已确认方向。正式 runtime 的 `cv2.matchTemplate` 也只使用人工 profile 方向，不能自动解决本问题。

## 环境能力

当前虚拟环境：

```text
OpenCV: 4.13.0
createGeneralizedHoughGuil: available
createGeneralizedHoughBallard: available
estimateAffinePartial2D: available
distanceTransform: available
findTransformECC: available
ximgproc.thinning: unavailable
scikit-image: unavailable
```

因此骨架化使用标准 OpenCV 形态学实现，实验阶段不新增大型依赖。

## 当前实施状态

```text
[done] 方案讨论与边界确认
[done] 设计文档
[done] TDD 实施计划
[done] 独立断点文档
[done] 实验 contracts 与合成测试（21 passed）
[done] 厚度无关骨架化（粗墙骨架对薄墙覆盖 95.65%）
[done] 人物锚点的旋转/比例/平移坐标变换
[done] GeneralizedHoughGuil 根因实验：离散角可用，任意角度不稳定
[done] 任意角度 / 比例轮廓重叠候选生成与尺度覆盖
[done] trimmed Chamfer 候选验证
[done] 歧义拒绝与完整实验编排
[done] stitching session / terrain 只读加载
[done] JSON 报告与候选叠图
[done] 当前 MapFlotsam 外部历史样本运行
[done] 当前结论：保持实验状态，需要真正同会话配对数据
```

## 当前测试断点

实验代码：

```text
tools/debug/poe2_partial_map_registration_probe.py
```

当前已实现：

- `HoughConfig`
- `RegistrationConfig`
- `RegistrationCandidate`
- `binary_mask(...)`
- `morphological_skeleton(...)`
- `normalize_shape(...)`
- `project_point(...)`
- `generate_hough_candidates(...)` 第一版

测试文件：

```text
tests/poe2_live_terrain/test_partial_map_registration_probe.py
```

最近一次探针测试：

```powershell
& D:/ACloud/.venv/Scripts/python.exe -m pytest tests/poe2_live_terrain/test_partial_map_registration_probe.py -q
```

2026-09-21 实测结果：

```text
21 passed
```

失败样例的真值：

```text
global center: (286, 194)
angle: 35 degrees
scale: 0.8
clutter: one unrelated line + one unrelated rectangle
```

原始 GHT 没有生成同时满足三项的候选。新的轮廓重叠候选生成 + Chamfer 验证在相同 `35 degrees` 合成契约上已经通过，并覆盖墙体粗细差异、结构噪声、镜像、重复房间歧义和小比例细线保持。

## 已验证与未验证证据

已验证：

- 输入 `0 degrees` 时，可得到约 `0 degrees / 0.79 scale`，中心准确。
- 输入 `45 degrees` 时，可得到约 `45 degrees / 0.80 scale`，中心约为 `(286, 195)`。
- 输入 `90 degrees` 时，可得到约 `90 degrees / 0.79 scale`，中心准确。
- 粗墙与薄墙先做原始二值连通域过滤、再骨架化后，骨架覆盖率达到 `95.65%`。
- `0/60/235` 三值渲染图会自动提取 `235` 高亮墙体，不把 `60` 灰色已知区域误当墙体。
- 旋转后的单像素骨架再次归一化不会删除短斜线片段。
- 小比例缩放前会临时加粗细线，避免 `1572` 个骨架像素在 `0.12` 倍时退化成仅 `16` 个像素。
- 候选生成对每个比例保留独立假设，避免错误小比例占满候选列表。
- 报告保存全部候选数值，只为前 6 名生成叠图；输入路径和 SHA-256 可追溯。

未验证 / 当前失败：

- 原始 GHT 对 `15 / 30 / 35 / 60 degrees` 不稳定；`Xi`、`AngleEpsilon`、Canny 阈值和标准线宽扫描均未恢复稳定真值。
- 当前 MapFlotsam 拼图会话自身记录 `terrain.status=missing`，使用的是显式传入的外部历史 terrain，实例一致性没有契约保证。
- 当前外部历史配对在 `0.10..1.20` 比例范围没有形成独立高分峰值，不能确认方向或位置。
- 尚未用两个真正同会话、同时保存 `stitched_map.png` 与 `terrain.png` 的地图实例验证。

## 当前实机实验结果

最新同会话配对结果：

```text
output: shape-registration-20260921-paired-144659-v1
accepted: false
reason: low_score
angle: 40 degrees
scale: 0.12
reflected: false
center: (786.5, 790.5)
score: 0.501965
score margin: 0.053991
forward coverage: 0.601023
reverse coverage: 0.480903
```

分差已经超过 `minimum_margin=0.05`，但得分仍低于 `minimum_score=0.68`，所以 `40 degrees` 只能称为第一候选，不能称为已确认方向。当前数据不需要重新采集；下一阶段回到算法侧，分析局部拼图中真实墙体、探索边界、传送门粗块和长斜线的语义差异。

### 2026-09-21 人工判图复核

已直接对照本会话的 `raw.png`、`wall_mask.png`、`stitched_map.png`、`stitched_map_overlay.png` 和 `terrain.png`，并对 8 个近圆孔候选做 8 方向红/青叠图。人工结论：

- `40 degrees / scale 0.12 / center (786.5, 790.5)` 是局部巧合，不应继续作为人工位置假设。
- 局部拼图中央圆环直径约 `80..90 px`，当前帧圆环直径约 `45 px`；完整地形近圆孔直径约 `35..94 px`。按同一结构估算，拼图到地形的合理比例优先为 `0.4..0.9`。
- 在 `0.4..0.9`、每 `5 degrees` 的受限搜索中，最好结果仅为 `center (1106.5, 697.5) / angle 0 / scale 0.4 / score 0.208844 / margin 0.012477`，且肉眼没有连续墙线重合，仍应拒绝。
- 左上圆孔 `(约 438,436)` 的 `135 degrees` 假设只能对齐圆孔相对位移，圆孔左上方主墙轮廓明显不同，不能确认。
- 中右部和最右部区域在整体稀疏程度上更接近局部拼图，但逐块旋转后同样没有形成“圆孔 + 长墙 + 第二边界”三项同时吻合的候选。
- 水平镜像的人工复核也没有出现连续重合。现有证据不能诚实地给出唯一位置或唯一方向。
- `stitched_map_overlay.png` 的轨迹共有 `70` 个点，最大相邻步长 `182.33 px`，`49` 步大于 `20 px`、`17` 步大于 `50 px`。这些跳变可能包含采样间隔，也可能包含错误拼接；在没有逐帧时间和匹配质量对应关系前，不能直接把整张拼图视为无误真值。

人工候选的保守排序仅用于下一轮局部实验，不表示定位成功：

```text
1. 地图中右部 / 最右部稀疏通道区域，方向约 45..135 degrees，低置信。
2. 左上圆孔 (约 438,436) 邻域，方向约 135 degrees，已因主墙不吻合而降级。
3. 当前算法 (786.5,790.5) / 40 degrees / 0.12，排除。
```

人工叠图和合理比例复核输出：

```text
data/poe2_live_terrain_test/probe_results/manual-visual-analysis-20260921/
data/poe2_live_terrain_test/probe_results/manual-plausible-scale-20260921-v1/
```

主要输出：

```text
data/poe2_live_terrain_test/probe_results/
  shape-registration-20260921-overlap-v1/
  shape-registration-20260921-overlap-v2/
  shape-registration-20260921-overlap-v3/
  shape-registration-20260921-overlap-v4-wide-scale/
```

迭代结论：

- `v1` 暴露小比例最近邻缩放导致骨架像素折叠，结果为 `ambiguous`，不可使用。
- `v2` 修复细线保持后为 `low_score`，证明旧高覆盖率主要来自尺度退化。
- `v3` 加入尺度覆盖和包围区域反向 Chamfer 后，最高分仅 `0.471750`。
- `v4-wide-scale` 将比例扩大到 `0.10..1.20`，仍为 `low_score`；最高候选为 `45 degrees / scale 0.10 / reflected=false / score 0.481288 / margin 0.007693`，不是已确认方向。
- 额外 8 方向逐比例诊断中，最高也只有约 `0.5525`，随后随比例增大整体下降，没有真实匹配应有的清晰峰值。

## 下一恢复动作

下一次不要继续调低分数门槛。严格按下面顺序恢复：

```text
1. 使用最新严格配对会话，不再使用外部历史 terrain 调参。
2. 先按轨迹逐帧检查拼接增量，定位 `>50 px` 跳变对应的帧、匹配分数和地图写入，确认拼图是否含错误拼接。
3. 分别标记局部拼图中的真实墙体、探索边界、传送门粗块和长斜线，确认哪些结构在完整 terrain 中有对应物。
4. 用当前单帧 `raw/wall_mask` 做基准，验证两种图之间是否需要非等比缩放、轴交换或镜像；在变换模型正确前，不继续全图调分。
5. 为候选评分增加结构类别或稳定结构掩码，避免所有白线等权参与 Chamfer。
6. 只围绕人工低置信区域生成局部精配准叠图；不再围绕已排除的 `40 degrees / 0.12 / (786.5,790.5)` 调参。
7. 保持 `minimum_score=0.68` 和 `minimum_margin=0.05`，算法通过前不降低门槛。
8. 当前实例通过后再采集第二个地图实例，验证多块一致性；两个实例均通过前不下沉 `core`。
```

骨架化的第一版失败原因已经确定：骨架化后再按连通分量面积过滤会删除薄斜线段；现已改为先在原始二值墙图上过滤小分量，再骨架化。这个顺序不能退回。

## 恢复时禁止事项

- 不把当前 `94 degrees / 0.16 scale / 0.462466 score` 旧结果称为正确方向。
- 不根据最高票强行输出 `confirmed`。
- 不为通过测试把任意角度契约静默缩成 45 度倍数；必须先用游戏数据证明方向确实离散。
- 不为通过外部历史配对样本调低 `minimum_score` 或 `minimum_margin`。
- 不在本阶段修改正式 runtime、第一页绘图模式或 profile。
- 不启动实际输入、Host 或 LAN 同步。

## 2026-09-22 实机玩家位置只读探针

已在用户保持运行的 PoE2 实例上完成一次同会话地形和玩家位置交叉验证。实验探针：

```text
tools/debug/poe2_player_memory_probe.py
```

本次结果文件：

```text
data/poe2_live_terrain_test/memory_probes/player-memory-probe-20260922-112805.json
data/poe2_live_terrain_test/memory_probes/player-memory-probe-20260922-113502.json
data/poe2_live_terrain_test/memory_probes/player-memory-probe-latest.json
data/poe2_live_terrain_test/memory_probes/terrain-latest.npz
data/poe2_live_terrain_test/memory_probes/terrain-latest.json
```

验证结果：

- 进程 `PathOfExile.exe`，PID `23496`，客户端构建 `8A102202FEA9B2498EA95BAE`。
- 当前区域 `MapFlotsam`，实例 `MapFlotsam:BB9AA6DE`，地形尺寸 `3382 x 1863`。
- 本地玩家实体元数据为 `Metadata/Characters/StrDex/StrDexFourb`，组件表解析到 `13` 个组件，其中包含 `Render`。
- `Render + 0x138` 连续读取 10 次均稳定为世界坐标 `(4190.2173, 4635.8696, -594.7950)`。
- 按当前契约 `grid_x = world_x * 23 / 250`、`grid_y = world_y * 23 / 250`，得到网格位置 `(385.50, 426.50)`，位于地形边界内。
- 同次快照的 `instance_id`、`area_id`、`area_hash`、宽高全部匹配；没有发送输入，也没有写入游戏进程。

这证明“直接从内存读取玩家世界坐标并映射到 native terrain grid”在当前客户端和当前实例上可行。仍未证明的是跨地图、切图瞬间、坐标原点变化和多人实体选择；因此本探针只保留在 `tools/debug`，暂不修改 `src/` 或正式 PoE2 runtime。`Render` 组件地址只作为本次诊断记录，不应硬编码进业务层。

每完成一个可验证阶段，立即更新本文件中的实施状态、最近测试结果、已否定假设和下一恢复动作。
