# PoE2 动态版本指纹实现计划

1. 在采集器测试中先加入未知指纹成功、AOB 缺失/歧义、已知指纹元数据冲突与缓存槽位复用的失败用例。运行 `D:/ACloud/.venv/Scripts/python.exe -m pytest tests/test_terrain_lab.py -q` 确认新用例先失败。
2. 在 `D:/ACloud/poe2-map-research/windows_capture.py` 的描述符解析处区分已知/未知版本。未知版本先做 AOB，再做结构、元数据和 guard 验证，并以本次真实指纹构造临时版本记录；绝不持久化白名单。
3. 运行采集器与会话测试；如游戏进程存在，执行 `experiments/live-terrain-preview/live_preview.py init` 的只读实测，并核对日志及会话指纹。
4. 检查正式页初始化链、错误呈现和复用会话边界；运行相关聚焦回归、编译检查，更新断点及 `CODEBASE.md`/架构迭代日志。
