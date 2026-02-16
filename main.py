"""
实时小地图拼接系统 - 程序入口

使用方法:
    python main.py

功能:
    1. 画框选择游戏小地图区域
    2. 实时监控并拼接地图
    3. HSV颜色识别 + 相位相关算法
    4. 高性能实时处理
"""

import sys
from PySide6.QtWidgets import QApplication
from gui import MainWindow


def main():
    """主函数"""
    print("=" * 60)
    print("实时小地图拼接系统")
    print("=" * 60)
    print()
    print("算法: 相位相关法 (cv2.phaseCorrelate)")
    print("特征: HSV颜色分割 + 二值化处理")
    print("性能: 10fps 实时处理")
    print()
    print("=" * 60)
    print()
    
    # 创建应用
    app = QApplication(sys.argv)
    
    # 创建主窗口
    window = MainWindow()
    window.show()
    
    print("√ 主窗口已启动")
    print()
    print("使用步骤:")
    print("  1. 点击'画框选择区域'按钮")
    print("  2. 在游戏小地图上拖动鼠标画框")
    print("  3. 按 ENTER 确认选择")
    print("  4. 点击'开始监控'启动拼接")
    print("  5. 玩游戏，自动构建完整地图!")
    print()
    print("=" * 60)
    
    # 运行应用
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
