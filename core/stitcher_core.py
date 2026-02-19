"""
地图拼接器 - 极简高精版 (Refactored)
去除冗余功能，回归核心算法，专注于 Frame-to-Frame + Keyframe Anchor 的高精度配准。

主要改进:
1. 移除 "全局校准" (Global Alignment) - 解决双眼皮和透视错误。
2. 移除 "运动平滑" (Smoothing) - 解决滞后和漂移。
3. 引入 "关键帧锚点" (Keyframe Anchor) - 减少累积误差。
4. 简化 "加权融合" (Weighted Merge) - 自然抗噪，防止墙体变粗。
"""

import cv2
import numpy as np
from collections import deque
import time

class PerformanceMonitor:
    """性能监控器"""
    
    def __init__(self):
        self.timings = {}
        self.frame_timings = []
        
    def record(self, name, duration_ms):
        if name not in self.timings:
            self.timings[name] = []
        self.timings[name].append(duration_ms)
        if len(self.timings[name]) > 100:
            self.timings[name].pop(0)
    
    def print_report(self):
        # 简化版报告
        pass

class Timer:
    """计时器"""
    def __init__(self, monitor, name):
        self.monitor = monitor
        self.name = name
        self.start_time = None
    def __enter__(self):
        self.start_time = time.perf_counter()
        return self
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.monitor:
            duration_ms = (time.perf_counter() - self.start_time) * 1000
            self.monitor.record(self.name, duration_ms)

