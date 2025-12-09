# -*- coding: utf-8 -*-
import time
import os
import logging
from airtest.core.api import Template
from i18n.i18n import get_text

class MapSearcher:
    """
    通用地图搜索组件
    负责：进出野外 -> 打开搜索菜单 -> 选图标 -> 调等级 -> 搜索 -> 结果校验(RGB) -> 点击定位
    """
    
    # === 坐标常量 ===
    POS_SLIDER_LEFT = (120, 1053) # 滑动条最左侧 (Lv.1 归零用)
    POS_BTN_MINUS   = (69, 1053)  # 减号 (归零用)
    POS_BTN_PLUS    = (487, 1053) # 加号 (调级用)
    
    # 滑动相关 (在图标区域滑动)
    SWIPE_START     = (636, 898)
    SWIPE_END       = (311, 880)

    # === 图标映射 ===
    ICON_MAP = {
        "beast":  r"assets/images/map_level/beast.png",
        "terror": r"assets/images/map_level/terror.png",
        "bread":  r"assets/images/map_level/bread.png",
        "wood":   r"assets/images/map_level/wood.png",
        "stone":  r"assets/images/map_level/stone.png",
        "iron":   r"assets/images/map_level/iron.png"
    }

    # 定义资源类型集合，用于判断按钮逻辑
    RESOURCE_TYPES = {"bread", "wood", "stone", "iron"}

    def __init__(self, device, data):
        self.device = device
        self.data = data
        self.logger = logging.getLogger(f"{data.instance_id}.MapSearcher")

        # === 核心资源加载 ===
        # 基础导航
        self.IMG_FIND = Template(r"assets/images/home/find.png", threshold=0.9)
        self.IMG_BTN_GO_MAP = Template(r"assets/images/home/btn_go_map.png", threshold=0.9)
        
        # [修改点 2] 加上 rgb=True 确保准确识别灰色状态
        self.IMG_GREY_MINUS = Template(r"assets/images/map_level/grey_minus.png", threshold=0.9, rgb=True)
        
        # 搜索与确认按钮 (Nuitka 兼容路径)
        self.IMG_BTN_SEARCH = Template(r"assets/images/map_level/btn_search.png", threshold=0.9)
        
        # 目标确认按钮 (开启 RGB 校验)
        self.IMG_BTN_ORANGE = Template(r"assets/images/map_level/btn_orange.png", threshold=0.9, rgb=True)
        self.IMG_BTN_GATHER = Template(r"assets/images/map_level/btn_gather.png", threshold=0.9, rgb=True)
        self.IMG_BTN_RALLY  = Template(r"assets/images/map_level/btn_rally.png",  threshold=0.9, rgb=True)

    def run(self, target_type, target_level):
        """
        执行完整的搜索流程 (带重试机制)
        :return: bool (True=成功找到并点击, False=彻底失败)
        """
        max_retries = 2
        
        for attempt in range(max_retries):
            self.logger.info(get_text("log_map_search_start", target_type, target_level) + f" (Attempt {attempt+1}/{max_retries})")
            
            # 1. 环境检查 (Ensure Wild)
            if not self._step_ensure_wild():
                continue 
                
            # 2. 点击放大镜
            if not self._step_click_find():
                continue 
                
            # 3. 寻找并选择图标
            if not self._step_select_icon(target_type):
                continue 
                
            # 4 & 5. 检查与调整等级
            self._step_adjust_level(target_level)
            
            # 6. 点击搜索按钮
            if not self._step_click_search_btn():
                self.logger.warning("搜索按钮未找到")
                continue

            # 7 & 8. 结果校验与定位点击 (Verify & Click)
            if self._step_validate_and_click_target(target_type):
                self.logger.info(get_text("log_map_search_finish"))
                return True 
            
            # 如果校验失败
            self.logger.warning(f"搜索后未找到有效目标 [{target_type}]，准备重试...")
            self.device.sleep(2.0)

        # 循环结束仍未成功
        self.logger.error(f"连续 {max_retries} 次未找到目标 [{target_type} Lv.{target_level}]，建议推迟任务。")
        return False

    def _step_ensure_wild(self):
        """步骤 1: 确保在野外"""
        self.device.ensure_home()
        if self.device.exists(self.IMG_BTN_GO_MAP):
            self.logger.info(get_text("log_ensure_wild_success") + " (Switching)")
            self.device.click(self.IMG_BTN_GO_MAP)
            self.device.sleep(1.5)
        else:
            self.logger.info(get_text("log_ensure_wild_success"))
        return True

    def _step_click_find(self):
        """步骤 2: 点击放大镜"""
        if self.device.exists(self.IMG_FIND):
            self.logger.info(get_text("log_click_find"))
            self.device.click(self.IMG_FIND)
            self.device.sleep(0.8)
            return True
        else:
            self.logger.error(get_text("err_find_icon_missing"))
            return False

    def _step_select_icon(self, target_type):
        """步骤 3: 寻找目标图标 (带滑动)"""
        path = self.ICON_MAP.get(target_type)
        if not path:
            self.logger.error(f"Unknown target type: {target_type}")
            return False
            
        tpl = Template(path, threshold=0.9)
        
        for i in range(3):
            if self.device.exists(tpl):
                self.logger.info(get_text("log_target_icon_found", target_type))
                self.device.click(tpl)
                self.device.sleep(0.5)
                return True
            
            if i < 2:
                self.logger.info(get_text("log_target_icon_not_found", target_type))
                self.device.swipe(self.SWIPE_START, self.SWIPE_END)
                self.device.sleep(1.0)
        
        self.logger.error(get_text("err_target_icon_missing", target_type))
        return False

    def _step_adjust_level(self, target_level):
        """步骤 4 & 5: 检查并调整等级"""
        img_level_path = f"assets/images/map_level/{target_level}.png"
        
        # 检查是否已匹配
        if os.path.exists(img_level_path):
            if self.device.exists(Template(img_level_path, threshold=0.9)):
                self.logger.info(get_text("log_search_level_match", target_level))
                return

        # 归零
        self.logger.info(get_text("log_search_level_reset"))
        self.device.click(self.POS_SLIDER_LEFT)
        self.device.sleep(0.2)
        
        for _ in range(10):
            if self.device.exists(self.IMG_GREY_MINUS):
                break
            self.device.click(self.POS_BTN_MINUS)
            
        # 递增
        clicks_needed = target_level - 1
        if clicks_needed > 0:
            self.logger.info(get_text("log_search_level_adjust", clicks_needed))
            for _ in range(clicks_needed):
                self.device.adb.touch(self.POS_BTN_PLUS)
                time.sleep(0.1) 
            self.device.sleep(0.5)

    def _step_click_search_btn(self):
        """步骤 6: 点击搜索按钮"""
        self.logger.info(get_text("log_click_search_btn"))
        if self.device.click(self.IMG_BTN_SEARCH):
            self.device.sleep(1.5) # 等待镜头移动
            return True
        return False

    def _step_validate_and_click_target(self, target_type):
        """
        步骤 7: 校验搜索结果并点击
        使用 rgb=True 确保精确匹配
        """
        target_btn = None
        
        # [修改点 1] 逻辑简化：资源类用 Gather，其他用 Orange
        if target_type in self.RESOURCE_TYPES:
            target_btn = self.IMG_BTN_GATHER
        else:
            # Beast 或 Terror
            target_btn = self.IMG_BTN_ORANGE

        # 2. 在屏幕上搜索该按钮
        if not self.device.exists(target_btn):
            self.logger.warning(f"未在屏幕上找到目标操作按钮 ({target_type})")
            return False
            
        # 3. 点击按钮
        self.logger.info(f"定位到目标 [{target_type}]，执行点击...")
        self.device.click(target_btn)
        self.device.sleep(1.0)
        
        # 4. Terror 的特殊第2步 (点击集结)
        if target_type == "terror":
            if self.device.exists(self.IMG_BTN_RALLY):
                self.logger.info("点击集结按钮...")
                self.device.click(self.IMG_BTN_RALLY)
                self.device.sleep(1.0)
                return True
            else:
                self.logger.warning("点击第1步后未发现集结按钮 (btn_rally.png)")
                return False
        
        return True