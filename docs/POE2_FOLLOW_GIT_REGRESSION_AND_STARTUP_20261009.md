# 跟随启动等待与Git差异定位

## 用户契约

点击开始后提供完整10秒切回PoE2窗口的时间。Vision/Control可以提前初始化和处理，但不得提前发送非零移动。跟随无总时长限制，用户显式停止才结束session。重建与定位异常应能追溯原始原因。

## Git对照

- 成功参考`a3070ea`：2026-10-07 01:46，旧实验跟随实现，页面常量为6秒，并非10秒。
- `f830537`：引入模块化engine/UI adapter；`97aefca`：生命周期清理；当前HEAD=`6068c97`。
- HEAD的engine.poll只有读取Vision→转Control→读snapshot→交output，没有当前worker watchdog/rebuild扩展。
- 工作树engine扩展增加了watchdog、异步rebuild、代际和receipt逻辑；本次确认的时序缺陷位于这些尚未提交修改。因此不能用一个已提交SHA解释所有现状，也不能直接Git bisect自动测实机：真实输入尚未授权给本轮，历史提交不包含当前缺陷代码。
- 本轮未reset、未回退、未提交全工作树，保留其他改动。

## 已确认与复现的三个缺陷

1. 读队列前判stall：父侧延迟3秒，两个队列已有最新结果，原poll仍先生成worker_stall:vision,control。若装配rebuild factory，会先回中并开始替换本来仍有结果的worker。
2. 换句柄前捕获旧handle：completed rebuild提交新句柄后，本次poll仍读取前面捕获的旧handle；真实旧queue若已dispose会产生queue_closed，再影响恢复。
3. 跨worker提前缩短启动窗：Control先产生seed snapshot，Vision首次采集尚未完成；原代码依据last_snapshot非空把两个worker都切为2秒门，Vision应有的10秒启动期失效。离线3秒Vision未完成场景复现stalled。

前两项修复前2 failed，第三项单独修复前1 failed。修复后同样场景通过。这证明源码缺陷真实存在，但03:07/03:08没有完整原始异常和进展年龄，不能断言两次实测就是这些缺陷触发。

## 修改后的执行次序

```text
点击开始 → 异步创建Control/Vision/Output
  → 输出actor启动10秒非零闸门，提前建立零租约/心跳
  → 页面启动完成后显示持续倒计时，不阻塞Qt
每次poll：
  收集完成的rebuild
  → 捕获本代有效handles
  → rebuild仍进行中：不读退休队列
  → 否则读取Vision/Control最新结果，刷新各自进展
  → 输出快照仍受真实10秒闸门控制
  → 最后按每个worker的首次结果状态检查10s/2s门
异常：
  原始error/traceback/PID/exitcode → first_fault持久保留
  → 进展年龄和attempt分类 → 回中/重建begin
  → rebuild completed（新handle身份、epoch）或错误
```

UI显示优先级：10秒切回游戏提示（附当前故障摘要）→worker故障/重建→当前snapshot状态。倒计时按秒变化记录，worker日志按状态变化记录，不每帧刷屏。

## 验证与边界

- 聚焦poll时序、page启动/倒计时、10秒输出边界、既有port/composition：38 passed in 4.91s。
- 输出边界实际检查9999ms仍无非零写入/位移receipt，10000ms才放行。
- 原始调用栈在后续stall摘要覆盖last_error后仍保留并落盘。
- 没有全量回归，没有游戏输入、内存读取、Host连接或自动重启。
- 需要重启工作台后代码才对运行中的GUI生效；本轮未自动重启。
- 仍未确认两次实测最初的worker异常、控制计算长尾或IPC停滞；新日志用于补足该证据，不拿离线复现冒充实机成功。