class MapStitcher:
    """
    实时地图拼接器 (Core Refactor)
    策略: 
    - 尽可能与"关键帧"(Keyframe)进行配准，而不是上一帧。
    - 只有当与关键帧的重叠度降低时，才切换新的关键帧。
    - 这样可以将累积误差降低 N 倍 (N=关键帧间隔)。
    """

    def __init__(self, canvas_size=6000, draw_scale=2.0):
        """初始化"""
        self.canvas_size = canvas_size
        self.draw_scale = draw_scale

        # 全局画布
        # 使用稀疏矩阵思想？不，OpenCV图像必须是Dense的。
        # 20000x20000 uint8 = 400MB 内存，完全可以接受。
        # 但如果是 float32 权重层，那就是 1.6GB，稍微有点大。
        # 我们需要保持 weight_layer 为 float32 以进行精确累积。
        # 总内存占用约 2GB，对于现代PC没问题。
        self.canvas = np.zeros((canvas_size, canvas_size), dtype=np.uint8)
        self.wall_layer = np.zeros((canvas_size, canvas_size), dtype=np.uint8)
        self.fog_layer = np.zeros((canvas_size, canvas_size), dtype=np.uint8)
        self.explored_map = np.zeros((canvas_size, canvas_size), dtype=np.uint8)
        
        # 权重层 (用于置信度融合)
        self.weight_layer = np.zeros((canvas_size, canvas_size), dtype=np.float32)

        # 核心坐标 (高精度 float)
        self.current_x = float(canvas_size // 2)
        self.current_y = float(canvas_size // 2)

        # 关键帧锚点系统
        self.keyframe_mask = None      # 当前锁定的关键帧图像
        self.keyframe_pos = (0.0, 0.0) # 关键帧在全局地图的绝对坐标
        self.keyframe_quality = 0.0    # 关键帧自身的质量
        
        # 上一帧 (作为Fallback)
        self.prev_mask = None
        self.prev_pos = (0.0, 0.0)

        # 统计
        self.stats = {
            'total_frames': 0,
            'successful_matches': 0,
            'failed_matches': 0,
            'match_quality': 0.0,
            'match_rate': 0.0, # Added missing key
            'keyframe_switches': 0,
            'exploration': 0.0,
            'avg_displacement': 0.0
        }

        # 性能监控
        self.perf = PerformanceMonitor()
        
        # 参数
        self.conf_thresh = 0.30       # F2F 匹配门槛，大幅降低 (原0.45)，防止轻微特征丢失导致断连
        self.keyframe_thresh = 0.25   # Anchor 维持门槛，降低要求，尽量不切换 Anchor
        self.weight_add = 0.3         # 单帧权重增量 (越小越平滑，抗噪越强)
        self.weight_cap = 5.0         # 最大权重

        # ⭐ 新增：历史记录（只加这3行）
        from collections import deque
        self.displacement_history = deque(maxlen=5)  # 保存最近5帧
        self.quality_history = deque(maxlen=5)

    def set_params(self, params):
        """设置参数"""
        if 'conf_thresh' in params:
            self.conf_thresh = float(params['conf_thresh'])
        if 'keyframe_thresh' in params:
            self.keyframe_thresh = float(params['keyframe_thresh'])
        if 'weight_add' in params:
            self.weight_add = float(params['weight_add'])
        if 'weight_cap' in params:
            self.weight_cap = float(params['weight_cap'])
        # 注意：canvas_size 和 draw_scale 通常不应该通过 set_params 修改
        # 因为它们会影响画布的初始化，需要重新创建画布
        # 如果确实需要修改，需要更复杂的逻辑来处理画布重建

    def get_params(self):
        """获取参数"""
        return {
            'conf_thresh': self.conf_thresh,
            'keyframe_thresh': self.keyframe_thresh,
            'weight_add': self.weight_add,
            'weight_cap': self.weight_cap,
            'canvas_size': self.canvas_size,
            'draw_scale': self.draw_scale
        }

    def save_map_package(self, folder_path):
        """
        保存地图包 (数据 Only)
        """
        import os
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
            
        # 保存完整数据矩阵
        # 使用 np.savez_compressed 压缩存储
        np.savez_compressed(
            os.path.join(folder_path, "map_data.npz"),
            canvas=self.canvas,
            weight_layer=self.weight_layer,
            explored_map=self.explored_map,
            wall_layer=self.wall_layer,
            fog_layer=self.fog_layer,
            current_pos=np.array([self.current_x, self.current_y]),
            canvas_size=self.canvas_size
        )
        print(f"地图数据已保存至: {folder_path}")

    def load_map_package(self, folder_path):
        """
        加载地图包
        """
        import os
        data_path = os.path.join(folder_path, "map_data.npz")
        if not os.path.exists(data_path):
            print(f"错误: 找不到地图数据 {data_path}")
            return False
            
        try:
            data = np.load(data_path)
            
            # 检查尺寸匹配
            saved_size = int(data['canvas_size'])
            if saved_size != self.canvas_size:
                print(f"警告: 地图尺寸不匹配 (保存: {saved_size}, 当前: {self.canvas_size})，可能导致加载失败")
                # 这里可以考虑自动resize，但为了安全先只警告
                
            self.canvas = data['canvas']
            self.weight_layer = data['weight_layer']
            self.explored_map = data['explored_map']
            
            # 尝试加载额外层 (兼容旧版本)
            if 'wall_layer' in data:
                self.wall_layer = data['wall_layer']
            if 'fog_layer' in data:
                self.fog_layer = data['fog_layer']
                
            # 恢复坐标
            if 'current_pos' in data:
                pos = data['current_pos']
                self.current_x = float(pos[0])
                self.current_y = float(pos[1])
                
            print(f"地图加载成功: {folder_path}")
            return True
        except Exception as e:
            print(f"加载地图失败: {e}")
            return False

    def add_frame(self, img, match_mask, save_mask, fog_mask, raw_gray=None, player_pos=None):
        """
        添加新帧 (核心逻辑)
        """
        frame_start = time.perf_counter()
        self.stats['total_frames'] += 1
        frame_num = self.stats['total_frames']
        
        # 玩家在小地图内的相对坐标
        h, w = save_mask.shape
        if player_pos is None:
            px, py = w // 2, h // 2
        else:
            px, py = player_pos

        # --- 0. 第一帧初始化 ---
        if self.keyframe_mask is None:
            self._place_first_frame(save_mask, fog_mask, px, py)
            
            # 初始化关键帧和上一帧
            self.keyframe_mask = match_mask.copy()
            self.keyframe_pos = (self.current_x, self.current_y)
            self.prev_mask = match_mask.copy()
            self.prev_pos = (self.current_x, self.current_y)
            
            print(f"[帧 {frame_num}] 🔥 系统初始化完成")
            return True

        # --- 1. 配准 (Registration) ---
        # 策略: 优先匹配关键帧 (Keyframe), 失败则匹配上一帧 (Prev Frame)
        
        dx, dy = 0.0, 0.0
        match_success = False
        match_type = "None"
        current_quality = 0.0

        # A. 尝试与关键帧匹配 (Anchor Matching)
        # 优点: 只要不换关键帧，误差就不会累积！
        k_shift, k_qual = self._estimate_displacement(self.keyframe_mask, match_mask)
        
        anchor_valid = False
        if k_shift is not None and k_qual > self.keyframe_thresh:
            # 预计算位置以进行跳变检查
            k_dx_raw, k_dy_raw = k_shift
            dx_global_raw = k_dx_raw * self.draw_scale
            dy_global_raw = k_dy_raw * self.draw_scale
            target_x_raw = self.keyframe_pos[0] - dx_global_raw
            target_y_raw = self.keyframe_pos[1] - dy_global_raw
            
            # Sanity Check: 检查是否发生瞬间大跳变 (误匹配常见症状)
            dist_jump = np.sqrt((target_x_raw - self.current_x)**2 + (target_y_raw - self.current_y)**2)
            
            # 规则：如果跳变 > 100px 且 置信度 < 0.6，则认为是误匹配
            if dist_jump < 100.0 or k_qual > 0.6:
                anchor_valid = True
            else:
                print(f"[帧 {frame_num}] ⚠️ Anchor跳变过大 ({dist_jump:.1f}px, Q:{k_qual:.2f})，拒绝误匹配")

        if anchor_valid:
            # 匹配成功，且质量很高 -> 保持关键帧
            k_dx, k_dy = k_shift

            # ⭐ 新增：平滑处理（只加这2行）
            k_dx, k_dy = self._smooth_displacement(k_dx, k_dy, k_qual)

            # 计算当前绝对位置
            dx_global = k_dx * self.draw_scale
            dy_global = k_dy * self.draw_scale

            target_x = self.keyframe_pos[0] - dx_global
            target_y = self.keyframe_pos[1] - dy_global

            self.current_x = target_x
            self.current_y = target_y

            match_success = True
            match_type = "Anchor"
            current_quality = k_qual
            
        else:
            # B. 关键帧匹配失败/质量低 -> 尝试与上一帧匹配 (Fallback)
            p_shift, p_qual = self._estimate_displacement(self.prev_mask, match_mask)

            if p_shift is not None and p_qual > self.conf_thresh:
                # F2F 成功
                p_dx, p_dy = p_shift

                # ⭐ 新增：平滑处理（只加这2行）
                p_dx, p_dy = self._smooth_displacement(p_dx, p_dy, p_qual)

                # Sanity Check: 检查位移是否合理 (Max Displacement Check)
                # 除非是传送，否则帧间位移不应过大 (例如 > 50px)
                # 如果位移过大，可能是误匹配
                p_dist = np.sqrt(p_dx**2 + p_dy**2)
                if p_dist > 50.0:
                    match_success = False
                    self.stats['failed_matches'] += 1
                    print(f"[帧 {frame_num}] ⚠️ F2F位移过大 ({p_dist:.1f}px)，忽略跳变 (Q:{p_qual:.2f})")
                else:
                    dx_global = p_dx * self.draw_scale
                    dy_global = p_dy * self.draw_scale

                    target_x = self.current_x - dx_global
                    target_y = self.current_y - dy_global

                    self.current_x = target_x
                    self.current_y = target_y

                    # ⭐ 关键逻辑: 既然关键帧跟不住了，且F2F成功了
                    # 我们需要决定是否将当前帧设为新的关键帧
                    
                    # 策略：Smart Anchor Update (智能锚点更新)
                    # 只有当当前帧的特征足够丰富时，才更新锚点
                    # 如果当前帧是一片白茫茫（特征少），我们宁愿不更新锚点，
                    # 而是继续依靠 F2F 漂流，直到遇到下一个特征丰富的帧。
                    # 这样可以防止锚点被"污染"成无特征帧，导致后续配准彻底失效。
                    
                    feature_score = cv2.countNonZero(match_mask)
                    # 阈值：假设至少需要 2% 的像素是特征点
                    # 100x100 的图需要 200 个点。通常 match_mask 应该有不少线条。
                    # 设为 500 (对于 200x200 左右的小地图来说不算高)
                    min_feature_score = 500 
                    
                    if feature_score > min_feature_score:
                        self.keyframe_mask = match_mask.copy()
                        self.keyframe_pos = (self.current_x, self.current_y)
                        self.stats['keyframe_switches'] += 1
                        print(f"[帧 {frame_num}] ⚓ Anchor更新 (Score: {feature_score})")
                    else:
                        print(f"[帧 {frame_num}] ⚠️ 特征不足 ({feature_score})，跳过Anchor更新，仅F2F")

                    match_success = True
                    match_type = "F2F-Reset"
                    current_quality = p_qual
            else:
                # C. 都失败了
                match_success = False
                self.stats['failed_matches'] += 1
                print(f"[帧 {frame_num}] ❌ 配准完全失败 (K:{k_qual:.2f}, P:{p_qual:.2f})")

        self.stats['match_quality'] = current_quality

        # --- 2. 绘制 (Drawing) ---
        if match_success:
            self.stats['successful_matches'] += 1
            
            # 准备绘制数据
            h_scaled = int(h * self.draw_scale)
            w_scaled = int(w * self.draw_scale)
            
            # 缩放 Mask
            save_mask_scaled = cv2.resize(save_mask, (w_scaled, h_scaled), interpolation=cv2.INTER_NEAREST)
            fog_mask_scaled = cv2.resize(fog_mask, (w_scaled, h_scaled), interpolation=cv2.INTER_NEAREST)
            
            # 统一厚度 (可选，保持简单)
            save_mask_scaled = self.standardize_wall_thickness(save_mask_scaled)
            
            px_scaled = int(px * self.draw_scale)
            py_scaled = int(py * self.draw_scale)
            
            # 融合
            self._merge_frame_weighted(
                save_mask_scaled, fog_mask_scaled,
                h_scaled, w_scaled, px_scaled, py_scaled
            )
            
            # 更新上一帧
            self.prev_mask = match_mask.copy()
            
            # 日志
            if frame_num % 10 == 0 or match_type == "F2F-Reset":
                print(f"[帧 {frame_num}] ✅ {match_type} | Q:{current_quality:.2f} | Pos:({self.current_x:.1f}, {self.current_y:.1f})")

        # 更新衍生统计
        if self.stats['total_frames'] > 0:
            self.stats['match_rate'] = (self.stats['successful_matches'] / self.stats['total_frames']) * 100.0

        return True

    def _smooth_displacement(self, dx, dy, quality):
        """
        无平滑：直接返回原始位移
        核心：保持最高响应性，避免累积误差
        """
        # 添加到历史（仅用于统计）
        self.displacement_history.append((dx, dy))
        self.quality_history.append(quality)

        # 直接返回原始值，不进行任何平滑
        return dx, dy

    def _estimate_displacement(self, img1, img2):
        """核心相位相关计算"""
        try:
            h, w = img1.shape
            hann = cv2.createHanningWindow((w, h), cv2.CV_32F)
            shift, response = cv2.phaseCorrelate(
                img1.astype(np.float32),
                img2.astype(np.float32),
                window=hann
            )

            # 静止滤波 (Dead Zone Filter)
            # 只有当位移超过阈值时才认为是有效移动
            # 0.2px 是一个很小的值，足以过滤掉压缩噪声和细微抖动
            dist = np.sqrt(shift[0]**2 + shift[1]**2)
            if dist < 0.2:
                return (0.0, 0.0), response

            return shift, response
        except:
            return None, 0.0

    def _place_first_frame(self, save_mask, fog_mask, px, py):
        """放置第一帧"""
        h, w = save_mask.shape
        h_scaled = int(h * self.draw_scale)
        w_scaled = int(w * self.draw_scale)
        
        save_mask_scaled = cv2.resize(save_mask, (w_scaled, h_scaled), interpolation=cv2.INTER_NEAREST)
        fog_mask_scaled = cv2.resize(fog_mask, (w_scaled, h_scaled), interpolation=cv2.INTER_NEAREST)
        
        save_mask_scaled = self.standardize_wall_thickness(save_mask_scaled)
        
        px_scaled = int(px * self.draw_scale)
        py_scaled = int(py * self.draw_scale)
        
        # 写入
        self._merge_frame_weighted(save_mask_scaled, fog_mask_scaled, h_scaled, w_scaled, px_scaled, py_scaled, force=True)

    def _merge_frame_weighted(self, save_mask, fog_mask, h, w, px, py, force=False):
        """
        加权融合算法 (Weighted Merge)
        - 使用浮点权重层累积置信度
        - 只有当权重超过阈值才显示为墙
        - 自然消除噪音，防止变胖
        """
        cur_x, cur_y = int(self.current_x), int(self.current_y)

        # 原始目标区域
        x1 = cur_x - px
        y1 = cur_y - py
        x2 = x1 + w
        y2 = y1 + h

        # 边界裁剪 (Clipping)
        # 计算与画布的交集
        c_x1 = max(0, x1)
        c_y1 = max(0, y1)
        c_x2 = min(self.canvas_size, x2)
        c_y2 = min(self.canvas_size, y2)

        # 如果无交集，直接返回
        if c_x1 >= c_x2 or c_y1 >= c_y2:
            return

        # 计算在源图像(save_mask)中的偏移
        src_x1 = c_x1 - x1
        src_y1 = c_y1 - y1
        src_x2 = src_x1 + (c_x2 - c_x1)
        src_y2 = src_y1 + (c_y2 - c_y1)

        # 提取裁剪后的源数据
        save_mask_clipped = save_mask[src_y1:src_y2, src_x1:src_x2]
        fog_mask_clipped = fog_mask[src_y1:src_y2, src_x1:src_x2]

        # ROI Views (使用裁剪后的坐标)
        roi_weight = self.weight_layer[c_y1:c_y2, c_x1:c_x2]
        roi_wall = self.wall_layer[c_y1:c_y2, c_x1:c_x2]
        roi_explored = self.explored_map[c_y1:c_y2, c_x1:c_x2]

        # ⭐ 新增：相似度检测（只加这4行）
        # 只在高质量匹配时进行重复检测，避免误判
        if self._is_too_similar(roi_wall, save_mask_clipped) and not force:
            print("[防止重复] 内容太相似，跳过本次绘制")
            self.stats['redundant_prevented'] = self.stats.get('redundant_prevented', 0) + 1
            return
        
        # 1. 墙体权重更新
        # 新墙体区域
        new_wall_mask = (save_mask_clipped > 127)
        
        # 增加权重
        # 只有在有墙的地方加分
        roi_weight[new_wall_mask] += self.weight_add
        
        # 限制最大权重 (防止无限增加)
        np.clip(roi_weight, 0, self.weight_cap, out=roi_weight)
        
        # 2. 决定显示哪些墙
        # 阈值判断: 权重 > 1.0 的地方才认为是真墙
        # 这意味着至少需要 3-4 帧确认 (0.3 * 4 = 1.2)
        # 这样单帧的跳变噪音会被过滤掉
        if force:
            roi_weight[new_wall_mask] = self.weight_cap # 强制第一帧直接显示
            visible_wall_mask = new_wall_mask
        else:
            visible_wall_mask = (roi_weight > 1.0)
            
        # 3. 写入 Wall Layer
        # 我们只更新 visible_wall_mask 为 True 的区域
        # 保持二值化: 255 or 0
        roi_wall[visible_wall_mask] = 255
        # 注意: 我们不清除旧墙，只添加新确信的墙。
        # 如果要清除错误的墙(擦除)，需要引入减分机制，目前暂不引入以保持简单。
        
        # 4. 更新探索状态 (强制更新视野范围)
        # 无论有没有迷雾，只要是当前帧覆盖的区域，都视为"已探索"
        # 创建一个默认的全白Mask (代表视野)
        view_mask = np.full_like(roi_explored, 255)
        
        # 如果有fog_mask，取并集 (或者直接覆盖，视情况而定)
        # 实际上，直接把当前视野全部标记为已探索是最稳妥的
        # 为了美观，可以对 view_mask 做一个圆角或渐变，但这里为了性能直接用矩形
        
        # 使用 max 运算来合并 (255覆盖0)
        np.maximum(roi_explored, view_mask, out=roi_explored)
        
        # 5. 更新 Canvas (用于显示)
        self.canvas[c_y1:c_y2, c_x1:c_x2] = roi_wall

    def _is_too_similar(self, roi_wall, save_mask):
        """
        判断是否太相似（防止重复绘制）
        简化版：只用IoU（交并比）
        """
        import numpy as np

        # 计算重叠区域
        overlap = (roi_wall > 127) | (save_mask > 127)
        if np.sum(overlap) < 100:
            return False  # 重叠太小，不是重复

        # 计算IoU（交并比）
        intersection = np.sum((roi_wall > 127) & (save_mask > 127))
        union = np.sum(overlap)
        iou = intersection / union

        # 如果IoU > 0.95，说明95%以上重叠，认为是重复
        if iou > 0.95:
            return True

        return False

    def standardize_wall_thickness(self, mask):
        """简单的形态学处理"""
        # 闭运算连接断点
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        return cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

    def _check_bounds(self, x1, y1, x2, y2):
        in_bounds = (0 <= x1 < self.canvas_size and
                0 <= y1 < self.canvas_size and
                0 < x2 <= self.canvas_size and
                0 < y2 <= self.canvas_size)
        
        if not in_bounds:
            print(f"[警告] 触达地图边界! ({x1},{y1}) -> ({x2},{y2}) Canvas:{self.canvas_size}")
            
        return in_bounds

    def get_current_position(self):
        return (int(self.current_x), int(self.current_y))

    def get_statistics(self):
        return {
            **self.stats,
            'redundant_prevented': self.stats.get('redundant_prevented', 0)
        }

    def reset(self):
        self.__init__(self.canvas_size, self.draw_scale)

    def get_cropped_map(self, margin=0):
        """获取裁剪后的地图 (包含迷雾)"""
        # 使用 explored_map 来确定边界，因为它包含所有看过的地方
        coords = cv2.findNonZero(self.explored_map)
        if coords is None:
            # 如果没有探索数据，尝试墙壁
            coords = cv2.findNonZero(self.wall_layer)
        
        if coords is None:
            return np.zeros((100, 100), dtype=np.uint8)
            
        x, y, w, h = cv2.boundingRect(coords)
        
        # ⭐ 扩展边界以包含当前玩家位置 (防止显示偏移)
        cx, cy = int(self.current_x), int(self.current_y)
        
        x2 = x + w
        y2 = y + h
        
        x = min(x, cx)
        y = min(y, cy)
        x2 = max(x2, cx + 1)
        y2 = max(y2, cy + 1)
        
        w = x2 - x
        h = y2 - y
        
        # 应用边距
        x = max(0, x - margin)
        y = max(0, y - margin)
        w = min(self.canvas_size - x, w + 2 * margin)
        h = min(self.canvas_size - y, h + 2 * margin)
        
        # 提取区域
        roi_wall = self.wall_layer[y:y+h, x:x+w]
        roi_explored = self.explored_map[y:y+h, x:x+w]
        
        # 合成显示图 (类似于 get_enhanced_map，但只返回图像)
        display = np.zeros_like(roi_wall)
        display[roi_explored > 0] = 60 
        display[roi_wall > 0] = 255
        
        return display

    def get_enhanced_map(self, margin=500):
        """
        获取用于显示的增强地图 (合成墙壁和迷雾背景)
        """
        # 1. 确定边界
        coords = cv2.findNonZero(self.explored_map)
        if coords is None:
            coords = cv2.findNonZero(self.wall_layer)
            
        if coords is None:
            return np.zeros((100, 100), dtype=np.uint8)
             
        x, y, w, h = cv2.boundingRect(coords)
        
        # 应用边距
        x = max(0, x - margin)
        y = max(0, y - margin)
        w = min(self.canvas_size - x, w + 2 * margin)
        h = min(self.canvas_size - y, h + 2 * margin)
        
        # 2. 提取区域
        roi_wall = self.wall_layer[y:y+h, x:x+w]
        roi_explored = self.explored_map[y:y+h, x:x+w]
        
        # 3. 合成显示图
        # 背景全黑 (0)
        display = np.zeros_like(roi_wall)
        
        # 探索过的区域 (迷雾) 显示为深灰色
        display[roi_explored > 0] = 60 
        
        # 墙壁显示为亮白色
        display[roi_wall > 0] = 255
        
        # 返回 (image, offset)
        return display, (x, y)

    # 兼容性接口 (防止UI报错)
    def set_merge_mode(self, mode, **kwargs): pass
    def set_global_correction(self, enabled): pass
    def set_motion_smoothing(self, enabled, **kwargs): pass
    def set_repair_params(self, **kwargs): pass
