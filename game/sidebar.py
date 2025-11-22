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
        self.logger = logging.getLogger("Game.Sidebar")
        
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
        self.POS_TOWN_PAGE_BTN = (170, 270)
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
        self.logger.info("Expanding sidebar...")
        
        

        for i in range(3):
            self.logger.info(f"Expand attempt {i+1}/3")
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
                    self.logger.warning("Neither btn_town nor btn_go_map found, skipping click.")

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