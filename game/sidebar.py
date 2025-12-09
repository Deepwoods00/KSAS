# -*- coding: utf-8 -*-
import logging
import cv2
import os
from airtest.core.api import Template
from i18n.i18n import get_text

class Sidebar:
    """
    游戏侧边栏交互类
    负责处理侧边栏的展开/收起，以及读取侧边栏上的信息（如行军队列状态）
    """
    def __init__(self, device, data):
        self.device = device
        self.data = data
        self.logger = logging.getLogger(f"{data.instance_id}.Game.Sidebar")
        
        # 初始化空闲队列数量 (从统计数据中读取，默认为 0)
        self.idle_march_count = self.data.get_stat("sidebar.idle_queues", 0)

        # --- 资源定义 ---
        self.IMG_BTN_TOWN = Template(r"assets/images/home/btn_town.png", threshold=0.9)
        self.IMG_BTN_GO_MAP = Template(r"assets/images/home/btn_go_map.png", threshold=0.9)
        self.IMG_SIDEBAR_CHECK = Template(r"assets/images/sidebar/sidebar_check.png", threshold=0.9)
        self.IMG_SIDEBAR_QUEUE_CHECK = Template(r"assets/images/sidebar/sidebar_queue_check.png", threshold=0.9)
        
        # --- 坐标与区域定义 ---
        self.POS_EXPAND_BTN = (4, 550)
        self.AREA_CHECK = (6, 242, 444, 297)
        
        # 侧边栏页面切换按钮
        self.POS_AFFAIRS_TAB = (149, 263)
        self.POS_MARCH_PAGE_BTN = (290, 270)

        # 行军队列检测区域 (x1, y1, x2, y2)
        self.MARCH_QUEUE_AREAS = [
            (370, 340, 430, 400), # Queue 1
            (370, 415, 430, 475), # Queue 2
            (370, 490, 430, 550), # Queue 3
            (370, 560, 430, 625), # Queue 4
            (370, 637, 430, 696), # Queue 5
            (370, 710, 430, 770)  # Queue 6
        ]

    def expand(self):
        """
        展开侧边栏
        逻辑:
        1. 检查是否有 btn_town.png (判断是否在野外)
           - 是: 点击 (4, 550)
           - 否: 点击 btn_go_map.png -> 等待 1.5s -> 点击 (4, 550)
        2. 检查 sidebar_check.png 是否出现
        """
        self.logger.info(get_text("log_sidebar_expanding"))
        
        

        for i in range(3):
            self.logger.info(get_text("log_sidebar_expand_attempt", i+1))
            # 0. 确保在主界面
            self.device.ensure_home()

            
            # 1. 场景判断与点击
            if self.device.exists(self.IMG_BTN_TOWN):
                self.logger.info(get_text("log_sidebar_wilderness"))
                self.device.click(self.POS_EXPAND_BTN)
            else:
                self.logger.info(get_text("log_sidebar_switch_map"))
                if self.device.exists(self.IMG_BTN_GO_MAP):
                    self.device.click(self.IMG_BTN_GO_MAP)
                    self.device.sleep(1.5)
                    self.device.click(self.POS_EXPAND_BTN)
                else:
                    self.logger.warning(get_text("log_sidebar_no_buttons"))

            # 2. 结果验证
            self.device.sleep(1.0) # 等待动画
            
            # 使用区域截图进行验证
            # AREA_CHECK = (6, 242, 444, 297) -> (x1, y1, x2, y2)
            screen_path = self.device._save_snapshot("sidebar_check")
            if screen_path:
                screen = cv2.imread(screen_path)
                if screen is not None:
                    # Crop: y1:y2, x1:x2
                    x1, y1, x2, y2 = self.AREA_CHECK
                    cropped = screen[y1:y2, x1:x2]
                    
                    # 匹配
                    res = self.IMG_SIDEBAR_CHECK.match_in(cropped)
                    if res:
                        self.logger.info(get_text("log_sidebar_expand_success"))
                        return True
        
        self.logger.error(get_text("log_sidebar_expand_failed"))
        return False

    def collapse(self):
        """
        收起侧边栏
        逻辑: 点击 btn_town.png -> 等待 1.5s -> 点击 btn_go_map.png
        """
        self.logger.info(get_text("log_sidebar_collapsing"))
        
        # 1. 点击回城
        if self.device.exists(self.IMG_BTN_TOWN):
            self.device.click(self.IMG_BTN_TOWN)
        
        # 2. 等待
        self.device.sleep(1.5)
        
        # 3. 点击出城
        if self.device.exists(self.IMG_BTN_GO_MAP):
            self.device.click(self.IMG_BTN_GO_MAP)

    def find_in_anchor_row(self, anchor_tpl, target_tpl, x_range=(373, 434), y_padding=15):
        """
        [修复版] 在锚点同一行寻找目标
        兼容 Airtest 返回 dict 或 tuple 的情况
        """
        # 1. 截取全屏
        screen_path = self.device._save_snapshot("row_search")
        if not screen_path:
            return None
        
        screen = cv2.imread(screen_path)
        if screen is None:
            return None

        # 2. 寻找锚点
        anchor_res = anchor_tpl.match_in(screen)
        
        if not anchor_res:
            return None

        try:
            # === [修复核心] 类型检查与边界计算 ===
            y_top = 0
            y_bottom = 0
            
            # 情况 A: 返回字典 (包含 rectangle)
            if isinstance(anchor_res, dict):
                rect = anchor_res.get('rectangle')
                if rect:
                    y_top = int(rect[0][1])     # 左上角 Y
                    y_bottom = int(rect[2][1])  # 右下角 Y
                else:
                    # 字典里没有矩形信息，回退到使用中心点
                    cx, cy = anchor_res['result']
                    h, w = anchor_tpl._imread().shape[:2]
                    y_top = int(cy - h/2)
                    y_bottom = int(cy + h/2)
            
            # 情况 B: 返回元组/列表 (只包含坐标) -> 报错就是因为进了这里
            elif isinstance(anchor_res, (tuple, list)):
                cx, cy = anchor_res
                # 获取模板图片的高度
                h, w = anchor_tpl._imread().shape[:2]
                y_top = int(cy - h/2)
                y_bottom = int(cy + h/2)
            
            else:
                self.logger.error(f"Unknown anchor_res type: {type(anchor_res)}")
                return None

            # 3. 应用外扩 (Padding)
            crop_y_min = max(0, y_top - y_padding)
            crop_y_max = min(screen.shape[0], y_bottom + y_padding)
            
            crop_x_min = max(0, x_range[0])
            crop_x_max = min(screen.shape[1], x_range[1])

            # 4. 裁剪图片
            cropped_img = screen[crop_y_min:crop_y_max, crop_x_min:crop_x_max]
            
            # 5. 在裁剪区寻找目标
            target_res = target_tpl.match_in(cropped_img)
            
            if target_res:
                # 6. 坐标转换
                # 同样要处理 target_res 可能是字典或元组的情况
                if isinstance(target_res, dict):
                    rel_x, rel_y = target_res['result']
                else:
                    rel_x, rel_y = target_res
                
                abs_x = int(crop_x_min + rel_x)
                abs_y = int(crop_y_min + rel_y)
                
                self.logger.info(f"Found target in row. Coords: ({abs_x}, {abs_y})")
                return (abs_x, abs_y)
            
        except Exception as e:
            self.logger.error(f"Row search error: {e}")
            import traceback
            traceback.print_exc() # 打印堆栈以便调试
            return None

        return None

    def switch_to_affairs_page(self):
        """
        切换到侧边栏的'事务'页面 (左侧标签)
        """
        # 1. 确保侧边栏已展开
        if not self.expand():
            return False
            
        self.logger.info("Switching to Affairs page...")
        
        # 2. 点击事务页签 (149, 263)
        self.device.click(self.POS_AFFAIRS_TAB)
        self.device.sleep(0.5) # 等待切换动画
        return True

    def scroll_up(self):
        """
        向上滑动 (查看下方内容)
        (227, 830) -> (224, 169)
        移动 1秒，悬停 1.5秒
        """
        self.logger.info("Sidebar: Scrolling UP...")
        self.device.drag_and_hold((227, 830), (224, 169), duration=1.8, hold=1.0)
        self.device.sleep(0.8)

    def reset_to_top(self):
        """
        回到顶部 (列表归位)
        (222, 317) -> (201, 1243)
        移动 1秒，悬停 1秒
        """
        self.logger.info("Sidebar: Resetting to TOP...")
        self.device.drag_and_hold((222, 317), (201, 1243), duration=1.0, hold=1.0)
        self.device.sleep(0.8)

    def get_idle_march_queues(self):
        """
        获取空闲行军队列数量
        逻辑:
        1. 展开侧边栏
        2. 点击行军页面按钮
        3. 循环检测 sidebar_queue_check.png
        4. 计算空闲数量并保存
        :return: int 空闲队列数量
        """
        self.logger.info(get_text("log_sidebar_checking_queues"))

        # 1. 展开侧边栏
        if not self.expand():
            self.logger.error(get_text("log_sidebar_expand_failed"))
            return 0

        # 2. 点击行军页面按钮
        self.device.click(self.POS_MARCH_PAGE_BTN)
        self.device.sleep(0.4) # 等待切换

        # 3. 获取用户设置的总队列数
        total_slots = self.data.get_cfg("modules.general.total_march_slots", 5)
        
        # 4. 循环检测
        # 假设: 队列从上到下排列，如果上面的忙碌，下面的才可能是空闲？
        # 或者: 只要有一个空闲，它下面的所有队列也都是空闲的？(通常游戏逻辑如此)
        # 逻辑: 找到第一个"没有 sidebar_queue_check.png" (即空闲) 的位置
        
        first_idle_index = -1
        
        # 截取屏幕一次，提高效率 (假设所有队列都在一屏内)
        screen_path = self.device._save_snapshot("march_check")
        if not screen_path:
            return 0
        screen = cv2.imread(screen_path)
        if screen is None:
            return 0

        for i in range(total_slots):
            if i >= len(self.MARCH_QUEUE_AREAS):
                break
                
            area = self.MARCH_QUEUE_AREAS[i]
            x1, y1, x2, y2 = area
            
            # 裁剪区域
            cropped = screen[y1:y2, x1:x2]
            
            # 检测忙碌图标 (sidebar_queue_check.png)
            # 如果存在 -> 忙碌
            # 如果不存在 -> 空闲
            if not self.IMG_SIDEBAR_QUEUE_CHECK.match_in(cropped):
                first_idle_index = i
                self.logger.info(get_text("log_sidebar_queue_idle_found", i + 1))
                break
        
        # 5. 计算结果
        if first_idle_index != -1:
            # 如果在索引 i 处发现空闲，说明从 i 开始到底部都是空闲的
            # 例如: 总数 5，索引 2 (第3个) 空闲 -> 空闲数为 5 - 2 = 3 (即 3, 4, 5)
            idle_count = total_slots - first_idle_index
        else:
            # 循环结束都没 break，说明全部忙碌
            idle_count = 0
            
        self.logger.info(get_text("log_sidebar_idle_count", idle_count))
        
        # 6. 保存并更新
        self.idle_march_count = idle_count
        self.data.set_stat("sidebar.idle_queues", idle_count)
        
        return idle_count