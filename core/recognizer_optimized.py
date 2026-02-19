"""
HSV颜色识别器 - 优化版
核心优化：
1. 结合recognizer_fixed.py的修复
2. 保持与现有系统的兼容性
3. 提升性能和准确性
"""

import cv2
import numpy as np


class HSVRecognizer:
    """HSV多层识别器 - 优化版"""

    def __init__(self):
        """初始化HSV颜色范围"""
        # 墙壁层（白色/灰色）
        self.wall_hsv_min = np.array([118, 5, 54])
        self.wall_hsv_max = np.array([132, 90, 225])

        # 迷雾层（蓝灰色）
        self.fog_hsv_min = np.array([91, 174, 188])
        self.fog_hsv_max = np.array([108, 243, 255])

        # 玩家标记（绿色/黄色）
        self.player_hsv_min = np.array([40, 100, 100])
        self.player_hsv_max = np.array([80, 255, 255])

        # 开关
        self.enable_wall = True
        self.enable_fog = True

        # 形态学操作核
        self.kernel_small = np.ones((3, 3), np.uint8)
        self.kernel_medium = np.ones((5, 5), np.uint8)

        # Canny边缘检测参数
        self.edge_low = 50
        self.edge_high = 150

        # 融合权重（用于配准增强）
        self.wall_weight = 70
        self.edge_weight = 30

        # CLAHE增强
        self.clahe_enabled = True
        self.clahe_clip = 3.0        # 适度降低 (原4.0)
        self.clahe_grid = 4          # 保持细粒度
        self._clahe = cv2.createCLAHE(
            clipLimit=self.clahe_clip,
            tileGridSize=(self.clahe_grid, self.clahe_grid)
        )

        # 颜色深化参数
        self.deepen_enabled = True
        self.deepen_factor = 1.0     # 降低增益，防止过曝 (原1.2)
        self.blue_boost = 1.0        # 降低蓝色增强 (原1.1)

        # Gamma校正 (新增：压暗中间调)
        self.gamma_enabled = True
        self.gamma_value = 2       # 激进压暗 (原1.5)，确保背景足够黑

        # 透明地图模式开关
        self.transparent_mode = True
        # 透明模式下的参数
        self.trans_wall_thresh = 50 # V - S 的阈值

        # 饱和度惩罚系数 (用于 V - S * factor)
        self.trans_sat_penalty = 1.5

        # TopHat结构提取参数
        self.tophat_enabled = True
        self.tophat_kernel_size = 15
        self.tophat_strength = 4   # 稍微降低强度 (原4.0)，避免放大背景噪点

        # 饱和度过滤参数 (新增：支持蓝色地图)
        self.sat_filter_enabled = True
        self.sat_filter_thresh = 40
        self.sat_filter_radius = 0  # 0=全局过滤(白图模式), >0=仅过滤玩家周围(蓝图模式)

    def get_params(self):
        """获取当前参数"""
        return {
            # HSV
            'wall_hsv_min': self.wall_hsv_min.tolist(),
            'wall_hsv_max': self.wall_hsv_max.tolist(),
            'fog_hsv_min': self.fog_hsv_min.tolist(),
            'fog_hsv_max': self.fog_hsv_max.tolist(),
            'player_hsv_min': self.player_hsv_min.tolist(),
            'player_hsv_max': self.player_hsv_max.tolist(),

            # Switches
            'enable_wall': self.enable_wall,
            'enable_fog': self.enable_fog,
            'clahe_enabled': self.clahe_enabled,
            'deepen_enabled': self.deepen_enabled,
            'gamma_enabled': self.gamma_enabled,
            'tophat_enabled': self.tophat_enabled,
            'sat_filter_enabled': self.sat_filter_enabled,

            # Params
            'clahe_clip': self.clahe_clip,
            'clahe_grid': self.clahe_grid,
            'deepen_factor': self.deepen_factor,
            'blue_boost': self.blue_boost,
            'gamma_value': self.gamma_value,
            'tophat_strength': self.tophat_strength,
            'tophat_kernel_size': self.tophat_kernel_size,
            'trans_sat_penalty': self.trans_sat_penalty,
            'trans_wall_thresh': self.trans_wall_thresh,
            'transparent_mode': self.transparent_mode,
            'sat_filter_thresh': self.sat_filter_thresh,
            'sat_filter_radius': self.sat_filter_radius,

            # Weights
            'wall_weight': self.wall_weight,
            'edge_weight': self.edge_weight,
            'edge_low': self.edge_low,
            'edge_high': self.edge_high,
            
            # Morphological kernels
            'kernel_small_size': self.kernel_small.shape[0],  # Assuming square kernel
            'kernel_medium_size': self.kernel_medium.shape[0]  # Assuming square kernel
        }

    def set_params(self, params):
        """设置参数 (支持部分更新)"""
        # HSV Arrays
        if 'wall_hsv_min' in params: self.wall_hsv_min = np.array(params['wall_hsv_min'])
        if 'wall_hsv_max' in params: self.wall_hsv_max = np.array(params['wall_hsv_max'])
        if 'fog_hsv_min' in params: self.fog_hsv_min = np.array(params['fog_hsv_min'])
        if 'fog_hsv_max' in params: self.fog_hsv_max = np.array(params['fog_hsv_max'])
        if 'player_hsv_min' in params: self.player_hsv_min = np.array(params['player_hsv_min'])
        if 'player_hsv_max' in params: self.player_hsv_max = np.array(params['player_hsv_max'])

        # Switches
        if 'enable_wall' in params: self.enable_wall = params['enable_wall']
        if 'enable_fog' in params: self.enable_fog = params['enable_fog']
        if 'clahe_enabled' in params: self.clahe_enabled = params['clahe_enabled']
        if 'deepen_enabled' in params: self.deepen_enabled = params['deepen_enabled']
        if 'gamma_enabled' in params: self.gamma_enabled = params['gamma_enabled']
        if 'tophat_enabled' in params: self.tophat_enabled = params['tophat_enabled']
        if 'sat_filter_enabled' in params: self.sat_filter_enabled = params['sat_filter_enabled']

        # Params
        if 'clahe_clip' in params:
            self.clahe_clip = params['clahe_clip']
            self._clahe.setClipLimit(self.clahe_clip)
        if 'clahe_grid' in params:
            self.clahe_grid = params['clahe_grid']
            self._clahe = cv2.createCLAHE(
                clipLimit=self.clahe_clip,
                tileGridSize=(self.clahe_grid, self.clahe_grid)
            )

        if 'deepen_factor' in params: self.deepen_factor = params['deepen_factor']
        if 'blue_boost' in params: self.blue_boost = params['blue_boost']
        if 'gamma_value' in params: self.gamma_value = params['gamma_value']
        if 'tophat_strength' in params: self.tophat_strength = params['tophat_strength']
        if 'tophat_kernel_size' in params: self.tophat_kernel_size = params['tophat_kernel_size']
        if 'trans_sat_penalty' in params: self.trans_sat_penalty = params['trans_sat_penalty']
        if 'trans_wall_thresh' in params: self.trans_wall_thresh = params['trans_wall_thresh']
        if 'transparent_mode' in params: self.transparent_mode = params['transparent_mode']
        if 'sat_filter_thresh' in params: self.sat_filter_thresh = params['sat_filter_thresh']
        if 'sat_filter_radius' in params: self.sat_filter_radius = params['sat_filter_radius']

        # Weights
        if 'wall_weight' in params: self.wall_weight = params['wall_weight']
        if 'edge_weight' in params: self.edge_weight = params['edge_weight']
        if 'edge_low' in params: self.edge_low = params['edge_low']
        if 'edge_high' in params: self.edge_high = params['edge_high']
        
        # Morphological kernels
        if 'kernel_small_size' in params: 
            size = int(params['kernel_small_size'])
            self.kernel_small = np.ones((size, size), np.uint8)
        if 'kernel_medium_size' in params: 
            size = int(params['kernel_medium_size'])
            self.kernel_medium = np.ones((size, size), np.uint8)

    def _compute_transparency_score(self, img):
        """
        计算透明地图的特征分数 (V - S * factor) + TopHat
        用于强化灰白色线条，抑制彩色/暗色背景以及大面积高亮背景
        """
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        h, s, v = cv2.split(hsv)

        # 1. 颜色分数 (Color Score)
        # 核心公式：Score = Brightness - Saturation * Penalty
        v_int = v.astype(np.int16)
        s_int = s.astype(np.int16)
        score_color = v_int - s_int * self.trans_sat_penalty
        score_color = np.clip(score_color, 0, 255).astype(np.uint8)

        if not self.tophat_enabled:
            return score_color

        # 2. 结构分数 (Structure Score) - TopHat
        # 提取高亮细节，抑制大面积背景（无论背景是黑是白）
        # 这是解决 "白色背景导致配准失败" 的关键
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (self.tophat_kernel_size, self.tophat_kernel_size))
        tophat = cv2.morphologyEx(v, cv2.MORPH_TOPHAT, kernel)
        
        # 增强 TopHat (通常 TopHat 结果较暗)
        # 使用 convertScaleAbs 进行饱和运算，防止溢出
        tophat_boosted = cv2.convertScaleAbs(tophat, alpha=self.tophat_strength, beta=0)

        # 3. 融合
        # 取两者最小值：必须既是"灰白色"(Color)，又是"细微结构"(Structure)
        # 这样可以有效过滤掉大面积的白色背景 (它Color分高，但Structure分低)
        score_final = cv2.min(score_color, tophat_boosted)

        return score_final

    def _preprocess_for_wall(self, img):
        """
        专用预处理：墙体提取 (激进压暗，只留高光)
        """
        # 0. Gamma 压暗
        if self.gamma_enabled:
            table = np.array([((i / 255.0) ** self.gamma_value) * 255 for i in np.arange(0, 256)]).astype("uint8")
            img = cv2.LUT(img, table)

        # 1. 高斯模糊
        img_blur = cv2.GaussianBlur(img, (3, 3), 0)

        # 2. CLAHE
        if self.clahe_enabled:
            lab = cv2.cvtColor(img_blur, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            l2 = self._clahe.apply(l)
            lab = cv2.merge((l2, a, b))
            img_enhanced = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
        else:
            img_enhanced = img_blur

        # 3. Top-Hat
        if self.tophat_enabled:
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (self.tophat_kernel_size, self.tophat_kernel_size))
            tophat = cv2.morphologyEx(img_enhanced, cv2.MORPH_TOPHAT, kernel)
            img_enhanced = cv2.add(img_enhanced, tophat)

        # 4. 截断与拉伸
        try:
            min_val = np.percentile(img_enhanced, 40) # 激进截断
            max_val = np.percentile(img_enhanced, 99)
            if max_val > min_val:
                img_enhanced = np.clip((img_enhanced - min_val) * 255.0 / (max_val - min_val), 0, 255).astype(np.uint8)
        except:
            pass

        # 5. 深化
        if self.deepen_enabled:
            img_enhanced = cv2.convertScaleAbs(img_enhanced, alpha=self.deepen_factor, beta=-60)
            b, g, r = cv2.split(img_enhanced)
            b = cv2.multiply(b, self.blue_boost)
            b = np.clip(b, 0, 255).astype(np.uint8)
            img_enhanced = cv2.merge((b, g, r))

        return img_enhanced

    def _preprocess_for_fog(self, img):
        """
        专用预处理：迷雾/地板提取 (温和增强，保留半透明细节)
        """
        # 1. 轻微模糊
        img_blur = cv2.GaussianBlur(img, (3, 3), 0)
        
        # 2. 对比度拉伸 (温和)
        # 不使用 Gamma 压暗，因为迷雾本身就是暗的/半透明的
        # 也不使用 TopHat，因为迷雾是大面积区域，不是线条
        try:
            min_val = np.percentile(img_blur, 5)  # 只切除最暗的5%
            max_val = np.percentile(img_blur, 95)
            if max_val > min_val:
                img_enhanced = np.clip((img_blur - min_val) * 255.0 / (max_val - min_val), 0, 255).astype(np.uint8)
            else:
                img_enhanced = img_blur
        except:
            img_enhanced = img_blur

        # 3. 轻微深化 (让颜色更明显)
        # beta=10: 稍微提亮一点，而不是压暗
        img_enhanced = cv2.convertScaleAbs(img_enhanced, alpha=1.1, beta=10)
        
        return img_enhanced

    def preprocess_image(self, img):
        """兼容旧接口，默认返回墙体处理结果"""
        return self._preprocess_for_wall(img)

    def get_raw_gray(self, img):
        """
        获取用于特征匹配的原始灰度图（增强纹理）

        Args:
            img: BGR图像

        Returns:
            灰度图像
        """
        img_processed = self.preprocess_image(img)
        gray = cv2.cvtColor(img_processed, cv2.COLOR_BGR2GRAY)

        # 掩盖玩家位置（中心区域）
        h, w = gray.shape
        cx, cy = w // 2, h // 2
        radius = 30
        cv2.circle(gray, (cx, cy), radius, 0, -1)

        return gray

    # Note: The duplicate set_params and get_params methods have been removed.
    # The original methods at the beginning of the class now contain all parameters.

    def extract_walls(self, img, is_processed=False):
        """
        提取墙壁层（二值化mask，强化去噪）

        Args:
            img: BGR图像
            is_processed: 是否已经预处理

        Returns:
            二值化mask（0/255）
        """
        if not self.enable_wall:
            return np.zeros(img.shape[:2], dtype=np.uint8)

        # 预处理
        if is_processed:
            img_processed = img
        else:
            img_processed = self._preprocess_for_wall(img)

        if self.transparent_mode:
            # 针对半透明灰白地图的专用提取逻辑
            # 获取 V-S 分数图
            score = self._compute_transparency_score(img_processed)

            # 二值化
            _, mask = cv2.threshold(score, self.trans_wall_thresh, 255, cv2.THRESH_BINARY)

            # 后处理（去噪）
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, self.kernel_medium)
            mask = self._filter_small_components(mask, min_area=20)

            return mask

        # 转HSV
        hsv = cv2.cvtColor(img_processed, cv2.COLOR_BGR2HSV)

        # 颜色范围提取
        mask = cv2.inRange(hsv, self.wall_hsv_min, self.wall_hsv_max)

        # 强化形态学处理
        # 1. 闭运算：填充小孔
        # 优化：改用小核 (3x3) 以防止窄路被堵住（之前是 medium 5x5）
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, self.kernel_small)

        # 2. 再次闭运算：连接断裂的墙壁 (已合并到上一步，或保留作为强化)
        # mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, self.kernel_small)

        # 3. ⭐ 墙体平滑与宽度统一
        # 优化：移除激进的膨胀/腐蚀，将平滑工作交给 Stitcher 的后处理
        # 这样可以保留更多细节，防止墙体粘连
        # mask = cv2.dilate(mask, self.kernel_small, iterations=1)
        # mask = cv2.erode(mask, self.kernel_small, iterations=1)
        
        # 3.3 中值滤波：去除孤立噪点，平滑边缘锯齿
        mask = cv2.medianBlur(mask, 3)

        # 3.4 骨架化 + 膨胀重构（可选，确保宽度完全一致）
        # 这里使用一种简单的平滑策略：高斯模糊 + 阈值截断
        # 这会让锯齿状的边缘变得圆润
        mask_blur = cv2.GaussianBlur(mask, (3, 3), 0)  # 减小模糊核，保留细节
        _, mask = cv2.threshold(mask_blur, 127, 255, cv2.THRESH_BINARY)

        # 4. 连通域分析：过滤小噪点
        mask = self._filter_small_components(mask, min_area=20)

        return mask

    def _filter_small_components(self, mask, min_area=20):
        """
        过滤小连通域（去除白噪声）

        Args:
            mask: 二值图
            min_area: 最小保留面积

        Returns:
            过滤后的mask
        """
        # 连通域分析
        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(
            mask, connectivity=8
        )

        # 创建输出mask
        output = np.zeros_like(mask)

        # 遍历每个连通域（跳过背景0）
        for i in range(1, num_labels):
            area = stats[i, cv2.CC_STAT_AREA]

            # 保留面积大于阈值的区域
            if area >= min_area:
                output[labels == i] = 255

        return output

    def extract_fog(self, img, is_processed=False):
        """
        提取迷雾层

        Args:
            img: BGR图像
            is_processed: 是否已预处理

        Returns:
            迷雾mask
        """
        if not self.enable_fog:
            return np.zeros(img.shape[:2], dtype=np.uint8)

        # 预处理
        if is_processed:
            img_processed = img
        else:
            img_processed = self._preprocess_for_fog(img)

        hsv = cv2.cvtColor(img_processed, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, self.fog_hsv_min, self.fog_hsv_max)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, self.kernel_medium)

        return mask

    def extract_player(self, img, is_processed=False):
        """
        提取玩家标记

        Args:
            img: BGR图像
            is_processed: 是否已预处理

        Returns:
            玩家mask
        """
        # 预处理
        if is_processed:
            img_processed = img
        else:
            img_processed = self.preprocess_image(img)

        hsv = cv2.cvtColor(img_processed, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, self.player_hsv_min, self.player_hsv_max)

        # 去噪
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, self.kernel_small)

        return mask

    def extract_combined(self, img, player_pos=None):
        """
        ⭐ 优化版：提取组合特征用于拼接
        """
        # 1. 墙壁层（纯二值化）
        # 注意：这里会调用 _preprocess_for_wall
        wall_mask = self.extract_walls(img, is_processed=False)

        # 2. 迷雾层
        # 注意：这里会调用 _preprocess_for_fog
        fog_mask = self.extract_fog(img, is_processed=False)

        # 3. 边缘层（用于增强配准）
        # 边缘提取需要清晰的线条，所以使用 Wall 的预处理结果
        img_wall_processed = self._preprocess_for_wall(img)
        gray = cv2.cvtColor(img_wall_processed, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, self.edge_low, self.edge_high)

        # ⭐ 新增：颜色过滤 (Color Filter) - 必须使用原始图像！
        # 预处理后的图像Gamma和颜色都失真了，无法区分黄色和白色
        # 我们使用原始图像的饱和度来过滤掉彩色的玩家箭头
        if self.sat_filter_enabled:
            hsv_raw = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
            _, s_raw, _ = cv2.split(hsv_raw)
            
            # 饱和度掩码：饱和度 > 40 的像素认为是“彩色”，不可能是白墙
            # 黄色箭头通常 S > 100，这个阈值很安全
            color_mask = (s_raw > self.sat_filter_thresh)
            
            # 如果设置了半径限制（Blue Map Mode），则只在玩家周围过滤
            if self.sat_filter_radius > 0:
                h_img, w_img = img.shape[:2]
                mask_radius = np.zeros((h_img, w_img), dtype=np.uint8)
                
                if player_pos:
                    cx_p, cy_p = player_pos
                else:
                    cx_p, cy_p = w_img // 2, h_img // 2
                    
                cv2.circle(mask_radius, (cx_p, cy_p), self.sat_filter_radius, 255, -1)
                color_mask = color_mask & (mask_radius > 0)
            
            # 从墙体 Mask 中剔除彩色区域
            wall_mask[color_mask] = 0
        
        # 4. ⭐ 关键优化：配准mask = 墙体 + 边缘，不混入灰度图
        ww = max(0, self.wall_weight)
        ew = max(0, self.edge_weight)
        total = max(1, ww + ew)

        a = ww / total
        b = ew / total

        # 只融合墙体和边缘（用于配准）
        match_mask = cv2.addWeighted(wall_mask, a, edges, b, 0)

        # 掩盖人物中心区域
        h, w = match_mask.shape
        if player_pos:
            cx, cy = player_pos
        else:
            cx, cy = w // 2, h // 2
            
        # 增大掩盖半径 (30 -> 45)，确保完全遮住玩家特效
        # 如果玩家有复杂的技能特效，这个半径可能还需要更大
        radius = 15
        cv2.circle(match_mask, (cx, cy), radius, 0, -1)
        
        # ⭐ 关键修复：同时掩盖 wall_mask 中的玩家区域！
        # 之前只掩盖了 match_mask，导致箭头被作为墙体保存到了地图上
        cv2.circle(wall_mask, (cx, cy), radius, 0, -1)

        # 确保输出是uint8
        match_mask = match_mask.astype(np.uint8)

        # ⭐ 返回：配准用mask、保存用mask（纯墙体）、迷雾
        return match_mask, wall_mask, fog_mask

    def get_preprocessed_image(self, img):
        """
        获取预处理后的图像（用于显示）

        Args:
            img: BGR图像

        Returns:
            预处理后的BGR图像
        """
        return self.preprocess_image(img)
