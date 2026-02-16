import os
import cv2
import numpy as np
from .recognizer_optimized import HSVRecognizer

class NavigationCore:
    """
    导航核心模块
    负责地图数据的加载和基于视觉的实时定位
    """
    
    def __init__(self, map_folder_path, center_offset_y=0):
        """
        初始化导航核心
        
        Args:
            map_folder_path (str): 地图数据文件夹路径 (包含 map_data.npz)
            center_offset_y (int): 角色在小地图截图中的Y轴偏移量
        """
        self.map_folder = map_folder_path
        self.map_data_path = os.path.join(map_folder_path, "map_data.npz")
        self.center_offset_y = center_offset_y
        
        if not os.path.exists(self.map_data_path):
            raise FileNotFoundError(f"Map data not found at: {self.map_data_path}")
            
        # 加载地图数据
        self._load_map_data()
        
        # 初始化图像识别器 (用于处理实时输入的小地图)
        self.recognizer = HSVRecognizer()
        
        # 定位状态
        self.current_pos = None # (x, y) 全局坐标
        self.last_pos = None
        self.is_localized = False
        
        # 搜索参数
        self.search_radius = 200 # 局部搜索半径 (像素)
        self.confidence_threshold = 0.6 # 匹配置信度阈值
        
        # 裁剪偏移量 (Crop Offset)
        # 用于将显示坐标 (局部) 映射回 全局坐标
        self.crop_offset = (0, 0)
        
        # 实时跟踪状态
        self.prev_mask = None # 上一帧的特征 mask
        
        # 手动偏移校准
        self.manual_offset = (0, 0)
        
        # 绘图缩放比例 (必须与 StitcherCore 保持一致)
        self.draw_scale = 2.0

    def set_center_offset(self, center_offset_y):
        """更新Y轴偏移量"""
        self.center_offset_y = center_offset_y
        print(f"NavigationCore center_offset_y updated to: {center_offset_y}")
        
    def _load_map_data(self):
        """加载 .npz 地图包"""
        try:
            data = np.load(self.map_data_path)
            # 我们主要使用 wall_layer 进行特征匹配，因为它包含了最清晰的静态特征
            self.wall_layer = data['wall_layer']
            self.explored_map = data['explored_map'] if 'explored_map' in data else None
            self.canvas_size = int(data['canvas_size']) if 'canvas_size' in data else 10000
            
            # 如果有保存的最后位置，可以作为初始猜测 (可选)
            if 'current_pos' in data:
                self.last_pos = data['current_pos']
                
            print(f"Map loaded. Size: {self.canvas_size}x{self.canvas_size}")
        except Exception as e:
            raise RuntimeError(f"Failed to load map data: {str(e)}")

    def set_initial_hint(self, pos):
        """设置初始位置提示"""
        self.current_pos = pos
        self.is_localized = True 
        
        # 重置跟踪器，强制下一帧进行局部搜索校准
        # 我们不从 map 提取 prev_mask，因为 map 是 2x 缩放的，而 prev_mask 需要是 1x 的
        # 相反，我们依靠下一帧的 localize 中的局部搜索逻辑来"吸附"到正确位置
        self.prev_mask = None
        
        print(f"Initial hint set to: {pos}. Waiting for next frame to snap.")

    def _estimate_displacement(self, img1, img2):
        """核心相位相关计算 (从 StitcherCore 复用)"""
        try:
            h, w = img1.shape
            hann = cv2.createHanningWindow((w, h), cv2.CV_32F)
            shift, response = cv2.phaseCorrelate(
                img1.astype(np.float32),
                img2.astype(np.float32),
                window=hann
            )

            # 静止滤波
            dist = np.sqrt(shift[0]**2 + shift[1]**2)
            if dist < 0.2:
                return (0.0, 0.0), response

            return shift, response
        except:
            return None, 0.0

    def localize(self, minimap_img):
        """
        定位当前位置
        
        Args:
            minimap_img (numpy.ndarray): 实时的游戏小地图截图 (BGR)
            
        Returns:
            tuple: (x, y, confidence) 全局坐标和置信度. 如果失败返回 (None, None, 0)
        """
        if minimap_img is None:
            return None, None, 0.0
            
        # 1. 预处理：提取特征 (Mask)
        # 使用与建图时相同的逻辑提取特征，保证匹配的一致性
        # extract_combined 返回的是 tuple: (match_mask, wall_mask, fog_mask)
        masks = self.recognizer.extract_combined(minimap_img)
        
        if masks is None:
            return None, None, 0.0
            
        # 修正：使用 wall_mask (masks[1]) 进行匹配
        # 因为地图数据 (wall_layer) 保存的是纯墙体 mask，而不是带有边缘增强的 match_mask
        # 但如果是 F2F 跟踪，我们可以用 match_mask (masks[0]) 来获得更多细节
        if isinstance(masks, tuple) and len(masks) >= 2:
            wall_mask = masks[1] # 纯墙体，用于全局匹配
            match_mask = masks[0] # 细节丰富，用于 F2F 跟踪
        else:
            wall_mask = masks[0]
            match_mask = masks[0]
            
        # 检查特征是否足够 (如果全是黑的，匹配也没意义)
        if cv2.countNonZero(match_mask) < 10:
            return None, None, 0.0

        # === 策略分支 ===
        # 如果已经定位且有上一帧，优先使用 F2F 跟踪 (响应最快)
        if self.is_localized and self.prev_mask is not None and self.current_pos is not None:
            shift, qual = self._estimate_displacement(self.prev_mask, match_mask)
            if shift is not None and qual > 0.1: # 门槛很低，只要有相关性就行
                dx, dy = shift
                
                # 坐标系转换：
                # 1. Phase Correlation 计算的是 img2(curr) 相对于 img1(prev) 的位移
                #    如果 shift = (10, 0)，说明图像内容向右移了 10px。
                #    在小地图中，如果地图背景向右移，说明玩家向左移了。
                #    所以玩家坐标变化应该是 (-10, 0)。
                #    即: global_pos -= shift
                
                # 2. 缩放修正：
                #    shift 是在原始分辨率 (1x) 下计算的。
                #    全局地图 (wall_layer) 是在 draw_scale (2x) 下保存的。
                #    所以位移量需要乘以 draw_scale。
                
                dx_global = dx * self.draw_scale
                dy_global = dy * self.draw_scale
                
                self.current_pos = (self.current_pos[0] - dx_global, self.current_pos[1] - dy_global)
                self.prev_mask = match_mask
                
                return self.current_pos[0], self.current_pos[1], qual

        # 如果没有上一帧 (刚初始化)，或者 F2F 失败，尝试全局/局部搜索校准
        # 使用 wall_mask 和 wall_layer 匹配
        
        # 2. 确定搜索区域
        search_area = self.wall_layer
        top_left_offset = (0, 0) # 搜索区域在全局地图中的偏移
        
        if self.is_localized and self.current_pos is not None:
            # 局部搜索模式 (Hint Mode 或 F2F 丢失后的恢复)
            cx, cy = int(self.current_pos[0]), int(self.current_pos[1])
            # 搜索半径：如果是 Hint 模式，可能偏差较大，给 300px
            # 注意：这是 Scaled 后的像素 (2x)，所以 300px 对应屏幕上 150px
            r = 300 
            
            # 计算局部窗口边界 (注意不要越界)
            x1 = max(0, cx - r)
            y1 = max(0, cy - r)
            x2 = min(self.canvas_size, cx + r)
            y2 = min(self.canvas_size, cy + r)
            
            # 裁剪搜索区域
            search_area = self.wall_layer[y1:y2, x1:x2]
            top_left_offset = (x1, y1)
            
            # 如果搜索区域太小，回退到全局搜索
            # 我们的模板将是 wall_mask 放大 2 倍后的尺寸
            h_raw, w_raw = wall_mask.shape
            h_scaled, w_scaled = int(h_raw * self.draw_scale), int(w_raw * self.draw_scale)
            
            if search_area.shape[0] < h_scaled or search_area.shape[1] < w_scaled:
                search_area = self.wall_layer
                top_left_offset = (0, 0)
        
        # 3. 模板匹配
        # TM_CCOEFF_NORMED 是最稳健的方法之一
        try:
            # 确保输入类型正确
            if wall_mask is None or search_area is None:
                return None, None, 0.0
                
            # === 关键修正：缩放匹配 ===
            # wall_mask 是原始截图 (1x)，search_area 是地图数据 (2x)
            # 必须将 wall_mask 放大到 2x 才能匹配
            h_raw, w_raw = wall_mask.shape
            h_scaled, w_scaled = int(h_raw * self.draw_scale), int(w_raw * self.draw_scale)
            
            wall_mask_scaled = cv2.resize(wall_mask, (w_scaled, h_scaled), interpolation=cv2.INTER_NEAREST)
            
            # 简单的形态学处理 (与 StitcherCore 保持一致)
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
            wall_mask_scaled = cv2.morphologyEx(wall_mask_scaled, cv2.MORPH_CLOSE, kernel)
            
            # 类型转换
            if search_area.dtype != np.uint8:
                search_area = search_area.astype(np.uint8)
            if wall_mask_scaled.dtype != np.uint8:
                wall_mask_scaled = wall_mask_scaled.astype(np.uint8)
                
            # 检查尺寸: 模板不能比搜索区域大
            h_s, w_s = search_area.shape
            h_t, w_t = wall_mask_scaled.shape
            if h_t > h_s or w_t > w_s:
                # 模板比搜索区域大，无法匹配
                return None, None, 0.0

            result = cv2.matchTemplate(search_area, wall_mask_scaled, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
            
            # 4. 解析结果
            if max_val >= self.confidence_threshold:
                # max_loc 是在 search_area 中的坐标 (x, y)
                # 需要转换为全局坐标
                # 模板匹配返回的是左上角坐标，我们需要中心坐标
                # 另外，需要应用Y轴偏移量
                offset_y_scaled = self.center_offset_y * self.draw_scale

                center_x = top_left_offset[0] + max_loc[0] + w_t // 2
                center_y = top_left_offset[1] + max_loc[1] + h_t // 2 + offset_y_scaled
                
                self.current_pos = (center_x, center_y)
                self.is_localized = True
                self.last_pos = self.current_pos
                
                # 初始化跟踪器 (使用原始 mask)
                self.prev_mask = match_mask
                
                return center_x, center_y, max_val
            else:
                # 匹配失败
                # 如果是局部搜索失败，下次应该尝试全局搜索
                if self.is_localized:
                    print(f"Local search failed (conf={max_val:.2f}). Switching to global search next time.")
                    self.is_localized = False 
                    self.prev_mask = None # 丢失跟踪
                
                return None, None, max_val
                
        except Exception as e:
            print(f"Localization error: {e}")
            return None, None, 0.0

    def get_map_image(self):
        """
        获取用于显示的完整地图图像
        基于 .npz 数据实时渲染，并自动裁剪到有效区域
        """
        # 创建基础画布 (全黑背景)
        h, w = self.wall_layer.shape
        display_img = np.zeros((h, w, 3), dtype=np.uint8)
        
        # 1. 渲染已探索区域 (深灰色)
        mask_combined = np.zeros((h, w), dtype=bool)
        
        if self.explored_map is not None:
            mask_explored = self.explored_map > 0
            if np.any(mask_explored):
                 display_img[mask_explored] = [40, 40, 40]
                 mask_combined |= mask_explored

        # 2. 渲染墙壁 (亮白色)
        if self.wall_layer is not None:
            mask_wall = self.wall_layer > 0
            if np.any(mask_wall):
                 display_img[mask_wall] = [220, 220, 220]
                 mask_combined |= mask_wall
            else:
                 print("Warning: wall_layer is empty (all zeros).")
        
        # 3. 自动裁剪
        # 找到所有非零区域的边界
        if np.any(mask_combined):
            rows = np.any(mask_combined, axis=1)
            cols = np.any(mask_combined, axis=0)
            y_min, y_max = np.where(rows)[0][[0, -1]]
            x_min, x_max = np.where(cols)[0][[0, -1]]
            
            # 增加一点 padding (比如 50px)
            pad = 50
            y_min = max(0, y_min - pad)
            y_max = min(h, y_max + pad)
            x_min = max(0, x_min - pad)
            x_max = min(w, x_max + pad)
            
            # 记录裁剪偏移量，以便后续将 UI 点击坐标映射回全局坐标
            self.crop_offset = (x_min, y_min)
            
            print(f"Auto-cropping map to: x[{x_min}:{x_max}], y[{y_min}:{y_max}]")
            return display_img[y_min:y_max, x_min:x_max]
        else:
            self.crop_offset = (0, 0)
            return display_img
