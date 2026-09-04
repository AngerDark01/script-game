# auto_modules

## 虚拟手柄工作台

在 Windows 10/11 上，`main.py` 现在会以管理员权限启动统一工作台，并在顶部提供 `🎮 虚拟手柄` 页面。它会复用独立的 C# Host 来提供两个 Xbox 360 XInput 虚拟手柄：

- Controller 1 / Controller 2 有独立配置，分别用 F7 / F8 启动或暂停；F9 会紧急重置两个手柄。
- 按键通过下拉列表配置，鼠标绑定始终通过鼠标下拉列表配置；暂停、关闭和重置时不会拦截已绑定输入。
- 自动化模块可通过 `core.actions.VirtualGamepadActionAdapter` 与页面同时连接同一个 Host，向 Controller 1 或 2 发送按钮、摇杆、扳机和重置信号。
- 关闭工作台时会先确认两个控制器 reset/pause；由工作台启动的 Host 会随之安全结束。

启动命令：

```powershell
cd D:\ACloud\auto_modules
D:\ACloud\.venv\Scripts\python.exe main.py
```

首次使用前需要安装已签名的 ViGEmBus 驱动；本项目不会使用任何第三方项目自带的未知安装包。

实时小地图拼接系统

## 项目简介
基于计算机视觉的实时游戏地图重建系统，支持火炬之光、流放之路等ARPG游戏。

## 核心特性
- ✅ 相位相关算法 - 快速精确的位移计算
- ✅ HSV颜色分割 - 智能识别地图墙壁
- ✅ 实时拼接 - 边玩边构建完整地图
- ✅ 人物追踪 - 实时显示位置和视野
- ✅ 高性能 - 优化的多线程架构

## 项目结构
```
auto_modules/
├── core/               # 核心算法模块
│   ├── capture.py      # 屏幕捕获
│   ├── recognizer.py   # HSV识别与二值化
│   ├── stitcher.py     # 地图拼接（相位相关）
│   └── tracker.py      # 人物位置追踪
├── gui/                # 图形界面模块
│   ├── main_window.py  # 主窗口
│   ├── overlay.py      # 区域选择覆盖层
│   └── widgets.py      # 自定义组件
├── utils/              # 工具模块
│   └── config.py       # 配置管理
├── main.py             # 程序入口
└── requirements.txt    # 依赖列表
```

## 安装依赖
```bash
pip install -r requirements.txt
```

## 使用说明
1. 运行程序：`python main.py`
2. 点击"画框选择区域"，在游戏小地图上画框
3. 点击"开始监控"，开始实时拼接
4. 玩游戏时自动构建完整地图

## 算法说明
- **位移计算**：OpenCV相位相关（cv2.phaseCorrelate）
- **特征提取**：HSV颜色空间分割 + Canny边缘检测
- **拼接策略**：加权融合避免硬边缘
- **性能优化**：控制帧率10fps，处理时间<50ms

## 系统要求
- Python 3.8+
- Windows/Linux/Mac
- OpenCV 4.5+
- PySide6
