"""
详细日志记录系统
记录所有参数、步骤和处理细节
"""

import logging
import os
from datetime import datetime
import json
import cv2
import numpy as np

def setup_detailed_logging():
    """设置详细日志记录"""
    # 创建logs目录
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # 生成日志文件名
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = f"log_detailed_{timestamp}.txt"
    log_path = os.path.join(log_dir, log_filename)
    
    # 配置日志
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_path, encoding='utf-8'),
            logging.StreamHandler()  # 同时输出到控制台
        ]
    )
    
    logger = logging.getLogger(__name__)
    
    # 记录系统信息
    logger.info("=" * 80)
    logger.info("详细日志记录系统启动")
    logger.info(f"日志文件: {log_path}")
    logger.info(f"启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 80)
    
    return logger, log_path

def log_system_info(logger):
    """记录系统信息"""
    logger.info("--- 系统信息 ---")
    import platform
    import sys
    
    logger.info(f"操作系统: {platform.system()} {platform.release()}")
    logger.info(f"Python版本: {sys.version}")
    logger.info(f"工作目录: {os.getcwd()}")
    
    try:
        import cv2
        import numpy as np
        import PySide6
        logger.info(f"OpenCV版本: {cv2.__version__}")
        logger.info(f"Numpy版本: {np.__version__}")
        logger.info(f"PySide6版本: {PySide6.__version__}")
    except ImportError as e:
        logger.error(f"导入库失败: {e}")

def log_project_structure(logger):
    """记录项目结构"""
    logger.info("--- 项目结构 ---")
    
    for root, dirs, files in os.walk("."):
        level = root.replace(".", "").count(os.sep)
        indent = " " * 2 * level
        logger.info(f"{indent}{os.path.basename(root)}/")
        subindent = " " * 2 * (level + 1)
        for file in files:
            logger.info(f"{subindent}{file}")

def log_module_details(logger):
    """记录模块详细信息"""
    logger.info("--- 模块详细信息 ---")
    
    # 记录core模块
    logger.info("core模块:")
    core_dir = "core"
    if os.path.exists(core_dir):
        for file in os.listdir(core_dir):
            if file.endswith('.py'):
                filepath = os.path.join(core_dir, file)
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                    line_count = len(content.split('\n'))
                    logger.info(f"  {file}: {line_count} 行")
                    
                    # 记录类和函数
                    import ast
                    try:
                        tree = ast.parse(content)
                        classes = [node.name for node in tree.body if isinstance(node, ast.ClassDef)]
                        functions = [node.name for node in tree.body if isinstance(node, ast.FunctionDef)]
                        
                        if classes:
                            logger.info(f"    类: {classes}")
                        if functions:
                            logger.info(f"    函数: {functions}")
                    except SyntaxError:
                        logger.warning(f"    无法解析 {file} 的语法")
    
    # 记录gui模块
    logger.info("gui模块:")
    gui_dir = "gui"
    if os.path.exists(gui_dir):
        for file in os.listdir(gui_dir):
            if file.endswith('.py'):
                filepath = os.path.join(gui_dir, file)
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                    line_count = len(content.split('\n'))
                    logger.info(f"  {file}: {line_count} 行")
                    
                    # 记录类和函数
                    import ast
                    try:
                        tree = ast.parse(content)
                        classes = [node.name for node in tree.body if isinstance(node, ast.ClassDef)]
                        functions = [node.name for node in tree.body if isinstance(node, ast.FunctionDef)]
                        
                        if classes:
                            logger.info(f"    类: {classes}")
                        if functions:
                            logger.info(f"    函数: {functions}")
                    except SyntaxError:
                        logger.warning(f"    无法解析 {file} 的语法")

def log_parameters(logger, recognizer):
    """记录参数信息"""
    logger.info("--- 当前参数设置 ---")
    if recognizer:
        params = recognizer.get_params()
        for key, value in params.items():
            logger.info(f"  {key}: {value}")

def log_image_processing_step(logger, step_name, img_shape, img_dtype, description=""):
    """记录图像处理步骤"""
    logger.info(f"--- {step_name} ---")
    logger.info(f"  描述: {description}")
    logger.info(f"  图像形状: {img_shape}")
    logger.info(f"  数据类型: {img_dtype}")
    if len(img_shape) == 3:
        logger.info(f"  通道数: {img_shape[2]}")
    logger.info(f"  形状信息: {img_shape}")

def log_hsv_analysis(logger, img, description=""):
    """记录HSV分析"""
    logger.info(f"--- HSV分析: {description} ---")
    if len(img.shape) == 3:
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        logger.info(f"  H通道: min={hsv[:,:,0].min()}, max={hsv[:,:,0].max()}, mean={hsv[:,:,0].mean():.2f}")
        logger.info(f"  S通道: min={hsv[:,:,1].min()}, max={hsv[:,:,1].max()}, mean={hsv[:,:,1].mean():.2f}")
        logger.info(f"  V通道: min={hsv[:,:,2].min()}, max={hsv[:,:,2].max()}, mean={hsv[:,:,2].mean():.2f}")

def log_feature_extraction(logger, wall_mask, fog_mask, combined_mask, description=""):
    """记录特征提取结果"""
    logger.info(f"--- 特征提取结果: {description} ---")
    logger.info(f"  墙壁掩码: 非零像素数={np.count_nonzero(wall_mask)}, 形状={wall_mask.shape}")
    logger.info(f"  迷雾掩码: 非零像素数={np.count_nonzero(fog_mask)}, 形状={fog_mask.shape}")
    logger.info(f"  组合掩码: 非零像素数={np.count_nonzero(combined_mask)}, 形状={combined_mask.shape}")

def log_displacement_calculation(logger, displacement, quality, description=""):
    """记录位移计算结果"""
    logger.info(f"--- 位移计算: {description} ---")
    if displacement is not None:
        dx, dy = displacement
        logger.info(f"  位移: dx={dx:.2f}, dy={dy:.2f}")
        logger.info(f"  质量: {quality:.4f}")
        logger.info(f"  位移幅度: {np.sqrt(dx**2 + dy**2):.2f}")
    else:
        logger.info(f"  位移: None (计算失败)")
        logger.info(f"  质量: {quality:.4f}")

def log_stitching_status(logger, stitcher, description=""):
    """记录拼接状态"""
    logger.info(f"--- 拼接状态: {description} ---")
    stats = stitcher.get_statistics()
    for key, value in stats.items():
        logger.info(f"  {key}: {value}")

def log_final_summary(logger, log_path):
    """记录最终总结"""
    logger.info("=" * 80)
    logger.info("详细日志记录完成")
    logger.info(f"日志文件: {log_path}")
    logger.info(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 80)

# 全局logger实例
logger_instance = None
log_file_path = None

def get_logger():
    """获取logger实例"""
    global logger_instance, log_file_path
    if logger_instance is None:
        logger_instance, log_file_path = setup_detailed_logging()
    return logger_instance

def get_log_file_path():
    """获取日志文件路径"""
    global log_file_path
    return log_file_path