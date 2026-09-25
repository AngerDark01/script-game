# PoE2 启动局部地图拼接采集设计

## 目标

把现有 PoE2 数据采集测试窗口扩展为独立绘图实验台。用户进入地图后开始监控并正常移动，程序利用连续小地图帧拼出一块更大的局部地图；该结果只用于下一阶段验证方向、比例和全局位置，不替代程序直接获取的完整地形。

## 架构边界

```text
PoE2 capture evidence
  raw / processed / feature / player center
            |
            v
PoE2 stitching session adapter
  lifecycle / layer adaptation / trajectory / snapshots
            |
            v
core.mapping.MapStitcher
  keyframe + F2F registration / quality gate / weighted merge
            |
            v
PoE2 capture monitor window
  controls / previews / statistics / explicit archive command
```

- `core.mapping` 保持游戏无关，不加入 PoE2 术语或规则。
- PoE2 适配层只组合底层能力并拥有自己的会话状态；UI 不读取或修改 stitcher 私有字段。
- 原绘图模式业务页面不修改。
- 正式 PoE2 定位 runtime 不接入实验拼图。
- 本阶段不执行输入、导航、Host 或 LAN 操作。

## 数据与状态

拼图会话包含 `idle/running/paused` 三态。`start()` 从 idle 或 paused 进入 running；`pause()` 停止消费新帧；`reset()` 创建全新 stitcher 并清空轨迹、当前结果和统计。

每帧从同一个 `CaptureEvidence` 派生：

- `match_mask`：清理后的 matcher feature，用于关键帧和 F2F 位移估计；
- `save_mask`：稳定地形边界层，用于落图；
- `fog_mask`：本阶段使用同尺寸零掩码，不把 PoE2 蓝色圆环写入局部地图；
- `player_position`：profile 配置中心点，单人模式不识别人形。

只有底层返回成功且统计表明帧通过落图质量门时，UI 才更新拼图结果。轨迹保存 stitcher 的当前画布位置，用于展示实际的相对移动路径。

## UI

现有截图监控窗口保持原始图、预处理图、匹配特征和完整地形浏览能力，并增加：

- 开始绘图、暂停绘图、重置地图、保存拼图实验；
- 右侧大幅拼接地图主视图；
- 当前相对位置与轨迹；
- 总帧数、成功/失败匹配、匹配率、当前质量、关键帧切换、低质量跳过数。

监控定时器继续负责“一帧只截取一次”。绘图开启时，同一个 evidence 先更新预览，再交给拼图会话，禁止为了拼图再次截图。

## 保存契约

显式保存命令创建独立实验目录，包含拼接地图 PNG、当前 raw/processed/feature/wall/fog、同地图实例完整 terrain 预览、轨迹与统计 JSON、profile 配置以及来源时间。没有当前 terrain 时允许保存，但 manifest 必须显式记录 missing，禁止借用其他实例。运行时默认只保存在内存，不持续落盘。

## 验收

- 原截图采集和历史浏览功能保持可用。
- 拼图开始/暂停/重置生命周期有单元测试。
- 相同帧不产生虚假位移，连续平移合成帧形成连续轨迹。
- 被拒绝帧不写入轨迹或污染地图。
- UI 测试覆盖按钮状态、主视图和统计刷新。
- 聚焦回归、架构边界、源码编译通过；全量回归只允许既有 PathFinder 失败。
