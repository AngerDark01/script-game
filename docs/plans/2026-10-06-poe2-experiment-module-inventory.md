# PoE2 实验页模块盘点与迁移映射

## 当前单体入口

文件：`src/auto_modules/ui/modes/poe2_live_terrain/capture_test_page.py`

当前约 6227 行，方法可按以下职责分组：

| 行为组 | 代表方法 | 目标模块 |
| --- | --- | --- |
| 页面/UI | `_build_ui`、`_render_*`、`_set_preview`、`_show_error` | `ui/modes/.../experiment_panel.py` |
| 地图/监控基础 | `initialize_session`、`capture_map`、`reset_session` | 现有正式组合 + 实验 façade |
| 双人视觉 | `_compute_dual_first_frame`、`_start_dual_motion`、`_tick_dual_motion`、`_drain_dual_motion_worker` | `experimental/multiplayer` |
| 恢复 | `_request_live_follow_reanchor`、`_schedule_live_follow_recovery_retry`、`_claim_dual_recovery` | `experimental/recovery` |
| 跟随 | `start_follow_experiment`、`_tick_follow_experiment_impl`、`_render_follow_overlay` | `experimental/follow` |
| 目标来源 | `_on_follow_map_click`、实时角色目标、双人目标 | `experimental/follow/target_sources.py` |
| 移动探针 | `start_program_move_probe`、`_tick_program_move_probe`、`stop_program_move_probe` | `experimental/probes` |
| 双人同目标 | `start_dual_target_experiment`、`_tick_dual_target_experiment_impl` | `experimental/probes/dual_target_probe.py` |
| 多帧/混合实验 | `start_hybrid_localization`、`start_multiframe_localization`、对应 tick | `experimental/localization` |
| 输出 | `ProgramFollowOutput` 绑定、release/stop | `experimental/adapters/gamepad_adapter.py` |
| 诊断 | `_append_session_log`、`_log_program_probe_diagnostics`、证据保存 | `experimental/diagnostics` |

## 共享状态盘点

第一阶段重点迁移以下状态：

- session/token：跟随、双人 worker、恢复 worker 的 generation 和 session id；
- map context：snapshot、source size、transform、map identity；
- visual state：latest state、captured timestamp、role observations、last accepted positions；
- recovery state：pending、episode active、retry owner、backoff、last recovery time；
- output state：program roles、lease、armed roles、last command、release reason；
- diagnostics：tick count、attempt count、frame count、elapsed metrics、snapshot references。

## 不允许直接迁移的内容

- Qt 控件引用；
- `QTimer.singleShot`；
- Windows foreground/window lookup；
- 虚拟手柄 Host 调用；
- 页面按钮文本和标签更新；
- PoE2 运行数据和截图缓存。

这些内容必须通过 port 或 UI callback 留在 adapter/composition 层。

## A0 完成检查

- [x] 总任务断点文档创建；
- [x] A0→C5 实施计划创建；
- [x] 页面方法和职责初步映射；
- [x] 共享状态类别列出；
- [x] 副作用边界列出；
- [x] 使用 CodeGraph 补齐关键调用路径：`_tick_dual_motion` → `_maybe_resume_dual_follow_after_relocalization` → `start_follow_experiment` → `_tick_follow_experiment` → `_tick_follow_experiment_impl` → `_request_live_follow_reanchor`；动态边界包括双人 worker、截图、识别器和窗口查找器；
- [ ] 为 A1 建立第一批失败测试；
- [ ] 提交 A0 检查点。
