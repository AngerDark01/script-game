# 架构文档独立目录

这个目录保存历史架构扫描快照，不包含源码、调试图片、地图数据或运行产物。快照中的
`core/events/types/portal|loot`、`gui/` 等路径反映迁移前结构，不再是当前权威路径。

当前权威架构请优先阅读仓库根目录的 `ARCHITECTURE_GUIDE.md`、`CODEBASE.md`、
`ITERATION_LOG.md`，以及 `src/auto_modules/features/<game>/` 下的业务域文档。

## 目录结构

```text
architecture_docs/
├── original/   # 原始英文/中英混排版本，按原项目相对路径镜像
└── zh-CN/      # 中文复刻版本，按同样相对路径组织
```

## 历史中文入口

- [中文总览](zh-CN/ARCHITECTURE_GUIDE.md)
- [中文迭代日志](zh-CN/ARCHITECTURE_ITERATION_LOG.md)
- [核心系统](zh-CN/core/ARCHITECTURE.md)
- [导航任务系统](zh-CN/core/navigation_tasks/ARCHITECTURE.md)
- [事件系统](zh-CN/core/events/ARCHITECTURE.md)
- [传送门事件包](zh-CN/core/events/types/portal/ARCHITECTURE.md)
- [GUI 总览](zh-CN/gui/ARCHITECTURE.md)
- [GUI 模式](zh-CN/gui/modes/ARCHITECTURE.md)
- [导航模式拆分](zh-CN/gui/modes/navigation/ARCHITECTURE.md)
- [GUI 对话框](zh-CN/gui/dialogs/ARCHITECTURE.md)
- [工具/探针](zh-CN/utils/ARCHITECTURE.md)
- [测试架构](zh-CN/tests/ARCHITECTURE.md)

## 原文入口

- [Original Guide](original/ARCHITECTURE_GUIDE.md)
- [Original Iteration Log](original/ARCHITECTURE_ITERATION_LOG.md)
